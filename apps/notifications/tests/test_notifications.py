"""Tests for the notification bell: creation rules, badge, read-on-open."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def anna():
    return User.objects.create_user("anna", password="x", first_name="Anna")


@pytest.fixture
def bo():
    return User.objects.create_user("bo", password="x")


class TestNotifyRules:
    def test_notify_creates_unread(self, anna, bo):
        notification = Notification.notify(anna, "Test", actor=bo)
        assert notification is not None and not notification.is_read
        assert Notification.unread_count(anna) == 1

    def test_self_notification_skipped(self, anna):
        assert Notification.notify(anna, "Test", actor=anna) is None

    def test_inactive_recipient_skipped(self, anna, bo):
        anna.is_active = False
        anna.save()
        assert Notification.notify(anna, "Test", actor=bo) is None


class TestBellViews:
    def test_badge_shows_count(self, client, anna, bo):
        Notification.notify(anna, "Hej", actor=bo)
        client.force_login(anna)
        response = client.get(reverse("notifications:partial-badge"))
        assert "1" in response.content.decode()

    def test_panel_marks_shown_read_when_opened(self, client, anna, bo):
        for i in range(3):
            Notification.notify(anna, f"Besked {i}", actor=bo)
        client.force_login(anna)

        response = client.post(reverse("notifications:partial-panel"))
        content = response.content.decode()
        assert "Besked 2" in content
        # Opened once → the shown items are read, badge OOB-clears.
        assert Notification.unread_count(anna) == 0
        assert 'hx-swap-oob="outerHTML"' in content

    def test_panel_marks_only_displayed_items_read(self, client, anna, bo):
        # More unread than the panel shows: the overflow must stay
        # unread and keep counting in the badge.
        for i in range(20):
            Notification.notify(anna, f"Besked {i}", actor=bo)
        client.force_login(anna)

        client.post(reverse("notifications:partial-panel"))
        assert Notification.unread_count(anna) == 5

    def test_panel_rejects_get(self, client, anna):
        # Marking read is a state change — a cross-site GET link must
        # not be able to trigger it.
        client.force_login(anna)
        assert client.get(reverse("notifications:partial-panel")).status_code == 405

    def test_panel_only_shows_own_notifications(self, client, anna, bo):
        Notification.notify(anna, "Til Anna", actor=bo)
        client.force_login(bo)
        response = client.post(reverse("notifications:partial-panel"))
        assert "Til Anna" not in response.content.decode()
        assert Notification.unread_count(anna) == 1  # untouched by Bo's open

    def test_anonymous_redirected(self, client):
        assert client.post(reverse("notifications:partial-panel")).status_code == 302
