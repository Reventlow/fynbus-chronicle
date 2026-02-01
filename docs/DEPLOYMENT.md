# Deployment Guide

This guide covers deploying FynBus Chronicle to production.

## Docker Deployment (Recommended)

### Prerequisites

- Docker and Docker Compose installed
- Domain name configured (optional but recommended)
- SSL certificate (Let's Encrypt recommended)

### Quick Deploy

```bash
# Clone repository
git clone <repository-url>
cd fynbus-chronicle

# Create production environment file
cp .env.example .env.prod

# Edit .env.prod with production settings
nano .env.prod

# Start services
docker compose -f docker-compose.prod.yml up -d
```

### Production Environment Variables

```env
# Required
SECRET_KEY=<generate-strong-key>
DEBUG=False
ALLOWED_HOSTS=chronicle.fynbus.dk

# Database
POSTGRES_DB=fynbus_chronicle
POSTGRES_USER=chronicle
POSTGRES_PASSWORD=<strong-password>
DATABASE_URL=postgres://chronicle:<password>@db:5432/fynbus_chronicle

# Security
CSRF_TRUSTED_ORIGINS=https://chronicle.fynbus.dk
SECURE_SSL_REDIRECT=True

# Email (Optional)
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_HOST_USER=it@fynbus.dk
EMAIL_HOST_PASSWORD=<password>
DEFAULT_FROM_EMAIL=it@fynbus.dk
CHRONICLE_EMAIL_RECIPIENTS=manager@fynbus.dk,team@fynbus.dk

# SSO (Optional)
SSO_ENABLED=True
MICROSOFT_CLIENT_ID=<app-id>
MICROSOFT_CLIENT_SECRET=<secret>
MICROSOFT_TENANT_ID=<tenant-id>
```

Generate a secure secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Build and Start

```bash
# Build images
docker compose -f docker-compose.prod.yml build

# Start services
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f web

# Create superuser
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

## Nginx Reverse Proxy

Example nginx configuration:

```nginx
server {
    listen 80;
    server_name chronicle.fynbus.dk;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name chronicle.fynbus.dk;

    ssl_certificate /etc/letsencrypt/live/chronicle.fynbus.dk/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/chronicle.fynbus.dk/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location /static/ {
        alias /var/www/chronicle/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/chronicle/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Database Backup

### Automated Backup Script

Create `/opt/chronicle/backup.sh`:

```bash
#!/bin/bash
set -e

BACKUP_DIR="/var/backups/chronicle"
DATE=$(date +%Y%m%d_%H%M%S)
CONTAINER="fynbus-chronicle-db-1"

mkdir -p $BACKUP_DIR

# Dump database
docker exec $CONTAINER pg_dump -U chronicle fynbus_chronicle | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Keep only last 7 days
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: db_$DATE.sql.gz"
```

Add to crontab:

```bash
0 2 * * * /opt/chronicle/backup.sh >> /var/log/chronicle-backup.log 2>&1
```

### Restore from Backup

```bash
# Stop web container
docker compose -f docker-compose.prod.yml stop web

# Restore database
gunzip -c backup.sql.gz | docker exec -i fynbus-chronicle-db-1 psql -U chronicle fynbus_chronicle

# Start web container
docker compose -f docker-compose.prod.yml start web
```

## SQLite Deployment (Simple)

For smaller installations, SQLite is sufficient:

1. Remove `db` service from docker-compose.prod.yml
2. Remove `DATABASE_URL` from environment
3. Mount a persistent volume for the SQLite file:

```yaml
volumes:
  - ./data:/app/data
```

Update settings to use `/app/data/db.sqlite3`.

## Monitoring

### Health Check Endpoint

Add to `chronicle/urls.py`:

```python
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "healthy"})

urlpatterns = [
    path("health/", health_check),
    # ... other urls
]
```

### Log Aggregation

Configure Django logging in `settings/prod.py`:

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
```

Docker logs can be collected with your preferred log aggregator.

## Updates

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# Run migrations
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs web

# Check container status
docker compose -f docker-compose.prod.yml ps
```

### Database Connection Issues

```bash
# Verify database is running
docker compose -f docker-compose.prod.yml exec db pg_isready

# Check connection from web container
docker compose -f docker-compose.prod.yml exec web python -c "
import django
django.setup()
from django.db import connection
connection.ensure_connection()
print('Database connected!')
"
```

### Static Files Not Loading

```bash
# Collect static files manually
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput

# Check static files directory
docker compose -f docker-compose.prod.yml exec web ls -la /app/staticfiles
```
