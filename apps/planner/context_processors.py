"""Template context for the Planner nav item."""

from django.conf import settings


def planner_nav(request) -> dict:
    return {"planner_enabled": settings.PLANNER_ENABLED}
