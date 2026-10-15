"""Share links for the statistics: public JSON + guide behind a secret token."""

import json
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone

from apps.dashboard.models import StatisticsShareLink

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(client):
    client.force_login(User.objects.create_user("editor", password="x"))
    return client


@pytest.fixture
def link():
    return StatisticsShareLink.objects.create(label="Claude Motion")


def test_token_is_long_and_random():
    a = StatisticsShareLink.objects.create(label="a")
    b = StatisticsShareLink.objects.create(label="b")
    assert len(a.token) >= 40 and a.token != b.token


def test_default_validity_is_30_days(link):
    assert timedelta(days=29) < link.expires_at - timezone.now() <= timedelta(days=30)


def test_shared_json_needs_no_login_and_counts_use(client, link):
    response = client.get(link.get_data_path())
    assert response.status_code == 200
    assert json.loads(response.content)["schema"] == "fynbus-chronicle/statistics"
    assert response["Cache-Control"] == "no-store"
    assert "noindex" in response["X-Robots-Tag"]
    link.refresh_from_db()
    assert link.use_count == 1 and link.last_used_at is not None


def test_guide_points_at_the_data(client, link):
    response = client.get(link.get_guide_path())
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/markdown")
    body = response.content.decode()
    assert link.get_data_path() in body
    assert "schema_version" in body
    assert "&amp;" not in body  # not HTML-escaped


@pytest.mark.parametrize("state", ["revoked", "expired", "unknown"])
def test_inactive_links_404(client, link, state):
    if state == "revoked":
        link.revoke()
        path = link.get_data_path()
    elif state == "expired":
        link.expires_at = timezone.now() - timedelta(seconds=1)
        link.save()
        path = link.get_data_path()
    else:
        path = reverse("dashboard:statistics-shared-json", kwargs={"token": "nope"})
    assert client.get(path).status_code == 404
    guide = path.replace("data.json", "vejledning.md")
    assert client.get(guide).status_code == 404


def test_editor_creates_a_link(editor):
    response = editor.post(reverse("dashboard:statistics-share"), {"label": "Motion", "days": "7"})
    assert response.status_code == 200
    link = StatisticsShareLink.objects.get()
    assert link.label == "Motion"
    assert timedelta(days=6) < link.expires_at - timezone.now() <= timedelta(days=7)
    body = response.content.decode()
    assert link.get_data_path() in body
    assert link.get_guide_path() in body
    assert "Kopiér prompt" in body


def test_invalid_validity_falls_back_to_default(editor):
    editor.post(reverse("dashboard:statistics-share"), {"label": "x", "days": "9999"})
    link = StatisticsShareLink.objects.get()
    assert link.expires_at - timezone.now() > timedelta(days=29)


def test_editor_revokes_a_link(editor, link):
    response = editor.post(reverse("dashboard:statistics-share"), {"revoke": link.pk})
    assert response.status_code == 302
    link.refresh_from_db()
    assert link.revoked_at is not None


def test_viewers_cannot_manage_links(client):
    user = User.objects.create_user("viewer", password="x")
    user.groups.add(Group.objects.get_or_create(name="Viewer")[0])
    client.force_login(user)
    assert client.get(reverse("dashboard:statistics-share")).status_code == 403


def test_share_page_requires_login(client):
    assert client.get(reverse("dashboard:statistics-share")).status_code == 302
