"""Tests for the on-call assignment service layer (FR #5).

The invariants under test: segments never overlap and tile the covered
part of the week, duty.user equals the last segment's holder, every
real change writes exactly one audit row, and no-ops write nothing.
"""

from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from apps.notifications.models import Notification
from apps.oncall import services
from apps.oncall.models import OnCallChange, OnCallDuty, OnCallSegment, week_span

pytestmark = pytest.mark.django_db

YEAR, WEEK = 2026, 30  # a stable future week for most tests


@pytest.fixture
def anna():
    return User.objects.create_user("anna", first_name="Anna", last_name="Andersen")


@pytest.fixture
def bo():
    return User.objects.create_user("bo", first_name="Bo", last_name="Berg")


@pytest.fixture
def editor():
    return User.objects.create_user("gre", first_name="Gorm", last_name="Reventlow")


def moment(year: int, week: int, weekday: int, hour: int = 0, minute: int = 0):
    """Aware datetime inside an ISO week (weekday 0 = Monday)."""
    start, _ = week_span(year, week)
    naive = datetime.combine(
        (start + timedelta(days=weekday)).date(), time(hour, minute)
    )
    return timezone.make_aware(naive, timezone.get_default_timezone())


def week_segments(year=YEAR, week=WEEK):
    return list(OnCallSegment.objects.filter(year=year, week_number=week).order_by("start_at"))


