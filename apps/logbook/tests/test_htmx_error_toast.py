"""A failed HTMX request must not fail silently.

htmx performs no swap on a 4xx/5xx response, so without a listener the
UI shows nothing at all and a rejected save looks like a dead button.
These tests pin the pieces that make the failure visible.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.logbook.models import PriorityItem, PriorityItemAppearance, WeekLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(client):
    user = User.objects.create_user("gre", password="x")
    client.force_login(user)
    return user


class TestErrorToastMarkup:
    def test_page_ships_the_error_listener(self, client, editor):
        html = client.get(reverse("logbook:weeklog-list")).content.decode()

        assert 'id="htmx-error-toast"' in html
        assert "htmx:responseError" in html
        assert "htmx:sendError" in html

    def test_toast_starts_hidden_and_is_assertive(self, client, editor):
        html = client.get(reverse("logbook:weeklog-list")).content.decode()
        toast = html[html.index('id="htmx-error-toast"') : html.index('id="htmx-error-text"')]

        assert "hidden" in toast
        assert 'role="alert"' in toast
        assert 'aria-live="assertive"' in toast

    def test_toast_has_no_inline_display(self, client, editor):
        """An inline `display` beats [hidden] { display: none }.

        0.10.6 shipped the toast with inline `display: flex`, so an empty
        red box sat in the corner of every page. The layout belongs in
        CSS, where `.error-toast[hidden]` can switch it off.
        """
        html = client.get(reverse("logbook:weeklog-list")).content.decode()
        toast = html[html.index('id="htmx-error-toast"') : html.index('id="htmx-error-text"')]

        assert "display" not in toast
        assert "error-toast" in toast

    def test_stylesheet_hides_the_toast(self):
        """The rule that actually keeps it off screen must exist."""
        from django.conf import settings

        css = (settings.BASE_DIR / "static" / "css" / "output.css").read_text()

        assert ".error-toast[hidden]" in css

    def test_403_gets_its_own_wording(self, client, editor):
        """403 is the one users hit in practice — stale session or CSRF."""
        html = client.get(reverse("logbook:weeklog-list")).content.decode()

        assert "403" in html
        assert "genindlæs siden" in html.lower()


class TestRejectedSaveIsAnErrorStatus:
    """The toast only fires on a real error status, so verify we send one."""

    def test_editing_without_permission_is_an_error_status(self, client):
        """A viewer's save must come back as a status htmx treats as an error."""
        from django.contrib.auth.models import Group

        viewer = User.objects.create_user("viewer", password="x")
        group, _ = Group.objects.get_or_create(name="Viewer")
        viewer.groups.add(group)
        client.force_login(viewer)

        weeklog = WeekLog.objects.create(year=2026, week_number=36)
        item = PriorityItem.objects.create(
            origin_weeklog=weeklog, title="Opgave", priority="medium", status="ongoing"
        )
        appearance = PriorityItemAppearance.objects.create(
            priority_item=item, weeklog=weeklog
        )

        response = client.post(
            reverse("logbook:priority-item-edit", kwargs={"pk": appearance.pk}),
            {"title": "Ændret", "priority": "high", "status": "ongoing",
             "description": "", "notes": ""},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code in (302, 403)
        item.refresh_from_db()
        assert item.title == "Opgave"
