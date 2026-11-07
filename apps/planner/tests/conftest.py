"""Shared fixtures: Planner settings with a fresh key pair, and Graph data."""

import pytest
from django.utils import timezone

from apps.planner.crypto import generate_keypair

TENANT = "11111111-2222-4333-8444-555555555555"
PLAN = "TestPlanId0000000000000000AB"
CLIENT_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


@pytest.fixture
def planner(settings):
    """Settings as in the sync container (web gets the same minus secrets)."""
    public, private = generate_keypair()
    settings.PLANNER_ENABLED = True
    settings.PLANNER_SYNC_ENABLED = True
    settings.PLANNER_TENANT_ID = TENANT
    settings.PLANNER_CLIENT_ID = CLIENT_ID
    settings.PLANNER_CLIENT_SECRET = "test-secret"
    settings.PLANNER_PLAN_ID = PLAN
    settings.PLANNER_SERVICE_ACCOUNT = "SVC-Chronicle-Planner@fynbus.dk"
    settings.PLANNER_PUBLIC_KEY = public
    settings.PLANNER_PRIVATE_KEY = private
    settings.PLANNER_REDIRECT_URI = "https://chronicle.fynbus.net/planner/connect/callback/"
    settings.PLANNER_WORK_HOURS = "mon-fri 07:15-17:30"
    settings.PLANNER_INTERVAL_WORK = 120
    settings.PLANNER_INTERVAL_OFF = 900
    return settings


def graph_data():
    """A small plan as Graph returns it."""
    return {
        f"/planner/plans/{PLAN}": {"id": PLAN, "title": "Intern IT - Backlog"},
        f"/planner/plans/{PLAN}/details": {"categoryDescriptions": {"category16": "Ubehandlet", "category2": None}},
        f"/planner/plans/{PLAN}/buckets": {"value": [
            {"id": "b1", "name": "Backlog (skal løses 2026)", "orderHint": "8585"},
            {"id": "b2", "name": "Icelog (kan vente til 2027)", "orderHint": "8586"},
        ]},
        f"/planner/plans/{PLAN}/tasks": {"value": [
            {"id": "t1", "bucketId": "b1", "title": "Fornyelse af funktionscertifikater", "percentComplete": 0,
             "priority": 3, "orderHint": "a", "dueDateTime": "2026-12-31T00:00:00Z",
             "assignments": {"u1": {}}, "appliedCategories": {"category16": True},
             "checklistItemCount": 2, "activeChecklistItemCount": 1, "referenceCount": 0,
             "hasDescription": True, "@odata.etag": "W/\"e1\""},
            {"id": "t2", "bucketId": "b2", "title": "Universal Print?", "percentComplete": 100,
             "priority": 5, "orderHint": "b", "completedDateTime": "2026-11-01T10:00:00Z",
             "assignments": {}, "appliedCategories": {}, "hasDescription": False, "@odata.etag": "W/\"e2\""},
        ], "@odata.nextLink": "https://graph.microsoft.com/v1.0/next-page"},
        "https://graph.microsoft.com/v1.0/next-page": {"value": [
            {"id": "t3", "bucketId": "b1", "title": "<script>alert(1)</script>", "percentComplete": 50,
             "priority": 1, "orderHint": "c", "assignments": {}, "appliedCategories": {},
             "hasDescription": False, "@odata.etag": "W/\"e3\""},
        ]},
        "/planner/tasks/t1/details": {"description": "Med MitID Erhverv.\n" + "x" * 5000, "@odata.etag": "W/\"d1\""},
        "/users/u1": {"id": "u1", "displayName": "Gorm Reventlow"},
    }


class FakeGraph:
    """Answers GraphClient.get/get_all from a dict; records the calls."""

    def __init__(self, data=None):
        self.data = data or graph_data()
        self.calls = []

    def get(self, path, params=None):
        self.calls.append(path)
        return self.data[path]

    def get_all(self, path, params=None):
        page = self.get(path, params)
        while True:
            yield from page.get("value", [])
            if not page.get("@odata.nextLink"):
                return
            page = self.get(page["@odata.nextLink"])


@pytest.fixture
def fake_graph():
    return FakeGraph()


@pytest.fixture
def web(planner, settings):
    """As the web container: no client secret, no private key."""
    settings.PLANNER_CLIENT_SECRET = ""
    private = settings.PLANNER_PRIVATE_KEY
    settings.PLANNER_PRIVATE_KEY = ""
    return private


@pytest.fixture
def mirrored(planner):
    from apps.planner.models import PlannerConnection, SyncState
    from apps.planner.sync import mirror_plan

    mirror_plan(FakeGraph(), PLAN)
    conn = PlannerConnection.get()
    conn.sealed_token_cache, conn.home_account_id, conn.account_upn = "x", "h", "SVC-Chronicle-Planner@fynbus.dk"
    conn.save()
    state = SyncState.get()
    state.last_success_at = timezone.now()
    state.save()
