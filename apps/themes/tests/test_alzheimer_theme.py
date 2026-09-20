"""World Alzheimer's Day theme — 21 September, every year.

The theme is seeded by migration 0009; these tests read what the seed
produced rather than creating their own rows, so they also catch a seed
that silently stopped running.
"""

from datetime import date
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.urls import reverse

from apps.themes.models import Theme, ThemeBannerMessage, ThemeSchedule

pytestmark = pytest.mark.django_db

SLUG = "alzheimer"


@pytest.fixture
def theme():
    return Theme.objects.get(slug=SLUG)


@pytest.fixture
def editor(client):
    user = User.objects.create_user("gre", password="x")
    client.force_login(user)
    return user


class TestSeed:
    def test_theme_exists_and_is_selectable(self, theme):
        assert theme.is_active is True
        assert theme.user_selectable is True
        assert theme.name == "Alzheimerdag"

    def test_scheduled_for_21_september_every_year(self, theme):
        schedule = ThemeSchedule.objects.get(theme=theme)

        assert (schedule.start_date.month, schedule.start_date.day) == (9, 21)
        assert schedule.start_date == schedule.end_date
        assert schedule.recurs_annually is True

    def test_has_banner_messages(self, theme):
        messages = ThemeBannerMessage.objects.filter(theme=theme, is_active=True)

        assert messages.count() >= 8

    def test_messages_point_somewhere_useful(self, theme):
        """The copy is information, not quips — a helpline and a site."""
        texts = " ".join(
            ThemeBannerMessage.objects.filter(theme=theme).values_list("text", flat=True)
        )

        assert "58 50 58 50" in texts  # Demenslinien
        assert "alzheimer.dk" in texts


class TestActivation:
    @pytest.mark.parametrize("year", [2026, 2027, 2031])
    def test_active_on_the_day_in_any_year(self, theme, year):
        with patch("apps.themes.models.timezone.localdate", return_value=date(year, 9, 21)):
            assert Theme.scheduled_for_today() == theme

    @pytest.mark.parametrize("day", [date(2026, 9, 20), date(2026, 9, 22)])
    def test_not_active_the_day_before_or_after(self, theme, day):
        with patch("apps.themes.models.timezone.localdate", return_value=day):
            assert Theme.scheduled_for_today() != theme

    def test_does_not_collide_with_pirate_day(self):
        """19 September is Pirate Day; the two days must stay separate."""
        with patch("apps.themes.models.timezone.localdate", return_value=date(2026, 9, 19)):
            active = Theme.scheduled_for_today()

        assert active is None or active.slug != SLUG


class TestRendering:
    def test_banner_renders_with_messages(self, theme):
        html = render_to_string("components/alzheimer_banner.html")

        assert 'class="alzheimer-banner"' in html
        assert "Verdens Alzheimerdag" in html
        assert "Demenslinien" in html

    def test_page_activates_it_via_force_theme(self, client, editor):
        response = client.get(reverse("dashboard:index"), {"force-theme": SLUG})
        html = response.content.decode()

        assert response.status_code == 200
        assert f"serverTheme: '{SLUG}'" in html
        assert "FORGLEM MIG EJ" in html

    def test_no_themed_greeting_or_phrase_swaps(self, client, editor):
        """This theme stays out of the wording; only the look changes."""
        html = client.get(reverse("dashboard:index"), {"force-theme": SLUG}).content.decode()

        # The greeting map has no entry for this theme, so it falls back
        # to the plain Danish greeting rather than an in-character one.
        assert "theme === 'alzheimer'" not in html

    def test_stylesheet_knows_the_theme(self):
        from django.conf import settings

        css = (settings.BASE_DIR / "static" / "css" / "output.css").read_text()

        assert 'data-event=alzheimer' in css or 'data-event="alzheimer"' in css
        assert ".alzheimer-banner" in css
