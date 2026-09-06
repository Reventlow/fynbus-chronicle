"""Reopening a closed task from the priorities search page."""

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from apps.logbook.models import PriorityItem, PriorityItemAppearance, WeekLog

pytestmark = pytest.mark.django_db

SEARCH_URL = "/logbook/priorities/search/?q=chronicle&status=all&year="


@pytest.fixture
def current_week():
    """The weeklog for the ISO week we are actually in."""
    return WeekLog.get_or_create_current_week()


@pytest.fixture
def closed_task():
    weeklog = WeekLog.objects.create(year=2026, week_number=30)
    item = PriorityItem.objects.create(
        origin_weeklog=weeklog,
        title="Chronicle: liggetid",
        priority="medium",
        status=PriorityItem.Status.COMPLETED,
        auto_closed=True,
    )
    PriorityItemAppearance.objects.create(priority_item=item, weeklog=weeklog)
    return item


@pytest.fixture
def editor(client):
    user = User.objects.create_user("gre", password="x")
    client.force_login(user)
    return user


@pytest.fixture
def viewer(client):
    user = User.objects.create_user("viewer", password="x")
    group, _ = Group.objects.get_or_create(name="Viewer")
    user.groups.add(group)
    client.force_login(user)
    return user


def reopen_url(item):
    return reverse("logbook:priority-item-reopen", kwargs={"pk": item.pk})


def history_url(item):
    return reverse("logbook:priority-item-history", kwargs={"pk": item.pk})


class TestReopen:
    def test_closed_task_becomes_ongoing(self, client, editor, closed_task, current_week):
        client.post(reopen_url(closed_task))
        closed_task.refresh_from_db()

        assert closed_task.status == PriorityItem.Status.ONGOING
        assert closed_task.auto_closed is False
        assert closed_task.closed_at is None

    def test_it_lands_on_the_current_week(self, client, editor, closed_task, current_week):
        client.post(reopen_url(closed_task))

        assert closed_task.appearances.filter(weeklog=current_week).exists()

    def test_reopening_twice_does_not_duplicate_the_appearance(
        self, client, editor, closed_task, current_week
    ):
        client.post(reopen_url(closed_task))
        closed_task.refresh_from_db()
        closed_task.status = PriorityItem.Status.COMPLETED
        closed_task.save(update_fields=["status"])

        client.post(reopen_url(closed_task))

        assert closed_task.appearances.filter(weeklog=current_week).count() == 1

    def test_it_works_without_a_weeklog_for_this_week(self, client, editor, closed_task):
        """Nothing to attach it to, but the task still reopens."""
        assert WeekLog.get_current_week() is None

        response = client.post(reopen_url(closed_task))
        closed_task.refresh_from_db()

        assert response.status_code == 302
        assert closed_task.status == PriorityItem.Status.ONGOING

    def test_a_deleted_task_is_refused(self, client, editor, closed_task):
        closed_task.soft_delete()

        client.post(reopen_url(closed_task))
        closed_task.refresh_from_db()

        assert closed_task.status == PriorityItem.Status.COMPLETED


class TestReturnsToTheSearchPage:
    def test_redirects_back_with_filters_intact(self, client, editor, closed_task):
        response = client.post(reopen_url(closed_task), HTTP_REFERER=SEARCH_URL)

        assert response.status_code == 302
        assert response["Location"] == SEARCH_URL

    def test_falls_back_to_the_task_history(self, client, editor, closed_task):
        response = client.post(reopen_url(closed_task))

        assert response["Location"] == history_url(closed_task)

    def test_an_offsite_referer_is_not_followed(self, client, editor, closed_task):
        response = client.post(reopen_url(closed_task), HTTP_REFERER="https://evil.example/x")

        assert response["Location"] == history_url(closed_task)


class TestPermissions:
    def test_viewer_cannot_reopen(self, client, viewer, closed_task):
        response = client.post(reopen_url(closed_task))
        closed_task.refresh_from_db()

        assert response.status_code == 403
        assert closed_task.status == PriorityItem.Status.COMPLETED

    def test_get_is_not_allowed(self, client, editor, closed_task):
        assert client.get(reopen_url(closed_task)).status_code == 405


class TestButtonVisibility:
    def test_button_shows_for_a_closed_task(self, client, editor, closed_task):
        html = client.get(reverse("logbook:priorities-search")).content.decode()

        assert reopen_url(closed_task) in html

    def test_no_button_for_an_open_task(self, client, editor):
        weeklog = WeekLog.objects.create(year=2026, week_number=31)
        item = PriorityItem.objects.create(
            origin_weeklog=weeklog, title="Åben opgave", priority="low", status="ongoing"
        )

        html = client.get(reverse("logbook:priorities-search")).content.decode()

        assert reopen_url(item) not in html

    def test_no_button_for_a_viewer(self, client, viewer, closed_task):
        html = client.get(reverse("logbook:priorities-search")).content.decode()

        assert reopen_url(closed_task) not in html
