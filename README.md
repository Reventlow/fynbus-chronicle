# FynBus Chronicle

IT Weekly Logbook System for FynBus IT department.

## Overview

FynBus Chronicle is a Django-based application for tracking weekly IT activities including:
- Helpdesk ticket statistics
- Priority tasks and projects
- Staff absences
- Security and system incidents

## Tech Stack

- **Backend**: Django 5.0+
- **Frontend**: HTMX + Alpine.js + Tailwind CSS
- **Database**: SQLite (default) / PostgreSQL (production)
- **PDF Export**: WeasyPrint
- **Auth**: Django Allauth with Office 365 SSO support
- **Containerization**: Docker

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

## Features

- **Dashboard**: Overview of current week, helpdesk chart, recent incidents
- **HTMX Forms**: Inline add/edit/delete without page reloads
- **Exports**: PDF, Markdown, and Email reports
- **Dark Mode**: Scandinavian-themed light/dark mode
- **Office 365 SSO**: Optional Microsoft authentication

## Documentation

- [Setup Guide](docs/SETUP.md) - Detailed installation instructions
- [Development Guide](docs/DEVELOPMENT.md) - Development workflow
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment
- [User Guide](docs/USER_GUIDE.md) - End-user documentation (Danish)
- [SSO Setup](docs/SSO_SETUP.md) - Office 365 configuration

## Screenshots

### Dashboard (Light Mode)
The dashboard provides an overview of the current week's activities with helpdesk statistics and recent incidents.

### Week Log Detail (Dark Mode)
Detailed view of a weekly log with inline editing of priority items, absences, and incidents.

## License

MIT License - FynBus IT 2024
