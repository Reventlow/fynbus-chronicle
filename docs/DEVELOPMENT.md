# Development Guide

This guide covers the structure, patterns and release routine of FynBus Chronicle. For a first local install, see [SETUP.md](SETUP.md).

## Project Structure

```
fynbus-chronicle/
├── chronicle/                  # Django project
│   ├── settings/               # base.py, dev.py, prod.py
│   ├── context_processors.py   # version, day theme, Read-only Friday, Touch-Grass-Weekend
│   ├── email_backends/graph.py # Microsoft Graph sendMail backend
│   └── urls.py                 # Root URL configuration
├── apps/
│   ├── accounts/       # Login/logout, LoginLog, Viewer role, API keys (api_auth.py, mint_api_key)
│   ├── api/            # JSON API under /api/v1/ (Bearer API keys)
│   ├── cves/           # Sårbarheder: CVEs with links, comment timeline and state
│   ├── dashboard/      # Kontrolpanel (overview.py), Statistik (statistics.py, exports.py), docs pages
│   ├── feedback/       # Forslag board (feature requests)
│   ├── images/         # Images pasted into descriptions, served by a login-gated view
│   ├── logbook/        # Week logs, priority tasks, incidents, absences, meeting minutes, sign-off
│   │   ├── exports/    # PDF, HTML, Markdown, email
│   │   ├── services/   # servicedesk.py (API client), ticket_mirror.py (HelpdeskTicket mirror)
│   │   ├── tasks.py    # Sync jobs run by run_scheduler
│   │   └── management/commands/
│   ├── notifications/  # In-app notifications (bell badge)
│   ├── oncall/         # On-call calendar: duties, segments, handovers, current_watch()
│   ├── reports/        # Standalone HTML reports, optional MP4 video, public token links
│   ├── tasks/          # LEGACY Opgaver app — still routed at /tasks/, not in the menu
│   └── themes/         # Day themes and schedules
├── templates/
│   ├── base.html       # Shell: sidebar, toolbar with {% block crumbs %}, HTMX error toast
│   └── components/     # sidebar.html, settings_controls.html, banners, pills, KPI cards …
├── static/
│   ├── src/input.css   # Tailwind source: design tokens + @layer components
│   ├── css/output.css  # Built CSS (npm run build:css)
│   └── js/             # htmx, Alpine.js, Chart.js, Sortable, description-images.js
├── docker/             # Dockerfile (web), Dockerfile.sync (scheduler), Dockerfile.dev, entrypoint.sh
├── docs/               # These docs — also rendered in the app under Dokumentation
├── CHANGELOG.md        # Danish release notes, newest first
└── version.txt         # Release version; CI tags the Docker images from it
```

### Apps at a glance

| App | What it does |
|-----|--------------|
| `logbook` | `WeekLog` per ISO week with priority tasks (`PriorityItem` lives across weeks, shown on each week through `PriorityItemAppearance`), incidents, absences, meeting minutes and sign-off (`WeekLogSignoff`). Exports the week report as PDF, HTML, Markdown and email. Holds the ServiceDesk integration and the `HelpdeskTicket` mirror. |
| `dashboard` | Kontrolpanel (`/dashboard/`), its HTMX partials and the helpers in `overview.py`; Statistik (`/dashboard/statistik/`) with exports (PDF/HTML/Markdown/JSON) and token share links; the docs pages (`/dashboard/docs/`). |
| `api` | REST endpoints for week logs, priority items, incidents, on-call, helpdesk data, changelog, feature requests and reports. |
| `accounts` | Login, `LoginLog`, the Viewer role (`permissions.py`) and `APIKey` (read/write scope). |
| `oncall` | `OnCallDuty`, `OnCallSegment`, `OnCallChange`; `current_watch()` returns who is on call now. |
| `feedback` | `FeatureRequest` — the Forslag board. |
| `reports` | `Report` with an optional video; files live in `REPORT_FILES_DIR`. |
| `images` | `PastedImage`; files live in `IMAGE_FILES_DIR`. |
| `themes` | `Theme`, `ThemeSchedule`, `ThemeBannerMessage`. Read-only Friday and Touch-Grass-Weekend are weekday-driven context processors in `chronicle/context_processors.py`. |
| `notifications` | `Notification` and the bell badge context processor. |
| `tasks` | Legacy, see [TASKS.md](TASKS.md). Priority tasks on the week logs replace it. |

