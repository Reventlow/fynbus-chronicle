"""Tests for the open-ticket age ("liggetid") breakdown (FR #8)."""

import pytest
from django.template.loader import render_to_string

from apps.api.serializers import serialize_weeklog
from apps.logbook.exports.markdown import generate_markdown
from apps.logbook.forms import WeekLogForm
from apps.logbook.models import WeekLog
from apps.logbook.services.servicedesk import ServiceDeskClient

pytestmark = pytest.mark.django_db

# One day in milliseconds — ages are computed from epoch-ms timestamps.
DAY_MS = 86_400_000


@pytest.fixture
def weeklog():
    """A week whose 40 open cases are split across all seven age buckets."""
    return WeekLog.objects.create(
        year=2026,
        week_number=35,
        helpdesk_new=12,
        helpdesk_closed=9,
        helpdesk_open=40,
        helpdesk_open_0_7=14,
        helpdesk_open_8_14=6,
        helpdesk_open_15_30=8,
        helpdesk_open_31_90=6,
        helpdesk_open_91_180=2,
        helpdesk_open_181_365=2,
        helpdesk_open_over_365=2,
    )


@pytest.fixture
def weeklog_without_breakdown():
    """A week logged before the breakdown existed — every bucket is 0."""
    return WeekLog.objects.create(year=2026, week_number=36, helpdesk_open=40)


class TestModelProperties:
    def test_buckets_carry_label_count_share_and_colour(self, weeklog):
        buckets = weeklog.helpdesk_age_buckets

        assert [b["count"] for b in buckets] == [14, 6, 8, 6, 2, 2, 2]
        assert [b["share"] for b in buckets] == [35.0, 15.0, 20.0, 15.0, 5.0, 5.0, 5.0]
        assert [b["label"] for b in buckets] == [
            "Under 1 uge",
            "1–2 uger",
            "2 uger – 1 måned",
            "1–3 måneder",
            "3–6 måneder",
            "6–12 måneder",
            "Over 12 måneder",
        ]
        # Colours come from the model spec so every surface matches.
        assert all(b["color"].startswith("#") for b in buckets)

    def test_totals(self, weeklog):
        assert weeklog.helpdesk_open_bucketed == 40
        assert weeklog.helpdesk_open_stale == 12  # everything older than a month
        assert weeklog.has_helpdesk_age_breakdown is True

    def test_week_without_breakdown_is_flagged(self, weeklog_without_breakdown):
        assert weeklog_without_breakdown.helpdesk_open_bucketed == 0
        assert weeklog_without_breakdown.has_helpdesk_age_breakdown is False
        # Shares must not divide by zero.
        assert all(b["share"] == 0.0 for b in weeklog_without_breakdown.helpdesk_age_buckets)


class TestApplyHelpdeskStats:
    def test_writes_counts_and_buckets(self, weeklog_without_breakdown):
        weeklog_without_breakdown.apply_helpdesk_stats(
            {
                "created": 5,
                "closed": 3,
                "open": 7,
                "open_by_age": {
                    "helpdesk_open_0_7": 4,
                    "helpdesk_open_8_14": 2,
                    "helpdesk_open_31_90": 1,
                },
            }
        )
        weeklog_without_breakdown.refresh_from_db()

        assert weeklog_without_breakdown.helpdesk_new == 5
        assert weeklog_without_breakdown.helpdesk_open == 7
        assert weeklog_without_breakdown.helpdesk_open_0_7 == 4
        assert weeklog_without_breakdown.helpdesk_open_31_90 == 1

    def test_missing_age_data_leaves_previous_breakdown_alone(self, weeklog):
        """A failed age query must not silently zero last sync's breakdown."""
        weeklog.apply_helpdesk_stats(
            {"created": 1, "closed": 2, "open": 40, "open_by_age": {}}
        )
        weeklog.refresh_from_db()

        assert weeklog.helpdesk_new == 1
        assert weeklog.helpdesk_open_0_7 == 14
        assert weeklog.helpdesk_open_over_365 == 2


