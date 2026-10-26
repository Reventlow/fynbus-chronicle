# Brugervejledning — FynBus Chronicle

Chronicle er IT-afdelingens ugelog: her planlægger, registrerer og følger vi ugens arbejde, helpdesk-tal, hændelser, sårbarheder og rådighedsvagt. Denne vejledning gælder version 1.1.

## Indhold

1. [Log ind](#log-ind)
2. [Brugerroller](#brugerroller)
3. [Navigation](#navigation)
4. [Kontrolpanel](#kontrolpanel)
5. [Ugelogs](#ugelogs)
6. [Opgavesøgning](#opgavesøgning)
7. [Vagtkalender](#vagtkalender)
8. [Statistik](#statistik)
9. [Sårbarheder (CVE'er)](#sårbarheder-cveer)
10. [Forslag](#forslag)
11. [Eksporter rapporter](#eksporter-rapporter)
12. [Rapporter](#rapporter)
13. [Notifikationer](#notifikationer)
14. [API-nøgler](#api-nøgler)
15. [Udseende og temaer](#udseende-og-temaer)

---

## Log ind

### Standard login

1. Gå til login-siden: `/accounts/login/`
2. Indtast dit brugernavn og adgangskode
3. Klik på "Log ind"

### Office 365 login (hvis aktiveret)

1. Klik på "Office 365" knappen
2. Log ind med din FynBus Office 365-konto
3. Godkend adgang første gang

---

## Brugerroller

FynBus Chronicle har to brugerroller:

### Redaktør (standard)

Alle brugere er redaktører som standard og har fuld adgang til at:

- Oprette, redigere og slette ugelogs
- Tilføje og administrere prioriterede opgaver, fravær og hændelser
- Redigere mødereferater
- Eksportere rapporter (PDF, Markdown, HTML, email)
- Tage, frigive og omfordele vagter i vagtkalenderen (inkl. deling af en uge mellem flere personer)
- Sortere prioriterede opgaver via træk-og-slip

### Læser (Viewer)

Brugere der er tilføjet til gruppen "Viewer" har kun læseadgang:

- **Kan se**: Kontrolpanel, ugelogs, vagtkalender, statistik, forslag, rapporter og dokumentation
- **Kan ikke**: Oprette, redigere, slette, sortere eller eksportere noget

Læsere ser ikke nogen handlingsknapper (Tilføj, Rediger, Slet, Eksporter osv.). Forsøg på at tilgå skrivebeskyttede funktioner direkte via URL returnerer en fejlside.

> **Bemærk:** Administratorer (staff-brugere) har altid fuld adgang uanset gruppemedlemskab.

Kontakt din administrator for at ændre din brugerrolle.

---

## Navigation

**Sidemenuen** til venstre fører til Kontrolpanel, Ugelog, Rådighedsvagt, Forslag, Rapporter, Statistik og Dokumentation. Tallet ved *Forslag* er antallet af åbne og igangværende forslag.

- Nederst står **Rådighedsvagt nu**: hvem der har vagten, til hvornår, og hvem der er den næste.
- I bunden finder du din profil (API-nøgler, Admin, Log ud), **tandhjulet** med indstillinger og knappen, der **klapper menuen sammen** til ikoner. Valget huskes i din browser.

**Bjælken øverst** viser, hvor du er (fx *Ugelogs / 2026 / Uge 42*), og har:
- **Søg i opgaver**: søger i de prioriterede opgaver på tværs af alle uger. Tryk **Ctrl+K** (⌘K på Mac) for at hoppe direkte til feltet.
- **Klokken** med dine notifikationer.

På mobil er sidemenuen skjult: tryk på menuknappen øverst til venstre for at få menu og indstillinger frem.

---

## Kontrolpanel

Kontrolpanelet viser ugen lige nu. Alt opdaterer sig selv, mens siden er åben: overskriften og kortene hentes igen hvert minut, nøgletallene hvert 30. sekund.

### Overskrift

Overskriften siger, hvor mange sager der er åbne, og om det er flere eller færre end ved udgangen af sidste uge — fx *"28 åbne sager, én flere end sidste uge."* Linjen under viser:
- **Live · synk kl …**: hvornår sagerne sidst blev hentet fra ServiceDesk.
- Ugens hændelser og hvor mange der er kritiske.
- Ugeloggen for ugen og antallet af opgaver på den.

Stopper synkroniseringen med ServiceDesk, skifter linjen til **"Synk med ServiceDesk fejlede"**, overskriften siger hvor gamle tallene er, og nøgletallene markeres **forældet**. Knappen **Prøv igen** starter en synkronisering med det samme.

### Nøgletal

Fire kort: åbne sager, nye og lukkede sager i ugen og nettoændringen. Pilen på *Åbne sager* starter en synkronisering.

### 01 Nu

- **Hændelser** fra de sidste 30 dage plus alle uløste, nyeste først. Den farvede kant og P1/P2/P3 viser alvoren (P1 kritisk, P2 høj, P3 lavere), og hver linje siger **Løst** eller **Uløst**. *Vis ældre* folder ældre, løste hændelser ud.
- **Aktuel ugelog**: ugens sammendrag, fravær og *alle* ugens opgaver med status. Afsluttede opgaver er nedtonede.
- **Rådighedsvagt** vises kun her, når sidemenuen ikke viser den: på mobil og med menuen klappet sammen.
- **Sårbarheder**: CVE'er, der er oprettet eller ændret de sidste 30 dage — dem der patches først, så de identificerede, til sidst de løste. Overskriften tæller alle åbne CVE'er og dem, der er løst i perioden. *Se alle CVE'er* åbner listen.

### 02 Åbne sager

- **Tekniker**: hvor mange åbne sager hver tekniker har; *Ikke tildelt* er grå.
- **Kategori**: åbne sager fordelt på ServiceDesk-kategori.
- **Liggetid**: hvor længe de åbne sager har ligget, i de samme syv grupper som ugerapporten, og hvor mange der har ligget i over 1 måned.
- **Nyeste uløste** og **Ældste uløste**: de seks nyeste og de seks ældste åbne sager med nummer, emne, tekniker og alder. Klik på en linje for at åbne sagen i ServiceDesk.

### 03 Udvikling

To grafer: nye mod lukkede sager pr. uge og antallet af åbne sager ved ugens udgang. Vælg 12 uger, 26 uger eller 12 måneder over hver graf.

Nederst står den **seneste ændring** i Chronicle; klik for at se hele ændringsloggen.

### Densitet

Under tandhjulet → **Densitet**:
- **Komfort** viser alt.
- **Kompakt** er tættere og skjuler graferne og afsnittet *Åbne sager*.
- **Dashboard** viser kun nøgletal og grafer — godt til en skærm på væggen.

---

## Ugelogs

### Oversigt

**Ugelog** i menuen viser alle uger som en liste: uge, sammendrag og en linje med antal opgaver, hændelser og helpdesk-tal. Den aktuelle uge er markeret. Filtrér på år i overskriften, eller klik på en uge for at åbne den.

### Opret ny ugelog

1. Klik **Ny ugelog**
2. Udfyld:
   - **År og uge**: udfyldes automatisk med den aktuelle uge
   - **Helpdesk statistik**: nye, lukkede og åbne sager
   - **Åbne sager fordelt på liggetid**: under 1 uge, 1–2 uger, 2 uger–1 måned, 1–3 måneder, 3–6 måneder, 6–12 måneder og over 12 måneder. Felterne udfyldes automatisk af ServiceDesk-synkroniseringen; udfylder du dem i hånden, skal de summe til antallet af åbne sager (eller stå på 0)
   - **Ugeoversigt**: kort beskrivelse af ugens aktiviteter
3. Klik **Opret ugelog**

### Ugeloggen

Adressen på en ugelog er `/logbook/<år>/<uge>/` — fx <https://chronicle.fynbus.net/logbook/2026/34/>. Ældre links med et id (`/logbook/39/`) sender dig videre til den rigtige uge.

Øverst står ugens helpdesk-tal med forrige uges tal under hvert. Derunder: klarmelding, sammendrag, mødereferat, prioriterede opgaver (*N åbne af M*), fravær og hændelser (*N denne uge · M kritisk*).

### Klarmelding — "ikke mere at tilføje"

Når du er færdig med at skrive på ugens log, kan du melde klar, så den
der afslutter ugen kan se, at du ikke har mere at tilføje.

1. Åbn ugeloggen og find kortet **Klarmelding** (øverst, under
   statistikken)
2. Klik **"Jeg har ikke mere til denne uge"**
3. Dit navn vises nu som en grøn markering på kortet — hold musen over
   for at se tidspunktet

Kommer du alligevel i tanke om mere, kan du klikke **"Fortryd
klarmelding"**, tilføje dine punkter og melde klar igen. Klarmeldingen
er personlig — den påvirker ikke dine kollegers markeringer.

### Prioriterede opgaver

En prioriteret opgave lever på tværs af uger: den lægges på den uge, den opstår, og kan føres videre med **Fra åbne**, som viser alle åbne opgaver fra tidligere uger. Afsluttede opgaver vises nedtonede. En opgave, der ikke er beskrevet i 6 uger, lukkes automatisk.

**Billeder i beskrivelsen**

Sæt et skærmbillede ind med **Ctrl+V** (eller træk en billedfil ind) i beskrivelsen på en opgave eller et forslag. Billedet uploades med det samme (højst 15 MB), og en forhåndsvisning under feltet viser resultatet, hvor du kan justere billedets størrelse. Billederne kommer med i PDF, HTML og email.

**Markdown i beskrivelser**

Beskrivelsen på en prioriteret opgave skrives i Markdown: `**fed**`, punkt- og
nummerlister, tabeller, citater, links og kode. En kodeblok laves med tre backticks og
gerne et sprog — ` ```bash `, ` ```python `, ` ```sql ` — så bliver den farvelagt. På
websiden får hver kodeblok en "Kopiér"-knap, når du holder musen over den.

Formateringen følger med i alle eksporter: PDF, HTML, email og Markdown-filen.

**Tilføj opgave**
1. Klik "Tilføj" ved Prioriterede opgaver
2. Udfyld:
   - Titel
   - Prioritet (Høj/Medium/Lav)
   - Status (Ikke startet/Igangværende/Blokeret/Afsluttet)
   - Beskrivelse
3. Klik "Tilføj"

**Flet opgaver**

Er den samme opgave oprettet to gange, flettes den ene ind i den anden med flet-ikonet på opgaven: vælg den opgave, den skal flettes ind i. Ugerne og beskrivelserne flyttes over, og den flettede opgave peger videre til den, den blev flettet ind i.

**Rediger opgave**
- Klik på blyant-ikonet
- Foretag ændringer
- Klik "Gem"

**Slet opgave**
- Klik på skraldespand-ikonet
- Bekræft sletning

### Fravær

**Registrer fravær**
1. Klik "Tilføj" ved Fravær
2. Udfyld:
   - Medarbejder
   - Type (Ferie/Sygdom/Kursus/Møde/Andet)
   - Fra dato og Til dato
   - Noter (valgfrit)
3. Klik "Tilføj"

### Hændelser

Brug hændelser til at dokumentere:
- Sikkerhedshændelser
- Systemfejl
- Netværksproblemer
- Databrud

**Registrer hændelse**
1. Klik "Tilføj" ved Hændelser
2. Udfyld:
   - Titel
   - Type og alvorlighed
   - Tidspunkt
   - Beskrivelse
3. Marker som løst når relevant
4. Tilføj løsningsbeskrivelse

---

---

## Opgavesøgning

**Ugelog → Opgavesøgning** (eller feltet *Søg i opgaver* øverst) søger i alle prioriterede opgaver på tværs af uger: titel, beskrivelse og ugebeskrivelser. Filtrér på status (åbne, lukkede, slettede, flettede) og år.

- Klik på en opgave for at se dens **historik**: alle uger, den har været med i, og hvad der blev skrevet hver uge. Historikken kan eksporteres og sendes som email ligesom ugeloggen.
- **Genåbn en afsluttet opgave** med ↺-knappen: den sættes til igangværende og lægges på indeværende uge. Du bliver stående i søgningen med de filtre, du havde.

---

## Vagtkalender

Vagtkalenderen (Rådighedsvagt) viser hvem der har rådighedsvagt uge for uge.

### Tag og frigiv en vagt

- **Tag vagt**: Klik "Tag vagt" på en ledig uge for at tage den selv.
- **Frigiv**: Klik "Frigiv" på din egen uge. Frigiver du midt i en uge, bevares dine allerede dækkede dage i historikken.

### Skift vagt (dropdown)

Klik på blyanten på et ugekort for at åbne vagtformularen:

- **Medarbejder**: Vælg hvem der skal have vagten — eller "— Ledig —" for at frigive den.
- **Fra dato**: Mandag betyder hele ugen. Vælg en senere dato for at dele ugen, fx hvis en kollega overtager fra torsdag.
- **Fra kl.** (valgfrit): Angiv et klokkeslæt hvis overdragelsen sker midt på dagen, fx kl. 14:00.
- **Noter**: Valgfri note der vises på ugekortet.

En delt uge vises med én linje pr. periode, fx "Anna · ma–on" og "Bo · on 14:00–sø". Kontrolpanelet, API'et og eksporterede rapporter viser altid den person der dækker lige nu.

> **Bemærk:** Vælger du en dato der allerede er passeret i indeværende uge, omskrives den registrerede dækning bagud. Ændringer kan ikke angives mere præcist end pr. minut.

### Eksempel: Overtag vagten nu

Peter har vagten i denne uge, og du overtager den fra nu af:

1. Find kortet for **denne uge** i kalenderen og klik på **blyanten**.
2. **Medarbejder**: Vælg dig selv.
3. **Fra dato**: Dagens dato (udfyldt på forhånd).
4. **Fra kl.**: Tidspunktet for overdragelsen, fx `13:50`. Lader du feltet stå tomt, gælder skiftet fra midnat — så tæller hele dagen som din.
5. Klik **Gem**.

Én handling klarer begge dele: Peters dækning afsluttes på tidspunktet, din begynder, og begge dele står i historikken ("Peter → Gorm · gældende fra fr 13:50").

**Hvis ugen står som ledig** (ingen har taget den), findes Peters hidtidige dækning ikke i systemet. Registrér den i to trin: tildel først Peter fra **mandag** (hele ugen), og tildel derefter dig selv fra dags dato og klokkeslæt. Begge trin logges.

### Historik og audit-log

Uger med ændringer viser et lille ur-ikon på ugekortet. Klik på det for at se panelet med:

- **Dækning**: Hvem der havde ansvaret hvilke dage (og klokkeslæt).
- **Ændringer**: Hvem der ændrede vagten, hvornår, og fra/til hvem.

Ændringer før version 0.8.0 er ikke registreret.

### Tidligere uger

Brug knapperne **Tidligere** (ingen, 4 eller 13 uger) og **Fremad** (13 eller 56 uger) i overskriften til at vælge, hvor mange uger kalenderen viser. Redaktører kan rette dækningen for en afsluttet uge via blyanten — rettelsen registreres i audit-loggen.

Ugekortet for den aktuelle uge har en farvet kant, og den der har vagten lige nu er markeret med **nu**. Hvem der har vagten, står også nederst i sidemenuen, sammen med hvornår vagten skifter, og hvem der er den næste.

---

---

## Statistik

**Statistik** i menuen viser helpdesk- og Chronicle-tal for de seneste 12 måneder:

1. **Hvornår**: nye sager pr. ugedag, et varmekort over ugedag og time, og hvor hurtigt sagerne bliver løst (median, gennemsnit og fordeling).
2. **Udvikling**: åbne sager ved hver uges udgang og oprettet mod løst pr. uge.
3. **Hvem og hvad**: kategorier, løste sager pr. tekniker, åbne sager efter alder og sager pr. afdeling.
4. **Chronicle**: prioriterede opgaver og hændelser.

**Vælg periode.** Felterne **Fra** og **Til** øverst vælger et andet tidsrum (begge dage er med). *Seneste 12 måneder* nulstiller. Slutter perioden før i dag, vises åbne sager, som de stod ved periodens slutning. Perioden står i adressen, så den kan bogmærkes eller deles.

**Eksportér** (redaktører) henter siden som PDF, HTML, Markdown eller JSON for den valgte periode. **Del som link** laver et hemmeligt link til tallene som JSON — til værktøjer, der ikke kan logge ind, fx Claude Motion. Linket udløber efter 7, 30 eller 90 dage eller 1 år og kan tilbagekaldes når som helst.

---

## Sårbarheder (CVE'er)

**Sårbarheder** i sidemenuen samler de sårbarheder, der rammer os, fra de bliver opdaget, til de er lukket.

- Hver CVE har id (fx *CVE-2026-109618*), emne, CVSS-score og alvorlighed (Kritisk ≥ 9, Høj ≥ 7, Medium ≥ 4, Lav > 0). Alvorligheden udledes af CVSS, hvis den ikke angives, og linket til cvefeed.io udfyldes automatisk.
- Status er **Identificeret**, **Patcher** eller **Løst**. Skift den med knapperne på CVE'ens side; hvert skift skrives i tidslinjen med navn og tidspunkt.
- Under **Links** samles advisories, leverandørnoter og sager. Under **Kommentarer** skrives noter (Markdown virker), nyeste øverst.
- Under **Vedhæftninger** lægges PDF'er, fx advisories fra FE-CSIRT. Vælg filen, giv den evt. en titel og kilde, angiv **TLP** (CLEAR, GREEN, AMBER, AMBER+STRICT, RED) og klik **Vedhæft PDF**. Klik på en PDF for at se den oven på siden; TLP-mærket står i toppen. Husk TLP, før du sender et dokument videre. PDF'er og Outlook-mails (.msg), højst 25 MB.
- En **Outlook-mail (.msg)**, fx en advarsel fra FE-CSIRT, kan vedhæftes direkte: træk den ud af Outlook og vælg den. Klik på den for at læse afsender, dato og tekst; *Hent* giver den oprindelige mail. PDF'er i mailen pakkes ud som egne vedhæftninger med samme TLP, og vælger du ingen TLP, bruges den, der står i mailen.
- Listen viser åbne CVE'er øverst og løste i 90 dage. Søg på id eller emne, eller vælg *Alle* for ældre.
- Klik **Ny CVE** for at oprette én. Findes id'et allerede, kommer du til den eksisterende i stedet for at lave en dublet. Harbinger opretter CVE'er via API'et og linker tilbage til sig selv.
- **Ugeloggen** viser af sig selv alle CVE'er, der var åbne på et tidspunkt i ugen, og markerer dem, der blev *løst denne uge*. Der er intet at overføre fra uge til uge. Afsnittet kommer også med i HTML- og PDF-eksporten.

### Sager: flere CVE'er med samme løsning

En **sag** samler CVE'er, der har samme vurdering og samme løsning, fx fire kerne-CVE'er, der lukkes af én kerneopdatering, eller Python- og Go-CVE'erne om den samme kompromitterede certifikatudsteder. Så skrives dokumentationen én gang.

- Klik **Sager** på CVE-listen og **Ny sag**. Giv sagen en titel, skriv **Vurdering** (er vi berørt, og hvorfor?) og **Løsning / handling**, og skriv CVE-id'erne adskilt af komma eller linjeskift. Kendte CVE'er flyttes ind; ukendte oprettes med sagens titel som emne.
- Fra en CVE's side: **Føj til sag** vælger en åben sag, og **Ny sag med denne CVE** starter en ny.
- **Sagens status gælder alle dens CVE'er.** Knapperne er *Identificeret*, *Patcher*, *Løst — patchet* og *Løst — ikke berørt*. Hver CVE får skiftet i sin egen tidslinje med "(via sag #n)". På en CVE i en sag er statusknapperne skiftet ud med et link til sagen.
- Vedhæftninger, links og kommentarer på sagen fungerer som på en CVE (også TLP og .msg).
- **En CVE kan kun være i én sag.** Tag den ud med ✕ på sagen for at flytte den; dens status bliver stående.
- Åbne sager står øverst på CVE-listen, og CVE'er i en sag har mærket *Sag #n* i lister og ugeloggen. Harbinger kan sende en hel sag på én gang.
- **Advarsler uden CVE-nummer**, fx fra CFCS: opret en sag og lad CVE-feltet stå tomt. Udfyld **Kilde** (fx CFCS), **Reference** (advarslens nummer og dato) og **Kildelink**, og vedhæft advarslen med dens TLP.
- **Ugeloggen og Kontrolpanelet** viser sagerne over CVE'erne. Ugeloggen viser hver sag, der var åben i løbet af ugen; Kontrolpanelet viser de åbne. En sag uden CVE'er kommer derfor med i ugens dokumentation.
- Søgefeltet på **Sager** finder titel, kilde, reference og CVE-id, også i løste sager.

Læsere kan se alt, men ikke oprette eller ændre.

---

## Forslag

**Forslag** er udviklingstavlen for Chronicle og IT: forslag til ny funktionalitet, UI-ændringer, integrationer og fejl.

1. Klik **Nyt forslag**, giv det en titel og en beskrivelse, og vælg kategori (Teknisk, UI / brugerflade, Integration, Fejl, Andet) og vigtighed (Lav, Medium, Høj, Kritisk).
2. Tavlen har tre kolonner: **Åbne**, **I gang** og **Løst**. Træk et forslag for at omprioritere det eller flytte det til en anden kolonne.
3. Når et forslag markeres som løst, får den der indsendte det besked via klokken.

Søg og filtrér på kategori og vigtighed over tavlen.

---

## Eksporter rapporter

Uger fra før liggetid-opdelingen blev indført viser ikke afsnittet. Administratoren kan genskabe tallene for en lukket uge fra ServiceDesk-historikken med `python manage.py backfill_liggetid <år> <uge>` (køres i sync-containeren).

Alle tre formater indeholder afsnittet **"Åbne sager fordelt på liggetid"**: en bjælke pr. aldersgruppe (under 1 uge, 1-2 uger, 2 uger-1 måned, 1-3 måneder, 3-6 måneder, 6-12 måneder og over 12 måneder) med antal og andel, samt en linje der opsummerer hvor mange af de åbne sager der har ligget i mere end 1 måned. Afsnittet vises kun for uger hvor opdelingen er registreret.

### PDF rapport

1. Åbn en ugelog
2. Klik "Eksporter" > "Download PDF"
3. PDF'en downloades automatisk

### Markdown

1. Åbn en ugelog
2. Klik "Eksporter" > "Download Markdown"
3. Markdown-filen downloades

### Email

1. Åbn en ugelog (eller en opgaves historik)
2. Klik "Eksportér" > "Email som HTML", "Email som PDF" eller "Email som HTML + PDF"
3. En bekræftelsesside viser **hvem der modtager** rapporten, afsenderen, emnet og hvad der vedhæftes
4. Klik "Send til N modtagere" — eller "Annullér" for at gå tilbage uden at sende

Intet sendes, før du trykker Send på bekræftelsessiden.

> **Bemærk:** Modtagerlisten er fælles for alle rapporter og sættes af administratoren (`CHRONICLE_EMAIL_RECIPIENTS`). Er den tom, er Send-knappen slået fra, og siden fortæller hvorfor. Afsenderen er den bruger der er logget ind.

---

## Rapporter

Menuen **Rapporter** samler selvstændige sider med egen grafik, fx den animerede årsgennemgang "Oktober 2026 – et kig et år tilbage". Siderne vises uden Chronicles menu og farver; de har deres eget udseende.

### Åbn og del

1. Klik "Rapporter" i menuen og derefter "Åbn" på en rapport
2. En rapport markeret **Offentligt link** kan åbnes uden login på sin adresse, fx `https://chronicle.fynbus.net/reports/oktober-2026-et-kig-et-aar-tilbage/`. Klik "Kopiér link" og send den til fx ledelsen
3. "Gør privat" lukker adressen med det samme, så den igen kræver login

> **Bemærk:** En offentlig rapport kan læses af alle, der kender adressen. Rapporter indekseres ikke af søgemaskiner. Der findes også et anonymt link (`/reports/p/…`), som ikke afslører titlen; "Nyt anonymt link" udsteder et nyt og lader det gamle dø.

### Læg en rapport op (redaktører)

1. Nederst på siden Rapporter: udfyld titel og beskrivelse, vælg en selvstændig `.html`-fil (højst 16 MB)
2. Vælg eventuelt "Erstat en eksisterende rapport" for at skifte indholdet ud og beholde linket
3. Sæt kryds i "Offentligt link", hvis rapporten skal kunne åbnes uden login
4. Vedhæft eventuelt en video (MP4, højst 300 MB). Den vises under rapporten med en download-knap, og listen får en "Download video"-knap

Rapporter kan også lægges op og opdateres via API'et: `PUT /api/v1/reports/<slug>/` med `title`, `html`, `description` og `is_public` (skrivenøgle); `PUT /api/v1/reports/<slug>/video/` med MP4-filen som rå body (`Content-Type: video/mp4`). `GET /api/v1/reports/` lister dem.

---

---

## Notifikationer

Klokken i bjælken øverst viser dine notifikationer, med en prik når der er nye:
- når en kollega sætter dig på vagt, overtager eller frigiver din vagt;
- når et forslag, du har indsendt, bliver løst.

Notifikationer markeres som læst, når du åbner klokken.

---

## API-nøgler

Under din profil nederst i sidemenuen → **API-nøgler** opretter du nøgler til at hente eller skrive Chronicle-data fra andre programmer, fx Claude-integrationen (MCP) eller scripts.

- **Læs** kan kun hente data; **Læs+skriv** kan også oprette ugelogs, opgaver, hændelser og CVE'er.
- Den fulde nøgle vises kun én gang, når den oprettes — gem den i en adgangskodemanager.
- En nøgle kan tilbagekaldes eller udskiftes når som helst.

API'et ligger under `/api/v1/`.

---

## Udseende og temaer

Tandhjulet nederst i sidemenuen samler indstillingerne. De gemmes i din browser.

- **Udseende**: lyst eller mørkt.
- **Densitet**: Komfort, Kompakt eller Dashboard (se [Kontrolpanel](#kontrolpanel)).
- **Accent**: Guld, Salvie, Blæk eller Saber.
- **Tema**: *Auto* følger kalenderen; du kan også vælge et tema fast.

### Dagstemaer

På bestemte dage skifter sitet udseende af sig selv — farver, logo-mærke og et
banner øverst. Temaet kan også vælges manuelt under tandhjulet nederst i sidemenuen → **Tema**, og
administratoren kan tilføje eller flytte datoer under "Administrér skeduler".

| Dato | Tema |
|------|------|
| 4. maj | Star Wars Day |
| 8. september og 5. april | Star Trek Day / First Contact Day |
| 19. september og 1. oktober | Pirate Day |
| 21. september | Verdens Alzheimerdag — lilla, med fakta og henvisninger til Alzheimerforeningen i banneret i stedet for vittigheder |

**Read-only Friday.** Hver fredag viser sitet et rødt banner øverst: ingen
ændringer i produktion i dag — deploys, patches og "lige en lille rettelse"
venter til mandag. Det er en regel, ikke et tema, så det kan ikke slås fra i
tema-panelet og vises oven i et eventuelt dagstema. Forhåndsvisning på andre
dage: tilføj `?force-friday=1` til adressen.

**Touch-Grass-Weekend.** Søsteren til Read-only Friday: hver lørdag og
søndag viser sitet et grønt banner — "Det er weekend. Gå udenfor." Det er
også en regel og vises oven i et eventuelt dagstema.

Vil du se et tema uden at vente på dagen, kan du tilføje `?force-theme=<navn>`
til adressen, fx `?force-theme=alzheimer`.

---

---

## Tips og tricks

- **Ctrl+K** (⌘K) hopper til søgefeltet.
- **Esc** lukker dialoger og menuer.
- Registrér hændelser med det samme, mens detaljerne er friske.
- Meld klar på ugeloggen, når du er færdig, så den der afslutter ugen ved det.

---

## Hjælp og support

Kontakt IT-afdelingen ved spørgsmål eller problemer, eller opret et forslag under **Forslag**.

- Email: it@fynbus.dk

For tekniske fejl, beskriv venligst:
1. Hvad du forsøgte at gøre
2. Hvad der skete
3. Eventuelle fejlmeddelelser
