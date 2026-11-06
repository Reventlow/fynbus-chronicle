"""Sealing between web and sync, and the sync schedule."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from django.core.exceptions import ImproperlyConfigured
from nacl.exceptions import CryptoError

from apps.planner import crypto
from apps.planner.schedule import interval_for, parse_work_hours

CPH = ZoneInfo("Europe/Copenhagen")


def test_seal_roundtrip(planner):
    blob = crypto.seal({"code": "abc"})
    assert "abc" not in blob
    assert crypto.open_sealed(blob) == {"code": "abc"}


def test_web_container_cannot_open(planner, settings):
    """Without the private key (as in the web container) nothing opens."""
    blob = crypto.seal({"code": "abc"})
    settings.PLANNER_PRIVATE_KEY = ""
    with pytest.raises(ImproperlyConfigured):
        crypto.open_sealed(blob)


def test_other_private_key_cannot_open(planner, settings):
    blob = crypto.seal("secret text")
    settings.PLANNER_PRIVATE_KEY = crypto.generate_keypair()[1]
    with pytest.raises(CryptoError):
        crypto.open_sealed(blob, as_json=False)


@pytest.mark.parametrize("moment, expected", [
    (datetime(2026, 11, 9, 7, 14, tzinfo=CPH), 900),   # Monday, before 07:15
    (datetime(2026, 11, 9, 7, 15, tzinfo=CPH), 120),   # Monday 07:15
    (datetime(2026, 11, 13, 17, 29, tzinfo=CPH), 120),  # Friday 17:29
    (datetime(2026, 11, 13, 17, 30, tzinfo=CPH), 900),  # Friday 17:30: quiet hours
    (datetime(2026, 11, 14, 12, 0, tzinfo=CPH), 900),  # Saturday
])
def test_interval_for(planner, moment, expected):
    assert interval_for(moment) == expected


def test_work_hours_are_local_time(planner):
    """08:00 in Copenhagen is 07:00 UTC in winter; still working hours."""
    assert interval_for(datetime(2026, 11, 9, 7, 0, tzinfo=ZoneInfo("UTC"))) == 120


def test_parse_work_hours_lists_and_errors():
    hours = parse_work_hours("mon,wed 08:00-16:00")
    assert hours.days == frozenset({0, 2})
    with pytest.raises(ImproperlyConfigured):
        parse_work_hours("weekdays 8-16")
