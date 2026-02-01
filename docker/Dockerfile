# FynBus Chronicle Production Dockerfile
# Multi-stage build for optimized image size

# Stage 1: Build Tailwind CSS
FROM node:20-alpine AS tailwind-builder

WORKDIR /build

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install

# Copy Tailwind config and source CSS
COPY tailwind.config.js ./
COPY static/src/ ./static/src/
COPY templates/ ./templates/
COPY apps/ ./apps/

# Build CSS
RUN npm run build:css

# Stage 2: Python dependencies
FROM python:3.12-slim AS python-builder

WORKDIR /build

# Install build dependencies for WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libharfbuzz-subset0 \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements/prod.txt ./
RUN pip install --no-cache-dir -r prod.txt

# Stage 3: Production image
FROM python:3.12-slim AS production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=chronicle.settings.prod

WORKDIR /app

# Install runtime dependencies for WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libharfbuzz-subset0 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=python-builder /opt/venv /opt/venv

# Copy application code
COPY manage.py ./
COPY chronicle/ ./chronicle/
COPY apps/ ./apps/
COPY templates/ ./templates/
COPY static/ ./static/

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
CMD ["gunicorn", "chronicle.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
