"""
Scheduled tasks for logbook app.

Uses django-apscheduler for periodic execution of background tasks.
"""

import logging

from apps.logbook.models import WeekLog
from apps.logbook.services.servicedesk import ServiceDeskClient

logger = logging.getLogger(__name__)


def sync_current_week_tickets() -> None:
    """
    Sync ticket counts for the current week from ServiceDesk Plus.

    This task:
    - Creates the current week's WeekLog if it doesn't exist
    - Fetches ticket statistics from ServiceDesk Plus API
    - Updates helpdesk_new, helpdesk_closed and open-ticket age buckets
    """
    client = ServiceDeskClient()

    if not client.enabled:
        logger.debug("ServiceDesk sync is disabled, skipping")
        return

    # Get or create current week's WeekLog
    weeklog = WeekLog.get_or_create_current_week()
    logger.info("Syncing tickets for %s", weeklog.week_label)

    # Fetch stats from ServiceDesk
    stats = client.get_week_stats(weeklog.year, weeklog.week_number)

    # Update WeekLog (including the open-ticket age breakdown, when the
    # sync managed to fetch it)
    weeklog.apply_helpdesk_stats(stats)

    logger.info(
        "Updated %s: new=%d, closed=%d, open=%d, by_age=%s",
        weeklog.week_label,
        stats["created"],
        stats["closed"],
        stats["open"],
        stats.get("open_by_age") or "n/a",
    )
