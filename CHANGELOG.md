# Changelog

All notable changes to FynBus Chronicle are documented here.

## 1.15.0 — 2026-10-30

### Added
- **Planlagte opgaver.** Ved siden af sårbarheder og hændelser kan en sag nu være en **planlagt opgave**: IT-arbejde, vi selv planlægger, fx en større opgradering eller en licensfornyelse. Opret den med **Ny planlagt opgave** på fanen *Sager*. Den har vurdering, løsning, vedhæftninger, links og kommentarer som de andre sager, kan have en **frist** (vist med rødt, når den er overskredet), og har status *Planlagt*, *I gang* eller *Udført*. Kontrolpanelets overskrift tæller de åbne planlagte opgaver, og ugelogens søjlediagram får en række for dem i uger, hvor der er nogen.
- **Ikoner for sagstyper.** På Kontrolpanelet, på fanen *Sager*, på sagens side og i ugeloggen har hver sag et ikon: et skjold for en sårbarhed, en advarselstrekant for en hændelse og en kalender med et flueben for en planlagt opgave.

## 1.14.0 — 2026-10-30

### Added
- **Flere monstre i Halloween-paraden.** En zombie slæber sig langsomt over skærmen og vil have kaffe. En anden er en *zombie-proces* med skiltet *kill -9 virker ikke*. En vampyr vil kun suge jeres båndbredde, går op i røg og flyver væk som flagermus. En kollega går ind, fuldmånen står op, og en varulv hyler over fredagsdeploy. Edderkopper firer sig ned fra toppen af skærmen i deres tråd, hænger og siger hej, og kravler op igen, nogle gange tre ad gangen.

## 1.13.0 — 2026-10-28

### Added
- **Halloween-tema, 24. oktober – 1. november** (hvert år). Græskar-orange i lyst tema og heksetime-lilla i mørkt, 🎃 som mærke (👻 i mørkt tema), et spindelvæv i hjørnet og et banner med uhyggelige IT-råd. Hilsenen på Kontrolpanelet bliver til *Bøh*.
- **Halloween-paraden:** et par gange i timen krydser nogen skærmen og laver noget fjollet. Et skelet taber hovedet og må løbe efter det, et andet skelet drikker kaffe, der løber lige ud gennem ribbenene, og et tredje moonwalker baglæns. Et spøgelse spørger efter wifi-koden, et andet kommer med *Ticket #666: Det spøger i printeren*. Et græskar ruller ind og bliver svimmelt, og tre flagermus flyver forbi, hvor den sidste først flyver den forkerte vej. Paraden kan ikke klikkes på og står aldrig i vejen. Den holder pause, når fanen ikke er synlig, og kører ikke, hvis styresystemet er sat til at begrænse animationer.

## 1.12.0 — 2026-10-28

### Changed
- **Sårbarheder hedder nu *Sårbarheder og hændelser*.** En hændelse er nu en **sag af typen Hændelse** med vurdering, løsning, vedhæftninger, links og kommentarer, ligesom en sårbarhed. Opret den med **Ny hændelse** på fanen *Sager*. En hændelse har status *Identificeret*, *Under behandling* eller *Færdigbehandlet*. Hver sag er mærket *Sårbarhed* eller *Hændelse* i lister, på Kontrolpanelet og i ugeloggen.
- **Hændelser i ugeloggen er stoppet.** De gamle står stadig som et skrivebeskyttet arkiv i deres uger og i de ugers eksport. Der kan ikke oprettes, rettes eller slettes nogen. API'ets `POST …/incidents/` (fx Chronicles MCP-værktøj) opretter nu en hændelses-sag og svarer i samme format som før.
- **Kontrolpanelet har ikke længere kortet *Hændelser*.** Linjen under overskriften tæller åbne hændelser og åbne sårbarheder.

### Added
- **Boksen *Vis i ugelogs-eksport*** på hvert afsnit af en sag: vurdering, løsning, vedhæftninger, links og kommentarer. Som standard kommer vurdering og løsning med. Kommentarer kommer kun med for den uge, de er skrevet i, og vedhæftninger kun med navn og TLP, aldrig som fil.
- **Søjlediagram i ugeloggen og dens eksport**: hændelser og sårbarheder, der var åbne ved ugens udgang, og dem, der blev færdigbehandlet i ugen.

## 1.11.1 — 2026-10-28

### Fixed
- Teksten øverst på CVE-listen bad om at *vælge Alle*, men *Alle* var kun et valg i Status-feltet, og det var ikke til at finde. Nu er det linket **vis alle CVE'er** (på Sager: **vis alle sager**). Det forsvinder, når alle allerede vises.

## 1.11.0 — 2026-10-27

### Added
- **En CVE uden sag får en tydelig boks *Ikke i en sag*** på sin side med to knapper: *Ny sag med denne CVE* og *Føj til eksisterende sag*. Alle CVE'er skal høre til en sag. Listen kan nu også vælge færdigbehandlede sager, ikke kun åbne. CVE'en får sagens status.
- I CVE-listen står *Ikke i en sag · læg den i en sag →* under en CVE uden sag. På Kontrolpanelet er overskriften *CVE'er uden sag* markeret. Begge fører direkte til boksen.

### Changed
- **Fanerne *CVE'er* og *Sager* siger nu, hvad tallet tæller**, fx *2 ikke færdigbehandlet · 9 i alt*. Det nøgne tal blev læst, som om der kun var registreret 2.

## 1.10.0 — 2026-10-27

### Changed
- **Kortet *Sårbarheder* på Kontrolpanelet er bygget op om sagerne.** Hver sag står med sine CVE'er nedenunder: id, emne og CVSS. Så kan man se, hvilke CVE'er der hører sammen, uden at åbne sagen. Hver CVE er et link.
  - Kortet viser de åbne sager og dem, der er færdigbehandlet de sidste 30 dage. Åbne sager står først.
  - Under sagerne står *CVE'er uden sag* fra de sidste 30 dage. En CVE i en sag vises kun under sin sag.
  - Overskriften tæller de åbne sager. Linjen over tæller de åbne CVE'er og dem, der er færdigbehandlet i perioden. Links fører til fanerne *Sager* og *CVE'er*.

## 1.9.0 — 2026-10-27

### Changed
- **"Løst" hedder nu "Færdigbehandlet"** under Sårbarheder: status, knapper, lister, Kontrolpanelet og ugeloggen (*Færdigbehandlet denne uge*), også i eksporten. En sikkerhedssag er sjældent endegyldigt løst. Vi kan vurdere og handle efter bedste viden og så lukke den. Ældre statusskift i tidslinjerne beholder deres oprindelige tekst. Hændelser i logbogen hedder stadig *Løst*.

### Added
- **Nyt udfald på sager: *Færdigbehandlet — risiko accepteret***, ved siden af *patchet* og *ikke berørt*. Det er til en sårbarhed, hvor vi bevidst vælger ikke at patche, fx fordi der ingen rettelse findes, eller fordi en anden foranstaltning dækker risikoen. Skriv begrundelsen i sagens *Vurdering* eller *Løsning / handling*. API'et tager `resolution: "risk_accepted"`.

## 1.8.0 — 2026-10-27

### Added
- **Redigér kommentarer i tidslinjen** på CVE'er og sager. Blyanten ved en kommentar åbner den til redigering direkte i tidslinjen. *Gem* gemmer, og *Annullér* fortryder.
  - Kun den, der har skrevet kommentaren, kan rette den. Statusskift kan ikke rettes. Tidslinjen er dokumentationen af, hvem der skrev hvad og hvornår.
  - En rettet kommentar viser *redigeret* med tidspunkt. Det oprindelige tidspunkt står uændret.

## 1.7.0 — 2026-10-27

### Added
- **ODT-dokumenter (.odt) kan vedhæftes** på CVE'er og sager, ligesom PDF'er og Outlook-mails, med titel, kilde og TLP. Det er fx til orienteringer, der kommer som et LibreOffice-dokument. En browser kan ikke vise et .odt, så et klik på det henter filen. Chronicle tjekker, at filen faktisk er et ODT-dokument, og ikke kun at navnet ender på .odt.

## 1.6.0 — 2026-10-26

### Added
- **Fanerne *CVE'er* og *Sager* øverst under Sårbarheder**, hver med antallet af åbne.
  - **Sager** viser hver sag med alle dens CVE'er nedenunder: id, emne, CVSS og status. Hver CVE er et link. En sag uden CVE'er viser kilde og reference.
  - **CVE'er** viser for en CVE i en sag linjen *↳ Sag #n · titel*, som fører til sagen.

### Changed
- Kortet *Åbne sager* over CVE-listen er fjernet. Sagerne har nu deres egen fane.

## 1.5.0 — 2026-10-26

### Added
- **Advarsler uden CVE-nummer, fx fra CFCS, kan dokumenteres som en sag uden CVE'er.** Sagen har nu felterne **Kilde** (fx CFCS), **Reference** (kildens eget nummer og dato) og **Kildelink**. Lad CVE-feltet stå tomt.
- **Sager står i ugeloggen.** Afsnittet *Sårbarheder* viser nu hver sag, der var åben i løbet af ugen, over CVE'erne, med status, kilde, reference og *Løst denne uge*. Det gælder også HTML- og PDF-eksporten. En sag uden CVE'er kommer dermed med i ugens dokumentation.
- **Åbne sager står på Kontrolpanelet** øverst i kortet *Sårbarheder*.
- **Søgning på Sager** finder titel, kilde, reference og CVE-id. Søgningen på CVE-listen finder også sagens reference.
- API'et `POST /api/v1/cve-cases/` tager `source` og `reference`, og begge felter er med i svaret.

### Changed
- Menupunktet **CVE'er** hedder nu **Sårbarheder**, fordi det også rummer advarsler uden CVE-nummer. Adresserne er de samme.

## 1.4.0 — 2026-10-26

### Added
- **Sager: flere CVE'er med samme løsning.** Når flere CVE'er har samme vurdering og samme løsning, kan de samles i en sag, så dokumentationen kun skrives én gang. Eksempler er fire kerne-CVE'er, der lukkes af samme kerneopdatering, eller Python- og Go-CVE'erne om den kompromitterede eMudhra-certifikatudsteder.
  - En sag har **titel**, **vurdering** og **løsning / handling** (Markdown virker) og har sine egne vedhæftninger med TLP, links og tidslinje, ligesom en CVE.
  - **Sagens status gælder alle dens CVE'er.** Knapperne er *Identificeret*, *Patcher*, *Løst — patchet* og *Løst — ikke berørt*. Hver CVE får skiftet i sin egen tidslinje.
  - En CVE kan kun være i én sag. På CVE'ens side står et link til sagen i stedet for statusknapperne. En fri CVE kan *føjes til en åben sag* eller starte en *ny sag*.
  - Opret en sag under **CVE'er → Sager → Ny sag** med CVE-id'erne adskilt af komma. Ukendte id'er oprettes med sagens titel.
  - Åbne sager står øverst på CVE-listen. CVE'er i en sag har mærket *Sag #n* i lister og ugeloggen. Søgning finder også sagens titel.
  - **API** til Harbinger: `GET`/`POST /api/v1/cve-cases/` og `GET /api/v1/cve-cases/<id>/`. Harbinger kan sende en hel sag på én gang og senere tilføje flere CVE'er til den. CVE'ers API-data viser nu, hvilken sag de er i.

## 1.3.2 — 2026-10-23

### Fixed
- **Links på en CVE er nu tydeligt klikbare.** Under *Links* står titlen som et link med ↗, og adressen under den kan også klikkes. Begge åbner i en ny fane, så CVE'en bliver stående.
- **Adresser i kommentarer bliver til links**, også når de skrives uden *https://* (fx *www.fortinet.com*), og de åbner i en ny fane.

## 1.3.1 — 2026-10-23

### Fixed
- **Ændringsloggen stod i forkert rækkefølge.** 1.3.0 var sorteret under 1.2.1, så Kontrolpanelet viste 1.2.1 som *Seneste ændring*. Nu står den nyeste version øverst igen.

## 1.3.0 — 2026-10-23

### Added
- **Outlook-mails (.msg) på CVE'er.** Under *Vedhæftninger* kan man nu også vedhæfte en mail, fx en advarsel fra FE-CSIRT, direkte fra Outlook.
  - **Klik på mailen** for at læse den: afsender, modtagere, dato, emne og teksten vises i samme visning som PDF'erne. Mailens egen HTML vises aldrig, kun teksten, så intet i mailen kan køre. *Hent* giver den oprindelige .msg-fil til Outlook.
  - **PDF'er i mailen pakkes ud** og lægges som egne vedhæftninger under mailen, så advisory'en kan åbnes med det samme. De får samme TLP som mailen.
  - **TLP findes automatisk:** vælger man ingen TLP, bruges markeringen fra mailens emne eller tekst (fx *TLP:AMBER*). Afsenderen bruges som kilde, hvis der ikke er angivet en.
  - Kun ægte Outlook-mails accepteres (tjekkes på indholdet), højst 25 MB. Sletter man mailen, beholdes de PDF'er, der blev pakket ud af den.

## 1.2.1 — 2026-10-22

### Changed
- **Sårbarheder er flyttet på kontrolpanelet.** Kortet med CVE'er fra de sidste 30 dage står nu under *Hændelser* i venstre kolonne, så sikkerhedshændelser og sårbarheder kan ses samlet. Højre kolonne viser rådighedsvagten og den aktuelle ugelog. Hændelseskortet fylder den resterende højde, så kolonnerne slutter i samme højde.

