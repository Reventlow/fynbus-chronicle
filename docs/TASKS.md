# Opgaver (legacy)

> **Opgaver-modulet er udfaset.** Det ligger stadig på `/tasks/`, men er ikke længere i menuen eller på Kontrolpanelet. Arbejde følges i dag med **prioriterede opgaver** på ugelogs: de lever på tværs af uger, kan føres videre, flettes og genåbnes, og kan søges frem med **Ctrl+K**. Se afsnittet *Prioriterede opgaver* i [Brugervejledningen](USER_GUIDE.md).
>
> Brug kun Opgaver til at slå gamle opgaver op. Opret ikke nye her.

Beskrivelsen nedenfor dækker det gamle modul, så eksisterende data stadig kan læses og vedligeholdes.

## Oversigt

Gå direkte til `/tasks/`. Listen viser alle opgaver med titel, status, planlagt start/slut og hvem opgaven er tildelt. Klik på en opgave for at se detaljer, noter og statushistorik.

---

## Opret og rediger opgave

> Kræver redaktørrettigheder. Brugere i Viewer-gruppen kan kun læse.

**Ny opgave** på listen eller **Rediger** på en opgave åbner formularen med:

- **Titel** og **Beskrivelse** (valgfri)
- **Status** (standard: Todo)
- **Planlagt start** og **Planlagt slut** (valgfri)
- **Tildelt**: aktive brugere
- **Godkendere**: en fast liste af navne (Anna Lise, Dennis, Morten, Peter, Gorm), gemt som tekst

---

## Statusser

| Status | Betydning |
|--------|-----------|
| Todo | Oprettet, ikke startet |
| I gang | Arbejdet er i gang |
| Pause | Sat på pause |
| Test | Testes |
| Godkendelse | Afventer godkendelse |
| Færdig | Afsluttet |

Der er ingen fast rækkefølge — en opgave kan skifte til enhver status.

---

## Skift status

> Kræver redaktørrettigheder.

- **På opgavesiden:** klik på statusmærket og vælg en ny status. Skiftet gemmes med det samme.
- **I formularen:** vælg ny status under **Rediger** og gem.

---

## Noter og vedhæftede filer

> Kræver redaktørrettigheder for at oprette og slette noter.

På opgavesiden: udfyld **Emne** og **Tekst**, vedhæft eventuelt en eller flere filer, og klik **Tilføj note**.

Tilladte filtyper: PNG, JPG, JPEG, GIF, PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX og MD. Filer med andre endelser springes over.

Sletter du en note, forsvinder dens vedhæftede filer også fra opgaven.

---

## Statushistorik

Hver statusændring logges med tidspunkt, bruger og fra/til-status — også startstatus, når opgaven oprettes, og ændringer foretaget i formularen. Historikken vises på opgavesiden.

---

## Sortering

Listen kan sorteres efter **Planlagt start** (standard), **Status**, **Titel** og **Oprettet**, stigende eller faldende.
