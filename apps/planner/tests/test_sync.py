"""Mirroring the plan, and the scheduler job around it."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.logbook.management.commands.run_scheduler import ServiceDeskJob, tick_all
from apps.planner.graph import PlannerError
from apps.planner.models import (
    DESCRIPTION_MAX,
    PendingSignIn,
    PlannerBucket,
    PlannerTask,
    SyncState,
)
from apps.planner.sync import PlannerJob, mirror_plan

from .conftest import PLAN, FakeGraph


@pytest.mark.django_db
def test_mirror_stores_plan_buckets_tasks(planner, fake_graph):
    counts = mirror_plan(fake_graph, PLAN)
    assert counts == {"buckets": 2, "tasks": 3, "details": 1, "removed": 0}
    t1 = PlannerTask.objects.get(id="t1")
    assert t1.bucket.name.startswith("Backlog")
    assert t1.label_keys == ["category16"] and t1.plan.labels == {"category16": "Ubehandlet"}
    assert (t1.checklist_total, t1.checklist_done) == (2, 1)
    assert t1.due_date.isoformat() == "2026-12-31"
    assert len(t1.description) == DESCRIPTION_MAX
    assert PlannerTask.objects.get(id="t2").is_complete
    assert PlannerTask.objects.get(id="t3").title == "<script>alert(1)</script>"  # stored as text


@pytest.mark.django_db
def test_mirror_fetches_details_only_for_changed_tasks(planner, fake_graph):
    mirror_plan(fake_graph, PLAN)
    again = FakeGraph()
    mirror_plan(again, PLAN)
    assert "/planner/tasks/t1/details" not in again.calls
    assert "/users/u1" not in again.calls  # names are cached
    again.data[f"/planner/plans/{PLAN}/tasks"]["value"][0]["@odata.etag"] = 'W/"changed"'
    third = FakeGraph(again.data)
    mirror_plan(third, PLAN)
    assert "/planner/tasks/t1/details" in third.calls
    full = FakeGraph(again.data)
    mirror_plan(full, PLAN, full_details=True)
    assert "/planner/tasks/t1/details" in full.calls


@pytest.mark.django_db
def test_mirror_removes_what_planner_removed(planner, fake_graph):
    mirror_plan(fake_graph, PLAN)
    data = fake_graph.data
    data[f"/planner/plans/{PLAN}/buckets"]["value"].pop()  # b2 gone
    data["https://graph.microsoft.com/v1.0/next-page"]["value"] = []  # t3 gone
    counts = mirror_plan(FakeGraph(data), PLAN)
    assert not PlannerTask.objects.filter(id="t3").exists()
    assert not PlannerBucket.objects.filter(id="b2").exists()
    assert PlannerTask.objects.get(id="t2").bucket is None  # its bucket vanished
    assert counts["removed"] == 1


# --- the job --------------------------------------------------------------------


class Auth:
    redeemed = []

    def __init__(self, *a, **kw):
        pass

    def access_token(self):
        return "tok"

    def redeem(self, pending):
        Auth.redeemed.append(pending.pk)
        pending.status = PendingSignIn.Status.DONE
        pending.save()


def _job(graph=None):
    graph = graph or FakeGraph()
    return PlannerJob(auth_factory=Auth, graph_factory=lambda token: graph), graph


@pytest.mark.django_db
def test_first_tick_syncs_and_schedules_next(planner):
    job, graph = _job()
    job.tick()
    state = SyncState.get()
    assert state.last_success_at and state.last_error == "" and state.running_since is None
    assert state.next_due_at > timezone.now()
    assert PlannerTask.objects.count() == 3


@pytest.mark.django_db
def test_not_due_and_not_requested_does_nothing(planner):
    job, graph = _job()
    job.tick()
    graph.calls.clear()
    job.tick()
    assert graph.calls == []


@pytest.mark.django_db
def test_sync_now_request_runs_after_cooldown(planner):
    job, graph = _job()
    job.tick()
    graph.calls.clear()
    SyncState.objects.filter(pk=1).update(requested_at=timezone.now())
    job.tick()  # within 30 s of the last run: wait
    assert graph.calls == []
    job.tick(now=timezone.now() + timedelta(seconds=31))
    assert graph.calls and not SyncState.get().is_requested


@pytest.mark.django_db
def test_failure_is_recorded_and_retried_later(planner):
    class Broken(FakeGraph):
        def get(self, path, params=None):
            raise PlannerError("Microsoft Graph svarede 403 Forbidden")
    job, _ = _job(Broken())
    job.tick()
    state = SyncState.get()
    assert "403" in state.last_error and state.last_success_at is None
    assert state.next_due_at > timezone.now() and state.running_since is None


@pytest.mark.django_db
def test_pending_sign_in_is_handed_over_on_tick(planner):
    pending = PendingSignIn.objects.create(sealed="x")
    job, _ = _job()
    job.tick()
    assert pending.pk in Auth.redeemed


@pytest.mark.django_db
def test_connecting_clears_old_not_connected_error(planner):
    SyncState.objects.update_or_create(pk=1, defaults={"last_error": "Planner er ikke forbundet."})
    PendingSignIn.objects.create(sealed="x")
    job, _ = _job()
    job.handle_sign_ins()
    state = SyncState.get()
    assert state.last_error == "" and state.next_due_at is not None


def test_job_disabled_without_plan(planner, settings):
    settings.PLANNER_PLAN_ID = ""
    assert not PlannerJob.enabled()


# --- the scheduler loop ---------------------------------------------------------------


def test_servicedesk_job_keeps_its_interval(settings, monkeypatch):
    settings.SERVICEDESK_SYNC_INTERVAL = 300
    calls = []
    monkeypatch.setattr("apps.logbook.management.commands.run_scheduler.sync_current_week_tickets",
                        lambda: calls.append("week"))
    monkeypatch.setattr("apps.logbook.management.commands.run_scheduler.sync_ticket_mirror",
                        lambda full: calls.append(("mirror", full)) or 1)
    clock = iter([0, 0, 5, 299, 300, 300])  # run 1 reads it twice, run 2 twice
    job = ServiceDeskJob(clock=lambda: next(clock))
    job.tick()               # t=0: runs, full mirror
    job.tick()               # t=5: not due
    job.tick()               # t=299: not due
    job.tick()               # t=300: runs, incremental mirror
    assert calls == ["week", ("mirror", True), "week", ("mirror", False)]


def test_one_failing_job_does_not_stop_the_others():
    ran = []

    class Bad:
        name = "bad"

        def tick(self):
            raise RuntimeError("boom")

    class Good:
        name = "good"

        def tick(self):
            ran.append(True)

    tick_all([Bad(), Good()])
    assert ran == [True]
