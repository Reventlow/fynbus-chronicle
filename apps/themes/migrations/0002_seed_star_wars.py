"""Seed the built-in Star Wars Day theme + its 2026-05-04 schedule.

Preserves the existing Star Wars Day functionality after the
IS_STAR_WARS_DAY → ACTIVE_THEME refactor: the date-based override that
used to be hard-coded in the context processor now lives in the DB.
"""

from datetime import date

from django.db import migrations


def seed_star_wars(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    ThemeSchedule = apps.get_model("themes", "ThemeSchedule")

    theme, _ = Theme.objects.get_or_create(
        slug="star-wars",
        defaults={
            "name": "Star Wars Day",
            "description": (
                "Editorial overlay for May 4th. Rebel orange in light mode, "
                "Sith red in dark, sticky banner with a rotating one-liner, "
                "starfield page background, Imperial/Rebel brand glyph swap, "
                "and a footer Easter egg."
            ),
            "is_active": True,
            "user_selectable": True,
        },
    )
    ThemeSchedule.objects.get_or_create(
        theme=theme,
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 4),
        defaults={"label": "Star Wars Day 2026"},
    )


def unseed(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    Theme.objects.filter(slug="star-wars").delete()


class Migration(migrations.Migration):

    dependencies = [("themes", "0001_initial")]

    operations = [
        migrations.RunPython(seed_star_wars, unseed),
    ]
