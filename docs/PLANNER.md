# Planner board

Chronicle can show one Microsoft Planner plan (at FynBus: *Intern IT - Backlog*) as a board under **Planner** in the menu: the same buckets and cards as in Planner, refreshed automatically. Since 1.17.0 editors who connect their own Microsoft account can also complete and reopen cards, drag them between buckets, add cards, and link a card to a Chronicle priority or case (both ways).

## How it works

```
            Microsoft Graph (Planner)
                     ▲
                     │  only from here
   ┌─────────────────┴──────────────────┐
   │ sync container (run_scheduler)     │  mirrors the plan into the database,
   │ client secret + private key        │  redeems the service account's sign-in
   └─────────────────┬──────────────────┘
                     │ shared database
   ┌─────────────────┴──────────────────┐
   │ web container                      │  shows the board from the mirror,
   │ public key only, no secret         │  records "Synk nu" and sign-ins (sealed)
   └────────────────────────────────────┘
```

- **Only the sync container talks to Microsoft.** It holds the app's client secret and the private key. The web container, which faces users, has neither, so a compromised web container can't read Planner tokens or call Graph.
- **The sign-in is a service account** (e.g. `SVC-Chronicle-Planner@fynbus.dk`) that is a member of the plan's group and nothing else, so its tokens reach only that plan. A staff member connects it once; the sync container keeps its token cache **sealed** in the database and refreshes it on every run.
- **Sealed hand-over:** Microsoft sends the one-time sign-in code to the web container. It seals the code with the public key straight away; only the sync container's private key opens it. The sealed code is deleted once used.
- **Schedule:** Mon–Fri 07:15–17:30 every 2 minutes, otherwise every 15 minutes (Danish time). **Synk nu** on the board runs a sync within seconds (at most one every 30 seconds). Task descriptions are re-read when a task changes, and all of them once an hour.
- **Who sees it:** editors (not the read-only *Viewer* group). Connecting or disconnecting the service account: staff.
- **Changes are made in the editor's own name.** The service account only reads. An editor connects their own account once (*Forbind min konto*, same sealed hand-over); a change on the board becomes a queued `PlannerChange` that the sync container makes with *that editor's* token on its next tick (every 5 seconds), so Planner's history and Purview's audit log show the real person. There is no fallback to the service account: without your own connection the board is read-only for you.
  - The board shows the change at once and the card polls until it is done; if Planner refuses it (most often 403: not a member of the plan's group), the card says why and a sync puts the board back.
  - Updates read the item first for its current etag and patch only the fields in question (a 412 race is retried once).
  - An editor can only connect *their own* account: the Entra object id of their SSO link must match, or, without SSO, their e-mail must equal the UPN. The service account is refused as a personal connection.
- **Links to Chronicle** (`PlannerLink`): *Knyt til Chronicle* creates a priority (this week's log) or a planned-task case from the card, or picks an existing one. In Planner the card gets the label *Prioriteret opgave* / *Sag* (created in the first free label slot if the plan has no label with that name) and a reference (attachment link) back to the Chronicle page. The priority's history page and the case page show a *Planner* link to the card. Removing a link in the admin doesn't touch the card in Planner.
- Text from Planner is shown as plain, escaped text, and descriptions are cut at 4,000 characters.

## Setup

### 1. Entra: app registration "Chronicle Planner"

- Single tenant; platform **Web**; redirect URI `https://chronicle.fynbus.net/planner/connect/callback/` (exact, with the trailing slash). For local testing also `http://localhost:8000/planner/connect/callback/`.
- *Allow public client flows* = **No**; no implicit grant.
- Delegated permissions **`Tasks.ReadWrite`**, **`User.ReadBasic.All`**, `offline_access`, `openid`, `profile`, with admin consent. No application permissions.
- A client secret (12 months). Copy its **Value** (40 characters), not the *Secret ID* (a GUID).
- Enterprise application: *Assignment required* = Yes; assign the service account **and every editor who will make changes on the board** (assign a group, e.g. *Chronicle-Planner*). Without it their sign-in fails with AADSTS50105.
- Editors who make changes must also be **members of the plan's Microsoft 365 group**; otherwise Planner refuses their changes (403) and the card says so.

### 2. Entra: the service account

- A user such as `SVC-Chronicle-Planner@fynbus.dk` with a licence that includes Planner (Business Basic, F1 or E1).
- **Member** of the Microsoft 365 group behind the plan, and of nothing else.
- MFA; its password and TOTP secret in the password manager.
- Conditional Access: exclude it from sign-in frequency for this app only, from a named location covering fbdocker01's public IP (the sync refreshes the token from the server) and the place you sign in from. Otherwise the connection lapses every few days.

### 3. Keys

Generate a key pair once:

```bash
docker exec chronicle-web python manage.py planner_keygen
```

### 4. Environment

`web.env`:

```env
PLANNER_ENABLED=True
PLANNER_CLIENT_ID=<Chronicle Planner client id>
PLANNER_PLAN_ID=<plan id from the Planner URL: .../plan/<this>/view/board>
PLANNER_SERVICE_ACCOUNT=SVC-Chronicle-Planner@fynbus.dk
PLANNER_PUBLIC_KEY=<from planner_keygen>
# MICROSOFT_TENANT_ID is used unless PLANNER_TENANT_ID is set.
```

`sync.env` (the sync container):

```env
PLANNER_SYNC_ENABLED=True
PLANNER_CLIENT_ID=<same>
PLANNER_CLIENT_SECRET=<the secret's Value>
PLANNER_PLAN_ID=<same>
PLANNER_SERVICE_ACCOUNT=SVC-Chronicle-Planner@fynbus.dk
PLANNER_PUBLIC_KEY=<same>
PLANNER_PRIVATE_KEY=<from planner_keygen; sync.env ONLY>
MICROSOFT_TENANT_ID=<tenant GUID>
# Optional schedule (defaults shown):
# PLANNER_WORK_HOURS=mon-fri 07:15-17:30
# PLANNER_INTERVAL_WORK=120
# PLANNER_INTERVAL_OFF=900
# Changes on the board (default on; False = read-only for everyone):
# PLANNER_WRITES_ENABLED=True
# Label names put on linked cards:
# PLANNER_LABEL_PRIORITY=Prioriteret opgave
# PLANNER_LABEL_CASE=Sag
```

Never put `PLANNER_CLIENT_SECRET` or `PLANNER_PRIVATE_KEY` in `web.env`. Redeploy the stack after changing either file.

### 5. Connect

1. As staff, open **Planner** in Chronicle and click **Forbind Planner** at the bottom.
2. Sign in to Microsoft **as the service account** (an incognito window avoids picking your own account). Any other account is refused.
3. Back on the board, the status line shows *Forbinder servicekontoen…*; within a few seconds the sync container connects and runs the first sync.
4. Each editor who wants to make changes clicks **Forbind min konto** at the top of the board and signs in with their own account.

## Operation

- **Status line** under the title: last sync and next one. It turns red with the reason if the sync fails or is more than three intervals overdue (e.g. *Login udløbet eller tilbagekaldt … Forbind Planner igen*).
- **Admin → Planner** shows the connection, sign-in attempts and sync state (the sealed values are never shown).
- **Disconnect:** *Afbryd* on the board forgets the tokens; the board keeps showing the last copy. To cut access at Microsoft too, revoke the service account's sessions in Entra.
- **Rotating the client secret:** create a new one, put its Value in `sync.env`, redeploy, delete the old one. The connection survives.
- **Rotating the key pair:** run `planner_keygen`, update both env files, redeploy, then connect again (the old sealed token cache can't be opened with the new key).

## Code

`apps/planner/`: `graph.py` (MSAL and Graph, sync side), `sync.py` (mirror and the scheduler job), `writes.py` (making queued changes, sync side), `crypto.py` (sealed boxes), `schedule.py`, `views.py` (web side). The job runs in `apps/logbook/management/commands/run_scheduler.py` next to the ServiceDesk sync; each has its own switch, and an error in one doesn't stop the other.
