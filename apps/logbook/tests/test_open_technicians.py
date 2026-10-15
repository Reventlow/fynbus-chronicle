"""Open helpdesk tickets by technician: the model helper, the dashboard card
and the week report (HTML context, email, Markdown)."""

from datetime import datetime, timedelta

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.logbook.exports.email import TECHNICIAN_CHART_CID, send_weeklog_email
from apps.logbook.exports.html import generate_html
from apps.logbook.exports.markdown import generate_markdown
from apps.logbook.models import HelpdeskTicket, WeekLog

pytestmark = pytest.mark.django_db


def ticket(sdp_id, created, closed=None, technician=""):
    return HelpdeskTicket.objects.create(
        sdp_id=sdp_id, created_at=created, closed_at=closed, is_open=closed is None,
        status="Åben" if closed is None else "Lukket", technician=technician,
    )


@pytest.fixture
def open_tickets():
    now = timezone.now()
    ticket(1, now - timedelta(days=5), technician="Peter Malmborg")
    ticket(2, now - timedelta(days=4), technician="Peter Malmborg")
    ticket(3, now - timedelta(days=3), technician="ANONYMOUS_301")
    ticket(4, now - timedelta(days=3), technician="ANONYMOUS_302")
    ticket(5, now - timedelta(days=2))
    ticket(6, now - timedelta(days=9), now - timedelta(days=1), technician="Gorm Reventlow")  # closed


def test_open_now_by_technician(open_tickets):
    result = HelpdeskTicket.open_by_technician()
    assert result["total"] == 5
    assert result["unassigned"] == 1
    assert result["assigned"] == 4
    labels = [t["label"] for t in result["technicians"]]
    # Anonymised leavers pooled; "Ikke tildelt" last and grey.
    assert labels == ["Anonymiseret tekniker", "Peter Malmborg", "Ikke tildelt"]
    assert result["technicians"][0]["count"] == 2
    assert result["technicians"][-1]["color"] == HelpdeskTicket.NO_CATEGORY_COLOR


def test_open_at_a_past_instant_includes_tickets_closed_since(open_tickets):
    at = timezone.now() - timedelta(days=2, hours=12)
    labels = [t["label"] for t in HelpdeskTicket.open_by_technician(at)["technicians"]]
    assert "Gorm Reventlow" in labels
    assert "Ikke tildelt" not in labels  # ticket 5 not created yet


def test_empty_mirror():
    assert HelpdeskTicket.open_by_technician() == {
        "total": 0, "assigned": 0, "unassigned": 0, "technicians": [],
    }


def test_weeklog_uses_the_week_end_for_a_past_week():
    created = timezone.make_aware(datetime(2026, 3, 3, 10, 0))
    ticket(1, created, created + timedelta(days=14), technician="Peter Malmborg")
    assert WeekLog.objects.create(year=2026, week_number=10).helpdesk_open_by_technician()["total"] == 1
    assert WeekLog.objects.create(year=2026, week_number=13).helpdesk_open_by_technician()["total"] == 0


def test_dashboard_card(client, open_tickets):
    client.force_login(User.objects.create_user("u", password="x"))
    assert reverse("dashboard:partial-open-technicians") in client.get(reverse("dashboard:index")).content.decode()
    body = client.get(reverse("dashboard:partial-open-technicians")).content.decode()
    assert "Peter Malmborg" in body
    assert "open-technicians-chart" in body
    assert "1 af 5 åbne sager er ikke tildelt en tekniker" in body


def test_week_report_html_and_markdown(open_tickets):
    weeklog = WeekLog.get_or_create_current_week()
    html = generate_html(weeklog)
    assert "Åbne sager fordelt på tekniker" in html
    assert "5 åbne sager ved ugens udgang, heraf 1 ikke tildelt en tekniker" in html
    markdown = generate_markdown(weeklog)
    assert "### Åbne sager fordelt på tekniker" in markdown
    assert "| Peter Malmborg | 2 | 40% |" in markdown


def test_week_report_email_attaches_the_donut(settings, open_tickets):
    settings.CHRONICLE_EMAIL_RECIPIENTS = ["team@fynbus.dk"]
    weeklog = WeekLog.get_or_create_current_week()
    ok, message = send_weeklog_email(weeklog, format="html", from_email="gorm@fynbus.dk")
    assert ok, message
    sent = mail.outbox[0]
    assert f"cid:{TECHNICIAN_CHART_CID}" in sent.body
    content_ids = [part.get("Content-ID") for part in sent.attachments if hasattr(part, "get")]
    assert f"<{TECHNICIAN_CHART_CID}>" in content_ids
