"""Seed the World Alzheimer's Day theme + schedule + banner messages.

Theme: Verdens Alzheimerdag, 21 September (marked since 1994; September is
World Alzheimer's Month). Unlike the other day-themes this one is not a
costume: purple is the international awareness colour, the forget-me-not
(forglemmigej — Alzheimerforeningen's symbol) is the glyph, and the banner
carries facts and pointers rather than quips. No phrase swaps, no themed
greetings — the site stays itself, dressed in purple for the day.

Schedule (annual): 21. september.
"""

from datetime import date

from django.db import migrations

DESCRIPTION = (
    "Verdens Alzheimerdag, 21. september. Lilla accent — sagens "
    "internationale farve — og forglemmigejen som mærke. Banneret "
    "roterer korte fakta og henvisninger (Alzheimerforeningen, "
    "Demenslinien) i stedet for vittigheder; ingen temaformuleringer "
    "andre steder på siden."
)

# Banner messages — factual, calm, Danish. Sources: Alzheimer's Disease
# International (the day, since 1994), Nationalt Videnscenter for Demens
# and Alzheimerforeningen (Danish prevalence, Demenslinien), WHO (share of
# dementia caused by Alzheimer's, risk factors).
MESSAGES = [
    "21. september er Verdens Alzheimerdag — markeret hvert år siden 1994.",
    "Forglemmigejen er symbolet: en lille blomst for dem, der glemmer, og dem, der husker for dem.",
    "Omkring 90.000 mennesker i Danmark lever med demens — og flere hundrede tusinde er pårørende.",
    "Alzheimers sygdom er den hyppigste årsag til demens — omkring to ud af tre tilfælde.",
    "Bær lilla i dag. Det er sagens farve verden over.",
    "Tal om det. Åbenhed gør demens lettere at leve med — for både den ramte og familien.",
    "Mød mennesket, ikke sygdommen: tal roligt, giv tid, og lad være med at rette.",
    "Hjernen holder af det samme som hjertet: bevægelse, søvn, fællesskab — og pas på hørelse og blodtryk.",
    "Har du brug for at tale med nogen? Demenslinien: 58 50 58 50 — Alzheimerforeningens rådgivning.",
    "Læs mere hos Alzheimerforeningen på alzheimer.dk.",
]


def seed_alzheimer(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    ThemeSchedule = apps.get_model("themes", "ThemeSchedule")
    ThemeBannerMessage = apps.get_model("themes", "ThemeBannerMessage")

    theme, _ = Theme.objects.get_or_create(
        slug="alzheimer",
        defaults={
            "name": "Alzheimerdag",  # short: it sits on a picker button
            "description": DESCRIPTION,
            "is_active": True,
            "user_selectable": True,
        },
    )

    ThemeSchedule.objects.get_or_create(
        theme=theme,
        start_date=date(2026, 9, 21),
        end_date=date(2026, 9, 21),
        defaults={"label": "Verdens Alzheimerdag", "recurs_annually": True},
    )

    # Skip if messages already exist, so admin edits survive a re-run.
    if not ThemeBannerMessage.objects.filter(theme=theme).exists():
        ThemeBannerMessage.objects.bulk_create(
            [ThemeBannerMessage(theme=theme, text=text, order=i) for i, text in enumerate(MESSAGES)]
        )


def unseed(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    Theme.objects.filter(slug="alzheimer").delete()


class Migration(migrations.Migration):

    dependencies = [("themes", "0008_seed_star_trek")]

    operations = [
        migrations.RunPython(seed_alzheimer, unseed),
    ]
