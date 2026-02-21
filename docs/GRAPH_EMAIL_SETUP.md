# Opsætning af email via Microsoft Graph

Denne guide beskriver hvordan FynBus Chronicle konfigureres til at sende emails via Microsoft Graph API i stedet for SMTP.

## Hvorfor Graph API?

- Virker med M365-tenants der har deaktiveret SMTP AUTH
- Ingen SMTP-legitimationsoplysninger at administrere
- Den indloggede bruger vises som emailafsender
- Genbruger den eksisterende Azure AD-appregistrering (fra SSO-opsætningen)

## Forudsætninger

- Azure AD-appregistrering (se [SSO Opsætning](/dashboard/docs/sso/) hvis den ikke allerede er konfigureret)
- Azure AD-administratoradgang til at tildele applikationstilladelser
- En gyldig M365-postkasse for afsenderadressen

## Trin 1: Tilføj Mail.Send-tilladelse

1. Gå til [Azure Portal](https://portal.azure.com)
2. Naviger til **Microsoft Entra ID** > **App registrations**
3. Vælg din FynBus Chronicle-app
4. Gå til **API permissions** > **Add a permission**
5. Vælg **Microsoft Graph**
6. Vælg **Application permissions** (ikke Delegated)
7. Søg efter og tilføj: `Mail.Send`
8. Klik **Add permissions**
9. Klik **Grant admin consent for [Organisation]**

> **Vigtigt**: Brug *Application*-tilladelser (ikke *Delegated*), da email sendes server-side via client credentials flow.

## Trin 2: Konfigurer miljøvariabler

Tilføj til din `.env` eller `.env.prod`:

```env
EMAIL_USE_GRAPH=True
```

Graph-backenden genbruger disse eksisterende indstillinger (fra SSO):

```env
MICROSOFT_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
MICROSOFT_CLIENT_SECRET=din-client-secret-værdi
MICROSOFT_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Disse email-indstillinger bruges stadig:

```env
DEFAULT_FROM_EMAIL=it@fynbus.dk
CHRONICLE_EMAIL_RECIPIENTS=manager@fynbus.dk,team@fynbus.dk
```

Hvis du bruger Docker, tilføj til docker-compose environment:

```yaml
- EMAIL_USE_GRAPH=${EMAIL_USE_GRAPH:-False}
```

## Trin 3: Verificering

### Hurtig test via Django shell

```bash
python manage.py shell
```

```python
from django.core.mail import send_mail

send_mail(
    subject="Test fra Chronicle",
    message="Graph email-backend virker!",
    from_email="it@fynbus.dk",
    recipient_list=["din-email@fynbus.dk"],
)
```

En succesfuld afsendelse returnerer `1` uden exceptions.

### Tjek logs

Backenden logger alle afsendelsesforsøg:

```
INFO Email sent via Graph API from=it@fynbus.dk to=['modtager@fynbus.dk'] subject='...'
```

## Fejlfinding

### 403 Forbidden

**Årsag**: Manglende eller ikke-godkendt `Mail.Send`-tilladelse.

**Løsning**:
1. Bekræft at `Mail.Send` er listet under API-tilladelser
2. Sørg for at admin-samtykke er givet (grønt flueben)
3. Vent et par minutter på at tilladelserne propageres

### 404 Not Found

**Årsag**: `from_email`-adressen er ikke en gyldig postkasse i tenanten.

**Løsning**: Sørg for at `DEFAULT_FROM_EMAIL` (eller den indloggede brugers email) svarer til en rigtig M365-postkasse.

### Token-hentningsfejl

**Årsag**: Ugyldige klient-legitimationsoplysninger.

**Løsning**:
1. Bekræft at `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` og `MICROSOFT_TENANT_ID` er korrekte
2. Tjek om client secret er udløbet
3. Opret en ny secret om nødvendigt (se [SSO Opsætning](/dashboard/docs/sso/#step-3-create-client-secret))

### Emails sendt men modtages ikke

**Årsag**: Emailen kan ligge i modtagerens uønsket post/spam-mappe.

**Løsning**:
1. Tjek spam/uønsket post-mapper
2. Tilføj afsenderadressen til organisationens liste over sikre afsendere
3. Bekræft SPF/DKIM/DMARC-records for dit domæne

## Sikkerhedsovervejelser

### Princippet om mindst mulig adgang

`Mail.Send`-applikationstilladelsen giver appen mulighed for at sende email som *enhver* bruger i tenanten. For at begrænse dette:

1. Gå i Azure Portal til **Enterprise applications** > vælg din app
2. Under **Properties**, sæt **Assignment required** til Yes
3. Brug [Application Access Policies](https://learn.microsoft.com/en-us/graph/auth-limit-mailbox-access) til at begrænse hvilke postkasser appen kan sende fra

### Rotation af secrets

Den samme client secret bruges til SSO og Graph-email. Når du roterer secrets:

1. Opret en ny secret i Azure (mens den gamle stadig virker)
2. Opdater `MICROSOFT_CLIENT_SECRET` i dit miljø
3. Genstart applikationen
4. Verificer at både SSO og email stadig virker
5. Slet den gamle secret i Azure

## Skift tilbage til SMTP

For at skifte tilbage til SMTP, sæt:

```env
EMAIL_USE_GRAPH=False
```

SMTP-indstillingerne (`EMAIL_HOST`, `EMAIL_PORT` osv.) bevares og bruges automatisk.

## Referencer

- [Microsoft Graph sendMail API](https://learn.microsoft.com/en-us/graph/api/user-sendmail)
- [Oversigt over applikationstilladelser](https://learn.microsoft.com/en-us/graph/permissions-overview#application-permissions)
- [Begræns applikationstilladelser til specifikke postkasser](https://learn.microsoft.com/en-us/graph/auth-limit-mailbox-access)
