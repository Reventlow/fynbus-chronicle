"""Case tasks (1.23.0): a sag with open tasks cannot be ready for review or solved."""

import json
from datetime import date

import pytest
from django.urls import reverse

from apps.cves.models import CVE, CaseTasksOpen, CVECase, CVETask


@pytest.fixture
def case(editor):
    return CVECase.objects.create(title="PHP session", created_by=editor, state=CVE.State.PATCHING)


@pytest.fixture
def member(case, cve):
    case.add_cves([cve], None)
    cve.refresh_from_db()
    return cve


def test_open_task_keeps_sag_in_patching_and_blocks_solving(case, member, editor):
    case.set_state(CVE.State.IDENTIFIED, editor)
    CVETask.add(case, title="Opdatér til 8.5.13", user=editor)
    case.refresh_from_db()
    assert case.state == CVE.State.PATCHING
    with pytest.raises(CaseTasksOpen):
        case.set_state(CVE.State.SOLVED, editor, resolution="patched")
    with pytest.raises(CaseTasksOpen):
        case.set_state(CVE.State.REVIEW, editor)
    case.refresh_from_db()
    assert case.state == CVE.State.PATCHING


def test_closing_all_tasks_moves_sag_to_review_and_cves_follow(case, member, editor):
    first = CVETask.add(case, title="Opdatér", user=editor)
    second = CVETask.add(case, title="Gammel version", user=editor)
    first.set_status(CVETask.Status.WAITING_RELEASE, editor)
    case.refresh_from_db()
    assert case.state == CVE.State.PATCHING  # waiting still counts as open
    first.set_status(CVETask.Status.DONE, editor)
    second.set_status(CVETask.Status.IGNORED, editor, note="Ingen licens; migrerer i 2027")
    case.refresh_from_db()
    member.refresh_from_db()
    assert case.state == CVE.State.REVIEW
    assert member.state == CVE.State.REVIEW


def test_ready_sag_is_solved_manually_and_reopens_on_new_task(case, member, editor):
    task = CVETask.add(case, title="Opdatér", user=editor)
    task.set_status(CVETask.Status.DONE, editor)
    case.set_state(CVE.State.SOLVED, editor, resolution="patched")
    case.refresh_from_db()
    assert case.state == CVE.State.SOLVED
    CVETask.add(case, title="Tjek efter opgradering", user=editor)
    case.refresh_from_db()
    assert case.state == CVE.State.PATCHING
    assert case.resolution == ""


def test_ignored_task_needs_a_note(case, editor):
    with pytest.raises(ValueError):
        CVETask.add(case, title="Skift app", user=editor, status=CVETask.Status.IGNORED)
    task = CVETask.add(case, title="Skift app", user=editor)
    with pytest.raises(ValueError):
        task.set_status(CVETask.Status.IGNORED, editor)
    assert task.set_status(CVETask.Status.IGNORED, editor, note="Beslutning: bliver stående")
    task.refresh_from_db()
    assert task.status == CVETask.Status.IGNORED and task.note == "Beslutning: bliver stående"


def test_sag_without_tasks_keeps_manual_states(case, member, editor):
    case.set_state(CVE.State.SOLVED, editor, resolution="not_affected")
    case.refresh_from_db()
    assert case.state == CVE.State.SOLVED
    case.sync_task_state(editor)
    case.refresh_from_db()
    assert case.state == CVE.State.SOLVED


def test_planned_task_has_no_gate(editor):
    planned = CVECase.objects.create(title="Opgradering", kind=CVECase.Kind.TASK, created_by=editor)
    assert not planned.tasks_gate
    assert planned.open_task_count() == 0


def test_task_counts_are_zero_filled(case, editor):
    CVETask.add(case, title="a", user=editor)
    CVETask.add(case, title="b", user=editor, status=CVETask.Status.WAITING_PATCH)
    counts = case.task_counts()
    assert counts[CVETask.Status.OPEN] == 1
    assert counts[CVETask.Status.WAITING_PATCH] == 1
    assert counts[CVETask.Status.IGNORED] == 0


