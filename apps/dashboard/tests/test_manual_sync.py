"""Manual ServiceDesk sync ("Prøv igen" / the KPI refresh button)."""

from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from apps.logbook.models import HelpdeskTicket

pytestmark = pytest.mark.django_db

STATS = {"created": 3, "closed": 2, "open": 40, "open_by_age": {}}


@pytest.fixture
def logged_in(client):
    client.force_login(User.objects.create_user("gre", password="x"))
    return client


@pytest.fixture
def stale_mirror():
    t = HelpdeskTicket.objects.create(sdp_id=1, created_at=timezone.now(), is_open=True, status="Åben")
    HelpdeskTicket.objects.filter(pk=t.pk).update(synced_at=timezone.now() - timedelta(hours=2))


def _touch_mirror(client=None):
    """Stand-in for a successful incremental sync: re-saves the newest ticket."""
    HelpdeskTicket.objects.first().save()
    return 1


def _patched(mirror_result):
    client = mock.patch("apps.logbook.services.servicedesk.ServiceDeskClient")
    mirror = mock.patch("apps.logbook.services.ticket_mirror.sync_incremental", side_effect=mirror_result)
    return client, mirror


def test_manual_sync_refreshes_the_mirror_and_clears_stale(logged_in, stale_mirror):
    client_patch, mirror_patch = _patched(_touch_mirror)
    with client_patch as Client, mirror_patch as mirror:
        Client.return_value.enabled = True
        Client.return_value.get_week_stats.return_value = STATS
        resp = logged_in.post(reverse("dashboard:sync-servicedesk"), {"reload": "1"})
    assert mirror.called
    body = resp.content.decode()
    assert "forældet" not in body
    assert resp["HX-Refresh"] == "true"


def test_failed_manual_sync_shows_an_error_and_does_not_reload(logged_in, stale_mirror):
    client_patch, mirror_patch = _patched(lambda client=None: None)
    with client_patch as Client, mirror_patch:
        Client.return_value.enabled = True
        Client.return_value.get_week_stats.return_value = STATS
        resp = logged_in.post(reverse("dashboard:sync-servicedesk"), {"reload": "1"})
    body = resp.content.decode()
    assert "Synk med ServiceDesk fejlede" in body
    assert "forældet" in body
    assert "HX-Refresh" not in resp
