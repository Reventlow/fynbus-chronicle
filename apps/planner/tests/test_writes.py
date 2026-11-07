"""The sync container making editors' changes in Planner (Graph faked)."""

import pytest
from django.utils import timezone

from apps.planner.graph import GraphError, PlannerError
from apps.planner.models import (
    PlannerChange,
    PlannerPlan,
    PlannerTask,
    PlannerUserConnection,
    SyncState,
)
from apps.planner.sync import mirror_plan
from apps.planner.writes import process_changes, reference_key

from .conftest import PLAN, FakeGraph


class WriteGraph(FakeGraph):
    """FakeGraph that also takes PATCH/POST, checks etags, and records writes."""

    def __init__(self, fail=None, races=0):
        super().__init__()
        self.writes, self.fail, self.races, self.version = [], fail, races, 1
        for path, item in list(self.data.items()):
            if path.startswith("/planner/tasks/") or path.endswith("/details"):
                item.setdefault("@odata.etag", 'W/"v1"')
        for t in self.data[f"/planner/plans/{PLAN}/tasks"]["value"] + \
                self.data["https://graph.microsoft.com/v1.0/next-page"]["value"]:
            self.data[f"/planner/tasks/{t['id']}"] = dict(t, planId=PLAN)
            self.data.setdefault(f"/planner/tasks/{t['id']}/details", {"@odata.etag": 'W/"d1"', "references": {}})

    def patch(self, path, body, etag):
        if self.fail:
            raise GraphError(self.fail, "Forbidden", path)
        if self.races:
            self.races -= 1
            raise GraphError(412, "PreconditionFailed", path)
        assert etag == self.data[path]["@odata.etag"], "must send the current etag"
        self.writes.append(("PATCH", path, body))
        item = self.data[path]
        for key, value in body.items():
            if isinstance(value, dict):
                item[key] = {**(item.get(key) or {}), **value}
            else:
                item[key] = value
        self.version += 1
        item["@odata.etag"] = f'W/"v{self.version}"'
        return dict(item)

    def post(self, path, body):
        if self.fail:
            raise GraphError(self.fail, "Forbidden", path)
        self.writes.append(("POST", path, body))
        task = {"id": "new1", "percentComplete": 0, "@odata.etag": 'W/"n1"', **body}
        self.data[f"/planner/tasks/{task['id']}"] = task
        return task


class Auth:
    users = []

    @classmethod
    def for_user(cls, user):
        conn = PlannerUserConnection.objects.filter(user=user).first()
        if not conn:
            raise PlannerError("Din Microsoft-konto er ikke forbundet til Planner.")
        cls.users.append(user.username)
        return cls()

    def access_token(self):
        return "tok"


@pytest.fixture
def anna(django_user_model, planner):
    user = django_user_model.objects.create_user("anna", email="anna@fynbus.dk")
    PlannerUserConnection.objects.create(user=user, sealed_token_cache="x", home_account_id="h")
    return user


def _run(graph, kind, task_id="", user=None, **payload):
    change = PlannerChange.objects.create(kind=kind, task_id=task_id, payload=payload, user=user)
    process_changes(Auth, lambda token: graph)
    change.refresh_from_db()
    return change


@pytest.fixture
def graph(planner):
    g = WriteGraph()
    mirror_plan(g, PLAN)
    return g


@pytest.mark.django_db
def test_complete_and_reopen_with_the_editors_token(graph, anna):
    Auth.users.clear()
    change = _run(graph, "complete", "t1", anna)
    assert change.status == "done" and Auth.users == ["anna"]
    assert graph.writes == [("PATCH", "/planner/tasks/t1", {"percentComplete": 100})]
    assert PlannerTask.objects.get(id="t1").is_complete
    _run(graph, "reopen", "t1", anna)
    assert PlannerTask.objects.get(id="t1").percent_complete == 0


@pytest.mark.django_db
def test_move_sends_bucket_and_order_hint(graph, anna):
    _run(graph, "move", "t1", anna, bucket_id="b2", order_hint="a b!")
    assert graph.writes[-1] == ("PATCH", "/planner/tasks/t1", {"bucketId": "b2", "orderHint": "a b!"})
    assert PlannerTask.objects.get(id="t1").bucket_id == "b2"


