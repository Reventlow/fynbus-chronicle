"""Accounts app configuration."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configuration for the accounts application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Konti"

    def ready(self) -> None:
        """Register signal handlers for login/logout tracking."""
        import apps.accounts.signals  # noqa: F401
