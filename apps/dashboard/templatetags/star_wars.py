"""Template tags for the May 4th Star Wars Day skin.

Two helpers:

* ``{% sw_phrase default rebel sith %}`` — emits all three phrasings of a
  label as nested ``<span>``s; the existing CSS picks the right one based
  on ``data-event`` + ``.dark``.
* ``{% sw_messages_json %}`` — returns the rotating-banner message list
  as a JSON literal (Alpine reads it directly from the attribute).
"""

import json

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def sw_phrase(default: str, rebel: str = "", sith: str = "") -> str:
    """Render the default phrase plus optional rebel/sith variants."""
    return format_html(
        '<span class="sw-phrase">'
        '<span class="sw-default">{}</span>'
        '<span class="sw-rebel" aria-hidden="true">{}</span>'
        '<span class="sw-sith" aria-hidden="true">{}</span>'
        "</span>",
        default,
        rebel or default,
        sith or default,
    )


# 100 quippy banner messages mixing FynBus operations + Star Wars universe.
# Mostly Danish, some English where the joke lives there. The first entry
# is the OG May the 4th greeting — it gets shown roughly 1% of the time.
SW_BANNER_MESSAGES: list[str] = [
    "Må Kraften være med dig. May the 4th be with you.",
    # Server / infra
    "Servere på Alderaan rapporteres som offline.",
    "Backup-job 04 fejlede — Death Star firewall blokerede igen.",
    "Cloud-tjenesten på Cloud City er fly-paused; Lando kontaktes.",
    "”Disse er ikke de servere du leder efter” — TOL-SW-02",
    "R2-D2 har patchet alle servere uden change-request.",
    "ManageEngine integrationen kører på Naboo nu — bedre latenstid.",
    "Kessel-runden under 12 parsec — imponerende uptime.",
    "DDoS fra en gruppe sandfolk; IDS opgraderes.",
    "Firewall opdateret med Mandalorian-regelsæt: ingen passerer uden bevis.",
    "Hyperdrive i server-rummet skal serviceres — Han Solo tilkaldt.",
    "Carbonite-arkivet kører igen efter 23 år i frostlager.",
    "Holocron-database synkroniseres hver 30. minut.",
    "Yavin IV-backup ligger i et fugtigt jungle-datacenter — overvejer flytning.",
    "Tatooine-noden har for høj temperatur — kølning bestilt.",
    "Endor-noden er nede; Ewokerne har frakoblet kablet igen.",
    # Software / apps
    "Wookieer anmoder om fuld adgang til Docunote.",
    "C-3PO har sendt 6.000.000 mails — har vi spamfilter?",
    "R2-D2 vil have aktindsigt på bodycam-optagelser efter kontrolafgift.",
    "Jar Jar Binks har tilføjet 47 priorities til ugelogen — review nogen?",
    "Yoda anmoder om mørkt tema: ”Mørkere skal det være.”",
    "Darth Vader bad om Excel-makroer aktiveret. Afvist.",
    "Jedi-rådet vil have Teams-integration på lyssværd.",
    "SDP-ticket #4242 lukket: ”Force-genstart løste det.”",
    "Aurebesh-dokumentation efterspurgt af Padawan-staben.",
    "Princess Leia sendte holo-message via Outlook — vedhæftning fejlede.",
    "Stormtroopers spørger om sigte-kalibrering på Helpdesk-køen.",
    "Imperial credits accepteres ikke længere i intranettet.",
    "Sith-protokol 66 detekteret af EDR — alle Jedi sat i karantæne.",
    "Boba Fett vil have privacy mode: ”Ingen kan se mig komme.”",
    "Han Solo-modus aktiveret: skyd først, dokumentér bagefter.",
    # FynBus operations
    "FynBus kom kun på andenpladsen i Boonta Eve Podrace.",
    "Passagerer på Tatooine-ruten siger det er alt for støvet.",
    "Hoth-ruten lukket — busserne fryser inde i hangaren.",
    "Endor-skoven fik ny holdeplads, men busserne klemmes mellem træerne.",
    "Bespin-ruten flyver over skyerne nu — 12 % hurtigere ankomst.",
    "Naboo-passagerer klager over ekstra gungans i bus 47.",
    "Coruscant-ruten har 14 niveauer af trafikprop — normal aften.",
    "Mos Eisley-stoppestedet anmoder om mere belysning — for mange skumle gæster.",
    "Dagobah-ruten aflyst — for sumpet for chaufførerne.",
    "R5-D4 ringede ind syg på første arbejdsdag.",
    "Klage: bussen kørte for hurtigt gennem Geonosis-arenaen.",
    "Imperial fragt-ekspres mister markedsandele til Outer Rim Transport.",
    "Wookiee-bussen har problemer med højdefri-grænsen.",
    "Gungan-passagerer klager: bus 12 har for få sub-aquatic ruter.",
    "Princess Leia bestilte to Senats-busser fredag — godkendt.",
    "Snowspeeder-bus afgang kl 06:30 — husk varme bukser.",
    "Aurra Sing klager over billet-appen: ”for komplekst med Aurebesh”.",
    "Mos Espa-ruten genåbnet efter sandstorm — 3 dages forsinkelse.",
    "Tarkin afslog ny rute til Kashyyyk: ”Wookieer ikke imperial-godkendt.”",
    "Ewok-børnene klager over bussens højde — pedaler for langt væk.",
    "Cantina-passager nægtede at betale: ”droids er ikke tilladt”.",
    "Ny Bespin-rute annonceret af Lando: ”kommer aldrig til at ændres.”",
    "Mandalorian klagede: ”I waited two parsecs at this stop.”",
    "Jedi-master Yoda kom for sent: ”Forsinket, jeg er.”",
    "Bus 28 til Anakin: ”Du skal have Senatets tilladelse for at parkere her.”",
    "Chauffør sendt til Mos Espa — efter Watto’s veksel-kurs er der knap råd til kaffe.",
    "Sand i alle bremser efter Tatooine-tur — værkstedet bandes i baggrunden.",
    # Sith / Imperial bureaucracy
    "Imperial finance kræver bilag for every Death Star-projekt.",
    "ITAR-godkendt Sith-protokol mangler 3 Force-formularer.",
    "Vader anmodede om compliance-rapport — Krennic gør det aldrig færdig.",
    "Tarkin fakturerede en hel planet — bogføring afviste.",
    "Imperial GDPR-ansøgning indsendt — afventer Sith-rådet.",
    "Stormtrooper-uddannelse: kun 13 % målcertificering opnået.",
    "Inkvisitor-onboarding udsat — HR mangler dokumentation.",
    "Empire skiftede IT-leverandør fra Kuat til Sienar Fleet — bedre SLA.",
    "Vader sendte HR-klage: ”min underordnede mangler ambition.”",
    "Carbonite-kompensation forlænget med 23 år — overenskomst ratificeret.",
    "Death Star QA-team identificerede 1 design-fejl. Kasseret.",
    "Sith Code Review approved — Anakin’s PR mergede ind i main.",
    "Krennic har lavet PowerPoint på 800 slides — er det for langt?",
    "Palpatine sendte all-hands: ”Senate dissolved” på agendaen.",
    "Empire bookede 14 mødelokaler til ”strategi” — ingen tjekkede ud.",
    # Tech / IT support
    "Have you tried turning Endor off and on again?",
    "Force-restart løste 73 % af alle tickets denne uge.",
    "Ctrl+Alt+Del skyder gennem en hyperdrive-cooldown.",
    "Password policy: min. 12 tegn, ingen ”Vader1234”.",
    "Multifaktor-godkendelse via Force-vision godkendt af IT-sikkerhed.",
    "Jedi-mind-trick virker stadig på Helpdesk niveau 1.",
    "Servere skal patches inden Order 66 — Endor-noden er sårbar.",
    "WLAN-signalet i karbonite-fryseren er lavt — overrasker ingen.",
    "Ny VPN kaldet ”Hyperspace” — 0,5 ms til galaksens midte.",
    "Bug i Death Star OS: ventilatoren tager én proton-torpedo.",
    "Yoda har skiftet til Linux: ”Apt install jedi-tools.”",
    "Lyssværd-emoji mangler i Slack — opgraderingen kommer.",
    "Force-push til main blokeret — kræver kode-review fra Master.",
    "Holographic call droppede — Cloud City-noden er ustabil.",
    "Stormtrooper-IT klagede: ”Mit visir kan ikke se 4K skærme.”",
    # Random absurd
    "Chewbacca sendte en Slack-kommentar — Google Translate kan ikke følge med.",
    "Ewok-CEO på vej til julefrokost — vagter alarmeret.",
    "Greedo skød først — pull request afvist.",
    "C-3PO har skiftet pronouns til ”they/them”; Anakin er ikke informeret.",
    "Han Solo bookede møde-rum i 6 år — der er stadig nogen i lokalet.",
    "Wookiee-CFO sendte kvartalsrapport: ”RAAARGGGGHHHH” (uændret YoY).",
    "Bossk installerede malware — har ikke read-only-adgang.",
    "Lando ringer hver 3. minut med deals: ”Ny aftale!”",
    "R2-D2 lavede en hjemmeside med .biz-domain — IT-sikkerhed kigger.",
    "Jabba kørte all-hands meeting — slæbt 4 timer over tid.",
    "Mace Windu vil ikke være IT-chef: ”Den her parti er forkert.”",
    "Senator Padmé bemærkede at IT-budgettet skal ratificeres.",
    "Obi-Wan sendte ticket: ”Fra et bestemt synspunkt fungerer det.”",
    "Anakin: ”Jeg kan godt lide sand. Det er ikke fint, det er groft og overalt.”",
    "Maul har sendt 3 ophidsede emails — han er fortsat aggressiv.",
    "Admiral Ackbar advarede om phishing: ”It’s a trap!”",
    "Salacious B. Crumb griner stadig hånligt af alle deploys.",
    "Porg fløj ind i serverrummet — alle pakker er nu rejected.",
]


@register.simple_tag
def sw_messages_json() -> str:
    """Emit the banner messages as a JSON literal for Alpine to consume."""
    return mark_safe(json.dumps(SW_BANNER_MESSAGES, ensure_ascii=False))
