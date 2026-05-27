"""Seed the Star Trek theme + schedules + banner messages.

Theme: Star Trek. Federation/Starfleet aesthetic in light mode (command
blue + Starfleet delta), Klingon Empire in dark mode (blood red + warrior
emblem).

Schedules (both annual):
  * 8. september — Star Trek Day (TOS premiere, 1966).
  * 5. april — First Contact Day (Zefram Cochrane's warp flight, 2063).

FR submitted from session 2026-05-08 (chronicle production API was down
when the FR was originally drafted; the in-app record is created via
MCP once the server is reachable again).
"""

from datetime import date

from django.db import migrations


DESCRIPTION = (
    "Editorial overlay for Star Trek anniversaries (8. sep. Star Trek Day, "
    "5. apr. First Contact Day). Light mode = Starfleet command blue with "
    "delta brand glyph; dark mode = Klingon blood-red with warrior emblem. "
    "Rotating banner with Federation, Klingon, Vulcan and Borg quips."
)


# Banner messages — frozen at migration time. Mix of Starfleet ops,
# Klingon culture, Federation diplomacy, and FynBus operations remixed
# as starship missions. Mostly Danish, classic catchphrases in original
# English where the joke lives there.
MESSAGES = [
    "Live long and prosper. 🖖",
    # Starfleet operations
    "Bro, Spock til Maskinrum: ”Lavt på dilithium, bestil mere kaffe.”",
    "Federation-server kører på warp 6 — hold dig fast.",
    "Engage! Backup-jobbet er sat i gang.",
    "Make it so — change-request godkendt.",
    "Sæt phasers på stun — kun til UAT-miljøet, tak.",
    "Beam me up, Scotty — VPN reconnect requested.",
    "Transporter-buffer ramte 87% — slet gamle profiles.",
    "Holodeck-program ”Café 47” er booket til julefrokosten.",
    "Photon-torpedoer affyret mod ransomware-trussel — neutraliseret.",
    "Sensor-arrays detekterer phishing-bølge fra Romulansk neutral zone.",
    "Tactical: Borg-kube indenfor scanner-rækkevidde. Resistance is futile.",
    "Stardate 79023.5: alle bus-systemer nominelle.",
    "Red Alert! Stormvarsel ramt monitoring-dashboardet.",
    "Yellow Alert: SLA truer med at falde — eskalér til kommandanten.",
    "Captain’s log, supplemental: backup-strategien er gennemgået.",
    "Kommandør Spock: ”Logical. Den ticket lukker sig selv.”",
    "Picard: ”Tea. Earl Grey. Hot.” — kaffemaskinen står stadig på pause.",
    "”There are four lights!” — monitoring-dashboardet bekræfter 4 grønne.",
    "Lt. Worf: ”Sir, jeg har installeret patch 3.5.” / ”Glimrende, Worf.”",
    # Klingon culture
    "Qapla'! Sprintet er afsluttet succesfuldt.",
    "”Today is a good day to deploy.” — Klingon DevOps proverb.",
    "Klingon-warbird klagede over latency — Kahless ringer ind.",
    "bIjatlh 'e' yImev — slå op i Klingon dictionary før support.",
    "”It is a good day to push to prod.” — Worf, sandsynligvis.",
    "Klingonsk æres-kodeks: ingen Force-push uden duel.",
    "Targ-fest fredag — ikke alle kødretter er DNS-godkendt.",
    "Klingonsk operativsystem booter på 4 sekunder — anstændigt.",
    "Bat'leth-træning kl. 15 i kantinen — bring eget håndklæde.",
    "Krigerens vej: man pull-requester ikke, man kræver merge.",
    "Heghlu'meH QaQ jajvam — det er en god dag til at deploye.",
    "Klingonsk sikkerhedspolitik: passwords skal kunne råbes over et bat'leth.",
    "Empire-firewall blokerer alle pakker uden ærefuldt subject.",
    "Klingonsk QA: ”det fejlede, men ærefuldt.”",
    # FynBus operations remixed
    "Bus 47 til DS9 — afgang fra perron 7, husk space-billet.",
    "Klage: chaufføren talte Klingon over højtaleren igen.",
    "Rute Risa indstillet — for mange ferierende Starfleet-officerer.",
    "Bus 28 sat i karantæne efter mistanke om kontaminerede tribbles.",
    "Passager på Vulcan-ruten klager over manglende logik i køreplan.",
    "Captain Janeway booker bus til Voyager-konferencen — 7 års forsinkelse.",
    "Klingonsk passager nægtede at vise billet: ”æresløst.”",
    "Bus 11 melder: Borg-passager forsøger at assimilere ticketautomaten.",
    "Bus 88 til Wolf 359 aflyst pga. Borg-aktivitet i sektoren.",
    "Inter-stellar shuttle anbefaler 4-timers buffer ved Bajor-overfarten.",
    "Risa-rute fuld bookings — sommerferiens nye favorit.",
    "Ferengi-passager forsøgte at sælge holo-billetter — afvist.",
    # IT / Tech
    "Have you tried turning the warp core off and on again?",
    "Force-restart løste 73 % af alle anomalier denne uge.",
    "Subspace-relay forsinket — kabel-firmaet undskylder.",
    "Q dukkede op med et helpdesk-spørgsmål — kompleksitet uvis.",
    "Universal Translator nede — kommunikér i emojis.",
    "EMH (Emergency Medical Hologram) tilkaldt til kantinens kaffemaskine.",
    "Stardrive offline — kontakter Geordi La Forge igen.",
    "VISOR-update tilgængelig — Geordi melder klar til opgradering.",
    "Bridge-kommando authenticated via biometric retinal scan + MFA.",
    "Replicator nægter at lave Earl Grey igen — Picard er ikke tilfreds.",
    "Holodeck-safety nul — Moriarty gør oprør igen.",
    "Dilithium-niveau på 12% — bestil ny forsyning fra Cardassia.",
    # Diplomacy / compliance
    "Federation-charter kræver bilag for hver første-kontakt.",
    "Prime Directive: ingen merging uden review fra Admiral.",
    "GDPR på Vulcan: ”logisk og uomgængeligt.”",
    "NIS2-audit udvidet til at omfatte Borg-collective.",
    "Romulansk forhandling kører over budget — Senatet bekymret.",
    "Cardassian-traktat ratificeret — fred i sektor 001.",
    "Bajor-aftale revideret — adgangskontrol opdateret.",
    "Section 31 anbefaler at ignorere denne politik. Senatet uenig.",
    # Random
    "Tribble fundet i serverrummet — formerer sig hurtigere end logs.",
    "Data sender ticket: ”Min følelses-chip har en bug.”",
    "Wesley Crusher tilbyder at hjælpe med deploy — alle nervøse.",
    "Tasha Yar gav security-briefing — kort men effektiv.",
    "T’Pol kræver, at alle møder afsluttes inden for 0.4 stunder.",
    "Neelix laver kaffe — bemandingen flygter.",
    "Seven of Nine: ”Effektivitet er ikke til forhandling.”",
    "Riker: ”Nummer to, jeg har en bekymring om change-management.”",
    "Bashir og O’Brien spiller Alamo på storskærmen igen.",
    "Quark sælger sub-routines under bordet — Compliance opmærksom.",
    "Garak: ”Ingen af mine udtalelser kan citeres som sandhed.”",
    "Sisko bestilte gumbo til alle — moralen steget.",
    "Khan har sendt en LinkedIn-anmodning til kaptajnen igen.",
]


