# Brugervejledning - FynBus Chronicle

Denne vejledning forklarer hvordan du bruger FynBus Chronicle til at registrere og følge IT-afdelingens ugentlige aktiviteter.

## Indhold

1. [Log ind](#log-ind)
2. [Brugerroller](#brugerroller)
3. [Kontrolpanel](#kontrolpanel)
4. [Ugelogs](#ugelogs)
5. [Opgaver](#opgaver)
6. [Vagtkalender](#vagtkalender)
7. [Eksporter rapporter](#eksporter-rapporter)
8. [Mørk tilstand](#mørk-tilstand)

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
- Oprette og styre opgaver med statusworkflow, noter og vedhæftede filer
- Tilføje og administrere prioriterede opgaver, fravær og hændelser
- Redigere mødereferater
- Eksportere rapporter (PDF, Markdown, HTML, email)
- Tage, frigive og omfordele vagter i vagtkalenderen (inkl. deling af en uge mellem flere personer)
- Sortere prioriterede opgaver via træk-og-slip

### Læser (Viewer)

Brugere der er tilføjet til gruppen "Viewer" har kun læseadgang:

- **Kan se**: Kontrolpanel, ugelogs, vagtkalender og dokumentation
- **Kan ikke**: Oprette, redigere, slette, sortere eller eksportere noget

Læsere ser ikke nogen handlingsknapper (Tilføj, Rediger, Slet, Eksporter osv.). Forsøg på at tilgå skrivebeskyttede funktioner direkte via URL returnerer en fejlside.

> **Bemærk:** Administratorer (staff-brugere) har altid fuld adgang uanset gruppemedlemskab.

Kontakt din administrator for at ændre din brugerrolle.

---

## Kontrolpanel

Kontrolpanelet giver et overblik over den aktuelle uges aktiviteter.

### Live opdateringer

Kontrolpanelet opdateres automatisk uden at du behøver genindlæse siden:
- **Helpdesk statistik**: Opdateres hvert 30. sekund
- **Aktuel uge**: Opdateres hvert minut
- **Graf og hændelser**: Opdateres hvert minut

Hvis ServiceDesk-integration er aktiveret, hentes helpdesk-tal automatisk fra ServiceDesk Plus.

### Komponenter

**Aktuel uge**
- Viser sammenfatning af den aktuelle ugelog
- Aktive prioriterede opgaver
- Planlagt fravær

**Helpdesk statistik**
- Graf over de sidste 52 ugers sager
- Gennemsnitlige nye og lukkede sager
- Antal åbne sager lige nu
- Opdateres automatisk hvis ServiceDesk-integration er aktiv

**Seneste hændelser**
- Liste over nylige hændelser
- Markering af uløste hændelser

### Hurtige handlinger

Klik på "Ny ugelog" for at oprette en ny ugelog.

---

## Ugelogs

### Oversigt

Gå til "Ugelogs" i navigationen for at se alle ugelogs.

**Filtrering**
- Brug dropdown-menuen til at filtrere efter år

### Opret ny ugelog

1. Klik på "Ny ugelog"
2. Udfyld:
   - **År og uge**: Udfyldes automatisk med aktuel uge
   - **Helpdesk statistik**: Nye, lukkede og åbne sager
   - **Ugeoversigt**: Kort beskrivelse af ugens aktiviteter
3. Klik "Opret ugelog"

### Se ugelog detaljer

Klik på "Se detaljer" for at åbne en ugelog.

Her kan du:
- Se helpdesk-statistik
- Administrere prioriterede opgaver
- Registrere fravær
- Dokumentere hændelser

### Prioriterede opgaver

**Tilføj opgave**
1. Klik "Tilføj" ved Prioriterede opgaver
2. Udfyld:
   - Titel
   - Prioritet (Høj/Medium/Lav)
   - Status (Ikke startet/Igangværende/Blokeret/Afsluttet)
   - Beskrivelse og noter
3. Klik "Tilføj"

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

## Opgaver

Opgaver-modulet bruges til at registrere og følge IT-opgaver og projekter.

### Grundlæggende funktioner

- **Opret opgaver** med titel, beskrivelse, planlagte datoer, ansvarlige og godkendere
- **Statusworkflow**: Todo → I gang → Test → Godkendelse → Færdig
- **Skift status** direkte fra opgavedetaljer via klik på statusbadget
- **Tilføj noter** med emne, tekst og vedhæftede filer
- **Statushistorik**: Alle statusændringer logges automatisk med tidspunkt og bruger

### Tidslinjevisning

Kontrolpanelet viser en Gantt-lignende tidslinje over aktive opgaver med farvekodning efter status. Klik på en opgave i tidslinjen for at se detaljer.

Se den fulde dokumentation under [Dokumentation > Opgaver](/dashboard/docs/tasks/).

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

Uger med ændringer viser et lille ur-ikon. Klik på det for at se panelet med:

- **Dækning**: Hvem der havde ansvaret hvilke dage (og klokkeslæt).
- **Ændringer**: Hvem der ændrede vagten, hvornår, og fra/til hvem.

Ændringer før version 0.8.0 er ikke registreret.

### Tidligere uger

Brug "Tidligere"-knapperne øverst til at vise 4, 13 eller 26 afsluttede uger. Redaktører kan rette dækningen for en afsluttet uge via blyanten — rettelsen registreres i audit-loggen.

### Notifikationer

Sættes du på vagt af en kollega, får du besked via klokken øverst til højre. Det samme gælder hvis din vagt overtages eller frigives af andre. Notifikationer markeres som læst når du åbner klokken.

---

## Eksporter rapporter

### PDF rapport

1. Åbn en ugelog
2. Klik "Eksporter" > "Download PDF"
3. PDF'en downloades automatisk

### Markdown

1. Åbn en ugelog
2. Klik "Eksporter" > "Download Markdown"
3. Markdown-filen downloades

### Email

1. Åbn en ugelog
2. Vælg format (HTML, PDF eller begge dele)
3. Klik "Send som email"
4. Rapporten sendes til konfigurerede modtagere med dig som afsender

> **Bemærk:** Email-funktionen kræver at administratoren har konfigureret email-modtagere i systemet. Afsenderen er den bruger der er logget ind.

---

## Mørk tilstand

FynBus Chronicle understøtter mørk tilstand for at reducere øjentræthed.

### Skift tema

1. Find sol/måne-ikonet i navigationsbjælken
2. Klik for at skifte mellem lys og mørk tilstand
3. Din præference gemmes automatisk

---

## Tips og tricks

### Tastatur genveje

- `Tab`: Naviger mellem felter
- `Enter`: Gem formular
- `Esc`: Annuller redigering

### Bedste praksis

1. **Opdater ugentligt**: Opret ugelogs løbende for nøjagtig historik
2. **Dokumenter hændelser**: Registrer hændelser med det samme mens detaljerne er friske
3. **Brug noter**: Tilføj kontekst til opgaver og fravær
4. **Eksporter regelmæssigt**: Send ugentlige rapporter til interessenter

---

## Hjælp og support

Kontakt IT-afdelingen ved spørgsmål eller problemer:

- Email: it@fynbus.dk
- Internt telefonnummer: [telefonnummer]

For tekniske fejl, beskriv venligst:
1. Hvad du forsøgte at gøre
2. Hvad der skete
3. Eventuelle fejlmeddelelser
