"""Contract pin for serialize_oncall.

The MCP server (mcp-chronicle) passes this JSON through verbatim and
deploys independently — the pre-0.8.0 keys must keep their exact names
and types, and ``user`` must resolve to whoever covers *now*.
"""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from apps.api.serializers import serialize_oncall
from apps.oncall import services
from apps.oncall.models import OnCallDuty, week_span

pytestmark = pytest.mark.django_db

#: The exact contract before FR #5 — never remove or rename these.
LEGACY_KEYS = {"year", "week", "label", "user", "notes"}
LEGACY_USER_KEYS = {"username", "full_name", "email"}


@pytest.fixture
def anna():
    return User.objects.create_user(
        "anna", email="anna@fynbus.dk", first_name="Anna", last_name="Andersen"
    )


def test_none_duty_serializes_to_none():
    assert serialize_oncall(None) is None


def test_legacy_contract_intact(anna):
    services.apply_assignment(2026, 30, anna, week_span(2026, 30)[0], anna)
    data = serialize_oncall(OnCallDuty.get_for_week(2026, 30))

    assert LEGACY_KEYS <= set(data)
    assert data["year"] == 2026 and data["week"] == 30
    assert data["label"] == "Uge 30, 2026"
    assert set(data["user"]) == LEGACY_USER_KEYS
    assert data["user"]["username"] == "anna"
    assert isinstance(data["notes"], str)


def test_contract_unchanged_after_handover(anna):
    """A split week must not change the shape of the legacy keys."""
    bo = User.objects.create_user("bo", email="bo@fynbus.dk")
    start, _ = week_span(2026, 30)
    services.apply_assignment(2026, 30, anna, start, anna)
    services.apply_assignment(2026, 30, bo, start + timedelta(days=3), anna)

    data = serialize_oncall(OnCallDuty.get_for_week(2026, 30))
    assert isinstance(data["user"], dict)  # still ONE object, never a list
    assert set(data["user"]) == LEGACY_USER_KEYS
    assert len(data["segments"]) == 2
    assert len(data["changes"]) == 2
    assert {"start_at", "end_at", "weekdays", "user"} == set(data["segments"][0])
    assert {"changed_at", "changed_by", "from_user", "to_user", "effective_at"} == set(
        data["changes"][0]
    )


def test_get_current_returns_todays_holder(anna):
    """The dashboard/API/MCP answer: whoever covers right now."""
    now = timezone.localtime()
    iso = now.date().isocalendar()
    services.apply_assignment(iso.year, iso.week, anna, week_span(iso.year, iso.week)[0], anna)
    data = serialize_oncall(OnCallDuty.get_current())
    assert data["user"]["username"] == "anna"
