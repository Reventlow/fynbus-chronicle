"""The week log reaches readers four ways: the PDF and HTML downloads
(weekly_report.html), the Markdown download (exports/markdown.py) and the
mail (email_body.html). Each carries its own markup, so a section added to
one can silently miss another, as happened with the on-call line and old
task notes in the mail and the cases in Markdown before 1.20.4. These
tests fill every section of one week and check that every fact, and the
order of the sections, is the same in all of them."""

import html as htmlmod
import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.utils import timezone

from apps.courses.models import CourseFolder, CourseLink
from apps.cves.models import CVECase, CVEComment, CVELink
from apps.logbook.exports.email import send_weeklog_email
from apps.logbook.exports.html import generate_html
from apps.logbook.exports.markdown import generate_markdown
from apps.logbook.exports.pdf import generate_pdf
from apps.logbook.models import (
    Absence,
    Incident,
    PriorityItem,
    PriorityItemAppearance,
    WeekLog,
)
from apps.oncall.models import OnCallDuty
from apps.planner.models import PlannerLink
from apps.servicedesk.models import TicketLink

pytestmark = pytest.mark.django_db

# label -> text that must appear in every output
FACTS = {
    "periode": "Uge 45",
    "rådighedsvagt": "Vagt Person",
    "nye sager": "Nye sager",
    "lukkede sager": "Lukkede sager",
    "åbne sager": "Åbne sager",
    "netto": "Netto ændring",
    "ugeoversigt": "UGEOVERSIGT-TEKST",
    "deltagere": "DELTAGER-A",
    "referat": "REFERAT-TEKST",
    "opgave": "OPGAVE-TITEL",
    "ugens beskrivelse": "UGE-BESKRIVELSE",
    "gamle noter": "GAMMEL-NOTE",
    "planner-pille": "Planner",
    "servicedesk-pille": "ServiceDesk #4711",
    "kursus-pille": "KURSUS-MAPPE",
    "fravær": "FRAVÆR-NAVN",
    "fravær-note": "FRAVÆR-NOTE",
    "hændelse": "HÆNDELSE-TITEL",
    "hændelse-beskrivelse": "HÆNDELSE-BESKRIVELSE",
    "hændelse-tidspunkt": "03/11/2026",
    "hændelse-løsning": "HÆNDELSE-LØSNING",
    "sag": "SAG-TITEL",
    "sag-reference": "SAG-REF-1",
    "sag-vurdering": "SAG-VURDERING",
    "sag-løsning": "SAG-HANDLING",
    "sag-kommentar": "SAG-KOMMENTAR",
    "sag-link": "SAG-LINKTEKST",
    "sag-servicedesk": "ServiceDesk #4712",
}
SECTIONS = ["Helpdesk Statistik", "Ugeoversigt", "Sårbarheder og hændelser", "Referat af mandags møde",
            "Prioriterede Opgaver", "Bemanding", "Hændelser"]


def at(y, m, d, h=12):
    return timezone.make_aware(datetime(y, m, d, h))


def text_of(markup: str) -> str:
    markup = re.sub(r"<(style|head)[^>]*>.*?</\1>", " ", markup, flags=re.S)
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", markup)))


def html_sections(markup: str) -> list[str]:
    return [text_of(h).strip() for h in re.findall(r"<h2[^>]*>(.*?)</h2>", markup, re.S)]


@pytest.fixture
def week(settings):
    settings.PLANNER_ENABLED = True
    settings.CHRONICLE_EMAIL_RECIPIENTS = ["it@example.test"]
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.SERVICEDESK_URL = "https://servicedesk.example.test"
    user = User.objects.create_user("gre", first_name="Vagt", last_name="Person")
    wl = WeekLog.objects.create(
        year=2026, week_number=45, helpdesk_new=17, helpdesk_closed=13, helpdesk_open=88,
        summary="UGEOVERSIGT-TEKST", meeting_attendees="DELTAGER-A", meeting_minutes="REFERAT-TEKST",
    )
    OnCallDuty.objects.create(year=2026, week_number=45, user=user)
    item = PriorityItem.objects.create(origin_weeklog=wl, title="OPGAVE-TITEL", priority="high",
                                       status="ongoing", notes="GAMMEL-NOTE")
    PriorityItemAppearance.objects.create(priority_item=item, weeklog=wl, description="UGE-BESKRIVELSE")
    PlannerLink.objects.create(task_id="t1", task_title="Kort", priority_item=item)
    TicketLink.objects.create(sdp_id=4711, subject="Emne", priority_item=item)
    CourseLink.objects.create(folder=CourseFolder.objects.create(name="KURSUS-MAPPE"), priority_item=item)
    Absence.objects.create(weeklog=wl, staff_name="FRAVÆR-NAVN", absence_type="vacation",
                           start_date=date(2026, 11, 2), end_date=date(2026, 11, 4), notes="FRAVÆR-NOTE")
    Incident.objects.create(weeklog=wl, title="HÆNDELSE-TITEL", incident_type="outage", severity="high",
                            description="HÆNDELSE-BESKRIVELSE", resolution="HÆNDELSE-LØSNING",
                            occurred_at=at(2026, 11, 3))
    case = CVECase.objects.create(title="SAG-TITEL", reference="SAG-REF-1", created_at=at(2026, 11, 2),
                                  created_by=user, assessment="SAG-VURDERING", solution="SAG-HANDLING",
                                  export_comments=True, export_links=True)
    comment = CVEComment.objects.create(case=case, text="SAG-KOMMENTAR", author=user)
    CVEComment.objects.filter(pk=comment.pk).update(created_at=at(2026, 11, 3))
    CVELink.objects.create(case=case, url="https://example.test/advisory", label="SAG-LINKTEKST")
    TicketLink.objects.create(sdp_id=4712, subject="Emne", case=case)
    return wl


def mail_body(wl) -> str:
    ok, msg = send_weeklog_email(wl, format="html")
    assert ok, msg
    return mail.outbox[-1].body


def missing(text: str) -> list[str]:
    return [label for label, needle in FACTS.items() if needle not in text]


def test_html_download_has_everything(week):
    assert missing(text_of(generate_html(week))) == []


def test_mail_has_everything(week):
    assert missing(text_of(mail_body(week))) == []


def test_markdown_has_everything(week):
    assert missing(generate_markdown(week)) == []


@pytest.mark.skipif(not shutil.which("pdftotext"), reason="pdftotext (poppler) not installed")
def test_pdf_has_everything(week):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(generate_pdf(week))
        f.flush()
        text = subprocess.run(["pdftotext", f.name, "-"], capture_output=True, text=True, check=True).stdout
    assert missing(re.sub(r"\s+", " ", text)) == []


def test_sections_in_the_same_order(week):
    download = [h for h in html_sections(generate_html(week)) if h in SECTIONS]
    in_mail = [h for h in html_sections(mail_body(week)) if h in SECTIONS]
    markdown = [h for h in re.findall(r"^## (.+)$", generate_markdown(week), re.M) if h in SECTIONS]
    assert download == SECTIONS
    assert in_mail == download
    assert markdown == download


def test_markdown_keeps_hidden_cases_out(week):
    CVECase.objects.create(title="INTERN-SAG", created_at=at(2026, 11, 2), export_assessment=False,
                           export_solution=False, export_comments=False, export_links=False,
                           export_attachments=False)
    md = generate_markdown(week)
    assert "INTERN-SAG" not in md
    assert "| Sårbarheder | 2 | 0 |" in md  # the counts still cover it, as in the PDF chart
