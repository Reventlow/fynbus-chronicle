"""Course links (1.20.2): tie a course folder or item to a priority or a
case; the priority/case gets a "Kursus" pill everywhere it is listed,
including the week log exports."""

import re
import zlib

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from apps.courses.models import CourseFolder, CourseLink, CourseMaterial
from apps.cves.models import CVECase
from apps.logbook.models import PriorityItem, PriorityItemAppearance, WeekLog

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def files(settings, tmp_path):
    settings.COURSE_FILES_DIR = tmp_path / "course_files"
    settings.SITE_URL = "https://chronicle.example.test"


@pytest.fixture
def editor(client):
    user = User.objects.create_user("gre", password="x")
    client.force_login(user)
    return user


@pytest.fixture
def week():
    return WeekLog.get_or_create_current_week()


@pytest.fixture
def folder():
    return CourseFolder.objects.create(name="Anthropic")


@pytest.fixture
def video(folder):
    return CourseMaterial.objects.create(folder=folder, kind="video", title="Modul 2", file="ab/x.mp4", original_name="x.mp4")


@pytest.fixture
def item(week):
    p = PriorityItem.objects.create(origin_weeklog=week, title="Deltog i Claude Code kursus")
    PriorityItemAppearance.objects.create(priority_item=p, weeklog=week)
    return p


@pytest.fixture
def case():
    return CVECase.objects.create(kind=CVECase.Kind.TASK, title="Claude-kursus for IT")


# --- linking from the course pages -------------------------------------------------


def test_picker_lists_open_priorities_and_cases(client, editor, folder, item, case):
    html = client.get(reverse("courses:folder-link", args=[folder.slug])).content.decode()
    assert f'value="p{item.pk}"' in html and f'value="c{case.pk}"' in html and "Knyt mappen" in html


def test_link_folder_to_priority(client, editor, folder, item):
    resp = client.post(reverse("courses:folder-link", args=[folder.slug]), {"target": f"p{item.pk}"})
    link = CourseLink.objects.get()
    assert link.folder == folder and link.priority_item == item and link.created_by == editor
    assert resp["Location"] == folder.get_absolute_url()
    client.post(reverse("courses:folder-link", args=[folder.slug]), {"target": f"p{item.pk}"})
    assert CourseLink.objects.count() == 1  # idempotent


def test_link_item_to_case_goes_to_player(client, editor, video, case):
    resp = client.post(reverse("courses:material-link", args=[video.key]), {"target": f"c{case.pk}"})
    link = CourseLink.objects.get()
    assert link.material == video and link.case == case and resp["Location"].endswith(f"#m-{video.key}")
    assert link.course_url == video.get_player_url() and link.course_label == "Anthropic: Modul 2"


def test_bad_target(client, editor, folder):
    client.post(reverse("courses:folder-link", args=[folder.slug]), {"target": "x1"})
    client.post(reverse("courses:folder-link", args=[folder.slug]), {"target": "p999"})
    assert not CourseLink.objects.exists()


def test_unlink(client, editor, folder, item):
    link = CourseLink.objects.create(folder=folder, priority_item=item)
    client.post(reverse("courses:unlink", args=[link.pk]))
    assert not CourseLink.objects.exists()


def test_links_need_an_editor(client, folder, item):
    link = CourseLink.objects.create(folder=folder, priority_item=item)
    for method, url in (("get", reverse("courses:folder-link", args=[folder.slug])),
                        ("post", reverse("courses:folder-link", args=[folder.slug])),
                        ("post", reverse("courses:unlink", args=[link.pk]))):
        resp = getattr(client, method)(url)
        assert resp.status_code == 302 and "/login" in resp["Location"]
    viewer = User.objects.create_user("v", password="x")
    viewer.groups.add(Group.objects.get_or_create(name="Viewer")[0])
    client.force_login(viewer)
    assert client.post(reverse("courses:unlink", args=[link.pk])).status_code == 403
    assert CourseLink.objects.count() == 1


