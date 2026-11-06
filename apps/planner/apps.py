"""MS Planner board: a read-only mirror of one Planner plan."""

from django.apps import AppConfig


class PlannerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.planner"
    verbose_name = "Planner"
