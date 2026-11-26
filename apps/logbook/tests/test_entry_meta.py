"""Forslag #20: "Tilføjet … af …" on the entries of the week log page.

Priority appearances and absences remember who added them
(``created_by``), and the week log page prints a small meta line under each
entry with the local (Europe/Copenhagen) time and the person. The line is
internal: the mail, PDF, HTML and Markdown exports must never show it.
"""

import json
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, date, datetime, timedelta

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse

from apps.accounts.models import APIKey
from apps.logbook.exports.email import send_weeklog_email
from apps.logbook.exports.html import generate_html
from apps.logbook.exports.markdown import generate_markdown
from apps.logbook.exports.pdf import generate_pdf
from apps.logbook.models import (
    Absence,
    HelpdeskTicket,
    PriorityItem,
    PriorityItemAppearance,
    WeekLog,
)

pytestmark = pytest.mark.django_db

# 07:55 UTC on 25 Nov 2026 is 08:55 in Copenhagen (CET, UTC+1).
ADDED_UTC = datetime(2026, 11, 25, 7, 55, tzinfo=UTC)
ADDED_LOCAL = "25.11.2026 kl. 08:55"


@pytest.fixture
def author():
    return User.objects.create_user("mra", password="x", first_name="Mette", last_name="Forfatter")


@pytest.fixture
def week():
    return WeekLog.objects.create(year=2026, week_number=48)


def detail(client, wl) -> str:
    return client.get(reverse("logbook:weeklog-detail", args=[wl.year, wl.week_number])).content.decode()


def add_task(wl, *, title="Opgave", by=None, description="") -> PriorityItemAppearance:
    item = PriorityItem.objects.create(origin_weeklog=wl, title=title, priority="medium", status="ongoing")
    return PriorityItemAppearance.objects.create(
        priority_item=item, weeklog=wl, created_by=by, description=description
    )


def add_absence(wl, *, by=None, name="Fraværende") -> Absence:
    return Absence.objects.create(
        weeklog=wl, staff_name=name, absence_type="vacation",
        start_date=date(2026, 11, 23), end_date=date(2026, 11, 24), created_by=by,
    )


def stamp(obj, *, created=ADDED_UTC, updated=None) -> None:
    """Pin created_at / updated_at (auto_now fields) with a queryset update."""
    type(obj).objects.filter(pk=obj.pk).update(created_at=created, updated_at=updated or created)


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------


def test_page_shows_local_time_and_full_name(client, author, week):
    client.force_login(author)
    stamp(add_task(week, by=author))
    stamp(add_absence(week, by=author))
    body = detail(client, week)
    assert body.count(f'Tilføjet <span class="num">{ADDED_LOCAL}</span> af Mette Forfatter') == 2


def test_page_falls_back_to_username(client, week):
    user = User.objects.create_user("nonamer", password="x")
    client.force_login(user)
    stamp(add_task(week, by=user))
    assert f"{ADDED_LOCAL}</span> af nonamer" in detail(client, week)


def test_page_without_created_by_has_no_af(client, author, week):
    client.force_login(author)
    stamp(add_task(week))
    stamp(add_absence(week))
    body = detail(client, week)
    lines = re.findall(r'<div class="entry-meta"[^>]*>(.*?)</div>', body, re.S)
    assert len(lines) == 2
    for line in lines:
        assert ADDED_LOCAL in line
        assert " af " not in line
        assert "redigeret" not in line


def test_page_shows_redigeret_only_when_clearly_edited(client, author, week):
    client.force_login(author)
    stamp(add_task(week, title="Rettet", by=author),
          updated=ADDED_UTC + timedelta(days=1, hours=1, minutes=5))
    stamp(add_absence(week, by=author), updated=ADDED_UTC + timedelta(seconds=2))
    body = detail(client, week)
    assert body.count("redigeret") == 1
    assert 'redigeret <span class="num">26.11.2026 kl. 10:00</span>' in body


def test_edited_at_threshold(week):
    appearance = add_task(week)
    stamp(appearance, updated=ADDED_UTC + timedelta(seconds=30))
    appearance.refresh_from_db()
    assert appearance.edited_at is None
    stamp(appearance, updated=ADDED_UTC + timedelta(minutes=5))
    appearance.refresh_from_db()
    assert appearance.edited_at == ADDED_UTC + timedelta(minutes=5)


# ---------------------------------------------------------------------------
# created_by is set by every create path that has a user
# ---------------------------------------------------------------------------


def test_new_task_from_week_log_page(client, author, week):
    client.force_login(author)
    response = client.post(
        reverse("logbook:priority-item-create") + f"?weeklog={week.pk}",
        {"title": "Ny opgave", "priority": "medium", "status": "not_started", "description": "x"},
    )
    assert response.status_code == 200
    appearance = PriorityItemAppearance.objects.get(priority_item__title="Ny opgave")
    assert appearance.created_by == author
    # The row HTMX swaps in carries the meta line too.
    assert "af Mette Forfatter" in response.content.decode()


