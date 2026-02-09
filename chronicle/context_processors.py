"""
Custom context processors for Chronicle.

Makes common variables available to all templates.
"""

from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings


def version(request):
    """
    Add the application version and date to template context.

    Reads version from version.txt and its modification date.
    """
    version_file = Path(settings.BASE_DIR) / "version.txt"

    try:
        app_version = version_file.read_text().strip()
        mtime = version_file.stat().st_mtime
        version_date = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%d. %b %Y")
    except FileNotFoundError:
        app_version = "unknown"
        version_date = ""

    return {"APP_VERSION": app_version, "APP_VERSION_DATE": version_date}
