"""Dashboard app configuration."""

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """Configuration for the dashboard application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dashboard"
    verbose_name = "Kontrolpanel"
