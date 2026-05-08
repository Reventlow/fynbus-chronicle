"""Seed the rotating banner messages for the existing themes.

The lists are inlined here as a frozen historical record so the
migration is self-contained and works on fresh DBs even after the
templatetag-module constants are removed (next commit). Editors
maintain copy from this point forward in Django admin under each
Theme's banner-messages inline.
"""

from django.db import migrations


# Star Wars Day messages — frozen at migration time. Mostly Danish, mixing
# FynBus operations with Star Wars universe. First entry is the OG May 4th
# greeting and shows ~1% of the time (random pick).
STAR_WARS_MESSAGES = [
    "Må Kraften være med dig. May the 4th be with you.",
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


# Pirate Day messages — Talk Like a Pirate Day (19. sep) and Hack Day (1. okt).
# Mix of pirate sprog, FynBus operations remixed, and cyber-pirate Hack Day quips.
PIRATE_MESSAGES = [
    "Yarr! Må vinden være med dig, matros.",
    "Skib ohøj! Alle servere bemandet.",
    "Shiver me timbers — patch-tirsdag ramte os igen.",
    "Avast ye! Phishing-mail i posten.",
    "Aye aye, captain — ticket #1337 lukket.",
    "Yo-ho-ho og en flaske kaffe — natshift på helpdesk.",
    "Til søs! Backup-rederiet sejler kl. 02:00.",
    "Landlubber-brugere kan ikke finde shift-knappen igen.",
    "Walk the plank — den der commitede direkte til main.",
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
    "Toldvæsenet kræver bilag for hver ROM-import.",
    "Søforklaring indleveret efter incident — afventer revision.",
    "GDPR for piratkort: ”Hvor er ROPA-registret begravet?”",
    "ISO/NIS2-audit anbefaler færre kanoner og flere dokumenter.",
    "Forsikringsselskabet vil ikke dække kraken-angreb.",
    "Kaptajn-eden ratificeret — alle overholder fra kl. 12:00 dag i dag.",
    "Risikovurdering: 3 kraken-angreb / kvartal; mitigering pågår.",
    "ISMS-styregruppen kræver mønstring kl. 09 hver mandag.",
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


def seed_messages(apps, schema_editor):
    Theme = apps.get_model("themes", "Theme")
    Msg = apps.get_model("themes", "ThemeBannerMessage")

    for slug, messages in [
        ("star-wars", STAR_WARS_MESSAGES),
        ("pirate", PIRATE_MESSAGES),
    ]:
        theme = Theme.objects.filter(slug=slug).first()
        if not theme:
            continue
        # Skip if already populated — re-running this migration shouldn't
        # blow away hand-curated edits made in admin.
        if Msg.objects.filter(theme=theme).exists():
            continue
        Msg.objects.bulk_create(
            [Msg(theme=theme, text=text, order=i) for i, text in enumerate(messages)]
        )


def unseed(apps, schema_editor):
    Msg = apps.get_model("themes", "ThemeBannerMessage")
    Msg.objects.filter(theme__slug__in=["star-wars", "pirate"]).delete()


class Migration(migrations.Migration):

    dependencies = [("themes", "0004_themebannermessage")]

    operations = [
        migrations.RunPython(seed_messages, unseed),
    ]
