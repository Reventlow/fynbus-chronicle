"""Kontrolpanel liggetid card: open tickets by age for the current week."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.logbook.models import WeekLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def logged_in(client):
    client.force_login(User.objects.create_user("u", password="x"))
    return client


def test_card_is_on_the_dashboard(logged_in):
    body = logged_in.get(reverse("dashboard:index")).content.decode()
    assert reverse("dashboard:partial-open-age") in body
    assert "Åbne sager fordelt på liggetid" in body


def test_bars_for_every_age_group(logged_in):
    weeklog = WeekLog.get_or_create_current_week()
    weeklog.helpdesk_open_0_7 = 5
    weeklog.helpdesk_open_15_30 = 10
    weeklog.helpdesk_open_91_180 = 5
    weeklog.save()
    body = logged_in.get(reverse("dashboard:partial-open-age")).content.decode()
    assert body.count("open-age-row") == len(WeekLog.HELPDESK_AGE_BUCKETS)
    assert "Over 12 måneder" in body
    assert "<strong>10</strong> · 50%" in body
    assert "5 af 20 åbne sager har ligget i mere end 1 måned" in body


def test_without_breakdown(logged_in):
    WeekLog.get_or_create_current_week()
    body = logged_in.get(reverse("dashboard:partial-open-age")).content.decode()
    assert "Ingen opdeling på liggetid" in body
