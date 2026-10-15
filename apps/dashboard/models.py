"""
Models for the dashboard application.

``StatisticsShareLink`` — a secret, read-only link to the statistics JSON
(and a guide to it), for tools that cannot log in, such as Claude on the
web. Each link is a random token: whoever has it can read the statistics
until it expires or is revoked, and nothing else.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


def _new_token() -> str:
    return secrets.token_urlsafe(32)  # 43 characters, 256 bits


class StatisticsShareLink(models.Model):
    """A revocable, expiring public link to the statistics export."""

    # Choices offered when creating a link, in days.
    VALIDITY_CHOICES = ((7, "7 dage"), (30, "30 dage"), (90, "90 dage"), (365, "1 år"))
    DEFAULT_VALIDITY_DAYS = 30

    label = models.CharField(
        verbose_name="Navn",
        max_length=100,
        help_text="Hvad linket bruges til, f.eks. 'Claude Motion'.",
    )
    token = models.CharField(max_length=64, unique=True, default=_new_token, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="statistics_share_links",
        verbose_name="Oprettet af",
    )
    created_at = models.DateTimeField(verbose_name="Oprettet", auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name="Udløber")
    revoked_at = models.DateTimeField(verbose_name="Tilbagekaldt", null=True, blank=True)
    last_used_at = models.DateTimeField(verbose_name="Sidst brugt", null=True, blank=True)
    use_count = models.PositiveIntegerField(verbose_name="Antal hentninger", default=0)

    class Meta:
        verbose_name = "Delt statistik-link"
        verbose_name_plural = "Delte statistik-links"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.label

    def save(self, *args, **kwargs):
        if self.expires_at is None:
            self.expires_at = timezone.now() + timedelta(days=self.DEFAULT_VALIDITY_DAYS)
        super().save(*args, **kwargs)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()

    @property
    def status_label(self) -> str:
        if self.revoked_at:
            return "Tilbagekaldt"
        if self.expires_at <= timezone.now():
            return "Udløbet"
        return "Aktiv"

    @classmethod
    def active(cls, token: str) -> "StatisticsShareLink | None":
        """The active link with this token, or None."""
        link = cls.objects.filter(token=token).first()
        return link if link and link.is_active else None

    def record_use(self) -> None:
        """Count a fetch (atomically, so parallel fetches are not lost)."""
        type(self).objects.filter(pk=self.pk).update(
            use_count=models.F("use_count") + 1, last_used_at=timezone.now()
        )

    def revoke(self) -> None:
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])

    def get_data_path(self) -> str:
        return reverse("dashboard:statistics-shared-json", kwargs={"token": self.token})

    def get_guide_path(self) -> str:
        return reverse("dashboard:statistics-shared-guide", kwargs={"token": self.token})
