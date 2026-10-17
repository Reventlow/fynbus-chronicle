"""Open helpdesk tickets by category: the model helper, the dashboard card
and the week report (PDF/HTML context, email, Markdown)."""

from datetime import datetime, timedelta

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.logbook.exports.email import CATEGORY_CHART_CID, send_weeklog_email
from apps.logbook.exports.html import generate_html
from apps.logbook.exports.markdown import generate_markdown
from apps.logbook.models import HelpdeskTicket, WeekLog

pytestmark = pytest.mark.django_db


def ticket(sdp_id, created, closed=None, category=""):
    return HelpdeskTicket.objects.create(
        sdp_id=sdp_id, created_at=created, closed_at=closed, is_open=closed is None,
        status="Åben" if closed is None else "Lukket", category=category,
    )


@pytest.fixture
def open_tickets():
    now = timezone.now()
    ticket(1, now - timedelta(days=5), category="Hardware & enheder")
    ticket(2, now - timedelta(days=4), category="Hardware & enheder")
    ticket(3, now - timedelta(days=3), category="Telefoni & kontaktcenter")
    ticket(4, now - timedelta(days=2))
    ticket(5, now - timedelta(days=9), now - timedelta(days=1), category="Øvrigt")  # closed


def test_open_now_by_category(open_tickets):
    result = HelpdeskTicket.open_by_category()
    assert result["total"] == 4
    assert result["uncategorised"] == 1
    labels = [c["label"] for c in result["categories"]]
    # Largest first, "Ingen kategori" always last and grey.
    assert labels == ["Hardware & enheder", "Telefoni & kontaktcenter", "Ingen kategori"]
    assert result["categories"][0]["share"] == 50.0
    assert result["categories"][-1]["color"] == HelpdeskTicket.NO_CATEGORY_COLOR


def test_open_at_a_past_instant_includes_tickets_closed_since(open_tickets):
    at = timezone.now() - timedelta(days=2, hours=12)
    result = HelpdeskTicket.open_by_category(at)
    # Tickets 1–3 existed; ticket 5 was still open then; ticket 4 not created yet.
    assert result["total"] == 4
    assert "Øvrigt" in [c["label"] for c in result["categories"]]


def test_empty_mirror():
    assert HelpdeskTicket.open_by_category() == {
        "total": 0, "categorised": 0, "uncategorised": 0, "categories": [],
    }


def test_weeklog_uses_now_for_the_current_week(open_tickets):
    weeklog = WeekLog.get_or_create_current_week()
    assert weeklog.helpdesk_open_by_category()["total"] == 4


def test_weeklog_uses_the_week_end_for_a_past_week():
    # A ticket opened in ISO week 10 of 2026 and closed in week 12.
    created = timezone.make_aware(datetime(2026, 3, 3, 10, 0))
    ticket(1, created, created + timedelta(days=14), category="Øvrigt")
    week_10 = WeekLog.objects.create(year=2026, week_number=10)
    week_13 = WeekLog.objects.create(year=2026, week_number=13)
    assert week_10.helpdesk_open_by_category()["total"] == 1
    assert week_13.helpdesk_open_by_category()["total"] == 0




def test_week_report_html_and_markdown(open_tickets):
    weeklog = WeekLog.get_or_create_current_week()
    html = generate_html(weeklog)
    assert "Åbne sager fordelt på kategori" in html
    assert "4 åbne sager ved ugens udgang, heraf 1 uden kategori" in html
    markdown = generate_markdown(weeklog)
    assert "### Åbne sager fordelt på kategori" in markdown
    assert "| Hardware & enheder | 2 | 50% |" in markdown


def test_week_report_without_mirror_has_no_section():
    weeklog = WeekLog.get_or_create_current_week()
    assert "Åbne sager fordelt på kategori" not in generate_html(weeklog)
    assert "Åbne sager fordelt på kategori" not in generate_markdown(weeklog)


def test_week_report_email_attaches_the_donut(settings, open_tickets):
    settings.CHRONICLE_EMAIL_RECIPIENTS = ["team@fynbus.dk"]
    weeklog = WeekLog.get_or_create_current_week()
    ok, message = send_weeklog_email(weeklog, format="html", from_email="gorm@fynbus.dk")
    assert ok, message
    sent = mail.outbox[0]
    assert f"cid:{CATEGORY_CHART_CID}" in sent.body
    content_ids = [part.get("Content-ID") for part in sent.attachments if hasattr(part, "get")]
    assert f"<{CATEGORY_CHART_CID}>" in content_ids
