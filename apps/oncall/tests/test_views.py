"""View-level tests: permissions, HTMX endpoints, form validation."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone

from apps.oncall import services
from apps.oncall.models import OnCallChange, OnCallDuty, week_span

pytestmark = pytest.mark.django_db

def _future_week(weeks_ahead: int = 4) -> tuple[int, int]:
    """An ISO (year, week) that is always in the future when the suite runs.

    These tests used to pin 2026 week 30, commented as "a stable future
    week". It stopped being one on 2026-07-20, and from then on the three
    claim/release tests failed — the views correctly hide those actions on
    a past week, so the failures said nothing about the behaviour under
    test. Deriving the week from today keeps that from happening again.
    """
    iso = (timezone.localdate() + timedelta(weeks=weeks_ahead)).isocalendar()
    return iso.year, iso.week


YEAR, WEEK = _future_week()


@pytest.fixture
def editor(client):
    user = User.objects.create_user("editor", password="x", first_name="Edi")
    client.force_login(user)
    return user


@pytest.fixture
def viewer(client):
    user = User.objects.create_user("viewer", password="x")
    group, _ = Group.objects.get_or_create(name="Viewer")
    user.groups.add(group)
    client.force_login(user)
    return user


@pytest.fixture
def anna():
    return User.objects.create_user("anna", first_name="Anna", last_name="Andersen")


class TestPermissions:
    def test_viewer_cannot_assign(self, client, viewer, anna):
        response = client.post(
            reverse("oncall:assign", args=[YEAR, WEEK]),
            {"user": anna.pk, "effective_date": "2026-07-20"},
        )
        assert response.status_code == 403

    def test_viewer_cannot_open_assign_form(self, client, viewer):
        assert client.get(reverse("oncall:assign-form", args=[YEAR, WEEK])).status_code == 403

    def test_viewer_can_read_history(self, client, viewer):
        assert client.get(reverse("oncall:history", args=[YEAR, WEEK])).status_code == 200

    def test_anonymous_redirected(self, client):
        response = client.get(reverse("oncall:calendar"))
        assert response.status_code == 302


class TestAssign:
    def test_assign_whole_week(self, client, editor, anna):
        monday = week_span(YEAR, WEEK)[0].date()
        response = client.post(
            reverse("oncall:assign", args=[YEAR, WEEK]),
            {"user": anna.pk, "effective_date": monday.isoformat(), "notes": "Uge 30"},
        )
        assert response.status_code == 200
        duty = OnCallDuty.objects.get(year=YEAR, week_number=WEEK)
        assert duty.user == anna and duty.notes == "Uge 30"
        change = OnCallChange.objects.get(year=YEAR, week_number=WEEK)
        assert change.changed_by == editor
        # Success swaps the polling card back in.
        assert f"oncall-week-{YEAR}-{WEEK}" in response.content.decode()

    def test_assign_with_time_splits(self, client, editor, anna):
        monday = week_span(YEAR, WEEK)[0].date()
        services.apply_assignment(YEAR, WEEK, editor, week_span(YEAR, WEEK)[0], editor)
        wednesday = monday + timedelta(days=2)
        response = client.post(
            reverse("oncall:assign", args=[YEAR, WEEK]),
            {"user": anna.pk, "effective_date": wednesday.isoformat(), "effective_time": "14:00"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "on 14:00" in content  # split week renders segment ranges

    def test_date_outside_week_rerenders_form_with_error(self, client, editor, anna):
        response = client.post(
            reverse("oncall:assign", args=[YEAR, WEEK]),
            {"user": anna.pk, "effective_date": "2026-01-01"},
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert f"oncall-week-form-{YEAR}-{WEEK}" in content
        assert "inden for ugen" in content
        assert not OnCallDuty.objects.filter(year=YEAR, week_number=WEEK).exists()

    def test_assign_ledig_frees_week(self, client, editor, anna):
        start = week_span(YEAR, WEEK)[0]
        services.apply_assignment(YEAR, WEEK, anna, start, editor)
        response = client.post(
            reverse("oncall:assign", args=[YEAR, WEEK]),
            {"user": "", "effective_date": start.date().isoformat()},
        )
        assert response.status_code == 200
        assert not OnCallDuty.objects.filter(year=YEAR, week_number=WEEK).exists()


class TestClaimReleaseEndpoints:
    def test_claim_and_release_roundtrip(self, client, editor):
        assert client.post(reverse("oncall:claim", args=[YEAR, WEEK])).status_code == 200
        assert OnCallDuty.objects.get(year=YEAR, week_number=WEEK).user == editor
        assert client.post(reverse("oncall:release", args=[YEAR, WEEK])).status_code == 200
        assert not OnCallDuty.objects.filter(year=YEAR, week_number=WEEK).exists()

    def test_get_not_allowed(self, client, editor):
        assert client.get(reverse("oncall:claim", args=[YEAR, WEEK])).status_code == 405


class TestFreedSplitWeekCard:
    def test_freed_split_week_shows_ledig_and_claim(self, client, editor, anna):
        """Review finding: a week freed after a mid-week handover kept
        rendering as staffed — 'Ledig'/'Tag vagt' were unreachable."""
        bo = User.objects.create_user("bo", first_name="Bo")
        start, _ = week_span(YEAR, WEEK)
        services.apply_assignment(YEAR, WEEK, anna, start, editor)
        handover = start + timedelta(days=2)
        services.apply_assignment(YEAR, WEEK, bo, handover, editor)
        services.apply_assignment(YEAR, WEEK, None, handover + timedelta(days=1), editor)

        response = client.get(reverse("oncall:week-status", args=[YEAR, WEEK]))
        content = response.content.decode()
        assert "Ledig" in content
        assert "Tag vagt" in content
        # Past coverage is still listed on the freed card.
        assert "Anna" in content and "Bo" in content


class TestCalendar:
    def test_past_param_extends_grid(self, client, editor):
        response = client.get(reverse("oncall:calendar"), {"past": 4})
        assert response.status_code == 200
        assert len(response.context["weeks"]) == 13 + 4

    def test_invalid_params_fall_back(self, client, editor):
        response = client.get(reverse("oncall:calendar"), {"past": "abc", "weeks": 999})
        assert response.context["past_weeks"] == 0
        assert response.context["num_weeks"] == 13
