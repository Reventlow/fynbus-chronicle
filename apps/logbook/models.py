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
        help_text="Deltagere til mandagsmødet",
    )
    meeting_minutes = models.TextField(
        verbose_name="Referat",
        blank=True,
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


class PriorityItem(models.Model):
    """
    Represents a priority task or project being tracked.

    Priority items can span multiple weeks and track status
    from 'not started' through 'completed'.
    """

    class Priority(models.TextChoices):
        HIGH = "high", "Høj"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Lav"

    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Ikke startet"
        ONGOING = "ongoing", "Igangværende"
        BLOCKED = "blocked", "Blokeret"
        COMPLETED = "completed", "Afsluttet"

    weeklog = models.ForeignKey(
        WeekLog,
        on_delete=models.CASCADE,
        related_name="priority_items",
        verbose_name="Ugelog",
    )
    title = models.CharField(
        verbose_name="Titel",
        max_length=200,
    )
    description = models.TextField(
        verbose_name="Beskrivelse",
        blank=True,
        help_text="Detaljeret beskrivelse af opgaven",
    )
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
        help_text="Eventuelle noter eller opdateringer",
    )
    order = models.PositiveIntegerField(
        verbose_name="Rækkefølge",
        default=0,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Prioriteret opgave"
        verbose_name_plural = "Prioriterede opgaver"
        ordering = ["order", "-priority", "title"]

    def __str__(self) -> str:
        return self.title

    @property
    def is_active(self) -> bool:
        """Check if item is still active (not completed)."""
        return self.status != self.Status.COMPLETED


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
