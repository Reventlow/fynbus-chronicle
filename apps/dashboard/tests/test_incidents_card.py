"""Kontrolpanel incidents card: the last 30 days, unresolved ones however
old, and older resolved ones behind "Vis ældre"."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.logbook.models import Incident, WeekLog

pytestmark = pytest.mark.django_db


def incident(title, days_ago, resolved=True):
    return Incident.objects.create(
        weeklog=WeekLog.get_or_create_current_week(), title=title,
        occurred_at=timezone.now() - timedelta(days=days_ago), resolved=resolved,
    )


@pytest.fixture
def logged_in(client):
    client.force_login(User.objects.create_user("u", password="x"))
    return client


def get_card(client):
    response = client.get(reverse("dashboard:partial-incidents"))
    return response.context, response.content.decode()


def test_recent_unresolved_and_older(logged_in):
    incident("Ny", 3)
    incident("Gammel uløst", 90, resolved=False)
    incident("Gammel løst", 60)
    context, body = get_card(logged_in)
    assert [i.title for i in context["incidents"]] == ["Ny", "Gammel uløst"]
    assert [i.title for i in context["older_incidents"]] == ["Gammel løst"]
    assert body.count("incident-older") == 1
    assert "Vis 1 ældre" in body
    # Severity is a rail and a mono P-level, not a pill.
    assert 'class="incident-sev" data-sev="P3"' in body
    assert "pill-bad" not in body.split("card-head", 1)[1].split("</div>", 1)[0]


def test_nothing_recent_still_offers_older(logged_in):
    incident("Gammel løst", 45)
    _, body = get_card(logged_in)
    assert "Ingen hændelser de sidste 30 dage" in body
    assert "Vis 1 ældre" in body


def test_no_toggle_without_older(logged_in):
    incident("Ny", 1)
    _, body = get_card(logged_in)
    assert "ældre →" not in body


def test_empty(logged_in):
    _, body = get_card(logged_in)
    assert "Ingen denne uge" in body
    assert "Ingen hændelser de sidste 30 dage" in body


def test_heading_counts_this_week_and_critical(logged_in):
    incident("Kritisk", 0).__class__.objects.filter(title="Kritisk").update(severity="critical")
    incident("Lav", 0)
    _, body = get_card(logged_in)
    assert "2 denne uge, 1 kritisk" in body


def test_every_row_says_solved_or_unsolved(logged_in):
    incident("Løst sag", 2)
    incident("Åben sag", 1, resolved=False)
    _, body = get_card(logged_in)
    assert body.count(">Løst</span>") == 1
    assert body.count(">Uløst</span>") == 1
