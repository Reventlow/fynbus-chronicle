"""Touch-Grass-Weekend banner (0.19.0): a green banner every Saturday and
Sunday telling people to log off. Weekday-driven like Read-only Friday, so it
is a context processor; ?force-weekend=1/0 previews it."""

from datetime import date
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.urls import reverse

from chronicle.context_processors import touch_grass_weekend

pytestmark = pytest.mark.django_db

FRIDAY = date(2026, 10, 2)
SATURDAY = date(2026, 10, 3)
SUNDAY = date(2026, 10, 4)


@pytest.fixture
def editor(client):
    user = User.objects.create_user("gre", password="x")
    client.force_login(user)
    return user


def _ctx(day, query=""):
    request = RequestFactory().get("/" + ("?" + query if query else ""))
    with patch("chronicle.context_processors.django_timezone.localdate", return_value=day):
        return touch_grass_weekend(request)["IS_TOUCH_GRASS_WEEKEND"]


@pytest.mark.parametrize("day", [SATURDAY, SUNDAY])
def test_true_on_the_weekend(day):
    assert _ctx(day) is True


@pytest.mark.parametrize("day", [date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1), FRIDAY])
def test_false_on_weekdays(day):
    assert _ctx(day) is False


def test_force_on_and_off():
    assert _ctx(FRIDAY, "force-weekend=1") is True
    assert _ctx(SATURDAY, "force-weekend=0") is False
    assert _ctx(SATURDAY, "force-weekend=maybe") is True  # garbage is ignored


def test_banner_renders_on_the_weekend(client, editor):
    with patch("chronicle.context_processors.django_timezone.localdate", return_value=SUNDAY):
        html = client.get(reverse("logbook:weeklog-list")).content.decode()
    assert 'class="tgw-banner"' in html
    assert "Touch-Grass-Weekend" in html
    assert 'class="tgw-grass"' in html
    assert 'data-tgw="1"' in html
    # Never on the same day as Read-only Friday.
    assert "rof-banner" not in html


def test_banner_absent_on_friday(client, editor):
    with patch("chronicle.context_processors.django_timezone.localdate", return_value=FRIDAY):
        html = client.get(reverse("logbook:weeklog-list")).content.decode()
    assert "tgw-banner" not in html
    assert "data-tgw" not in html
    assert 'class="rof-banner"' in html


def test_styling_is_compiled():
    css = open("static/css/output.css", encoding="utf-8").read()
    assert ".tgw-banner" in css and ".tgw-grass" in css
    assert "html[data-tgw] .brand-mark" in css


def test_banner_survives_an_active_theme(client, editor):
    """The weekend banner and a day-theme banner coexist."""
    with patch("chronicle.context_processors.django_timezone.localdate", return_value=SATURDAY):
        response = client.get(reverse("logbook:weeklog-list"), {"force-theme": "pirate"})
    html = response.content.decode()
    assert 'class="tgw-banner"' in html
    assert 'class="pirate-banner"' in html
