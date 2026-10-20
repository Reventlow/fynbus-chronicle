# Setup Guide

This guide covers setting up FynBus Chronicle for local development. Production is described in [DEPLOYMENT.md](DEPLOYMENT.md).

## Prerequisites

- **Python 3.12+** (the Docker images and CI use 3.12)
- **Node.js 20+** and **npm** (Tailwind CSS build only)
- **WeasyPrint system libraries** for PDF export

### WeasyPrint libraries

```bash
# Arch Linux
paru -S pango cairo gdk-pixbuf2 libffi shared-mime-info

# Debian/Ubuntu
sudo apt install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info
```

## Installation

### 1. Clone and create a virtual environment

```bash
git clone <repository-url>
cd fynbus-chronicle
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements/dev.txt   # base.txt + pytest, ruff, debug tools
npm install                           # Tailwind CSS
```

### 3. Configure the environment

```bash
cp .env.example .env
```

Settings are read with python-decouple from environment variables or `.env`. For local development you only need:

```env
SECRET_KEY=<any long random string>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

Generate a key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

`manage.py` uses `chronicle.settings.dev` by default. In dev settings, email is always printed to the console (the Graph/SMTP settings have no effect), password validation is off, and session/CSRF cookies work over plain HTTP.

### 4. Build the CSS

```bash
npm run build:css   # one-off build into static/css/output.css
npm run watch:css   # rebuild on change
```

### 5. Create the database

```bash
python manage.py migrate
python manage.py createsuperuser
```

SQLite is used unless `DATABASE_URL` is set; the file is `db.sqlite3` in the project root (or in `SQLITE_DIR`). Migrations also create the **Viewer** group and seed the day themes.

### 6. Run the server

```bash
python manage.py runserver
```

Open http://localhost:8000 — you are sent to the login page, then to the Kontrolpanel at `/dashboard/`.

Run the CSS watcher in a second terminal while you work on templates.

### Alternative: Docker Compose for development

`docker-compose.yml` builds `docker/Dockerfile.dev`, mounts the source, runs the CSS watcher, migrates and starts `runserver` on port 8000:

```bash
docker compose up
```

## Roles

Users in the **Viewer** group are read-only: they see every page but cannot create, edit, delete, reorder or export. Everyone else is an editor; staff users always have full access. Add a user to the group in Django Admin at `/admin/auth/group/`.

## Optional integrations

None of these are needed to run Chronicle locally.

- **Office 365 SSO** — set `SSO_ENABLED=True` and the `MICROSOFT_*` variables. See [SSO_SETUP.md](SSO_SETUP.md).
- **Email via Microsoft Graph** — `EMAIL_USE_GRAPH=True` reuses the `MICROSOFT_*` app registration (needs the Mail.Send application permission). See [GRAPH_EMAIL_SETUP.md](GRAPH_EMAIL_SETUP.md). Only takes effect with prod settings.
- **ServiceDesk Plus** — set `SERVICEDESK_URL`, `SERVICEDESK_API_KEY` and `SERVICEDESK_SYNC_ENABLED=True` (every sync path checks it), then fill data by hand:

  ```bash
  python manage.py sync_servicedesk              # this week's ticket counts
  python manage.py sync_helpdesk_tickets --full  # ticket mirror for Statistik and the Kontrolpanel
  ```

  Or run the same loop as production: `python manage.py run_scheduler`.

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | Required |
| `DEBUG` | Debug mode (dev settings force `True`, prod `False`) | `False` |
| `ALLOWED_HOSTS` | Comma-separated hosts | `localhost` |
| `DATABASE_URL` | PostgreSQL URL; empty means SQLite (PostgreSQL needs `psycopg` from `requirements/prod.txt`) | empty |
| `SQLITE_DIR` | Directory of `db.sqlite3` | project root |
| `REPORT_FILES_DIR` | Report video files | `<SQLITE_DIR>/report_files` |
| `IMAGE_FILES_DIR` | Pasted images | `<SQLITE_DIR>/image_files` |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated origins incl. scheme (and port if not 443) | empty |
| `SECURE_SSL_REDIRECT` | Redirect HTTP to HTTPS (prod settings only) | `False` |
| `SSO_ENABLED` | Enable Office 365 login | `False` |
| `MICROSOFT_CLIENT_ID` | Azure AD app client ID (SSO and Graph email) | empty |
| `MICROSOFT_CLIENT_SECRET` | Azure AD app secret | empty |
| `MICROSOFT_TENANT_ID` | Azure AD tenant ID | `common` |
| `EMAIL_USE_GRAPH` | Send email via Microsoft Graph instead of SMTP | `False` |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_USE_TLS` | SMTP server | empty / `587` / `True` |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP login | empty |
| `DEFAULT_FROM_EMAIL` | Sender address | `it@fynbus.dk` |
| `CHRONICLE_EMAIL_RECIPIENTS` | Comma-separated recipients of email exports (week report, priority task) | empty |
| `SERVICEDESK_URL` | ServiceDesk Plus base URL | empty |
| `SERVICEDESK_API_KEY` | ServiceDesk Plus technician API key | empty |
| `SERVICEDESK_SYNC_ENABLED` | Master switch for all ServiceDesk syncs: scheduler, management commands and the Kontrolpanel sync button | `False` |
| `SERVICEDESK_SYNC_INTERVAL` | Seconds between scheduler cycles | `300` |

## Everyday commands

```bash
python manage.py makemigrations && python manage.py migrate
.venv/bin/python -m pytest -q
.venv/bin/ruff check <changed files>
```

Reset the local database (development only):

```bash
rm db.sqlite3 && python manage.py migrate && python manage.py createsuperuser
```

## Troubleshooting

### PDF export fails

WeasyPrint cannot find Pango/Cairo — install the libraries listed under Prerequisites.

### Page has no styling

Build the CSS (`npm run build:css`) and check that `static/css/output.css` exists.

### "Database is locked" (SQLite)

Two processes are writing at once, typically `runserver` and `run_scheduler`. Restart one of them, or use PostgreSQL via `DATABASE_URL`.

## Next Steps

- [Development Guide](DEVELOPMENT.md) — structure, patterns, testing and releasing
- [Deployment](DEPLOYMENT.md) — production on fbdocker01
- [SSO Setup](SSO_SETUP.md) and [Graph Email Setup](GRAPH_EMAIL_SETUP.md)
