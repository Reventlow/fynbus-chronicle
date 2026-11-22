"""Keep the running week log's delopgave counts current (1.27.0).

Any change that can move the counts (a delopgave added, changed or deleted,
or a sag's kind changed) re-records them on this week's log. Once the week
ends the log keeps the last numbers, which are how the week ended.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.cves.models import CVECase, CVETask, record_week_task_stats


@receiver(post_save, sender=CVETask, dispatch_uid="cves_task_saved_week_stats")
@receiver(post_delete, sender=CVETask, dispatch_uid="cves_task_deleted_week_stats")
@receiver(post_save, sender=CVECase, dispatch_uid="cves_case_saved_week_stats")
def refresh_week_task_stats(sender, **kwargs) -> None:
    record_week_task_stats()
