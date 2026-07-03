"""Views for the notification bell: badge polling and the dropdown panel."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Notification

#: How many notifications the dropdown panel shows.
PANEL_LIMIT = 15


@login_required
def badge(request: HttpRequest) -> HttpResponse:
    """Self-polling unread-count badge on the bell (feedback badge pattern)."""
    return render(
        request,
        "notifications/_badge.html",
        {"unread_count": Notification.unread_count(request.user)},
    )


@login_required
@require_POST
def panel(request: HttpRequest) -> HttpResponse:
    """Dropdown panel content. Opening it marks the shown items as read.

    POST, not GET: marking read is a state change and must not be
    triggerable by a cross-site link. Only the displayed items are
    marked — older unread ones keep counting in the badge until they
    scroll into the panel. The response carries an out-of-band badge
    swap so the count updates the moment the panel opens.
    """
    notifications = list(
        Notification.objects.filter(recipient=request.user).select_related("actor")[:PANEL_LIMIT]
    )
    # Remember which ones were unread so the panel can highlight them,
    # then clear the flag — "read when opened".
    unread_pks = [n.pk for n in notifications if not n.is_read]
    for notification in notifications:
        notification.was_unread = not notification.is_read
    Notification.objects.filter(pk__in=unread_pks).update(read_at=timezone.now())

    return render(
        request,
        "notifications/_panel.html",
        {
            "notifications": notifications,
            "unread_count": Notification.unread_count(request.user),
            "badge_oob": True,
        },
    )
