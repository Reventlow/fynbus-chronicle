"""
Models for the on-call duty (rådighedsvagt) application.

Tracks which team member is on-call for each week.
"""

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class OnCallDuty(models.Model):
    """
    Represents a weekly on-call duty assignment.

    Each week can have at most one person on-call.
    """

    year = models.PositiveIntegerField(
        verbose_name="År",
        validators=[MinValueValidator(2024), MaxValueValidator(2100)],
    )
    week_number = models.PositiveIntegerField(
        verbose_name="Uge",
        validators=[MinValueValidator(1), MaxValueValidator(53)],
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
        """Get on-call duty for the current ISO week."""
        now = timezone.now()
        iso = now.isocalendar()
        return cls.objects.filter(year=iso.year, week_number=iso.week).select_related("user").first()

    @classmethod
    def get_for_week(cls, year: int, week: int) -> "OnCallDuty | None":
        """Get on-call duty for a specific week."""
        return cls.objects.filter(year=year, week_number=week).select_related("user").first()
