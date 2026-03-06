"""
Management command to periodically sync ServiceDesk tickets.

Usage:
    python manage.py run_scheduler

Runs a simple loop that syncs ticket counts every SERVICEDESK_SYNC_INTERVAL
seconds (default: 300). The dashboard sync button works independently.
"""

import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.logbook.tasks import sync_current_week_tickets

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Run periodic ServiceDesk sync in a simple loop."""

    help = "Run periodic ServiceDesk sync (loops forever, Ctrl+C to stop)"

    def handle(self, *args, **options) -> None:
        """Loop forever: sync tickets, sleep, repeat."""
        interval = getattr(settings, "SERVICEDESK_SYNC_INTERVAL", 300)
        sync_enabled = getattr(settings, "SERVICEDESK_SYNC_ENABLED", False)

        if not sync_enabled:
            self.stdout.write(
                self.style.WARNING(
                    "ServiceDesk sync is disabled (SERVICEDESK_SYNC_ENABLED=False)"
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting ServiceDesk sync loop (every {interval}s). "
                "Press Ctrl+C to stop."
            )
        )

        try:
            while True:
                try:
                    sync_current_week_tickets()
                    self.stdout.write(
                        self.style.SUCCESS("Sync complete, sleeping...")
                    )
                except Exception:
                    logger.exception("Error during sync")
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nScheduler stopped."))
