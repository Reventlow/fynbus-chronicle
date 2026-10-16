"""The Statistik page's Fra/Til period: parsing, figures and exports."""

import json
from datetime import date, datetime, timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.dashboard import exports
from apps.dashboard.statistics import (
    chronicle_statistics,
    default_period,
    helpdesk_statistics,
    period_from_params,
)
from apps.logbook.models import HelpdeskTicket, Incident, WeekLog

pytestmark = pytest.mark.django_db

NOW = timezone.make_aware(datetime(2026, 10, 14, 12, 0))  # a Wednesday


def make(sdp_id, created, closed=None, **kw):
    return HelpdeskTicket.objects.create(
        sdp_id=sdp_id,
        created_at=created,
        closed_at=closed,
        is_open=closed is None,
        status="Åben" if closed is None else "Lukket",
        **kw,
    )


def local(y, m, d, h=12):
    return timezone.make_aware(datetime(y, m, d, h, 0))


# --- Parsing -------------------------------------------------------------------


def test_no_params_is_the_default_year():
    period, error = period_from_params({}, NOW)
    assert error is None
    assert period == default_period(NOW)
    assert period.is_default and period.live
    assert period.week_count == 52 and period.month_count == 12
    assert period.query == ""


def test_both_days_are_inclusive():
    period, error = period_from_params({"fra": "2026-01-01", "til": "2026-03-31"}, NOW)
    assert error is None
    assert not period.is_default and not period.live
    assert period.start == timezone.make_aware(datetime(2026, 1, 1))
    assert period.end == timezone.make_aware(datetime(2026, 4, 1))
    assert (period.first_day, period.last_day) == (date(2026, 1, 1), date(2026, 3, 31))
    assert period.month_count == 3
    assert period.query == "fra=2026-01-01&til=2026-03-31"


def test_an_end_today_or_later_ends_now_and_stays_live():
    period, _ = period_from_params({"fra": "2026-10-01", "til": "2026-12-31"}, NOW)
    assert period.end == NOW and period.live


def test_missing_start_is_a_year_before_the_end():
    period, _ = period_from_params({"til": "2026-06-30"}, NOW)
    assert period.end - period.start == timedelta(days=365)


@pytest.mark.parametrize("params", [
    {"fra": "2026-13-01"},
    {"fra": "i går"},
    {"fra": "2026-05-01", "til": "2026-04-01"},
])
def test_bad_input_falls_back_to_the_default_with_a_message(params):
    period, error = period_from_params(params, NOW)
    assert period.is_default
    assert error


# --- Figures -------------------------------------------------------------------


def test_counts_only_tickets_inside_the_period():
    make(1, local(2026, 1, 15), local(2026, 1, 16))   # inside
    make(2, local(2026, 3, 31, 23), None)             # last day, still open
    make(3, local(2026, 4, 1, 1), None)               # the day after
    make(4, local(2025, 12, 31), local(2026, 1, 2))   # before, solved inside
    period, _ = period_from_params({"fra": "2026-01-01", "til": "2026-03-31"}, NOW)
    stats = helpdesk_statistics(period=period)
    assert stats["total_created"] == 2
    assert stats["total_solved"] == 2  # tickets 1 and 4
    assert stats["per_month"] == round(2 / period.months, 1)


def test_weekly_series_covers_the_period():
    period, _ = period_from_params({"fra": "2026-01-05", "til": "2026-02-01"}, NOW)  # Mon – Sun
    weekly = helpdesk_statistics(period=period)["weekly"]
    assert [w["week_start"] for w in weekly] == [
        date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19), date(2026, 1, 26),
    ]


def test_open_tickets_are_rebuilt_at_the_end_of_a_past_period():
    make(1, local(2026, 2, 1), local(2026, 5, 1))  # open on 31 March, closed since
    make(2, local(2026, 2, 1), local(2026, 3, 1))  # closed before the end
    make(3, local(2026, 9, 1))                     # open now, created after
    period, _ = period_from_params({"fra": "2026-01-01", "til": "2026-03-31"}, NOW)
    stats = helpdesk_statistics(period=period)
    assert stats["open_now"] == 1
    # 1 Feb to the end of 31 March is 58 days: the 1–3 months bucket.
    assert sum(b["count"] for b in stats["open_by_age"]) == 1


def test_incidents_and_months_follow_the_period():
    weeklog = WeekLog.objects.create(year=2026, week_number=7)
    Incident.objects.create(weeklog=weeklog, title="I", occurred_at=local(2026, 2, 10))
    Incident.objects.create(weeklog=weeklog, title="Udenfor", occurred_at=local(2026, 5, 10))
    period, _ = period_from_params({"fra": "2026-01-01", "til": "2026-03-31"}, NOW)
    inc = chronicle_statistics(period=period)["incidents"]
    assert inc["total"] == 1
    assert inc["months"] == ["jan 26", "feb 26", "mar 26"]
    assert inc["by_month"] == [0, 1, 0]


# --- Page and exports -------------------------------------------------------------


@pytest.fixture
def editor(client):
    client.force_login(User.objects.create_user("gre", password="x"))
    return client


def test_page_shows_the_chosen_period_and_keeps_it_on_export_links(editor):
    make(1, local(2026, 2, 1))
    body = editor.get(
        reverse("dashboard:statistics"), {"fra": "2026-01-01", "til": "2026-03-31"}
    ).content.decode()
    assert "Valgt periode" in body
    assert 'name="fra" value="2026-01-01"' in body
    assert "Åbne ved periodens slutning" in body
    assert "export/pdf/?fra=2026-01-01&amp;til=2026-03-31" in body


def test_page_explains_a_bad_period(editor):
    body = editor.get(
        reverse("dashboard:statistics"), {"fra": "2026-05-01", "til": "2026-04-01"}
    ).content.decode()
    assert "Startdatoen skal ligge før slutdatoen" in body
    assert "Seneste 12 måneder" in body


def test_json_export_uses_the_period(editor):
    make(1, local(2026, 2, 1))
    response = editor.get(
        reverse("dashboard:statistics-export", args=["json"]),
        {"fra": "2026-01-01", "til": "2026-03-31"},
    )
    assert 'filename="statistik_2026-01-01_2026-03-31.json"' in response["Content-Disposition"]
    doc = json.loads(response.content)
    assert doc["period"]["days"] == 90
    assert doc["period"]["description"] == "Valgt periode: 01.01.2026 – 31.03.2026."
    assert doc["helpdesk"]["summary"]["tickets_created"] == 1


def test_default_export_is_unchanged():
    data = exports.collect(NOW)
    assert data["period"].is_default
    assert exports.filename(data, "md") == "statistik_2026-10-14.md"
