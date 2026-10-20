# Deployment Guide

How FynBus Chronicle runs in production and how a new version gets there. Building a release (version bump, changelog, CI) is described in [DEVELOPMENT.md](DEVELOPMENT.md#releasing).

## Production at a glance

| | |
|---|---|
| URL | https://chronicle.fynbus.net |
| Host | `fbdocker01` |
| Deploy method | GitOps — the compose file in the `FynBus/infrastructure-as-code` repo, `docker-compose/chronicle/compose.yml` |
| Containers | `chronicle-web` (`elohite/chronicle`) and `chronicle-sync` (`elohite/chronicle_sync_servicedesk`) |
| Configuration | Environment files on the host, not in this repo |

Both images are built from the same commit and tagged with the same version, so **both tags are always bumped together**. A sync container running older code writes stale statistics.

Production is defined only in `infrastructure-as-code`, deployed as the Portainer stack **chronicle**, which follows that file through GitOps polling. `docker-compose.prod.yml` in this repo mirrors its shape (same two images, env files, shared data volume) and runs with `CHRONICLE_VERSION=<version> docker compose -f docker-compose.prod.yml up -d`; `docker-compose.sqlite.yml` is a standalone example.

> **Read-only Friday:** no production changes on Fridays — no deploys, no config changes. Chronicle shows a red banner on Fridays as a reminder.

## Deploying a new version

1. **Release** — push the version bump to `main` (see [Releasing](DEVELOPMENT.md#releasing)) and wait for the CI `build` job to finish.
2. **Gate: check that both tags exist on Docker Hub.** Do this as a separate step, and stop if either is missing:

   ```bash
   V=$(cat version.txt)
   for img in chronicle chronicle_sync_servicedesk; do
     printf '%s:%s -> ' "$img" "$V"
     curl -s -o /dev/null -w '%{http_code}\n' \
       "https://hub.docker.com/v2/repositories/elohite/$img/tags/$V/"
   done
   ```

   Both must return `200`. Bumping the compose file to a tag that does not exist once made the host recreate `chronicle-web` without an image, and the site returned 502 until it was fixed.
3. **Bump both image tags** in `infrastructure-as-code/docker-compose/chronicle/compose.yml` to the new version, commit and push.
4. **Wait.** Portainer polls the repository and redeploys the stack on `fbdocker01` within a few minutes; there is nothing to run on the host.
5. **Verify** on the host:

   ```bash
   docker inspect -f '{{.Config.Image}}' chronicle-web chronicle-sync
   ```

   Both lines should show the new version. The version is also shown in the app (footer and Dokumentation → Changelog).

### What happens when the containers start

**`chronicle-web`** (`docker/Dockerfile`, entrypoint `docker/entrypoint.sh`):

1. If `DATABASE_URL` is set, waits up to 30 seconds for the database port.
2. `python manage.py migrate --noinput` — upgrades need no manual steps.
3. `python manage.py collectstatic --noinput --clear` (static files are served by WhiteNoise).
4. Starts gunicorn on port 8000 with 2 workers.

**`chronicle-sync`** (`docker/Dockerfile.sync`) has no entrypoint script and does not migrate — the web container does that. It runs `python manage.py run_scheduler`, which **first waits until the database has every migration its code expects** (logged once a minute while waiting), so a sync container that starts before `chronicle-web` has migrated never writes into an old schema. Then:

- Exits immediately with a warning if `SERVICEDESK_SYNC_ENABLED` is not `True`.
- Every `SERVICEDESK_SYNC_INTERVAL` seconds (default 300): syncs this week's ServiceDesk counts onto the current week log, then updates the `HelpdeskTicket` mirror (Statistik and the open-ticket cards on the Kontrolpanel).
- The mirror is synced **in full on start and then every 24 hours**, incrementally (changed tickets only) in between. A failure in one sync does not stop the other.
- On start it logs `Starting ServiceDesk sync loop (every 300s).`

The sync image contains only `requirements/base.txt` and the app code (no templates, static files or gunicorn). Its Docker health check only verifies that Django and the ServiceDesk client load.

Both containers must use the same database: the same `DATABASE_URL`, or the same volume mounted at `SQLITE_DIR`.

### Rolling back

Set both tags back to the previous version in `infrastructure-as-code` and push. Migrations are not reversed automatically: if the release added migrations, check that the older code still runs against the newer schema, or migrate back by hand (`docker exec chronicle-web python manage.py migrate <app> <migration>`) **before** switching the image.

## Configuration

Production settings are `chronicle.settings.prod` (set in both images). They force `DEBUG=False`, trust `X-Forwarded-Proto` from the reverse proxy, enable HSTS and secure cookies, and log to stdout. All variables are listed in [SETUP.md](SETUP.md#environment-variables); the ones that matter in production:

| Container | Variables |
|-----------|-----------|
| web | `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SECURE_SSL_REDIRECT`, `DATABASE_URL` or `SQLITE_DIR`, `SSO_ENABLED`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT_ID`, `EMAIL_USE_GRAPH` (or the `EMAIL_*` SMTP variables), `DEFAULT_FROM_EMAIL`, `CHRONICLE_EMAIL_RECIPIENTS`, `SERVICEDESK_URL`, `SERVICEDESK_API_KEY`, `SERVICEDESK_SYNC_ENABLED=True` (for the Kontrolpanel sync button) |
| sync | `SECRET_KEY`, `DATABASE_URL` or `SQLITE_DIR`, `SERVICEDESK_URL`, `SERVICEDESK_API_KEY`, `SERVICEDESK_SYNC_ENABLED=True`, `SERVICEDESK_SYNC_INTERVAL` |

Never put secrets in this repo or in `infrastructure-as-code`; they belong in the environment files on the host.

**`CSRF_TRUSTED_ORIGINS` must list every origin the site is reached on**, including the port when it is not 443. Django compares scheme, host and port exactly; a missing origin shows up as a 403 on every form submit while GET pages look normal. Reaching the site through an SSH tunnel on e.g. `:8443` needs that origin listed too — or browse without the port.

See [SSO_SETUP.md](SSO_SETUP.md) and [GRAPH_EMAIL_SETUP.md](GRAPH_EMAIL_SETUP.md) for the Azure app registration.

## Data and backup

With SQLite, everything lives in `SQLITE_DIR` (`/app/data` in the images' compose examples):

- `db.sqlite3` — the database
- `report_files/` — report videos (`REPORT_FILES_DIR`)
- `image_files/` — pasted images (`IMAGE_FILES_DIR`)

Back up that whole directory. With PostgreSQL, back up the database with `pg_dump` and the two file directories separately.

## Operations

Run management commands inside the containers on `fbdocker01`:

```bash
# Create an admin user
docker exec -it chronicle-web python manage.py createsuperuser

# Mint an API key for scripts / MCP (printed once)
docker exec chronicle-web python manage.py mint_api_key <username> --scope=read --label="<label>"

# ServiceDesk: manual syncs and backfill (in the sync container, which has the ServiceDesk settings)
docker exec chronicle-sync python manage.py sync_servicedesk
docker exec chronicle-sync python manage.py sync_helpdesk_tickets --full
docker exec chronicle-sync python manage.py backfill_liggetid --all-missing --dry-run

# Logs
docker logs --tail 100 chronicle-web
docker logs --tail 100 chronicle-sync
```

Logged-in users can also trigger a sync from the Kontrolpanel (refresh / *Prøv igen*): this week's counts plus an incremental mirror update. It runs in the web container, so the web container needs the three `SERVICEDESK_*` variables above as well; otherwise the card shows *ServiceDesk sync er deaktiveret*.

## Troubleshooting

**Site returns 502 after a deploy** — check that both image tags exist on Docker Hub and that `chronicle-web` is running (`docker ps`, `docker logs chronicle-web`). A failing migration stops the entrypoint before gunicorn starts.

**Every form submit returns 403** — the browser's origin is missing from `CSRF_TRUSTED_ORIGINS` (see Configuration). Since failed HTMX requests show an error toast, "the button does nothing" plus a 403 toast points here.

**Helpdesk numbers or Statistik are stale** — check `docker logs chronicle-sync`. If the container keeps exiting, `SERVICEDESK_SYNC_ENABLED` is probably not `True`. Test the API key with `docker exec chronicle-sync python manage.py sync_servicedesk`.

**"Database is locked" (SQLite)** — web and sync write to the same file. Occasional locks resolve on the next cycle; if they persist, raise `SERVICEDESK_SYNC_INTERVAL` or move to PostgreSQL.
