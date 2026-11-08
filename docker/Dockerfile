# FynBus Chronicle Production Dockerfile
# Multi-stage build for optimized image size

# Stage 1: Build Tailwind CSS
FROM node:26-alpine AS tailwind-builder

WORKDIR /build

# Copy package files
COPY package.json package-lock.json ./

# Install exactly what package-lock.json lists (fails if it is out of date)
RUN npm ci

# Copy Tailwind config and source CSS
COPY tailwind.config.js ./
COPY static/src/ ./static/src/
COPY templates/ ./templates/
COPY apps/ ./apps/
# Scripts that create elements with their own classes (see tailwind.config.js).
COPY static/js/description-images.js ./static/js/

# Build CSS
RUN npm run build:css

# Stage 2: Python dependencies (use full image for building - has more libs)
FROM python:3.12-bookworm AS python-builder

WORKDIR /build

# Install build dependencies for WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango1.0-dev \
    libcairo2-dev \
    libgdk-pixbuf-2.0-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies from the hash-pinned lock (see requirements/lock/)
COPY requirements/lock/requirements-prod.txt ./requirements/lock/
RUN pip install --no-cache-dir --require-hashes -r requirements/lock/requirements-prod.txt

# Stage 3: Production image
FROM python:3.12-slim AS production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=chronicle.settings.prod

WORKDIR /app

# Install runtime dependencies for WeasyPrint (Debian Bookworm packages)
# ca-certificates is listed explicitly so every build pulls the current Debian bundle
# (e.g. the 2026-10 eMudhra emSign G3 / Comodo AAA distrust) even from a stale base layer.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=python-builder /opt/venv /opt/venv

# Copy application code
COPY manage.py ./
COPY chronicle/ ./chronicle/
COPY apps/ ./apps/
# Scripts that create elements with their own classes (see tailwind.config.js).
COPY static/js/description-images.js ./static/js/
COPY templates/ ./templates/
COPY static/ ./static/
COPY docs/ ./docs/
COPY LICENSE ./
COPY CHANGELOG.md ./
COPY version.txt ./

# Copy built CSS from Tailwind builder
COPY --from=tailwind-builder /build/static/css/output.css ./static/css/output.css

# Copy entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create non-root user
RUN useradd -m -u 1000 chronicle && \
    chown -R chronicle:chronicle /app

USER chronicle

# Collect static files
RUN python manage.py collectstatic --noinput --clear 2>/dev/null || true

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
# --timeout 300: storing a large course video (up to 1.5 GB) means copying it
# from the upload temp file to the data volume, which can outlast the 30 s
# default. The proxy (NPM) buffers the upload itself, so a slow client never
# holds a worker.
CMD ["gunicorn", "chronicle.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "300"]
