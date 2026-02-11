"""On-call duty app configuration."""

from django.apps import AppConfig


class OncallConfig(AppConfig):
    """Configuration for the on-call duty application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.oncall"
    verbose_name = "Rådighedsvagt"
