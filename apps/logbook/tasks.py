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
    - Updates helpdesk_new and helpdesk_closed counts
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

    # Update WeekLog
    weeklog.helpdesk_new = stats["created"]
    weeklog.helpdesk_closed = stats["closed"]
    weeklog.helpdesk_open = stats["open"]
    weeklog.save(update_fields=["helpdesk_new", "helpdesk_closed", "helpdesk_open", "updated_at"])

    logger.info(
        "Updated %s: new=%d, closed=%d, open=%d",
        weeklog.week_label,
        stats["created"],
        stats["closed"],
        stats["open"],
    )
