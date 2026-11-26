"""Seed the Christmas theme ("Jul") + schedule + banner messages.

Theme: Jul. A winter palette: nisse red on frost blue with spruce-green ink
in light mode, warm red on a midnight-blue winter night in dark mode, and a
slow, faint snowfall behind the page. Besides the usual banner it runs the
"julestue" scenes (static/js/christmas-parade.js): now and then a nisse
walks in to spread some cheer (and sometimes to tease: tugging a card's
corner, hanging a tiny nisse hat on a heading), children have a snowball
fight along the bottom, a Lucia procession walks by (rare, but guaranteed
once on 13 December), a reindeer peeks up, a nisse brings risalamande with
the marzipan pig in tow, a woven julehjerte floats down, and the sleigh
crosses the sky. On the Kontrolpanel a kalenderlys stands right above the
rådighedsvagt card and burns down through the day (apps/themes/candle.py).

Asked for in forslag #21 ("Jule tema"), 2026.

Schedule (annual): 1.–26. december (all of Advent through 2. juledag).
"""

from datetime import date

from django.db import migrations

DESCRIPTION = (
    "Jul, 1.–26. december. Nisserødt på frostblåt (lys) og varm rød på "
    "vinternat (mørk), stille snefald bag siden, et banner med julehygge og "
    "IT-råd, og indimellem kommer en nisse forbi og spreder juleglæde — eller "
    "driller lidt. Børn i sneboldkamp, Luciaoptog (altid den 13.), et rensdyr "
    "der kigger frem, risalamande med mandelgave, et julehjerte og slæden. På "
    "kontrolpanelet står et kalenderlys over rådighedsvagten og brænder ned "
    "i løbet af dagen."
)

# Banner messages — Danish, warm and playful; several carry a real security
# nudge under the nissehue, like the Halloween banner does.
MESSAGES = [
    "Glædelig december! Nissen har lovet ikke at røre firewall-reglerne. I år.",
    "En julegave fra ”pakkeservice” med et link? Det er ikke julemanden. Det er phishing.",
    "Lås skærmen, når du henter gløgg. Nisserne er meget nysgerrige.",
    "Ønskesedlen: flere logs, færre incidents og en printer, der bare virker.",
    "Mandlen må gerne gemmes i risalamanden. Passwords må ikke gemmes i Excel.",
    "Kalenderlyset brænder ned. Det gør certifikater også — tjek udløbsdatoerne.",
    "Juleaften er ikke en god dag at deploye på. Julefreden gælder også prod.",
    "Nissehuen holder hovedet varmt. MFA holder kontoen varm. Brug begge.",
    "Et gavekort-ønske fra ”direktøren” på SMS? Ring og spørg. Det er aldrig ham.",
    "Pebernødder i tastaturet? Vend det om og ryst forsigtigt. Ikke over serveren.",
    "Julehjerter flettes, VLAN'er segmenteres. Begge dele kræver tålmodighed.",
    "Sankta Lucia kommer d. 13. med lys i håret. Og med adgangskort, som alle andre.",
    "Rådighedsvagten holder også jul. Vær sød ved den, der har vagten.",
    "Ingen nisser i serverrummet uden følgeseddel. Heller ikke de små.",
    "Klap lige julefrokostbillederne sammen, før de lander i kanalen med alle.",
]


def seed_christmas(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    ThemeSchedule = apps.get_model("themes", "ThemeSchedule")
    ThemeBannerMessage = apps.get_model("themes", "ThemeBannerMessage")

    theme, _ = Theme.objects.get_or_create(
        slug="christmas",
        defaults={
            "name": "Jul",
            "description": DESCRIPTION,
            "is_active": True,
            "user_selectable": True,
        },
    )

    ThemeSchedule.objects.get_or_create(
        theme=theme,
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 26),
        defaults={"label": "Jul", "recurs_annually": True},
    )

    # Skip if messages already exist, so admin edits survive a re-run.
    if not ThemeBannerMessage.objects.filter(theme=theme).exists():
        ThemeBannerMessage.objects.bulk_create(
            [ThemeBannerMessage(theme=theme, text=text, order=i) for i, text in enumerate(MESSAGES)]
        )


def unseed(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    Theme.objects.filter(slug="christmas").delete()


class Migration(migrations.Migration):

    dependencies = [("themes", "0010_seed_halloween")]

    operations = [
        migrations.RunPython(seed_christmas, unseed),
    ]
