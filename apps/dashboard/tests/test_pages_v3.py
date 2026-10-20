"""v3 design on the remaining pages: toolbar breadcrumbs, list rows, no
old sand-* classes, status as dot + text."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.logbook.models import Incident, PriorityItem, PriorityItemAppearance, WeekLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(client):
    client.force_login(User.objects.create_user("gre", password="x"))
    return client


@pytest.mark.parametrize("name, args", [
    ("logbook:weeklog-list", []),
    ("oncall:calendar", []),
    ("dashboard:docs-index", []),
    ("dashboard:docs-page", ["user-guide"]),
    ("feedback:board", []),
    ("reports:list", []),
    ("logbook:priorities-search", []),
    ("logbook:weeklog-create", []),
    ("accounts:api-keys", []),
])
def test_page_uses_the_v3_shell_without_old_classes(editor, name, args):
    body = editor.get(reverse(name, args=args)).content.decode()
    assert 'class="toolbar"' in body
    assert "sand-" not in body
    # Breadcrumbs live in the toolbar, never as an in-page row.
    assert 'color: var(--ink-5);">/</span>' not in body


def test_weeklog_list_rows_count_tasks_and_incidents(editor):
    week = WeekLog.objects.create(year=2026, week_number=40, summary="En travl uge.")
    item = PriorityItem.objects.create(origin_weeklog=week, title="A", priority="medium")
    PriorityItemAppearance.objects.create(priority_item=item, weeklog=week)
    from django.utils import timezone
    Incident.objects.create(weeklog=week, title="H", occurred_at=timezone.now())
    body = editor.get(reverse("logbook:weeklog-list")).content.decode()
    assert 'class="list-row"' in body
    assert "1 opgave" in body and "1 hændelse" in body
    assert "En travl uge." in body


def test_oncall_week_cards_keep_their_actions(editor):
    body = editor.get(reverse("oncall:calendar")).content.decode()
    assert "oncall-card" in body
    assert "Tag vagt" in body and "Ledig" in body


def test_solved_feedback_is_faded_not_struck(editor):
    from apps.feedback.models import FeatureRequest

    fr = FeatureRequest.objects.create(title="Løst forslag", description="x")
    FeatureRequest.objects.filter(pk=fr.pk).update(status="solved")
    body = editor.get(reverse("feedback:detail", args=[fr.pk])).content.decode()
    assert "line-through" not in body
    assert 'class="task-status"' in body


def test_user_guide_contents_links_resolve(editor):
    """Heading anchors keep Danish letters, so every contents link works."""
    import re

    body = editor.get(reverse("dashboard:docs-page", args=["user-guide"])).content.decode()
    ids = set(re.findall(r'id="([^"]+)"', body))
    links = set(re.findall(r'href="#([^"]+)"', body))
    assert "opgavesøgning" in ids and "api-nøgler" in ids
    assert links - ids == set()


def test_links_between_docs_open_the_docs_pages():
    from apps.dashboard.views import link_docs

    html = ('<a href="DEPLOYMENT.md#rolling-back">a</a> <a href="../CHANGELOG.md">b</a> '
            '<a href="https://example.com/x.md">c</a> <a href="#local">d</a>')
    out = link_docs(html)
    assert reverse("dashboard:docs-page", args=["deployment"]) + "#rolling-back" in out
    assert reverse("dashboard:docs-page", args=["changelog"]) in out
    assert 'href="https://example.com/x.md"' in out and 'href="#local"' in out


def test_development_guide_links_resolve_in_app(editor):
    body = editor.get(reverse("dashboard:docs-page", args=["development"])).content.decode()
    assert 'href="DEPLOYMENT.md' not in body
    assert reverse("dashboard:docs-page", args=["deployment"]) in body
