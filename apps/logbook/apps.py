"""Logbook app configuration."""

from django.apps import AppConfig


class LogbookConfig(AppConfig):
    """Configuration for the logbook application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.logbook"
    verbose_name = "Ugelog"
