"""Recording that a week log was sent (FR #19).

A successful email send, in any format and from any send path (the
confirmation page, the admin action), stores ``emailed_at`` / ``emailed_by``.
A report mailed outside Chronicle can be recorded with the editor-only
"Markér som sendt" action. The week log page shows the result.
"""

from datetime import date
from unittest.mock import patch

import pytest
from django.contrib.admin.sites import site as admin_site
from django.contrib.auth.models import Group, User
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.logbook.exports.email import send_weeklog_email
from apps.logbook.models import WeekLog

pytestmark = pytest.mark.django_db

RECIPIENTS = ["chef@fynbus.dk"]


@pytest.fixture
def recipients(settings):
    settings.CHRONICLE_EMAIL_RECIPIENTS = RECIPIENTS
    return RECIPIENTS


@pytest.fixture
def weeklog():
    return WeekLog.objects.create(year=2026, week_number=47)


@pytest.fixture
def anna():
    return User.objects.create_user("anna", password="x", first_name="Anna", last_name="Andersen", email="anna@fynbus.dk")


@pytest.fixture
def viewer():
    user = User.objects.create_user("viewer", password="x")
    user.groups.add(Group.objects.get_or_create(name="Viewer")[0])
    return user


def mark_url(weeklog):
    return reverse("logbook:weeklog-mark-emailed", kwargs={"year": weeklog.year, "week": weeklog.week_number})


# --- model ------------------------------------------------------------------


@pytest.mark.parametrize(
    "today, expected",
    [
        (date(2026, 11, 26), (2026, 47)),  # an ordinary Thursday in week 48
        (date(2026, 1, 1), (2025, 52)),    # week 1 of 2026 -> last week of 2025
        (date(2021, 1, 4), (2020, 53)),    # a 53-week year
    ],
)
def test_previous_iso_week_crosses_the_year_boundary(today, expected):
    assert WeekLog.previous_iso_week(today) == expected


def test_mark_emailed_leaves_updated_at_alone(weeklog, anna):
    before = WeekLog.objects.get(pk=weeklog.pk).updated_at
    weeklog.mark_emailed(anna)
    weeklog.refresh_from_db()
    assert weeklog.is_emailed
    assert weeklog.emailed_by == anna
    assert weeklog.updated_at == before


def test_new_week_logs_start_unsent(weeklog):
    assert weeklog.emailed_at is None
    assert weeklog.emailed_by is None
    assert not weeklog.is_emailed


# --- the send itself ---------------------------------------------------------


@pytest.mark.parametrize("fmt", ["html", "pdf", "both"])
def test_successful_send_records_who_and_when(weeklog, anna, recipients, mailoutbox, fmt):
    before = timezone.now()
    with patch("apps.logbook.exports.email.generate_pdf", return_value=b"%PDF-1.4"):
        ok, _message = send_weeklog_email(weeklog, format=fmt, from_email=anna.email, sent_by=anna)
    assert ok
    assert len(mailoutbox) == 1
    weeklog.refresh_from_db()
    assert weeklog.emailed_at >= before
    assert weeklog.emailed_by == anna


def test_failed_send_records_nothing(weeklog, anna, recipients):
    with patch("django.core.mail.EmailMessage.send", side_effect=OSError("smtp nede")):
        ok, message = send_weeklog_email(weeklog, format="html", sent_by=anna)
    assert not ok
    assert "smtp nede" in message
    weeklog.refresh_from_db()
    assert weeklog.emailed_at is None


def test_no_recipients_records_nothing(weeklog, anna, settings):
    settings.CHRONICLE_EMAIL_RECIPIENTS = []
    ok, _message = send_weeklog_email(weeklog, format="html", sent_by=anna)
    assert not ok
    weeklog.refresh_from_db()
    assert weeklog.emailed_at is None


def test_confirm_page_post_records_the_sender(client, weeklog, anna, recipients, mailoutbox):
    client.force_login(anna)
    url = reverse("logbook:export-email", kwargs={"year": 2026, "week": 47})
    client.post(url, {"format": "html"})
    weeklog.refresh_from_db()
    assert weeklog.emailed_by == anna
    assert weeklog.emailed_at is not None