@pytest.mark.django_db
def test_create_puts_card_on_top_and_in_the_mirror(graph, anna):
    change = _run(graph, "create", user=anna, bucket_id="b1", title="Ny opgave")
    method, path, body = graph.writes[-1]
    assert (method, path) == ("POST", "/planner/tasks")
    assert body == {"planId": PLAN, "bucketId": "b1", "title": "Ny opgave", "orderHint": " !"}
    assert change.task_id == "new1" and PlannerTask.objects.get(id="new1").bucket_id == "b1"


@pytest.mark.django_db
def test_link_names_a_free_label_applies_it_and_adds_reference(graph, anna):
    url = "https://chronicle.fynbus.net/logbook/priorities/12/history/"
    change = _run(graph, "link", "t3", anna, url=url, alias="Chronicle: Prioriteret opgave #12",
                  label="Prioriteret opgave")
    assert change.status == "done", change.message
    plan_patch, task_patch, details_patch = graph.writes
    # category16 is taken ("Ubehandlet"), category2 is unnamed but unused: category1 is first free.
    assert plan_patch == ("PATCH", f"/planner/plans/{PLAN}/details", {"categoryDescriptions": {"category1": "Prioriteret opgave"}})
    assert task_patch == ("PATCH", "/planner/tasks/t3", {"appliedCategories": {"category1": True}})
    ref = details_patch[2]["references"]
    assert list(ref) == ["https%3A//chronicle%2Efynbus%2Enet/logbook/priorities/12/history/"]
    assert ref[list(ref)[0]]["alias"] == "Chronicle: Prioriteret opgave #12"
    assert PlannerPlan.objects.get(id=PLAN).labels["category1"] == "Prioriteret opgave"
    assert "category1" in PlannerTask.objects.get(id="t3").label_keys


@pytest.mark.django_db
def test_link_reuses_an_existing_label_by_name(graph, anna):
    _run(graph, "link", "t3", anna, url="https://x/", alias="a", label="ubehandlet")
    assert graph.writes[0] == ("PATCH", "/planner/tasks/t3", {"appliedCategories": {"category16": True}})


@pytest.mark.django_db
def test_label_slot_used_as_bare_colour_is_not_taken(graph, anna):
    PlannerTask.objects.filter(id="t1").update(label_keys=["category1", "category16"])
    _run(graph, "link", "t3", anna, url="https://x/", alias="a", label="Sag")
    assert graph.writes[0][2] == {"categoryDescriptions": {"category2": "Sag"}}


@pytest.mark.django_db
def test_etag_race_is_retried_once(planner, anna):
    g = WriteGraph(races=1)
    mirror_plan(g, PLAN)
    assert _run(g, "complete", "t1", anna).status == "done"


@pytest.mark.django_db
def test_forbidden_explains_and_requests_a_sync(planner, anna):
    g = WriteGraph(fail=403)
    mirror_plan(g, PLAN)
    SyncState.objects.filter(pk=1).update(requested_at=None, last_attempt_at=timezone.now())
    change = _run(g, "complete", "t1", anna)
    assert change.status == "failed" and "medlem af planens gruppe" in change.message
    assert SyncState.get().is_requested  # puts the optimistic board state back


@pytest.mark.django_db
def test_change_by_unconnected_editor_fails_without_service_account(graph, django_user_model, planner):
    bob = django_user_model.objects.create_user("bob")
    change = _run(graph, "complete", "t1", bob)
    assert change.status == "failed" and "ikke forbundet" in change.message
    assert graph.writes == []


@pytest.mark.django_db
def test_writes_switched_off_leave_changes_pending(graph, anna, settings):
    from apps.planner.sync import PlannerJob
    settings.PLANNER_WRITES_ENABLED = False
    PlannerChange.objects.create(kind="complete", task_id="t1", user=anna)
    assert PlannerJob(auth_factory=Auth, graph_factory=lambda t: graph).handle_changes() == 0
    assert graph.writes == []


def test_reference_key_encoding():
    assert reference_key("https://a.b/c?x=1#y@z%") == "https%3A//a%2Eb/c?x=1%23y%40z%25"