class TestBucketByAge:
    def test_boundaries(self):
        now_ms = 2_000 * DAY_MS
        created = [
            now_ms,  # 0 days
            now_ms - 7 * DAY_MS,  # 7 days — still "under 1 uge"
            now_ms - 8 * DAY_MS,  # 8 days
            now_ms - 14 * DAY_MS,  # 14 days
            now_ms - 15 * DAY_MS,  # 15 days
            now_ms - 30 * DAY_MS,  # 30 days
            now_ms - 31 * DAY_MS,  # 31 days
            now_ms - 90 * DAY_MS,  # 90 days
            now_ms - 91 * DAY_MS,  # 91 days
            now_ms - 180 * DAY_MS,  # 180 days
            now_ms - 181 * DAY_MS,  # 181 days
            now_ms - 365 * DAY_MS,  # 365 days
            now_ms - 366 * DAY_MS,  # 366 days — open-ended bucket
            now_ms - 1_200 * DAY_MS,
        ]

        assert ServiceDeskClient.bucket_by_age(created, now_ms) == {
            "helpdesk_open_0_7": 2,
            "helpdesk_open_8_14": 2,
            "helpdesk_open_15_30": 2,
            "helpdesk_open_31_90": 2,
            "helpdesk_open_91_180": 2,
            "helpdesk_open_181_365": 2,
            "helpdesk_open_over_365": 2,
        }

    def test_future_timestamps_count_as_brand_new(self):
        """Clock skew must not push a ticket into the "over 12 måneder" bucket."""
        now_ms = 1_000 * DAY_MS
        buckets = ServiceDeskClient.bucket_by_age([now_ms + 5 * DAY_MS], now_ms)

        assert buckets["helpdesk_open_0_7"] == 1

    def test_empty_input(self):
        assert set(ServiceDeskClient.bucket_by_age([], 0).values()) == {0}


class TestForm:
    def base_data(self, **overrides):
        data = {
            "year": 2026,
            "week_number": 37,
            "helpdesk_new": 3,
            "helpdesk_closed": 2,
            "helpdesk_open": 10,
            "helpdesk_open_0_7": 0,
            "helpdesk_open_8_14": 0,
            "helpdesk_open_15_30": 0,
            "helpdesk_open_31_90": 0,
            "helpdesk_open_91_180": 0,
            "helpdesk_open_181_365": 0,
            "helpdesk_open_over_365": 0,
            "summary": "",
        }
        data.update(overrides)
        return data

    def test_all_zero_breakdown_is_allowed(self):
        assert WeekLogForm(data=self.base_data()).is_valid()

    def test_matching_breakdown_is_allowed(self):
        form = WeekLogForm(
            data=self.base_data(helpdesk_open_0_7=6, helpdesk_open_31_90=4)
        )
        assert form.is_valid(), form.errors

    def test_breakdown_that_does_not_add_up_is_rejected(self):
        form = WeekLogForm(data=self.base_data(helpdesk_open_0_7=6))

        assert not form.is_valid()
        assert "summer til 6" in form.non_field_errors()[0]


class TestReportOutput:
    def test_html_report_renders_the_breakdown(self, weeklog):
        html = render_to_string(
            "logbook/exports/weekly_report.html", {"weeklog": weeklog}
        )

        assert "Åbne sager fordelt på liggetid" in html
        assert "Over 12 måneder" in html
        assert "12 af 40 åbne sager har ligget i mere end 1 måned." in html

    def test_html_report_omits_the_section_without_data(self, weeklog_without_breakdown):
        html = render_to_string(
            "logbook/exports/weekly_report.html",
            {"weeklog": weeklog_without_breakdown},
        )

        assert "liggetid" not in html.lower()

    def test_bar_widths_use_a_decimal_point(self):
        """Danish L10N formats 12.5 as "12,5" — invalid inside a CSS width.

        The bar widths therefore force unlocalized output; without it the
        browser/WeasyPrint drops the width and every bar renders the same.
        """
        weeklog = WeekLog.objects.create(
            year=2026,
            week_number=38,
            helpdesk_open=8,
            helpdesk_open_0_7=1,
            helpdesk_open_8_14=7,
        )

        for template in (
            "logbook/exports/weekly_report.html",
            "logbook/exports/email_body.html",
            "dashboard/partials/helpdesk_stats.html",
        ):
            html = render_to_string(template, {"weeklog": weeklog})
            assert "12.5%" in html, template
            assert "12,5%" not in html, template

    def test_email_body_renders_the_breakdown(self, weeklog):
        html = render_to_string("logbook/exports/email_body.html", {"weeklog": weeklog})

        assert "Åbne sager fordelt på liggetid" in html

    def test_markdown_report_renders_a_table(self, weeklog):
        markdown = generate_markdown(weeklog)

        assert "### Åbne sager fordelt på liggetid" in markdown
        assert "| Under 1 uge | 14 | 35% |" in markdown

    def test_markdown_report_omits_the_section_without_data(
        self, weeklog_without_breakdown
    ):
        assert "liggetid" not in generate_markdown(weeklog_without_breakdown).lower()


class TestApiPayload:
    def test_serializer_exposes_buckets(self, weeklog):
        data = serialize_weeklog(weeklog)

        assert data["helpdesk_open_stale"] == 12
        assert len(data["helpdesk_open_by_age"]) == 7
        assert data["helpdesk_open_by_age"][0] == {
            "key": "helpdesk_open_0_7",
            "label": "Under 1 uge",
            "count": 14,
            "share": 35.0,
        }
