"""The sync container waits for the web container's migrations."""

from unittest import mock

import pytest

from apps.logbook.management.commands import run_scheduler

pytestmark = pytest.mark.django_db


def test_no_pending_migrations_in_a_migrated_database():
    assert run_scheduler.pending_migrations() == []


def test_waits_until_migrations_are_applied():
    answers = iter([["logbook.0016_new"], ["logbook.0016_new"], []])
    sleeps = []
    with mock.patch.object(run_scheduler, "pending_migrations", lambda: next(answers)):
        run_scheduler.wait_for_migrations(sleep=sleeps.append, poll=10)
    assert sleeps == [10, 10]
