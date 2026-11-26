"""Christmas theme "Jul" (forslag #21): seeded with an annual 1–26 Dec
schedule and banner messages, the scenes script on every page, and the
kalenderlys above the on-call card on the Kontrolpanel, burning down
through the day."""

import json
import re
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from apps.themes.candle import DAYS, candle_state
from apps.themes.models import Theme, ThemeSchedule
from apps.themes.templatetags.christmas import candle_caption

JS = Path(settings.BASE_DIR) / "static" / "js" / "christmas-parade.js"


@pytest.mark.django_db
class TestSeed:
    def test_seeded_selectable_with_annual_schedule(self):
        theme = Theme.objects.get(slug="christmas")
        assert theme.name == "Jul"
        assert theme.is_active and theme.user_selectable
        sched = ThemeSchedule.objects.get(theme=theme)
        assert sched.recurs_annually
        for day in (date(2026, 12, 1), date(2027, 12, 13), date(2026, 12, 24), date(2030, 12, 26)):
            assert sched.covers(day)
        for day in (date(2026, 11, 30), date(2026, 12, 27), date(2027, 1, 1)):
            assert not sched.covers(day)
        assert theme.banner_messages.count() >= 10
        assert theme.when_label == "1.–26. dec"

    def test_in_the_tweaks_panel(self, client, django_user_model):
        client.force_login(django_user_model.objects.create_user("gre", password="x"))
        html = client.get(reverse("logbook:weeklog-list")).content.decode()
        assert 'class="theme-dot" data-theme="christmas"' in html


