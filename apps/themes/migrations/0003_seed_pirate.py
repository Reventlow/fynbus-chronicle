"""Seed the Pirate theme + its two schedules.

Activates on:
  * 19. september — Talk Like a Pirate Day (international).
  * 1. oktober — International Hack Day (FynBus reading: pirates ≈ hackers).

FR #2: https://chronicle.fynbus.net:8443/feedback/2/
"""

from datetime import date

from django.db import migrations


PIRATE_DESCRIPTION = (
    "Editorial overlay for Talk Like a Pirate Day (19. sep.) and Hack Day "
    "(1. okt.). Sea-chart parchment in light mode with rum-bottle teal "
    "accent; stormy-night navy in dark mode with brass-gold. Sticky banner "
    "with rotating pirate quips, anchor / skull brand-glyph swap, faint "
    "compass-rose page background, and a footer Easter egg."
)


def seed_pirate(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    ThemeSchedule = apps.get_model("themes", "ThemeSchedule")

    theme, _ = Theme.objects.get_or_create(
        slug="pirate",
        defaults={
            "name": "Pirate Day",
            "description": PIRATE_DESCRIPTION,
            "is_active": True,
            "user_selectable": True,
        },
    )
    ThemeSchedule.objects.get_or_create(
        theme=theme,
        start_date=date(2026, 9, 19),
        end_date=date(2026, 9, 19),
        defaults={"label": "Talk Like a Pirate Day 2026"},
    )
    ThemeSchedule.objects.get_or_create(
        theme=theme,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 1),
        defaults={"label": "International Hack Day 2026"},
    )


def unseed(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    Theme.objects.filter(slug="pirate").delete()


class Migration(migrations.Migration):

    dependencies = [("themes", "0002_seed_star_wars")]

    operations = [
        migrations.RunPython(seed_pirate, unseed),
    ]
