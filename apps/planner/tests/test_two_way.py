"""Phases 3-4: linked cards and Chronicle kept in step both ways, and
"Opret i Planner" from a priority or case."""

import pytest
from django.test import RequestFactory
from django.utils import timezone

from apps.cves.models import CVECase, CVEComment
from apps.logbook.models import PriorityItem, PriorityItemAppearance, WeekLog
from apps.planner import linksync
from apps.planner.linksync import chronicle_state, planner_state, reconcile_task
from apps.planner.models import (
    PlannerChange,
    PlannerLink,
    PlannerTask,
    PlannerUserConnection,
)
from apps.planner.sync import mirror_plan
from apps.planner.writes import process_changes

from .conftest import PLAN
from .test_writes import Auth, WriteGraph


@pytest.fixture
def anna(django_user_model, planner):
    user = django_user_model.objects.create_user("anna", email="anna@fynbus.dk", first_name="Anna")
    PlannerUserConnection.objects.create(user=user, sealed_token_cache="x", home_account_id="h")
    return user


@pytest.fixture
def graph(planner):
    g = WriteGraph()
    mirror_plan(g, PLAN)
    return g


@pytest.fixture
def item(planner):
    weeklog = WeekLog.get_or_create_current_week()
    item = PriorityItem.objects.create(origin_weeklog=weeklog, title="Certifikater")
    PriorityItemAppearance.objects.create(priority_item=item, weeklog=weeklog)
    return item


@pytest.fixture
def case(planner):
    return CVECase.objects.create(kind=CVECase.Kind.TASK, title="Opgradering")


def _link(task_id, obj):
    field = "case" if getattr(obj, "is_case", False) else "priority_item"
    task = PlannerTask.objects.get(id=task_id)
    return PlannerLink.objects.create(task_id=task_id, task_title=task.title, **{field: obj},
                                      planner_state=planner_state(task.percent_complete),
                                      chronicle_state=chronicle_state(obj))


class ActingAs:
    """Stand-in for CurrentRequestMiddleware."""

    def __init__(self, user):
        self.request = RequestFactory().post("/")
        self.request.user = user

    def __enter__(self):
        self.token = linksync._request.set(self.request)

    def __exit__(self, *exc):
        linksync._request.reset(self.token)


@pytest.mark.parametrize("percent, state", [(0, "not_started"), (50, "in_progress"), (99, "in_progress"), (100, "done")])
def test_planner_states(percent, state):
    assert planner_state(percent) == state


# --- Planner → Chronicle ------------------------------------------------------------------


@pytest.mark.django_db
def test_completing_card_in_planner_closes_priority(graph, item):
    _link("t1", item)  # t1 is not started, item not started
    graph.data[f"/planner/plans/{PLAN}/tasks"]["value"][0]["percentComplete"] = 100
    counts = mirror_plan(graph, PLAN)
    item.refresh_from_db()
    assert item.status == "completed" and item.closed_at and counts["linked_updated"] == 1
    assert not PlannerChange.objects.exists()  # not echoed back to Planner


@pytest.mark.django_db
def test_card_in_progress_moves_case_and_logs_it(graph, case):
    _link("t1", case)
    graph.data[f"/planner/plans/{PLAN}/tasks"]["value"][0]["percentComplete"] = 50
    mirror_plan(graph, PLAN)
    case.refresh_from_db()
    assert case.state == "patching" and case.state_label == "I gang"
    assert CVEComment.objects.filter(case=case, text__contains="Ændret i Planner").exists()


@pytest.mark.django_db
def test_reopened_card_reopens_completed_priority_on_this_week(graph, item):
    t2 = PlannerTask.objects.get(id="t2")  # completed in Planner
    item.status = "completed"
    item.save()
    _link(t2.id, item)
    graph.data[f"/planner/plans/{PLAN}/tasks"]["value"][1]["percentComplete"] = 0
    mirror_plan(graph, PLAN)
    item.refresh_from_db()
    assert item.status == "not_started" and item.closed_at is None


@pytest.mark.django_db
def test_blocked_priority_stays_blocked_while_card_is_in_progress(graph, item):
    item.status = "blocked"
    item.save()
    link = _link("t3", item)  # t3 is 50 %
    graph.data["https://graph.microsoft.com/v1.0/next-page"]["value"][0]["percentComplete"] = 60
    mirror_plan(graph, PLAN)
    item.refresh_from_db()
    link.refresh_from_db()
    assert item.status == "blocked" and link.planner_state == "in_progress"


@pytest.mark.django_db
def test_first_sight_only_records_states(graph, item):
    link = PlannerLink.objects.create(task_id="t2", priority_item=item)  # e.g. linked before 1.18.0
    reconcile_task(PlannerTask.objects.get(id="t2"))
    link.refresh_from_db()
    item.refresh_from_db()
    assert (link.planner_state, link.chronicle_state) == ("done", "not_started") and item.status == "not_started"


@pytest.mark.django_db
def test_board_change_carries_to_chronicle_as_that_editor(graph, anna, case):
    _link("t1", case)
    PlannerChange.objects.create(kind="complete", task_id="t1", user=anna)
    process_changes(Auth, lambda token: graph)
    case.refresh_from_db()
    assert case.state == "solved" and case.solved_by == anna


# --- Chronicle → Planner ------------------------------------------------------------------


