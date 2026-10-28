"""Seed the Halloween theme + schedule + banner messages.

Theme: Halloween. Pumpkin orange in light mode, witching-hour purple with
a slime-green ink in dark mode; the jack-o'-lantern is the brand glyph
(a ghost in dark mode). Besides the usual banner it runs the "parade"
(static/js/halloween-parade.js): now and then a ghost, a jack-o'-lantern,
bats or a skeleton crosses the screen and does something silly. Asked
for by Gorm on 2026-10-28 ("ghosts, jack-o'-lanterns and skeletons
crossing the screen from time to time doing something stupid funny").

Schedule (annual): 24. oktober – 1. november (Halloween is the 31st;
the week around it, through Allehelgensdag).
"""

from datetime import date

from django.db import migrations

DESCRIPTION = (
    "Halloween, 24. oktober – 1. november. Græskar-orange accent (lys) og "
    "heksetime-lilla (mørk), græskarlygten som mærke, et banner med "
    "uhyggelige IT-råd — og en parade: indimellem krydser et spøgelse, et "
    "græskar, flagermus eller et skelet skærmen og laver noget fjollet."
)

# Banner messages — Danish, IT-flavoured, a little spooky. Some carry a
# real security tip under the costume, like the other themes' banners.
MESSAGES = [
    "Bøh! Har du prøvet at slukke og tænde igen?",
    "Det spøger ikke i serverrummet. Det er bare ventilationen. Tror vi.",
    "Phishing-mails er årets mest skræmmende kostume. Kig altid på afsenderen.",
    "Skeletter i skabet? Vi har dem i Active Directory: konti, ingen har brugt siden 2019.",
    "Gamle passwords går igen. Begrav dem ordentligt — brug Bitwarden.",
    "Trick or treat? Et USB-stik fra parkeringspladsen er altid trick.",
    "Den hovedløse rytter er bare en bruger uden MFA.",
    "Græskarlygten lyser orange. Det gør Zabbix også, når noget er galt.",
    "Spøgelsesbusser kører ikke. Tjek køreplanen.",
    "Printeren på gangen er ikke besat. Den er bare … printer.",
    "Zombie-processer: døde, men nægter at forlade proces-tabellen.",
    "Lås skærmen, når du går. Spøgelser læser med over skulderen.",
]


def seed_halloween(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    ThemeSchedule = apps.get_model("themes", "ThemeSchedule")
    ThemeBannerMessage = apps.get_model("themes", "ThemeBannerMessage")

    theme, _ = Theme.objects.get_or_create(
        slug="halloween",
        defaults={
            "name": "Halloween",
            "description": DESCRIPTION,
            "is_active": True,
            "user_selectable": True,
        },
    )

    ThemeSchedule.objects.get_or_create(
        theme=theme,
        start_date=date(2026, 10, 24),
        end_date=date(2026, 11, 1),
        defaults={"label": "Halloween", "recurs_annually": True},
    )

    # Skip if messages already exist, so admin edits survive a re-run.
    if not ThemeBannerMessage.objects.filter(theme=theme).exists():
        ThemeBannerMessage.objects.bulk_create(
            [ThemeBannerMessage(theme=theme, text=text, order=i) for i, text in enumerate(MESSAGES)]
        )


def unseed(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    Theme.objects.filter(slug="halloween").delete()


class Migration(migrations.Migration):

    dependencies = [("themes", "0009_seed_alzheimer")]

    operations = [
        migrations.RunPython(seed_halloween, unseed),
    ]
