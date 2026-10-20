"""Kontrolpanel v3: headline wording, sync state, shell and changelog strip."""

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.dashboard.overview import (
    changelog_strip,
    count_words,
    headline_delta,
    sync_state,
)
from apps.logbook.models import HelpdeskTicket, WeekLog
from apps.oncall.models import OnCallDuty, current_watch

pytestmark = pytest.mark.django_db


@pytest.fixture
def logged_in(client):
    client.force_login(User.objects.create_user("gre", password="x", first_name="Gorm"))
    return client


def test_count_words():
    assert [count_words(n) for n in (1, 4, 10, 11)] == ["én", "fire", "ti", "11"]


@pytest.mark.parametrize("delta, text, tone", [
    (-4, "fire færre", "good"), (3, "tre flere", "bad"), (0, "uændret", "flat"), (-27, "27 færre", "good"),
])
def test_headline_delta(delta, text, tone):
    assert headline_delta(delta) == {"text": text, "tone": tone}
    assert headline_delta(None) is None


def test_sync_state_is_stale_without_or_with_old_syncs():
    assert sync_state()["stale"]
    t = HelpdeskTicket.objects.create(sdp_id=1, created_at=timezone.now(), is_open=True, status="Åben")
    assert not sync_state()["stale"]
    HelpdeskTicket.objects.filter(pk=t.pk).update(synced_at=timezone.now() - timedelta(hours=2))
    assert sync_state()["stale"]


def test_changelog_strip():
    body = "### Fixed\n- **Søgefeltet i *Tilføj* mister ikke markøren.** Mere tekst."
    strip = changelog_strip("0.20.11 — 2026-10-16", body, today=date(2026, 10, 17))
    assert strip == {"version": "0.20.11", "summary": "Søgefeltet i Tilføj mister ikke markøren.", "when": "i går"}


def test_headline_states_open_tickets_and_the_weekly_change(logged_in):
    weeklog = WeekLog.get_or_create_current_week()
    weeklog.helpdesk_open, weeklog.helpdesk_new, weeklog.helpdesk_closed = 134, 51, 55
    weeklog.save()
    HelpdeskTicket.objects.create(sdp_id=1, created_at=timezone.now(), is_open=True, status="Åben")
    body = logged_in.get(reverse("dashboard:index")).content.decode()
    assert '<span class="num">134</span> åbne sager' in body
    assert "fire færre</span> end sidste uge." in body
    assert "Synk med ServiceDesk fejlede" not in body


def test_failing_sync_is_called_out(logged_in):
    body = logged_in.get(reverse("dashboard:index")).content.decode()
    assert "Synk med ServiceDesk fejlede" in body
    assert "Prøv igen" in body


def test_numbered_sections_and_shell(logged_in):
    body = logged_in.get(reverse("dashboard:index")).content.decode()
    for n, title in (("01", "Nu"), ("02", "Åbne sager"), ("03", "Udvikling")):
        assert f'<span class="section-label-n">{n}</span>' in body
        assert f'<h2 class="display">{title}</h2>' in body
    assert '<aside class="sidebar"' in body
    assert 'class="toolbar"' in body
    assert "nav-shell" not in body
    assert reverse("dashboard:partial-oncall-mini") in body
    # The dashboard on-call card is only a fallback for when the sidebar's is hidden.
    assert 'class="dash-oncall"' in body


def test_current_week_lists_every_task_without_strikethrough(logged_in):
    from apps.logbook.models import PriorityItem, PriorityItemAppearance

    weeklog = WeekLog.get_or_create_current_week()
    for i in range(13):
        item = PriorityItem.objects.create(
            origin_weeklog=weeklog, title=f"Opgave {i}", priority="medium",
            status="completed" if i < 3 else ("blocked" if i == 3 else "ongoing"),
        )
        PriorityItemAppearance.objects.create(priority_item=item, weeklog=weeklog)
    body = logged_in.get(reverse("dashboard:partial-current-week")).content.decode()
    assert body.count('<div class="task-row') == 13
    assert body.count("task-row is-done") == 3
    assert "line-through" not in body
    assert "10 åbne · 3 afsluttet" in body
    assert body.count("pill pill-bad") == 1  # only Blokeret keeps a pill


def test_current_watch_names_the_next_person():
    now = timezone.now()
    iso = timezone.localtime(now).isocalendar()
    a = User.objects.create_user("a", first_name="Anders", last_name="S")
    b = User.objects.create_user("b", first_name="Bente", last_name="K")
    OnCallDuty.objects.create(year=iso.year, week_number=iso.week, user=a)
    nxt = (timezone.localtime(now) + timedelta(days=7)).isocalendar()
    OnCallDuty.objects.create(year=nxt.year, week_number=nxt.week, user=b)
    watch = current_watch(now)
    assert watch["user"] == a and watch["next_user"] == b
    assert watch["until_long"] == "mandag 00:00"
    assert watch["until_short"] == "man 00:00"


def test_headline_refreshes_itself(logged_in):
    page = logged_in.get(reverse("dashboard:index")).content.decode()
    assert 'id="dash-headline"' in page
    assert reverse("dashboard:partial-headline") in page and "every 60s, refresh" in page
    partial = logged_in.get(reverse("dashboard:partial-headline")).content.decode()
    assert 'id="dash-headline"' in partial
    assert "åbne sager" in partial or "åben sag" in partial
