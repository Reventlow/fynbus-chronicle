"""
Models for the on-call duty (rådighedsvagt) application.

Three related tables:

- ``OnCallDuty`` — one row per ISO week; ``user`` is the *base* assignee
  and is kept equal to the holder of the last coverage segment of the
  week. Unchanged schema since 0001 so existing consumers keep working.
- ``OnCallSegment`` — per-period coverage within a week (supports
  mid-week and intra-day handovers). Deliberately has NO foreign key to
  ``OnCallDuty``: releasing a week deletes the duty row, but the
  coverage record must survive for the history.
- ``OnCallChange`` — audit trail of assignment changes (who changed
  what, when, effective from). Rows exist from 0.8.0 onwards; earlier
  changes were never recorded.

All writes to duty/segments/changes go through
``apps.oncall.services.apply_assignment`` — never write these tables
directly from views.
"""

from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

#: Short Danish weekday labels indexed by ``date.weekday()``.
DAYS_SHORT = ["ma", "ti", "on", "to", "fr", "lø", "sø"]

YEAR_VALIDATORS = [MinValueValidator(2024), MaxValueValidator(2100)]
WEEK_VALIDATORS = [MinValueValidator(1), MaxValueValidator(53)]


def week_span(year: int, week: int) -> tuple[datetime, datetime]:
    """Aware [Monday 00:00, next Monday 00:00) span for an ISO week.

    Boundaries are built per-day and made aware separately so DST
    transitions inside the week cannot skew them.
    """
    monday = date.fromisocalendar(year, week, 1)
    tz = timezone.get_default_timezone()
    start = timezone.make_aware(datetime.combine(monday, time.min), tz)
    end = timezone.make_aware(datetime.combine(monday + timedelta(days=7), time.min), tz)
    return start, end


def boundary_label(moment: datetime, *, is_end: bool = False) -> str:
    """Compact Danish label for a segment boundary, e.g. 'ma' or 'on 14:00'.

    Exclusive end boundaries at midnight belong to the previous day
    ('until Sunday midnight' renders as 'sø', not 'ma').
    """
    local = timezone.localtime(moment)
    if local.time() == time.min:
        day = local - timedelta(days=1) if is_end else local
        return DAYS_SHORT[day.weekday()]
    return f"{DAYS_SHORT[local.weekday()]} {local:%H:%M}"


class OnCallDuty(models.Model):
    """
    Represents a weekly on-call duty assignment.

    Each week can have at most one *base* assignee; ``user`` always
    matches the holder of the week's last coverage segment. For "who is
    on call right now" use :meth:`get_current`, which resolves the
    current segment.
    """

    year = models.PositiveIntegerField(
        verbose_name="År",
        validators=YEAR_VALIDATORS,
    )
    week_number = models.PositiveIntegerField(
        verbose_name="Uge",
        validators=WEEK_VALIDATORS,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Medarbejder",
        related_name="oncall_duties",
    )
    notes = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Noter",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rådighedsvagt"
        verbose_name_plural = "Rådighedsvagter"
        ordering = ["-year", "-week_number"]
        unique_together = ["year", "week_number"]
        indexes = [
            models.Index(fields=["-year", "-week_number"]),
        ]

    def __str__(self) -> str:
        return f"Uge {self.week_number}, {self.year} - {self.user.get_full_name() or self.user.username}"

    @property
    def week_label(self) -> str:
        """Human-readable week label."""
        return f"Uge {self.week_number}, {self.year}"

    @classmethod
    def get_current(cls) -> "OnCallDuty | None":
        """Get on-call duty for the current ISO week.

        ``user`` on the returned instance is resolved to whoever covers
        *right now* (segment-aware), swapped in memory only — NEVER call
        ``.save()`` on an instance returned from here. During a coverage
        gap (released mid-week, next holder starts later) nobody covers
        right now, so None is returned even though a duty row exists.
        The reverse gap — the week's tail was freed while the earlier
        holder is still mid-shift, so no duty row exists — returns an
        unsaved instance synthesized from the covering segment.
        """
        now = timezone.localtime()
        iso = now.date().isocalendar()
        duty = cls.objects.filter(year=iso.year, week_number=iso.week).select_related("user").first()
        segment = OnCallSegment.covering(now)
        if segment is not None:
            if duty is None:
                return cls(year=iso.year, week_number=iso.week, user=segment.user)
            if segment.user_id != duty.user_id:
                duty.user = segment.user
            return duty
        if duty is None:
            return None
        if OnCallSegment.objects.filter(year=iso.year, week_number=iso.week).exists():
            return None
        # No segments at all (pre-backfill data): fall back to the base assignee.
        return duty

    @classmethod
    def get_for_week(cls, year: int, week: int) -> "OnCallDuty | None":
        """Get on-call duty for a specific week (base assignee, unresolved)."""
        return cls.objects.filter(year=year, week_number=week).select_related("user").first()


