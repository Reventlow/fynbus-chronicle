"""Halloween theme (1.13.0): seeded with an annual 24 Oct – 1 Nov schedule,
banner messages, and the parade script on every page."""

from datetime import date

import pytest
from django.urls import reverse

from apps.themes.models import Theme, ThemeSchedule


@pytest.mark.django_db
class TestHalloween:
    def test_seeded_with_annual_schedule(self):
        theme = Theme.objects.get(slug="halloween")
        assert theme.is_active and theme.user_selectable
        sched = ThemeSchedule.objects.get(theme=theme)
        assert sched.recurs_annually
        for day in (date(2027, 10, 24), date(2026, 10, 31), date(2030, 11, 1)):
            assert sched.covers(day)
        assert not sched.covers(date(2026, 11, 2)) and not sched.covers(date(2026, 10, 23))
        assert theme.banner_messages.count() >= 10

    def test_banner_and_parade_on_the_page(self, client, django_user_model):
        user = django_user_model.objects.create_user("gre", password="x")
        client.force_login(user)
        body = client.get(reverse("dashboard:index") + "?force-theme=halloween").content.decode()
        assert "serverTheme: 'halloween'" in body
        assert 'class="halloween-banner"' in body and "halloween-banner-messages" in body
        assert "js/halloween-parade" in body
        assert "halloween-footer-egg" in body

    def test_parade_has_the_monsters(self):
        """1.14.0: zombies, a vampire, a werewolf and spiders joined the parade."""
        from pathlib import Path
        from django.conf import settings
        js = (Path(settings.BASE_DIR) / "static" / "js" / "halloween-parade.js").read_text()
        for skit in ("zombieShuffle", "zombieProcess", "vampire", "werewolf", "spiderDrop", "spiderTrio",
                     "skeletonHead", "ghostWifi", "pumpkinRoll", "bats"):
            assert f"    {skit}: function" in js
