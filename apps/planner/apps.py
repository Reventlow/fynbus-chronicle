"""MS Planner board: a mirror of one Planner plan, with changes made by
editors and linked priorities and cases kept in step both ways."""

from django.apps import AppConfig


class PlannerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.planner"
    verbose_name = "Planner"

    def ready(self) -> None:
        from django.db.models.signals import post_save

        from apps.cves.models import CVECase
        from apps.logbook.models import PriorityItem

        from .linksync import chronicle_changed

        def on_save(sender, instance, raw=False, **kwargs):
            if not raw:  # not while loading fixtures
                chronicle_changed(instance)

        for model in (PriorityItem, CVECase):
            post_save.connect(on_save, sender=model, dispatch_uid=f"planner_sync_{model.__name__}", weak=False)
