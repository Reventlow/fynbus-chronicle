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
    """Compatibility shim. Use the ``active_theme`` processor instead.

    Returns ``IS_STAR_WARS_DAY = True`` whenever ``ACTIVE_THEME`` resolves
    to the ``star-wars`` slug — covers both the schedule-driven default
    and the user/query-param override paths so existing template
    references keep working.
    """
    # Computed by active_theme(); avoid duplicating the lookup.
    ctx = active_theme(request)
    return {"IS_STAR_WARS_DAY": ctx.get("ACTIVE_THEME") == "star-wars"}


def active_theme(request):
    """Resolve the visual theme that should be applied to this response.

    Order of precedence:

    1. ``?force-theme=<slug>`` query param (preview hatch).
    2. Any ``ThemeSchedule`` whose ``start_date <= today <= end_date``.
       Earliest start_date wins on overlap. Schedule-based themes
       override user preferences globally.
    3. ``None`` server-side. The base.html Alpine layer applies the
       user's localStorage pick if and only if the server didn't set
       ``data-event``.

    Exposes both ``ACTIVE_THEME`` (slug or empty) and ``ACTIVE_THEMES``
    (the queryset of selectable themes for the tweaks panel dropdown).
    """
    # Avoid an import cycle at module load.
    from apps.themes.models import Theme

    slug = ""

    if request is not None:
        forced = (request.GET.get("force-theme") or "").strip().lower()
        # Backward-compat with the old ?force-star-wars=1 query param.
        if forced:
            slug = forced
        elif request.GET.get("force-star-wars") == "1":
            slug = "star-wars"

    if not slug:
        scheduled = Theme.scheduled_for_today()
        if scheduled is not None:
            slug = scheduled.slug

    selectable = (
        Theme.objects.filter(is_active=True, user_selectable=True).order_by("name")
    )

    return {
        "ACTIVE_THEME": slug,
        "ACTIVE_THEMES": selectable,
    }
