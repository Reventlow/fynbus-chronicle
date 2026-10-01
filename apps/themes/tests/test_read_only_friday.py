"""Read-only Friday banner (0.16.0): a red banner every Friday saying no
changes go to production today. Weekday-driven, so it is a context
processor rather than a ThemeSchedule row; ?force-friday=1/0 previews it.
"""

from datetime import date
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.urls import reverse

from chronicle.context_processors import read_only_friday

pytestmark = pytest.mark.django_db

FRIDAY = date(2026, 10, 2)
THURSDAY = date(2026, 10, 1)


@pytest.fixture
def editor(client):
    user = User.objects.create_user("gre", password="x")
    client.force_login(user)
    return user


def _ctx(day, query=""):
    request = RequestFactory().get("/" + ("?" + query if query else ""))
    with patch("chronicle.context_processors.django_timezone.localdate", return_value=day):
        return read_only_friday(request)["IS_READ_ONLY_FRIDAY"]


def test_true_on_a_friday():
    assert _ctx(FRIDAY) is True


@pytest.mark.parametrize("day", [date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30), THURSDAY, date(2026, 10, 3), date(2026, 10, 4)])
def test_false_on_every_other_weekday(day):
    assert _ctx(day) is False


def test_force_on_and_off():
    assert _ctx(THURSDAY, "force-friday=1") is True
    assert _ctx(FRIDAY, "force-friday=0") is False
    assert _ctx(FRIDAY, "force-friday=maybe") is True  # garbage is ignored


def test_banner_renders_on_friday(client, editor):
    with patch("chronicle.context_processors.django_timezone.localdate", return_value=FRIDAY):
        html = client.get(reverse("logbook:weeklog-list")).content.decode()
    assert 'class="rof-banner"' in html
    assert "Read-only Friday" in html
    assert "Ingen ændringer i produktion i dag" in html
    # 0.16.2: the html element carries the hook for the viewport frame + red brand mark.
    assert '<html lang="da" data-rof="1"' in html


def test_banner_absent_on_thursday(client, editor):
    with patch("chronicle.context_processors.django_timezone.localdate", return_value=THURSDAY):
        html = client.get(reverse("logbook:weeklog-list")).content.decode()
    assert "rof-banner" not in html
    assert "data-rof" not in html


def test_loud_styling_is_compiled():
    css = open("static/css/output.css", encoding="utf-8").read()
    assert "html[data-rof] body::after" in css or "html[data-rof] body:after" in css
    assert "html[data-rof] .brand-mark" in css


def test_banner_survives_an_active_theme(client, editor):
    """The rule banner and a day-theme banner coexist — e.g. Pirate Day on a Friday."""
    with patch("chronicle.context_processors.django_timezone.localdate", return_value=FRIDAY):
        response = client.get(reverse("logbook:weeklog-list"), {"force-theme": "pirate"})
    html = response.content.decode()
    assert 'class="rof-banner"' in html
    # data-event is bound by Alpine at runtime; the server-side signal is the context.
    assert response.context["ACTIVE_THEME"] == "pirate"
    assert 'class="pirate-banner"' in html
