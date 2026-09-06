"""Viewers must be blocked *before* a write happens, not after.

EditorRequiredMixin used to run the view first and check the role
afterwards: the response was a 403, but the object had already been
created, updated or deleted. These tests cover every class-based write
view that uses the mixin.
"""

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from apps.logbook.models import (
    Absence,
    Incident,
    PriorityItem,
    PriorityItemAppearance,
    WeekLog,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def weeklog():
    return WeekLog.objects.create(year=2026, week_number=36)


@pytest.fixture
def viewer(client):
    user = User.objects.create_user("viewer", password="x")
    group, _ = Group.objects.get_or_create(name="Viewer")
    user.groups.add(group)
    client.force_login(user)
    return user


@pytest.fixture
def editor(client):
    user = User.objects.create_user("editor", password="x")
    client.force_login(user)
    return user


@pytest.fixture
def appearance(weeklog):
    item = PriorityItem.objects.create(
        origin_weeklog=weeklog, title="Opgave", priority="medium", status="ongoing"
    )
    return PriorityItemAppearance.objects.create(priority_item=item, weeklog=weeklog)


PRIORITY_POST = {
    "title": "Ændret af viewer",
    "priority": "high",
    "status": "completed",
    "description": "",
    "notes": "",
}


class TestViewerCannotWrite:
    def test_cannot_edit_a_priority_item(self, client, viewer, appearance):
        url = reverse("logbook:priority-item-edit", kwargs={"pk": appearance.pk})

        response = client.post(url, PRIORITY_POST, HTTP_HX_REQUEST="true")

        assert response.status_code == 403
        appearance.priority_item.refresh_from_db()
        assert appearance.priority_item.title == "Opgave"
        assert appearance.priority_item.status == "ongoing"

    def test_cannot_create_a_priority_item(self, client, viewer, weeklog):
        url = reverse("logbook:priority-item-create")

        response = client.post(
            f"{url}?weeklog={weeklog.pk}", PRIORITY_POST, HTTP_HX_REQUEST="true"
        )

        assert response.status_code == 403
        assert not PriorityItem.objects.filter(title="Ændret af viewer").exists()

    def test_cannot_delete_a_priority_item(self, client, viewer, appearance):
        url = reverse("logbook:priority-item-delete", kwargs={"pk": appearance.pk})

        response = client.delete(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 403
        assert PriorityItemAppearance.objects.filter(pk=appearance.pk).exists()

    def test_cannot_edit_a_weeklog(self, client, viewer, weeklog):
        url = reverse(
            "logbook:weeklog-edit",
            kwargs={"year": weeklog.year, "week": weeklog.week_number},
        )

        response = client.post(
            url,
            {
                "year": weeklog.year,
                "week_number": weeklog.week_number,
                "helpdesk_new": 999,
                "helpdesk_closed": 0,
                "helpdesk_open": 0,
                "helpdesk_open_0_7": 0,
                "helpdesk_open_8_14": 0,
                "helpdesk_open_15_30": 0,
                "helpdesk_open_31_90": 0,
                "helpdesk_open_91_180": 0,
                "helpdesk_open_181_365": 0,
                "helpdesk_open_over_365": 0,
                "summary": "",
            },
        )

        assert response.status_code == 403
        weeklog.refresh_from_db()
        assert weeklog.helpdesk_new == 0

    def test_cannot_create_an_absence(self, client, viewer, weeklog):
        url = reverse("logbook:absence-create")

        response = client.post(
            f"{url}?weeklog={weeklog.pk}",
            {
                "staff_name": "Viewer",
                "absence_type": "vacation",
                "start_date": "2026-09-01",
                "end_date": "2026-09-02",
                "notes": "",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 403
        assert not Absence.objects.filter(staff_name="Viewer").exists()

    def test_cannot_create_an_incident(self, client, viewer, weeklog):
        url = reverse("logbook:incident-create")

        response = client.post(
            f"{url}?weeklog={weeklog.pk}",
            {
                "title": "Falsk hændelse",
                "description": "x",
                "incident_type": "other",
                "severity": "low",
                "occurred_at": "2026-09-01 10:00",
                "resolved": False,
                "resolution": "",
            },
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 403
        assert not Incident.objects.filter(title="Falsk hændelse").exists()

    def test_cannot_open_an_edit_form(self, client, viewer, appearance):
        url = reverse("logbook:priority-item-edit", kwargs={"pk": appearance.pk})

        assert client.get(url, HTTP_HX_REQUEST="true").status_code == 403


class TestEditorStillWorks:
    def test_editor_can_edit_a_priority_item(self, client, editor, appearance):
        url = reverse("logbook:priority-item-edit", kwargs={"pk": appearance.pk})

        response = client.post(url, PRIORITY_POST, HTTP_HX_REQUEST="true")

        assert response.status_code == 200
        appearance.priority_item.refresh_from_db()
        assert appearance.priority_item.title == "Ændret af viewer"

    def test_staff_in_viewer_group_is_still_an_editor(self, client, appearance):
        """Staff override: group membership must not lock an admin out."""
        user = User.objects.create_user("boss", password="x", is_staff=True)
        group, _ = Group.objects.get_or_create(name="Viewer")
        user.groups.add(group)
        client.force_login(user)
        url = reverse("logbook:priority-item-edit", kwargs={"pk": appearance.pk})

        assert client.post(url, PRIORITY_POST, HTTP_HX_REQUEST="true").status_code == 200


class TestAnonymousStillRedirects:
    def test_anonymous_gets_the_login_redirect_not_a_403(self, client, appearance):
        url = reverse("logbook:priority-item-edit", kwargs={"pk": appearance.pk})

        response = client.get(url)

        assert response.status_code == 302
        assert "/login" in response["Location"] or "login" in response["Location"]
