"""The "Planner ↗" pill on priorities and cases linked to a Planner card,
wherever they are listed."""

import pytest
from django.urls import reverse

from apps.cves.models import CVECase
from apps.logbook.models import PriorityItem, PriorityItemAppearance, WeekLog
from apps.planner.models import PlannerLink

TASK_URL = "/Home/Task/task-42"


@pytest.fixture
def linked(planner, django_user_model, client):
    client.force_login(django_user_model.objects.create_user("anna"))
    weeklog = WeekLog.get_or_create_current_week()
    item = PriorityItem.objects.create(origin_weeklog=weeklog, title="Certifikater")
    PriorityItemAppearance.objects.create(priority_item=item, weeklog=weeklog)
    case = CVECase.objects.create(kind=CVECase.Kind.TASK, title="Opgradering")
    PlannerLink.objects.create(task_id="task-42", task_title="Kort i Planner", priority_item=item)
    PlannerLink.objects.create(task_id="task-42", task_title="Kort i Planner", case=case)
    # An unlinked one of each, which gets no pill.
    other = PriorityItem.objects.create(origin_weeklog=weeklog, title="Uden link")
    PriorityItemAppearance.objects.create(priority_item=other, weeklog=weeklog)
    CVECase.objects.create(kind=CVECase.Kind.TASK, title="Uden link")
    return weeklog


def _pages(weeklog):
    return {
        "week log": reverse("logbook:weeklog-detail", args=[weeklog.year, weeklog.week_number]),
        "priority search": reverse("logbook:priorities-search"),
        "case list": reverse("cves:case-list"),
        "dashboard week": reverse("dashboard:partial-current-week"),
        "dashboard cases": reverse("dashboard:partial-cves"),
    }


@pytest.mark.django_db
@pytest.mark.parametrize("page", ["week log", "priority search", "case list", "dashboard week", "dashboard cases"])
def test_linked_items_have_a_planner_pill(client, linked, page):
    html = client.get(_pages(linked)[page]).content.decode()
    assert "pill-planner" in html and TASK_URL in html, page


@pytest.mark.django_db
def test_week_log_shows_pill_on_priority_and_case(client, linked):
    html = client.get(_pages(linked)["week log"]).content.decode()
    # one pill on the priority row, one row under the case (it is open this week)
    assert html.count(TASK_URL) == 2


@pytest.mark.django_db
def test_no_pill_when_planner_is_off(client, linked, settings):
    settings.PLANNER_ENABLED = False
    for page, url in _pages(linked).items():
        assert "pill-planner" not in client.get(url).content.decode(), page


@pytest.mark.django_db
@pytest.mark.parametrize("page", ["case list", "priority search", "dashboard cases"])
def test_lists_cost_no_query_per_linked_row(client, linked, page):
    """planner_links is prefetched: more linked rows, same number of queries."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    url = _pages(linked)[page]
    with CaptureQueriesContext(connection) as before:
        client.get(url)
    weeklog = WeekLog.objects.first()
    for i in range(4):
        case = CVECase.objects.create(kind=CVECase.Kind.TASK, title=f"Ekstra {i}")
        PlannerLink.objects.create(task_id=f"t{i}", task_title="x", case=case)
        item = PriorityItem.objects.create(origin_weeklog=weeklog, title=f"Ekstra {i}")
        PlannerLink.objects.create(task_id=f"t{i}", task_title="x", priority_item=item)
    with CaptureQueriesContext(connection) as after:
        client.get(url)
    assert len(after) == len(before), page
