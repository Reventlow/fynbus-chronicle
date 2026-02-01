"""
Management command to import historical week logs.
"""

from datetime import datetime, timezone as dt_timezone

from django.core.management.base import BaseCommand

from apps.logbook.models import Incident, PriorityItem, WeekLog


class Command(BaseCommand):
    """Import historical week log data."""

    help = "Import historical week log data"

    def handle(self, *args, **options):
        """Import all historical week data."""

        self.import_week_46_2025()
        self.import_week_48_2025()
        self.import_week_51_2025()
        self.import_week_1_2026()
        self.import_week_2_2026()
        self.import_week_3_2026()
        self.import_week_4_2026()
        self.import_week_5_2026()

        self.stdout.write(self.style.SUCCESS("\nAll imports complete!"))

    def import_week_46_2025(self):
        """Week 46, 2025 (November 14, 2025)."""
        self.stdout.write("\n--- Week 46, 2025 ---")

        weeklog, created = WeekLog.objects.get_or_create(
            year=2025,
            week_number=46,
            defaults={
                "helpdesk_new": 6,
                "helpdesk_closed": 0,
                "helpdesk_open": 71,
                "summary": """Bemærkning: Sagsniveauet er svagt stigende fra sidste uge på 65 sager, men vi forventer bedre fremdrift når projekttid frigives de kommende uger.

Større nedbrud: Ingen

Evt:
Morten arbejder hjemmefra to dage om ugen de næste par uger for at skabe mere fokuseret projekttid. Det forventes at forbedre vores fremdrift på sager og backlog-opgaver.""",
            },
        )
        self._log_created(weeklog, created)

        priority_items = [
            ("Oplæring og videregivelse af information til Gorm", "For at sikre hurtig onboarding og kontinuitet i teamet", "high"),
            ("Dokumentation af FynBus' IT-infrastruktur", "Styrker driftssikkerhed og reducerer personafhængighed", "high"),
            ("Gennemgang af FynBus' mailopsætning og mailsikkerhed", "For at sikre compliance og sikre at vores løsning er sikker", "medium"),
            ("Klargøring af tablets til Odense Kommune", "Leverance klar til brug i driften", "medium"),
            ("Overblik og prioritering af backlog-opgaver", "Skaber klar plan for kommende uger", "medium"),
        ]
        self._create_priority_items(weeklog, priority_items)

    def import_week_48_2025(self):
        """Week 48, 2025 (November 28, 2025)."""
        self.stdout.write("\n--- Week 48, 2025 ---")

        weeklog, created = WeekLog.objects.get_or_create(
            year=2025,
            week_number=48,
            defaults={
                "helpdesk_new": 0,
                "helpdesk_closed": 0,
                "helpdesk_open": 71,
                "summary": """Bemærkning: Der er kommet lidt flere nye sager, end vi har nået at behandle denne uge.

Evt: Intet til evt i denne uge.""",
            },
        )
        self._log_created(weeklog, created)

        priority_items = [
            ("Kortlægning af status på FynBus' IT-struktur og fremsendelse til Jura", "Sikrer overblik i forhold til NIS2 og fremtidig governance", "high"),
            ("Oplæring af Gorm i FynBus' systemer og arbejdsgange", "Docunote og Intune - styrker kapaciteten i teamet og reducerer flaskehalse", "high"),
            ("Udvikling af chaufførsalg på tablets", "I samarbejde med Sydtrafik og ekstern partner - sikre de opfylder projektets krav", "high"),
            ("Opsætning af integrationer og server til Business Central Online", "Nødvendig at få overblik over implantations krav og at den kommende løsning lever op til de opgaver FynBus anvender i dag", "medium"),
            ("Udarbejdelse af generel beredskabsplan for IT", "Skaber bedre kriseberedskab og hurtigere reaktionstid ved nedbrud og klarer arbejdsgange", "medium"),
            ("Udarbejdelse af generelle arbejdsgange og supportkultur for Intern IT", "Ensretter service, minimerer fejl og øger gennemsigtighed", "medium"),
        ]
        self._create_priority_items(weeklog, priority_items)

        # Incident: NemID nedbrud
        incident, inc_created = Incident.objects.get_or_create(
            weeklog=weeklog,
            title="NemID-nedbrud",
            defaults={
                "incident_type": "system",
                "severity": "low",
                "description": "NemID-nedbrud 25/11 påvirkede enkelte tjenester hos leverandører, vi anvender. Det har kun ramt få brugere og vurderes derfor at have haft meget lav impact for FynBus.",
                "occurred_at": datetime(2025, 11, 25, 10, 0, tzinfo=dt_timezone.utc),
                "resolved": True,
                "resolution": "Ekstern hændelse hos leverandør. Meget lav impact for FynBus.",
            },
        )
        if inc_created:
            self.stdout.write(f"  Created incident: {incident.title}")

    def import_week_51_2025(self):
        """Week 51, 2025 (December 19, 2025)."""
        self.stdout.write("\n--- Week 51, 2025 ---")

        weeklog, created = WeekLog.objects.get_or_create(
            year=2025,
            week_number=51,
            defaults={
                "helpdesk_new": 0,
                "helpdesk_closed": 0,
                "helpdesk_open": 65,
                "summary": """En forbedring fra de sidste par uger.

Evt:
I forbindelse med jule- og nytårsperioden opsætter vi skilt på IT-døren samt besked på Intra om, at IT-support i hverdagene mellem jul og nytår håndteres telefonisk via Gorm.""",
            },
        )
        self._log_created(weeklog, created)

        priority_items = [
            ("Teknisk møde med Atea, Sydtrafik og Netcompany vedr. chaufførsalg", "Mandag", "high"),
            ("Test af mTLS i Chrome ifm. chaufførsalg", "Mandag", "high"),
            ("Møde med Rejsekort ang. chaufførsalg udfordringer", "Tirsdag - møde med Palle, Linda og Christine om mTLS og Chrome udfordringer", "high"),
            ("Vurdering af AI-tilbud sammen med AI-gruppen", "Tirsdag - komme med en anbefaling", "medium"),
            ("Klargøring og afsendelse af mail vedr. chaufførsalg til Rejsekort", "Onsdag - indeholder anbefalinger ift. identificerede udfordringer og mulige løsninger", "high"),
            ("Møde med CyberPilot om sikkerhedsmåling", "Onsdag - evt. ny undersøgelse i 2026", "medium"),
            ("Møde med Atea om fremtidig strategisk plan for IT i FynBus", "Torsdag", "medium"),
            ("Klargøring af udstyr og oprettelse af 6 nye medarbejdere", "Starter d. 5. januar", "medium"),
            ("Offboarding af Mathias", "Fredag", "medium"),
            ("Opsætning af Puzzel ifm. ferieafvikling", "Fredag - FynBus telefoni system", "medium"),
        ]
        self._create_priority_items(weeklog, priority_items)

    def import_week_1_2026(self):
        """Week 1, 2026 (January 2, 2026)."""
        self.stdout.write("\n--- Week 1, 2026 ---")

        weeklog, created = WeekLog.objects.get_or_create(
            year=2026,
            week_number=1,
            defaults={
                "helpdesk_new": 0,
                "helpdesk_closed": 0,
                "helpdesk_open": 64,
                "summary": """Noter: Intet at tilføje.""",
            },
        )
        self._log_created(weeklog, created)

        priority_items = [
            ("Dokumentation af nuværende servermiljø", "Arbejdet er fortsat i gang", "high"),
            ("Dokumentation af interne services i Docker Swarm", "", "high"),
            ("Udarbejdelse af udkast til udvidelse af vagtordning", "", "medium"),
            ("Udarbejdelse af guide om systemejerskab vs driftsadministration", "Beskriver forskellen mellem systemejerskab og driftsadministration", "medium"),
        ]
        self._create_priority_items(weeklog, priority_items)

        # Incident: Flextrafik routing
        incident, inc_created = Incident.objects.get_or_create(
            weeklog=weeklog,
            title="Flextrafik - manglende routing til NT",
            defaults={
                "incident_type": "system",
                "severity": "high",
                "description": "Der var ikke blevet bestilt opkald til routing til NT. Fejlen tog ca. 1½ dag at identificere, fejlfinde og implementere løsning på.",
                "occurred_at": datetime(2025, 12, 30, 10, 0, tzinfo=dt_timezone.utc),
                "resolved": True,
                "resolution": "Hændelsen gennemgås internt i IT i næste uge med henblik på læring og forebyggelse.",
            },
        )
        if inc_created:
            self.stdout.write(f"  Created incident: {incident.title}")

    def import_week_2_2026(self):
        """Week 2, 2026 (January 9, 2026)."""
        self.stdout.write("\n--- Week 2, 2026 ---")

        weeklog, created = WeekLog.objects.get_or_create(
            year=2026,
            week_number=2,
            defaults={
                "helpdesk_new": 0,
                "helpdesk_closed": 0,
                "helpdesk_open": 67,
                "summary": """Bemærkning: Ingen bemærkninger

Større nedbrud: Ingen

Eventuelt:
- Afklaring med Økonomi om udeståender ifm. gammelt økonomisystem og serverluk hos Unit IT. Vurdering af migrering af Always On VPN inden 31-01-2026 eller evt. forlængelse.
- Genoptagelse af dialog om serverrum pga. defekt køleanlæg. Leverandør anbefaler nyt anlæg, beslutning nødvendig.
- Fremadrettet afholdelse af ugentlige statusmøder med Dennis.""",
            },
        )
        self._log_created(weeklog, created)

        priority_items = [
            ("Gennemgang af hændelse omkring manglende bestilling af viderestilling i Puzzel", "Mellem jul og nytår", "high"),
            ("Onboarding af Peter", "Inkl. oprettelse af adgange og møder med systemgennemgang", "high"),
            ("Afklaring af rollefordeling og ansvar i afdelingen", "", "high"),
            ("Møde og gennemgang om udkast til udvidelse af vagtordning", "", "medium"),
            ("Forberedelse til månedsmøde", "", "medium"),
            ("Dokumentation af Puzzel telefonsystem", "", "medium"),
            ("Dokumentation af Moxso awareness-træning", "", "medium"),
            ("Dokumentation af servere", "", "medium"),
            ("Udarbejdelse af oversigt over systemer og komponenter", "", "medium"),
            ("Afklaring vedr. servere fra gammelt økonomisystem og VPN-løsning hos Unit IT", "", "medium"),
        ]
        self._create_priority_items(weeklog, priority_items)

    def import_week_3_2026(self):
        """Week 3, 2026 (January 16, 2026)."""
        self.stdout.write("\n--- Week 3, 2026 ---")

        weeklog, created = WeekLog.objects.get_or_create(
            year=2026,
            week_number=3,
            defaults={
                "helpdesk_new": 0,
                "helpdesk_closed": 0,
                "helpdesk_open": 73,
                "summary": """Bemærkning: Ingen bemærkninger

Noter: Intet at tilføje.""",
            },
        )
        self._log_created(weeklog, created)

        priority_items = [
            ("Dokumentation af nuværende systemoversigt", "Arbejdet er fortsat i gang", "high"),
            ("Arbejde på chaufførsalg interne services", "", "high"),
            ("Onboarding af Peter", "Inkl. Puzzel, Zabbix + domæne admin. bruger", "high"),
            ("Proact", "", "medium"),
            ("Forberedelse til månedesmøde", "", "medium"),
            ("Gennemgang af Hakon løsning", "", "medium"),
            ("Beslutning ang. VPN hos Unit-it", "Der fortsættes med drift af VPN løsning hos Unit-it (nedlukning udskydes)", "medium"),
            ("Beslutning ang. køl i serverrum TOL", "Der bestilles en ny enhed til erstatning af den som ikke virker", "medium"),
            ("Fokus på bedre brug af servicedesk", "Specielt til ikke kritiske opgaver", "medium"),
        ]
        self._create_priority_items(weeklog, priority_items)

        # Incident: FlexDanmark down
        incident, inc_created = Incident.objects.get_or_create(
            weeklog=weeklog,
            title="FlexDanmark nede",
            defaults={
                "incident_type": "system",
                "severity": "medium",
                "description": "Hele FlexDanmark var nede et kort stykke tirsdag d. 13.01.26.",
                "occurred_at": datetime(2026, 1, 13, 10, 0, tzinfo=dt_timezone.utc),
                "resolved": True,
                "resolution": "Vi fandt en mangel i opsætningen, så vi en anden gang hurtigere kan sætte en driftsbesked på telefonsystemet.",
            },
        )
        if inc_created:
            self.stdout.write(f"  Created incident: {incident.title}")

    def import_week_4_2026(self):
        """Week 4, 2026 (January 23, 2026)."""
        self.stdout.write("\n--- Week 4, 2026 ---")

        weeklog, created = WeekLog.objects.get_or_create(
            year=2026,
            week_number=4,
            defaults={
                "helpdesk_new": 0,
                "helpdesk_closed": 0,
                "helpdesk_open": 86,
                "summary": """Noter: Peter havde barn første og anden sygedag.""",
            },
        )
        self._log_created(weeklog, created)

        priority_items = [
            ("Fortsat onboarding af Gorm og Peter", "", "high"),
            ("Fortsat dokumentation af nuværende systemoversigt", "", "high"),
            ("IP whitelisting besluttet på styregruppemøde ift. chaufførsalg", "Afventer ændring", "high"),
            ("Udarbejdelse af de 4 risikoanalyser", "", "high"),
            ("Arbejde på AI politik og retningslinjer", "", "medium"),
            ("Dokumenteret løsning fra Hacon", "", "medium"),
            ("Møde med Atea om IT-miljø og gennemgang af netværksudstyr", "Onsdag", "medium"),
            ("Fejlsøgning på problemet med lukning af computere", "", "high"),
            ("Genetablering af server til gammelt Økonomisystem", "Ifm. anmodning fra Økonomi", "medium"),
            ("Opdatering og vedligeholdelse af servere", "", "medium"),
            ("Udarbejdelse af talefiler til busserne", "Skal afleveres til Plan i uge 5", "medium"),
            ("Afleveret løsning til bestilling af basiskort til kundecenteret", "", "medium"),
        ]
        self._create_priority_items(weeklog, priority_items)

        # Incident: Microsoft faulty update
        incident, inc_created = Incident.objects.get_or_create(
            weeklog=weeklog,
            title="Microsoft fejlbehæftet opdatering - computere kunne ikke slukke",
            defaults={
                "incident_type": "system",
                "severity": "high",
                "description": "Microsoft udsendte en fejlbehæftet opdatering, som forhindrede mange af vores computere i at slukke. Den midlertidige løsning og efterfølgende fejlrettelse virkede ikke.",
                "occurred_at": datetime(2026, 1, 20, 10, 0, tzinfo=dt_timezone.utc),
                "resolved": True,
                "resolution": "Vi har testet og besluttet at fremrykke opgraderingen til Windows 11, da den løser problemet.",
            },
        )
        if inc_created:
            self.stdout.write(f"  Created incident: {incident.title}")

    def import_week_5_2026(self):
        """Week 5, 2026 (January 30, 2026)."""
        self.stdout.write("\n--- Week 5, 2026 ---")

        weeklog, created = WeekLog.objects.get_or_create(
            year=2026,
            week_number=5,
            defaults={
                "helpdesk_new": 0,
                "helpdesk_closed": 0,
                "helpdesk_open": 86,
                "summary": """Noter: Morten havde barnets 1. og 2. sygedag i starten af ugen, Gorm holder fleksfri fredag.""",
            },
        )
        self._log_created(weeklog, created)

        priority_items = [
            ("Leverance af talefiler til Plan gennemført", "", "high"),
            ("Fortsat opgradering af Windows 11 23H2 til Windows 11 24H2", "", "high"),
            ("Adgang til rapporter og indkøb af licenser til Power BI Pro", "", "medium"),
            ("FTP-server adgang for Faaborg Midtfyn Kommune", "", "medium"),
            ("Superbrugermøde i DocuNote og gennemgang af skabeloner/fraser", "Med Marc Toft", "medium"),
            ("Møde og afklaring om VPN-tunnel til Hacon", "Ifm. infrastrukturopgradering", "medium"),
            ("Udarbejde beredskabsskabelon til Intern IT", "", "medium"),
            ("Udarbejde beredskabsskabelon til FynBus", "", "medium"),
            ("Ad-hoc møde med Ingrid, Laura og Cecilie om DocuNote roller", "", "low"),
            ("Gennemgang af Teams licenser og dialog med TDC", "Omkring besøg af Midtrafik", "medium"),
            ("Teknisk afklaring af kommende salgssted", "Leveringsdato rykket til 10/3", "medium"),
        ]
        self._create_priority_items(weeklog, priority_items)

        # Incident: Power outage during floor sanding
        incident, inc_created = Incident.objects.get_or_create(
            weeklog=weeklog,
            title="Strømafbrydelse under gulvslibning i kantinen",
            defaults={
                "incident_type": "system",
                "severity": "medium",
                "description": "Under gulvslibningen i kantinen slog nogle sikringer i eltavlen fra, hvilket medførte problemer i printerlokalet og i Mødelokale A.",
                "occurred_at": datetime(2026, 1, 28, 10, 0, tzinfo=dt_timezone.utc),
                "resolved": True,
                "resolution": "De fejl der var opstået deraf, blev udbedret inden bestyrelsesmødet.",
            },
        )
        if inc_created:
            self.stdout.write(f"  Created incident: {incident.title}")

    def _log_created(self, weeklog, created):
        """Log whether weeklog was created or already existed."""
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created WeekLog for week {weeklog.week_number}, {weeklog.year}"))
        else:
            self.stdout.write(f"WeekLog for week {weeklog.week_number}, {weeklog.year} already exists")

    def _create_priority_items(self, weeklog, items):
        """Create priority items for a weeklog."""
        for item_data in items:
            title, description, priority = item_data
            item, created = PriorityItem.objects.get_or_create(
                weeklog=weeklog,
                title=title,
                defaults={
                    "description": description,
                    "priority": priority,
                    "status": "completed",  # Historical items are completed
                },
            )
            if created:
                self.stdout.write(f"  Created: {title[:50]}...")
