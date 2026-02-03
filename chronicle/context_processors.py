"""
Custom context processors for Chronicle.

Makes common variables available to all templates.
"""

from pathlib import Path

from django.conf import settings


def version(request):
    """
    Add the application version to template context.

    Reads version from version.txt in the project root.
    """
    version_file = Path(settings.BASE_DIR) / "version.txt"

    try:
        app_version = version_file.read_text().strip()
    except FileNotFoundError:
        app_version = "unknown"

    return {"APP_VERSION": app_version}
