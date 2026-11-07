"""The ServiceDesk page: tickets sorted into mine / not assigned / others,
links to priorities and cases, the internal note, and the pill."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from apps.cves.models import CVECase
from apps.logbook.models import (
    HelpdeskTicket,
    PriorityItem,
    PriorityItemAppearance,
    WeekLog,
)
from apps.logbook.services import ticket_mirror
from apps.logbook.services.servicedesk import ServiceDeskClient
from apps.servicedesk import views
from apps.servicedesk.models import TicketLink

SD = "https://servicedesk.example.test"
NOW = timezone.now()


class Notes:
    """Stands in for ServiceDeskClient.add_note: records, answers ``error``."""

    def __init__(self, error=None):
        self.calls, self.error = [], error

    def __call__(self, request_id, html):
        self.calls.append((request_id, html))
        return self.error


@pytest.fixture
def notes(monkeypatch):
    fake = Notes()
    monkeypatch.setattr(ServiceDeskClient, "add_note", fake)
    return fake


@pytest.fixture
def sd(settings):
    settings.SERVICEDESK_URL = SD
    settings.SERVICEDESK_API_KEY = "test-key"


def ticket(sdp_id, *, technician="", email="", days=3, closed_days_ago=None, subject="Printer virker ikke",
           status="Åben"):
    closed = closed_days_ago is not None
    return HelpdeskTicket.objects.create(
        sdp_id=sdp_id, subject=subject, technician=technician, technician_email=email,
        created_at=NOW - timedelta(days=days), status="Lukket" if closed else status, is_open=not closed,
        closed_at=(NOW - timedelta(days=closed_days_ago)) if closed else None)


@pytest.fixture
def anna(django_user_model, client):
    user = django_user_model.objects.create_user("anna", email="Anna@FynBus.dk", first_name="Anna",
                                                 last_name="Hansen")
    client.force_login(user)
    return user


def _groups(response):
    return {g["key"]: [t.sdp_id for t in g["tickets"]] for g in response.context["groups"]}


# --- sorting ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_open_tickets_sorted_into_mine_unassigned_and_others(client, anna, sd):
    ticket(1, technician="Anna Hansen", email="anna@fynbus.dk", days=2)
    ticket(2, technician="Anna Hansen", email="anna@fynbus.dk", days=40)
    ticket(3, days=1)
    ticket(4, technician="Morten", email="morten@fynbus.dk")
    ticket(5, technician="Anna Hansen", days=5)  # no e-mail mirrored yet: name match
    ticket(6, technician="Anna", email="anna@fynbus.dk", closed_days_ago=1)  # closed: not on Uløste

    response = client.get(reverse("servicedesk:tickets"))
    assert response.status_code == 200
    # oldest first
    assert _groups(response) == {"mine": [2, 5, 1], "unassigned": [3], "others": [4]}
    assert response.context["open_count"] == 5


@pytest.mark.django_db
def test_closed_tab_shows_recently_closed_newest_first(client, anna, sd):
    ticket(1, technician="Anna Hansen", email="anna@fynbus.dk", days=20, closed_days_ago=10)
    ticket(2, technician="Anna Hansen", email="anna@fynbus.dk", days=5, closed_days_ago=2)
    ticket(3, closed_days_ago=50, days=60)
    ticket(4, technician="Morten", closed_days_ago=3)
    ticket(5)  # open

    response = client.get(reverse("servicedesk:tickets"), {"vis": "closed"})
    assert _groups(response) == {"mine": [2, 1], "unassigned": [], "others": [4]}
    response = client.get(reverse("servicedesk:tickets"), {"vis": "closed", "dage": "90"})
    assert _groups(response)["unassigned"] == [3]
    # an unknown period falls back to 30 days
    assert client.get(reverse("servicedesk:tickets"), {"vis": "closed", "dage": "x"}).context["days"] == 30


@pytest.mark.django_db
def test_ticket_links_to_servicedesk_and_shows_age(client, anna, sd):
    ticket(4711, days=12)
    ticket(4712, days=20, closed_days_ago=5)
    html = client.get(reverse("servicedesk:tickets")).content.decode()
    assert f"{SD}/WorkOrder.do?woMode=viewWO&amp;woID=4711" in html
    assert "12 dage" in html
    html = client.get(reverse("servicedesk:tickets"), {"vis": "closed"}).content.decode()
    assert "15 dage" in html  # took 15 days to close


@pytest.mark.parametrize("delta, text", [
    (timedelta(minutes=20), "under 1 t"), (timedelta(hours=5), "5 t"),
    (timedelta(days=1, hours=2), "1 dag"), (timedelta(days=12), "12 dage"),
])
def test_age_text(delta, text):
    assert views.age_text(delta) == text


@pytest.mark.django_db
def test_page_needs_login(client):
    response = client.get(reverse("servicedesk:tickets"))
    assert response.status_code == 302


# --- the mirror keeps the technician's e-mail ---------------------------------------------


def test_mirror_keeps_technician_email():
    values = ticket_mirror.ticket_values({
        "id": "9", "created_time": {"value": "1700000000000"}, "status": {"name": "Åben"},
        "technician": {"name": "Anna Hansen", "email_id": "Anna@FynBus.dk"},
    })
    assert values["technician"] == "Anna Hansen" and values["technician_email"] == "anna@fynbus.dk"
    assert ticket_mirror.ticket_values({"id": "9", "created_time": {"value": "1700000000000"},
                                        "technician": None})["technician_email"] == ""


# --- linking ------------------------------------------------------------------------------


@pytest.fixture
def week():
    return WeekLog.get_or_create_current_week()


@pytest.mark.django_db
def test_link_to_existing_priority_adds_internal_note(client, anna, sd, notes, week):
    t = ticket(4711)
    item = PriorityItem.objects.create(origin_weeklog=week, title="Printere på værkstedet")
    response = client.post(reverse("servicedesk:link", args=[4711]), {"action": "existing", "target": f"p{item.pk}"})
    assert response.status_code == 200
    link = TicketLink.objects.get()
    assert (link.sdp_id, link.priority_item, link.subject, link.created_by) == (4711, item, t.subject, anna)
    assert link.note_added_at and not link.note_error
    (sdp_id, html), = notes.calls
    assert sdp_id == 4711
    assert f"http://testserver/logbook/priorities/{item.pk}/history/" in html
    assert "Printere på værkstedet" in html and "Anna Hansen" in html and "Knyttet til" in html
    # the row now shows the link
    assert "Printere på værkstedet" in response.content.decode()


@pytest.mark.django_db
def test_link_twice_sends_one_note(client, anna, sd, notes):
    ticket(4711)
    case = CVECase.objects.create(kind=CVECase.Kind.TASK, title="Ny printer")
    for _ in range(2):
        client.post(reverse("servicedesk:link", args=[4711]), {"action": "existing", "target": f"c{case.pk}"})
    assert TicketLink.objects.count() == 1 and len(notes.calls) == 1


@pytest.mark.django_db
def test_new_priority_and_case_from_ticket(client, anna, sd, notes, week):
    ticket(4711, subject="VPN driller", status="I gang")
    client.post(reverse("servicedesk:link", args=[4711]), {"action": "priority"})
    client.post(reverse("servicedesk:link", args=[4711]), {"action": "case"})
    item = PriorityItem.objects.get(title="VPN driller")
    assert item.status == PriorityItem.Status.ONGOING
    assert PriorityItemAppearance.objects.filter(priority_item=item, weeklog=week).exists()
    case = CVECase.objects.get(title="VPN driller")
    assert case.kind == CVECase.Kind.TASK and case.state == CVECase.State.PATCHING
    assert TicketLink.objects.filter(sdp_id=4711).count() == 2


@pytest.mark.django_db
def test_failed_note_is_shown_and_can_be_retried(client, anna, sd, notes):
    ticket(4711)
    case = CVECase.objects.create(kind=CVECase.Kind.TASK, title="Ny printer")
    notes.error = "ServiceDesk afviste noten (HTTP 403). Må API-nøglen skrive noter?"
    html = client.post(reverse("servicedesk:link", args=[4711]),
                       {"action": "existing", "target": f"c{case.pk}"}).content.decode()
    link = TicketLink.objects.get()
    assert link.note_added_at is None and "HTTP 403" in link.note_error
    assert "Ingen note i ServiceDesk" in html and "Prøv igen" in html

    notes.error = None
    html = client.post(reverse("servicedesk:retry-note", args=[link.pk])).content.decode()
    link.refresh_from_db()
    assert link.note_added_at and not link.note_error and "Ingen note i ServiceDesk" not in html
    assert len(notes.calls) == 2


@pytest.mark.django_db
def test_unlink_removes_link_and_notes_it(client, anna, sd, notes):
    ticket(4711)
    case = CVECase.objects.create(kind=CVECase.Kind.TASK, title="Ny printer")
    client.post(reverse("servicedesk:link", args=[4711]), {"action": "existing", "target": f"c{case.pk}"})
    link = TicketLink.objects.get()
    response = client.post(reverse("servicedesk:unlink", args=[link.pk]))
    assert response.status_code == 200 and not TicketLink.objects.exists()
    assert "Ikke længere knyttet til" in notes.calls[-1][1]


@pytest.mark.django_db
def test_viewer_cannot_link(client, django_user_model, sd, notes):
    user = django_user_model.objects.create_user("vera")
    user.groups.add(Group.objects.get_or_create(name="Viewer")[0])
    client.force_login(user)
    ticket(4711)
    assert client.get(reverse("servicedesk:tickets")).context["can_link"] is False
    assert client.get(reverse("servicedesk:link", args=[4711])).status_code == 403
    assert client.post(reverse("servicedesk:link", args=[4711]), {"action": "case"}).status_code == 403
    assert not CVECase.objects.exists() and not notes.calls


@pytest.mark.django_db
def test_link_form_lists_open_targets(client, anna, sd, week):
    ticket(4711)
    PriorityItem.objects.create(origin_weeklog=week, title="Åben opgave")
    PriorityItem.objects.create(origin_weeklog=week, title="Færdig opgave", status=PriorityItem.Status.COMPLETED)
    html = client.get(reverse("servicedesk:link", args=[4711])).content.decode()
    assert "Åben opgave" in html and "Færdig opgave" not in html


@pytest.mark.django_db
def test_bad_action_is_refused(client, anna, sd, notes):
    ticket(4711)
    assert client.post(reverse("servicedesk:link", args=[4711]), {"action": "existing", "target": "x1"}).status_code == 400
    assert client.post(reverse("servicedesk:link", args=[9999]), {"action": "case"}).status_code == 404


# --- the note itself ----------------------------------------------------------------------


@pytest.mark.django_db
def test_note_escapes_titles(rf, anna):
    case = CVECase.objects.create(kind=CVECase.Kind.TASK, title="<script>alert(1)</script>")
    link = TicketLink(sdp_id=1, case=case)
    request = rf.get("/")
    request.user = anna
    html = views.note_html(link, request)
    assert "<script>" not in html and "&lt;script&gt;" in html


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.ok = status < 400

    def json(self):
        return self._body


@pytest.mark.parametrize("status, body, expected", [
    (201, {"response_status": {"status": "success", "status_code": 2000}}, None),
    (403, {"response_status": {"status": "failed"}}, "HTTP 403"),
    (404, {}, "findes ikke længere"),
    (400, {"response_status": [{"status": "failed", "messages": [{"message": "Bad input"}]}]}, "Bad input"),
])
def test_add_note_posts_internal_note(settings, monkeypatch, status, body, expected):
    settings.SERVICEDESK_URL, settings.SERVICEDESK_API_KEY = SD + "/", "test-key"
    sent = {}

    def post(url, headers, data, timeout):
        sent.update(url=url, headers=headers, data=data)
        return FakeResponse(status, body)

    monkeypatch.setattr("apps.logbook.services.servicedesk.requests.post", post)
    result = ServiceDeskClient().add_note(4711, "<p>Hej</p>")
    assert sent["url"] == f"{SD}/api/v3/requests/4711/notes"
    assert sent["headers"]["authtoken"] == "test-key"
    assert '"show_to_requester": false' in sent["data"]["input_data"]
    assert '"notify_technician": false' in sent["data"]["input_data"]
    if expected is None:
        assert result is None
    else:
        assert expected in result


def test_add_note_without_settings(settings):
    settings.SERVICEDESK_URL, settings.SERVICEDESK_API_KEY = "", ""
    assert "ikke sat op" in ServiceDeskClient().add_note(1, "x")


# --- the pill on priorities and cases -----------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("page", ["week log", "priority search", "case list", "dashboard week", "dashboard cases",
                                  "priority page", "case page"])
def test_linked_items_have_a_servicedesk_pill(client, anna, sd, week, page):
    item = PriorityItem.objects.create(origin_weeklog=week, title="Printere")
    PriorityItemAppearance.objects.create(priority_item=item, weeklog=week)
    case = CVECase.objects.create(kind=CVECase.Kind.TASK, title="Ny printer")
    TicketLink.objects.create(sdp_id=4711, subject="Printer", priority_item=item)
    TicketLink.objects.create(sdp_id=4711, subject="Printer", case=case)
    url = {
        "week log": reverse("logbook:weeklog-detail", args=[week.year, week.week_number]),
        "priority search": reverse("logbook:priorities-search"),
        "case list": reverse("cves:case-list"),
        "dashboard week": reverse("dashboard:partial-current-week"),
        "dashboard cases": reverse("dashboard:partial-cves"),
        "priority page": reverse("logbook:priority-item-history", args=[item.pk]),
        "case page": reverse("cves:case-detail", kwargs={"pk": case.pk}),
    }[page]
    html = client.get(url).content.decode()
    assert "pill-sd" in html and "woID=4711" in html, page
