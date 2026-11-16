"""Personal Kontrolpanel (1.21.0, forslag #17): each user orders the
sections and hides sections or single cards; the choice is theirs alone,
survives sections added later, and hidden cards are not rendered (so their
partials are never polled)."""

import re

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from apps.dashboard.layout import (
    DEFAULT_ORDER,
    build_layout,
    clean,
    empty_in,
    layout_for,
)
from apps.dashboard.models import DashboardLayout

pytestmark = pytest.mark.django_db

INDEX = reverse("dashboard:index")
SAVE = reverse("dashboard:layout")
PARTIALS = {
    "kpi": "dashboard:partial-helpdesk-stats",
    "now.cases": "dashboard:partial-cves",
    "now.week": "dashboard:partial-current-week",
    "open.breakdown": "dashboard:partial-open-breakdown",
    "open.lists": "dashboard:partial-open-ticket-lists",
    "trend.flow": "dashboard:partial-helpdesk-flow-chart",
    "trend.open_chart": "dashboard:partial-helpdesk-chart",
    "changelog": "dashboard:partial-latest-change",
}


@pytest.fixture
def user(client):
    u = User.objects.create_user("gre", password="x")
    client.force_login(u)
    return u


def page(client) -> str:
    resp = client.get(INDEX)
    assert resp.status_code == 200
    return resp.content.decode()


def polled(html: str) -> set[str]:
    return {key for key, name in PARTIALS.items() if f'hx-get="{reverse(name)}"' in html}


class TestBuildLayout:
    def test_default_is_every_section_in_order_and_numbered(self):
        layout = build_layout()
        assert [s.key for s in layout] == DEFAULT_ORDER == ["kpi", "now", "open", "trend", "changelog"]
        assert not any(s.hidden for s in layout)
        assert [s.n for s in layout] == ["", "01", "02", "03", ""]

    def test_clean_drops_unknown_and_duplicate_keys_and_appends_missing_sections(self):
        order, hidden = clean(["trend", "bogus", "trend", "kpi"], ["now.cases", "nope", "open.x", 5])
        assert order == ["trend", "kpi", "now", "open", "changelog"]
        assert hidden == ["now.cases"]

    def test_clean_survives_garbage(self):
        assert clean("kpi", {"a": 1}) == (DEFAULT_ORDER, [])

    def test_numbers_follow_the_visible_order(self):
        layout = build_layout(["trend", "open", "now", "kpi", "changelog"], ["open"])
        assert [(s.key, s.n) for s in layout if not s.hidden] == [("trend", "01"), ("now", "02"), ("kpi", ""), ("changelog", "")]

    def test_section_with_every_card_hidden_counts_as_hidden(self):
        trend = {s.key: s for s in build_layout(None, ["trend.flow", "trend.open_chart"])}["trend"]
        assert trend.hidden and not trend.key_hidden

    def test_layout_for_reads_the_saved_layout(self, user):
        DashboardLayout.objects.create(user=user, order=["changelog"], hidden=["kpi"])
        layout = layout_for(user)
        assert layout[0].key == "changelog"
        assert {s.key: s.hidden for s in layout}["kpi"]