def test_editor_adds_task_on_case_page(editor_client, case):
    response = editor_client.post(reverse("cves:case-task-create", args=[case.pk]), {
        "title": "Opdatér PHP", "status": "waiting_release", "due_date": "2026-12-15",
    })
    assert response.status_code == 302
    task = case.tasks.get()
    assert task.status == CVETask.Status.WAITING_RELEASE
    assert task.due_date == date(2026, 12, 15)
    case.refresh_from_db()
    assert case.state == CVE.State.PATCHING


def test_viewer_cannot_add_or_change_tasks(viewer_client, case, editor):
    task = CVETask.add(case, title="a", user=editor)
    response = viewer_client.post(reverse("cves:case-task-create", args=[case.pk]), {"title": "x"})
    assert response.status_code == 403
    response = viewer_client.post(reverse("cves:case-task-status", args=[case.pk, task.pk]), {"status": "done"})
    assert response.status_code == 403
    task.refresh_from_db()
    assert task.status == CVETask.Status.OPEN


def test_state_button_refuses_solving_with_open_tasks(editor_client, case, editor):
    CVETask.add(case, title="a", user=editor)
    response = editor_client.post(reverse("cves:case-state", args=[case.pk]),
                                  {"state": "solved", "resolution": "patched"}, follow=True)
    case.refresh_from_db()
    assert case.state == CVE.State.PATCHING
    assert "åbne opgaver" in response.content.decode()


def test_task_list_shows_counts_and_filters(editor_client, case, editor):
    CVETask.add(case, title="venter", user=editor, status=CVETask.Status.WAITING_PATCH)
    CVETask.add(case, title="gjort", user=editor, status=CVETask.Status.DONE)
    response = editor_client.get(reverse("cves:task-list"))
    assert response.status_code == 200
    assert response.context["active_count"] == 1
    response = editor_client.get(reverse("cves:task-list") + "?status=done")
    assert [t.title for t in response.context["tasks"]] == ["gjort"]


# -- API -------------------------------------------------------------------

def _api(client, key, method, url, body=None):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {key}"}
    if method == "get":
        return client.get(url, **headers)
    return getattr(client, method)(url, data=json.dumps(body or {}), content_type="application/json", **headers)


def test_api_create_list_and_update_task(client, case, write_key, read_key):
    url = reverse("api:cve-case-task-create", args=[case.pk])
    response = _api(client, write_key, "post", url, {"title": "Opdatér heimdall", "status": "waiting_release"})
    assert response.status_code == 201
    task_id = response.json()["task"]["id"]
    assert response.json()["case"]["state"] == CVE.State.PATCHING

    listing = _api(client, read_key, "get", reverse("api:cve-case-tasks", args=[case.pk]))
    assert listing.json()["open"] == 1

    patch_url = reverse("api:cve-task-update", args=[task_id])
    response = _api(client, write_key, "patch", patch_url, {"status": "ignored"})
    assert response.status_code == 400
    response = _api(client, write_key, "patch", patch_url, {"status": "ignored", "note": "Ingen licens"})
    assert response.status_code == 200
    assert response.json()["case"]["state"] == CVE.State.REVIEW


def test_api_refuses_solving_a_sag_with_open_tasks(client, case, write_key, editor):
    CVETask.add(case, title="a", user=editor)
    response = _api(client, write_key, "post", reverse("api:cve-case-list"),
                    {"id": case.pk, "state": "solved", "resolution": "patched"})
    assert response.status_code == 409
    case.refresh_from_db()
    assert case.state == CVE.State.PATCHING


def test_api_read_key_cannot_create_tasks(client, case, read_key):
    response = _api(client, read_key, "post", reverse("api:cve-case-task-create", args=[case.pk]), {"title": "x"})
    assert response.status_code == 403
