"""Tests for the liggetid write endpoint (FR #8 backfill path)."""

import json

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.accounts.models import APIKey
from apps.logbook.models import WeekLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def weeklog():
    """A closed week with a recorded open count but no breakdown."""
    return WeekLog.objects.create(year=2026, week_number=34, helpdesk_open=62)


@pytest.fixture
def write_key():
    user = User.objects.create_user("gre", password="x")
    _, raw = APIKey.generate(user=user, scope=APIKey.Scope.WRITE, label="test")
    return raw


@pytest.fixture
def read_key():
    user = User.objects.create_user("reader", password="x")
    _, raw = APIKey.generate(user=user, scope=APIKey.Scope.READ, label="test")
    return raw


def url(year=2026, week=34):
    return reverse("api:weeklog-helpdesk-age", kwargs={"year": year, "week": week})


def patch(client, key, body, year=2026, week=34):
    return client.patch(
        url(year, week),
        data=json.dumps(body),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {key}",
    )


class TestAuth:
    def test_requires_a_key(self, client, weeklog):
        response = client.patch(url(), data="{}", content_type="application/json")
        assert response.status_code == 401

    def test_read_key_is_rejected(self, client, weeklog, read_key):
        response = patch(client, read_key, {"helpdesk_open_0_7": 62})
        assert response.status_code == 403

    def test_get_is_not_allowed(self, client, weeklog, write_key):
        response = client.get(url(), HTTP_AUTHORIZATION=f"Bearer {write_key}")
        assert response.status_code == 405


class TestWrite:
    def test_sets_the_breakdown(self, client, weeklog, write_key):
        response = patch(
            client,
            write_key,
            {
                "helpdesk_open_0_7": 7,
                "helpdesk_open_8_14": 7,
                "helpdesk_open_15_30": 6,
                "helpdesk_open_31_90": 11,
                "helpdesk_open_91_180": 23,
                "helpdesk_open_181_365": 8,
                "helpdesk_open_over_365": 0,
            },
        )

        assert response.status_code == 200, response.content
        weeklog.refresh_from_db()
        assert weeklog.helpdesk_open_91_180 == 23
        assert weeklog.helpdesk_open_bucketed == 62
        assert weeklog.has_helpdesk_age_breakdown is True
        # Untouched buckets default to 0 rather than erroring.
        assert weeklog.helpdesk_open_over_365 == 0

    def test_can_correct_the_total(self, client, weeklog, write_key):
        """Reconstruction may fall short of the recorded count."""
        response = patch(
            client,
            write_key,
            {"helpdesk_open": 61, "helpdesk_open_0_7": 61},
        )

        assert response.status_code == 200
        weeklog.refresh_from_db()
        assert weeklog.helpdesk_open == 61
        assert weeklog.helpdesk_open_0_7 == 61

    def test_mismatched_breakdown_is_rejected(self, client, weeklog, write_key):
        response = patch(client, write_key, {"helpdesk_open_0_7": 61})

        assert response.status_code == 400
        assert response.json()["error"] == "breakdown_mismatch"
        weeklog.refresh_from_db()
        assert weeklog.helpdesk_open_0_7 == 0

    def test_all_zero_clears_the_breakdown_without_touching_the_total(
        self, client, weeklog, write_key
    ):
        weeklog.helpdesk_open_0_7 = 62
        weeklog.save()

        response = patch(client, write_key, {})

        assert response.status_code == 200
        weeklog.refresh_from_db()
        assert weeklog.helpdesk_open == 62
        assert weeklog.has_helpdesk_age_breakdown is False

    @pytest.mark.parametrize("value", [-1, "7", 1.5, True, None])
    def test_rejects_non_counts(self, client, weeklog, write_key, value):
        response = patch(client, write_key, {"helpdesk_open_0_7": value})

        assert response.status_code == 400
        assert response.json()["error"] == "invalid_value"

    def test_rejects_unknown_fields(self, client, weeklog, write_key):
        response = patch(client, write_key, {"helpdesk_open_8_30": 5})

        assert response.status_code == 400
        assert response.json()["error"] == "unknown_field"

    def test_unknown_week_is_404(self, client, weeklog, write_key):
        response = patch(client, write_key, {}, week=52)
        assert response.status_code == 404
