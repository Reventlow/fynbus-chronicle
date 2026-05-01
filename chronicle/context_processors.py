"""
Custom context processors for Chronicle.

Makes common variables available to all templates.
"""

from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.utils import timezone as django_timezone


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


def star_wars_day(request):
    """
    Expose IS_STAR_WARS_DAY = True on May 4 (Europe/Copenhagen), or when the
    request carries ?force-star-wars=1 (preview hatch for screenshots and
    pre-flight checks). The skin disappears automatically the next day —
    no cleanup needed.
    """
    today = django_timezone.localdate()
    is_sw_day = today.month == 5 and today.day == 4
    if not is_sw_day and request is not None and request.GET.get("force-star-wars") == "1":
        is_sw_day = True
    return {"IS_STAR_WARS_DAY": is_sw_day}
