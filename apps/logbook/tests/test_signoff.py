"""Tests for the per-user "nothing more to add this week" sign-off (FR #7)."""

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from apps.api.serializers import serialize_weeklog
from apps.logbook.models import WeekLog, WeekLogSignoff

pytestmark = pytest.mark.django_db


@pytest.fixture
def weeklog():
    return WeekLog.objects.create(year=2026, week_number=34)


@pytest.fixture
def anna():
    return User.objects.create_user("anna", password="x", first_name="Anna")


@pytest.fixture
def bo():
    return User.objects.create_user("bo", password="x")


@pytest.fixture
def viewer():
    user = User.objects.create_user("viewer", password="x")
    group, _ = Group.objects.get_or_create(name="Viewer")
    user.groups.add(group)
    return user


def toggle_url(weeklog):
    return reverse("logbook:weeklog-signoff-toggle", kwargs={"pk": weeklog.pk})


class TestToggle:
    def test_toggle_creates_signoff(self, client, weeklog, anna):
        client.force_login(anna)
        response = client.post(toggle_url(weeklog))
        assert response.status_code == 200
        assert weeklog.signoffs.filter(user=anna).exists()
        assert "Fortryd klarmelding" in response.content.decode()

    def test_toggle_twice_removes_signoff(self, client, weeklog, anna):
        client.force_login(anna)
        client.post(toggle_url(weeklog))
        response = client.post(toggle_url(weeklog))
        assert response.status_code == 200
        assert not weeklog.signoffs.filter(user=anna).exists()
        assert "Jeg har ikke mere til denne uge" in response.content.decode()

    def test_signoffs_are_per_user(self, client, weeklog, anna, bo):
        client.force_login(anna)
        client.post(toggle_url(weeklog))
        client.force_login(bo)
        client.post(toggle_url(weeklog))
        assert weeklog.signoffs.count() == 2
        # Bo's undo leaves Anna's marker untouched.
        client.post(toggle_url(weeklog))
        assert list(
            weeklog.signoffs.values_list("user__username", flat=True)
        ) == ["anna"]

    def test_get_not_allowed(self, client, weeklog, anna):
        client.force_login(anna)
        assert client.get(toggle_url(weeklog)).status_code == 405

    def test_anonymous_redirected_to_login(self, client, weeklog):
        response = client.post(toggle_url(weeklog))
        assert response.status_code == 302

    def test_viewer_forbidden(self, client, weeklog, viewer):
        client.force_login(viewer)
        assert client.post(toggle_url(weeklog)).status_code == 403


class TestDetailPage:
    def test_detail_shows_signed_off_users(self, client, weeklog, anna, bo):
        WeekLogSignoff.objects.create(weeklog=weeklog, user=anna)
        client.force_login(bo)
        html = client.get(weeklog.get_absolute_url()).content.decode()
        assert "Klarmelding" in html
        assert "Anna" in html
        # Bo hasn't signed off, so he gets the affirmative button.
        assert "Jeg har ikke mere til denne uge" in html

    def test_detail_empty_state(self, client, weeklog, anna):
        client.force_login(anna)
        html = client.get(weeklog.get_absolute_url()).content.decode()
        assert "Ingen har meldt klar endnu" in html


class TestSerializer:
    def test_full_weeklog_includes_signoffs(self, weeklog, anna):
        WeekLogSignoff.objects.create(weeklog=weeklog, user=anna)
        data = serialize_weeklog(weeklog, full=True)
        assert len(data["signoffs"]) == 1
        entry = data["signoffs"][0]
        assert entry["username"] == "anna"
        assert entry["full_name"] == "Anna"
        assert entry["created_at"]

    def test_summary_weeklog_has_no_signoffs_key(self, weeklog):
        assert "signoffs" not in serialize_weeklog(weeklog)
