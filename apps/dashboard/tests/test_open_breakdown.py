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


def test_age_buckets_and_over_one_month_pill(logged_in):
    weeklog = WeekLog.get_or_create_current_week()
    weeklog.helpdesk_open_0_7 = 5
    weeklog.helpdesk_open_15_30 = 10
    weeklog.helpdesk_open_91_180 = 3
    weeklog.helpdesk_open_over_365 = 2
    weeklog.save()
    groups = age_groups(weeklog)
    assert [g["count"] for g in groups["groups"]] == [5, 0, 10, 0, 3, 0, 2]
    assert groups["stale"] == 5
    body = get_bento(logged_in)
    assert "5 over 1 måned" in body
    assert "2 uger – 1 måned" in body and "Over 12 måneder" in body


def test_without_data(logged_in):
    WeekLog.get_or_create_current_week()
    body = get_bento(logged_in)
    assert "Ingen åbne sager" in body
    assert "Ingen opdeling på liggetid" in body


def test_donut_segments_cover_the_circle():
    segs = donut_segments([{"count": 1, "color": "a"}, {"count": 3, "color": "b"}])
    assert [s["offset"] for s in segs] == ["-0.00", "-75.40"]
    assert donut_segments([]) == []


# --- Newest and oldest open tickets -------------------------------------------


def test_newest_and_oldest_open_tickets_link_to_servicedesk(logged_in, settings):
    settings.SERVICEDESK_URL = "https://servicedesk.example/"
    now = timezone.now()
    for i in range(1, 9):
        HelpdeskTicket.objects.create(
            sdp_id=100 + i, created_at=now - timedelta(days=i), is_open=True,
            status="Åben", subject=f"Sag {i}",
        )
    HelpdeskTicket.objects.create(  # closed: never listed
        sdp_id=999, created_at=now - timedelta(days=50), closed_at=now, is_open=False,
        status="Lukket", subject="Lukket sag",
    )
    response = logged_in.get(reverse("dashboard:partial-open-ticket-lists"))
    assert [t.sdp_id for t in response.context["newest"]] == [101, 102, 103, 104, 105, 106]
    assert [t.sdp_id for t in response.context["oldest"]] == [108, 107, 106, 105, 104, 103]
    body = response.content.decode()
    assert 'href="https://servicedesk.example/WorkOrder.do?woMode=viewWO&amp;woID=101"' in body
    assert "Sag 8" in body and "Lukket sag" not in body
    assert "8 d" in body


def test_mirror_copies_the_subject():
    from apps.logbook.services.ticket_mirror import ticket_values

    values = ticket_values({
        "id": "15869", "created_time": {"value": "1760000000000"}, "status": {"name": "Åben"},
        "subject": "  Julespeak  ",
    })
    assert values["subject"] == "Julespeak"


def test_age_label():
    from apps.dashboard.overview import age_label

    now = timezone.now()
    assert [age_label(now - d, now) for d in (
        timedelta(minutes=5), timedelta(hours=5), timedelta(days=12), timedelta(days=210),
    )] == ["5 min", "5 t", "12 d", "7 mdr"]
