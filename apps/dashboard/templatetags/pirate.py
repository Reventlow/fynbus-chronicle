"""Template tags for the Pirate Day skin (19. sep. / 1. okt.).

Two helpers, mirroring the Star Wars setup:

* ``{% pirate_phrase default pirate %}`` — emits both phrasings as nested
  ``<span>``s; CSS picks the right one based on ``data-event="pirate"``.
* ``{% pirate_messages_json %}`` — returns the rotating-banner message
  list as a JSON literal (Alpine reads it directly from the attribute).
"""

import json

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def pirate_phrase(default: str, pirate: str = "") -> str:
    """Render the default phrase plus an optional pirate variant.

    Same shape as ``sw_phrase`` but with a single alternate (pirate sprog
    is the same in both light and dark mode — only the visuals differ).
    """
    return format_html(
        '<span class="pirate-phrase">'
        '<span class="pirate-default">{}</span>'
        '<span class="pirate-alt" aria-hidden="true">{}</span>'
        "</span>",
        default,
        pirate or default,
    )


# ~80 quippy banner messages mixing FynBus operations + pirate sprog +
# International Hack Day vibes. Mostly Danish, some English where the
# joke lives there. The first entry is the OG Talk Like a Pirate Day
# greeting — it gets shown roughly 1% of the time.
PIRATE_BANNER_MESSAGES: list[str] = [
    "Yarr! Må vinden være med dig, matros.",
    # Pirate sprog basics
    "Skib ohøj! Alle servere bemandet.",
    "Shiver me timbers — patch-tirsdag ramte os igen.",
    "Avast ye! Phishing-mail i posten.",
    "Aye aye, captain — ticket #1337 lukket.",
    "Yo-ho-ho og en flaske kaffe — natshift på helpdesk.",
    "Til søs! Backup-rederiet sejler kl. 02:00.",
    "Landlubber-brugere kan ikke finde shift-knappen igen.",
    "Walk the plank — den der commitede direkte til main.",
    # Server / infra som pirateri
    "Vores datacenter er nu officielt en skattekiste.",
    "Hyperdrive er erstattet med kanon-deck — kortere boot-tid.",
    "Storm i SAN-rummet: et drev over bord.",
    "Vagthavende kaptajn: VPN-tunnellen er stabil indtil videre.",
    "Karavellen MS Postgres satte ny rekord på krydstogtet.",
    "Skibsvragsbjærgning: gendan-job kørte uden tab.",
    "Backupskonnerten ”Restorationen” lagde til kaj kl. 03:14.",
    "Alle krudtkamre patched mod Order-66 angreb.",
    "Anker hejst, replikering startet mod sekundær-havn.",
    "Sø-monster (eller bare en proces der hænger) sløver bus 17.",
    # Hack Day / cyber-pirate references
    "Hack the Planet! 1. oktober — internationale piratkodere mødes.",
    "Capture the flag på FynBus’ CTF-server kl. 16:00.",
    "Zero-day fundet i kahytten — patches sejler i nat.",
    "Pen-test blev til ægte boarding aktion — IDS lo lidt.",
    "Skibsbrud-forensics: ”det var ikke isbjerget, det var ransomware.”",
    "Defcon-niveau orange — jeg gentager: orange.",
    "Rubber-ducky USB fundet i kantinen — beslaglagt.",
    "Reverse-engineered en gammel COBOL-skifter — fungerer stadig.",
    "Buffer overflow detekteret — root-skud ind i båden.",
    "Bug bounty udbetalt i guldmønter (eller dækadgang).",
    "RFC 1918 er pirat-territorium nu.",
    "Brute-force angreb afvist af MFA-papegøje.",
    # FynBus operations remixed pirate-style
    "Bus 42 sejler videre til Mos Espa — afgang fra perron 7.",
    "Klage: chaufføren krævede otte mønter for én tur.",
    "Skattejagt langs rute 191 — alle holdesteder markeret med X.",
    "Kortlægning af busterminalen — kompasset peger nu mod kantinen.",
    "Kaptajn Jensen overtager bus 28 — fuld fart mod Odense Havn.",
    "Plankegang-trapping installeret ved Pirat-Park-and-Ride.",
    "Storm i Storebæltsoverfarten — bus 33 til ankers.",
    "Papegøje observeret på passagersæde 14C — ikke billet-godkendt.",
    "Ny rute opdaget på et gammelt kort — ingen ved hvor den fører hen.",
    "Pluk-sokken (engelsk: pirate flag) hejst på rute 555.",
    "Bus 88 til Skagen: ”Rederiet siger nordover, kaptajn.”",
    "Tatovering-rabat ved bestilling af 30-dages periodekort.",
    "Lommepenge-pris: én skilling per zone (fortolkes liberalt).",
    "FynBus’ skattekort viser et stort X ved Tinghusvej.",
    "Kaperkaptajn rapporterer: konkurrenten kører for tæt på vor route.",
    "Krudtdamp i bremserne — værkstedet bandes nedenunder.",
    "Pirat-plebs i bussen synger igen — chaufføren bestiller sosk.",
    # IT-support / Helpdesk pirate edition
    "Have you tried turning the cannon off and on again?",
    "Force-restart hjalp 73 % af alle skibe denne uge.",
    "Kaptajnens password er ikke længere ”fluffy” — godt.",
    "Kompasset peger mod nord — eller mod nærmeste WiFi.",
    "Captcha kunne ikke skelne en papegøje fra en robot — opdateres.",
    "MFA via stemme-løsen: ”Ahoy!” fungerer 60 % af gangene.",
    "Login fejlede 3 gange — søulken på kontoret er sat i stokken.",
    "Anker-mærket på taskbar betyder ”SMB-share”.",
    "Disken er fyldt med rom-billeder igen.",
    "Aurebesh er erstattet med pirat-dialekt på kortene.",
    "Kortpåse fundet i serverrum — indeholder gamle SSH-nøgler.",
    "ARRRR: Authentication, Replication, RAID, Recovery, Repository.",
    # Sø-bureaukrati & compliance
    "Toldvæsenet kræver bilag for hver ROM-import.",
    "Søforklaring indleveret efter incident — afventer revision.",
    "GDPR for piratkort: ”Hvor er ROPA-registret begravet?”",
    "ISO/NIS2-audit anbefaler færre kanoner og flere dokumenter.",
    "Forsikringsselskabet vil ikke dække kraken-angreb.",
    "Kaptajn-eden ratificeret — alle overholder fra kl. 12:00 dag i dag.",
    "Risikovurdering: 3 kraken-angreb / kvartal; mitigering pågår.",
    "ISMS-styregruppen kræver mønstring kl. 09 hver mandag.",
    # Pirat-pop-kultur / random
    "Long John Silver vil have remote-adgang til kortrummet — afvist.",
    "Kaptajn Sparrow ringede ind syg igen — for tredje gang i denne uge.",
    "Davy Jones har bedt om mørkt tema: ”Endnu mørkere skal det være.”",
    "Black Pearl er den hurtigste server i flåden — uptime 99.9 %.",
    "Mr. Smee tog endnu en kop kaffe i pause-kahytten.",
    "Hook har sendt passwordreset-anmodning igen — 14. gang i dag.",
    "Skibskat fundet sovende på et af tastaturerne — keylogger uskadeliggjort.",
    "”Det er ikke en bug, det er en feature, savvy?” — Kaptajn Sparrow",
    "Krakenen i kælderen kræver tre ofre om måneden — rens jeres logs.",
    "Pegleg-Pete har sendt 47 tickets på en time — review someone?",
    "Piratrådet beslutter: rom er en del af lønpakken igen.",
    "Schooner-skipper indvilliger i at bruge Confluence — historisk.",
    "Treasure map blevet OCR’et til en JSON-fil — venter på review.",
    "Skibsspil-aften fredag: Hearts of Iron eller Sea of Thieves?",
    "Den flyvende hollænder rapporteret offline — har været det i 200 år.",
    "Papagøjen råbte ”push to prod!” — alle gik i panik.",
]


@register.simple_tag
def pirate_messages_json() -> str:
    """Emit the banner messages as a JSON literal for Alpine to consume."""
    return mark_safe(json.dumps(PIRATE_BANNER_MESSAGES, ensure_ascii=False))
