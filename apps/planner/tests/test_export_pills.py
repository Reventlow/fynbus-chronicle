"""The Planner pill in the week log exports (HTML/PDF, mail body, Markdown)."""

import pytest
from django.core import mail

from apps.cves.models import CVECase
from apps.logbook.exports.email import send_weeklog_email
from apps.logbook.exports.html import generate_html
from apps.logbook.exports.markdown import generate_markdown
from apps.logbook.models import PriorityItem, PriorityItemAppearance, WeekLog
from apps.planner.models import PlannerLink

ITEM_URL = "/Home/Task/task-item"
CASE_URL = "/Home/Task/task-case"


@pytest.fixture
def week(planner, settings):
    settings.CHRONICLE_EMAIL_RECIPIENTS = ["team@fynbus.dk"]
    weeklog = WeekLog.get_or_create_current_week()
    item = PriorityItem.objects.create(origin_weeklog=weeklog, title="Certifikater")
    PriorityItemAppearance.objects.create(priority_item=item, weeklog=weeklog)
    plain = PriorityItem.objects.create(origin_weeklog=weeklog, title="Uden link")
    PriorityItemAppearance.objects.create(priority_item=plain, weeklog=weeklog)
    case = CVECase.objects.create(kind=CVECase.Kind.TASK, title="Opgradering", assessment="Plan")
    PlannerLink.objects.create(task_id="task-item", task_title="Kort A", priority_item=item)
    PlannerLink.objects.create(task_id="task-case", task_title="Kort B", case=case)
    return weeklog


@pytest.mark.django_db
def test_html_and_pdf_export(week):
    """The PDF is rendered from the same HTML template."""
    html = generate_html(week)
    assert html.count(ITEM_URL) == 1 and html.count(CASE_URL) == 1
    assert "Planner &#8599;" in html and 'class="pill-planner"' not in html  # inline styles only


@pytest.mark.django_db
def test_mail_body(week):
    ok, message = send_weeklog_email(week, format="html", from_email="gorm@fynbus.dk")
    assert ok, message
    body = mail.outbox[0].body
    assert ITEM_URL in body and CASE_URL in body


@pytest.mark.django_db
def test_markdown_export(week):
    md = generate_markdown(week)
    assert "| Certifikater [Planner ↗](https://tasks.office.com/" in md and ITEM_URL in md
    assert "| Uden link |" in md


@pytest.mark.django_db
def test_no_pill_when_planner_is_off(week, settings):
    settings.PLANNER_ENABLED = False
    assert "/Home/Task/" not in generate_html(week)
    assert "/Home/Task/" not in generate_markdown(week)


@pytest.mark.django_db
def test_pdf_has_clickable_planner_links(week):
    import re
    import zlib

    from apps.logbook.exports.pdf import generate_pdf

    pdf = generate_pdf(week)
    # WeasyPrint compresses objects; the link annotations sit in those streams.
    text = pdf + b"".join(zlib.decompressobj().decompress(m) for m in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S)
                          if m[:1] == b"x")
    assert pdf.startswith(b"%PDF") and b"Home/Task/task-item" in text and b"Home/Task/task-case" in text
