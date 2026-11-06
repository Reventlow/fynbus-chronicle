"""
Management command for the sync container's background jobs.

Usage:
    python manage.py run_scheduler

One loop, ticking every TICK_SECONDS, drives independent jobs. Each has its
own switch and schedule, and an error in one never stops the others:

* **ServiceDesk** (``SERVICEDESK_SYNC_ENABLED``): ticket counts every
  SERVICEDESK_SYNC_INTERVAL seconds (default: 300), plus the ticket mirror
  behind the statistics page: a full sync on start-up and then once every
  FULL_MIRROR_SYNC_EVERY, an incremental one (changed tickets only) in
  between. The dashboard sync button works independently.
* **Planner** (``PLANNER_SYNC_ENABLED``, see apps/planner/sync.py): hands
  over sign-ins and answers "Synk nu" within a tick, and mirrors the plan
  every 2 minutes in working hours, every 15 minutes otherwise.

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
from apps.planner.sync import PlannerJob

logger = logging.getLogger(__name__)

# How often the statistics mirror is rebuilt from scratch.
FULL_MIRROR_SYNC_EVERY = timedelta(hours=24)

# How often to re-check for unapplied migrations while waiting.
MIGRATION_POLL_SECONDS = 10

# How often the loop looks at its jobs. Short, so that a Planner sign-in or
# "Synk nu" is picked up within seconds; each job decides itself whether it
# is due.
TICK_SECONDS = 5


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


class ServiceDeskJob:
    """Ticket counts and the statistics mirror, as before 1.16.0."""

    name = "servicedesk"

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.next_run: float | None = None
        # Monotonic time of the last successful full mirror sync; None
        # forces one on the first cycle.
        self.last_full_mirror: float | None = None

    @staticmethod
    def enabled() -> bool:
        return bool(getattr(settings, "SERVICEDESK_SYNC_ENABLED", False))

    def tick(self) -> None:
        now = self.clock()
        if self.next_run is not None and now < self.next_run:
            return
        self.next_run = now + getattr(settings, "SERVICEDESK_SYNC_INTERVAL", 300)
        try:
            sync_current_week_tickets()
        except Exception:
            logger.exception("Error during sync")

        # The mirror is separate, so a failure there never holds up
        # the week counts above (and vice versa).
        try:
            full = (
                self.last_full_mirror is None
                or self.clock() - self.last_full_mirror >= FULL_MIRROR_SYNC_EVERY.total_seconds()
            )
            synced = sync_ticket_mirror(full=full)
            if full and synced is not None:
                self.last_full_mirror = self.clock()
        except Exception:
            logger.exception("Error during ticket mirror sync")


def enabled_jobs() -> list:
    return [job for job in (ServiceDeskJob(), PlannerJob()) if job.enabled()]


def tick_all(jobs) -> None:
    """One pass over the jobs; a failing job is logged and skipped."""
    for job in jobs:
        try:
            job.tick()
        except Exception:
            logger.exception("Error in %s job", job.name)


class Command(BaseCommand):
    """Run the sync container's jobs in one loop."""

    help = "Run ServiceDesk and Planner sync (loops forever, Ctrl+C to stop)"

    def handle(self, *args, **options) -> None:
        jobs = enabled_jobs()
        if not jobs:
            self.stdout.write(self.style.WARNING(
                "No sync job is enabled (SERVICEDESK_SYNC_ENABLED, PLANNER_SYNC_ENABLED)"))
            return

        self.stdout.write(self.style.SUCCESS(
            f"Starting sync loop for {', '.join(j.name for j in jobs)}. Press Ctrl+C to stop."))

        wait_for_migrations()

        try:
            while True:
                tick_all(jobs)
                time.sleep(TICK_SECONDS)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nScheduler stopped."))
