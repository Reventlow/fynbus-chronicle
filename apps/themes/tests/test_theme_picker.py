"""The theme picker in the tweaks panel: one row per selectable theme with
its accent dot, date hint and a check on the selected row (0.14.1).

Before this the picker was a wrapping row of pills; five names of very
different lengths broke onto three ragged lines in the 280 px panel.
"""

from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.themes.models import Theme, ThemeSchedule

pytestmark = pytest.mark.django_db


@pytest.fixture
def client_logged_in() -> Client:
    user = User.objects.create_user("picker", password="x")
    client = Client()
    client.force_login(user)
    return client


def _theme(slug: str, name: str, **sched) -> Theme:
    theme = Theme.objects.create(slug=slug, name=name, is_active=True, user_selectable=True)
    if sched:
        ThemeSchedule.objects.create(theme=theme, **sched)
    return theme


def test_when_label_single_day_annual():
    theme = _theme("t1", "T1", start_date=date(2026, 9, 21), end_date=date(2026, 9, 21), recurs_annually=True)
    assert theme.when_label == "21. sep"


def test_when_label_range_same_month():
    theme = _theme("t2", "T2", start_date=date(2026, 9, 19), end_date=date(2026, 9, 21), recurs_annually=True)
    assert theme.when_label == "19.–21. sep"


def test_when_label_range_across_year():
    theme = _theme("t3", "T3", start_date=date(2026, 12, 27), end_date=date(2027, 1, 3), recurs_annually=True)
    assert theme.when_label == "27. dec – 3. jan"


def test_when_label_prefers_annual_over_one_shot():
    theme = _theme("t4", "T4", start_date=date(2026, 3, 1), end_date=date(2026, 3, 2), recurs_annually=False)
    ThemeSchedule.objects.create(
        theme=theme, start_date=date(2026, 5, 4), end_date=date(2026, 5, 4), recurs_annually=True
    )
    assert theme.when_label == "4. maj"


def test_when_label_empty_without_schedule():
    assert _theme("t5", "T5").when_label == ""


def test_panel_renders_rows_with_dot_date_and_check(client_logged_in):
    # Star Wars Day is seeded by migration 0002 with its annual 4 May schedule.
    assert Theme.objects.filter(slug="star-wars", schedules__recurs_annually=True).exists()
    html = client_logged_in.get(reverse("logbook:weeklog-list")).content.decode()
    assert 'class="theme-list" role="radiogroup"' in html
    assert 'class="theme-dot" data-theme="star-wars"' in html
    assert '<span class="theme-row-when">4. maj</span>' in html
    assert "theme-row-check" in html
    # The Auto row leads the list and explains itself.
    assert 'class="theme-row-when">følger kalenderen' in html
    # The old wrapping pill row is gone.
    assert 'class="flex flex-wrap gap-2"' not in html


def test_panel_omits_date_hint_without_schedule(client_logged_in):
    _theme("plain", "Plain")
    html = client_logged_in.get(reverse("logbook:weeklog-list")).content.decode()
    assert 'data-theme="plain"' in html
    assert '<span class="theme-row-name">Plain</span>\n' in html
    # No empty date span for a theme without a schedule: Auto plus one per scheduled theme.
    scheduled = Theme.objects.filter(is_active=True, user_selectable=True, schedules__isnull=False).distinct().count()
    assert html.count('class="theme-row-when"') == 1 + scheduled


def test_panel_query_count_is_flat(client_logged_in, django_assert_max_num_queries):
    for i in range(4):
        _theme(f"q{i}", f"Q{i}", start_date=date(2026, 1, i + 1), end_date=date(2026, 1, i + 1), recurs_annually=True)
    url = reverse("logbook:weeklog-list")
    # Warm-up to settle session/auth queries, then assert schedules are prefetched (no N+1).
    client_logged_in.get(url)
    with django_assert_max_num_queries(30):
        client_logged_in.get(url)
