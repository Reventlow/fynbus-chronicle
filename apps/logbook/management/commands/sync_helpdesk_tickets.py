"""
Management command to fill or refresh the helpdesk ticket mirror.

Usage:
    python manage.py sync_helpdesk_tickets          # changed tickets only
    python manage.py sync_helpdesk_tickets --full   # rebuild the whole mirror

The scheduler (run_scheduler) does this on its own; the command is for a
first fill or a manual check.
"""

from django.core.management.base import BaseCommand

from apps.logbook.models import HelpdeskTicket
from apps.logbook.tasks import sync_ticket_mirror


class Command(BaseCommand):
    """Sync the HelpdeskTicket mirror from ServiceDesk Plus."""

    help = "Sync the helpdesk ticket mirror used by the statistics page"

    def add_arguments(self, parser) -> None:
        """Add command arguments."""
        parser.add_argument(
            "--full",
            action="store_true",
            help="Rebuild the whole mirror instead of fetching changed tickets only",
        )

    def handle(self, *args, **options) -> None:
        """Run the sync and report the result."""
        synced = sync_ticket_mirror(full=options["full"])
        if synced is None:
            self.stdout.write(
                self.style.ERROR("Sync failed or ServiceDesk sync is disabled; see the log")
            )
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {synced} tickets; the mirror holds {HelpdeskTicket.objects.count()}"
            )
        )
