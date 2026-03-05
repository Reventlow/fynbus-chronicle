# Opgaver - Opgavestyring

Opgaver-modulet giver IT-afdelingen mulighed for at registrere, spore og styre opgaver og projekter med godkendere, ansvarlige, statushistorik og noter.

## Indhold

1. [Oversigt](#oversigt)
2. [Opret opgave](#opret-opgave)
3. [Statusworkflow](#statusworkflow)
4. [Skift status](#skift-status)
5. [Noter og vedhæftede filer](#noter-og-vedhæftede-filer)
6. [Statushistorik](#statushistorik)
7. [Tidslinjevisning](#tidslinjevisning)
8. [Sortering](#sortering)

---

## Oversigt

Opgaver-siden viser en liste over alle registrerede opgaver med:

- **Titel**: Opgavens navn
- **Status**: Aktuel status med farvekodning
- **Planlagt start/slut**: Tidsramme for opgaven
- **Tildelt**: Hvem der er ansvarlig for opgaven

Naviger til Opgaver via menuen eller gå direkte til `/tasks/`.

---

## Opret opgave

> Kræver redaktørrettigheder.

1. Klik **Ny opgave** på opgavesiden
2. Udfyld:
   - **Titel**: Kort beskrivelse af opgaven
   - **Beskrivelse**: Detaljeret beskrivelse (valgfrit)
   - **Status**: Startstatus (standard: Todo)
   - **Planlagt start**: Forventet startdato (valgfrit)
   - **Planlagt slut**: Forventet slutdato (valgfrit)
   - **Tildelt**: Vælg ansvarlige medarbejdere
   - **Godkendere**: Vælg godkendere for opgaven
3. Klik **Opret opgave**

Alle statusændringer logges automatisk i statushistorikken.

---

## Statusworkflow

Opgaver har seks statusser med følgende farvekoder:

| Status | Dansk | Farve | Beskrivelse |
|--------|-------|-------|-------------|
| Todo | Todo | Grå | Opgaven er oprettet men ikke startet |
| Doing | I gang | Blå | Arbejdet er i gang |
| Paused | Pause | Gul | Opgaven er sat på pause |
| Testing | Test | Lilla | Opgaven testes |
| Approval | Godkendelse | Orange | Afventer godkendelse |
| Complete | Færdig | Grøn | Opgaven er afsluttet |

En typisk opgave gennemgår flowet:

**Todo** → **I gang** → **Test** → **Godkendelse** → **Færdig**

Opgaver kan sættes på **Pause** fra enhver status og genoptages senere.

---

## Skift status

> Kræver redaktørrettigheder.

Der er to måder at skifte status:

### Fra opgavedetaljer (inline)

1. Åbn en opgave
2. Klik på statusbadget
3. Vælg ny status fra dropdown-menuen
4. Statusskift logges automatisk

### Fra redigeringsformularen

1. Åbn en opgave
2. Klik **Rediger**
3. Vælg ny status
4. Klik **Gem ændringer**

---

## Noter og vedhæftede filer

> Kræver redaktørrettigheder for at oprette og slette noter.

### Tilføj note

1. Åbn en opgave
2. Scroll ned til notefomularen
3. Udfyld **Emne** og **Tekst**
4. Vedhæft filer (valgfrit) - klik **Vælg filer** og vælg en eller flere filer
5. Klik **Tilføj note**

### Tilladte filtyper

Følgende filtyper kan vedhæftes:

- **Billeder**: PNG, JPG, JPEG, GIF
- **Dokumenter**: PDF, DOC, DOCX, MD
- **Præsentationer**: PPT, PPTX
- **Regneark**: XLS, XLSX

### Slet note

1. Klik på slet-ikonet ved noten
2. Bekræft sletning

Bemærk: Sletning af en note fjerner også alle vedhæftede filer.

---

## Statushistorik

Alle statusændringer logges automatisk med:

- **Tidspunkt**: Hvornår ændringen fandt sted
- **Bruger**: Hvem der foretog ændringen
- **Fra/til status**: Hvilken status opgaven gik fra og til

Historikken vises som en tidslinje på opgavedetaljesiden med farvekodede statusbadges.

---

## Tidslinjevisning

Kontrolpanelet viser en **Opgave Tidslinje** - et Gantt-lignende diagram der visualiserer aktive opgaver:

- Vandret bjælke for hver opgave fra planlagt start til slut
- Farvekodning efter aktuel status
- Klik på en bjælke for at gå til opgavedetaljer
- Hold musen over en bjælke for at se tildelte og godkendere
- Opdateres automatisk hvert minut

Kun opgaver med planlagte start- og slutdatoer vises i tidslinjen.

---

## Sortering

Opgavelisten kan sorteres efter:

- **Planlagt start**: Opgaver med nærmeste startdato først (standard)
- **Status**: Gruppér efter statustype
- **Titel**: Alfabetisk rækkefølge
- **Oprettet**: Nyeste eller ældste først

Klik på sorteringsknapperne for at skifte mellem stigende og faldende rækkefølge.
