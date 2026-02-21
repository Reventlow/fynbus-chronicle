"""Account models for login/logout tracking."""

from django.conf import settings
from django.db import models


class LoginLog(models.Model):
    """Records user login and logout events."""

    class Event(models.TextChoices):
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="login_logs",
        null=True,
        blank=True,
    )
    event = models.CharField(max_length=10, choices=Event.choices)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default="")

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Login log"
        verbose_name_plural = "Login logs"

    def __str__(self) -> str:
        return f"{self.user} – {self.event} @ {self.timestamp:%Y-%m-%d %H:%M}"