class TestCandleState:
    """The burn computation (apps/themes/candle.py) — pure, local time in."""

    def test_new_candle_at_midnight_on_the_first(self):
        s = candle_state(datetime(2026, 12, 1, 0, 0))
        assert (s.day, s.burned, s.lit) == (1, 0.0, True)
        assert s.remaining == 1.0

    def test_melts_through_the_day(self):
        assert candle_state(datetime(2026, 12, 1, 12, 0)).burned == pytest.approx(0.5 / DAYS)
        assert candle_state(datetime(2026, 12, 13, 6, 0)).burned == pytest.approx(12.25 / DAYS)
        s = candle_state(datetime(2026, 12, 24, 18, 0))
        assert (s.day, s.lit) == (24, True)
        assert s.burned == pytest.approx(23.75 / DAYS)

    def test_continuous_and_monotonic_through_advent(self):
        moments = [datetime(2026, 12, d, h, m) for d in range(1, 25) for h in (0, 7, 15, 23) for m in (0, 59)]
        burned = [candle_state(t).burned for t in moments]
        assert burned == sorted(burned)
        # Midnight continues where the evening before left off (no jumps).
        assert candle_state(datetime(2026, 12, 6, 0, 0)).burned == pytest.approx(
            candle_state(datetime(2026, 12, 5, 23, 59, 59)).burned, abs=1e-4
        )
        assert candle_state(datetime(2026, 12, 24, 23, 59, 59)).burned == pytest.approx(1.0, abs=1e-4)

    def test_burnt_out_after_christmas_eve(self):
        for when in (datetime(2026, 12, 25, 0, 0), datetime(2026, 12, 26, 14, 30), datetime(2026, 12, 31, 23, 0)):
            s = candle_state(when)
            assert (s.day, s.burned, s.lit) == (24, 1.0, False)

    def test_outside_december_shows_the_first(self):
        """A forced preview in November (or a summer pick) shows 1 December."""
        s = candle_state(datetime(2026, 11, 26, 18, 0))
        assert (s.day, s.lit) == (1, True)
        assert s.burned == pytest.approx(0.75 / DAYS)
        assert candle_state(datetime(2027, 1, 5, 0, 0)).day == 1

    def test_caption(self):
        assert candle_caption(1, True) == "23 dage til juleaften"
        assert candle_caption(23, True) == "1 dag til juleaften"
        assert candle_caption(24, True).startswith("Juleaften")
        assert candle_caption(24, False) == "Brændt ned. Glædelig jul!"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_js_candle_matches_python():
    """static/js/christmas-parade.js's candleState mirrors candle_state()."""
    cases = [(12, 1, 0, 0, 0), (12, 1, 12, 0, 0), (12, 13, 6, 30, 15), (12, 24, 23, 59, 59),
             (12, 25, 9, 0, 0), (12, 26, 20, 0, 0), (11, 26, 18, 0, 0), (1, 5, 3, 0, 0)]
    script = (
        "const fs = require('fs'), vm = require('vm');"
        "const box = { module: { exports: {} } };"
        "vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), box);"
        "const { candleState, candleCaption } = box.module.exports;"
        "const out = JSON.parse(process.argv[2]).map(([mo, d, h, mi, s]) => {"
        "  const st = candleState(new Date(2026, mo - 1, d, h, mi, s));"
        "  return [st.day, st.burned, st.lit, candleCaption(st)]; });"
        "console.log(JSON.stringify(out));"
    )
    result = subprocess.run(["node", "-e", script, str(JS), json.dumps(cases)],
                            capture_output=True, text=True, check=True, timeout=30)
    for (mo, d, h, mi, s), (day, burned, lit, caption) in zip(cases, json.loads(result.stdout), strict=True):
        py = candle_state(datetime(2026, mo, d, h, mi, s))
        assert (day, lit) == (py.day, py.lit)
        assert burned == pytest.approx(py.burned)
        assert caption == candle_caption(py.day, py.lit)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_js_lucia_due_days():
    """luciaDueOn(): 13 December, plus the Monday after when the 13th falls on
    a weekend; never once this browser has served the guarantee that year."""
    cases = [
        # (y, m, d, servedYear, due)
        (2026, 12, 13, None, True),     # Sunday: still due on the day itself…
        (2026, 12, 14, None, True),     # …and on the Monday after
        (2026, 12, 15, None, False),
        (2025, 12, 15, None, True),     # 13th is a Saturday: Monday is the 15th
        (2025, 12, 14, None, False),
        (2027, 12, 13, None, True),     # 13th is a Monday: only that day
        (2027, 12, 14, None, False),
        (2026, 12, 5, None, False),
        (2026, 11, 13, None, False),
        (2026, 12, 14, "2026", False),  # already served this year
        (2026, 12, 14, "2025", True),   # served last year only
    ]
    script = (
        "const fs = require('fs'), vm = require('vm');"
        "const box = { module: { exports: {} } };"
        "vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), box);"
        "const { luciaDueOn } = box.module.exports;"
        "console.log(JSON.stringify(JSON.parse(process.argv[2]).map("
        "  ([y, m, d, served]) => luciaDueOn(new Date(y, m - 1, d, 10, 0), served))));"
    )
    result = subprocess.run(["node", "-e", script, str(JS), json.dumps([c[:4] for c in cases])],
                            capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(result.stdout) == [c[4] for c in cases]


# Runs christmas-parade.js against a minimal fake DOM, clock, timers and
# localStorage, then replays a scenario: ["play", "YYYY-MM-DD", scene] calls
# the public chronicleChristmas.play(); ["tick", "YYYY-MM-DD"] fires the
# scheduler's pending timer. Prints the scenes played and the storage.
LUCIA_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const steps = JSON.parse(process.argv[2]);
const store = {}, played = [], timers = [];
let now = new Date(2026, 10, 26, 10, 0).getTime();
const RealDate = Date;
class FakeDate extends RealDate {
  constructor(...a) { if (a.length) super(...a); else super(now); }
  static now() { return now; }
}
function el() {
  return { style: { setProperty() {} }, classList: { add() {}, remove() {} }, setAttribute() {},
           appendChild() {}, querySelector() { return null; }, querySelectorAll() { return []; },
           addEventListener() {}, remove() {}, insertBefore() {}, isConnected: true };
}
const body = el();
body.appendChild = (actor) => { played.push(actor.className); };
const document = {
  readyState: 'complete', hidden: false, body, createElement: el,
  documentElement: { getAttribute: () => 'christmas' },
  querySelector: () => null, querySelectorAll: () => [], addEventListener() {},
};
const window = { matchMedia: () => ({ matches: false }), location: { search: '' },
                 getComputedStyle: () => ({ position: 'static' }) };
const box = {
  window, document, Date: FakeDate, URLSearchParams,
  localStorage: { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } },
  setTimeout: (fn) => { timers.push(fn); return timers.length; }, clearTimeout() {}, setInterval() {},
};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), box);
// Run every queued timer except the scheduler's own (named `tick`).
function flush() {
  for (let i = 0; i < timers.length; i++) {
    if (timers[i] && timers[i].name !== 'tick') { const fn = timers[i]; timers[i] = null; fn(); }
  }
}
for (const [kind, day, scene] of steps) {
  const [y, m, d] = day.split('-').map(Number);
  now = new RealDate(y, m - 1, d, 10, 0).getTime();
  const before = played.length;
  if (kind === 'play') window.chronicleChristmas.play(scene);
  else {
    const i = timers.findIndex((fn) => fn && fn.name === 'tick');
    const fn = timers[i]; timers[i] = null; fn();
  }
  flush();
  steps.played = (steps.played || []).concat([played.slice(before).join(' | ')]);
}
console.log(JSON.stringify({ played: steps.played, store }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_js_lucia_preview_or_random_does_not_use_up_the_guarantee():
    """A Lucia played early (a preview in November, a random pick or the
    console hook on 5 December) leaves the guaranteed one on the due day;
    the scheduler then plays it and only that marks it as served."""
    steps = [["play", "2026-11-26", "lucia"], ["play", "2026-12-05", "lucia"], ["tick", "2026-12-14"]]
    result = subprocess.run(["node", "-e", LUCIA_HARNESS, str(JS), json.dumps(steps)],
                            capture_output=True, text=True, check=True, timeout=30)
    out = json.loads(result.stdout)
    assert all("xm-procession" in p for p in out["played"]), out
    assert out["store"] == {"chronicleLuciaServed": "2026"}


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_js_lucia_early_plays_store_nothing():
    steps = [["play", "2026-11-26", "lucia"], ["play", "2026-12-05", "lucia"]]
    result = subprocess.run(["node", "-e", LUCIA_HARNESS, str(JS), json.dumps(steps)],
                            capture_output=True, text=True, check=True, timeout=30)
    out = json.loads(result.stdout)
    assert all("xm-procession" in p for p in out["played"]), out
    assert out["store"] == {}


@pytest.mark.django_db
class TestPages:
    @pytest.fixture
    def user_client(self, client, django_user_model):
        client.force_login(django_user_model.objects.create_user("gre", password="x"))
        return client

    def test_banner_scenes_and_footer(self, user_client):
        body = user_client.get(reverse("logbook:weeklog-list") + "?force-theme=christmas").content.decode()
        assert "serverTheme: 'christmas'" in body
        assert 'class="christmas-banner"' in body and "christmas-banner-messages" in body
        assert "js/christmas-parade" in body
        assert "christmas-footer-egg" in body
        # The kalenderlys belongs to the Kontrolpanel only.
        assert "data-xc" not in body

    def test_candle_above_both_on_call_cards(self, user_client, monkeypatch):
        monkeypatch.setattr("apps.themes.templatetags.christmas._local_now",
                            lambda: datetime(2026, 12, 13, 12, 0))
        body = user_client.get(reverse("dashboard:index") + "?force-theme=christmas").content.decode()
        assert body.count("data-xc ") == 2
        # Sidebar: the candle sits right above the on-call mini card.
        assert body.index("xc-slot-sidebar") < body.index('class="sidebar-oncall"')
        # Kontrolpanel: right above the on-call card (shown on phones and
        # with the sidebar collapsed).
        dash = body.index("xc-slot-dash")
        assert dash < body.index('class="dash-oncall"')
        assert "hx-get" not in body[dash:body.index('class="dash-oncall"')]
        # 13 December at noon: 12.5 of 24 marks gone, a dot decimal for CSS.
        left = re.search(r"--xc-left: ([0-9.]+);", body).group(1)
        assert float(left) == pytest.approx(1 - 12.5 / DAYS, abs=1e-4)
        assert 'data-lit="1"' in body
        assert "<span class=\"num\" data-xc-day>13</span>. december" in body
        assert "11 dage til juleaften" in body
        assert all(f"<span>{n}</span>" in body for n in (1, 12, 24))

    def test_candle_burnt_out_on_boxing_day(self, user_client, monkeypatch):
        monkeypatch.setattr("apps.themes.templatetags.christmas._local_now",
                            lambda: datetime(2026, 12, 26, 9, 0))
        body = user_client.get(reverse("dashboard:index") + "?force-theme=christmas").content.decode()
        assert 'data-lit="0"' in body and "--xc-left: 0.0000;" in body
        assert "Brændt ned. Glædelig jul!" in body

    def test_no_candle_under_another_server_theme(self, user_client):
        body = user_client.get(reverse("dashboard:index") + "?force-theme=halloween").content.decode()
        assert "data-xc" not in body

    def test_dashboard_partials_still_render(self, user_client):
        """The HTMX-loaded on-call cards are untouched by the theme."""
        for name in ("dashboard:partial-oncall", "dashboard:partial-oncall-mini"):
            resp = user_client.get(reverse(name) + "?force-theme=christmas")
            assert resp.status_code == 200


class TestScenes:
    def test_scenes_present(self):
        js = JS.read_text()
        for skit in ("nisseCheer", "nisseGlitter", "nisseTug", "nisseHat", "snowballFight",
                     "lucia", "reindeerPeek", "risalamande", "julehjerte", "sleigh"):
            assert f"    {skit}: function" in js

    def test_gated_and_gentle(self):
        js = JS.read_text()
        assert 'getAttribute("data-event") === "christmas"' in js
        assert "prefers-reduced-motion: reduce" in js
        assert "document.hidden" in js
        css = (Path(settings.BASE_DIR) / "static" / "src" / "input.css").read_text()
        assert ".xm-actor {" in css and "pointer-events: none;" in css
        # No third-party art: every figure is inline SVG, no image files.
        assert not re.search(r"\.(png|gif|webp|jpe?g)\b", js)

    def test_sidebar_candle_never_clips_the_footer(self):
        """The 100vh, overflow-hidden sidebar: the candle slot is the item that
        gives way (min-height: 0), and when it had to, the script marks
        data-xc-cramped and the dashboard copy takes over."""
        css = (Path(settings.BASE_DIR) / "static" / "src" / "input.css").read_text()
        slot = re.search(r'html\[data-event="christmas"\] \.xc-slot-sidebar \{([^}]*)\}', css).group(1)
        assert "min-height: 0" in slot and "overflow: hidden" in slot and "flex: 0 1 auto" in slot
        assert 'html[data-event="christmas"][data-xc-cramped] .xc-slot-sidebar' in css
        assert 'html[data-event="christmas"][data-xc-cramped] .xc-slot-dash { display: block; }' in css
        js = JS.read_text()
        assert "function fitSidebarCandle()" in js and "watchSidebarCandle();" in js
        assert 'setAttribute("data-xc-cramped"' in js