def test_new_absence_from_week_log_page(client, author, week):
    client.force_login(author)
    response = client.post(
        reverse("logbook:absence-create") + f"?weeklog={week.pk}",
        {"staff_name": "Kollega", "absence_type": "sick",
         "start_date": "2026-11-24", "end_date": "2026-11-24", "notes": ""},
    )
    assert response.status_code == 200
    assert Absence.objects.get(staff_name="Kollega").created_by == author
    assert "af Mette Forfatter" in response.content.decode()


def test_carry_from_open_tasks(client, author, week):
    client.force_login(author)
    old = WeekLog.objects.create(year=2026, week_number=47)
    item = add_task(old, title="Gammel").priority_item
    client.post(reverse("logbook:weeklog-add-existing-post", args=[week.pk]), {"item_ids": [item.pk]})
    assert PriorityItemAppearance.objects.get(priority_item=item, weeklog=week).created_by == author


def test_reopen_puts_task_on_current_week_as_the_user(client, author):
    client.force_login(author)
    current = WeekLog.get_or_create_current_week()
    old = WeekLog.objects.create(year=2020, week_number=10)
    item = add_task(old, title="Lukket").priority_item
    item.status = PriorityItem.Status.COMPLETED
    item.save()
    client.post(reverse("logbook:priority-item-reopen", args=[item.pk]))
    assert PriorityItemAppearance.objects.get(priority_item=item, weeklog=current).created_by == author


def test_system_reopen_leaves_created_by_empty():
    current = WeekLog.get_or_create_current_week()
    old = WeekLog.objects.create(year=2020, week_number=11)
    item = add_task(old, title="Planner-sync").priority_item
    item.status = PriorityItem.Status.COMPLETED
    item.save()
    item.reopen(into_weeklog=current)
    assert PriorityItemAppearance.objects.get(priority_item=item, weeklog=current).created_by is None


def test_reopen_keeps_an_existing_appearances_author(author):
    current = WeekLog.get_or_create_current_week()
    other = User.objects.create_user("other")
    appearance = add_task(current, by=author)
    appearance.priority_item.reopen(into_weeklog=current, by=other)
    appearance.refresh_from_db()
    assert appearance.created_by == author


@pytest.fixture
def api_key(author):
    _, raw = APIKey.generate(user=author, scope=APIKey.Scope.WRITE, label="test")
    return raw


def test_api_create_sets_the_keys_user(client, api_key, author, week):
    response = client.post(
        f"/api/v1/weeklogs/{week.year}/{week.week_number}/priority-items/",
        data=json.dumps({"title": "Fra API"}), content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {api_key}",
    )
    assert response.status_code == 201
    assert PriorityItemAppearance.objects.get(priority_item__title="Fra API").created_by == author


def test_api_carry_sets_the_keys_user(client, api_key, author, week):
    item = add_task(WeekLog.objects.create(year=2026, week_number=46), title="Båret").priority_item
    response = client.post(
        f"/api/v1/weeklogs/{week.year}/{week.week_number}/priority-items/carry/",
        data=json.dumps({"item_ids": [item.pk]}), content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {api_key}",
    )
    assert response.status_code == 201
    assert PriorityItemAppearance.objects.get(priority_item=item, weeklog=week).created_by == author


def test_task_from_planner_card_and_servicedesk_ticket(author):
    from apps.planner.models import PlannerTask
    from apps.planner.views import _priority_from as from_card
    from apps.servicedesk.views import _priority_from as from_ticket

    task = PlannerTask(title="Kort", priority=5, description="")
    ticket = HelpdeskTicket(sdp_id=1234, subject="Ticket", status="Åben")
    for item in (from_card(task, author), from_ticket(ticket, author)):
        assert item.appearances.get().created_by == author


# ---------------------------------------------------------------------------
# Never in the exports
# ---------------------------------------------------------------------------


@pytest.fixture
def exported_week(settings, author, week):
    settings.CHRONICLE_EMAIL_RECIPIENTS = ["it@example.test"]
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    stamp(add_task(week, title="EKSPORT-OPGAVE", by=author, description="BESKRIVELSE"),
          updated=ADDED_UTC + timedelta(days=1))
    stamp(add_absence(week, by=author, name="EKSPORT-FRAVÆR"), updated=ADDED_UTC + timedelta(days=1))
    return week


def assert_no_meta(text: str) -> None:
    # The entries themselves are there ...
    assert "EKSPORT-OPGAVE" in text and "EKSPORT-FRAVÆR" in text
    # ... but not who added them, or when.
    for needle in ("Tilføjet", "redigeret", "Forfatter", "08:55", "25.11.2026"):
        assert needle not in text, needle


