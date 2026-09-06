"""The notes field is gone from the priority-item form.

The team writes everything in the per-week description, so `notes` is no
longer editable from the UI. The column stays on the model because older
tasks still carry text there, and those keep rendering — so the tests
below cover both halves: not editable, not lost.
"""

import pytest
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.urls import reverse

from apps.logbook.forms import PriorityItemForm
from apps.logbook.models import PriorityItem, PriorityItemAppearance, WeekLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(client):
    user = User.objects.create_user("gre", password="x")
    client.force_login(user)
    return user


@pytest.fixture
def legacy_task():
    """An older task that still has notes from before the field was dropped."""
    weeklog = WeekLog.objects.create(year=2026, week_number=36)
    item = PriorityItem.objects.create(
        origin_weeklog=weeklog,
        title="Service - UPS",
        priority="medium",
        status="ongoing",
        notes="Præventivt eftersyn + skift af sliddele",
    )
    appearance = PriorityItemAppearance.objects.create(
        priority_item=item, weeklog=weeklog, description=""
    )
    return item, appearance


class TestFormNoLongerOffersNotes:
    def test_form_has_no_notes_field(self):
        assert "notes" not in PriorityItemForm().fields

    def test_form_still_has_the_fields_we_use(self):
        fields = PriorityItemForm().fields

        assert {"title", "priority", "status", "description"} <= set(fields)

    def test_rendered_form_has_no_notes_input(self, client, editor, legacy_task):
        _, appearance = legacy_task

        html = client.get(
            reverse("logbook:priority-item-edit", kwargs={"pk": appearance.pk}),
            HTTP_HX_REQUEST="true",
        ).content.decode()

        assert 'name="notes"' not in html
        assert ">Noter<" not in html

    def test_posted_notes_are_ignored(self, client, editor, legacy_task):
        """A stray `notes` in the POST must not reach the model."""
        item, appearance = legacy_task

        client.post(
            reverse("logbook:priority-item-edit", kwargs={"pk": appearance.pk}),
            {
                "title": "Service - UPS",
                "priority": "medium",
                "status": "ongoing",
                "description": "Eftersyn gennemført",
                "notes": "smuglet ind",
            },
            HTTP_HX_REQUEST="true",
        )
        item.refresh_from_db()

        assert item.notes == "Præventivt eftersyn + skift af sliddele"


class TestExistingNotesSurvive:
    def test_editing_a_task_keeps_its_notes(self, client, editor, legacy_task):
        item, appearance = legacy_task

        client.post(
            reverse("logbook:priority-item-edit", kwargs={"pk": appearance.pk}),
            {
                "title": "Service - UPS (TOL)",
                "priority": "high",
                "status": "completed",
                "description": "Afsluttet",
            },
            HTTP_HX_REQUEST="true",
        )
        item.refresh_from_db()

        assert item.title == "Service - UPS (TOL)"
        assert item.status == "completed"
        assert item.notes == "Præventivt eftersyn + skift af sliddele"

    def test_history_page_still_shows_legacy_notes(self, client, editor, legacy_task):
        item, _ = legacy_task

        html = client.get(
            reverse("logbook:priority-item-history", kwargs={"pk": item.pk})
        ).content.decode()

        assert "Præventivt eftersyn" in html

    def test_report_still_shows_legacy_notes(self, legacy_task):
        item, appearance = legacy_task

        html = render_to_string(
            "logbook/exports/weekly_report.html",
            {"weeklog": appearance.weeklog, "priority_items": [appearance]},
        )

        assert "Præventivt eftersyn" in html

    def test_a_task_without_notes_renders_nothing_extra(self, editor):
        weeklog = WeekLog.objects.create(year=2026, week_number=35)
        item = PriorityItem.objects.create(
            origin_weeklog=weeklog, title="Ny opgave", priority="low", status="ongoing"
        )
        appearance = PriorityItemAppearance.objects.create(
            priority_item=item, weeklog=weeklog, description="Kun beskrivelse"
        )

        html = render_to_string(
            "logbook/partials/priority_item_row.html",
            {"appearance": appearance, "item": item, "is_editor": True},
        )

        assert "Kun beskrivelse" in html
        assert "Noter" not in html