@pytest.mark.django_db
def test_closing_priority_in_chronicle_queues_progress_as_the_editor(graph, anna, item):
    link = _link("t1", item)
    with ActingAs(anna):
        item.status = "completed"
        item.save()
    change = PlannerChange.objects.get()
    assert (change.kind, change.task_id, change.user, change.payload) == ("progress", "t1", anna, {"percent": 100})
    process_changes(Auth, lambda token: graph)
    assert graph.writes[-1] == ("PATCH", "/planner/tasks/t1", {"percentComplete": 100})
    link.refresh_from_db()
    item.refresh_from_db()
    assert link.planner_state == link.chronicle_state == "done" and item.status == "completed"


@pytest.mark.django_db
def test_case_state_from_api_user(graph, anna, case):
    _link("t1", case)
    request = RequestFactory().patch("/")
    from django.contrib.auth.models import AnonymousUser
    request.user, request.api_user = AnonymousUser(), anna
    token = linksync._request.set(request)
    try:
        case.set_state("patching")
    finally:
        linksync._request.reset(token)
    assert PlannerChange.objects.get().payload == {"percent": 50}


@pytest.mark.django_db
def test_no_user_no_push_and_a_note(graph, item):
    link = _link("t1", item)
    item.auto_close()
    link.refresh_from_db()
    assert not PlannerChange.objects.exists() and "uden en bruger" in link.sync_note


@pytest.mark.django_db
def test_unconnected_editor_gets_a_note_not_the_service_account(graph, django_user_model, item):
    bob = django_user_model.objects.create_user("bob", first_name="Bob")
    link = _link("t1", item)
    with ActingAs(bob):
        item.status = "ongoing"
        item.save()
    link.refresh_from_db()
    assert not PlannerChange.objects.exists() and "Bob har ikke forbundet" in link.sync_note


@pytest.mark.django_db
def test_unrelated_save_sends_nothing(graph, anna, item):
    _link("t1", item)
    with ActingAs(anna):
        item.title = "Nyt navn"
        item.save()
        item.touch()
    assert not PlannerChange.objects.exists()


# --- Opret i Planner ----------------------------------------------------------------------


@pytest.fixture
def connected_client(client, anna, graph):
    client.force_login(anna)
    return client


@pytest.mark.django_db
def test_create_from_case_queues_full_card(connected_client, anna, case):
    case.due_date = timezone.localdate().replace(month=12, day=31)
    case.assessment = "Plan"
    case.save()
    response = connected_client.post("/planner/create-from/", {"target": f"c{case.pk}", "bucket": "b2"})
    assert response.status_code == 302 and response["Location"] == case.get_absolute_url()
    data = PlannerChange.objects.get(kind="create").payload
    assert data["link"] == {"case": case.pk} and data["bucket_id"] == "b2" and data["title"] == "Opgradering"
    assert data["description"] == "Plan" and data["due"].endswith("-12-31") and data["percent"] == 0
    assert data["label"] == "Sag" and data["url"].endswith(case.get_absolute_url())
    # A second click while it is on its way does nothing.
    connected_client.post("/planner/create-from/", {"target": f"c{case.pk}", "bucket": "b2"})
    assert PlannerChange.objects.filter(kind="create").count() == 1


@pytest.mark.django_db
def test_create_from_makes_linked_labelled_card(graph, anna, item, connected_client):
    item.notes = "Noter"
    item.status = "ongoing"
    item.save()
    connected_client.post("/planner/create-from/", {"target": f"p{item.pk}", "bucket": "b1"})
    process_changes(Auth, lambda token: graph)
    change = PlannerChange.objects.get(kind="create")
    assert change.status == "done", change.message
    post = next(w for w in graph.writes if w[0] == "POST")[2]
    assert post["percentComplete"] == 50 and post["bucketId"] == "b1"
    link = PlannerLink.objects.get(priority_item=item)
    assert link.task_id == "new1" and link.planner_state == link.chronicle_state == "in_progress"
    paths = [w[1] for w in graph.writes]
    assert "/planner/tasks/new1/details" in paths and f"/planner/plans/{PLAN}/details" in paths
    assert PlannerTask.objects.get(id="new1").description == "Noter"
    item.refresh_from_db()
    assert item.status == "ongoing"  # unchanged by its own new card


@pytest.mark.django_db
def test_create_from_needs_own_connection(client, django_user_model, graph, item):
    client.force_login(django_user_model.objects.create_user("bob"))
    assert client.post("/planner/create-from/", {"target": f"p{item.pk}", "bucket": "b1"}).status_code == 403


@pytest.mark.django_db
def test_detail_pages_offer_create_or_show_link(connected_client, item, case):
    page = connected_client.get(f"/logbook/priorities/{item.pk}/history/").content.decode()
    assert "Opret i Planner" in page and f'value="p{item.pk}"' in page
    _link("t1", case)
    page = connected_client.get(case.get_absolute_url()).content.decode()
    assert "Opret i Planner" not in page and "/Home/Task/t1" in page


@pytest.mark.django_db
def test_detail_page_shows_sync_note(connected_client, case):
    link = _link("t1", case)
    PlannerLink.objects.filter(pk=link.pk).update(sync_note="Ikke sendt til Planner: Bob har ikke forbundet")
    assert "Bob har ikke forbundet" in connected_client.get(case.get_absolute_url()).content.decode()
