"""
Management command to periodically sync ServiceDesk tickets.

Usage:
    python manage.py run_scheduler

Runs a simple loop that syncs ticket counts every SERVICEDESK_SYNC_INTERVAL
seconds (default: 300). The dashboard sync button works independently.

Each cycle also updates the ticket mirror behind the statistics page:
a full sync on start-up and then once every FULL_MIRROR_SYNC_EVERY, an
incremental one (changed tickets only) in between.

The web container applies migrations when it starts; this container
does not. After a release the two can start in either order, so the
loop first waits until the database schema matches this code
(``wait_for_migrations``) instead of syncing into an old schema.
"""

import logging
import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.logbook.tasks import sync_current_week_tickets, sync_ticket_mirror

logger = logging.getLogger(__name__)

# How often the statistics mirror is rebuilt from scratch.
FULL_MIRROR_SYNC_EVERY = timedelta(hours=24)

# How often to re-check for unapplied migrations while waiting.
MIGRATION_POLL_SECONDS = 10


def pending_migrations() -> list[str]:
    """Migrations this code has that the database has not applied yet."""
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    return [f"{m.app_label}.{m.name}" for m, _backwards in executor.migration_plan(targets)]


def wait_for_migrations(sleep=time.sleep, poll: int = MIGRATION_POLL_SECONDS) -> None:
    """Block until the web container has migrated the database.

    Logs the pending migrations once a minute while waiting. Never runs
    ``migrate`` itself: two containers migrating at once is worse than a
    short wait.
    """
    waited = 0
    while True:
        pending = pending_migrations()
        if not pending:
            return
        if waited % 60 == 0:
            logger.warning(
                "Waiting for %d unapplied migration(s) before syncing: %s",
                len(pending), ", ".join(pending[:5]),
            )
        sleep(poll)
        waited += poll


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

        wait_for_migrations()

        # Monotonic time of the last successful full mirror sync; None
        # forces one on the first cycle.
        last_full_mirror: float | None = None

        try:
            while True:
                try:
                    sync_current_week_tickets()
                    self.stdout.write(
                        self.style.SUCCESS("Sync complete, sleeping...")
                    )
                except Exception:
                    logger.exception("Error during sync")

                # The mirror is separate, so a failure there never holds up
                # the week counts above (and vice versa).
                try:
                    full = (
                        last_full_mirror is None
                        or time.monotonic() - last_full_mirror
                        >= FULL_MIRROR_SYNC_EVERY.total_seconds()
                    )
                    synced = sync_ticket_mirror(full=full)
                    if full and synced is not None:
                        last_full_mirror = time.monotonic()
                except Exception:
                    logger.exception("Error during ticket mirror sync")

                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nScheduler stopped."))
