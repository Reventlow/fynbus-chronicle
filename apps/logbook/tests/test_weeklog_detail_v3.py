"""Ugelog detail (v3): full lists with counts, faded (not struck) done tasks,
last week's figures under the stats, incidents without severity pills."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.logbook.models import Incident, PriorityItem, PriorityItemAppearance, WeekLog

pytestmark = pytest.mark.django_db


def test_detail_page(client):
    client.force_login(User.objects.create_user("gre", password="x"))
    prev = WeekLog.objects.create(year=2026, week_number=41, helpdesk_new=40)
    week = WeekLog.objects.create(year=2026, week_number=42, helpdesk_new=51)
    for i in range(13):
        item = PriorityItem.objects.create(
            origin_weeklog=week, title=f"Opgave {i}", priority="medium",
            status="completed" if i < 3 else "ongoing",
        )
        PriorityItemAppearance.objects.create(priority_item=item, weeklog=week)
    for sev in ("critical", "high", "low", "low"):
        Incident.objects.create(weeklog=week, title=f"H {sev}", severity=sev, occurred_at=timezone.now())

    body = client.get(reverse("logbook:weeklog-detail", args=[2026, 42])).content.decode()
    assert body.count('id="priority-item-') == 13
    assert "10 åbne af 13" in body and "3 / 13 afsluttet" in body
    assert "4 denne uge · 1 kritisk" in body
    assert f"vs. uge {prev.week_number}: <span class=\"num\">40</span>" in body
    assert "line-through" not in body
    assert body.count("opacity: 0.5;") == 3
    assert 'class="incident-sev" data-sev="P1"' in body
    # The toolbar carries the breadcrumb now.
    assert '<span class="current">Uge 42</span>' in body