class TestPage:
    def test_default_page_polls_every_card_and_has_the_dialog(self, client, user):
        html = page(client)
        assert polled(html) == set(PARTIALS)
        assert "Tilpas kontrolpanel" in html and 'id="dashboard-layout-data"' in html

    def test_hidden_cards_and_sections_are_not_rendered(self, client, user):
        DashboardLayout.objects.create(user=user, order=DEFAULT_ORDER, hidden=["kpi", "now.cases", "trend"])
        assert polled(page(client)) == {"now.week", "open.breakdown", "open.lists", "changelog"}

    def test_one_card_left_in_nu_gets_the_full_width(self, client, user):
        DashboardLayout.objects.create(user=user, hidden=["now.week"])
        assert 'class="now-grid is-single"' in page(client)

    def test_sections_render_in_the_saved_order(self, client, user):
        DashboardLayout.objects.create(user=user, order=["trend", "now", "kpi", "open", "changelog"])
        html = page(client)
        positions = [html.index(f'hx-get="{reverse(PARTIALS[k])}"') for k in ("trend.flow", "now.cases", "kpi", "open.lists")]
        assert positions == sorted(positions)
        assert html.index(">01<") < html.index("Udvikling") < html.index(">02<")

    def test_everything_hidden_offers_the_way_back(self, client, user):
        DashboardLayout.objects.create(user=user, hidden=list(DEFAULT_ORDER))
        html = page(client)
        assert polled(html) == set() and "dash-empty dash-empty-all" in html

    def test_hint_when_the_density_hides_what_is_left(self):
        assert empty_in(build_layout(None, ["kpi", "open", "trend"])) == ["dashboard"]  # now + changelog left
        assert empty_in(build_layout(None, ["kpi", "now"])) == ["compact"]  # open, trend, changelog left
        assert empty_in(build_layout()) == []

    def test_retry_sync_still_has_its_target_with_the_kpis_hidden(self, client, user):
        # The headline's "Prøv igen" posts into #helpdesk-stats-container;
        # htmx refuses to send at all when the target is missing.
        DashboardLayout.objects.create(user=user, hidden=["kpi"])
        html = page(client)
        assert 'id="helpdesk-stats-container" hidden' in html and "kpi" not in polled(html)

    def test_dialog_starts_from_the_saved_layout(self, client, user):
        DashboardLayout.objects.create(user=user, order=["trend"], hidden=["trend.flow", "trend.open_chart", "kpi"])
        rows = client.get(INDEX).context["layout_editor"]
        assert [r["key"] for r in rows][0] == "trend"
        trend, kpi = rows[0], next(r for r in rows if r["key"] == "kpi")
        # every card off, but the section box itself stays ticked
        assert trend["hidden"] is False and [p["shown"] for p in trend["parts"]] == [False, False]
        assert kpi["hidden"] is True

    def test_enter_in_the_dialog_saves_rather_than_resets(self, client, user):
        # Enter submits the first of the form's own submit buttons, so the
        # layout form must not own a reset: "Nulstil" belongs to its own form.
        html = page(client)
        form = re.search(r'<form method="post" action="[^"]*/kontrolpanel/layout/" class="card".*?</form>', html, re.S).group(0)
        own_submits = [b for b in re.findall(r"<button[^>]*>", form) if 'type="submit"' in b and "form=" not in b]
        assert own_submits and not any("reset" in b for b in own_submits)
        reset = re.search(r'<form id="dashboard-layout-reset".*?</form>', html, re.S).group(0)
        assert 'name="reset"' in reset and "csrfmiddlewaretoken" in reset

    def test_layouts_are_per_user(self, client, user):
        other = User.objects.create_user("abc")
        DashboardLayout.objects.create(user=other, hidden=["kpi", "now", "open", "trend"])
        assert polled(page(client)) == set(PARTIALS)


class TestSave:
    def test_save_cleans_and_stores(self, client, user):
        resp = client.post(SAVE, {"order": ["open", "kpi", "evil"], "hidden": ["trend.flow", "<script>"]})
        assert resp.status_code == 302 and resp["Location"] == INDEX
        saved = DashboardLayout.objects.get(user=user)
        assert saved.order == ["open", "kpi", "now", "trend", "changelog"] and saved.hidden == ["trend.flow"]

    def test_save_again_updates_the_same_row(self, client, user):
        client.post(SAVE, {"order": DEFAULT_ORDER, "hidden": ["kpi"]})
        client.post(SAVE, {"order": DEFAULT_ORDER})
        assert DashboardLayout.objects.get(user=user).hidden == []

    def test_reset_returns_to_the_standard_layout(self, client, user):
        DashboardLayout.objects.create(user=user, hidden=["kpi"])
        client.post(SAVE, {"reset": "1", "order": DEFAULT_ORDER, "hidden": ["kpi"]})
        assert not DashboardLayout.objects.exists()

    def test_viewers_may_arrange_their_own_page(self, client, user):
        user.groups.add(Group.objects.get_or_create(name="Viewer")[0])
        client.post(SAVE, {"order": DEFAULT_ORDER, "hidden": ["changelog"]})
        assert DashboardLayout.objects.get(user=user).hidden == ["changelog"]

    def test_get_is_refused_and_anonymous_is_sent_to_login(self, client, user):
        assert client.get(SAVE).status_code == 405
        client.logout()
        resp = client.post(SAVE, {"hidden": ["kpi"]})
        assert resp.status_code == 302 and "/login" in resp["Location"]
        assert not DashboardLayout.objects.exists()
