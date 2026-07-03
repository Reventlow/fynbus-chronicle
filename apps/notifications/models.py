"""
In-app notifications shown behind the bell in the global nav.

Kept deliberately generic (recipient, message, optional link) so any
feature can notify users — first consumer is the on-call calendar
(assignment/handover notices, FR #5).
"""

from django.contrib.auth.models import User
from django.db import models


class Notification(models.Model):
    """One message for one user, read when the bell panel is opened."""

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Modtager",
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_sent",
        verbose_name="Udført af",
    )
    message = models.CharField(max_length=255, verbose_name="Besked")
    url = models.CharField(max_length=255, blank=True, verbose_name="Link")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oprettet")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Læst")

    class Meta:
        verbose_name = "Notifikation"
        verbose_name_plural = "Notifikationer"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.recipient.username}: {self.message}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    @classmethod
    def notify(
        cls,
        recipient: User,
        message: str,
        url: str = "",
        actor: User | None = None,
    ) -> "Notification | None":
        """Create a notification, skipping self-notifications and inactive users."""
        if recipient is None or not recipient.is_active:
            return None
        if actor is not None and recipient.pk == actor.pk:
            return None
        return cls.objects.create(recipient=recipient, actor=actor, message=message, url=url)

    @classmethod
    def unread_count(cls, user: User) -> int:
        return cls.objects.filter(recipient=user, read_at__isnull=True).count()
