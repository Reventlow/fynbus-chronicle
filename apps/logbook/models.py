"""
Models for the FynBus Chronicle logbook application.

These models track weekly IT activities including:
- Weekly logs with summaries and helpdesk statistics
- Priority items (ongoing tasks and projects)
- Staff absences
- Security/system incidents
"""

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class WeekLog(models.Model):
    """
    Represents a weekly IT log entry.

    Each week has one log entry containing helpdesk statistics,
    a summary of activities, and related priority items, absences,
    and incidents.
    """

    year = models.PositiveIntegerField(
        verbose_name="År",
        validators=[MinValueValidator(2024), MaxValueValidator(2100)],
        db_index=True,
    )
    week_number = models.PositiveIntegerField(
        verbose_name="Uge",
        validators=[MinValueValidator(1), MaxValueValidator(53)],
    )

    # Helpdesk statistics
    helpdesk_new = models.PositiveIntegerField(
        verbose_name="Nye sager",
        default=0,
        help_text="Antal nye helpdesk-sager i ugen",
    )
    helpdesk_closed = models.PositiveIntegerField(
        verbose_name="Lukkede sager",
        default=0,
        help_text="Antal lukkede helpdesk-sager i ugen",
    )
    helpdesk_open = models.PositiveIntegerField(
        verbose_name="Åbne sager",
        default=0,
        help_text="Samlet antal åbne sager ved ugens slutning",
    )

    # Weekly summary
    summary = models.TextField(
        verbose_name="Ugeoversigt",
        blank=True,
        help_text="Kort beskrivelse af ugens vigtigste aktiviteter",
    )

    # Monday meeting minutes
    meeting_skipped = models.BooleanField(
        verbose_name="Møde aflyst",
        default=False,
        help_text="Angiv om mandagsmødet blev aflyst denne uge",
    )
    meeting_skipped_reason = models.CharField(
        verbose_name="Årsag til aflysning",
        max_length=200,
        blank=True,
        help_text="Kort begrundelse for hvorfor mødet blev aflyst",
    )
    meeting_attendees = models.TextField(
        verbose_name="Deltagere",
        blank=True,
        default="",
        help_text="Deltagere til mandagsmødet",
    )
    meeting_minutes = models.TextField(
        verbose_name="Referat",
        blank=True,
        default="",
        help_text="Referat af mandagsmødet",
    )

    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weeklogs_created",
        verbose_name="Oprettet af",
    )
    created_at = models.DateTimeField(
        verbose_name="Oprettet",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        verbose_name="Opdateret",
        auto_now=True,
    )

    class Meta:
        verbose_name = "Ugelog"
        verbose_name_plural = "Ugelogs"
        ordering = ["-year", "-week_number"]
        unique_together = ["year", "week_number"]
        indexes = [
            models.Index(fields=["-year", "-week_number"]),
        ]

    def __str__(self) -> str:
        return f"Uge {self.week_number}, {self.year}"

    def get_absolute_url(self) -> str:
        """Return URL for viewing this week log."""
        return reverse("logbook:weeklog-detail", kwargs={"pk": self.pk})

    @classmethod
    def get_current_week(cls) -> "WeekLog | None":
        """
        Get or return None for the current week's log.

        Returns:
            WeekLog instance for current week, or None if not found.
        """
        now = timezone.now()
        iso_calendar = now.isocalendar()
        return cls.objects.filter(
            year=iso_calendar.year,
            week_number=iso_calendar.week,
        ).first()

    @classmethod
    def get_or_create_current_week(cls, user: User | None = None) -> "WeekLog":
        """
        Get or create the current week's log.

        Args:
            user: The user creating the log (if new).

        Returns:
            WeekLog instance for current week.
        """
        now = timezone.now()
        iso_calendar = now.isocalendar()
        weeklog, _ = cls.objects.get_or_create(
            year=iso_calendar.year,
            week_number=iso_calendar.week,
            defaults={"created_by": user},
        )
        return weeklog

    @property
    def week_label(self) -> str:
        """Human-readable week label."""
        return f"Uge {self.week_number}, {self.year}"

    @property
    def helpdesk_delta(self) -> int:
        """Calculate net change in helpdesk tickets."""
        return self.helpdesk_new - self.helpdesk_closed

    @staticmethod
    def helpdesk_weekly_averages() -> dict[str, float]:
        """
        Calculate average weekly created and closed tickets over the last 52 weeks.

        Returns:
            Dict with 'avg_new' and 'avg_closed' rounded to one decimal.
        """
        from django.db.models import Avg

        result = WeekLog.objects.order_by("-year", "-week_number")[:52].aggregate(
            avg_new=Avg("helpdesk_new"),
            avg_closed=Avg("helpdesk_closed"),
        )
        return {
            "avg_new": round(result["avg_new"] or 0, 1),
            "avg_closed": round(result["avg_closed"] or 0, 1),
        }

    def auto_close_stale_priorities(self) -> int:
        """Auto-close every active priority item whose ``last_active_at`` is
        older than ``PriorityItem.AUTO_CLOSE_AFTER_WEEKS`` weeks.

        Cheap and idempotent — safe to call on every view of the current
        week. Returns the number of items closed. Carry-over is *not*
        automatic — the user picks which open tasks to bring forward via
        the "Tilføj eksisterende opgave" dialog.
        """
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(
            weeks=PriorityItem.AUTO_CLOSE_AFTER_WEEKS
        )
        stale = list(
            PriorityItem.objects.filter(last_active_at__lt=cutoff).exclude(
                status=PriorityItem.Status.COMPLETED
            )
        )
        for item in stale:
            item.auto_close()
        return len(stale)

    def add_existing_priority_items(self, item_ids) -> int:
        """Carry the given priority items into this weeklog by creating
        appearance rows for any that aren't already present. Bumps each
        item's ``last_active_at`` so the auto-close clock resets.

        Returns the number of appearances actually created.
        """
        if not item_ids:
            return 0
        next_order = (
            self.priority_appearances.aggregate(m=models.Max("order"))["m"] or -1
        ) + 1
        existing = set(
            self.priority_appearances.filter(
                priority_item_id__in=item_ids
            ).values_list("priority_item_id", flat=True)
        )
        added = 0
        for item in PriorityItem.objects.filter(pk__in=item_ids):
            if item.pk in existing:
                continue
            PriorityItemAppearance.objects.create(
                priority_item=item,
                weeklog=self,
                order=next_order,
            )
            next_order += 1
            added += 1
            item.touch()
        return added