def test_course_page_shows_work_to_signed_in_only(client, editor, folder, video, item, case):
    CourseLink.objects.create(folder=folder, priority_item=item)
    CourseLink.objects.create(material=video, case=case)
    html = client.get(folder.get_absolute_url()).content.decode()
    assert "Prioriteret opgave: Deltog i Claude Code kursus" in html and f"Planlagt opgave #{case.pk}" in html
    assert "Knyt til opgave" in html
    client.logout()
    html = client.get(folder.get_absolute_url()).content.decode()
    assert "Deltog i Claude Code kursus" not in html and "Claude-kursus for IT" not in html


def test_links_go_with_their_ends(folder, video, item, case):
    CourseLink.objects.create(folder=folder, priority_item=item)
    CourseLink.objects.create(material=video, case=case)
    item.delete()
    video.delete()
    assert not CourseLink.objects.exists()


def test_reserved_slug(client, editor):
    client.post(reverse("courses:index"), {"name": "Knytning"})
    assert CourseFolder.objects.get().slug == "knytning-2"


# --- the pill on priorities and cases ----------------------------------------------


@pytest.mark.parametrize("page", ["week log", "priority search", "case list", "dashboard week", "dashboard cases",
                                  "priority page", "case page"])
def test_linked_work_has_a_course_pill(client, editor, folder, video, item, case, week, page):
    CourseLink.objects.create(folder=folder, priority_item=item)
    CourseLink.objects.create(material=video, case=case)
    url = {
        "week log": reverse("logbook:weeklog-detail", args=[week.year, week.week_number]),
        "priority search": reverse("logbook:priorities-search"),
        "case list": reverse("cves:case-list"),
        "dashboard week": reverse("dashboard:partial-current-week"),
        "dashboard cases": reverse("dashboard:partial-cves"),
        "priority page": reverse("logbook:priority-item-history", args=[item.pk]),
        "case page": reverse("cves:case-detail", kwargs={"pk": case.pk}),
    }[page]
    html = client.get(url).content.decode()
    assert "pill-course" in html, page
    if page in ("case list", "dashboard cases", "case page"):
        assert video.get_player_url() in html, page
    else:
        assert folder.get_absolute_url() in html, page


# --- the pill in the week log exports -----------------------------------------------


@pytest.fixture
def export_week(settings, week, folder, video, item, case):
    settings.CHRONICLE_EMAIL_RECIPIENTS = ["team@fynbus.dk"]
    case.assessment = "Plan"
    case.save()
    CourseLink.objects.create(folder=folder, priority_item=item)
    CourseLink.objects.create(material=video, case=case)
    return week


def test_export_html_has_course_pills(export_week, folder, video):
    from apps.logbook.exports.html import generate_html

    html = generate_html(export_week)
    assert f'href="https://chronicle.example.test{folder.get_absolute_url()}"' in html
    assert f'href="https://chronicle.example.test{video.get_player_url()}"' in html
    assert "Kursus: Anthropic &#8599;" in html and 'class="pill-course"' not in html  # inline styles only


def test_export_mail_has_course_pills(export_week, folder, video):
    from django.core import mail

    from apps.logbook.exports.email import send_weeklog_email

    ok, message = send_weeklog_email(export_week, format="html", from_email="gorm@fynbus.dk")
    assert ok, message
    body = mail.outbox[0].body
    assert f"https://chronicle.example.test{folder.get_absolute_url()}" in body
    assert f"https://chronicle.example.test{video.get_player_url()}" in body


def test_export_markdown_has_course_links(export_week, folder):
    from apps.logbook.exports.markdown import generate_markdown

    md = generate_markdown(export_week)
    assert f"| Deltog i Claude Code kursus [Kursus: Anthropic ↗](https://chronicle.example.test{folder.get_absolute_url()}) |" in md


def test_export_pdf_has_clickable_course_links(export_week, folder, video):
    from apps.logbook.exports.pdf import generate_pdf

    pdf = generate_pdf(export_week)
    # decompressobj, not decompress: the regex can cut a binary stream short
    # (its bytes may contain the end marker), and a partial read is enough.
    text = pdf + b"".join(zlib.decompressobj().decompress(m) for m in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S)
                          if m[:1] == b"x")
    assert folder.get_absolute_url().encode() in text and video.key.encode() in text
