"""Changes on the board (web side): who may make them, what is queued,
what the board shows straight away, and links to Chronicle."""

import pytest
from django.contrib.auth.models import Group

from apps.cves.models import CVECase
from apps.logbook.models import PriorityItem
from apps.planner.models import (
    PlannerChange,
    PlannerLink,
    PlannerTask,
    PlannerUserConnection,
)


@pytest.fixture
def anna(django_user_model):
    return django_user_model.objects.create_user("anna", email="anna@fynbus.dk", password="x")


@pytest.fixture
def connected(anna):
    PlannerUserConnection.objects.create(user=anna, account_upn="anna@fynbus.dk",
                                         sealed_token_cache="x", home_account_id="h")
    return anna


@pytest.mark.django_db
def test_unconnected_editor_sees_no_controls_and_cannot_post(client, anna, web, mirrored):
    client.force_login(anna)
    html = client.get("/planner/").content.decode()
    assert "Tilføj opgave" not in html and "planner:complete" not in html and "/complete/" not in html
    assert client.post("/planner/task/t1/complete/", {"done": "1"}).status_code == 403
    assert client.post("/planner/bucket/b1/add/", {"title": "x"}).status_code == 403
    assert not PlannerChange.objects.exists()


@pytest.mark.django_db
def test_viewer_cannot_write_even_if_connected(client, web, mirrored, django_user_model):
    vera = django_user_model.objects.create_user("vera")
    vera.groups.add(Group.objects.get_or_create(name="Viewer")[0])
    PlannerUserConnection.objects.create(user=vera, sealed_token_cache="x", home_account_id="h")
    client.force_login(vera)
    assert client.post("/planner/task/t1/complete/", {"done": "1"}).status_code == 403


@pytest.mark.django_db
def test_connected_editor_gets_controls(client, connected, web, mirrored):
    client.force_login(connected)
    html = client.get("/planner/").content.decode()
    assert "Tilføj opgave" in html and "/planner/task/t1/complete/" in html
    assert "anna@fynbus.dk" in html and "Flyt til" in html


@pytest.mark.django_db
def test_complete_is_shown_at_once_and_queued(client, connected, web, mirrored):
    client.force_login(connected)
    html = client.post("/planner/task/t1/complete/", {"done": "1"}).content.decode()
    assert "is-done" in html and "Gemmer i Planner" in html and "every 2s" in html
    assert PlannerTask.objects.get(id="t1").is_complete
    change = PlannerChange.objects.get()
    assert (change.kind, change.task_id, change.user) == ("complete", "t1", connected)


@pytest.mark.django_db
def test_reopen(client, connected, web, mirrored):
    client.force_login(connected)
    client.post("/planner/task/t2/complete/", {"done": "0"})
    assert PlannerChange.objects.get().kind == "reopen" and not PlannerTask.objects.get(id="t2").is_complete


@pytest.mark.django_db
def test_drag_queues_bucket_and_neighbours(client, connected, web, mirrored):
    client.force_login(connected)
    client.post("/planner/task/t1/move/", {"bucket": "b2", "prev": "", "next": "b"})
    change = PlannerChange.objects.get()
    assert change.payload == {"bucket_id": "b2", "order_hint": " b!"}
    assert PlannerTask.objects.get(id="t1").bucket_id == "b2"


@pytest.mark.django_db
def test_move_from_menu_goes_to_top_and_reloads(client, connected, web, mirrored):
    client.force_login(connected)
    response = client.post("/planner/task/t1/move/", {"bucket": "b2", "from_menu": "1"})
    assert response["HX-Refresh"] == "true"
    assert PlannerChange.objects.get().payload["order_hint"] == " !"


@pytest.mark.django_db
def test_move_to_unknown_bucket_or_task_is_404(client, connected, web, mirrored):
    client.force_login(connected)
    assert client.post("/planner/task/t1/move/", {"bucket": "nope"}).status_code == 404
    assert client.post("/planner/task/nope/move/", {"bucket": "b1"}).status_code == 404


