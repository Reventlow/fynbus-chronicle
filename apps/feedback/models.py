"""Feature request / development pipeline models.

The user-facing surface is a Kanban-style board: ``open`` requests on the
left, ``in_progress`` middle, ``solved`` bucket on the right (or below).
Within each column the manual ``order`` field drives the sort.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class FeatureRequest(models.Model):
    """A request for new functionality, a UI tweak, an integration, or a bug fix."""

    class Category(models.TextChoices):
        TECHNICAL = "technical", "Teknisk"
        UI = "ui", "UI / brugerflade"
        INTEGRATION = "integration", "Integration"
        BUG = "bug", "Fejl"
        OTHER = "other", "Andet"

    class Importance(models.TextChoices):
        LOW = "low", "Lav"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "Høj"
        CRITICAL = "critical", "Kritisk"

    class Status(models.TextChoices):
        OPEN = "open", "Åben"
        IN_PROGRESS = "in_progress", "I gang"
        SOLVED = "solved", "Løst"

    title = models.CharField(verbose_name="Titel", max_length=200)
    description = models.TextField(
        verbose_name="Beskrivelse",
        blank=True,
        help_text="Hvad ønskes der? Hvorfor? Eventuelle links til GitHub-issues, Figma osv.",
    )
    category = models.CharField(
        verbose_name="Kategori",
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    importance = models.CharField(
        verbose_name="Vigtighed",
        max_length=10,
        choices=Importance.choices,
        default=Importance.MEDIUM,
    )
    status = models.CharField(
        verbose_name="Status",
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    order = models.PositiveIntegerField(
        verbose_name="Rækkefølge",
        default=0,
        help_text="Manuel sortering inden for kolonnen.",
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feature_requests_submitted",
        verbose_name="Indsendt af",
    )
    solved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feature_requests_solved",
        verbose_name="Løst af",
    )
    solved_at = models.DateTimeField(
        verbose_name="Løst",
        null=True,
        blank=True,
    )
    resolution_notes = models.TextField(
        verbose_name="Løsning",
        blank=True,
        help_text="Hvad endte vi med at gøre? Hvilken commit / pr / hvilken version?",
    )
    triggers_version_bump = models.BooleanField(
        verbose_name="Udløser version-bump",
        default=False,
        help_text=(
            "Sæt sand hvis forslaget kræver et minor- eller major-bump af "
            "applikationen, ikke kun en patch. Bruges til at planlægge "
            "udgivelseskadencen."
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Feature-forslag"
        verbose_name_plural = "Feature-forslag"
        ordering = ["status", "order", "-created_at"]
        indexes = [
            models.Index(fields=["status", "order"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.OPEN

    @property
    def is_in_progress(self) -> bool:
        return self.status == self.Status.IN_PROGRESS

    @property
    def is_solved(self) -> bool:
        return self.status == self.Status.SOLVED

    def mark_solved(self, *, by) -> None:
        was_solved = self.is_solved
        self.status = self.Status.SOLVED
        self.solved_by = by
        self.solved_at = timezone.now()
        self.save(update_fields=["status", "solved_by", "solved_at", "updated_at"])
        if not was_solved:
            self.notify_submitter_solved(actor=by)

    def notify_submitter_solved(self, *, actor=None) -> None:
        """Bell-notify the submitter that their suggestion shipped.

        ``Notification.notify`` already skips inactive users and the case
        where the submitter solved their own request. Callers are
        responsible for only invoking this on the open/in_progress →
        solved transition so reopen/re-solve cycles don't spam.
        """
        from django.urls import reverse

        from apps.notifications.models import Notification

        if self.submitted_by is None:
            return
        Notification.notify(
            recipient=self.submitted_by,
            message=f"Dit forslag ”{self.title}” er løst",
            url=reverse("feedback:detail", kwargs={"pk": self.pk}),
            actor=actor,
        )

    def reopen(self) -> None:
        self.status = self.Status.OPEN
        self.solved_by = None
        self.solved_at = None
        self.save(update_fields=["status", "solved_by", "solved_at", "updated_at"])
