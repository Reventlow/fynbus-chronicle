"""Sending a report by email goes through a confirmation page (0.15.0, FR #10).

The "Email som …" links used to send on GET — one click, no way to see who
would receive it. Now GET shows recipients, sender, subject and attachments
and sends nothing; only the page's POST sends. Covers both the weeklog and
the priority-history reports.
"""

from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from apps.logbook.exports.email import email_recipients, email_summary
from apps.logbook.models import PriorityItem, WeekLog

pytestmark = pytest.mark.django_db

RECIPIENTS = ["chef@fynbus.dk", "it-team@fynbus.dk"]


@pytest.fixture
def editor(client):
    user = User.objects.create_user("gre", password="x", email="gre@fynbus.dk")
    client.force_login(user)
    return user


@pytest.fixture
def weeklog():
    return WeekLog.objects.create(year=2026, week_number=36)


@pytest.fixture
def item(weeklog):
    return PriorityItem.objects.create(
        origin_weeklog=weeklog, title="Skift af UPS", priority="medium", status="ongoing"
    )


@pytest.fixture
def recipients(settings):
    settings.CHRONICLE_EMAIL_RECIPIENTS = RECIPIENTS
    return RECIPIENTS


def _weeklog_url(weeklog, fmt="both"):
    return reverse("logbook:export-email", kwargs={"year": weeklog.year, "week": weeklog.week_number}) + f"?format={fmt}"


def _item_url(item, fmt="both"):
    return reverse("logbook:priority-export-email", kwargs={"pk": item.pk}) + f"?format={fmt}"


# --- helpers ----------------------------------------------------------------


def test_email_recipients_trims_and_dedupes(settings):
    settings.CHRONICLE_EMAIL_RECIPIENTS = [" a@fynbus.dk", "b@fynbus.dk ", "a@fynbus.dk", ""]
    assert email_recipients() == ["a@fynbus.dk", "b@fynbus.dk"]


@pytest.mark.parametrize(
    "fmt, label, n_attachments",
    [("html", "HTML", 1), ("pdf", "PDF", 1), ("both", "HTML + PDF", 2)],
)
def test_email_summary_describes_format(recipients, fmt, label, n_attachments):
    summary = email_summary(subject="S", format=fmt, pdf_filename="r.pdf", from_email="me@fynbus.dk")
    assert summary["format_label"] == label
    assert len(summary["attachments"]) == n_attachments
    assert summary["recipients"] == RECIPIENTS
    assert summary["from_email"] == "me@fynbus.dk"


def test_email_summary_falls_back_to_default_sender(settings, recipients):
    settings.DEFAULT_FROM_EMAIL = "it@fynbus.dk"
    assert email_summary(subject="S", format="pdf", pdf_filename="r.pdf", from_email="")["from_email"] == "it@fynbus.dk"


# --- weeklog: GET confirms, POST sends ---------------------------------------


@patch("apps.logbook.views.send_weeklog_email")
def test_get_shows_recipients_and_sends_nothing(send, client, editor, weeklog, recipients):
    response = client.get(_weeklog_url(weeklog, "both"))

    assert response.status_code == 200
    html = response.content.decode()
    for addr in RECIPIENTS:
        assert addr in html
    assert "Modtagere (2)" in html
    assert "FynBus IT Ugelog - Uge 36, 2026" in html
    assert "gre@fynbus.dk" in html  # the sender
    assert "ugelog_2026_uge36.pdf" in html
    assert 'name="format" value="both"' in html
    assert "Send til 2 modtagere" in html
    send.assert_not_called()


@patch("apps.logbook.views.send_weeklog_email", return_value=(True, "Email (PDF) sendt til 2 modtager(e)."))
def test_post_sends_with_posted_format_and_redirects(send, client, editor, weeklog, recipients):
    url = reverse("logbook:export-email", kwargs={"year": 2026, "week": 36})
    response = client.post(url, {"format": "pdf"})

    assert response.status_code == 302
    assert response["Location"] == weeklog.get_absolute_url()
    send.assert_called_once_with(weeklog, format="pdf", from_email="gre@fynbus.dk")


@patch("apps.logbook.views.send_weeklog_email", return_value=(False, "Fejl ved afsendelse af email: boom"))
def test_post_failure_surfaces_as_error_message(send, client, editor, weeklog, recipients):
    url = reverse("logbook:export-email", kwargs={"year": 2026, "week": 36})
    response = client.post(url, {"format": "both"}, follow=True)
    msgs = [str(m) for m in response.context["messages"]]
    assert any("boom" in m for m in msgs)


@patch("apps.logbook.views.send_weeklog_email")
def test_invalid_format_is_a_400_not_a_send(send, client, editor, weeklog, recipients):
    assert client.get(_weeklog_url(weeklog, "docx")).status_code == 400
    assert client.post(reverse("logbook:export-email", kwargs={"year": 2026, "week": 36}), {"format": "docx"}).status_code == 400
    send.assert_not_called()


def test_no_recipients_disables_send(client, editor, weeklog, settings):
    settings.CHRONICLE_EMAIL_RECIPIENTS = []
    html = client.get(_weeklog_url(weeklog)).content.decode()
    assert "Ingen modtagere er konfigureret" in html
    assert "Modtagere (0)" in html
    assert 'disabled aria-disabled="true"' in html


def test_viewer_cannot_reach_the_confirm_page(client, weeklog, recipients):
    viewer = User.objects.create_user("viewer", password="x")
    viewer.groups.add(Group.objects.get_or_create(name="Viewer")[0])
    client.force_login(viewer)
    assert client.get(_weeklog_url(weeklog)).status_code == 403


def test_real_send_goes_to_the_listed_recipients(client, editor, weeklog, recipients, mailoutbox):
    """End to end with the locmem backend: the addresses on the page are the
    addresses on the wire."""
    client.post(reverse("logbook:export-email", kwargs={"year": 2026, "week": 36}), {"format": "pdf"})
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == RECIPIENTS
    assert mailoutbox[0].from_email == "gre@fynbus.dk"


# --- priority history: same shape --------------------------------------------


@patch("apps.logbook.exports.priority.send_priority_email")
def test_priority_get_confirms(send, client, editor, item, recipients):
    html = client.get(_item_url(item, "html")).content.decode()
    assert "FynBus IT Opgavelog — Skift af UPS" in html
    assert "Modtagere (2)" in html
    assert 'name="format" value="html"' in html
    send.assert_not_called()


def test_priority_post_sends_and_redirects(client, editor, item, recipients, mailoutbox):
    url = reverse("logbook:priority-export-email", kwargs={"pk": item.pk})
    response = client.post(url, {"format": "html"})
    assert response.status_code == 302
    assert response["Location"] == reverse("logbook:priority-item-history", kwargs={"pk": item.pk})
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == RECIPIENTS
