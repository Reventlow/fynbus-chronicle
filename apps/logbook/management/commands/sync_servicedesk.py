"""
Management command to manually sync ServiceDesk ticket counts.

Usage:
    python manage.py sync_servicedesk          # Sync current week
    python manage.py sync_servicedesk --all    # Sync all existing weeks
"""

from django.core.management.base import BaseCommand

from apps.logbook.models import WeekLog
from apps.logbook.services.servicedesk import ServiceDeskClient


class Command(BaseCommand):
    """Manually sync ticket counts from ServiceDesk Plus."""

    help = "Sync helpdesk ticket counts from ServiceDesk Plus"

    def add_arguments(self, parser) -> None:
        """Add command arguments."""
        parser.add_argument(
            "--all",
            action="store_true",
            help="Sync all existing WeekLogs, not just current week",
        )

    def handle(self, *args, **options) -> None:
        """Execute the sync."""
        client = ServiceDeskClient()

        if not client.enabled:
            self.stdout.write(
                self.style.ERROR(
                    "ServiceDesk sync is disabled. "
                    "Set SERVICEDESK_SYNC_ENABLED=True in .env"
                )
            )
            return

        if not client.api_key:
            self.stdout.write(
                self.style.ERROR(
                    "ServiceDesk API key not configured. "
                    "Set SERVICEDESK_API_KEY in .env"
                )
            )
            return

        if options["all"]:
            weeklogs = WeekLog.objects.all()
            self.stdout.write(f"Syncing {weeklogs.count()} weeks...")
        else:
            weeklog = WeekLog.get_or_create_current_week()
            weeklogs = [weeklog]
            self.stdout.write(f"Syncing current week: {weeklog.week_label}")

        # Get current week info to determine if we should update open count
        current_weeklog = WeekLog.get_or_create_current_week()
        current_week_key = (current_weeklog.year, current_weeklog.week_number)

        for weeklog in weeklogs:
            stats = client.get_week_stats(weeklog.year, weeklog.week_number)
            weeklog.helpdesk_new = stats["created"]
            weeklog.helpdesk_closed = stats["closed"]

            # Only update open count for current week (historical data not available)
            is_current = (weeklog.year, weeklog.week_number) == current_week_key
            if is_current:
                weeklog.helpdesk_open = stats["open"]
                weeklog.save(update_fields=["helpdesk_new", "helpdesk_closed", "helpdesk_open", "updated_at"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {weeklog.week_label}: new={stats['created']}, "
                        f"closed={stats['closed']}, open={stats['open']}"
                    )
                )
            else:
                weeklog.save(update_fields=["helpdesk_new", "helpdesk_closed", "updated_at"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {weeklog.week_label}: new={stats['created']}, "
                        f"closed={stats['closed']}"
                    )
                )

        self.stdout.write(self.style.SUCCESS("Sync complete!"))
