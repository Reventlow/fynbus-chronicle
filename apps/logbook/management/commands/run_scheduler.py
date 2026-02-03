"""
Management command to run the APScheduler for periodic tasks.

Usage:
    python manage.py run_scheduler

This starts a blocking scheduler that runs periodic tasks like
syncing ticket counts from ServiceDesk Plus.
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore

from apps.logbook.tasks import sync_current_week_tickets

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Run the APScheduler for periodic background tasks."""

    help = "Run the APScheduler for periodic tasks (ServiceDesk sync, etc.)"

    def handle(self, *args, **options) -> None:
        """Start the scheduler with configured jobs."""
        scheduler = BlockingScheduler()
        scheduler.add_jobstore(DjangoJobStore(), "default")

        # Get sync interval from settings (default: 5 minutes)
        interval = getattr(settings, "SERVICEDESK_SYNC_INTERVAL", 300)
        sync_enabled = getattr(settings, "SERVICEDESK_SYNC_ENABLED", False)

        if sync_enabled:
            scheduler.add_job(
                sync_current_week_tickets,
                trigger=IntervalTrigger(seconds=interval),
                id="sync_servicedesk_tickets",
                name="Sync ServiceDesk ticket counts",
                replace_existing=True,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Added ServiceDesk sync job (every {interval} seconds)"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "ServiceDesk sync is disabled (SERVICEDESK_SYNC_ENABLED=False)"
                )
            )

        self.stdout.write(self.style.SUCCESS("Starting scheduler..."))
        self.stdout.write("Press Ctrl+C to exit")

        try:
            scheduler.start()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Scheduler stopped"))
            scheduler.shutdown()