def test_not_in_mail(exported_week):
    ok, msg = send_weeklog_email(exported_week, format="html")
    assert ok, msg
    message = mail.outbox[-1]
    assert_no_meta(message.body)
    for alternative, _ in getattr(message, "alternatives", []):
        assert_no_meta(alternative)


def test_not_in_html_download(exported_week):
    assert_no_meta(generate_html(exported_week))


def test_not_in_markdown(exported_week):
    assert_no_meta(generate_markdown(exported_week))


@pytest.mark.skipif(not shutil.which("pdftotext"), reason="pdftotext (poppler) not installed")
def test_not_in_pdf(exported_week):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(generate_pdf(exported_week))
        f.flush()
        text = subprocess.run(["pdftotext", f.name, "-"], capture_output=True, text=True, check=True).stdout
    assert_no_meta(text)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def entry_meta_migration():
    """The forslag #20 migration module, found by suffix so it survives a renumbering."""
    import importlib
    from pathlib import Path

    import apps.logbook.migrations as migrations_pkg

    (path,) = Path(migrations_pkg.__file__).parent.glob("*_entry_created_by.py")
    return importlib.import_module(f"apps.logbook.migrations.{path.stem}")


def test_migration_does_not_mark_old_absences_as_edited(week):
    """Adding updated_at fills it with "now"; the data step resets it to created_at."""
    from django.apps import apps as django_apps

    absence = add_absence(week)
    stamp(absence, updated=ADDED_UTC + timedelta(days=30))
    entry_meta_migration().absences_unedited(django_apps, None)
    absence.refresh_from_db()
    assert absence.updated_at == absence.created_at
    assert absence.edited_at is None


# Migration 0008 ran on 7 May 2026 and bulk-created one appearance per
# existing task, stamping them all with that moment.
BACKFILL_RAN_UTC = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
TASK_ADDED_UTC = datetime(2026, 2, 17, 9, 30, tzinfo=UTC)


def backfilled_task(wl, *, edited=None) -> PriorityItemAppearance:
    """A task added in Feb whose origin appearance 0008 stamped in May."""
    appearance = add_task(wl)
    PriorityItem.objects.filter(pk=appearance.priority_item_id).update(created_at=TASK_ADDED_UTC)
    # bulk_create sets created_at and updated_at microseconds apart.
    stamp(
        appearance,
        created=BACKFILL_RAN_UTC,
        updated=edited or BACKFILL_RAN_UTC + timedelta(microseconds=7),
    )
    return appearance


def run_backfill_repair():
    from django.apps import apps as django_apps

    entry_meta_migration().backfilled_appearances_dated(django_apps, None)


def test_migration_dates_backfilled_appearances_by_their_task():
    """The 0008 backfill time is replaced by the task's own creation time, unedited."""
    old_week = WeekLog.objects.create(year=2026, week_number=8)
    appearance = backfilled_task(old_week)
    run_backfill_repair()
    appearance.refresh_from_db()
    assert appearance.created_at == TASK_ADDED_UTC
    assert appearance.updated_at == TASK_ADDED_UTC
    assert appearance.edited_at is None


def test_migration_keeps_a_real_edit_on_a_backfilled_appearance():
    """A backfilled row edited later keeps that edit time, so it still reads "redigeret"."""
    old_week = WeekLog.objects.create(year=2026, week_number=8)
    edited = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
    appearance = backfilled_task(old_week, edited=edited)
    run_backfill_repair()
    appearance.refresh_from_db()
    assert appearance.created_at == TASK_ADDED_UTC
    assert appearance.edited_at == edited


def test_migration_leaves_other_appearances_alone(author, week):
    """Rows made together with their task, carried rows and rows with an author keep their times."""
    same_request = add_task(week)
    PriorityItem.objects.filter(pk=same_request.priority_item_id).update(
        created_at=ADDED_UTC - timedelta(seconds=2)
    )
    stamp(same_request)

    carried_from = WeekLog.objects.create(year=2026, week_number=47)
    origin = add_task(carried_from)
    PriorityItem.objects.filter(pk=origin.priority_item_id).update(created_at=ADDED_UTC - timedelta(days=7))
    stamp(origin, created=ADDED_UTC - timedelta(days=7))
    carried = PriorityItemAppearance.objects.create(priority_item=origin.priority_item, weeklog=week)
    stamp(carried)

    authored = add_task(week, by=author)
    PriorityItem.objects.filter(pk=authored.priority_item_id).update(created_at=TASK_ADDED_UTC)
    stamp(authored)

    run_backfill_repair()
    for row in (same_request, carried, authored):
        row.refresh_from_db()
        assert row.created_at == ADDED_UTC