class TestApplyAssignment:
    def test_whole_week_assignment(self, anna, editor):
        start, end = week_span(YEAR, WEEK)
        change = services.apply_assignment(YEAR, WEEK, anna, start, editor)

        duty = OnCallDuty.objects.get(year=YEAR, week_number=WEEK)
        assert duty.user == anna
        segments = week_segments()
        assert len(segments) == 1
        assert (segments[0].start_at, segments[0].end_at) == (start, end)
        assert change.from_user is None and change.to_user == anna

    def test_mid_week_handover_splits_coverage(self, anna, bo, editor):
        start, end = week_span(YEAR, WEEK)
        services.apply_assignment(YEAR, WEEK, anna, start, editor)
        handover = moment(YEAR, WEEK, 2, 14)  # Wednesday 14:00
        services.apply_assignment(YEAR, WEEK, bo, handover, editor)

        segments = week_segments()
        assert [(s.user, s.start_at, s.end_at) for s in segments] == [
            (anna, start, handover),
            (bo, handover, end),
        ]
        assert OnCallDuty.objects.get(year=YEAR, week_number=WEEK).user == bo

    def test_handover_on_segment_start_replaces_it(self, anna, bo, editor):
        start, end = week_span(YEAR, WEEK)
        services.apply_assignment(YEAR, WEEK, anna, start, editor)
        # Re-assign from Monday 00:00 — Anna's segment must be replaced,
        # never truncated to a zero-length (end <= start) row.
        services.apply_assignment(YEAR, WEEK, bo, start, editor)

        segments = week_segments()
        assert len(segments) == 1
        assert segments[0].user == bo
        assert (segments[0].start_at, segments[0].end_at) == (start, end)

    def test_consecutive_splits(self, anna, bo, editor):
        start, end = week_span(YEAR, WEEK)
        carl = User.objects.create_user("carl")
        services.apply_assignment(YEAR, WEEK, anna, start, editor)
        services.apply_assignment(YEAR, WEEK, bo, moment(YEAR, WEEK, 2), editor)
        services.apply_assignment(YEAR, WEEK, carl, moment(YEAR, WEEK, 4, 12), editor)

        segments = week_segments()
        assert [s.user for s in segments] == [anna, bo, carl]
        # Contiguous tiling: each segment starts where the previous ended.
        assert segments[0].start_at == start
        assert segments[-1].end_at == end
        for prev, nxt in zip(segments, segments[1:]):
            assert prev.end_at == nxt.start_at

    def test_release_mid_week_preserves_past_coverage(self, anna, editor):
        start, _ = week_span(YEAR, WEEK)
        services.apply_assignment(YEAR, WEEK, anna, start, editor)
        release_at = moment(YEAR, WEEK, 3, 9)  # Thursday 09:00
        change = services.apply_assignment(YEAR, WEEK, None, release_at, editor)

        assert not OnCallDuty.objects.filter(year=YEAR, week_number=WEEK).exists()
        segments = week_segments()
        assert len(segments) == 1
        assert segments[0].user == anna
        assert segments[0].end_at == release_at
        assert change.to_user is None

    def test_noop_writes_no_audit_row(self, anna, editor):
        start, _ = week_span(YEAR, WEEK)
        services.apply_assignment(YEAR, WEEK, anna, start, editor)
        result = services.apply_assignment(YEAR, WEEK, anna, moment(YEAR, WEEK, 2), editor)

        assert result is None
        assert OnCallChange.objects.filter(year=YEAR, week_number=WEEK).count() == 1
        assert len(week_segments()) == 1

    def test_noop_with_notes_updates_notes_only(self, anna, editor):
        start, _ = week_span(YEAR, WEEK)
        services.apply_assignment(YEAR, WEEK, anna, start, editor)
        services.apply_assignment(YEAR, WEEK, anna, start, editor, notes="Ferieafløsning")

        duty = OnCallDuty.objects.get(year=YEAR, week_number=WEEK)
        assert duty.notes == "Ferieafløsning"
        assert OnCallChange.objects.filter(year=YEAR, week_number=WEEK).count() == 1

    def test_release_free_week_is_noop(self, editor):
        result = services.apply_assignment(YEAR, WEEK, None, week_span(YEAR, WEEK)[0], editor)
        assert result is None
        assert OnCallChange.objects.count() == 0

    def test_effective_at_outside_week_raises(self, anna, editor):
        _, end = week_span(YEAR, WEEK)
        with pytest.raises(ValueError):
            services.apply_assignment(YEAR, WEEK, anna, end, editor)

    def test_whole_week_restore_over_split_rewrites_tail(self, anna, bo, editor):
        """Review finding: 'give Anna the whole week' over a split must
        not no-op just because Anna already covers Monday."""
        start, end = week_span(YEAR, WEEK)
        services.apply_assignment(YEAR, WEEK, anna, start, editor)
        services.apply_assignment(YEAR, WEEK, bo, moment(YEAR, WEEK, 2, 14), editor)

        change = services.apply_assignment(YEAR, WEEK, anna, start, editor)

        assert change is not None
        segments = week_segments()
        assert len(segments) == 1
        assert segments[0].user == anna
        assert (segments[0].start_at, segments[0].end_at) == (start, end)
        assert OnCallDuty.objects.get(year=YEAR, week_number=WEEK).user == anna

    def test_gap_fill_by_duty_holder_is_not_noop(self, anna, bo, editor):
        """Coverage gap (release, later assignment): extending the duty
        holder's coverage back over the gap must not no-op."""
        start, end = week_span(YEAR, WEEK)
        services.apply_assignment(YEAR, WEEK, anna, start, editor)
        services.apply_assignment(YEAR, WEEK, None, moment(YEAR, WEEK, 2), editor)
        services.apply_assignment(YEAR, WEEK, bo, moment(YEAR, WEEK, 4), editor)

        change = services.apply_assignment(YEAR, WEEK, bo, moment(YEAR, WEEK, 2), editor)

        assert change is not None
        segments = week_segments()
        assert [(s.user, s.start_at, s.end_at) for s in segments] == [
            (anna, start, moment(YEAR, WEEK, 2)),
            (bo, moment(YEAR, WEEK, 2), end),
        ]

    def test_displaced_later_holder_notified(self, anna, bo, editor):
        """Review finding: reassigning from Monday over a split must
        notify the later-segment holder losing their shift too."""
        carl = User.objects.create_user("carl", first_name="Carl")
        start, _ = week_span(YEAR, WEEK)
        services.apply_assignment(YEAR, WEEK, anna, start, editor)
        services.apply_assignment(YEAR, WEEK, bo, moment(YEAR, WEEK, 2), editor)
        Notification.objects.all().delete()

        services.apply_assignment(YEAR, WEEK, carl, start, editor)

        recipients = set(Notification.objects.values_list("recipient__username", flat=True))
        assert {"anna", "bo", "carl"} <= recipients

    def test_reclaim_after_release_merges_segments(self, anna, editor):
        """Review finding: release-then-reclaim by the same person must
        not leave a cosmetic 'split week' (two adjacent own segments)."""
        start, end = week_span(YEAR, WEEK)
        services.apply_assignment(YEAR, WEEK, anna, start, editor)
        services.apply_assignment(YEAR, WEEK, None, moment(YEAR, WEEK, 1, 14), editor)
        services.apply_assignment(YEAR, WEEK, anna, moment(YEAR, WEEK, 1, 14), editor)

        segments = week_segments()
        assert len(segments) == 1
        assert (segments[0].start_at, segments[0].end_at) == (start, end)
        assert OnCallSegment.split_week_display(YEAR, WEEK) is None

    def test_week_53_and_year_rollover(self, anna, editor):
        # ISO year 2026 has 53 weeks; week 53 spans into January 2027.
        start, end = week_span(2026, 53)
        assert start.date().isocalendar()[:2] == (2026, 53)
        assert (end - timedelta(days=1)).date() > start.date()
        services.apply_assignment(2026, 53, anna, start, editor)
        segments = week_segments(2026, 53)
        assert segments[0].end_at == end


