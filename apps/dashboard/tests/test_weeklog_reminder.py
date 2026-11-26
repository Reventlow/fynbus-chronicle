"""The Kontrolpanel's reminder to send last week's log (FR #19).

Shown to editors while the previous ISO week's log is unsent (or was never
created), with who should send it (this week's rådighedsvagt, split weeks
included) and who has meldt klar. Gone once the log is sent.
"""

from datetime import datetime, timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone

from apps.dashboard.overview import weeklog_send_reminder
from apps.logbook.models import WeekLog, WeekLogSignoff
from apps.oncall import services
from apps.oncall.models import OnCallDuty, week_span

pytestmark = pytest.mark.django_db

# A fixed moment for the helper tests: Thursday 26 Nov 2026 10:00, week 48.
NOW = timezone.make_aware(datetime(2026, 11, 26, 10, 0))


@pytest.fixture
def anna():
    return User.objects.create_user("anna", password="x", first_name="Anna", last_name="Andersen")


@pytest.fixture
def bo():
    return User.objects.create_user("bo", password="x", first_name="Bo", last_name="Berg")


@pytest.fixture
def viewer():
    user = User.objects.create_user("viewer", password="x")
    user.groups.add(Group.objects.get_or_create(name="Viewer")[0])
    return user


def _previous_week_log(**kwargs) -> WeekLog:
    """The log of the week before the real today (for the page tests)."""
    year, week = WeekLog.previous_iso_week()
    return WeekLog.objects.create(year=year, week_number=week, **kwargs)


def _current_week() -> tuple[int, int]:
    iso = timezone.localdate().isocalendar()
    return iso.year, iso.week


# --- the helper ---------------------------------------------------------------


def test_reminder_for_an_unsent_log(anna):
    weeklog = WeekLog.objects.create(year=2026, week_number=47)
    reminder = weeklog_send_reminder(NOW)
    assert reminder["year"] == 2026 and reminder["week"] == 47
    assert reminder["weeklog"] == weeklog
    assert reminder["oncall_week"] == 48


def test_no_reminder_once_sent(anna):
    weeklog = WeekLog.objects.create(year=2026, week_number=47)
    weeklog.mark_emailed(anna)
    assert weeklog_send_reminder(NOW) is None


def test_reminder_when_last_weeks_log_does_not_exist():
    reminder = weeklog_send_reminder(NOW)
    assert reminder["weeklog"] is None
    assert reminder["signoffs"] == []
    assert (reminder["year"], reminder["week"]) == (2026, 47)


def test_only_the_previous_week_counts(anna):
    """An unsent log from two weeks ago does not trigger the reminder by
    itself; only the week right before the current one does."""
    WeekLog.objects.create(year=2026, week_number=46)
    WeekLog.objects.create(year=2026, week_number=47).mark_emailed(anna)
    assert weeklog_send_reminder(NOW) is None


def test_reminder_crosses_the_year_boundary():
    reminder = weeklog_send_reminder(timezone.make_aware(datetime(2027, 1, 5, 9, 0)))  # week 1, 2027
    assert (reminder["year"], reminder["week"]) == (2026, 53)


def test_sender_is_this_weeks_oncall(anna, bo):
    services.apply_assignment(2026, 48, anna, week_span(2026, 48)[0], anna)
    services.apply_assignment(2026, 47, bo, week_span(2026, 47)[0], bo)  # last week's holder is not asked
    reminder = weeklog_send_reminder(NOW)
    assert reminder["sender"] == anna
    assert reminder["split"] == []


def test_split_week_names_the_holder_covering_now(anna, bo):
    start = week_span(2026, 48)[0]
    services.apply_assignment(2026, 48, anna, start, anna)
    services.apply_assignment(2026, 48, bo, start + timedelta(days=2), anna)  # Bo from Wednesday
    on_tuesday = weeklog_send_reminder(start + timedelta(days=1, hours=9))
    on_thursday = weeklog_send_reminder(NOW)
    assert on_tuesday["sender"] == anna
    assert on_thursday["sender"] == bo
    assert [s.user for s in on_thursday["split"]] == [anna, bo]


def test_sender_falls_back_to_the_base_assignee_without_segments(anna):
    OnCallDuty.objects.create(year=2026, week_number=48, user=anna)  # pre-segment data
    assert weeklog_send_reminder(NOW)["sender"] == anna


def test_nobody_on_call():
    reminder = weeklog_send_reminder(NOW)
    assert reminder["sender"] is None
    assert reminder["split"] == []


def test_signoffs_are_listed_oldest_first(anna, bo):
    weeklog = WeekLog.objects.create(year=2026, week_number=47)
    WeekLogSignoff.objects.create(weeklog=weeklog, user=bo)
    WeekLogSignoff.objects.create(weeklog=weeklog, user=anna)
    assert [s.user for s in weeklog_send_reminder(NOW)["signoffs"]] == [bo, anna]


# --- the Kontrolpanel -------------------------------------------------------------


def test_dashboard_shows_the_reminder(client, anna, bo):
    weeklog = _previous_week_log()
    WeekLogSignoff.objects.create(weeklog=weeklog, user=bo)
    year, week = _current_week()
    services.apply_assignment(year, week, anna, week_span(year, week)[0], anna)
    client.force_login(anna)
    html = client.get(reverse("dashboard:index")).content.decode()
    assert 'id="weeklog-reminder"' in html
    assert "er ikke sendt" in html
    assert weeklog.get_absolute_url() in html
    assert "Anna Andersen</strong> (dig), som har rådighedsvagten" in html
    assert "Bo Berg" in html  # meldt klar
    assert reverse("logbook:weeklog-mark-emailed", kwargs={"year": weeklog.year, "week": weeklog.week_number}) in html


def test_dashboard_hides_the_reminder_once_sent(client, anna):
    _previous_week_log().mark_emailed(anna)
    client.force_login(anna)
    html = client.get(reverse("dashboard:index")).content.decode()
    assert 'id="weeklog-reminder"' not in html


def test_dashboard_reminder_for_a_missing_log_links_to_create(client, anna):
    year, week = WeekLog.previous_iso_week()
    client.force_login(anna)
    html = client.get(reverse("dashboard:index")).content.decode()
    assert "er ikke oprettet" in html
    assert f"{reverse('logbook:weeklog-create')}?year={year}&amp;week={week}" in html
    assert "Ingen har rådighedsvagten" in html


def test_viewers_get_no_reminder(client, viewer):
    _previous_week_log()
    client.force_login(viewer)
    html = client.get(reverse("dashboard:index")).content.decode()
    assert 'id="weeklog-reminder"' not in html
    partial = client.get(reverse("dashboard:partial-weeklog-reminder")).content.decode()
    assert partial.strip() == ""


def test_partial_is_empty_once_sent(client, anna):
    weeklog = _previous_week_log()
    client.force_login(anna)
    url = reverse("dashboard:partial-weeklog-reminder")
    assert 'id="weeklog-reminder"' in client.get(url).content.decode()
    weeklog.mark_emailed(anna)
    assert client.get(url).content.decode().strip() == ""


def test_mark_from_the_dashboard_returns_there(client, anna):
    weeklog = _previous_week_log()
    client.force_login(anna)
    url = reverse("logbook:weeklog-mark-emailed", kwargs={"year": weeklog.year, "week": weeklog.week_number})
    response = client.post(url, {"next": reverse("dashboard:index")}, follow=True)
    assert response.redirect_chain[-1][0] == reverse("dashboard:index")
    assert 'id="weeklog-reminder"' not in response.content.decode()
