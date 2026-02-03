"""
ServiceDesk Plus API integration service.

Handles communication with ManageEngine ServiceDesk Plus API
to fetch ticket statistics for Chronicle WeekLogs.
"""

import logging
import urllib.parse
from datetime import datetime, timedelta
from typing import TypedDict

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class TicketStats(TypedDict):
    """Ticket statistics for a week."""

    created: int
    closed: int
    open: int


class ServiceDeskClient:
    """
    Client for ManageEngine ServiceDesk Plus API.

    Fetches ticket counts for specified ISO weeks using the v3 API.
    """

    def __init__(self) -> None:
        """Initialize the client with settings from Django config."""
        self.base_url = getattr(settings, "SERVICEDESK_URL", "")
        self.api_key = getattr(settings, "SERVICEDESK_API_KEY", "")
        self.enabled = getattr(settings, "SERVICEDESK_SYNC_ENABLED", False)

    def _get_week_timestamps(self, year: int, week: int) -> tuple[int, int]:
        """
        Calculate start and end timestamps for an ISO week.

        Args:
            year: ISO year
            week: ISO week number

        Returns:
            Tuple of (start_ms, end_ms) Unix timestamps in milliseconds
        """
        # Get the Monday of the given ISO week
        jan4 = datetime(year, 1, 4)
        start_of_week1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
        monday = start_of_week1 + timedelta(weeks=week - 1)
        sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

        start_ms = int(monday.timestamp() * 1000)
        end_ms = int(sunday.timestamp() * 1000) + 999

        return start_ms, end_ms

    def _query_count(self, field: str, start_ms: int, end_ms: int) -> int:
        """
        Query ServiceDesk API for ticket count.

        Args:
            field: Field to filter on (created_time or completed_time)
            start_ms: Start timestamp in milliseconds
            end_ms: End timestamp in milliseconds

        Returns:
            Total count of matching tickets
        """
        if not self.base_url or not self.api_key:
            logger.warning("ServiceDesk URL or API key not configured")
            return 0

        input_data = {
            "list_info": {
                "row_count": 1,
                "get_total_count": True,
                "search_criteria": [
                    {
                        "field": field,
                        "condition": "between",
                        "values": [str(start_ms), str(end_ms)],
                    }
                ],
            }
        }

        encoded_input = urllib.parse.quote(str(input_data).replace("'", '"'))
        url = f"{self.base_url}/api/v3/requests?input_data={encoded_input}"

        try:
            response = requests.get(
                url,
                headers={
                    "authtoken": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("response_status", [{}])[0].get("status") == "success":
                return data.get("list_info", {}).get("total_count", 0)
            else:
                logger.error("ServiceDesk API error: %s", data.get("response_status"))
                return 0

        except requests.RequestException as e:
            logger.error("ServiceDesk API request failed: %s", e)
            return 0

    # Statuses considered "open" in ServiceDesk Plus
    OPEN_STATUSES = ["Åben", "I bero", "Tildelt", "I gang", "Afventer svar"]

    def _query_open_count(self) -> int:
        """
        Query ServiceDesk API for total open ticket count.

        Returns:
            Total count of open tickets (all non-closed/cancelled statuses)
        """
        if not self.base_url or not self.api_key:
            logger.warning("ServiceDesk URL or API key not configured")
            return 0

        total = 0
        for status in self.OPEN_STATUSES:
            input_data = {
                "list_info": {
                    "row_count": 1,
                    "get_total_count": True,
                    "search_criteria": [
                        {
                            "field": "status.name",
                            "condition": "is",
                            "value": status,
                        }
                    ],
                }
            }

            encoded_input = urllib.parse.quote(str(input_data).replace("'", '"'))
            url = f"{self.base_url}/api/v3/requests?input_data={encoded_input}"

            try:
                response = requests.get(
                    url,
                    headers={
                        "authtoken": self.api_key,
                        "Content-Type": "application/json",
                    },
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                if data.get("response_status", [{}])[0].get("status") == "success":
                    total += data.get("list_info", {}).get("total_count", 0)

            except requests.RequestException as e:
                logger.error("ServiceDesk API request failed for status %s: %s", status, e)

        return total

    def get_week_stats(self, year: int, week: int) -> TicketStats:
        """
        Fetch ticket counts for a specific ISO week.

        Args:
            year: ISO year
            week: ISO week number

        Returns:
            TicketStats with created and closed counts
        """
        if not self.enabled:
            logger.debug("ServiceDesk sync is disabled")
            return TicketStats(created=0, closed=0, open=0)

        start_ms, end_ms = self._get_week_timestamps(year, week)

        created = self._query_count("created_time", start_ms, end_ms)
        closed = self._query_count("completed_time", start_ms, end_ms)
        open_count = self._query_open_count()

        logger.info(
            "ServiceDesk stats for week %d/%d: created=%d, closed=%d, open=%d",
            week,
            year,
            created,
            closed,
            open_count,
        )

        return TicketStats(created=created, closed=closed, open=open_count)
