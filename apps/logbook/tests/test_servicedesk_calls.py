"""How many ServiceDesk API calls a sync cycle costs.

The scheduler runs every SERVICEDESK_SYNC_INTERVAL seconds (300 by
default), so each extra call per cycle is ~288 extra calls a day. These
tests pin the budget so a future change cannot quietly multiply it.
"""

import json
import urllib.parse
from unittest.mock import patch

import pytest

from apps.logbook.models import WeekLog
from apps.logbook.services.servicedesk import ServiceDeskClient

pytestmark = pytest.mark.django_db

DAY_MS = 86_400_000


class FakeResponse:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class FakeServiceDesk:
    """Records every call and answers list/count queries plausibly."""

    def __init__(self, open_tickets: int = 35, fail_listing: bool = False):
        self.calls: list[dict] = []
        self.open_tickets = open_tickets
        self.fail_listing = fail_listing

    def __call__(self, url, headers=None, timeout=None):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        payload = json.loads(query["input_data"][0])
        info = payload["list_info"]
        self.calls.append(info)

        criteria = info.get("search_criteria", [])
        is_status_query = any(c.get("field") == "status.name" for c in criteria)
        wants_rows = info.get("row_count", 1) > 1

        if is_status_query and wants_rows:
            if self.fail_listing:
                return FakeResponse({"response_status": [{"status": "failed"}]})
            start = info.get("start_index", 1)
            page = [
                {"created_time": {"value": str(1_000 * DAY_MS - i * DAY_MS)}}
                for i in range(start - 1, min(start - 1 + info["row_count"], self.open_tickets))
            ]
            return FakeResponse(
                {
                    "response_status": [{"status": "success"}],
                    "requests": page,
                    "list_info": {
                        "has_more_rows": start - 1 + len(page) < self.open_tickets,
                        "total_count": self.open_tickets,
                    },
                }
            )

        count = self.open_tickets if is_status_query else 7
        return FakeResponse(
            {
                "response_status": [{"status": "success"}],
                "requests": [],
                "list_info": {"total_count": count, "has_more_rows": False},
            }
        )


@pytest.fixture
def client(settings):
    settings.SERVICEDESK_URL = "https://servicedesk.example"
    settings.SERVICEDESK_API_KEY = "test-key"
    settings.SERVICEDESK_SYNC_ENABLED = True
    return ServiceDeskClient()


class TestCallBudget:
    def test_a_sync_cycle_costs_three_calls(self, client):
        """created count + closed count + one open listing."""
        fake = FakeServiceDesk(open_tickets=35)

        with patch("apps.logbook.services.servicedesk.requests.get", fake):
            stats = client.get_week_stats(2026, 35)

        assert len(fake.calls) == 3, [c.get("search_criteria") for c in fake.calls]
        assert stats["open"] == 35
        assert sum(stats["open_by_age"].values()) == 35

    def test_open_statuses_are_one_query_not_one_per_status(self, client):
        """The status filter uses a values list, not a call per status."""
        fake = FakeServiceDesk()

        with patch("apps.logbook.services.servicedesk.requests.get", fake):
            client.get_week_stats(2026, 35)

        status_criteria = [
            c
            for call in fake.calls
            for c in call.get("search_criteria", [])
            if c.get("field") == "status.name"
        ]
        assert len(status_criteria) == 1
        assert status_criteria[0]["values"] == ServiceDeskClient.OPEN_STATUSES

    def test_paging_only_costs_more_beyond_a_full_page(self, client):
        """250 open tickets = 3 pages, so 2 counts + 3 pages."""
        fake = FakeServiceDesk(open_tickets=250)

        with patch("apps.logbook.services.servicedesk.requests.get", fake):
            stats = client.get_week_stats(2026, 35)

        assert len(fake.calls) == 5
        assert stats["open"] == 250

    def test_historical_reconstruction_costs_two_calls(self, client):
        """One listing of what is still open, one of what closed since."""
        fake = FakeServiceDesk()

        with patch("apps.logbook.services.servicedesk.requests.get", fake):
            created = client.fetch_open_created_times_at(900 * DAY_MS)

        assert created is not None
        assert len(fake.calls) == 2


class TestListingFailure:
    def test_falls_back_to_the_count_query(self, client):
        """A failed listing must not zero the open count."""
        fake = FakeServiceDesk(open_tickets=35, fail_listing=True)

        with patch("apps.logbook.services.servicedesk.requests.get", fake):
            stats = client.get_week_stats(2026, 35)

        # 2 counts + 1 failed listing + 5 per-status fallback counts.
        assert len(fake.calls) == 8
        assert stats["open"] == 35 * len(ServiceDeskClient.OPEN_STATUSES)
        # No age data rather than wrong age data.
        assert stats["open_by_age"] == {}

    def test_weeklog_keeps_its_previous_breakdown(self, client):
        """apply_helpdesk_stats leaves buckets alone when age data is missing."""
        weeklog = WeekLog.objects.create(
            year=2026, week_number=35, helpdesk_open=10, helpdesk_open_0_7=10
        )
        fake = FakeServiceDesk(open_tickets=9, fail_listing=True)

        with patch("apps.logbook.services.servicedesk.requests.get", fake):
            weeklog.apply_helpdesk_stats(client.get_week_stats(2026, 35))

        weeklog.refresh_from_db()
        assert weeklog.helpdesk_open_0_7 == 10
