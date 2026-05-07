"""Account models for login/logout tracking and API key issuance."""

import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


# Raw key prefix conventions:
#   fbc_R_<32 chars>   read-only
#   fbc_W_<32 chars>   read+write
# The 8-character prefix stored in the DB is `fbc_R_xx` / `fbc_W_xx`,
# i.e. the literal scope marker plus two characters of the random body.
# Enough to identify the key in UIs and logs without exposing it.
RAW_KEY_BODY_BYTES = 24  # → 32 chars urlsafe base64 (no padding)


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


class APIKey(models.Model):
    """Per-user API key used by external clients (MCP server, scripts).

    Raw keys are never persisted — only the SHA-256 digest. The 8-character
    plaintext prefix (e.g. ``fbc_R_aB``) lets users identify a key in the
    UI and admin without exposing the secret.
    """

    class Scope(models.TextChoices):
        READ = "read", "Læs"
        WRITE = "write", "Læs+skriv"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
        verbose_name="Bruger",
    )
    scope = models.CharField(
        max_length=10,
        choices=Scope.choices,
        default=Scope.READ,
        verbose_name="Adgang",
    )
    label = models.CharField(
        max_length=80,
        blank=True,
        default="",
        verbose_name="Etiket",
        help_text="Til genkendelse — fx 'Claude MCP – laptop'",
    )
    prefix = models.CharField(max_length=10, db_index=True, unique=True)
    hashed_key = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "API-nøgle"
        verbose_name_plural = "API-nøgler"

    def __str__(self) -> str:
        suffix = " (tilbagekaldt)" if self.revoked_at else ""
        return f"{self.user} – {self.get_scope_display()} – {self.prefix}{suffix}"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def revoke(self) -> None:
        """Mark this key as revoked. Idempotent."""
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])

    @staticmethod
    def hash_raw(raw_key: str) -> str:
        """SHA-256 of the raw key — what's stored and compared against."""
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @classmethod
    def generate(
        cls,
        *,
        user,
        scope: str,
        label: str = "",
    ) -> tuple["APIKey", str]:
        """Mint a new key. Returns (instance, raw_key). Raw key is shown ONCE."""
        scope_marker = "R" if scope == cls.Scope.READ else "W"
        body = secrets.token_urlsafe(RAW_KEY_BODY_BYTES).rstrip("=")
        raw_key = f"fbc_{scope_marker}_{body}"
        prefix = raw_key[:8]  # "fbc_R_xx" or "fbc_W_xx"
        instance = cls.objects.create(
            user=user,
            scope=scope,
            label=label,
            prefix=prefix,
            hashed_key=cls.hash_raw(raw_key),
        )
        return instance, raw_key

    @classmethod
    def authenticate(cls, raw_key: str) -> "APIKey | None":
        """Resolve a raw key to its active APIKey row, or None.

        Side-effect: stamps last_used_at on success.
        """
        if not raw_key or not raw_key.startswith("fbc_"):
            return None
        prefix = raw_key[:8]
        try:
            api_key = cls.objects.select_related("user").get(prefix=prefix, revoked_at__isnull=True)
        except cls.DoesNotExist:
            return None
        if api_key.hashed_key != cls.hash_raw(raw_key):
            return None
        # Stamp last_used_at without bumping updated_at on the user row, etc.
        cls.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())
        return api_key