## Code Style

### Python

- Follow PEP 8; type hints on function signatures.
- Document modules, classes and non-trivial functions. Code and comments in English; UI text in Danish.
- Lint with ruff (`pyproject.toml` selects E, F, I, N, W, UP). The tree is not ruff-clean or ruff-formatted as a whole, so run it on the files you touch rather than reformatting everything:

```bash
.venv/bin/ruff check path/to/changed_file.py
```

### Templates

- Django templates + HTMX + Alpine.js; Tailwind classes and the component classes from `input.css`.
- **`{# … #}` comments are single-line only.** A multi-line `{# … #}` is rendered as text on the page. Use `{% comment %} … {% endcomment %}` for anything longer than one line.
- Pages set their breadcrumb by overriding `{% block crumbs %}` from `base.html`; it is shown in the toolbar, not on the page.
- Hide write controls from viewers with `{% if is_editor %}` (see Permissions).

### JavaScript

- Keep it minimal: HTMX for server round-trips, Alpine.js for local state.
- Chart.js for charts. The vendored libraries live in `static/js/`.

## Frontend

### Tailwind and design tokens

`static/src/input.css` holds the v3 design system:

- `:root` design tokens as OKLCH CSS variables (`--paper`, `--surface-*`, `--ink-*`, `--accent`, `--good`, `--warn`, `--bad`, `--info`, shadows, density), redefined under `html.dark`.
- Accent variants via `html[data-accent="…"]` and day-theme skins via `html[data-event="…"]`.
- Component classes in `@layer components` (`.card`, `.pill`, `.btn`, `.btn-primary`, `.nav-link`, `.tab-link` …).

The `sand-*`, `sage-*`, `gold-*` and `terracotta-*` palettes in `tailwind.config.js` remain for older components; new components use the CSS variables.

Build the CSS after changing `input.css` or adding classes to templates:

```bash
npm run build:css   # minified build into static/css/output.css
npm run watch:css   # rebuild on change while developing
```

### Shell and settings

