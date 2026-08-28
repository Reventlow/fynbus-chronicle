"""
ServiceDesk Plus API integration service.

Handles communication with ManageEngine ServiceDesk Plus API
to fetch ticket statistics for Chronicle WeekLogs.
"""

import json
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
    # Age ("liggetid") breakdown of the open tickets, keyed by WeekLog field
    # name. Empty when the age queries could not be answered.
    open_by_age: dict[str, int]


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

        encoded_input = urllib.parse.quote(json.dumps(input_data))
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

            encoded_input = urllib.parse.quote(json.dumps(input_data))
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

    # Max rows per page and a safety valve on the number of pages, so a
    # misbehaving API can never turn the sync into an endless paging loop.
    PAGE_SIZE = 100
    MAX_PAGES = 20

    def _open_status_criterion(self) -> dict:
        """Search criterion matching every status Chronicle counts as open.

        One criterion with a ``values`` list rather than one query per
        status — the sync runs every few minutes, so the difference is five
        API calls per cycle versus one.
        """
        return {"field": "status.name", "condition": "is", "values": list(self.OPEN_STATUSES)}

    def fetch_open_requests(self, created_before_ms: int | None = None) -> list[dict] | None:
        """
        Fetch every currently open request, with its creation timestamp.

        This one listing answers both questions the sync asks — how many
        tickets are open, and how old each of them is — so the counts and
        the age breakdown can never disagree with each other.

        Args:
            created_before_ms: Only requests created at or before this
                instant. Used when reconstructing a past week.

        Returns:
            The request rows, or None if any page failed — a partial list
            would understate both the count and the breakdown.
        """
        criteria = [self._open_status_criterion()]
        if created_before_ms is not None:
            criteria.append(
                {
                    "field": "created_time",
                    "condition": "lte",
                    "value": str(created_before_ms),
                    "logical_operator": "AND",
                }
            )
        return self._fetch_paged(criteria, ["created_time", "status"])

    def _fetch_paged(self, criteria: list[dict], fields: list[str]) -> list[dict] | None:
        """Page through /requests for the given search criteria.

        Returns None if any page fails — a partial list would understate
        whatever is being counted.
        """
        if not self.base_url or not self.api_key:
            logger.warning("ServiceDesk URL or API key not configured")
            return None

        rows: list[dict] = []
        start_index = 1

        for _ in range(self.MAX_PAGES):
            input_data = {
                "list_info": {
                    "row_count": self.PAGE_SIZE,
                    "start_index": start_index,
                    "fields_required": fields,
                    "search_criteria": criteria,
                }
            }
            url = f"{self.base_url}/api/v3/requests?input_data={urllib.parse.quote(json.dumps(input_data))}"

            try:
                response = requests.get(
                    url,
                    headers={"authtoken": self.api_key, "Content-Type": "application/json"},
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError) as e:
                logger.error("ServiceDesk query failed: %s", e)
                return None

            if data.get("response_status", [{}])[0].get("status") != "success":
                logger.error("ServiceDesk query error: %s", data.get("response_status"))
                return None

            rows += data.get("requests", []) or []

            if not (data.get("list_info") or {}).get("has_more_rows"):
                return rows
            start_index += self.PAGE_SIZE

        logger.warning("ServiceDesk query hit the %d page cap", self.MAX_PAGES)
        return rows

    @staticmethod
    def _created_ms(request_row: dict) -> int | None:
        """Epoch-ms out of a request's created_time field, or None."""
        created = request_row.get("created_time")
        raw = created.get("value") if isinstance(created, dict) else created
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def fetch_open_created_times_at(self, at_ms: int) -> list[int] | None:
        """Creation timestamps of every request that was open at ``at_ms``.

        Reconstructs a past week: a ticket was open at that instant if it
        was created at or before it and either is still open now, or was
        completed afterwards. Tickets deleted or merged since then cannot
        be recovered, so the count can come out slightly below what was
        recorded at the time.

        Returns None if any query failed.
        """
        now_ms = int(datetime.now().timestamp() * 1000)

        still_open = self.fetch_open_requests(created_before_ms=at_ms)
        if still_open is None:
            return None
        created_times = [ms for ms in map(self._created_ms, still_open) if ms is not None]

        closed_since = self._fetch_paged(
            [
                {
                    "field": "completed_time",
                    "condition": "between",
                    "values": [str(at_ms), str(now_ms)],
                },
                {
                    "field": "created_time",
                    "condition": "lte",
                    "value": str(at_ms),
                    "logical_operator": "AND",
                },
            ],
            ["created_time", "completed_time", "status"],
        )
        if closed_since is None:
            return None
        created_times += [ms for ms in map(self._created_ms, closed_since) if ms is not None]

        return created_times

    @staticmethod
    def bucket_by_age(created_times_ms: list[int], now_ms: int) -> dict[str, int]:
        """
        Group creation timestamps into WeekLog age ("liggetid") buckets.

        Args:
            created_times_ms: Creation timestamps in milliseconds.
            now_ms: Reference "now" in milliseconds.

        Returns:
            Dict keyed by WeekLog field name with a count per bucket.
        """
        from ..models import WeekLog

        buckets = {field: 0 for field, *_ in WeekLog.HELPDESK_AGE_BUCKETS}

        for created_ms in created_times_ms:
            age_days = max(0, (now_ms - created_ms) // 86_400_000)
            for field, _label, _low, high, _color in WeekLog.HELPDESK_AGE_BUCKETS:
                if high is None or age_days <= high:
                    buckets[field] += 1
                    break

        return buckets

    def get_open_by_age(self) -> dict[str, int]:
        """
        Fetch the age breakdown of all currently open requests.

        Returns:
            Dict keyed by WeekLog field name, or an empty dict when the
            breakdown could not be determined.
        """
        rows = self.fetch_open_requests()
        if rows is None:
            return {}

        created_times = [ms for ms in map(self._created_ms, rows) if ms is not None]
        now_ms = int(datetime.now().timestamp() * 1000)
        return self.bucket_by_age(created_times, now_ms)

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
            return TicketStats(created=0, closed=0, open=0, open_by_age={})

        start_ms, end_ms = self._get_week_timestamps(year, week)

        created = self._query_count("created_time", start_ms, end_ms)
        closed = self._query_count("completed_time", start_ms, end_ms)

        # One listing of the open tickets answers both the count and the age
        # breakdown; three API calls per sync in total. If it fails, fall back
        # to the count-only query (one call per status) so the headline number
        # still updates and the previous breakdown is left in place.
        open_rows = self.fetch_open_requests()
        if open_rows is None:
            logger.warning("Open-ticket listing failed, falling back to count query")
            open_count = self._query_open_count()
            open_by_age: dict[str, int] = {}
        else:
            open_count = len(open_rows)
            created_times = [ms for ms in map(self._created_ms, open_rows) if ms is not None]
            open_by_age = self.bucket_by_age(
                created_times, int(datetime.now().timestamp() * 1000)
            )

        logger.info(
            "ServiceDesk stats for week %d/%d: created=%d, closed=%d, open=%d, by_age=%s",
            week,
            year,
            created,
            closed,
            open_count,
            open_by_age or "n/a",
        )

        return TicketStats(
            created=created,
            closed=closed,
            open=open_count,
            open_by_age=open_by_age,
        )
