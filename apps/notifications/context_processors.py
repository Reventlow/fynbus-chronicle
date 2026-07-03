"""Context processor exposing the unread notification count to every template.

Adds ``UNREAD_NOTIFICATIONS_COUNT`` so the nav bell badge renders correctly
on initial page load, before the 60s HTMX poll takes over.
"""

from .models import Notification


def notifications_badge(request):
    if not request.user.is_authenticated:
        return {"UNREAD_NOTIFICATIONS_COUNT": 0}
    return {"UNREAD_NOTIFICATIONS_COUNT": Notification.unread_count(request.user)}
