"""Tests for the helpdesk ticket mirror and the Statistik page."""

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.dashboard.statistics import chronicle_statistics, helpdesk_statistics
from apps.logbook.models import HelpdeskTicket, Incident, PriorityItem, WeekLog
from apps.logbook.services import ticket_mirror
from apps.logbook.services.servicedesk import ServiceDeskClient

pytestmark = pytest.mark.django_db

NOW = timezone.make_aware(datetime(2026, 10, 14, 12, 0))  # a Wednesday


def ms(dt: datetime) -> str:
    return str(int(dt.timestamp() * 1000))


def row(sdp_id, created, *, status="Lukket", completed=None, requester="1",
        category=None, technician=None, updated=None):
    """A ServiceDesk request row shaped like the v3 API returns it."""
    return {
        "id": str(sdp_id),
        "created_time": {"value": ms(created)},
        "completed_time": {"value": ms(completed)} if completed else None,
        "resolved_time": None,
        "last_updated_time": {"value": ms(updated or completed or created)},
        "status": {"name": status},
        "requester": {"id": requester, "department": {"name": "IT"}},
        "category": {"name": category} if category else None,
        "technician": {"name": technician} if technician else None,
    }


class FakeClient(ServiceDeskClient):
    """ServiceDeskClient whose listings come from a list, or fail."""

    def __init__(self, rows=None, fail=False):
        super().__init__()
        self.enabled = True
        self.rows = rows or []
        self.fail = fail
        self.criteria = []

    def _fetch_paged(self, criteria, fields, max_pages=None):
        self.criteria.append(criteria)
        return None if self.fail else list(self.rows)


# --- Mirror -----------------------------------------------------------------


def test_ticket_values_parses_a_closed_ticket():
    created = NOW - timedelta(hours=5)
    values = ticket_mirror.ticket_values(
        row(7, created, completed=NOW, category="Hardware", technician="Morten")
    )
    assert values["sdp_id"] == 7
    assert abs(values["created_at"] - created) < timedelta(milliseconds=1)
    assert values["closed_at"] is not None
    assert values["is_open"] is False
    assert values["category"] == "Hardware"
    assert values["technician"] == "Morten"
    assert values["requester_ref"] == "1"


def test_ticket_values_open_ticket_has_no_close_time():
    values = ticket_mirror.ticket_values(row(8, NOW, status="Åben"))
    assert values["is_open"] is True
    assert values["closed_at"] is None


def test_ticket_values_cancelled():
    values = ticket_mirror.ticket_values(row(9, NOW, status="Annulleret", completed=NOW))
    assert values["is_cancelled"] is True
    assert values["is_open"] is False


def test_ticket_values_rejects_rows_without_id_or_created():
    assert ticket_mirror.ticket_values({"id": None}) is None
    assert ticket_mirror.ticket_values({"id": "3", "created_time": None}) is None


def test_full_sync_upserts_and_prunes():
    HelpdeskTicket.objects.create(sdp_id=999, created_at=NOW, status="Lukket", is_open=False)
    client = FakeClient([row(1, NOW), row(2, NOW, status="Åben")])
    assert ticket_mirror.sync_full(client) == 2
    assert set(HelpdeskTicket.objects.values_list("sdp_id", flat=True)) == {1, 2}
    # Created, completed and open listings.
    assert len(client.criteria) == 3


def test_full_sync_never_prunes_on_failure():
    HelpdeskTicket.objects.create(sdp_id=999, created_at=NOW, status="Lukket", is_open=False)
    assert ticket_mirror.sync_full(FakeClient(fail=True)) is None
    assert HelpdeskTicket.objects.filter(sdp_id=999).exists()


def test_incremental_sync_fetches_changes_since_newest():
    HelpdeskTicket.objects.create(
        sdp_id=1, created_at=NOW, status="Åben", is_open=True, sdp_updated_at=NOW
    )
    client = FakeClient([row(1, NOW, completed=NOW + timedelta(hours=1))])
    assert ticket_mirror.sync_incremental(client) == 1
    assert HelpdeskTicket.objects.get(sdp_id=1).is_open is False
    (criterion,) = client.criteria[0]
    assert criterion["field"] == "last_updated_time"


def test_incremental_sync_on_empty_mirror_does_a_full_sync():
    client = FakeClient([row(1, NOW)])
    ticket_mirror.sync_incremental(client)
    assert len(client.criteria) == 3


# --- Statistics ---------------------------------------------------------------


def make(sdp_id, created, closed=None, **kw):
    return HelpdeskTicket.objects.create(
        sdp_id=sdp_id,
        created_at=created,
        closed_at=closed,
        is_open=closed is None,
        status=kw.pop("status", "Åben" if closed is None else "Lukket"),
        **kw,
    )


