"""Backfill one whole-week coverage segment per existing OnCallDuty row.

Without this, per-day/per-moment coverage queries and the split-week
export rendering would show gaps for every week assigned before 0.8.0.
Idempotent: weeks that already have segments are skipped. The reverse
is a no-op: deleting segments on rollback would also destroy real
handover records created after deploy, and a full rollback drops the
table via 0002 anyway.
"""

from datetime import date, datetime, time, timedelta

from django.db import migrations
from django.utils import timezone


def _week_span(year: int, week: int) -> tuple[datetime, datetime]:
    # Re-declared here rather than imported from apps.oncall.models so the
    # migration stays frozen even if the model helper changes later.
    monday = date.fromisocalendar(year, week, 1)
    tz = timezone.get_default_timezone()
    start = timezone.make_aware(datetime.combine(monday, time.min), tz)
    end = timezone.make_aware(datetime.combine(monday + timedelta(days=7), time.min), tz)
    return start, end


def backfill_segments(apps, schema_editor):
    OnCallDuty = apps.get_model("oncall", "OnCallDuty")
    OnCallSegment = apps.get_model("oncall", "OnCallSegment")

    covered = set(OnCallSegment.objects.values_list("year", "week_number"))
    segments = []
    for duty in OnCallDuty.objects.all():
        if (duty.year, duty.week_number) in covered:
            continue
        start, end = _week_span(duty.year, duty.week_number)
        segments.append(
            OnCallSegment(
                year=duty.year,
                week_number=duty.week_number,
                user_id=duty.user_id,
                start_at=start,
                end_at=end,
            )
        )
    OnCallSegment.objects.bulk_create(segments)


class Migration(migrations.Migration):
    dependencies = [
        ("oncall", "0002_oncallsegment_oncallchange"),
    ]

    operations = [
        migrations.RunPython(backfill_segments, migrations.RunPython.noop),
    ]