class TestClaimRelease:
    def test_claim_free_week(self, anna):
        services.claim_week(YEAR, WEEK, anna)
        duty = OnCallDuty.objects.get(year=YEAR, week_number=WEEK)
        assert duty.user == anna
        assert week_segments()[0].start_at == week_span(YEAR, WEEK)[0]

    def test_claim_taken_week_is_noop(self, anna, bo):
        services.claim_week(YEAR, WEEK, anna)
        services.claim_week(YEAR, WEEK, bo)
        assert OnCallDuty.objects.get(year=YEAR, week_number=WEEK).user == anna
        assert OnCallChange.objects.count() == 1

    def test_claim_after_mid_week_release_starts_at_release(self, anna, bo, editor):
        start, end = week_span(YEAR, WEEK)
        services.apply_assignment(YEAR, WEEK, anna, start, editor)
        release_at = moment(YEAR, WEEK, 2, 14)
        services.apply_assignment(YEAR, WEEK, None, release_at, editor)

        services.claim_week(YEAR, WEEK, bo)
        segments = week_segments()
        # Bo's coverage starts exactly where Anna's preserved record ends.
        assert [(s.user, s.start_at, s.end_at) for s in segments] == [
            (anna, start, release_at),
            (bo, release_at, end),
        ]

    def test_release_other_users_week_is_noop(self, anna, bo):
        services.claim_week(YEAR, WEEK, anna)
        result = services.release_week(YEAR, WEEK, bo)
        assert result is None
        assert OnCallDuty.objects.filter(year=YEAR, week_number=WEEK).exists()

    def test_release_future_week_removes_everything(self, anna):
        services.claim_week(YEAR, WEEK, anna)
        services.release_week(YEAR, WEEK, anna)
        assert not OnCallDuty.objects.filter(year=YEAR, week_number=WEEK).exists()
        assert week_segments() == []

    def test_split_week_release_keeps_current_holders_segment(self, anna, bo, editor):
        """Review finding: on a split current week only the base
        assignee sees 'Frigiv'; releasing must free their OWN trailing
        run, never truncate the earlier holder's active coverage."""
        now = timezone.localtime()
        iso = now.date().isocalendar()
        start, end = week_span(iso.year, iso.week)
        handover = (now + timedelta(hours=2)).replace(second=0, microsecond=0)
        if handover >= end:
            pytest.skip("handover would fall outside the current week")

        services.apply_assignment(iso.year, iso.week, anna, start, editor)
        services.apply_assignment(iso.year, iso.week, bo, handover, editor)

        services.release_week(iso.year, iso.week, bo)

        segments = list(
            OnCallSegment.objects.filter(year=iso.year, week_number=iso.week).order_by("start_at")
        )
        # Anna's segment survives untouched; only Bo's future part is gone.
        assert [(s.user, s.start_at, s.end_at) for s in segments] == [(anna, start, handover)]
        assert OnCallDuty.get_current().user == anna


class TestGetCurrentGap:
    def test_coverage_gap_returns_none(self, anna, bo, editor):
        """Review finding: released-now + assigned-later must not
        report the future holder as covering right now."""
        now = timezone.localtime()
        iso = now.date().isocalendar()
        start, end = week_span(iso.year, iso.week)
        later = (now + timedelta(hours=2)).replace(second=0, microsecond=0)
        if later >= end:
            pytest.skip("gap window would fall outside the current week")

        services.apply_assignment(iso.year, iso.week, anna, start, editor)
        services.apply_assignment(iso.year, iso.week, None, now, editor)
        services.apply_assignment(iso.year, iso.week, bo, later, editor)

        assert OnCallDuty.get_for_week(iso.year, iso.week).user == bo
        assert OnCallDuty.get_current() is None


class TestNotifications:
    def test_assignee_notified_when_assigned_by_other(self, anna, editor):
        services.apply_assignment(YEAR, WEEK, anna, week_span(YEAR, WEEK)[0], editor)
        notification = Notification.objects.get(recipient=anna)
        assert f"uge {WEEK}, {YEAR}" in notification.message
        assert notification.actor == editor

    def test_self_claim_stays_silent(self, anna):
        services.claim_week(YEAR, WEEK, anna)
        assert Notification.objects.count() == 0

    def test_displaced_holder_notified_on_handover(self, anna, bo, editor):
        services.apply_assignment(YEAR, WEEK, anna, week_span(YEAR, WEEK)[0], editor)
        Notification.objects.all().delete()
        services.apply_assignment(YEAR, WEEK, bo, moment(YEAR, WEEK, 3), editor)

        messages = {n.recipient.username: n.message for n in Notification.objects.all()}
        assert "bo" in messages and "overtager" in messages["anna"]

    def test_mid_week_suffix_in_message(self, anna, editor):
        services.apply_assignment(YEAR, WEEK, anna, moment(YEAR, WEEK, 2, 14), editor)
        notification = Notification.objects.get(recipient=anna)
        assert "fra on 14:00" in notification.message


class TestGetCurrent:
    def test_get_current_resolves_todays_holder(self, anna, bo, editor):
        now = timezone.localtime()
        iso = now.date().isocalendar()
        start, _ = week_span(iso.year, iso.week)
        services.apply_assignment(iso.year, iso.week, anna, start, editor)
        # Future-dated handover later today/tonight: duty.user flips to
        # Bo, but *now* Anna still covers.
        handover = (now + timedelta(hours=2)).replace(second=0, microsecond=0)
        _, end = week_span(iso.year, iso.week)
        if handover < end:
            services.apply_assignment(iso.year, iso.week, bo, handover, editor)
            duty = OnCallDuty.get_for_week(iso.year, iso.week)
            assert duty.user == bo
            assert OnCallDuty.get_current().user == anna
