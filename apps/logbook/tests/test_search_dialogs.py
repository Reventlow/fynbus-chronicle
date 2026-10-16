"""Live filtering in the "add existing" and merge dialogs.

Filtering must swap only the result list. Swapping the whole dialog
replaces the search field mid-typing: the caret jumps to the start and
letters typed while a request is in flight are lost.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.logbook.models import PriorityItem, PriorityItemAppearance, WeekLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(client):
    client.force_login(User.objects.create_user("gre", password="x"))
    return client


@pytest.fixture
def tasks():
    old = WeekLog.objects.create(year=2026, week_number=30)
    now = WeekLog.objects.create(year=2026, week_number=31)
    items = []
    for title in ("Veeam-opsætning", "Puzzel hold"):
        item = PriorityItem.objects.create(origin_weeklog=old, title=title, priority="medium")
        PriorityItemAppearance.objects.create(priority_item=item, weeklog=old)
        items.append(item)
    return now, items


def search_input(body: str) -> str:
    return re.search(r'<input type="text" name="q"[^>]*>', body).group(0)


def test_add_existing_filter_swaps_only_the_results(editor, tasks):
    weeklog, _ = tasks
    url = reverse("logbook:weeklog-add-existing", args=[weeklog.pk])
    body = editor.get(url, {"q": "veeam"}).content.decode()
    field = search_input(body)
    assert 'hx-target="#add-existing-results"' in field
    assert 'hx-select="#add-existing-results"' in field
    results = body.split('id="add-existing-results"', 1)[1]
    assert "Veeam-opsætning" in results and "Puzzel hold" not in results
    # The search field sits outside the swapped list.
    assert 'name="q"' not in results


def test_merge_filter_swaps_only_the_results(editor, tasks):
    _, (veeam, puzzel) = tasks
    url = reverse("logbook:priority-item-merge", args=[veeam.pk])
    body = editor.get(url, {"q": "puzzel"}).content.decode()
    field = search_input(body)
    assert 'hx-target="#merge-results"' in field
    assert 'hx-select="#merge-results"' in field
    results = body.split('id="merge-results"', 1)[1]
    assert "Puzzel hold" in results
    assert 'name="q"' not in results