def test_helpdesk_headline_numbers():
    make(1, NOW - timedelta(days=3), NOW - timedelta(days=2), requester_ref="a", technician="Morten")
    make(2, NOW - timedelta(days=10), NOW - timedelta(days=9), requester_ref="a", technician="Peter")
    make(3, NOW - timedelta(days=1), requester_ref="b")
    make(4, NOW - timedelta(days=2), NOW - timedelta(days=1), requester_ref="c",
         is_cancelled=True, status="Annulleret")
    make(5, NOW - timedelta(days=500), NOW - timedelta(days=400), requester_ref="d")  # outside

    stats = helpdesk_statistics(NOW)
    assert stats["total_created"] == 4
    assert stats["requesters"] == 3
    assert stats["per_month"] == round(4 / 12, 1)
    assert stats["open_now"] == 1
    assert stats["cancelled"] == 1
    # Cancelled tickets are not "solved".
    assert stats["total_solved"] == 2
    assert {t["label"] for t in stats["technicians"]} == {"Morten", "Peter"}
    assert stats["resolution"]["count"] == 2
    assert stats["resolution"]["median"] == "24,0 t"


def test_anonymised_and_missing_technicians_get_labels():
    make(1, NOW - timedelta(days=3), NOW - timedelta(days=2), technician="ANONYMOUS_123")
    make(2, NOW - timedelta(days=3), NOW - timedelta(days=2), technician="")
    labels = {t["label"] for t in helpdesk_statistics(NOW)["technicians"]}
    assert labels == {"Anonymiseret tekniker", "Ikke tildelt"}


def test_categories_exclude_uncategorised_from_the_split():
    make(1, NOW - timedelta(days=1), category="Hardware")
    make(2, NOW - timedelta(days=1), category="")
    stats = helpdesk_statistics(NOW)
    assert stats["categories"] == [{"label": "Hardware", "count": 1, "share": 100.0}]
    assert stats["uncategorised"] == 1
    assert stats["uncategorised_share"] == 50


def test_open_per_week_is_reconstructed_from_open_and_close_times():
    # Open for most of the year, closed two days ago.
    make(1, NOW - timedelta(days=300), NOW - timedelta(days=2))
    stats = helpdesk_statistics(NOW)
    assert len(stats["weekly"]) == 52
    assert stats["weekly"][-2]["open"] == 1   # end of last week: still open
    assert stats["weekly"][-1]["open"] == 0   # now: closed


def test_weekday_and_hour_are_local_time():
    # 07:30 UTC on a Wednesday is 09:30 in Copenhagen (summer time).
    make(1, datetime(2026, 10, 7, 7, 30, tzinfo=dt_timezone.utc))
    stats = helpdesk_statistics(NOW)
    assert stats["busiest_hour"] == 9
    assert stats["busiest_day"] == "Onsdag"


def test_open_by_age_uses_weeklog_buckets():
    make(1, NOW - timedelta(days=3))
    make(2, NOW - timedelta(days=100))
    buckets = helpdesk_statistics(NOW)["open_by_age"]
    assert len(buckets) == len(WeekLog.HELPDESK_AGE_BUCKETS)
    assert sum(b["count"] for b in buckets) == 2


def test_chronicle_statistics():
    weeklog = WeekLog.objects.create(year=2026, week_number=41)
    PriorityItem.objects.create(origin_weeklog=weeklog, title="A", priority="high")
    done = PriorityItem.objects.create(origin_weeklog=weeklog, title="B")
    done.status = PriorityItem.Status.COMPLETED
    done.closed_at = timezone.now()
    done.save()
    PriorityItem.objects.create(origin_weeklog=weeklog, title="C", deleted_at=timezone.now())
    Incident.objects.create(weeklog=weeklog, title="Nedbrud", description="x",
                            severity="critical", incident_type="network")

    stats = chronicle_statistics()
    assert stats["priorities"]["created"] == 2
    assert stats["priorities"]["completed"] == 1
    assert stats["priorities"]["active"] == 1
    assert stats["incidents"]["total"] == 1
    assert stats["incidents"]["critical"] == 1
    assert stats["incidents"]["unresolved"] == 1
    assert stats["incidents"]["by_type"][0]["label"] == "Netværk"


# --- Page ---------------------------------------------------------------------


def test_statistics_page_requires_login(client):
    response = client.get(reverse("dashboard:statistics"))
    assert response.status_code == 302


def test_statistics_page_renders(client):
    user = User.objects.create_user("viewer", password="x")
    client.force_login(user)
    make(1, timezone.now() - timedelta(days=2), timezone.now() - timedelta(days=1), technician="Morten")
    response = client.get(reverse("dashboard:statistics"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Statistik" in body
    assert 'id="stats-data"' in body
    assert "Morten" in body


def test_statistics_page_without_data_explains_itself(client):
    client.force_login(User.objects.create_user("viewer", password="x"))
    response = client.get(reverse("dashboard:statistics"))
    assert "sync_helpdesk_tickets" in response.content.decode()


def test_heatmap_cells_carry_the_count():
    # Two tickets on a Wednesday at 09 local time (07 UTC in summer time).
    make(1, datetime(2026, 10, 7, 7, 10, tzinfo=dt_timezone.utc))
    make(2, datetime(2026, 9, 30, 7, 40, tzinfo=dt_timezone.utc))
    stats = helpdesk_statistics(NOW)
    cell = stats["heatmap"][2]["cells"][9]
    assert cell["count"] == 2
    assert cell["avg"] > 0
    assert stats["heat_max"] == 2