class OnCallSegment(models.Model):
    """A contiguous span within one ISO week covered by one person.

    ``end_at`` is exclusive, so a handover at 14:00 splits cleanly:
    the old holder's segment ends 14:00, the new one starts 14:00.
    Segments of a week never overlap and run contiguously from the
    earliest start to the end of the week — enforced by
    ``services.apply_assignment``, not by the database.
    """

    year = models.PositiveIntegerField(
        verbose_name="År",
        validators=YEAR_VALIDATORS,
    )
    week_number = models.PositiveIntegerField(
        verbose_name="Uge",
        validators=WEEK_VALIDATORS,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Medarbejder",
        related_name="oncall_segments",
    )
    start_at = models.DateTimeField(verbose_name="Fra")
    end_at = models.DateTimeField(verbose_name="Til")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vagtperiode"
        verbose_name_plural = "Vagtperioder"
        ordering = ["start_at"]
        indexes = [
            models.Index(fields=["year", "week_number"]),
            models.Index(fields=["start_at", "end_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=F("start_at")),
                name="oncall_segment_ends_after_start",
            ),
        ]

    def __str__(self) -> str:
        name = self.user.get_full_name() or self.user.username
        return f"Uge {self.week_number}, {self.year}: {name} ({self.range_label})"

    @property
    def range_label(self) -> str:
        """Compact Danish range, e.g. 'ma–on', 'on 14:00–sø' or 'to'."""
        start = boundary_label(self.start_at)
        end = boundary_label(self.end_at, is_end=True)
        return start if start == end else f"{start}–{end}"

    @classmethod
    def covering(cls, moment: datetime) -> "OnCallSegment | None":
        """The segment covering the given moment, if any."""
        return (
            cls.objects.filter(start_at__lte=moment, end_at__gt=moment)
            .select_related("user")
            .first()
        )

    @classmethod
    def for_week(cls, year: int, week: int) -> "models.QuerySet[OnCallSegment]":
        """All segments of a week, chronological."""
        return cls.objects.filter(year=year, week_number=week).select_related("user")

    @classmethod
    def split_week_display(cls, year: int, week: int) -> str | None:
        """'Anna Andersen (ma–on), Bo Berg (on 14:00–sø)' for split weeks.

        None for whole-week (or uncovered) weeks, so single-holder
        rendering everywhere stays exactly as before FR #5.
        """
        segments = list(cls.for_week(year, week))
        if len(segments) < 2:
            return None
        return ", ".join(
            f"{s.user.get_full_name() or s.user.username} ({s.range_label})" for s in segments
        )


class OnCallChange(models.Model):
    """Audit trail for on-call assignment changes.

    ``from_user`` NULL = week was free (claim / first assignment);
    ``to_user`` NULL = released. ``effective_at`` is the week's Monday
    00:00 for whole-week changes and a mid-week moment for handovers —
    it bridges the audit trail to the coverage segments.

    Changes before 0.8.0 were never recorded, so old weeks have no rows.
    """

    year = models.PositiveIntegerField(
        verbose_name="År",
        validators=YEAR_VALIDATORS,
    )
    week_number = models.PositiveIntegerField(
        verbose_name="Uge",
        validators=WEEK_VALIDATORS,
    )
    from_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="oncall_changes_from",
        verbose_name="Fra",
    )
    to_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="oncall_changes_to",
        verbose_name="Til",
    )
    effective_at = models.DateTimeField(verbose_name="Gældende fra")
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="oncall_changes_made",
        verbose_name="Ændret af",
    )
    changed_at = models.DateTimeField(
        verbose_name="Ændret",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Vagtændring"
        verbose_name_plural = "Vagtændringer"
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["year", "week_number"]),
        ]

    def __str__(self) -> str:
        def name(user: User | None) -> str:
            if user is None:
                return "Ledig"
            return user.get_full_name() or user.username

        return f"Uge {self.week_number}, {self.year}: {name(self.from_user)} → {name(self.to_user)}"

    @property
    def is_whole_week(self) -> bool:
        """True when the change applies from the start of the week."""
        return self.effective_at == week_span(self.year, self.week_number)[0]

    @property
    def effective_label(self) -> str:
        """Compact Danish label for when the change takes effect."""
        return boundary_label(self.effective_at)
