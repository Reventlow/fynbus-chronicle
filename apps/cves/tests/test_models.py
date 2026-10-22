"""CVE model behaviour: ids, derived fields, state transitions and the
time-window queries behind the Kontrolpanel card and the week log."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.cves.models import CVE, CVEComment, CVELink, iso_week_bounds, normalise_cve_id

pytestmark = pytest.mark.django_db


class TestCveId:
    def test_normalises_case_and_whitespace(self):
        assert normalise_cve_id("  cve-2026-1234 ") == "CVE-2026-1234"

    def test_accepts_long_sequence_numbers(self):
        assert normalise_cve_id("CVE-2026-109618") == "CVE-2026-109618"

    @pytest.mark.parametrize("bad", ["", "CVE-26-1234", "CVE-2026-123", "2026-1234", "CVE-2026-12a4", "GHSA-xxxx"])
    def test_rejects_malformed(self, bad):
        with pytest.raises(ValidationError):
            normalise_cve_id(bad)

    def test_save_upper_cases(self):
        cve = CVE.objects.create(cve_id="cve-2026-0001", subject="x")
        assert cve.cve_id == "CVE-2026-0001"

    def test_full_clean_rejects_malformed(self):
        with pytest.raises(ValidationError):
            CVE(cve_id="nope", subject="x").full_clean()


class TestDerivedFields:
    def test_cvefeed_url_defaults_from_id(self):
        cve = CVE.objects.create(cve_id="CVE-2026-0002", subject="x")
        assert cve.cvefeed_url == "https://cvefeed.io/vuln/detail/CVE-2026-0002"

    def test_explicit_cvefeed_url_is_kept(self):
        cve = CVE.objects.create(cve_id="CVE-2026-0003", subject="x", cvefeed_url="https://example.com/a")
        assert cve.cvefeed_url == "https://example.com/a"

    @pytest.mark.parametrize(
        ("cvss", "severity"),
        [
            ("10.0", "critical"),
            ("9.0", "critical"),
            ("8.9", "high"),
            ("7.0", "high"),
            ("6.9", "medium"),
            ("4.0", "medium"),
            ("3.9", "low"),
            ("0.1", "low"),
            ("0.0", "none"),
            (None, "none"),
        ],
    )
    def test_severity_from_cvss(self, cvss, severity):
        cve = CVE.objects.create(cve_id="CVE-2026-0004", subject="x", cvss=cvss)
        assert cve.severity == severity

    def test_explicit_severity_wins(self):
        cve = CVE.objects.create(cve_id="CVE-2026-0005", subject="x", cvss="9.8", severity="low")
        assert cve.severity == "low"


class TestStateTransitions:
    def test_default_state_is_identified(self, cve):
        assert cve.state == CVE.State.IDENTIFIED
        assert cve.solved_at is None

    def test_solving_stamps_and_records(self, cve, editor):
        assert cve.set_state(CVE.State.SOLVED, editor) is True
        cve.refresh_from_db()
        assert cve.state == "solved"
        assert cve.solved_at is not None
        assert cve.solved_by == editor
        entry = cve.comments.get()
        assert entry.kind == CVEComment.Kind.STATE
        assert entry.text == "Status: Identificeret → Løst"
        assert entry.author == editor

    def test_leaving_solved_clears_stamp(self, cve, editor):
        cve.set_state(CVE.State.SOLVED, editor)
        cve.set_state(CVE.State.PATCHING, editor)
        cve.refresh_from_db()
        assert cve.solved_at is None
        assert cve.solved_by is None
        assert cve.comments.first().text == "Status: Løst → Patcher"
        assert cve.comments.count() == 2

    def test_same_state_is_a_no_op(self, cve, editor):
        assert cve.set_state(CVE.State.IDENTIFIED, editor) is False
        assert cve.comments.count() == 0

    def test_unknown_state_raises(self, cve, editor):
        with pytest.raises(ValueError):
            cve.set_state("bogus", editor)


class TestTouch:
    def _age(self, cve, days):
        old = timezone.now() - timedelta(days=days)
        CVE.objects.filter(pk=cve.pk).update(updated_at=old, created_at=old)
        cve.refresh_from_db()
        return old

    def test_comment_touches_cve(self, cve, editor):
        old = self._age(cve, 40)
        CVEComment.objects.create(cve=cve, text="hej", author=editor)
        cve.refresh_from_db()
        assert cve.updated_at > old

    def test_link_touches_cve(self, cve, editor):
        old = self._age(cve, 40)
        CVELink.objects.create(cve=cve, url="https://example.com", added_by=editor)
        cve.refresh_from_db()
        assert cve.updated_at > old


class TestActiveInLast:
    def test_window(self, editor):
        recent = CVE.objects.create(cve_id="CVE-2026-1001", subject="ny")
        stale = CVE.objects.create(cve_id="CVE-2026-1002", subject="gammel")
        old = timezone.now() - timedelta(days=45)
        CVE.objects.filter(pk=stale.pk).update(updated_at=old, created_at=old)
        assert list(CVE.objects.active_in_last(30)) == [recent]

    def test_comment_brings_it_back(self, editor):
        stale = CVE.objects.create(cve_id="CVE-2026-1003", subject="gammel")
        old = timezone.now() - timedelta(days=45)
        CVE.objects.filter(pk=stale.pk).update(updated_at=old, created_at=old)
        CVEComment.objects.create(cve=stale, text="stadig relevant")
        assert stale in CVE.objects.active_in_last(30)


class TestOpenDuring:
    """ISO week 2026-W20 runs Mon 11 May – Sun 17 May 2026."""

    @pytest.fixture
    def weeks(self):
        return iso_week_bounds(2026, 20), iso_week_bounds(2026, 21)

    @staticmethod
    def at(y, m, d, h=12):
        return timezone.make_aware(datetime(y, m, d, h))

    def make(self, n, created, solved=None):
        cve = CVE.objects.create(cve_id=f"CVE-2026-{n:04d}", subject="x", created_at=created)
        if solved:
            CVE.objects.filter(pk=cve.pk).update(state=CVE.State.SOLVED, solved_at=solved)
        return cve

    def test_bounds_are_local_midnight(self):
        start, end = iso_week_bounds(2026, 20)
        assert timezone.localtime(start).isoformat().startswith("2026-05-11T00:00:00")
        assert end - start == timedelta(days=7)

    def test_open_across_weeks(self, weeks):
        (s20, e20), (s21, e21) = weeks
        cve = self.make(1, self.at(2026, 5, 1))
        assert cve in CVE.objects.open_during(s20, e20)
        assert cve in CVE.objects.open_during(s21, e21)

    def test_solved_mid_week_shows_that_week_only(self, weeks):
        (s20, e20), (s21, e21) = weeks
        cve = self.make(2, self.at(2026, 5, 1), solved=self.at(2026, 5, 13))
        assert cve in CVE.objects.open_during(s20, e20)
        assert cve not in CVE.objects.open_during(s21, e21)
        cve.refresh_from_db()
        assert cve.solved_within(s20, e20)
        assert not cve.solved_within(s21, e21)

    def test_created_after_week_not_shown(self, weeks):
        (s20, e20), _ = weeks
        cve = self.make(3, self.at(2026, 5, 18, 9))
        assert cve not in CVE.objects.open_during(s20, e20)

    def test_solved_before_week_not_shown(self, weeks):
        (s20, e20), _ = weeks
        cve = self.make(4, self.at(2026, 4, 1), solved=self.at(2026, 5, 10, 23))
        assert cve not in CVE.objects.open_during(s20, e20)

    def test_created_last_minute_of_week_is_shown(self, weeks):
        (s20, e20), _ = weeks
        cve = self.make(5, e20 - timedelta(minutes=1))
        assert cve in CVE.objects.open_during(s20, e20)


class TestOpenFirst:
    def test_patching_identified_solved(self, editor):
        solved = CVE.objects.create(cve_id="CVE-2026-2001", subject="a")
        solved.set_state(CVE.State.SOLVED, editor)
        identified = CVE.objects.create(cve_id="CVE-2026-2002", subject="b")
        patching = CVE.objects.create(cve_id="CVE-2026-2003", subject="c")
        patching.set_state(CVE.State.PATCHING, editor)
        assert list(CVE.objects.open_first()) == [patching, identified, solved]


def test_cvss_is_decimal(cve):
    cve.refresh_from_db()
    assert cve.cvss == Decimal("9.8")
