# FynBus Chronicle

The weekly log and dashboard of the FynBus IT department — **version 1.1**.

Chronicle is where the IT department plans, records and looks back on its work: the week log with priority tasks, incidents and staffing, live helpdesk figures from ManageEngine ServiceDesk Plus, the on-call rota, statistics and shareable reports.

## Features

- **Kontrolpanel**: a live dashboard — open tickets and the change since last week, incidents, the current week's tasks, open tickets by technician, category and age, the newest and oldest unsolved tickets (linked into ServiceDesk), and trends. Refreshes itself; flags a failing sync.
- **Week logs**: priority tasks that live across weeks (Markdown, pasted images, merge, reopen, auto-close after six weeks), incidents, absences, meeting minutes and sign-off. Task search across all weeks.
- **Exports**: the week report and a task's history as PDF, HTML, Markdown and email (Microsoft Graph), with a confirmation step before sending.
- **ServiceDesk Plus integration**: weekly helpdesk figures and age buckets, plus a local mirror of every ticket (subject, category, technician, department) kept in sync by a separate container.
- **Statistik**: helpdesk and Chronicle statistics for any period, exportable as PDF/HTML/Markdown/JSON, with expiring share links for tools that cannot log in.
- **Rådighedsvagt**: on-call calendar with split weeks, mid-week handovers, history and notifications.
- **CVE'er (Sårbarheder)**: tracked vulnerabilities with CVSS, state (identified → patching → solved), links and a comment timeline; a Kontrolpanel card, an automatic section in each week log, and API endpoints for Harbinger.
- **Forslag**: a feature-request board; **Rapporter**: standalone HTML reports with optional video and public links.
- **REST API** under `/api/v1/` with per-user read or read/write API keys (used by the Claude MCP connector).
- **v3 design**: sidebar shell, light and dark mode, accent colours, density modes, and day themes (Star Wars, Pirate Day, Star Trek, World Alzheimer's Day, Read-only Friday, Touch-Grass-Weekend).
- **Office 365 SSO** (optional) and two roles: editor and read-only viewer.

## Tech Stack

- **Backend**: Django 5.0+
- **Frontend**: HTMX + Alpine.js + Tailwind CSS
- **Database**: SQLite (default) / PostgreSQL (production)
- **PDF Export**: WeasyPrint
- **Auth**: Django Allauth with Office 365 SSO support
- **Charts**: Chart.js (web), matplotlib (PDF/email)
- **Tests**: pytest
- **Containerization**: Docker (web + ServiceDesk sync), images built by GitHub Actions

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone and start
git clone <repository-url>
cd fynbus-chronicle
cp .env.example .env

# Start development server
docker compose up
```

Access at: http://localhost:8000

### Option 2: Local Development

```bash
# Prerequisites: Python 3.12+, Node.js 20+

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements/dev.txt
npm install

# Setup environment
cp .env.example .env
# Edit .env with your settings

# Build CSS and run
npm run build:css
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Documentation

- [User Guide](docs/USER_GUIDE.md) — for colleagues (Danish)
- [Setup Guide](docs/SETUP.md) — local installation
- [Development Guide](docs/DEVELOPMENT.md) — structure, conventions, tests and the release routine
- [Deployment Guide](docs/DEPLOYMENT.md) — Docker images, GitOps deploy and the sync container
- [SSO Setup](docs/SSO_SETUP.md) — Office 365 sign-in
- [Email Setup](docs/GRAPH_EMAIL_SETUP.md) — SMTP or Microsoft Graph
- [CHANGELOG](CHANGELOG.md) — every release (Danish)

The same documents are available inside Chronicle under **Dokumentation**.

## License

MIT License — see [LICENSE](LICENSE).
