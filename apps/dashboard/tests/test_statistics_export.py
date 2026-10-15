"""Exports of the Statistik page: PDF, HTML, Markdown and JSON."""

import json
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone

from apps.dashboard import exports
from apps.logbook.models import HelpdeskTicket

pytestmark = pytest.mark.django_db


@pytest.fixture
def tickets():
    now = timezone.now()
    HelpdeskTicket.objects.create(
        sdp_id=1, created_at=now - timedelta(days=3), closed_at=now - timedelta(days=2),
        status="Lukket", is_open=False, requester_ref="a", technician="Morten", category="Hardware",
    )
    HelpdeskTicket.objects.create(
        sdp_id=2, created_at=now - timedelta(days=1), status="Åben", is_open=True, requester_ref="b",
    )


@pytest.fixture
def editor(client):
    client.force_login(User.objects.create_user("editor", password="x"))
    return client


def url(fmt):
    return reverse("dashboard:statistics-export", args=[fmt])


def test_json_is_self_describing(tickets):
    doc = exports.generate_json(exports.collect())
    assert doc["schema"] == "fynbus-chronicle/statistics"
    assert doc["schema_version"] == 1
    assert doc["period"]["days"] == 365
    summary = doc["helpdesk"]["summary"]
    assert summary["tickets_created"] == 2
    assert summary["distinct_requesters"] == 2
    assert summary["open_now"] == 1
    res = doc["helpdesk"]["resolution_time"]
    assert res["median_hours"] == pytest.approx(24, abs=0.01)
    assert len(res["distribution"]) == 7
    assert len(doc["helpdesk"]["hourly_heatmap"]["rows"]) == 7
    assert all(len(r["counts"]) == 24 for r in doc["helpdesk"]["hourly_heatmap"]["rows"])
    assert len(doc["helpdesk"]["weekly"]) == 52
    assert doc["helpdesk"]["solved_by_technician"][0]["technician"] == "Morten"
    assert "definitions" in doc and "median" in doc["definitions"]


def test_json_download(editor, tickets):
    response = editor.get(url("json"))
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")
    assert response["Content-Disposition"].startswith("attachment;")
    assert response["Content-Disposition"].endswith('.json"')
    assert json.loads(response.content)["helpdesk"]["summary"]["tickets_created"] == 2


def test_json_inline(editor, tickets):
    response = editor.get(url("json") + "?inline=1")
    assert response["Content-Disposition"].startswith("inline;")


def test_markdown_download(editor, tickets):
    response = editor.get(url("markdown"))
    assert response.status_code == 200
    body = response.content.decode()
    assert body.startswith("# FynBus IT — Statistik")
    assert "| Sager oprettet |" in body
    assert "Morten" in body


def test_html_download_is_standalone(editor, tickets):
    response = editor.get(url("html"))
    body = response.content.decode()
    assert response.status_code == 200
    assert "<style>" in body
    assert "data:image/png;base64," in body
    assert "/static/" not in body


def test_pdf_download(editor, tickets):
    response = editor.get(url("pdf"))
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_unknown_format_404(editor):
    assert editor.get(url("xlsx")).status_code == 404


def test_viewers_cannot_export(client):
    user = User.objects.create_user("viewer", password="x")
    user.groups.add(Group.objects.get_or_create(name="Viewer")[0])
    client.force_login(user)
    assert client.get(url("json")).status_code == 403
    page = client.get(reverse("dashboard:statistics")).content.decode()
    assert "Eksportér" not in page


def test_editors_see_the_export_menu(editor):
    page = editor.get(reverse("dashboard:statistics")).content.decode()
    assert url("json") in page
    assert url("pdf") in page


def test_export_requires_login(client):
    assert client.get(url("json")).status_code == 302