@pytest.mark.django_db
def test_add_shows_placeholder_and_queues(client, connected, web, mirrored):
    client.force_login(connected)
    html = client.post("/planner/bucket/b1/add/", {"title": "  Ny   <b>opgave</b> "}).content.decode()
    assert "Opretter i Planner" in html and "&lt;b&gt;" in html
    assert PlannerChange.objects.get().payload == {"bucket_id": "b1", "title": "Ny <b>opgave</b>"}
    assert client.post("/planner/bucket/b1/add/", {"title": "  "}).status_code == 204


@pytest.mark.django_db
def test_change_poll_returns_real_card_once_created(client, connected, web, mirrored):
    client.force_login(connected)
    client.post("/planner/bucket/b1/add/", {"title": "Ny"})
    change = PlannerChange.objects.get()
    assert "Opretter" in client.get(f"/planner/change/{change.pk}/").content.decode()
    PlannerTask.objects.create(id="new1", plan_id=PlannerTask.objects.first().plan_id, bucket_id="b1", title="Ny")
    PlannerChange.objects.filter(pk=change.pk).update(status="done", task_id="new1")
    html = client.get(f"/planner/change/{change.pk}/").content.decode()
    assert 'data-task="new1"' in html and "every 2s" not in html


@pytest.mark.django_db
def test_failed_change_is_explained_on_the_card(client, connected, web, mirrored):
    client.force_login(connected)
    client.post("/planner/task/t1/complete/", {"done": "1"})
    change = PlannerChange.objects.get()
    PlannerChange.objects.filter(pk=change.pk).update(status="failed", message="Er du medlem af planens gruppe?")
    html = client.get(f"/planner/change/{change.pk}/").content.decode()
    assert "Ikke gemt i Planner" in html and "medlem" in html


@pytest.mark.django_db
def test_create_priority_from_card(client, connected, web, mirrored):
    client.force_login(connected)
    html = client.post("/planner/task/t1/link/", {"action": "priority"}).content.decode()
    item = PriorityItem.objects.get()
    assert item.title == "Fornyelse af funktionscertifikater" and item.priority == "high"
    assert item.notes.startswith("Med MitID Erhverv.") and item.appearances.count() == 1
    assert f"Prioriteret opgave #{item.pk}" in html
    change = PlannerChange.objects.get()
    assert change.kind == "link" and change.payload["label"] == "Prioriteret opgave"
    assert change.payload["url"] == f"http://testserver/logbook/priorities/{item.pk}/history/"
    assert PlannerLink.objects.get().priority_item == item


@pytest.mark.django_db
def test_create_case_from_card(client, connected, web, mirrored):
    client.force_login(connected)
    client.post("/planner/task/t1/link/", {"action": "case"})
    case = CVECase.objects.get()
    assert case.kind == "task" and case.due_date.isoformat() == "2026-12-31" and case.created_by == connected
    assert PlannerChange.objects.get().payload["label"] == "Sag"


@pytest.mark.django_db
def test_link_existing_once(client, connected, web, mirrored):
    case = CVECase.objects.create(kind="incident", title="Nedbrud")
    client.force_login(connected)
    form = client.get("/planner/task/t1/link/").content.decode()
    assert f'value="c{case.pk}"' in form
    client.post("/planner/task/t1/link/", {"action": "existing", "target": f"c{case.pk}"})
    client.post("/planner/task/t1/link/", {"action": "existing", "target": f"c{case.pk}"})
    assert PlannerLink.objects.count() == 1 and PlannerChange.objects.count() == 1
    assert client.post("/planner/task/t1/link/", {"action": "existing", "target": "x1"}).status_code == 400


@pytest.mark.django_db
def test_backlink_on_case_and_priority_pages(client, connected, web, mirrored):
    client.force_login(connected)
    client.post("/planner/task/t1/link/", {"action": "case"})
    client.post("/planner/task/t1/link/", {"action": "priority"})
    case, item = CVECase.objects.get(), PriorityItem.objects.get()
    for url in (case.get_absolute_url(), f"/logbook/priorities/{item.pk}/history/"):
        html = client.get(url).content.decode()
        assert "Planner: Fornyelse af funktionscertifikater" in html and "/Home/Task/t1" in html