class PriorityItem(models.Model):
    """
    A long-lived priority task that may span many weekly logs.

    The task itself carries title/priority/status/notes and remembers
    when it was first created (``origin_weeklog``) and the last time a
    user actively touched it (``last_active_at`` — drives the auto-close
    rule). Per-week details (description, ordering) live on the related
    ``PriorityItemAppearance`` rows, one per week the task was visible.
    """

    AUTO_CLOSE_AFTER_WEEKS = 6

    class Priority(models.TextChoices):
        HIGH = "high", "Høj"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Lav"

    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Ikke startet"
        ONGOING = "ongoing", "Igangværende"
        BLOCKED = "blocked", "Blokeret"
        COMPLETED = "completed", "Afsluttet"

    origin_weeklog = models.ForeignKey(
        WeekLog,
        on_delete=models.CASCADE,
        related_name="originated_priority_items",
        verbose_name="Oprindelig ugelog",
        help_text="Den uge opgaven først blev oprettet i.",
    )
    title = models.CharField(verbose_name="Titel", max_length=200)
    priority = models.CharField(
        verbose_name="Prioritet",
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    status = models.CharField(
        verbose_name="Status",
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED,
    )
    notes = models.TextField(
        verbose_name="Noter",
        blank=True,
        help_text="Generelle noter, der gælder hele opgavens livscyklus",
    )

    # Auto-close machinery
    last_active_at = models.DateTimeField(
        verbose_name="Sidst aktiv",
        default=timezone.now,
        help_text=(
            "Bumpes ved bruger-handling (statusskift, redigering, ny "
            "uge-beskrivelse). Drevet af 6-ugers auto-luk-reglen."
        ),
    )
    auto_closed = models.BooleanField(
        verbose_name="Auto-lukket",
        default=False,
    )
    closed_at = models.DateTimeField(
        verbose_name="Lukket",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Prioriteret opgave"
        verbose_name_plural = "Prioriterede opgaver"
        ordering = ["-last_active_at", "-priority", "title"]
        indexes = [
            models.Index(fields=["status", "last_active_at"]),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def is_active(self) -> bool:
        """True for any status that's not 'completed'."""
        return self.status != self.Status.COMPLETED

    @property
    def has_history(self) -> bool:
        """True if this task has appeared on more than one weeklog —
        i.e. there's something worth showing on the history page.

        Used by the row template to conditionally render the "Se historik"
        link. Issues one COUNT query per call; cheap for the scale of
        a single weeklog's priority list (~10 items).
        """
        return self.appearances.count() > 1

    def touch(self, *, save: bool = True) -> None:
        """Bump last_active_at to mark a real user-driven change."""
        self.last_active_at = timezone.now()
        if save:
            self.save(update_fields=["last_active_at", "updated_at"])

    def auto_close(self) -> None:
        """Close this item due to the 6-week-since-last-active rule."""
        now = timezone.now()
        self.status = self.Status.COMPLETED
        self.auto_closed = True
        self.closed_at = now
        self.save(update_fields=["status", "auto_closed", "closed_at", "updated_at"])

    def merge_into(self, winner: "PriorityItem") -> None:
        """Fold this task into ``winner`` and delete it.

        The **winner** must be active (you can't fold work into a task
        that's already declared done). The **loser** can be anything —
        merging a closed task into an active one is supported as a way
        to revive prematurely-closed work into a live task without
        manually reopening it first. After the merge:

        * Every appearance of ``self`` moves to ``winner``. If ``winner``
          already has an appearance on the same weeklog, the two
          descriptions are concatenated with a ``— flettet —`` separator
          and the loser appearance is dropped.
        * ``winner.notes`` gets the loser's notes appended with a
          ``— flettet fra: <title> —`` header so context isn't lost.
        * ``winner.origin_weeklog`` becomes the earlier of the two
          origins so the history page starts from the real beginning.
        * ``winner.last_active_at`` becomes the max of both.
        * ``winner``'s title, priority, and status are kept as-is.
        * ``self`` is deleted at the end.

        Raises ``ValueError`` for self-merge or when either task is
        already completed.
        """
        from django.db import transaction

        if self.pk == winner.pk:
            raise ValueError("Cannot merge a task into itself.")
        if not winner.is_active:
            raise ValueError(
                "Winner task must be active — you can't merge into a closed task."
            )

        sep = "\n\n— flettet —\n"

        with transaction.atomic():
            # Move / merge appearances
            for la in list(self.appearances.select_related("weeklog")):
                wa = winner.appearances.filter(weeklog=la.weeklog).first()
                if wa is None:
                    la.priority_item = winner
                    la.save(update_fields=["priority_item"])
                else:
                    if la.description and la.description.strip() != wa.description.strip():
                        wa.description = (
                            (wa.description + sep + la.description).strip()
                            if wa.description
                            else la.description
                        )
                        wa.save(update_fields=["description", "updated_at"])
                    la.delete()

            # Combine notes
            if self.notes and self.notes.strip():
                header = f"\n\n— flettet fra: {self.title} —\n"
                winner.notes = (
                    (winner.notes + header + self.notes).strip()
                    if winner.notes
                    else self.notes
                )

            # Pick earlier origin
            if (
                self.origin_weeklog.year,
                self.origin_weeklog.week_number,
            ) < (
                winner.origin_weeklog.year,
                winner.origin_weeklog.week_number,
            ):
                winner.origin_weeklog = self.origin_weeklog

            # Max of last_active_at
            if self.last_active_at > winner.last_active_at:
                winner.last_active_at = self.last_active_at

            winner.save(
                update_fields=[
                    "notes",
                    "origin_weeklog",
                    "last_active_at",
                    "updated_at",
                ]
            )
            self.delete()

    def reopen(self, *, into_weeklog: WeekLog | None = None) -> None:
        """Flip the item back to ongoing and bump last_active_at.

        If ``into_weeklog`` is supplied, an appearance for that week is
        created (if it doesn't already exist) so the item shows up there
        immediately. Used by the "toggle open" UX which automatically
        adds reopened tasks to the current week.
        """
        self.status = self.Status.ONGOING
        self.auto_closed = False
        self.closed_at = None
        self.last_active_at = timezone.now()
        self.save(update_fields=[
            "status", "auto_closed", "closed_at", "last_active_at", "updated_at",
        ])
        if into_weeklog is not None:
            PriorityItemAppearance.objects.get_or_create(
                priority_item=self,
                weeklog=into_weeklog,
            )


class PriorityItemAppearance(models.Model):
    """A priority task's appearance in a single weekly log.

    Carries the per-week description and the per-week display order.
    One row per (task, weeklog) pair. Auto-created by the carry-over
    flow when a current weeklog is opened, or explicitly by the user
    when they add a task on a given week.
    """

    priority_item = models.ForeignKey(
        PriorityItem,
        on_delete=models.CASCADE,
        related_name="appearances",
        verbose_name="Opgave",
    )
    weeklog = models.ForeignKey(
        WeekLog,
        on_delete=models.CASCADE,
        related_name="priority_appearances",
        verbose_name="Ugelog",
    )
    description = models.TextField(
        verbose_name="Beskrivelse",
        blank=True,
        default="",
        help_text="Hvad skete der med opgaven i denne uge?",
    )
    order = models.PositiveIntegerField(
        verbose_name="Rækkefølge",
        default=0,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Opgave-tilknytning"
        verbose_name_plural = "Opgave-tilknytninger"
        ordering = ["order", "created_at"]
        unique_together = [("priority_item", "weeklog")]
        indexes = [
            models.Index(fields=["weeklog", "order"]),
        ]

    def __str__(self) -> str:
        return f"{self.priority_item.title} @ {self.weeklog.week_label}"


class Absence(models.Model):
    """
    Tracks staff absences for IT planning purposes.

    Includes vacation, sick leave, courses, and other absences
    that affect IT support availability.
    """

    class AbsenceType(models.TextChoices):
        VACATION = "vacation", "Ferie"
        SICK = "sick", "Sygdom"
        COURSE = "course", "Kursus"
        MEETING = "meeting", "Møde/Konference"
        FLEX = "flex", "Flex fri"
        WFH = "wfh", "Arbejder hjemme"
        OTHER = "other", "Andet"

    weeklog = models.ForeignKey(
        WeekLog,
        on_delete=models.CASCADE,
        related_name="absences",
        verbose_name="Ugelog",
    )
    staff_name = models.CharField(
        verbose_name="Medarbejder",
        max_length=100,
    )
    absence_type = models.CharField(
        verbose_name="Type",
        max_length=20,
        choices=AbsenceType.choices,
        default=AbsenceType.VACATION,
    )
    start_date = models.DateField(
        verbose_name="Fra dato",
    )
    end_date = models.DateField(
        verbose_name="Til dato",
    )
    notes = models.CharField(
        verbose_name="Noter",
        max_length=200,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bemanding"
        verbose_name_plural = "Bemanding"
        ordering = ["start_date"]

    def __str__(self) -> str:
        return f"{self.staff_name}: {self.get_absence_type_display()} ({self.start_date} - {self.end_date})"

    @property
    def duration_days(self) -> int:
        """Calculate duration in days (inclusive)."""
        return (self.end_date - self.start_date).days + 1

    @property
    def weekday_range(self) -> str:
        """Return Danish weekday range, e.g. 'onsdag til fredag' or 'mandag'."""
        days_da = [
            "mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag",
        ]
        start_day = days_da[self.start_date.weekday()]
        end_day = days_da[self.end_date.weekday()]
        if self.start_date == self.end_date:
            return start_day.capitalize()
        return f"{start_day.capitalize()} til {end_day}"


class Incident(models.Model):
    """
    Records security or system incidents.

    Used for tracking and reporting significant events
    that require documentation or follow-up.
    """

    class Severity(models.TextChoices):
        CRITICAL = "critical", "Kritisk"
        HIGH = "high", "Høj"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Lav"

    class IncidentType(models.TextChoices):
        SECURITY = "security", "Sikkerhed"
        SYSTEM = "system", "Systemfejl"
        NETWORK = "network", "Netværk"
        DATA = "data", "Data"
        OTHER = "other", "Andet"

    weeklog = models.ForeignKey(
        WeekLog,
        on_delete=models.CASCADE,
        related_name="incidents",
        verbose_name="Ugelog",
    )
    title = models.CharField(
        verbose_name="Titel",
        max_length=200,
    )
    incident_type = models.CharField(
        verbose_name="Type",
        max_length=20,
        choices=IncidentType.choices,
        default=IncidentType.OTHER,
    )
    severity = models.CharField(
        verbose_name="Alvorlighed",
        max_length=20,
        choices=Severity.choices,
        default=Severity.MEDIUM,
    )
    description = models.TextField(
        verbose_name="Beskrivelse",
        help_text="Detaljeret beskrivelse af hændelsen",
    )
    resolution = models.TextField(
        verbose_name="Løsning",
        blank=True,
        help_text="Hvordan blev hændelsen løst?",
    )
    occurred_at = models.DateTimeField(
        verbose_name="Tidspunkt",
        default=timezone.now,
    )
    resolved = models.BooleanField(
        verbose_name="Løst",
        default=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Hændelse"
        verbose_name_plural = "Hændelser"
        ordering = ["-occurred_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.get_severity_display()})"