## 1.2.0 — 2026-10-22

### Added
- **PDF'er på CVE'er.** CVE'ens side har fået et kort, *Vedhæftninger*, hvor redaktører kan vedhæfte PDF'er, fx advisories fra FE-CSIRT (CSIRT@fe-ddis.dk).
  - Hver PDF får en **TLP-markering** (TLP:CLEAR, GREEN, AMBER, AMBER+STRICT eller RED), som vises med de officielle farver, så ingen kommer til at sende et AMBER-dokument videre ved en fejl. Titel og kilde er valgfri.
  - **Klik på en PDF** for at åbne den i en visning oven på siden, med TLP-mærket i toppen og knapper til *Åbn i ny fane*, *Hent* og *Luk*.
  - Kun ægte PDF'er accepteres (tjekkes på indholdet, ikke kun filnavnet), højst 25 MB. Filerne gemmes ved siden af databasen og vises kun for brugere, der er logget ind. Browseren må ikke gemme kopier.
  - Sletter man en PDF, slettes filen også fra serveren.

## 1.1.0 — 2026-10-22

### Added
- **Sårbarheder (CVE'er).** Et nyt punkt i sidemenuen samler de CVE'er, der rammer os.
  - **Listen** viser åbne CVE'er øverst og løste i 90 dage, med CVSS farvet efter alvorlighed, status og link til cvefeed.io. Søg på id eller emne, eller filtrér på status.
  - **CVE'ens side** har status-knapper (*Identificeret*, *Patcher*, *Løst*), links til advisories og sager og en tidslinje med kommentarer i Markdown. Hvert statusskift skrives i tidslinjen.
  - **Ny CVE** udleder alvorligheden af CVSS og udfylder cvefeed.io-linket. Formularen kan forudfyldes fra et link, og et id, der allerede findes, fører til den eksisterende CVE i stedet for en dublet.
  - **Kontrolpanelet** har fået et kort under *01 Nu* med CVE'er fra de sidste 30 dage og antallet af åbne og løste.
  - **Ugeloggen** viser af sig selv de CVE'er, der var åbne i løbet af ugen, og markerer dem, der blev løst. Afsnittet kommer også med i HTML- og PDF-eksporten.
  - **API** til Harbinger: `GET`/`POST /api/v1/cves/` og `GET /api/v1/cves/<cve-id>/`. Findes CVE'en allerede, tilføjes kun kommentaren.

## 1.0.5 — 2026-10-22

### Security
- **Kompromitterede eMudhra-rodcertifikater er ikke længere betroet.** Begge images bygges nu med den aktuelle `ca-certificates` fra Debian og kræver `certifi>=2026.10.19`, så *emSign ECC Root CA - G3* og *Comodo AAA Services root* er fjernet. Uden det kunne en angriber med en falsk certifikatkæde udgive sig for ServiceDesk eller andre tjenester, som Chronicle henter data fra.

## 1.0.4 — 2026-10-20

### Fixed
- **CI kører nu alle tests.** Byggeriet brugte `manage.py test`, som ikke finder de pytest-baserede tests, så en stor del af dem blev aldrig kørt. Nu køres `pytest`, og en fejlende test stopper udgivelsen, før der bygges images.
- **Synk-containeren venter på databasen.** Efter en udgivelse venter den, til web-containeren har kørt alle migreringer, i stedet for at synkronisere mod et gammelt skema.
- **Links mellem dokumenterne virker i Chronicle.** Et link som *DEPLOYMENT.md#rolling-back* åbner nu den rigtige side under Dokumentation.

### Changed
- `docker-compose.prod.yml` følger nu produktionens opsætning: de to rigtige images, env-filer og fælles datavolumen. Versionen vælges med `CHRONICLE_VERSION`.
- `pyproject.toml` læser versionen fra `version.txt`, så der kun er ét sted at opdatere den.
- Rester af den gamle opgavetidslinje på kontrolpanelet er fjernet.

## 1.0.3 — 2026-10-20

### Changed
- **Dokumentationen er opdateret til version 1.0.**
  - *Brugervejledningen* beskriver sidemenuen, søgning med Ctrl+K, indstillingerne under tandhjulet, det nye Kontrolpanel, opgavesøgning, Statistik med valgfri periode og delte links, Forslag, notifikationer, API-nøgler, billeder med Ctrl+V og Touch-Grass-Weekend. Det gamle Opgaver-afsnit er fjernet.
  - *README* og de tekniske vejledninger (*Setup*, *Development*, *Deployment*) følger, hvordan Chronicle bygges, udgives og kører i dag. *Development* har fået et afsnit om udgivelser.
  - *Opgaver* er markeret som det gamle opgavemodul.
- Overskrifter med æ, ø og å i dokumentationen kan nu linkes til, så indholdsfortegnelsen i brugervejledningen virker.

## 1.0.2 — 2026-10-20

### Changed
- **Overskriften på Kontrolpanelet opdaterer sig selv.** Antal åbne sager, *Live · synk kl …*, ugens hændelser og ugeloggen hentes igen hvert minut, ligesom kortene nedenunder. Efter *Prøv igen* opdateres den med det samme.

## 1.0.1 — 2026-10-19

### Fixed
- **"Prøv igen" og opdateringsknappen på Kontrolpanelet virker igen.** En manuel synk opdaterede kun ugens tal, ikke kopien af sagerne, som "Synk fejlede"/"forældet" læses fra — så siden så uændret ud efter klikket. Knappen kører nu hele synken, og fejler den, står det på kortet i stedet for at intet sker.

## 1.0.0 — 2026-10-17

🎉 **Chronicle 1.0.** Fra første commit den 1. februar 2026 til i dag: 254 commits, 126 udgivelser, 431 tests — og et værktøj, IT-afdelingen bruger hver uge.

### Hvad 1.0 lover
- **API'et under `/api/v1/`** og statistikkens JSON-skema (version 1) ændres kun bagudkompatibelt.
- **Opgraderinger kører af sig selv:** databasen migreres, når containeren starter; ingen manuelle trin.

### Det har vi bygget
- **Ugelogs** med prioriterede opgaver, der lever på tværs af uger (Markdown, billeder med Ctrl+V, fletning, genåbning, auto-luk efter 6 uger), hændelser, bemanding, mødereferat og klarmelding.
- **Eksport** af ugerapporten som PDF, HTML, Markdown og email via Microsoft Graph, med bekræftelse før afsendelse.
- **ServiceDesk-integration:** ugens helpdesk-tal, liggetid og en lokal kopi af alle sager med emne, kategori, tekniker og afdeling.
- **Kontrolpanel** med nøgletal, hændelser, åbne sager fordelt på tekniker, kategori og liggetid, de nyeste og ældste uløste sager med direkte link til ServiceDesk, og udviklingen over tid.
- **Statistik** over et valgfrit tidsrum, med eksport og delte links til Claude Motion.
- **Rådighedsvagt** med vagtkalender, delte uger, vagtskifte midt i ugen og historik.
- **Forslag** som udviklingstavle, **Rapporter** med slides og video, **notifikationer** og **API-nøgler** til MCP og scripts.
- **Temaer:** Star Wars, Pirate Day, Star Trek, Verdens Alzheimerdag, Read-only Friday og Touch-Grass-Weekend.
- **v3-designet:** sidemenu, nummererede afsnit, tynde kanter og temaets farver på alle sider, i lyst og mørkt, på skærm og mobil.

Tak til alle, der har brugt Chronicle, meldt fejl og foreslået forbedringer. Det er jeres værktøj.

## 0.21.3 — 2026-10-17

### Changed
- **Det nye design på resten af siderne.** Alle sider i menuen bruger nu samme udtryk som Kontrolpanelet: overskrift med rubrik, tynde kanter og temaets farver i lyst og mørkt.
  - **Ugelogs:** én liste med uge, sammendrag og en linje med opgaver, hændelser og helpdesk-tal. Den aktuelle uge er markeret.
  - **Rådighedsvagt:** nye ugekort med navn, vagtskifte og *nu* ved den, der har vagten. Den aktuelle uge har en farvet kant, tidligere uger er nedtonede. Vælg tidsrum med knapper i overskriften.
  - **Dokumentation:** dokumenterne står i en kolonne ved siden af teksten med indholdsfortegnelse, og teksten følger temaet.
  - **Statistik** er delt i nummererede afsnit: *Hvornår*, *Udvikling*, *Hvem og hvad* og *Chronicle*.
  - Ugelog-formularen, email-bekræftelsen, login og *Adgang nægtet* har fået den nye overskrift.
- **Brødkrummen står i bjælken øverst** på alle sider, ikke længere som en linje på selve siden.
- **Status vises som en farvet prik med tekst** på Forslag, Rapporter, opgavesøgning, opgavehistorik, delte links og API-nøgler. Kun *Blokeret* og *slettet* har stadig et rødt mærke.
- **Løste forslag er nedtonede** i stedet for overstreget.
- Forslagstavlen og søgefelterne på Forslag og i opgavesøgningen folder pænt på mobil.

## 0.21.2 — 2026-10-17

### Added
- **Nyeste og ældste uløste sager på Kontrolpanelet.** Under *Åbne sager* står de seks nyeste og de seks ældste åbne sager med nummer, emne, tekniker og alder. Hver linje åbner sagen direkte i ServiceDesk.
  - Chronicle gemmer nu sagens emne fra ServiceDesk. Eksisterende sager får emnet ved den fulde synkronisering, som kører, når synkroniseringen starter.

### Changed
- **Statistik følger temaets farver.** Graferne, varmekortet og søjlerne bruger accentfarven og de øvrige temafarver, også i mørk tilstand og med dagens tema, og tegnes om, når du skifter.
- **Liggetid på Kontrolpanelet bruger igen de syv aldersgrupper** fra ugerapporten (*Under 1 uge* … *Over 12 måneder*) og tallet *over 1 måned*, med den nye stablede søjle og en kompakt liste.
- **Nøgletallene fylder mindre.** Liggetidssøjlen er fjernet fra *Åbne sager*, da den nu står under *Åbne sager*-afsnittet, og kortene er lavere.

## 0.21.1 — 2026-10-17

### Changed
- **Rådighedsvagten står kun i sidemenuen.** Kortet på Kontrolpanelet vises kun, når sidemenuens kort ikke kan ses: på mobil og når menuen er klappet sammen. Sidemenuens kort viser nu også, hvem der er næste på vagt.
- **Hændelser på Kontrolpanelet viser altid, om de er løst eller uløst**, med en grøn eller rød prik.

## 0.21.0 — 2026-10-17

### Changed
- **Nyt udseende: sidemenu i stedet for topmenu.** Menuen sidder nu i venstre side med rådighedsvagten nederst, og den kan klappes sammen til ikoner. Valget huskes.
  - Tandhjulet nederst i menuen samler *Udseende* (lyst/mørkt), *Densitet*, *Accent* og *Tema*. Mørk tilstand har ikke længere sin egen knap.
  - Øverst på hver side står en smal bjælke med brødkrumme, søgning i opgaver (Ctrl/⌘+K) og notifikationer. Temabannerne står under den.
  - På mobil er menuen skjult bag menuknappen i bjælken.
  - Kort har nu en tynd kant i stedet for skygge.
- **Kontrolpanelet er bygget om i nummererede afsnit.** Overskriften siger, hvor mange sager der er åbne, og om det er flere eller færre end sidste uge. Linjen under viser synkronisering, ugens hændelser og ugelogen.
  - *01 Nu:* hændelser, rådighedsvagt (nu med vagtskifte og næste på vagt) og ugens opgaver. *Alle* ugens opgaver vises, afsluttede er nedtonede i stedet for overstreget.
  - *02 Åbne sager:* tekniker, kategori og liggetid samlet i ét kort. Liggetid er samlet i fire grupper med et mærke for sager over 3 måneder.
  - *03 Udvikling:* de to grafer, nu med ændringen over den viste periode under grafen for åbne sager.
  - Seneste ændring er en smal linje nederst.
  - Hændelser viser alvor som en farvet kant og P1/P2/P3 i teksten i stedet for et mærke.
  - Stopper synkroniseringen med ServiceDesk, siger overskriften, hvor gamle tallene er, nøgletallene markeres *forældet*, og der er en *Prøv igen*-knap.
- **Ugelog:** overskrift og nøgletal folder pænt på smalle skærme, og nøgletallene viser forrige uges tal. Opgaver viser *N åbne af M* og *x / M afsluttet*, hændelser *N denne uge · M kritisk*. Afsluttede opgaver er nedtonede, ikke overstreget, også i opgavesøgningen.

## 0.20.12 — 2026-10-16

### Added
- **Vælg periode på Statistik-siden.** Felterne *Fra* og *Til* øverst på siden. Standard er stadig de seneste 12 måneder frem til nu, og *Seneste 12 måneder* nulstiller valget.
  - Begge dage er med. Alle tal, uge- og månedsgrafer, ugedagsgennemsnit og hændelser følger perioden.
  - Slutter perioden før i dag, vises åbne sager, som de stod ved periodens slutning (genberegnet ud fra oprettelses- og lukketid). Aktive prioriterede opgaver er altid dagens tal, fordi deres statushistorik ikke gemmes.
  - Perioden står i adressen, så den kan bogmærkes eller deles, og eksporterne (PDF, HTML, Markdown og JSON) bruger den samme periode. Delingslinket til Claude Motion viser fortsat de seneste 12 måneder.

## 0.20.11 — 2026-10-16

### Fixed
- **Søgefeltet i *Tilføj åbne opgaver fra tidligere uger* og *Flet* mister ikke længere markøren.** Før blev hele dialogen genindlæst efter få bogstaver, så markøren sprang til starten af feltet, og bogstaver skrevet imens forsvandt. Nu opdateres kun listen med opgaver, og feltet bliver stående, mens du skriver.

## 0.20.10 — 2026-10-15

### Added
- **Sager pr. afdeling på Statistik-siden.** Et nyt kort med én søjle pr. afdeling for årets sager, med antal og andel, sorteret efter flest sager. Sager uden afdeling står som *Ingen afdeling*.
  - Afdelingen er den, som den person, der oprettede sagen, hører til i ServiceDesk. Annullerede sager tæller med, ligesom i kategorierne.
  - Fordelingen er også med i eksporterne: HTML/PDF, Markdown og JSON (`helpdesk.created_by_department`).

## 0.20.9 — 2026-10-15

### Added
- **Åbne sager fordelt på liggetid på Kontrolpanelet.** Et kort med de samme søjler som i ugerapporten, én pr. aldersgruppe fra *Under 1 uge* til *Over 12 måneder*, med antal og andel og en linje om, hvor mange sager der har ligget i mere end en måned.
  - Kortet står i fuld bredde under de to donut-diagrammer i rækken *Åbne sager lige nu*. Det opdateres hvert minut og skjules i Kompakt-visning ligesom de andre grafer.
  - Tallene er de samme som den lille søjle på nøgletallet *Åbne sager*: ugens seneste ServiceDesk-synkronisering.

## 0.20.8 — 2026-10-15

### Changed
- **Hændelser på Kontrolpanelet viser kun de seneste 30 dage.** Hændelser, der stadig er uløste, vises altid, uanset alder.
  - Ældre hændelser ligger bag *Vis ældre* nederst på kortet (op til 20). *Kun de seneste 30 dage* klapper dem sammen igen, og valget holder, når kortet opdateres hvert minut.
  - Er der ingen hændelser i perioden, står der *Ingen hændelser de seneste 30 dage*, og de ældre kan stadig foldes ud.

## 0.20.7 — 2026-10-15

### Changed
- **Ny rækkefølge på Kontrolpanelet**, så det vigtigste står øverst:
  1. Nøgletallene for helpdesk (uændret).
  2. **Nu:** hændelser, rådighedsvagt og aktuel ugelog.
  3. **Åbne sager lige nu:** fordelt på tekniker og på kategori, side om side.
  4. **Udvikling:** *Ny vs. lukket* og *Åbne sager — udvikling*, side om side.
  5. Seneste ændring i Chronicle.
- Kompakt og Dashboard viser de samme kort som før: Kompakt skjuler graferne og seneste ændring, Dashboard skjuler hændelser, vagt, ugelog og seneste ændring.

## 0.20.6 — 2026-10-15

### Added
- **Åbne sager fordelt på tekniker.** Et donut-diagram over de åbne helpdesk-sager fordelt på den tekniker, sagen er tildelt i ServiceDesk, i samme stil som kategori-diagrammet:
  - **Kontrolpanelet** har et nyt kort under kategori-kortet. Det opdateres hvert minut og skjules i Kompakt-visning.
  - **Ugerapporten** (PDF, HTML, mail og Markdown) har en ny sektion efter kategorierne, med samme regler for tidspunkt: åbne nu for den aktuelle uge, åbne ved ugens udgang for tidligere uger.
  - Sager uden tekniker vises som en grå skive, *Ikke tildelt*. Teknikere, som ServiceDesk har anonymiseret (tidligere ansatte), samles under *Anonymiseret tekniker*.

## 0.20.5 — 2026-10-15

### Added
- **Åbne sager fordelt på kategori.** Et donut-diagram over de åbne helpdesk-sager fordelt på ServiceDesk-kategori:
  - **Kontrolpanelet** har et nyt kort med diagrammet, en forklaring og antal og andel pr. kategori. Kortet opdateres hvert minut og skjules i Kompakt-visning ligesom de andre grafer.
  - **Ugerapporten** (PDF, HTML, mail og Markdown) har en ny sektion med samme diagram og samme farver. For den aktuelle uge er det sagerne, der er åbne nu; for en tidligere uge er det sagerne, der var åbne ved ugens udgang. I mailen sendes diagrammet som indlejret billede, og forklaringen er en tabel, så den holder i Outlook.
  - Sager uden kategori vises som en grå skive, *Ingen kategori*. Ved få åbne sager giver det et ærligere billede end kun at regne andele af de kategoriserede.

## 0.20.4 — 2026-10-15

### Added
- **Del statistikken som link (Claude Motion).** Under *Statistik → Eksportér → Del som link* kan redaktører oprette hemmelige links til statistikken for værktøjer, der ikke kan logge ind, f.eks. Claude på nettet og Claude Motion.
  - Hvert link får et navn og en gyldighed (7, 30, 90 dage eller 1 år) og kan tilbagekaldes med det samme. Siden viser, hvor mange gange og hvornår linket sidst er hentet.
  - Linket har to adresser: **data** (`…/data.json`, statistikken som JSON, beregnet frisk ved hver hentning) og en **vejledning** (`…/vejledning.md`). Vejledningen forklarer Claude hvert felt og enhederne og de forbehold, der gælder (kalendertid, de manglende kategorier, anonymiserede teknikere), og foreslår et forløb i ti scener til en animeret præsentation på dansk.
  - *Kopiér prompt* giver en færdig dansk prompt med begge links, som kan sættes direkte ind i Claude Motion. Siden har en trin-for-trin-vejledning.
  - Linkene kræver ikke login, men giver kun adgang til statistikken. Svarene caches ikke og indekseres ikke, og et ukendt, udløbet eller tilbagekaldt link giver 404.

## 0.20.3 — 2026-10-15

### Added
- **Eksport af Statistik.** Statistik-siden har nu samme *Eksportér*-menu som ugerapporten (kun for redaktører):
  - **PDF** og **HTML**: hele siden som rapport med ugerapportens layout; graferne tegnes på serveren og ligger i filen, så den virker uden login.
  - **Markdown**: alle tal som tabeller.
  - **JSON**: et maskinlæsbart dokument til andre værktøjer, f.eks. Claude Motion. Det har faste engelske nøgler, eksplicitte enheder (timer, procent, antal), periode og kilder, og definitionerne bag tallene. Det indeholder alle rå tal, også varmekortet som 7 × 24 tal og de 52 uger. Formatet er versioneret (`schema_version`). *Vis JSON i browseren* åbner filen direkte i stedet for at downloade den.

## 0.20.2 — 2026-10-15

### Changed
- **Forklaringer under løsningstiderne på Statistik.** Median, gennemsnit, "9 ud af 10 er løst inden" og "løst inden for et døgn" har nu hver en kort tekst, der forklarer, hvad tallet betyder — og hvorfor gennemsnittet ligger langt over medianen.

## 0.20.1 — 2026-10-15

### Changed
- **Tal i varmekortet på Statistik.** Hvert felt i "Hvornår på dagen skriver kollegerne?" viser nu antallet af nye sager i perioden for den ugedag og time; tomme felter står blanke, og på de mørkeste felter er tallet hvidt. Alle timer har nu en overskrift. Hold musen over et felt for at se gennemsnittet pr. dag.

## 0.20.0 — 2026-10-15

### Added
- **Statistik-side.** Ny side under *Statistik* i menuen med et års tal (de seneste 365 dage):
  - **Helpdesk:** antal oprettede sager, hvor mange forskellige kolleger der har skrevet, gennemsnit pr. måned, median løsningstid og åbne sager lige nu.
  - **Hvornår der skrives:** nye sager pr. ugedag i gennemsnit og et varmekort over ugedag × klokkeslæt.
  - **Løsningstid:** median, gennemsnit, hvornår 9 ud af 10 er løst, andel løst inden for et døgn og en fordeling fra "under 1 time" til "over 4 uger". Det er kalendertid, så nætter og weekender tæller med.
  - **Pr. uge:** åbne sager ved ugens udgang og oprettet mod løst.
  - **Fordelinger:** sager pr. kategori, løste sager pr. tekniker (i procent) og åbne sager efter alder.
  - **Chronicle:** prioriterede opgaver (oprettet, afsluttet, aktive, levetid, pr. måned) og nedbrud/hændelser (antal, pr. måned, alvorlighed og type).
- **Spejl af helpdesk-sagerne.** Statistikken bygger på en lokal kopi af sagerne i ServiceDesk (tabellen `HelpdeskTicket`), som synk-containeren holder opdateret: en fuld synkronisering ved opstart og én gang i døgnet, og derimellem kun de ændrede sager i hver runde. Der gemmes kun det, statistikken bruger. Anmoderen gemmes som ServiceDesk-id, ikke som navn. `python manage.py sync_helpdesk_tickets [--full]` kører synkroniseringen manuelt. Sagerne kan ses (ikke redigeres) under Admin → Helpdesk-sager.

## 0.19.1 — 2026-10-14

### Added
- **Forhåndsvisning og størrelse på indsatte billeder.** Så snart en beskrivelse indeholder et billede, vises en forhåndsvisning under feltet — renderet præcis som på detaljesiden. Hold musen over et billede for at vælge størrelse: **S** (240 px), **M** (480 px), **L** (800 px) eller **Fuld**, eller træk i det runde håndtag i hjørnet for en fri bredde. ✕ fjerner billedet fra teksten. Størrelsen gemmes i teksten som `![billede|480](/images/…)` og bruges også på detaljesiden og i eksporter.
- **Billeder i hændelser.** Beskrivelsen på en hændelse tager nu også imod indsatte billeder (Ctrl+V, træk-og-slip, forhåndsvisning og størrelse) og vises som Markdown i ugeloggen. Billederne kommer med i ugerapporten: i PDF'en og HTML-eksporten er de indlejret i selve filen, og i mailen sendes de som indlejrede billeder ligesom graferne, så modtagerne ser dem uden at logge ind. Bredden begrænses til siden (PDF) og mailens bredde, så et stort screenshot ikke løber ud over kanten.

### Changed
- I ugerapport-mailen vises hændelsernes beskrivelse nu i fuld længde og formateret som Markdown — før blev den skåret ned til 30 ord som ren tekst. PDF og HTML viser også beskrivelsen formateret.

### Fixed
- Indsætning læser nu også billeder, som browseren kun lægger i udklipsholderens `items` og ikke i `files`.

## 0.19.0 — 2026-10-14

### Added
- **Indsæt billeder med Ctrl+V.** I beskrivelsen på opgaver og feature requests kan et screenshot nu indsættes direkte fra udklipsholderen (eller trækkes ind i feltet). Billedet uploades med det samme, og der indsættes en Markdown-reference, `![billede](/images/…)`, hvor markøren står. Beskrivelserne vises nu som Markdown på detaljesiderne, så billederne ses der; på feature-request-tavlen står der `[billede]` i forhåndsvisningen. Kun PNG, JPEG, GIF og WebP (maks. 15 MB) accepteres — formatet afgøres af selve filen, ikke filnavnet. Billederne ligger i `IMAGE_FILES_DIR` (standard: ved siden af databasen, på data-volumen i Docker) og kræver login for at blive vist. Kun redaktører kan uploade.
- **Touch-Grass-Weekend.** Søsteren til Read-only Friday: hver lørdag og søndag viser Chronicle et grønt banner — "Det er weekend. Gå udenfor." — med en roterende påmindelse om, at det kan vente til mandag, medmindre man har vagten. Banneret har en græskant, en stribe græs løber langs bunden af vinduet, og logomærket bliver grønt. Det følger lys/mørk tilstand og lever side om side med temadagene. `?force-weekend=1` viser det på hverdage, `?force-weekend=0` skjuler det i weekenden.

## 0.18.1 — 2026-10-10

### Fixed
- **Video-upload via API'et afviste rigtige videoer.** `PUT /api/v1/reports/<slug>/video/` læste hele filen ind i hukommelsen og ramte Djangos grænse på 2,5 MB med et 400-svar. Filen streames nu til disk i bidder, så grænsen er de 300 MB, der var meningen.

## 0.18.0 — 2026-10-10

### Added
- **Video på rapporter.** En rapport kan have en MP4 vedhæftet (upload-formularen eller `PUT /api/v1/reports/<slug>/video/`). Videoen streames med understøttelse af spoling (HTTP Range), kan downloades med `?download=1`, og følger rapportens adgang: offentlig rapport, offentlig video. Listen Rapporter viser "Slides + video" og en download-knap. Filerne ligger i `REPORT_FILES_DIR` (standard: ved siden af databasen, altså på det persisterede data-volumen i Docker).

## 0.17.1 — 2026-10-10

### Changed
- **Offentlige rapporter er åbne på deres almindelige adresse.** `/reports/<slug>/` kræver ikke længere login, når rapporten er markeret offentlig; "Gør privat" lukker den igen. Siden Rapporter viser nu den læsbare adresse som det link, der kopieres. Det anonyme token-link (`/reports/p/…`) findes stadig for links, der allerede er sendt ud, og kan fornys med "Nyt anonymt link".

## 0.17.0 — 2026-10-10

### Added
- **Menuen Rapporter.** Selvstændige HTML-sider med egen grafik, fx den animerede årsgennemgang, kan lægges op i Chronicle og findes under "Rapporter". Siderne serveres uden Chronicles menu og farver. En rapport kan markeres **offentlig** og får så et langt, ugætteligt link, der virker uden login, så den kan sendes til ledelsen eller andre uden en Chronicle-konto. "Gør privat" slår linket fra med det samme, "Nyt link" udsteder et nyt. Redaktører lægger rapporter op fra siden (filupload, valgfri erstatning af en eksisterende rapport så linket bevares) eller via API'et: `PUT /api/v1/reports/<slug>/` og `GET /api/v1/reports/`. Offentlige sider sendes med `noindex`, `no-store` og `Referrer-Policy: no-referrer`, så linket ikke lækker. (FR #14)

## 0.16.2 — 2026-10-01

### Changed
- **Read-only Friday er nu umulig at overse.** (FR #12 fra mra: "Kan vi MEGET tydeligt fremhæve …") Banneret er massivt rødt med hvid tekst og advarselsstriber i enderne, og teksten "Ingen ændringer i produktion i dag" står fast — kun den afsluttende påmindelse roterer. Hele siden får en rød ramme, der bliver stående mens man scroller, og logomærket i navigationen skifter til rødt. Stadig kun om fredagen; `?force-friday=1` viser det på andre dage.

## 0.16.1 — 2026-10-01

### Fixed
- **Send-knappen på email-bekræftelsen sendte ikke.** Knappen skiftede til "Sender…" og blev slået fra i samme klik, og Alpine nåede at slå den fra, før browseren udførte selve indsendelsen — så formularen blev aldrig sendt, og der skete "ingenting". Nu skifter knappen først, når formularen faktisk er sendt af sted (på `submit`), hvor det kun forhindrer dobbeltklik. Fejl indført i 0.15.0.

### Added
- **Afsendelser logges.** Hvert forsøg på at sende en rapport logges i containerloggen med bruger, emne, format og antal modtagere, og resultatet logges som INFO (sendt) eller ERROR (fejlbesked fra Graph/SMTP). Sendefunktionerne sluger selv undtagelser til en toast, så en fejlet afsendelse efterlod hidtil intet spor.

## 0.16.0 — 2026-10-01

### Added
- **Read-only Friday-banner.** Hver fredag (dansk tid) viser sitet et rødt banner øverst: "Read-only Friday — ingen ændringer i produktion i dag", med et par roterende påmindelser om at deploys, patches og "lige en lille rettelse" venter til mandag. Det er en regel, ikke et tema: det følger ugedagen frem for en dato, kan ikke slås fra i tema-panelet, og ligger oven i et eventuelt dagstema (Pirate Day falder fx på en fredag i 2026). Forhåndsvisning med `?force-friday=1`, skjul på en fredag med `?force-friday=0`.

## 0.15.0 — 2026-09-22

### Added
- **Bekræftelse før en rapport sendes som email.** "Email som HTML/PDF/HTML + PDF" i eksport-menuen sendte rapporten med det samme — ét klik, ingen mulighed for at se hvem der fik den. Nu åbner de en bekræftelsesside, der viser modtagerne (fra `CHRONICLE_EMAIL_RECIPIENTS`), afsenderen, emnet og hvad der vedhæftes, med en "Send til N modtagere"-knap og Annullér. Intet sendes, før der trykkes Send; selve afsendelsen sker som POST med CSRF-beskyttelse i stedet for et GET-link. Er modtagerlisten tom, er knappen slået fra, og siden forklarer hvorfor. Gælder både ugelog-rapporten og opgave-historikken. (FR #10)

### Changed
- Et ugyldigt `format` på email-eksporten svarer nu 400 i stedet for stille at falde tilbage til "both".

## 0.14.1 — 2026-09-20

### Changed
- **Temavælgeren i tweaks-panelet er en lodret liste.** Fem temanavne af meget forskellig længde kunne ikke ombrydes pænt som piller i det 280 px brede panel — "Pirate Day" og "Star Trek" knækkede over to linjer. Nu har hvert tema sin egen række med en prik i temaets accentfarve, dets dato ("21. sep", "4. maj") og et flueben på det valgte. "Auto" står øverst med forklaringen "følger kalenderen". Datoen kommer fra temaets skedule (`Theme.when_label`), som hentes i ét ekstra opslag frem for ét pr. tema.

## 0.14.0 — 2026-09-20

### Added
- **Tema for Verdens Alzheimerdag, 21. september.** Sitet skifter til lilla — sagens internationale farve, hentet fra Alzheimer's Awareness-mærket (dyb kongelilla i ringen, vandrette bånd ned til lys lilla) — med et forglemmigej-mærke i logoet og et banner, der roterer korte fakta og henvisninger: Demenslinien (58 50 58 50) og alzheimer.dk. Bannerets mærke er en egen tegning i stil med dagens kampagnegrafik: et hoved i profil, den lilla sløjfe dér hvor sindet sidder, tre kronblade. Ingen vittigheder, ingen temaformuleringer andre steder — dagen er ikke et kostume. Kører automatisk hvert år den 21. september og kan vælges manuelt i tema-panelet som "Alzheimerdag".

## 0.13.1 — 2026-09-07

### Fixed
- **Rapport-emailen kan læses i Outlook classic.** Den klassiske Outlook-klient på Windows renderer mail gennem Word, som hverken kan flexbox, `max-width`, `border-radius` eller `data:`-URL'er. Mailen så derfor fin ud i Outlook web og ødelagt i klienten. Fire ting er lavet om:
  - **Graferne sendes nu som inline-vedhæftninger** og refereres med `cid:` i stedet for at ligge som base64 i `src`. Word afviser `data:`-URL'er helt, så begge grafer var tomme kasser. Beskeden sendes som `multipart/related`, så klienten viser dem i teksten frem for at liste dem som filer. Graph-backend'en forstår nu `contentId`/`isInline`.
  - **Nøgletallene (Nye/Lukkede/Åbne/Netto) er nu en tabel** i stedet for flexbox, som Word ignorerer — de stablede sig oven på hinanden i fuld bredde.
  - **Hele mailen ligger i en 600 px centreringstabel**, og billeder har `width`/`height` som HTML-attributter, så Word ikke skalerer dem efter sin egen DPI.
  - **Kodeblokke ligger i en tabelcelle med `bgcolor`**, fordi Word ikke tegner baggrund eller ramme på et `<pre>`. Tomme afsnit, som Markdown efterlader før hver blok, fjernes — Word viser dem som blanke linjer.
- PDF- og HTML-eksporten er uændret at se på; kodeblokkenes tabel renderer ens i WeasyPrint og browseren. Kun mailen skifter grafer til `cid:` — den selvstændige HTML-eksport beholder `data:`-URL'er, så filen stadig virker alene.

## 0.13.0 — 2026-09-06

### Added
- **Genåbn-knap på opgavesøgningen.** Afsluttede opgaver har nu en ↺-knap i søgeresultatet: den sætter opgaven tilbage til "igangværende", rydder auto-lukket-markeringen og lægger den på indeværende uge, så den er synlig et sted og ikke kun kan findes gennem søgning. Knappen vises kun på afsluttede opgaver, kun for redaktører, og ikke på slettede eller flettede.
- Efter handlingen lander man samme sted i søgningen — med fritekst, status og år intakt — i stedet for at blive sendt til opgavens historik. Et referer uden for sitet følges ikke.

## 0.12.1 — 2026-09-06

### Changed
- **Større beskrivelsesfelt på prioriterede opgaver.** Tekstfeltet gik fra 3 til 8 linjer. Beskrivelsen er nu det eneste felt på en opgave og indeholder Markdown — trin, kodeblokke, tabeller — så der var for lidt plads at arbejde i.

## 0.12.0 — 2026-09-06

### Changed
- **Noter-feltet er væk fra prioriterede opgaver.** Alt skrives i beskrivelsen for ugen, så feltet er fjernet fra opret/rediger-formularen. Formularen er nu Titel, Prioritet, Status og Beskrivelse.
- Kolonnen bliver på modellen: 23 ældre opgaver har stadig tekst i noter, og den bliver ved med at blive vist på opgavens historik og i rapporterne. Nye opgaver har ingen noter, så de steder står tomme og fylder ingenting. Feltet kan stadig redigeres i admin, og API'et tager stadig imod `notes` — MCP-værktøjerne er uændrede.

## 0.11.2 — 2026-09-06

### Fixed
- **Nummererede lister startede forfra ved 1.** A numbered procedure whose steps are separated by code blocks — step, ```bash``` block, next step — renders as several separate lists, each carrying a `start` attribute so the numbering continues. The sanitiser's allowlist did not include `start`, so it was stripped and every step came out as "1." Reported from uge 36, where each step of the Veeam setup is followed by a shell block.
- **Kolonnejustering i tabeller forsvandt** for the same reason: `|:---|---:|` becomes `style="text-align: …"` on the cells, which the allowlist also dropped. Both are back, along with `colspan`/`rowspan`. The allowlist still refuses `style` on everything else in the web renderer, so raw HTML cannot smuggle in layout.

## 0.11.1 — 2026-09-06

### Fixed
- **Tom rød boks i hjørnet af hver side.** The htmx error toast added in 0.10.6 carried its layout as an inline `display: flex`, which beats the browser's `[hidden] { display: none }` rule — so the empty toast sat visible in the bottom-right corner of every page, showing nothing but its close button. The layout moved to `.error-toast` in the stylesheet, where `.error-toast[hidden]` can switch it off. Two tests now guard it: the markup must carry no inline `display`, and the rule must exist in the built CSS.

## 0.11.0 — 2026-09-06

### Added
- **Markdown i prioriterede opgaver.** Beskrivelser og noter renderes nu som Markdown i stedet for rå tekst: **fed**, lister, tabeller, citater, overskrifter, links og kode. Bare URL'er bliver stadig klikbare af sig selv, som de var før.
- **Syntaksfarvning i kodeblokke.** En fence med et sprog (` ```bash `, ` ```python `, …) farvelægges med Pygments. Websiden bruger CSS-klasser, så koden følger lys/mørk tilstand; en fence uden sprog gættes ikke, den forbliver neutral.
- **Kopiér-knap** på hver kodeblok på websiden, også på blokke der kommer ind med en HTMX-opdatering.
- **Det samme i alle eksporter.** PDF, HTML-eksport og email får den fulde formatering med farvelægning og blokke inlinet som `style`-attributter, fordi mailklienter fjerner stylesheets og Outlook taber CSS ved indsæt. Markdown-eksporten er uændret — den indeholder kilden i forvejen.

### Changed
- Rækken i ugeloggen justerer nu pills og knapper efter opgavens titel i stedet for at centrere dem, så de ikke svæver midt i en høj beskrivelse.
- Renderet Markdown saniteres med nh3 (Ammonia) mod en allowlist. Felterne skrives af kolleger, men de er stadig brugerinput; rå `<script>`, event-handlers og `javascript:`-links overlever ikke, og links får `rel="noopener noreferrer"`. Det gælder også mødereferatet, som hidtil blev renderet uden filter.

## 0.10.6 — 2026-09-06

### Fixed
- **Sikkerhed: læsere kunne skrive alligevel.** `EditorRequiredMixin` ran the view *first* and checked the role afterwards, so a user in the Viewer group got a 403 back while their write had already been committed. Six paths were affected: create/edit/delete of a prioriteret opgave, edit of a ugelog, and create of fravær and hændelser. The role is now checked before the view body runs; anonymous users still get the login redirect rather than a 403, and staff still override group membership.
- **HTMX-fejl er ikke længere tavse.** htmx performs no swap on a 4xx/5xx response, so a rejected save looked like a dead button — nothing moved, nothing was said. Every HTMX failure now raises a toast in the corner ("Handlingen blev afvist (403). Din session er sandsynligvis udløbet — genindlæs siden og prøv igen.", a server-error variant, and one for a request that never reached the server).

### Note
- If every form on the site 403s while pages load fine, the origin you are browsing on is missing from `CSRF_TRUSTED_ORIGINS` — Django matches scheme, host **and port** exactly, so reaching Chronicle through a tunnel on `:8443` needs that exact origin listed. See docs/DEPLOYMENT.md.

## 0.10.5 — 2026-09-03

### Changed
- **Ugelogs adresseres nu på år og uge.** `/logbook/39/` became `/logbook/2026/34/` — the way the team refers to a week, rather than a database id nobody can read. The edit page (`/logbook/2026/34/edit/`) and the four export endpoints (`/logbook/2026/34/export/pdf/` and friends) follow the same shape, which also matches what the JSON API has always used (`/api/v1/weeklogs/<år>/<uge>/`).
- Old id-based links keep working: `/logbook/<id>/` and `/logbook/<id>/edit/` answer with a permanent redirect to the year/week URL, so bookmarks and links inside already-sent reports still resolve.
- The HTMX partial endpoints inside the weeklog page (klarmelding, mødereferat, "tilføj eksisterende opgave") stay id-addressed — they are POST targets rendered into the page and never appear in the address bar.

## 0.10.4 — 2026-08-28

### Changed
- **Sync'en kalder ServiceDesk 3 gange i stedet for 12.** The open-ticket queries were one API call per status (five), and the liggetid breakdown added five more on top. ServiceDesk Plus accepts a `values` list on `status.name`, so a single listing now returns every open ticket with its `created_time` — the count and the age breakdown come from the same rows and can no longer disagree. A sync cycle is now: new-count, closed-count, one open listing (plus one call per extra 100 open tickets). At the default five-minute interval that is ~860 calls a day instead of ~3.500 — and below the ~2.000 the sync made before liggetid existed. Historical reconstruction (`backfill_liggetid`) dropped from six calls per week to two.
- If the listing fails, the sync falls back to the old count-per-status query so the headline number still updates, and leaves the previous breakdown in place rather than replacing it with zeros.

### Fixed
- **Count-forespørgslerne sendte Python-syntaks som JSON.** `_query_count` and `_query_open_count` serialised their payload with `str(dict)` and a quote swap, which emits `True` rather than `true` and would corrupt any value containing an apostrophe. Both now use `json.dumps`. ServiceDesk happened to accept the old form, so no numbers were wrong.

## 0.10.3 — 2026-08-27

### Added
- **Backfill af liggetid for lukkede uger** (FR #8, opfølgning). The sync only ever fills in the current week, so weeks that closed before 0.10.0 showed no liggetid section at all. New `backfill_liggetid <år> <uge>` management command reconstructs a past week from ServiceDesk history: a ticket counts as open at the week's snapshot instant if it was created by then and is either still open or was closed afterwards, and ages are measured at that instant rather than today. `--all-missing` walks every week without a breakdown, `--dry-run` prints without saving. Run it where the ServiceDesk credentials live (the sync container).
- **`PATCH /api/v1/weeklogs/<år>/<uge>/helpdesk-age/`** (write scope) sets the seven buckets on a past week. Same rule as the form: the buckets must add up to "Åbne sager", with an optional `helpdesk_open` to correct the total; all-zero clears the breakdown.

### Note
- A reconstruction can land slightly below the recorded open count — tickets deleted or merged since the snapshot cannot be recovered. The command refuses to save on a mismatch unless `--adjust-total` is passed, so the discrepancy stays visible rather than being silently absorbed into a bucket.

## 0.10.2 — 2026-08-27

### Fixed
- **Sync-containeren bygges nu af CI og versionsstyres.** `chronicle_sync_servicedesk` was built by hand and last pushed on 2026-02-03, so the deployed scheduler ran February's code against the current database — it would never have written the new liggetid buckets. CI now builds `docker/Dockerfile.sync` on every push to main and tags it with the same `version.txt` version as the web image, and the compose file pins both services to that version instead of letting the sync float on `:latest`.

## 0.10.1 — 2026-08-27

### Changed
- **Finere liggetid-opdeling** (FR #8, opfølgning). The age breakdown went from four buckets to seven: under 1 uge, 1–2 uger, 2 uger – 1 måned, 1–3 måneder, 3–6 måneder, 6–12 måneder og over 12 måneder. The bar colours now run as a ramp from sage (nyeste) to terracotta (ældste) and live in the model spec, so the report, the email body and the dashboard card can never drift apart. The highlight line counts everything older than **1 måned** (was 30 dage — same threshold, clearer wording).
- The four 0.10.0 bucket fields are replaced by seven (migration `logbook/0013`). The old counts are dropped rather than split: the ServiceDesk sync recomputes the current week within five minutes, and no week had a hand-entered breakdown yet.

## 0.10.0 — 2026-08-27

### Added
- **Åbne sager opdelt på liggetid** (FR #8). Every report now carries an "Åbne sager fordelt på liggetid" section: one bar per age group — 0–7, 8–30, 31–90 and over 90 dage — with the count, the share, and a summary line ("10 af 40 åbne sager har ligget i mere end 30 dage"). Rendered in the PDF, the HTML export, the email body and the Markdown export; the section is skipped for weeks that have no breakdown, so old weeklogs are untouched.
- **Liggetid på kontrolpanelet.** The "Åbne sager" KPI card gets a slim stacked bar (hover a segment for its bucket and count) plus an "X over 30 dage" line, so the split is visible without opening a report.
- **Automatisk opdeling fra ServiceDesk.** The sync pages through every open request, reads `created_time` and buckets the ages itself; the four new counts are stored on the weeklog as a snapshot, so a week keeps the numbers that were true when it was logged. A failed age query leaves the previous breakdown in place instead of zeroing it.
- **Manuel indtastning.** The weeklog form (and the admin) expose the four buckets for weeks kept by hand. A partially filled breakdown that does not add up to "Åbne sager" is rejected; all-zero simply means "no breakdown".
- **API additive fields**: `helpdesk_open_by_age` and `helpdesk_open_stale` on the weeklog payload, plus `open_by_age`/`open_stale` per week on `/api/v1/helpdesk/data/` and the dashboard chart endpoint. Existing keys are unchanged.

## 0.9.0 — 2026-08-21

### Added
- **Klarmelding på ugeloggen** (FR #7). Every weeklog gets a "Klarmelding" card: editors can mark "Jeg har ikke mere til denne uge", and whoever compiles/closes the week sees green pills with the names (hover shows the timestamp) of colleagues who are done contributing. The marker is per-user and toggleable ("Fortryd klarmelding" undoes it); viewers see the list but can't sign off, since they can't contribute content anyway. New `WeekLogSignoff` model (one row per weeklog × user), HTMX toggle endpoint, admin inline on the weeklog, and an additive `signoffs` list on the full weeklog API/MCP payload.

## 0.8.2 — 2026-07-27

### Changed
- **Afsluttede opgaver nedtones ikke længere** (FR #6). Completed priority items kept full-strength text: the row `opacity` fade and the muted grey title colour are gone from the weeklog list, the dashboard "Denne uge" panel and the priority search. The checkmark, the strikethrough and the status pill still mark completion — the text just stays readable. Deleted items keep their dimming (different state, different cue).

### Added
- **Bell notification when a feature request is solved.** Marking a request "Løst" — via the board's solve button, the edit form, a drag into the solved column, or the API/MCP — now notifies the submitter ("Dit forslag ”…” er løst") with a link to the request. Self-solves and re-solves of an already-solved request stay silent.

## 0.8.1 — 2026-07-03

### Changed
- **Brugervejledning: konkret vagtoverdragelses-eksempel.** New "Eksempel: Overtag vagten nu" walkthrough in the Vagtkalender section — how to record "Peter havde vagten indtil nu, jeg har den fra nu" in one action, plus the two-step flow for retroactively recording the previous holder when the week was never claimed. Docs only, no code changes.

## 0.8.0 — 2026-07-03

### Added
- **Vagtskifte-dropdown på vagtkalenderen** (FR #5). Every week card gets a pencil that swaps in an assign form: pick any active user (or "— Ledig —" to free the week), a "Fra dato" and optional "Fra kl." for mid-week/intra-day handovers ("Bo overtager torsdag kl. 14:00"), and an optional note. Split weeks render one line per period ("Anna · ma–on 14:00 / Bo · on 14:00–sø") with today's holder highlighted.
- **Per-day coverage record.** New `OnCallSegment` model (datetime-based, end-exclusive, no FK to the duty row so history survives releases). Every existing week was backfilled with one whole-week segment. Releasing mid-week keeps the already-covered days on record.
- **Audit trail.** New `OnCallChange` model (TaskStateChange pattern): who changed the shift, when, from → til whom, effective from. Written exclusively inside the single service entry point `services.apply_assignment` — claim, release and assign all funnel through it. Changes before 0.8.0 were never recorded. Append-only in admin.
- **Historik-panel.** Weeks with changes show a clock icon that loads a panel above the grid: "Dækning" (who had which days) + "Ændringer" (the audit trail). Viewers can read it; only editors can mutate.
- **Tidligere uger.** The calendar can show 4/13/26 past weeks; editors can correct a closed week's coverage through the same audited form. Claim/release stay hidden on past weeks.
- **Notifikationsklokke.** New `apps.notifications` app wires up the previously decorative bell: unread badge (60s poll + instant OOB clear), dropdown panel, and read-on-open semantics. First consumer: on-call changes notify the assignee and any displaced holder ("Du er sat på rådighedsvagt uge 29, 2026 fra to 14:00"); self-service claim/release stays silent.
- **API additive fields** on `/api/v1/oncall/current/`: `segments`, `changes`, `created_at`, `updated_at`. Legacy keys are contract-pinned and unchanged; `user` now resolves to whoever covers *right now* during a split week (dashboard and MCP `chronicle_oncall_current` get this for free). Weekly-report exports show "Anna (ma–on), Bo (on 14:00–sø)" only when a week is actually split — single-holder output is byte-identical.

### Fixed
- **UTC seam in week resolution.** `get_current()` and the calendar grid used `timezone.now().isocalendar()` (UTC) — near midnight Sunday/Monday they could disagree with Copenhagen's ISO week. Both now use `timezone.localdate()`.
- **Invalid year/week URLs** (e.g. `/oncall/2026/99/status/`) returned 500; now 404.

## 0.7.18 — 2026-06-18

### Added
- **Incident audit trail.** `Incident.created_by` (FK to user, nullable, `SET_NULL` on user delete). Captured automatically in `IncidentCreateView` (`request.user`) and in the API `log_incident` endpoint (`request.api_user`). Existing 27 incidents get NULL — irrecoverable from the data, but every new one will show who logged it. Surfaced in the expanded incident row as "Logget af **{name}** · Oprettet {timestamp}" plus an updated-at stamp when it differs from created_at.
- **API exposes `created_at` / `updated_at` / `created_by`** on every incident response (`serialize_incident`). MCP `chronicle_incidents` now returns these fields too — no MCP server change needed since it forwards whatever the API returns.

## 0.7.17 — 2026-05-27

### Added
- **Themed top-of-page greeting.** The `Goddag, Gorm. her er ugen.` headline now picks a greeting based on time-of-day **and** the active theme + light/dark mode. Star Wars light → "Hilsen", Star Wars dark → "Imperial dag", Pirate → "Ahoj" / "Yarr", Star Trek Federation → "Hilsen, kommandør", Star Trek Klingon → "Qapla". Falls back to "Goddag" when no theme is active. All 24 variants (6 modes × 4 time slots — morning / day / evening / night) live in a small lookup table inside the existing Alpine `x-text` expression so it stays fully client-side and reactive to tweaks-panel changes.

## 0.7.16 — 2026-05-27

### Added
- **Star Trek phrase swaps** for the dashboard, with separate Federation (light) and Klingon (dark) phrasings — mirrors the Star Wars rebel/sith split. `{% sw_phrase %}` extended with two new optional kwargs: `trek=` for Federation light mode and `klingon=` for Klingon dark mode (falls back to `trek` if omitted). Translations include Rådighedsvagt → Kommandør på vagt / Krigsleder på vagt, Lukkede sager → Fuldførte missioner / Æresfulde sejre, Bemanding → Bridge-mandskab / Krigerbande, Aktive opgaver → Aktive direktiver / Ordrer fra Kahless, Helpdesk → Stjerneflåde-rapport / Empire-rapport, Hændelser → Anomalier / Kampe, etc.

## 0.7.15 — 2026-05-27

### Added
- **Star Trek theme** (FR #4 — submitted in-app once the API came back). Light mode = Federation/Starfleet command blue with the ▲ command-delta brand glyph; dark mode = Klingon Empire blood-red with the ⊛ warrior emblem. 79 rotating banner messages mixing Starfleet operations, Klingon culture, Federation diplomacy, FynBus bus operations remixed as starship missions, and classic catchphrases ("Live long and prosper.", "Engage.", "Qapla'!", "Make it so."). Faint star-chart dot pattern as page background. Footer Easter egg: `▲ NCC-1701 · STARDATE 79023.5 ▲`.
- Two annual schedules seeded: **8. september** (Star Trek Day — TOS premiere 1966) and **5. april** (First Contact Day — Cochrane's warp flight 2063).
- Selectable from the tweaks panel year-round; schedules always win on the two real dates. Preview anytime via `?force-theme=star-trek`.

## 0.7.14 — 2026-05-08

### Fixed
- **Multi-line `{# … #}` comment leaking on the dashboard above the Seneste ændring card.** Same recurring bug that has bitten this codebase seven times now — the `{# … #}` form is single-line only. Fixed the dashboard one and swept the codebase: five additional component templates (`pill.html`, `tabs.html`, `avatar.html`, `section_head.html`, `segmented.html`) had the same defect lurking — all converted to `{% comment %} … {% endcomment %}`. Verified zero remaining unclosed `{#` blocks.

## 0.7.13 — 2026-05-08

### Fixed
- **Dashboard "+ Tilføj" on Aktive opgaver now opens the form.** Previously the link only scrolled to `#priority-items-list` on the weeklog detail page; the user still had to click "Tilføj ny" to open the form. Now the dashboard link carries `?action=add`, the detail page reads it on `DOMContentLoaded`, auto-clicks the (newly id'd) `#priority-add-new-btn`, and strips the param via `history.replaceState` so a refresh doesn't re-trigger.

## 0.7.12 — 2026-05-08

### Changed
- **Header version + Seneste ændring card auto-update** via HTMX polling. Both poll every 300s — the header's `v0.7.x` reuses the existing footer-version partial endpoint, and the dashboard's "Seneste ændring" card got a new `partial-latest-change` endpoint that re-reads `CHANGELOG.md` on each tick. Same cadence as the footer link, so all three version-aware spots refresh in sync after a deploy without anyone having to reload.

## 0.7.11 — 2026-05-08

### Added
- **Export priority-item history** (FR #3). The priority history page (`/logbook/priorities/<pk>/history/`) now has the same 6-option Eksportér dropdown as the weeklog detail page: Download PDF, Download Markdown, Download HTML, Email som HTML, Email som PDF, Email som HTML + PDF. Mirrors the weeklog export plumbing (WeasyPrint for PDF, shared `pdf_styles.css`, Django email through the same `CHRONICLE_EMAIL_RECIPIENTS` list). New `apps.logbook.exports.priority` module + `templates/logbook/exports/priority_report.html`. Filenames are `opgavelog_<pk>_<title-slug>.<ext>`.

## 0.7.10 — 2026-05-08

### Added
- **Annual recurrence on theme schedules.** `ThemeSchedule.recurs_annually` (default off in admin, default on in the `/themes/` page form since most theme dates are holidays). When set, the schedule fires every year on the same month/day and the year column is just an anchor — Star Wars Day, Pirate Day and Hack Day all roll forward to 2027/2028/… without needing new rows. Year-spanning ranges (e.g. 27 dec → 3 jan) are supported. The three seeded schedules are backfilled to recurring via data migration; existing one-shot schedules are left untouched.
- New `ThemeSchedule.covers(today)` method encapsulates the date logic; `Theme.scheduled_for_today()` filters one-shots in SQL and evaluates annual matches in Python (the (month, day) match doesn't translate cleanly to SQL across year boundaries).

### Changed
- `/themes/` page lists recurring schedules without a year and tags them with an "årligt" pill; one-shot schedules continue to show full dates.

## 0.7.9 — 2026-05-08

### Changed
- **Forslag badge auto-updates** without a page reload. New partial endpoint at `/feedback/partials/nav-badge/` returns the badge as a self-polling `<span>` (`hx-get` + `hx-trigger="every 60s"` + `hx-swap="outerHTML"`); the global nav `{% include %}`s it. Same pattern as the oncall card and footer version. Wrapper stays in the DOM even at zero count so the polling loop survives transitions in either direction (open → solved or solved → reopened).

## 0.7.8 — 2026-05-08

### Added
- **Notification badge on "Forslag"** in the global nav. Shows the count of feature requests with status `open` or `in_progress`, hides at zero. Mono pill styled with `--accent` so it picks up the active theme/accent for free. New `apps.feedback.context_processors.feedback_badge` exposes `OPEN_FEEDBACK_COUNT` to every template; nav link reads it.

## 0.7.7 — 2026-05-08

### Changed
- **Banner messages now live in the database.** The Star Wars (106) and Pirate (84) rotating banner copy used to be hardcoded Python lists in two separate templatetag modules. Moved to a new `ThemeBannerMessage` model (FK to Theme + text + is_active + order + notes) so editors can curate copy without a code change/redeploy. Admin: inline editor on the Theme page, plus a standalone `ThemeBannerMessage` list with `list_editable` on `is_active` and `order`. Data migration freezes the original lists into the DB on first apply.
- New shared `{% theme_messages_json "<slug>" %}` template tag in `apps.themes.templatetags.theme_messages` replaces the per-theme `sw_messages_json` / `pirate_messages_json` tags. Both banners read from it.
- Dropped `apps/dashboard/templatetags/pirate.py` (now empty after the message list moved to the DB) and the hardcoded `SW_BANNER_MESSAGES` list from `star_wars.py`. The phrase-swap `{% sw_phrase %}` tag stays put — it's the only thing that module still ships.

## 0.7.6 — 2026-05-08

### Added
- **Pirate phrase swaps** for the dashboard text. The Star Wars theme already morphed labels via `{% sw_phrase %}` (Rådighedsvagt → Jedi på vagt, Åbne sager → Aktive missioner, etc.); the pirate theme now does the same, e.g. **Rådighedsvagt → Kaptajn på vagt**, **Åbne sager → Åbne kapringer**, **Lukkede sager → Skat hjembragt**, **Netto → Skattekiste-balance**, **Helpdesk → Skibslog-rapport**, **Bemanding → Skibsmandskab**, **Aktive opgaver → Pligter på dækket**.

### Changed
- `{% sw_phrase %}` (in the `star_wars` template-tag library, name kept for backwards compat) now takes a 4th optional `pirate` argument so all theme phrasings live in a single tag rather than a parallel `{% pirate_phrase %}`. Output adds a `<span class="sw-pirate">` that CSS reveals when `data-event="pirate"` is set.

## 0.7.5 — 2026-05-08

### Added
- **Pirate Day theme** (FR #2). New `pirate` theme + two seeded schedules: **19. september** (Talk Like a Pirate Day) and **1. oktober** (International Hack Day — pirates ≈ hackers). Light mode = parchment cream + rum-bottle teal accent, anchor brand glyph; dark mode = stormy navy + brass-gold accent, Jolly Roger ☠ glyph. Sticky banner with ~80 rotating quips mixing pirate sprog, FynBus operations, and cyber-pirate Hack Day jokes. Faint compass-rose dot pattern as page background. Footer Easter egg: `☠ X MARKER STEDET · 19/9 · 1/10 ☠`. New `{% pirate_phrase default pirate %}` template tag mirrors `{% sw_phrase %}` for pirate-sprog label swaps.
- Selectable from the tweaks panel year-round (same plumbing as Star Wars Day); schedules always win over user picks. Preview anytime via `?force-theme=pirate`.

## 0.7.4 — 2026-05-08

### Added
- **Dedicated theme management page** at `/themes/` (editor-only). Lists every active theme with its existing schedules and an inline form per theme to add new date ranges. Replaces the previous admin-only workflow — FR #1 originally asked for a real page, and digging into Django admin to plan next year's Star Wars Day was friction. Themes themselves are still created in admin (each new theme needs CSS work) but date-driven scheduling now lives in the app proper.
- "Administrér skeduler" link in the tweaks panel under the Tema picker, visible only to editors.

## 0.7.3 — 2026-05-08

### Fixed
- Editorial header buttons (Eksportér / Ny ugelog) overlapped the tweaks dropdown when the Star Wars theme was active. Caused by the starfield rule `html[data-event="star-wars"] body > * { z-index: 1 }`, whose `(0,1,1)` specificity beat `.nav-shell { z-index: 40 }`'s `(0,1,0)`, dropping the nav-shell to z-1 (same as `<main>`) and letting source order win. Added a more-specific `body > .nav-shell { z-index: 50 }` rule so the nav stays on top and its dropdown can overlay main content properly.

## 0.7.2 — 2026-05-08

### Fixed
- Tema dropdown in the tweaks panel was a one-way trap — picking "Star Wars Day" applied the theme but selecting "Auto" afterward didn't deselect it. Caused by Alpine's `x-model` not propagating writes reliably from inside the nested `x-data="{ open: false }"` scope of the tweaks dropdown (same root cause as the accent-picker bug fix in 0.2.16). Replaced the `<select>` with a button row mirroring the accent picker; each button assigns `userTheme` directly and dispatches the existing `accent-change` event after `$nextTick`. Auto / Star Wars Day toggle cleanly in both directions now.

## 0.7.1 — 2026-05-08

### Fixed
- Multi-line `{# … #}` comment above the banner include in `base.html` was leaking onto every page as visible text. Switched to `{% comment %} … {% endcomment %}`. (Sixth occurrence — already in MEMORY; clearly the fail mode is "I write comments while also writing other code and forget".) Tightening my own discipline.

## 0.7.0 — 2026-05-08

### Added
- **Generalised theme system.** New `apps.themes` app with `Theme` (slug, name, description, is_active, user_selectable) and `ThemeSchedule` (theme + start/end date + label) models. Themes are managed in Django admin; schedules define date ranges where a theme overrides user preferences globally. Seeded with the existing **Star Wars Day** theme (slug: `star-wars`) + its 2026-05-04 schedule, so the existing date-driven behaviour is preserved.
- **User theme picker** in the tweaks panel — a "Tema" dropdown listing all `user_selectable` themes plus an "Auto" default. Saved to `localStorage`. Schedules always win; user pick applies on days when nothing is scheduled. The dropdown is disabled (and shows "Aktivt: <slug> (skedule overruler dit valg)") when a schedule is currently active.
- New context processor `chronicle.context_processors.active_theme` exposes `ACTIVE_THEME` (slug) + `ACTIVE_THEMES` (selectable list). Resolution order: `?force-theme=<slug>` → `ThemeSchedule.scheduled_for_today()` → empty (lets the user's localStorage pick apply client-side).

### Changed
- `IS_STAR_WARS_DAY` is now a thin compatibility shim around `ACTIVE_THEME == "star-wars"` — covers both schedule and user-pick paths.
- Star Wars banner now renders unconditionally; CSS hides it unless `html[data-event="star-wars"]` is set. So toggling Star Wars from the tweaks panel year-round shows the full skin (banner, accent, glyph, starfield, footer egg) the same way May 4th does.
- Backward compat preserved: `?force-star-wars=1` still works as an alias for `?force-theme=star-wars`.

### Solves
- Feature request #1 ("Bring back Star Wars Theme", marked **v++**): Star Wars theme is now available year-round via the tweaks-panel "Tema" picker, with schedules overriding on May 4 (and any future date the admin adds). Originally shipped as 0.6.1; re-versioned to 0.7.0 because solving a feature request with `triggers_version_bump=True` calls for a minor bump, not a patch.

## 0.6.0 — 2026-05-08

### Added
- **Feature requests / development pipeline.** New app `apps.feedback` with a Kanban-style board at `/feedback/` (linked from the top nav as "Forslag"). Three columns: **Åbne**, **I gang**, **Løst**. Anyone authenticated can submit; editors drag-reorder within columns and across columns to change status, mark as solved (stamps `solved_by` / `solved_at`), or reopen.
- **`FeatureRequest`** model fields: title, description (urlize-aware), category (Teknisk / UI / Integration / Fejl / Andet), importance (Lav / Medium / Høj / Kritisk), status (open / in_progress / solved), `order`, `triggers_version_bump` (checkbox — flag forslag der kræver minor- eller major-bump, ikke kun patch), resolution_notes, submitted_by, solved_by, solved_at.
- **Filters on the board:** free-text query, category, and importance — combinable.
- **Detail page** with editor actions (Rediger / Markér som løst / Genåbn) and a green "Løsning" card once solved.
- **Admin** view with status / importance badges and a `v++` boolean column.
- **API** endpoints under `/api/v1/feature-requests/` — list (with filters), detail, create, PATCH, solve. `triggers_version_bump` is exposed in the serializer.
- **MCP** (mcp-chronicle 0.3.0): `chronicle_list_feature_requests`, `chronicle_submit_feature_request`, `chronicle_update_feature_request`, `chronicle_solve_feature_request` — so I can submit/track requests from a Claude Code session.

## 0.5.8 — 2026-05-07

### Changed
- URLs in description / notes / summary fields now render as clickable links. Applied via Django's built-in `|urlize` filter to: priority appearance descriptions (in weeklog rows + history timeline), priority task notes, incident description and resolution, weeklog summary, and absence notes. Links pick up the user's accent for colour and underline. So pasting `https://github.com/foo/bar/pull/42` into a per-week description now lights up as a real link without escaping HTML elsewhere.

## 0.5.7 — 2026-05-07

### Added
- **Soft-delete for priority tasks.** Both manual deletion and the merge-loser path now stamp `deleted_at` instead of nuking the row, so nothing is lost. Merged losers also get a `merged_into` FK pointing at the winner.
- New "Slet helt" button on the history page (editor-only) — soft-deletes the entire task. Companion "Gendan" button on the same page restores it.
- Search page status filter expands with **Slettede**, **Flettede**, and **Alt inkl. slettede & flettede** options. Tombstones render struck-through with a `slettet` or `flettet` pill in place of the status pill; merged ones expose a link to the winner via the title's history page.
- New `PriorityItemQuerySet` helpers: `.active()`, `.deleted()`, `.merged()`, `.tombstones()`. Default queryset still returns everything so reverse relations and admin behave normally.

### Changed
- Weeklog detail, current-week dashboard card, "Fra åbne" dialog, merge-candidate list, and the auto-close pass all filter to active items only — soft-deleted tasks disappear from week views immediately. The API's `weeklog.priority_items` payload likewise hides deleted tasks. New `deleted_at` and `merged_into_id` fields are exposed on the priority item serializer for tooling.
- The history page header surfaces tombstone state (deleted date, "Flettet ind i …" pointer) so the audit trail is obvious.

## 0.5.6 — 2026-05-07

### Changed
- Footer now uses the editorial design tokens (paper / hairline / ink scale) instead of the legacy sand palette, and picks up the user's accent: a 64×2 px rule sits over the top border in `--accent`, and the version number renders as a small `--accent-soft / --accent-ink` pill (matching the "Se historik" pill on priority rows). Switching the tweaks-panel accent now retints the footer immediately. Admin link stays as a plain text link in `--ink-3 → --ink-1` on hover.

### Removed
- "Sidste 7 dage" subheading from the dashboard incidents card — it wasn't accurate (the list is the most recent N incidents regardless of age) and the eyebrow alone is enough.

## 0.5.5 — 2026-05-07

### Changed
- Closed → open merges are now allowed. The merge rule loosened from "both must be active" to "winner must be active" — folding a closed task into an open one is supported as a way to revive prematurely-closed work without manually reopening it first. Open → closed and closed → closed still refuse with a clear error. The merge button now appears on every priority row in the search page (open or closed); the dialog header notes when the loser is closed.

## 0.5.4 — 2026-05-07

### Added
- Merge action available from the search page too. Each open task now shows a small merge icon-button in its row (next to the priority/status pills). Click → same modal as on the weeklog detail (pick a winner, confirm). Closed tasks don't show the button — only open tasks can be merged.

## 0.5.3 — 2026-05-07

### Added
- **Merge two open priority tasks.** A new icon-button on every active priority row opens a dialog listing all *other* active tasks (filterable). Pick one and confirm — the loser's appearances move to the winner (descriptions concatenated with a `— flettet —` separator on same-week conflicts), the loser's notes append to the winner under a `— flettet fra: <title> —` header, the winner's `origin_weeklog` shifts to the earlier of the two so the history page starts from the real beginning, and the loser is deleted. Winner keeps its title, priority, status, and the current week's row as-is.
- New endpoint: `POST /api/v1/priority-items/{loser_id}/merge-into/{winner_id}/` (write scope) for MCP and scripted merges.
- New `PriorityItem.merge_into(winner)` method enforces both tasks must be active and refuses self-merge.

## 0.5.2 — 2026-05-07

### Added
- "Se historik" pill next to the task title in every priority row that has appeared on more than one weeklog. Links straight to the history page; uses the accent palette so it picks up the user's tweak. Tasks that only exist on their origin week (i.e. no real history yet) still don't show the pill.

## 0.5.1 — 2026-05-07

### Fixed
- Multi-line `{# … #}` comment at the top of `priority_item_row.html` was leaking onto the weeklog detail page once for every priority appearance. Switched to `{% comment %} … {% endcomment %}`. (This is the *fifth* time this exact bug has surfaced in this codebase — already saved as a memory note, will keep watching.)

## 0.5.0 — 2026-05-07

### Added
- **Multi-week priority tasks.** Schema split into long-lived `PriorityItem` (title, priority, status, notes, origin_weeklog, last_active_at, auto_closed) plus a new `PriorityItemAppearance` row per (task, week) carrying the per-week **description** + display order. Each week's description is preserved separately so a task accumulates a true history. Existing items are backfilled: every old `PriorityItem.description` is moved to an appearance for that item's origin week.
- **Manual carry-over** via a "Fra åbne" dialog on each weeklog's priority section. The dialog lists every active task that isn't already on this week (filterable by text), and the user picks any number to bring forward. No automatic carry-over — staying in control was the point.
- **Auto-close after 6 weeks of silence.** When a current weeklog is opened, items whose `last_active_at` is older than `PriorityItem.AUTO_CLOSE_AFTER_WEEKS` (=6 weeks) are auto-closed (`status=completed, auto_closed=True`). Touching an item (status, fields, or a description edit on any of its appearances) bumps `last_active_at` and resets the clock.
- **Reopen → auto-add to current week.** Toggling a completed task back to `ongoing` (via UI or API PATCH) automatically creates an appearance on the current ISO week and resets the auto-close clock.
- **Search page** at `/logbook/priorities/search/` (linked from each weeklog's priority section as "Søg") with text + status + year filters across all tasks, open or closed.
- **History page** at `/logbook/priorities/{id}/history/` showing every weekly appearance of one task with its description — one-click from the row title.

### Changed
- Priority row URLs (`priority-item-edit/delete/row/reorder`) now key on `PriorityItemAppearance.pk` (the row in the weeklog UI) instead of `PriorityItem.pk`. Editing updates the long-lived task's title/priority/status/notes plus the current row's description; deleting only removes the row from the week (the task lives on).
- Dashboard's current-week card now lists priority appearances (with per-week description) instead of bare priority items.
- API: `weeklog.priority_items` now returns appearances with nested `priority_item` plus per-week `description`. New endpoints: `GET /api/v1/priority-items/{id}/history/` and `POST /api/v1/weeklogs/{year}/{week}/priority-items/carry/`. Reopening via PATCH automatically adds the task to the current week.
- Admin: `PriorityItem` admin shows `last_active_at`, `auto_closed`, and the appearance count. New `PriorityItemAppearance` admin for spot-checking history. The weeklog inline shows appearances now (not raw items).

## 0.4.0 — 2026-05-01

### Added
- **API keys + JSON API.** Per-user API keys with two scopes (`read`, `write`). New `apps.accounts.APIKey` model stores SHA-256 hashes only — raw keys (`fbc_R_…` / `fbc_W_…`) are shown exactly once at creation/reroll, then never again. Bearer-token auth via the new `@api_auth(scope=...)` decorator (`apps/accounts/api_auth.py`).
- **`apps.api`** — new app at `/api/v1/` with read endpoints (`weeklogs/`, `weeklogs/current/`, `weeklogs/{year}/{week}/`, `incidents/`, `oncall/current/`, `helpdesk/data/`, `changelog/latest/`) and write endpoints (`weeklogs/{year}/{week}/priority-items/`, `priority-items/{id}/`, `weeklogs/{year}/{week}/incidents/`).
- **Self-service UI** at `/accounts/api-keys/` (linked from the user dropdown) — list, generate, reroll, revoke. New keys show in a one-time copy-to-clipboard reveal.
- **Admin** registration of `APIKey` with scope/last-used columns, bulk-revoke action, and read-only hash. Adding via admin is disabled — must be minted through the self-service page or the new `manage.py mint_api_key <username> --scope=read --label=...` command.

## 0.3.4 — 2026-05-01

### Added
- New "Saber" accent in the tweaks panel — saturated lightsaber red, derived from the May 4th Sith dark-mode skin so it's available year-round. Light mode picks `oklch(0.55 0.18 25)`, dark mode keeps the brighter Sith `oklch(0.62 0.20 25)`. Sits as the fourth pill in the accent picker after Guld / Sage / Blæk.

## 0.3.3 — 2026-05-01

### Fixed
- Star Wars banner was leaking Alpine code as visible text under the nav. The 106-message JSON sat inside `x-data="..."`, and the first straight `"` character in any message terminated the HTML attribute early, dumping the rest of the Alpine initialiser into the document body. Moved the messages into a `<script type="application/json" id="sw-banner-messages">` tag and have Alpine read them via `JSON.parse(...textContent)` on init — quotes are no longer in attribute scope, so the leak is gone.

## 0.3.2 — 2026-05-01

### Added
- Rotating banner messages on Star Wars Day. The "4. maj" strip now picks from 106 FynBus × Star Wars one-liners and cycles every 2 minutes ("Servere på Alderaan offline", "Wookieer anmoder om fuld adgang til Docunote", "Passagerer på Tatooine-ruten siger det er for støvet", "FynBus kom kun på andenpladsen i Boonta Eve Podrace", "Greedo skød først — pull request afvist", …). Initial message is random so reloads feel fresh; messages crossfade with a 220 ms opacity transition. List lives in `apps/dashboard/templatetags/star_wars.py` (`SW_BANNER_MESSAGES`) — easy to extend for next year.

## 0.3.1 — 2026-05-01

### Added
- Star Wars Day phrase swaps. New `{% sw_phrase %}` template tag (`apps/dashboard/templatetags/star_wars.py`) renders three nested spans (default/rebel/sith); CSS shows the right one based on `data-event` + `.dark`. Wired into the dashboard's chart titles + eyebrows, the four KPI eyebrows, the on-call card, the current-week card's section eyebrows, the incidents card, and the live/synkroniseret line.
  - Light/Rebel examples: "Lukkede sager → Fuldførte missioner", "Hændelser → Indsatser", "Rådighedsvagt → Jedi på vagt", "Live → Holocron"
  - Dark/Sith examples: "Lukkede sager → Rebel agents fanget", "Netto → Imperial kontrol", "Hændelser → Sith-aktioner", "Rådighedsvagt → Inkvisitor på vagt", "Aktive opgaver → Imperial direktiver"

## 0.3.0 — 2026-05-01

### Added
- May 4th Star Wars Day skin. On 2026-05-04 (Europe/Copenhagen), the dashboard layers a one-day theme over the editorial design system: Rebel-orange accent in light mode, Sith-red accent in dark mode, a thin sticky banner ("⚔ 4. maj · Må Kraften være med dig.") under the nav, a faint starfield behind the page, a brand-mark glyph swap (✦ Rebel / ⌖ Imperial), and a small mono Easter egg in the footer. Implemented as a single `IS_STAR_WARS_DAY` context processor that flips `data-event="star-wars"` on `<html>`; the skin reuses the existing accent token plumbing so pills, focus rings, the on-call avatar, and the open-tickets chart line all retint automatically.
- Preview hatch: `?force-star-wars=1` on any URL turns the skin on for the current request, useful for screenshots and pre-flight checks. The skin disappears on its own at midnight on May 5th — no cleanup PR needed.

## 0.2.22 — 2026-05-01

### Fixed
- Density segmented control's "Dashboard" button overflowed past the tweaks dropdown: flex items don't shrink below their content min-width by default, so the longest label dictated the button size. Added `min-width: 0`, `white-space: nowrap`, and `text-align: center` to `.segmented-btn` so `flex-1` distributes equal widths regardless of label, and bumped the dropdown from 240 px to 280 px to give the three-mode control room to breathe.

## 0.2.21 — 2026-05-01

### Changed
- Dashboard density mode now puts the two charts side-by-side. Wrapped the flow row + tasks row in a new `.js-dashboard-main` container that flips to a 2-column grid only when `data-density="dashboard"` (passthrough flex column otherwise, so Komfort/Kompakt are unchanged). The flow chart sits left, the open-tickets chart sits right; below 1024 px width the layout falls back to a single column.

## 0.2.20 — 2026-05-01

### Changed
- Kompakt density mode now hides the "Seneste ændring" changelog card too (previously only Dashboard mode hid it). The card carries a new `js-dashboard-changelog` hook so it's distinct from the incidents card, which still shows in Kompakt.
- Kompakt mode also collapses both two-column grid rows to a single column (matching what Dashboard mode already does). The rail and the incidents card now span full width instead of sitting next to an empty column where the chart used to live, so incidents lands visually higher up the page.

## 0.2.19 — 2026-05-01

### Fixed
- Three multi-line `{# … #}` comments (one in `nav.html`'s tweaks dropdown, two in `dashboard/index.html`) leaked onto the rendered page as visible text — Django's `{# … #}` syntax is single-line only. Switched to `{% comment %} … {% endcomment %}` for all three. The "Three modes: …" block above the density segmented control and the row-level hook documentation in the dashboard are no longer visible.

## 0.2.18 — 2026-05-01

### Changed
- Density toggle in the tweaks panel is now a 3-mode segmented control: **Komfort** (default, all sections visible), **Kompakt** (denser spacing tokens *and* both chart cards hidden), and **Dashboard** (only the editorial header, KPI strip, and chart cards — side rail, changelog, and incidents are hidden).
- Dashboard sections carry stable hook classes (`js-dashboard-graphs`, `js-dashboard-rail`, `js-dashboard-extras`, plus row-level `js-dashboard-flow-row` / `js-dashboard-tasks-row`) so each density mode hides the right pieces purely via CSS — no template branching, no HTMX refetches, instant toggle.
- Density state migration: any legacy `localStorage.density` value other than the three known modes is coerced back to `comfortable` on load, and the `<html>` `data-density` binding now generalises to all three values.

## 0.2.17 — 2026-05-01

### Fixed
- Open-tickets chart line was rendering near-navy in dark mode (and similarly miscoloured in light mode for any non-default accent). Newer Chromium preserves the authored `oklch()` form when serialising `getComputedStyle().color`, and my probe was running a generic digit-extraction regex over the result — so for `oklch(0.80 0.11 80)` it picked up `H=80` as `B=80` and produced rgb(0,0,80). Replace the regex with an explicit OKLCH → sRGB converter that handles `rgb()`, `oklch()`, and `#rrggbb` outputs cleanly. Same fix applied to the flow chart's "Nye sager" area-fill probe.

## 0.2.16 — 2026-05-01

### Fixed
- Charts didn't actually retint when changing the accent in the tweaks panel. The accent buttons live inside a nested Alpine `x-data` scope so the html-level `$watch('accent', ...)` was unreliable. Each accent button (and the dark-mode toggle) now explicitly fires the `accent-change` CustomEvent on `window` after a `$nextTick`, so the chart listeners receive it regardless of whether the parent watcher picked up the inner-scope write.

## 0.2.15 — 2026-05-01

### Changed
- Flow chart's "Nye sager" area fill now tracks the tweaks-panel accent (the wash under the curve subtly retints with gold/sage/terracotta/ink). Line colours remain `--chart-info` blue and `--chart-good` dashed-sage so the two series stay distinct — only the gradient fill picks up `--accent`. Hooked into the existing `accent-change` event so the tint updates instantly.

## 0.2.14 — 2026-05-01

### Changed
- Broaden the reach of the tweaks-panel accent presets so changing gold → sage → terracotta → ink visibly retints the page. Three targeted moves per the UI-expert review (full Option 2 + bounded Option 1):
  - Editorial header eyebrow now leads with a 24×2 px accent rule
  - KPI netto card's neutral "·0" pill swaps to `--accent-soft / --accent-ink` (▲/▼ states stay green/red so the sign semantic is preserved)
  - "Åbne sager — udvikling" chart (single series) now probes `--accent` for its line + gradient + point colours; multi-series flow chart keeps its independent `--chart-info / --chart-good` palette so legibility holds
- Wire an `accent-change` custom event from the root `<html>` Alpine watcher (fires on accent or dark-mode change) so the open-tickets chart re-tints instantly without waiting for the 60 s HTMX refresh

## 0.2.13 — 2026-05-01

### Added
- 12U / 26U / 12M segmented control on the "Åbne sager — udvikling" chart, mirroring the flow chart. Selection persists in `localStorage` (key: `openChartWindow`) and survives the 60 s HTMX refresh; the eyebrow ("Helpdesk · 12 uger") and the Laveste / Nuværende / Højeste stats below the chart all update to reflect the current window.

## 0.2.12 — 2026-05-01

### Fixed
- "+ Ny ugelog" button on `/logbook/` (and other legacy templates) was rendering as a tall narrow box with the icon stacked above the text. The standalone `.btn-primary`, `.btn-ghost`, and `.btn-danger` classes weren't inheriting the `inline-flex` layout from `.btn` the way `.btn-secondary` and `.btn-outline` already did. They now `@apply btn` so any legacy template using only the modifier class (e.g. `class="btn-primary"`) renders correctly.
- Eyebrow above the helpdesk flow chart was hardcoded to `Helpdesk · 12 uger` even when 26U or 12M was selected. Lifted the segmented-control's Alpine state to the chart card and bound the eyebrow's window label to it; it now reads `12 uger`, `26 uger`, or `12 måneder` according to the active selection.

## 0.2.11 — 2026-05-01

### Added
- 12U / 26U / 12M segmented control on the helpdesk flow chart now actually changes the visible window (last 12 / 26 / 52 weeks). Selection persists in `localStorage` and survives the chart's 60-second HTMX refresh — the active partial subscribes via a `flow-chart-window` custom event so the chart updates in place instead of re-fetching.

## 0.2.10 — 2026-05-01

### Removed
- "Rådighedsvagt: {name}" segment from the dashboard editorial header sub-line. The on-call name already appears in the dedicated card on the right rail, so the duplication was redundant. Also drops the now-unused `oncall` lookup from `DashboardView` — the on-call card pulls its own data via the partial view.

## 0.2.9 — 2026-04-30

### Changed
- "Aktive opgaver" now sits at the bottom of the current-week card, after Bemanding, instead of just below the summary
- "Aktive opgaver" lists every priority item regardless of status (was filtered to `ongoing`/`blocked` only). Completed items render struck-through with reduced opacity and a green status pill so they read as "done" context rather than active work; raised the cap from 5 to 8 rows.

## 0.2.8 — 2026-04-30

### Changed
- Re-balance the dashboard main row from `1.7fr / 1fr` to `1.25fr / 1fr`. The Rådighedsvagt + Aktuel ugelog rail was much narrower than the helpdesk flow chart, which had room to spare; the rail cards now have noticeably more breathing room while the chart still gets the wider half.

## 0.2.7 — 2026-04-30

### Added
- "Tilføj" link in the "Aktive opgaver" section of the dashboard's current-week card. Clicking it routes to the weeklog detail page anchored on `#priority-items-list` so the user lands directly on the priorities section to add a new one. The button only appears for editors.
- App version (`v0.2.7`) appended to the dashboard editorial header eyebrow next to the date, so it's always visible at a glance.

### Changed
- "Aktive opgaver" section now always renders on the current-week card (with an "Ingen aktive opgaver." placeholder when empty), so the "Tilføj" button is reachable even when there are no priorities yet.

## 0.2.6 — 2026-04-30

### Added
- "Seneste ændring" card on the dashboard pulls the most recent CHANGELOG.md entry and renders it under the helpdesk chart, so the previously empty space below "Åbne sager — udvikling" now shows what shipped most recently. Includes a "Se alle" link to the full changelog.

## 0.2.5 — 2026-04-30

### Removed
- "Opgave Tidslinje" Gantt-style card pulled from the bottom of the dashboard. The `dashboard:task-timeline-partial` endpoint and its API still exist for any external use, but it no longer renders on the kontrolpanel.

## 0.2.4 — 2026-04-30

### Removed
- "Opgaver" entry pulled from the top nav and mobile menu. The `/tasks/` URLs and views remain reachable directly; only the navigation surface is gone.

## 0.2.3 — 2026-04-30

### Fixed
- Helpdesk flow chart was rendering as black + dark-red lines instead of blue + sage. cssnano minifies `rgb(r, g, b)` declarations to `#rrggbb` during the Tailwind build, so the JS `rgbVar` helper that was looking only for decimal digits fell through to its `[0,0,0]` fallback. Updated to accept both `rgb()` and `#rrggbb` forms.
- Multi-line `{# … #}` comment at the top of `helpdesk_flow_chart.html` was leaking onto the page as visible text — Django comments are single-line only. Switched to `{% comment %} … {% endcomment %}`.

## 0.2.2 — 2026-04-30

### Fixed
- Helpdesk flow chart's "Nye" and "Lukket" series rendered as nearly identical blue lines because the editorial `--good` token has very low chroma (0.06), so converted to RGB it sat next to `--info`. Charts now use a separate higher-chroma palette (`--chart-info`, `--chart-good`, `--chart-accent` defined in light/dark variants) and "Lukkede sager" gets a dashed line so the two series stay distinct even side-by-side. Legend swatches updated to match.
- Chart tooltips were rendering as Chart.js's default near-black box because the `display:none` color probe sometimes returned an empty string and `rgba()` fell back to `rgba(0,0,0,1)`. Tooltip surface, ink, border, and grid colors are now picked from explicit per-mode palettes — no probe needed — so contrast is reliable in both light and dark mode.

## 0.2.1 — 2026-04-30

### Removed
- Drop the non-functional "Søg ⌘K" search affordance from the top nav. It was a visual element from the design handoff with no backend behind it; pruned until a real search lands.

## 0.2.0 — 2026-04-30

Editorial redesign milestone. Rolls up every change from the 0.1.61 → 0.1.64 series — new OKLCH design tokens, Inter Tight + Instrument Serif + JetBrains Mono fonts, sticky blurred nav with brand mark and tweaks panel, editorial dashboard and weeklog headers, restyled rows and pills, density/accent toggles, retuned dark mode, and Chart.js color compatibility fixes — under a single minor version bump to mark the new design system as the baseline.

## 0.1.64 — 2026-04-30

### Fixed
- Dashboard header sub-line was showing the "Alle løst" pill from the incidents card instead of the intended "N hændelser denne uge" + on-call name; the broken `hx-select` indirection has been removed and `incident_count_week` + `oncall` are now rendered server-side from `DashboardView` context
- Stop the helpdesk-chart card from stretching to the height of the (much taller) incidents card by adding `items-start` to their grid row

## 0.1.63 — 2026-04-30

### Fixed
- Helpdesk and flow charts now render again. Edge's CanvasGradient color-stop parser doesn't accept `oklch(L C H / a)` either (after the previous fix removed the invalid `oklch(...)22` hex-alpha concatenation), so all chart colors are now probed through a hidden `<span>` to resolve them to RGB before being passed to `addColorStop` / borderColor / tooltip styles. This works in every browser that supports `getComputedStyle`.

### Changed
- Greeting in the dashboard editorial header now picks `Godmorgen` / `Goddag` / `Godaften` / `Godnat` from the local clock instead of being hardcoded to "Godmorgen".

### Removed
- Drop the leaky `\\U\\g\\e` escape pattern from the dashboard eyebrow `{% now %}` tag — Django template literals don't honor Python-style escaping, so the literal "Uge" now lives outside the format string.

## 0.1.62 — 2026-04-30

### Changed
- Lighten dark-mode surface lightness so the new editorial palette is more comfortable: `--paper` 0.16 → 0.225, `--surface-1` 0.205 → 0.275, `--surface-2` 0.185 → 0.250 (still slate-cool, but in Linear/Notion territory rather than near-black)
- Soften dark-mode `--ink-1` from 0.97 to 0.93 so headings no longer glare on the lighter bg, with matching nudges to `--ink-2/4/5` to preserve the contrast steps
- Lift dark-mode chip `--*-soft` backgrounds (0.30–0.32 → 0.34–0.36) and `--*-ink` text (0.85 → 0.86–0.88) so pills read as elevated against the new paper
- Reduce dark-mode card/popover shadow alphas (0.40/0.50 → 0.25/0.38) to suit the lighter surfaces

## 0.1.61 — 2026-04-30

### Changed
- Implement editorial Chronicle redesign from `chronicle.zip` design handoff: switch to Inter Tight + Instrument Serif + JetBrains Mono fonts, slate-cool OKLCH ink palette, normalized semantic color tokens (`--paper`, `--surface-1`, `--ink-1…5`, `--accent`, `--good`, `--warn`, `--bad`, `--info`)
- Rebuild navigation shell as sticky blurred top bar with brand mark, search affordance, theme toggle, density/accent tweaks panel, bell, and gradient-avatar user dropdown
- Rebuild dashboard with editorial header band ("Godmorgen, {name}. her er ugen."), live sync indicator, 4-card KPI strip, 1.7fr/1fr grid (flow chart + on-call/current-week rail), incidents list with severity rail
- Rebuild weeklog detail with breadcrumb, 64px Instrument Serif H1, KPI strip, pull-quote summary card, restyled priority/absence/incident rows (drag handle, custom check, gradient avatars, collapsible incidents)
- Recolor Chart.js helpdesk charts to use the new CSS-variable palette so they react to dark mode and accent changes
- Add `data-density="compact"` and `data-accent="sage|terracotta|ink"` modifiers wired via Alpine + localStorage

### Added
- `templates/components/{pill,avatar,kpi_card,section_head,segmented,tabs}.html` reusable partials
- `slideIn` and `pulseGlow` keyframes for inline-edit animations and live sync dot

## 0.1.60 — 2026-04-11

### Changed
- Apply Notion/Linear/Cal.com design refinements: multi-layer shadows, whisper borders, tighter heading typography, improved metric cards, badge micro-tracking
- Remove automatic version bumping from CI pipeline

## 0.1.57 — 2026-04-03

### Fixed
- Restore `beforeend` swap for incident create
- Disable localization on incident `occurred_at` field for datetime-local compatibility
- Correct datetime format for incident form to prevent data loss on edit
- Correct HTMX target for incident edit form submission

## 0.1.55 — 2026-03-26

### Added
- 56-week view option to on-call calendar

## 0.1.53 — 2026-03-16

### Fixed
- Add `run_scheduler` management command to sync service

## 0.1.50 — 2026-03-06

### Added
- Manual sync button for ServiceDesk stats on kontrolpanel
- Color-coded state segments in task timeline chart

### Changed
- Replace APScheduler with simple sleep loop for ServiceDesk sync

### Fixed
- Missing closing `>` on priority item form div tag

## 0.1.45 — 2026-03-05

### Added
- Opgaver (Tasks) feature with full task management, timeline chart, assignees, and approvers
- Auto-refresh oncall week cards via HTMX polling

### Fixed
- Task timeline x-axis anchored to oldest task start date
- Task timeline chart rewrite with production logging
- Task approvers changed from M2M users to free-text field with fixed checkbox choices
- Auto-scroll and focus form when adding priority items
- Workflow concurrency to prevent Docker Hub rate limits

## 0.1.40 — 2026-03-02

### Fixed
- Add `default=""` to meeting fields to prevent NOT NULL constraint error

## 0.1.38 — 2026-02-22

### Added
- Weekly average stats to all exports (PDF, Markdown, HTML, email)

## 0.1.28 — 2026-02-21

### Added
- Inline meeting minutes with pill-based attendees and live markdown preview
- Drag-and-drop reordering for priority items
- Microsoft Graph API email backend
- Viewer read-only user group with RBAC
- Login/logout tracking with read-only admin
- Grouped bar chart for new vs closed tickets on dashboard
- New vs closed bar chart in exports
- Matplotlib helpdesk trend chart in exports

### Fixed
- HTML export and email chart scaling
- Docs dark mode, added Graph email guide in Danish
- Outlook web paste compatibility (inline styles, table layouts, bgcolor)
- Export improvements: card-style rows, rounded corners, visible pills, stats spacing

## 0.1.25 — 2026-02-13

### Changed
- Rename Fravær to Bemanding and add Arbejder hjemme option

## 0.1.23 — 2026-02-11

### Added
- On-call duty (rådighedsvagt) planning feature

### Fixed
- Stack stat cards vertically in dashboard right column

## 0.1.21 — 2026-02-10

### Fixed
- Show full descriptions in PDF/Markdown/HTML exports

## 0.1.18 — 2026-02-09

### Added
- Auto-updating version with date in footer via HTMX
- Danish weekday range on dashboard absence entries
- "Flex fri" absence type

### Fixed
- Absence edit not saving and dates not populating

## 0.1.15 — 2026-02-05

### Added
- HTML export format

### Fixed
- Priority item edit

## 0.1.13 — 2026-02-03

### Added
- ServiceDesk Plus integration with auto-sync

### Fixed
- Dynamic version in footer and dashboard card height
- Documentation for ServiceDesk integration

## 0.1.8 — 2026-02-02

### Added
- Favicon (calendar/weekly log design)
- Improved markdown export to match PDF structure

### Fixed
- Dark mode support for form fields
- Cancel button row restoration when editing
- OOB swap to close form after creating new entry
- Docker image to include docs/ and LICENSE

## 0.1.0 — 2026-02-01

### Added
- Initial release of FynBus Chronicle
- Weekly IT logbook with helpdesk statistics tracking
- Priority items, absences, and incident management
- PDF and Markdown export
- Docker containerization with multi-stage build
- SQLite-only deployment option
- Django admin with staff management
