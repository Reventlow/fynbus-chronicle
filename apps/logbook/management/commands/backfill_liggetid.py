"""Reconstruct a past week's open-ticket age ("liggetid") breakdown.

The ServiceDesk sync only ever fills in the current week, so weeks that
closed before the breakdown existed have empty buckets and their reports
skip the liggetid section. This command rebuilds the breakdown for such a
week from ServiceDesk ticket history.

A ticket counts as open at instant T if it was created at or before T and
either is still open now, or was completed after T. Ages are measured at T
— not today — so the numbers match what the week actually looked like.

Usage:
    python manage.py backfill_liggetid 2026 34
    python manage.py backfill_liggetid 2026 34 --dry-run
    python manage.py backfill_liggetid --all-missing

Requires the ServiceDesk credentials, so run it where the sync scheduler
runs (the chronicle_sync_servicedesk container).
"""

from datetime import UTC

from django.core.management.base import BaseCommand, CommandError

from apps.logbook.models import WeekLog
from apps.logbook.services.servicedesk import ServiceDeskClient


class Command(BaseCommand):
    help = "Rebuild a past week's liggetid breakdown from ServiceDesk history"

    def add_arguments(self, parser) -> None:
        parser.add_argument("year", nargs="?", type=int, help="ISO year, e.g. 2026")
        parser.add_argument("week", nargs="?", type=int, help="ISO week number, 1-53")
        parser.add_argument(
            "--all-missing",
            action="store_true",
            help="Backfill every weeklog that has no breakdown yet",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the reconstructed numbers without saving",
        )
        parser.add_argument(
            "--adjust-total",
            action="store_true",
            help=(
                "Correct helpdesk_open to the reconstructed total when they "
                "disagree (tickets deleted since the snapshot). Without this "
                "the week is skipped so the mismatch stays visible."
            ),
        )

    def handle(self, *args, **options) -> None:
        client = ServiceDeskClient()
        if not client.base_url or not client.api_key:
            raise CommandError("ServiceDesk URL or API key not configured")

        if options["all_missing"]:
            weeklogs = [
                w
                for w in WeekLog.objects.order_by("-year", "-week_number")
                if not w.has_helpdesk_age_breakdown
            ]
            if not weeklogs:
                self.stdout.write("Every weeklog already has a breakdown.")
                return
        else:
            year, week = options["year"], options["week"]
            if year is None or week is None:
                raise CommandError("Give a year and week, or use --all-missing")
            try:
                weeklogs = [WeekLog.objects.get(year=year, week_number=week)]
            except WeekLog.DoesNotExist as exc:
                raise CommandError(f"No weeklog for {year} week {week}") from exc

        for weeklog in weeklogs:
            self._backfill(client, weeklog, options)

    def _backfill(self, client: ServiceDeskClient, weeklog: WeekLog, options: dict) -> None:
        """Reconstruct and (unless dry-run) save one week's breakdown."""
        # Reconstruct as of the moment the open-count snapshot was taken, so
        # the reconstructed total is comparable to the recorded one.
        snapshot_at = weeklog.updated_at or weeklog.created_at
        snapshot_ms = int(snapshot_at.timestamp() * 1000)

        created_times = client.fetch_open_created_times_at(snapshot_ms)
        if created_times is None:
            self.stderr.write(
                self.style.ERROR(f"{weeklog.week_label}: ServiceDesk query failed, skipping")
            )
            return

        buckets = client.bucket_by_age(created_times, snapshot_ms)
        total = sum(buckets.values())

        self.stdout.write(
            f"\n{weeklog.week_label} "
            f"(snapshot {snapshot_at.astimezone(UTC):%Y-%m-%d %H:%M} UTC)"
        )
        for field, label, *_ in WeekLog.HELPDESK_AGE_BUCKETS:
            self.stdout.write(f"  {label:<20} {buckets[field]:>4}")
        self.stdout.write(f"  {'SUM':<20} {total:>4}  (recorded open: {weeklog.helpdesk_open})")

        if total != weeklog.helpdesk_open and not options["adjust_total"]:
            self.stderr.write(
                self.style.WARNING(
                    f"  Skipped: reconstruction totals {total} but the week records "
                    f"{weeklog.helpdesk_open} open cases. Tickets deleted or merged since "
                    "the snapshot cannot be recovered — rerun with --adjust-total to "
                    "accept the reconstructed total."
                )
            )
            return

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("  Dry run, nothing saved."))
            return

        fields = [field for field, *_ in WeekLog.HELPDESK_AGE_BUCKETS]
        for field in fields:
            setattr(weeklog, field, buckets[field])
        weeklog.helpdesk_open = total
        weeklog.save(update_fields=["helpdesk_open", *fields, "updated_at"])
        self.stdout.write(self.style.SUCCESS("  Saved."))
