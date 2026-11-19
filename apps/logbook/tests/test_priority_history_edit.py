"""Editing a task from its history page (feature request #18).

The history page edits the task itself (title, priority, status, and legacy
notes when a task still has them) and each week's description, without the
user having to find the week the task sits on. Status changes must behave
exactly like the weeklog row form, so the reopen rules are tested here too.
"""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone

from apps.logbook.models import PriorityItem, PriorityItemAppearance, WeekLog

pytestmark = pytest.mark.django_db

HX = {"HTTP_HX_REQUEST": "true"}


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


@pytest.fixture
def current_week():
    return WeekLog.get_or_create_current_week()


@pytest.fixture
def task():
    """An open task on an old week, last touched a while ago."""
    weeklog = WeekLog.objects.create(year=2026, week_number=30)
    item = PriorityItem.objects.create(
        origin_weeklog=weeklog, title="Hastighedstest", priority="medium", status="ongoing",
    )
    item.last_active_at = timezone.now() - timedelta(days=20)
    item.save(update_fields=["last_active_at"])
    appearance = PriorityItemAppearance.objects.create(
        priority_item=item, weeklog=weeklog, description="Første uge"
    )
    return item, appearance


def history_url(item):
    return reverse("logbook:priority-item-history", kwargs={"pk": item.pk})


def task_edit_url(item):
    return reverse("logbook:priority-item-task-edit", kwargs={"pk": item.pk})


def week_edit_url(appearance):
    return reverse("logbook:priority-history-week-edit", kwargs={"pk": appearance.pk})


def task_post(**overrides):
    data = {"title": "Hastighedstest", "priority": "medium", "status": "ongoing"}
    data.update(overrides)
    return data


class TestHistoryPageButtons:
    def test_editor_sees_task_and_week_edit(self, client, editor, task):
        item, appearance = task
        html = client.get(history_url(item)).content.decode()

        assert task_edit_url(item) in html
        assert week_edit_url(appearance) in html
        assert 'id="task-edit-slot"' in html

    def test_viewer_sees_no_edit(self, client, viewer, task):
        item, appearance = task
        html = client.get(history_url(item)).content.decode()

        assert task_edit_url(item) not in html
        assert week_edit_url(appearance) not in html
        assert "Første uge" in html  # the timeline itself still renders

    def test_deleted_task_has_no_edit(self, client, editor, task):
        item, appearance = task
        item.soft_delete()
        html = client.get(history_url(item)).content.decode()

        assert task_edit_url(item) not in html
        assert week_edit_url(appearance) not in html


class TestTaskEdit:
    def test_get_returns_the_form(self, client, editor, task):
        item, _ = task
        html = client.get(task_edit_url(item), **HX).content.decode()

        assert 'name="title"' in html and 'name="status"' in html
        assert 'name="description"' not in html

    def test_save_updates_the_task_and_refreshes(self, client, editor, task):
        item, _ = task
        before = item.last_active_at

        response = client.post(
            task_edit_url(item), task_post(title="Hastighedstest (LibreSpeed)", priority="high"), **HX
        )
        item.refresh_from_db()

        assert response.status_code == 204
        assert response["HX-Refresh"] == "true"
        assert item.title == "Hastighedstest (LibreSpeed)"
        assert item.priority == "high"
        assert item.last_active_at > before

    def test_invalid_post_returns_the_form_with_errors(self, client, editor, task):
        item, _ = task
        response = client.post(task_edit_url(item), task_post(title=""), **HX)
        item.refresh_from_db()

        assert response.status_code == 200
        assert "input-error-message" in response.content.decode()
        assert item.title == "Hastighedstest"

    def test_reopening_puts_it_on_the_current_week(self, client, editor, task, current_week):
        item, _ = task
        item.status = PriorityItem.Status.COMPLETED
        item.save(update_fields=["status"])

        client.post(task_edit_url(item), task_post(status="ongoing"), **HX)
        item.refresh_from_db()

        assert item.status == PriorityItem.Status.ONGOING
        assert item.appearances.filter(weeklog=current_week).exists()

    def test_reopening_without_a_current_weeklog_clears_auto_close(self, client, editor, task):
        """No weeklog for this week yet: still a proper reopen, just no week."""
        item, _ = task
        assert WeekLog.get_current_week() is None
        item.auto_close()

        client.post(task_edit_url(item), task_post(status="ongoing"), **HX)
        item.refresh_from_db()

        assert item.status == PriorityItem.Status.ONGOING
        assert item.auto_closed is False and item.closed_at is None
        assert item.appearances.count() == 1

    def test_reopen_hint_survives_a_rejected_save(self, client, editor, task):
        item, _ = task
        item.status = PriorityItem.Status.COMPLETED
        item.save(update_fields=["status"])

        html = client.post(task_edit_url(item), task_post(title="", status="ongoing"), **HX).content.decode()

        assert "genåbnet som Igangværende" in html

    def test_completing_does_not_add_a_week(self, client, editor, task, current_week):
        item, _ = task
        client.post(task_edit_url(item), task_post(status="completed"), **HX)
        item.refresh_from_db()

        assert item.status == PriorityItem.Status.COMPLETED
        assert not item.appearances.filter(weeklog=current_week).exists()

    def test_viewer_is_refused(self, client, viewer, task):
        item, _ = task
        assert client.get(task_edit_url(item), **HX).status_code == 403
        assert client.post(task_edit_url(item), task_post(title="x"), **HX).status_code == 403
        item.refresh_from_db()
        assert item.title == "Hastighedstest"

    @pytest.mark.parametrize("state", ["deleted", "merged"])
    def test_deleted_or_merged_task_is_404(self, client, editor, task, state):
        item, _ = task
        if state == "deleted":
            item.soft_delete()
        else:
            winner = PriorityItem.objects.create(
                origin_weeklog=item.origin_weeklog, title="Vinder", status="ongoing"
            )
            item.merge_into(winner)

        assert client.get(task_edit_url(item), **HX).status_code == 404
        assert client.post(task_edit_url(item), task_post(title="x"), **HX).status_code == 404


