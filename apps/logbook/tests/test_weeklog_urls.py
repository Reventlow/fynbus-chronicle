"""Weeklogs are addressed by ISO year + week, not by database id."""

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from apps.logbook.models import WeekLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def weeklog():
    return WeekLog.objects.create(year=2026, week_number=34, helpdesk_open=61)


@pytest.fixture
def editor(client):
    user = User.objects.create_user("gre", password="x")
    client.force_login(user)
    return user


@pytest.fixture
def viewer(client):
    user = User.objects.create_user("viewer", password="x")
    group, _ = Group.objects.get_or_create(name="Viewer")
    user.groups.add(group)
    client.force_login(user)
    return user


class TestUrlShape:
    def test_detail_url_is_year_and_week(self, weeklog):
        assert weeklog.get_absolute_url() == "/logbook/2026/34/"

    def test_edit_url_is_year_and_week(self):
        url = reverse("logbook:weeklog-edit", kwargs={"year": 2026, "week": 34})
        assert url == "/logbook/2026/34/edit/"

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("logbook:export-pdf", "/logbook/2026/34/export/pdf/"),
            ("logbook:export-markdown", "/logbook/2026/34/export/markdown/"),
            ("logbook:export-html", "/logbook/2026/34/export/html/"),
            ("logbook:export-email", "/logbook/2026/34/export/email/"),
        ],
    )
    def test_export_urls_are_year_and_week(self, name, expected):
        assert reverse(name, kwargs={"year": 2026, "week": 34}) == expected


class TestDetailView:
    def test_resolves_the_right_week(self, client, editor, weeklog):
        WeekLog.objects.create(year=2026, week_number=35)

        response = client.get("/logbook/2026/34/")

        assert response.status_code == 200
        assert response.context["weeklog"] == weeklog

    def test_unknown_week_is_404(self, client, editor, weeklog):
        assert client.get("/logbook/2026/52/").status_code == 404

    def test_same_week_in_another_year_is_a_different_page(self, client, editor, weeklog):
        other = WeekLog.objects.create(year=2025, week_number=34)

        response = client.get("/logbook/2025/34/")

        assert response.context["weeklog"] == other

    def test_edit_page_resolves(self, client, editor, weeklog):
        response = client.get("/logbook/2026/34/edit/")
        assert response.status_code == 200
        assert response.context["object"] == weeklog


class TestLegacyRedirects:
    """Links created before 0.10.5 carry the database id."""

    def test_detail_id_redirects_permanently(self, client, editor, weeklog):
        response = client.get(f"/logbook/{weeklog.pk}/")

        assert response.status_code == 301
        assert response["Location"] == "/logbook/2026/34/"

    def test_edit_id_redirects_permanently(self, client, editor, weeklog):
        response = client.get(f"/logbook/{weeklog.pk}/edit/")

        assert response.status_code == 301
        assert response["Location"] == "/logbook/2026/34/edit/"

    def test_unknown_id_is_404(self, client, editor):
        assert client.get("/logbook/999999/").status_code == 404

    def test_redirect_survives_following(self, client, editor, weeklog):
        response = client.get(f"/logbook/{weeklog.pk}/", follow=True)

        assert response.status_code == 200
        assert response.context["weeklog"] == weeklog


class TestPermissionsUnchanged:
    def test_viewer_can_read_a_weeklog(self, client, viewer, weeklog):
        assert client.get("/logbook/2026/34/").status_code == 200

    def test_viewer_cannot_edit(self, client, viewer, weeklog):
        response = client.get("/logbook/2026/34/edit/")
        assert response.status_code in (302, 403)
