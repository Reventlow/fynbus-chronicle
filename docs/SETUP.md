# Setup Guide

This guide covers setting up FynBus Chronicle for local development.

## Prerequisites

### Required Software

- **Python 3.12+**: `python --version`
- **Node.js 20+**: `node --version`
- **npm**: `npm --version`

### Arch Linux Specific

For WeasyPrint PDF generation on Arch Linux:

```bash
paru -S pango cairo gdk-pixbuf2 libffi shared-mime-info
```

Or with pacman:

```bash
sudo pacman -S pango cairo gdk-pixbuf2 libffi shared-mime-info
```

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd fynbus-chronicle
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements/dev.txt
```

### 4. Install Node Dependencies

```bash
npm install
```

### 5. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Required
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Optional: Database (leave empty for SQLite)
# DATABASE_URL=postgres://user:password@localhost:5432/fynbus_chronicle

# Optional: Office 365 SSO
SSO_ENABLED=False
# MICROSOFT_CLIENT_ID=
# MICROSOFT_CLIENT_SECRET=
# MICROSOFT_TENANT_ID=
```

Generate a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 6. Build Tailwind CSS

```bash
npm run build:css
```

For development with auto-rebuild:

```bash
npm run watch:css
```

### 7. Initialize Database

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 8. Create Viewer Group

The migration creates a "Viewer" auth group automatically when you run migrations (step 7). To restrict a user to read-only access:

1. Go to Django Admin: `http://localhost:8000/admin/auth/group/`
2. Click on the "Viewer" group
3. Add users to the group

Users in the Viewer group can see all pages but cannot create, edit, delete, reorder, or export anything. Staff users always have full access regardless of group membership.

### 9. Run Development Server

```bash
python manage.py runserver
```

Access at: http://localhost:8000

## Development Workflow

### Running Both CSS Watch and Django Server

In separate terminals:

```bash
# Terminal 1: CSS watcher
npm run watch:css

# Terminal 2: Django server
python manage.py runserver
```

Or use the provided script (if available) or tmux/screen.

### Database Commands

```bash
# Create new migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Reset database (development only)
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | Required |
| `DEBUG` | Debug mode | `False` |
| `ALLOWED_HOSTS` | Comma-separated hosts | `localhost` |
| `DATABASE_URL` | PostgreSQL connection string | SQLite |
| `SSO_ENABLED` | Enable Office 365 SSO | `False` |
| `MICROSOFT_CLIENT_ID` | Azure AD app client ID | - |
| `MICROSOFT_CLIENT_SECRET` | Azure AD app secret | - |
| `MICROSOFT_TENANT_ID` | Azure AD tenant ID | `common` |
| `EMAIL_USE_GRAPH` | Use Microsoft Graph API for email | `False` |
| `EMAIL_HOST` | SMTP server | - |
| `EMAIL_PORT` | SMTP port | `587` |
| `EMAIL_HOST_USER` | SMTP username | - |
| `EMAIL_HOST_PASSWORD` | SMTP password | - |
| `DEFAULT_FROM_EMAIL` | Default sender email | `it@fynbus.dk` |
| `CHRONICLE_EMAIL_RECIPIENTS` | Comma-separated email recipients | - |
| `SERVICEDESK_URL` | ServiceDesk Plus base URL | `https://servicedesk.fynbus.dk` |
| `SERVICEDESK_API_KEY` | ServiceDesk Plus API technician key | - |
| `SERVICEDESK_SYNC_ENABLED` | Enable automatic ticket sync | `False` |
| `SERVICEDESK_SYNC_INTERVAL` | Sync interval in seconds | `300` (5 min) |

## Troubleshooting

### WeasyPrint Errors

If PDF generation fails with missing library errors:

```bash
# Arch Linux
paru -S pango cairo gdk-pixbuf2

# Ubuntu/Debian
sudo apt install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0
```

### Tailwind CSS Not Loading

1. Ensure CSS is built: `npm run build:css`
2. Check `static/css/output.css` exists
3. Verify `STATICFILES_DIRS` in settings includes the static folder

### Database Locked (SQLite)

This can happen with concurrent access. Either:
- Restart the development server
- Switch to PostgreSQL for multi-user development

## Next Steps

- [Development Guide](DEVELOPMENT.md) - Coding standards and patterns
- [SSO Setup](SSO_SETUP.md) - Configure Office 365 authentication
- [Graph Email Setup](GRAPH_EMAIL_SETUP.md) - Send email via Microsoft Graph API