class TestLegacyNotes:
    def test_no_notes_field_without_notes(self, client, editor, task):
        item, _ = task
        html = client.get(task_edit_url(item), **HX).content.decode()

        assert 'name="notes"' not in html

    def test_posted_notes_are_ignored_without_notes(self, client, editor, task):
        """The field is not offered, so a stray value must not create notes."""
        item, _ = task
        client.post(task_edit_url(item), task_post(notes="smuglet ind"), **HX)
        item.refresh_from_db()

        assert item.notes == ""

    def test_existing_notes_can_be_edited_and_cleared(self, client, editor, task):
        item, _ = task
        item.notes = "Skrevet via API'et"
        item.save(update_fields=["notes"])

        html = client.get(task_edit_url(item), **HX).content.decode()
        assert 'name="notes"' in html and "Skrevet via API" in html

        client.post(task_edit_url(item), task_post(notes="Rettet"), **HX)
        item.refresh_from_db()
        assert item.notes == "Rettet"

        client.post(task_edit_url(item), task_post(notes=""), **HX)
        item.refresh_from_db()
        assert item.notes == ""


class TestWeekEdit:
    def test_get_returns_the_description_form(self, client, editor, task):
        _, appearance = task
        html = client.get(week_edit_url(appearance), **HX).content.decode()

        assert 'name="description"' in html and "Første uge" in html

    def test_save_updates_that_week_and_returns_the_row(self, client, editor, task):
        item, appearance = task
        before = item.last_active_at

        response = client.post(week_edit_url(appearance), {"description": "Rettet beskrivelse"}, **HX)
        appearance.refresh_from_db()
        item.refresh_from_db()

        assert appearance.description == "Rettet beskrivelse"
        html = response.content.decode()
        assert f'id="history-week-{appearance.pk}"' in html and "Rettet beskrivelse" in html
        assert item.last_active_at > before

    def test_other_weeks_are_untouched(self, client, editor, task):
        item, appearance = task
        other = PriorityItemAppearance.objects.create(
            priority_item=item,
            weeklog=WeekLog.objects.create(year=2026, week_number=31),
            description="Anden uge",
        )
        client.post(week_edit_url(appearance), {"description": "Kun uge 30"}, **HX)
        other.refresh_from_db()

        assert other.description == "Anden uge"

    def test_cancel_returns_the_row(self, client, editor, task):
        _, appearance = task
        html = client.get(
            reverse("logbook:priority-history-week", kwargs={"pk": appearance.pk}), **HX
        ).content.decode()

        assert f'id="history-week-{appearance.pk}"' in html and "Første uge" in html

    def test_viewer_is_refused(self, client, viewer, task):
        _, appearance = task
        assert client.get(week_edit_url(appearance), **HX).status_code == 403
        assert client.post(week_edit_url(appearance), {"description": "x"}, **HX).status_code == 403
        appearance.refresh_from_db()
        assert appearance.description == "Første uge"

    def test_week_of_deleted_task_is_404(self, client, editor, task):
        item, appearance = task
        item.soft_delete()

        assert client.post(week_edit_url(appearance), {"description": "x"}, **HX).status_code == 404