def test_admin_action_records_the_sender(weeklog, anna, recipients, mailoutbox):
    anna.is_staff = True
    anna.save()
    request = RequestFactory().post("/admin/")
    request.user = anna
    model_admin = admin_site._registry[WeekLog]
    with patch.object(model_admin, "message_user"), patch(
        "apps.logbook.exports.email.generate_pdf", return_value=b"%PDF-1.4"
    ):
        model_admin.send_email(request, WeekLog.objects.filter(pk=weeklog.pk))
    weeklog.refresh_from_db()
    assert weeklog.emailed_by == anna


# --- "Markér som sendt" --------------------------------------------------------


def test_editor_can_mark_as_sent(client, weeklog, anna):
    client.force_login(anna)
    response = client.post(mark_url(weeklog))
    assert response.status_code == 302
    assert response["Location"] == weeklog.get_absolute_url()
    weeklog.refresh_from_db()
    assert weeklog.emailed_by == anna
    assert weeklog.emailed_at is not None


def test_mark_redirects_to_a_local_next(client, weeklog, anna):
    client.force_login(anna)
    response = client.post(mark_url(weeklog), {"next": reverse("dashboard:index")})
    assert response["Location"] == reverse("dashboard:index")


def test_mark_ignores_an_offsite_next(client, weeklog, anna):
    client.force_login(anna)
    response = client.post(mark_url(weeklog), {"next": "https://evil.example/"})
    assert response["Location"] == weeklog.get_absolute_url()


def test_mark_does_not_overwrite_a_real_send(client, weeklog, anna):
    bo = User.objects.create_user("bo", password="x")
    weeklog.mark_emailed(bo)
    sent_at = WeekLog.objects.get(pk=weeklog.pk).emailed_at
    client.force_login(anna)
    client.post(mark_url(weeklog))
    weeklog.refresh_from_db()
    assert weeklog.emailed_by == bo
    assert weeklog.emailed_at == sent_at


def test_viewer_cannot_mark(client, weeklog, viewer):
    client.force_login(viewer)
    assert client.post(mark_url(weeklog)).status_code == 403
    weeklog.refresh_from_db()
    assert weeklog.emailed_at is None


def test_anonymous_is_sent_to_login(client, weeklog):
    response = client.post(mark_url(weeklog))
    assert response.status_code == 302
    assert "login" in response["Location"]
    weeklog.refresh_from_db()
    assert weeklog.emailed_at is None


def test_mark_needs_post(client, weeklog, anna):
    client.force_login(anna)
    assert client.get(mark_url(weeklog)).status_code == 405


def test_mark_unknown_week_is_404(client, anna):
    client.force_login(anna)
    url = reverse("logbook:weeklog-mark-emailed", kwargs={"year": 2026, "week": 12})
    assert client.post(url).status_code == 404


def test_mark_requires_csrf(weeklog, anna):
    from django.test import Client

    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(anna)
    assert csrf_client.post(mark_url(weeklog)).status_code == 403
    weeklog.refresh_from_db()
    assert weeklog.emailed_at is None


# --- the week log page --------------------------------------------------------


def test_detail_shows_who_sent_it_and_when(client, weeklog, anna):
    weeklog.mark_emailed(anna)
    weeklog.refresh_from_db()
    local = timezone.localtime(weeklog.emailed_at)
    client.force_login(anna)
    html = client.get(weeklog.get_absolute_url()).content.decode()
    assert f"kl. {local:%H:%M} af Anna Andersen" in html
    assert "Ikke sendt" not in html
    assert "Markér som sendt" not in html


def test_detail_unsent_offers_the_mark_button_to_editors(client, weeklog, anna):
    client.force_login(anna)
    html = client.get(weeklog.get_absolute_url()).content.decode()
    assert "Ikke sendt" in html
    assert "Markér som sendt" in html
    assert mark_url(weeklog) in html


def test_detail_unsent_has_no_mark_button_for_viewers(client, weeklog, viewer):
    client.force_login(viewer)
    html = client.get(weeklog.get_absolute_url()).content.decode()
    assert "Ikke sendt" in html
    assert "Markér som sendt" not in html


def test_create_form_takes_year_and_week_from_the_query(client, anna):
    client.force_login(anna)
    response = client.get(reverse("logbook:weeklog-create") + "?year=2025&week=52")
    form = response.context["form"]
    assert form["year"].value() == 2025
    assert form["week_number"].value() == 52