- `templates/components/sidebar.html` — the v3 sidebar (Kontrolpanel, Ugelog, Rådighedsvagt, CVE'er, Forslag, Rapporter, Statistik, Dokumentation), collapsible to icons.
- `templates/base.html` — toolbar with the crumbs block, mobile menu, messages and the HTMX error toast (failed requests show a toast with the status instead of failing silently).
- `templates/components/settings_controls.html` — the settings popover. Dark mode, density, accent, theme and sidebar state are Alpine state on `<html>`, persisted in `localStorage`.

### Day themes

A day theme is a seed migration in `apps/themes/migrations/` (Theme + ThemeSchedule + ThemeBannerMessage), a banner partial in `templates/components/<slug>_banner.html` included from `base.html`, an `html[data-event="<slug>"]` skin block in `input.css`, and a footer line in `components/footer.html`. Preview any theme with `?force-theme=<slug>`.

## HTMX Patterns

### CSRF

`base.html` sends the CSRF token with every HTMX request:

```html
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

### Inline CRUD

Rows are swapped in place. Priority tasks are the reference implementation:

- `logbook:priority-item-create` (`?weeklog=<id>`) returns the form; on success it creates the `PriorityItem` and its first `PriorityItemAppearance` and returns `logbook/partials/priority_item_row.html`, plus an out-of-band delete of the form container.
- `priority-item-edit`, `priority-item-delete` and `priority-item-row` take the **appearance** pk, not the `PriorityItem` pk.
- On validation errors the view sets `HX-Retarget` to `#priority-item-form-container`.

**Edit forms must target their own container**, e.g. `#incident-form-container`, not the row id they replaced — that element no longer exists after the swap. See `priority_item_form.html` and `absence_form.html`.

### Dates in forms

Fields rendered with `<input type="datetime-local">` need `localize=False` on the form field; Django's localisation otherwise ignores the widget's format and the input stays empty.

## Permissions

Users in the **Viewer** group are read-only. Everyone else is an editor; staff always are. The group is created by migration `accounts/0001_create_viewer_group`.

| Component | Location | Purpose |
|-----------|----------|---------|
| `is_editor(user)` | `apps/accounts/permissions.py` | `False` for Viewer members (staff always `True`) |
| `EditorRequiredMixin` | `apps/accounts/permissions.py` | CBV mixin — 403 for viewers, checked *before* the view runs |
| `@editor_required` | `apps/accounts/permissions.py` | FBV decorator — same check |
| `editor_context` | `apps/accounts/context_processors.py` | `is_editor` in every template |

```python
from apps.accounts.permissions import EditorRequiredMixin, editor_required

class MyCreateView(EditorRequiredMixin, CreateView):
    ...

@login_required
@editor_required
def my_write_view(request):
    ...
```

## API

- Endpoints in `apps/api/urls.py`, mounted at `/api/v1/`.
- Auth: `Authorization: Bearer <key>`, handled by `@api_auth(scope="read"|"write")` in `apps/accounts/api_auth.py`. Read endpoints accept read and write keys; write endpoints need a write key. API views are CSRF-exempt.
- Users create, re-roll and revoke keys at `/accounts/api-keys/`. For scripts or break-glass: `python manage.py mint_api_key <username> --scope=write --label="…"` (prints the key once).
- The API under `/api/v1/` changes only backwards-compatibly (promise since 1.0).

### CVE endpoints

Used by Harbinger. They validate every field (choices included) and answer `400 {"error", "field"?, "detail"}` on bad input; `error` is `invalid_body`, `missing_field` or `invalid_field`.

| Method | Path | Scope | Purpose |
|--------|------|-------|---------|
| `GET` | `/api/v1/cves/` | read | All CVEs, open first. `?state=identified\|patching\|solved` |
| `POST` | `/api/v1/cves/` | write | Create a CVE — or, if the id exists, leave its fields alone and add `comment` |
| `GET` | `/api/v1/cves/<cve_id>/` | read | One CVE (id case-insensitive) with `links` and `comments`; 404 if unknown |
| `GET` | `/api/v1/cve-cases/` | read | All CVE cases, open first, each with its `cves` |
| `POST` | `/api/v1/cve-cases/` | write | Create a case (`title`, `assessment`, `solution`, `source`, `reference`, `source_url`, `comment`, `state`, `resolution`, `cves: [{cve_id, subject, …}]`), or extend one with `id`. Unknown CVEs are created; a CVE already in another case → 409 and nothing changes. 201 created / 200 updated |
| `GET` | `/api/v1/cve-cases/<id>/` | read | One case |

`POST` body: `cve_id` and `subject` (≤ 300 chars) are required; `cvss` (number 0–10), `severity` (`critical`, `high`, `medium`, `low`, `none`; derived from `cvss` when null), `cvefeed_url`, `source_url` (http(s)) and `comment` (Markdown) may be null. `source` is set to `harbinger` when `source_url` is given, else `api`. Answers `201` when created and `200` when the CVE existed, both with:

```json
{"id": 7, "cve_id": "CVE-2026-109618", "subject": "OpenSSH regreSSHion igen",
 "cvss": 9.8, "severity": "critical", "state": "identified",
 "url": "https://chronicle.fynbus.net/cves/7/", "created": true}
```

The `GET` detail adds `state_display`, `severity_display`, `cvefeed_url`, `source`, `source_url`, `created_at`, `updated_at`, `solved_at`, `links` (`url`, `label`, `added_at`) and `comments` (`text`, `kind` = `comment`|`state`, `author`, `created_at`; newest first). The list items have the `POST` shape without `created`.

The new-CVE form can also be prefilled by a link: `/cves/new/?cve_id=…&subject=…&cvss=…&severity=…&cvefeed_url=…&source_url=…` (an existing id redirects to that CVE).

The Statistik share links (`/dashboard/statistik/delt/<token>/data.json` and `vejledning.md`) live in the dashboard app, not in the API, and use the token in the URL instead of an API key.

## ServiceDesk integration

- `apps/logbook/services/servicedesk.py` — `ServiceDeskClient`, configured by `SERVICEDESK_URL` and `SERVICEDESK_API_KEY`.
- `apps/logbook/services/ticket_mirror.py` — keeps the `HelpdeskTicket` mirror in step (`sync_full`, `sync_incremental`). Statistik and the open-ticket cards on the Kontrolpanel read from it.
- `apps/logbook/tasks.py` — `sync_current_week_tickets()` and `sync_ticket_mirror(full=…)`, run by `run_scheduler`. The Kontrolpanel sync button (`sync_servicedesk_stats` in `apps/dashboard/views.py`) does the same work inline, with an incremental mirror update.
- Every sync path is a no-op unless `SERVICEDESK_SYNC_ENABLED=True`.

Management commands (all in `apps/logbook/management/commands/`):

| Command | Purpose |
|---------|---------|
| `run_scheduler` | Loop used by the sync container (see [DEPLOYMENT.md](DEPLOYMENT.md)) |
| `sync_servicedesk [--all]` | Sync week ticket counts for the current week, or all week logs |
| `sync_helpdesk_tickets [--full]` | Refresh the ticket mirror (changed tickets, or full rebuild) |
| `backfill_liggetid <year> <week> [--dry-run]` / `--all-missing` | Rebuild a past week's open-ticket age breakdown |

## Adding features

### New model

1. Model in the app's `models.py`, form in `forms.py`, admin in `admin.py`.
2. Views — protect writes with `EditorRequiredMixin` / `@editor_required`.
3. Templates: page plus `partials/` row and form for HTMX.
4. URL patterns.
5. `python manage.py makemigrations && python manage.py migrate` and commit the migration.

### New Kontrolpanel card

1. View in `apps/dashboard/views.py` (logic that can be tested on its own goes in `overview.py`).
2. Partial in `templates/dashboard/partials/`.
3. URL in `apps/dashboard/urls.py`.
4. An `hx-get` loader in `templates/dashboard/index.html`.

## Testing

pytest with pytest-django (`DJANGO_SETTINGS_MODULE = chronicle.settings.dev` from `pyproject.toml`). Tests live in `apps/<app>/tests/` (about 440 tests).

```bash
.venv/bin/python -m pytest -q                 # everything
.venv/bin/python -m pytest -q apps/logbook    # one app
.venv/bin/python -m pytest -q -k signoff      # by name
```

CI runs `python manage.py check` and the same `python -m pytest -q` (see below), so a failing test stops the release before any image is built. Run it locally before pushing.

## Releasing

Work is committed to `main`. Every push to `main` builds and pushes Docker images tagged with the version in `version.txt`, so a push that ships code must carry a new version.

1. **Bump `version.txt`** — the only place the version lives (`pyproject.toml` reads it too). CI tags both Docker images from this file, not from the changelog. Forgetting it once made CI overwrite the previous version's tag.
2. **Add a CHANGELOG.md entry at the top**, in Danish:

   ```markdown
   ## X.Y.Z — YYYY-MM-DD

   ### Added
   - …

   ### Changed
   - …

   ### Fixed
   - …
   ```

   Use only the sections you need. Check that the heading matches `version.txt`.
3. **Pick the version:** patch bump (X.Y.Z+1) for follow-ups within a feature, minor bump (X.Y+1.0) for a new feature line.
4. Run the tests: `.venv/bin/python -m pytest -q`.
5. **Commit GPG-signed** (`git commit -S`, or with `commit.gpgsign` set) and push to `main`.
6. CI builds and pushes the images. Deploy as described in [DEPLOYMENT.md](DEPLOYMENT.md).

### CI

`.github/workflows/ci_cd.yml`:

- **On push and pull request to `main`:** `test` job — Python 3.12, `pip install -r requirements/dev.txt`, `python manage.py check`, `python -m pytest -q`.
- **On push to `main` only, after tests pass:** `build` job — builds and pushes
  - `elohite/chronicle:<version.txt>` and `:latest` from `docker/Dockerfile`
  - `elohite/chronicle_sync_servicedesk:<version.txt>` and `:latest` from `docker/Dockerfile.sync`

Docker Hub credentials come from the repository secrets `DOCKER_HUB_USERNAME` and `DOCKER_HUB_ACCESS_TOKEN`.
