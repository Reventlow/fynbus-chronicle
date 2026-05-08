"""Backfill existing schedules to recur annually.

The three seeded schedules (Star Wars Day 2026, Talk Like a Pirate Day
2026, International Hack Day 2026) are all date-anchored holidays that
recur every year. Flip them to ``recurs_annually=True`` so they fire
again in 2027 without needing new rows.

Editor-curated schedules added later are intentionally left untouched
— if you've added a one-shot range manually, you didn't want it to
recur.
"""

from django.db import migrations


SEEDED_LABELS = {
    "Star Wars Day 2026",
    "Talk Like a Pirate Day 2026",
    "International Hack Day 2026",
}


def make_seeded_recurring(apps, schema_editor):
    ThemeSchedule = apps.get_model("themes", "ThemeSchedule")
    ThemeSchedule.objects.filter(label__in=SEEDED_LABELS).update(
        recurs_annually=True
    )


def revert(apps, schema_editor):
    ThemeSchedule = apps.get_model("themes", "ThemeSchedule")
    ThemeSchedule.objects.filter(label__in=SEEDED_LABELS).update(
        recurs_annually=False
    )


class Migration(migrations.Migration):

    dependencies = [("themes", "0006_add_recurs_annually")]

    operations = [
        migrations.RunPython(make_seeded_recurring, revert),
    ]
