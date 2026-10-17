"""Kontrolpanel "Åbne sager" bento: technicians, categories and age groups."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.dashboard.overview import age_groups, donut_segments
from apps.logbook.models import HelpdeskTicket, WeekLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def logged_in(client):
    client.force_login(User.objects.create_user("u", password="x"))
    return client


def ticket(sdp_id, technician="", category=""):
    return HelpdeskTicket.objects.create(
        sdp_id=sdp_id, created_at=timezone.now() - timedelta(days=2), is_open=True,
        status="Åben", technician=technician, category=category,
    )


def get_bento(client) -> str:
    return client.get(reverse("dashboard:partial-open-breakdown")).content.decode()


def test_bento_is_on_the_dashboard(logged_in):
    body = logged_in.get(reverse("dashboard:index")).content.decode()
    assert reverse("dashboard:partial-open-breakdown") in body
    assert "Åbne sager" in body and 'class="card bento"' in body


def test_technician_bars_scale_to_the_largest_and_mute_unassigned(logged_in):
    ticket(1, "Peter Malmborg", "Hardware")
    ticket(2, "Peter Malmborg", "Hardware")
    ticket(3, "", "Software")
    body = get_bento(logged_in)
    assert "Peter Malmborg" in body
    assert 'style="width: 100.0%;"' in body  # the largest bar is full width
    assert "bento-bar is-muted" in body and "Ikke tildelt" in body


def test_category_donut_is_svg_with_total(logged_in):
    ticket(1, "A", "Hardware")
    ticket(2, "A", "Software")
    ticket(3, "A", "")
    body = get_bento(logged_in)
    assert body.count("<circle") == 3
    assert ">3</text>" in body and "ÅBNE" in body
    assert "Ingen kategori" in body


def test_age_groups_and_over_three_months_pill(logged_in):
    weeklog = WeekLog.get_or_create_current_week()
    weeklog.helpdesk_open_0_7 = 5
    weeklog.helpdesk_open_15_30 = 10
    weeklog.helpdesk_open_91_180 = 3
    weeklog.helpdesk_open_over_365 = 2
    weeklog.save()
    groups = age_groups(weeklog)
    assert [g["count"] for g in groups["groups"]] == [5, 10, 0, 5]
    assert groups["over_3_months"] == 5
    body = get_bento(logged_in)
    assert "5 over 3 mdr" in body
    assert "1–4 uger" in body


def test_without_data(logged_in):
    WeekLog.get_or_create_current_week()
    body = get_bento(logged_in)
    assert "Ingen åbne sager" in body
    assert "Ingen opdeling på liggetid" in body


def test_donut_segments_cover_the_circle():
    segs = donut_segments([{"count": 1, "color": "a"}, {"count": 3, "color": "b"}])
    assert [s["offset"] for s in segs] == ["-0.00", "-75.40"]
    assert donut_segments([]) == []