def seed_star_trek(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    ThemeSchedule = apps.get_model("themes", "ThemeSchedule")
    Msg = apps.get_model("themes", "ThemeBannerMessage")

    theme, _ = Theme.objects.get_or_create(
        slug="star-trek",
        defaults={
            "name": "Star Trek",
            "description": DESCRIPTION,
            "is_active": True,
            "user_selectable": True,
        },
    )

    # Two annual schedules — Star Trek Day + First Contact Day.
    ThemeSchedule.objects.get_or_create(
        theme=theme,
        start_date=date(2026, 9, 8),
        end_date=date(2026, 9, 8),
        defaults={"label": "Star Trek Day", "recurs_annually": True},
    )
    ThemeSchedule.objects.get_or_create(
        theme=theme,
        start_date=date(2026, 4, 5),
        end_date=date(2026, 4, 5),
        defaults={"label": "First Contact Day", "recurs_annually": True},
    )

    # Banner messages — skip if any already exist for this theme so
    # re-runs / hand-edits in admin survive.
    if not Msg.objects.filter(theme=theme).exists():
        Msg.objects.bulk_create(
            [Msg(theme=theme, text=text, order=i) for i, text in enumerate(MESSAGES)]
        )


def unseed(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    Theme.objects.filter(slug="star-trek").delete()


class Migration(migrations.Migration):

    dependencies = [("themes", "0007_backfill_recurring_schedules")]

    operations = [
        migrations.RunPython(seed_star_trek, unseed),
    ]
