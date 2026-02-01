#!/bin/bash
set -e

# Wait for database if DATABASE_URL is set
if [ -n "$DATABASE_URL" ]; then
    echo "Waiting for database..."
    # Extract host and port from DATABASE_URL
    # Example: postgres://user:pass@host:port/dbname
    DB_HOST=$(echo $DATABASE_URL | sed -e 's/.*@//' -e 's/:.*//' -e 's/\/.*//')
    DB_PORT=$(echo $DATABASE_URL | sed -e 's/.*://' -e 's/\/.*//')

    # Default port if not specified
    if [ -z "$DB_PORT" ] || [ "$DB_PORT" = "$DB_HOST" ]; then
        DB_PORT=5432
    fi

    # Wait for database to be ready
    for i in {1..30}; do
        if python -c "import socket; socket.create_connection(('$DB_HOST', $DB_PORT), timeout=1)" 2>/dev/null; then
            echo "Database is ready!"
            break
        fi
        echo "Waiting for database... ($i/30)"
        sleep 1
    done
fi

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

# Execute the main command
exec "$@"
