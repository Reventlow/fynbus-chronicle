# Changelog

All notable changes to FynBus Chronicle are documented here.

## 0.5.6 — 2026-05-07

### Changed
- Footer now uses the editorial design tokens (paper / hairline / ink scale) instead of the legacy sand palette, and picks up the user's accent: a 64×2 px rule sits over the top border in `--accent`, and the version number renders as a small `--accent-soft / --accent-ink` pill (matching the "Se historik" pill on priority rows). Switching the tweaks-panel accent now retints the footer immediately. Admin link stays as a plain text link in `--ink-3 → --ink-1` on hover.

### Removed
- "Sidste 7 dage" subheading from the dashboard incidents card — it wasn't accurate (the list is the most recent N incidents regardless of age) and the eyebrow alone is enough.

## 0.5.5 — 2026-05-07

### Changed
- Closed → open merges are now allowed. The merge rule loosened from "both must be active" to "winner must be active" — folding a closed task into an open one is supported as a way to revive prematurely-closed work without manually reopening it first. Open → closed and closed → closed still refuse with a clear error. The merge button now appears on every priority row in the search page (open or closed); the dialog header notes when the loser is closed.

## 0.5.4 — 2026-05-07

### Added
- Merge action available from the search page too. Each open task now shows a small merge icon-button in its row (next to the priority/status pills). Click → same modal as on the weeklog detail (pick a winner, confirm). Closed tasks don't show the button — only open tasks can be merged.

## 0.5.3 — 2026-05-07

### Added
- **Merge two open priority tasks.** A new icon-button on every active priority row opens a dialog listing all *other* active tasks (filterable). Pick one and confirm — the loser's appearances move to the winner (descriptions concatenated with a `— flettet —` separator on same-week conflicts), the loser's notes append to the winner under a `— flettet fra: <title> —` header, the winner's `origin_weeklog` shifts to the earlier of the two so the history page starts from the real beginning, and the loser is deleted. Winner keeps its title, priority, status, and the current week's row as-is.
- New endpoint: `POST /api/v1/priority-items/{loser_id}/merge-into/{winner_id}/` (write scope) for MCP and scripted merges.
- New `PriorityItem.merge_into(winner)` method enforces both tasks must be active and refuses self-merge.

## 0.5.2 — 2026-05-07

### Added
- "Se historik" pill next to the task title in every priority row that has appeared on more than one weeklog. Links straight to the history page; uses the accent palette so it picks up the user's tweak. Tasks that only exist on their origin week (i.e. no real history yet) still don't show the pill.

## 0.5.1 — 2026-05-07

### Fixed
- Multi-line `{# … #}` comment at the top of `priority_item_row.html` was leaking onto the weeklog detail page once for every priority appearance. Switched to `{% comment %} … {% endcomment %}`. (This is the *fifth* time this exact bug has surfaced in this codebase — already saved as a memory note, will keep watching.)

## 0.5.0 — 2026-05-07

### Added
- **Multi-week priority tasks.** Schema split into long-lived `PriorityItem` (title, priority, status, notes, origin_weeklog, last_active_at, auto_closed) plus a new `PriorityItemAppearance` row per (task, week) carrying the per-week **description** + display order. Each week's description is preserved separately so a task accumulates a true history. Existing items are backfilled: every old `PriorityItem.description` is moved to an appearance for that item's origin week.
- **Manual carry-over** via a "Fra åbne" dialog on each weeklog's priority section. The dialog lists every active task that isn't already on this week (filterable by text), and the user picks any number to bring forward. No automatic carry-over — staying in control was the point.
- **Auto-close after 6 weeks of silence.** When a current weeklog is opened, items whose `last_active_at` is older than `PriorityItem.AUTO_CLOSE_AFTER_WEEKS` (=6 weeks) are auto-closed (`status=completed, auto_closed=True`). Touching an item (status, fields, or a description edit on any of its appearances) bumps `last_active_at` and resets the clock.
- **Reopen → auto-add to current week.** Toggling a completed task back to `ongoing` (via UI or API PATCH) automatically creates an appearance on the current ISO week and resets the auto-close clock.
- **Search page** at `/logbook/priorities/search/` (linked from each weeklog's priority section as "Søg") with text + status + year filters across all tasks, open or closed.
- **History page** at `/logbook/priorities/{id}/history/` showing every weekly appearance of one task with its description — one-click from the row title.

### Changed
- Priority row URLs (`priority-item-edit/delete/row/reorder`) now key on `PriorityItemAppearance.pk` (the row in the weeklog UI) instead of `PriorityItem.pk`. Editing updates the long-lived task's title/priority/status/notes plus the current row's description; deleting only removes the row from the week (the task lives on).
- Dashboard's current-week card now lists priority appearances (with per-week description) instead of bare priority items.
- API: `weeklog.priority_items` now returns appearances with nested `priority_item` plus per-week `description`. New endpoints: `GET /api/v1/priority-items/{id}/history/` and `POST /api/v1/weeklogs/{year}/{week}/priority-items/carry/`. Reopening via PATCH automatically adds the task to the current week.
- Admin: `PriorityItem` admin shows `last_active_at`, `auto_closed`, and the appearance count. New `PriorityItemAppearance` admin for spot-checking history. The weeklog inline shows appearances now (not raw items).

## 0.4.0 — 2026-05-01

### Added
- **API keys + JSON API.** Per-user API keys with two scopes (`read`, `write`). New `apps.accounts.APIKey` model stores SHA-256 hashes only — raw keys (`fbc_R_…` / `fbc_W_…`) are shown exactly once at creation/reroll, then never again. Bearer-token auth via the new `@api_auth(scope=...)` decorator (`apps/accounts/api_auth.py`).
- **`apps.api`** — new app at `/api/v1/` with read endpoints (`weeklogs/`, `weeklogs/current/`, `weeklogs/{year}/{week}/`, `incidents/`, `oncall/current/`, `helpdesk/data/`, `changelog/latest/`) and write endpoints (`weeklogs/{year}/{week}/priority-items/`, `priority-items/{id}/`, `weeklogs/{year}/{week}/incidents/`).
- **Self-service UI** at `/accounts/api-keys/` (linked from the user dropdown) — list, generate, reroll, revoke. New keys show in a one-time copy-to-clipboard reveal.
- **Admin** registration of `APIKey` with scope/last-used columns, bulk-revoke action, and read-only hash. Adding via admin is disabled — must be minted through the self-service page or the new `manage.py mint_api_key <username> --scope=read --label=...` command.

## 0.3.4 — 2026-05-01

### Added
- New "Saber" accent in the tweaks panel — saturated lightsaber red, derived from the May 4th Sith dark-mode skin so it's available year-round. Light mode picks `oklch(0.55 0.18 25)`, dark mode keeps the brighter Sith `oklch(0.62 0.20 25)`. Sits as the fourth pill in the accent picker after Guld / Sage / Blæk.

## 0.3.3 — 2026-05-01

### Fixed
- Star Wars banner was leaking Alpine code as visible text under the nav. The 106-message JSON sat inside `x-data="..."`, and the first straight `"` character in any message terminated the HTML attribute early, dumping the rest of the Alpine initialiser into the document body. Moved the messages into a `<script type="application/json" id="sw-banner-messages">` tag and have Alpine read them via `JSON.parse(...textContent)` on init — quotes are no longer in attribute scope, so the leak is gone.

## 0.3.2 — 2026-05-01

### Added
- Rotating banner messages on Star Wars Day. The "4. maj" strip now picks from 106 FynBus × Star Wars one-liners and cycles every 2 minutes ("Servere på Alderaan offline", "Wookieer anmoder om fuld adgang til Docunote", "Passagerer på Tatooine-ruten siger det er for støvet", "FynBus kom kun på andenpladsen i Boonta Eve Podrace", "Greedo skød først — pull request afvist", …). Initial message is random so reloads feel fresh; messages crossfade with a 220 ms opacity transition. List lives in `apps/dashboard/templatetags/star_wars.py` (`SW_BANNER_MESSAGES`) — easy to extend for next year.

## 0.3.1 — 2026-05-01

### Added
- Star Wars Day phrase swaps. New `{% sw_phrase %}` template tag (`apps/dashboard/templatetags/star_wars.py`) renders three nested spans (default/rebel/sith); CSS shows the right one based on `data-event` + `.dark`. Wired into the dashboard's chart titles + eyebrows, the four KPI eyebrows, the on-call card, the current-week card's section eyebrows, the incidents card, and the live/synkroniseret line.
  - Light/Rebel examples: "Lukkede sager → Fuldførte missioner", "Hændelser → Indsatser", "Rådighedsvagt → Jedi på vagt", "Live → Holocron"
  - Dark/Sith examples: "Lukkede sager → Rebel agents fanget", "Netto → Imperial kontrol", "Hændelser → Sith-aktioner", "Rådighedsvagt → Inkvisitor på vagt", "Aktive opgaver → Imperial direktiver"

## 0.3.0 — 2026-05-01

### Added
- May 4th Star Wars Day skin. On 2026-05-04 (Europe/Copenhagen), the dashboard layers a one-day theme over the editorial design system: Rebel-orange accent in light mode, Sith-red accent in dark mode, a thin sticky banner ("⚔ 4. maj · Må Kraften være med dig.") under the nav, a faint starfield behind the page, a brand-mark glyph swap (✦ Rebel / ⌖ Imperial), and a small mono Easter egg in the footer. Implemented as a single `IS_STAR_WARS_DAY` context processor that flips `data-event="star-wars"` on `<html>`; the skin reuses the existing accent token plumbing so pills, focus rings, the on-call avatar, and the open-tickets chart line all retint automatically.
- Preview hatch: `?force-star-wars=1` on any URL turns the skin on for the current request, useful for screenshots and pre-flight checks. The skin disappears on its own at midnight on May 5th — no cleanup PR needed.

## 0.2.22 — 2026-05-01

### Fixed
- Density segmented control's "Dashboard" button overflowed past the tweaks dropdown: flex items don't shrink below their content min-width by default, so the longest label dictated the button size. Added `min-width: 0`, `white-space: nowrap`, and `text-align: center` to `.segmented-btn` so `flex-1` distributes equal widths regardless of label, and bumped the dropdown from 240 px to 280 px to give the three-mode control room to breathe.

## 0.2.21 — 2026-05-01

### Changed
- Dashboard density mode now puts the two charts side-by-side. Wrapped the flow row + tasks row in a new `.js-dashboard-main` container that flips to a 2-column grid only when `data-density="dashboard"` (passthrough flex column otherwise, so Komfort/Kompakt are unchanged). The flow chart sits left, the open-tickets chart sits right; below 1024 px width the layout falls back to a single column.

## 0.2.20 — 2026-05-01

### Changed
- Kompakt density mode now hides the "Seneste ændring" changelog card too (previously only Dashboard mode hid it). The card carries a new `js-dashboard-changelog` hook so it's distinct from the incidents card, which still shows in Kompakt.
- Kompakt mode also collapses both two-column grid rows to a single column (matching what Dashboard mode already does). The rail and the incidents card now span full width instead of sitting next to an empty column where the chart used to live, so incidents lands visually higher up the page.

## 0.2.19 — 2026-05-01

### Fixed
- Three multi-line `{# … #}` comments (one in `nav.html`'s tweaks dropdown, two in `dashboard/index.html`) leaked onto the rendered page as visible text — Django's `{# … #}` syntax is single-line only. Switched to `{% comment %} … {% endcomment %}` for all three. The "Three modes: …" block above the density segmented control and the row-level hook documentation in the dashboard are no longer visible.

## 0.2.18 — 2026-05-01

### Changed
- Density toggle in the tweaks panel is now a 3-mode segmented control: **Komfort** (default, all sections visible), **Kompakt** (denser spacing tokens *and* both chart cards hidden), and **Dashboard** (only the editorial header, KPI strip, and chart cards — side rail, changelog, and incidents are hidden).
- Dashboard sections carry stable hook classes (`js-dashboard-graphs`, `js-dashboard-rail`, `js-dashboard-extras`, plus row-level `js-dashboard-flow-row` / `js-dashboard-tasks-row`) so each density mode hides the right pieces purely via CSS — no template branching, no HTMX refetches, instant toggle.
- Density state migration: any legacy `localStorage.density` value other than the three known modes is coerced back to `comfortable` on load, and the `<html>` `data-density` binding now generalises to all three values.

## 0.2.17 — 2026-05-01

### Fixed
- Open-tickets chart line was rendering near-navy in dark mode (and similarly miscoloured in light mode for any non-default accent). Newer Chromium preserves the authored `oklch()` form when serialising `getComputedStyle().color`, and my probe was running a generic digit-extraction regex over the result — so for `oklch(0.80 0.11 80)` it picked up `H=80` as `B=80` and produced rgb(0,0,80). Replace the regex with an explicit OKLCH → sRGB converter that handles `rgb()`, `oklch()`, and `#rrggbb` outputs cleanly. Same fix applied to the flow chart's "Nye sager" area-fill probe.

## 0.2.16 — 2026-05-01

### Fixed
- Charts didn't actually retint when changing the accent in the tweaks panel. The accent buttons live inside a nested Alpine `x-data` scope so the html-level `$watch('accent', ...)` was unreliable. Each accent button (and the dark-mode toggle) now explicitly fires the `accent-change` CustomEvent on `window` after a `$nextTick`, so the chart listeners receive it regardless of whether the parent watcher picked up the inner-scope write.

## 0.2.15 — 2026-05-01

### Changed
- Flow chart's "Nye sager" area fill now tracks the tweaks-panel accent (the wash under the curve subtly retints with gold/sage/terracotta/ink). Line colours remain `--chart-info` blue and `--chart-good` dashed-sage so the two series stay distinct — only the gradient fill picks up `--accent`. Hooked into the existing `accent-change` event so the tint updates instantly.

## 0.2.14 — 2026-05-01

### Changed
- Broaden the reach of the tweaks-panel accent presets so changing gold → sage → terracotta → ink visibly retints the page. Three targeted moves per the UI-expert review (full Option 2 + bounded Option 1):
  - Editorial header eyebrow now leads with a 24×2 px accent rule
  - KPI netto card's neutral "·0" pill swaps to `--accent-soft / --accent-ink` (▲/▼ states stay green/red so the sign semantic is preserved)
  - "Åbne sager — udvikling" chart (single series) now probes `--accent` for its line + gradient + point colours; multi-series flow chart keeps its independent `--chart-info / --chart-good` palette so legibility holds
- Wire an `accent-change` custom event from the root `<html>` Alpine watcher (fires on accent or dark-mode change) so the open-tickets chart re-tints instantly without waiting for the 60 s HTMX refresh

## 0.2.13 — 2026-05-01

### Added
- 12U / 26U / 12M segmented control on the "Åbne sager — udvikling" chart, mirroring the flow chart. Selection persists in `localStorage` (key: `openChartWindow`) and survives the 60 s HTMX refresh; the eyebrow ("Helpdesk · 12 uger") and the Laveste / Nuværende / Højeste stats below the chart all update to reflect the current window.

## 0.2.12 — 2026-05-01

### Fixed
- "+ Ny ugelog" button on `/logbook/` (and other legacy templates) was rendering as a tall narrow box with the icon stacked above the text. The standalone `.btn-primary`, `.btn-ghost`, and `.btn-danger` classes weren't inheriting the `inline-flex` layout from `.btn` the way `.btn-secondary` and `.btn-outline` already did. They now `@apply btn` so any legacy template using only the modifier class (e.g. `class="btn-primary"`) renders correctly.
- Eyebrow above the helpdesk flow chart was hardcoded to `Helpdesk · 12 uger` even when 26U or 12M was selected. Lifted the segmented-control's Alpine state to the chart card and bound the eyebrow's window label to it; it now reads `12 uger`, `26 uger`, or `12 måneder` according to the active selection.

## 0.2.11 — 2026-05-01

### Added
- 12U / 26U / 12M segmented control on the helpdesk flow chart now actually changes the visible window (last 12 / 26 / 52 weeks). Selection persists in `localStorage` and survives the chart's 60-second HTMX refresh — the active partial subscribes via a `flow-chart-window` custom event so the chart updates in place instead of re-fetching.

## 0.2.10 — 2026-05-01

### Removed
- "Rådighedsvagt: {name}" segment from the dashboard editorial header sub-line. The on-call name already appears in the dedicated card on the right rail, so the duplication was redundant. Also drops the now-unused `oncall` lookup from `DashboardView` — the on-call card pulls its own data via the partial view.

## 0.2.9 — 2026-04-30

### Changed
- "Aktive opgaver" now sits at the bottom of the current-week card, after Bemanding, instead of just below the summary
- "Aktive opgaver" lists every priority item regardless of status (was filtered to `ongoing`/`blocked` only). Completed items render struck-through with reduced opacity and a green status pill so they read as "done" context rather than active work; raised the cap from 5 to 8 rows.

## 0.2.8 — 2026-04-30

### Changed
- Re-balance the dashboard main row from `1.7fr / 1fr` to `1.25fr / 1fr`. The Rådighedsvagt + Aktuel ugelog rail was much narrower than the helpdesk flow chart, which had room to spare; the rail cards now have noticeably more breathing room while the chart still gets the wider half.

## 0.2.7 — 2026-04-30

### Added
- "Tilføj" link in the "Aktive opgaver" section of the dashboard's current-week card. Clicking it routes to the weeklog detail page anchored on `#priority-items-list` so the user lands directly on the priorities section to add a new one. The button only appears for editors.
- App version (`v0.2.7`) appended to the dashboard editorial header eyebrow next to the date, so it's always visible at a glance.

### Changed
- "Aktive opgaver" section now always renders on the current-week card (with an "Ingen aktive opgaver." placeholder when empty), so the "Tilføj" button is reachable even when there are no priorities yet.

## 0.2.6 — 2026-04-30

### Added
- "Seneste ændring" card on the dashboard pulls the most recent CHANGELOG.md entry and renders it under the helpdesk chart, so the previously empty space below "Åbne sager — udvikling" now shows what shipped most recently. Includes a "Se alle" link to the full changelog.

## 0.2.5 — 2026-04-30

### Removed
- "Opgave Tidslinje" Gantt-style card pulled from the bottom of the dashboard. The `dashboard:task-timeline-partial` endpoint and its API still exist for any external use, but it no longer renders on the kontrolpanel.

## 0.2.4 — 2026-04-30

### Removed
- "Opgaver" entry pulled from the top nav and mobile menu. The `/tasks/` URLs and views remain reachable directly; only the navigation surface is gone.

## 0.2.3 — 2026-04-30

### Fixed
- Helpdesk flow chart was rendering as black + dark-red lines instead of blue + sage. cssnano minifies `rgb(r, g, b)` declarations to `#rrggbb` during the Tailwind build, so the JS `rgbVar` helper that was looking only for decimal digits fell through to its `[0,0,0]` fallback. Updated to accept both `rgb()` and `#rrggbb` forms.
- Multi-line `{# … #}` comment at the top of `helpdesk_flow_chart.html` was leaking onto the page as visible text — Django comments are single-line only. Switched to `{% comment %} … {% endcomment %}`.

## 0.2.2 — 2026-04-30

### Fixed
- Helpdesk flow chart's "Nye" and "Lukket" series rendered as nearly identical blue lines because the editorial `--good` token has very low chroma (0.06), so converted to RGB it sat next to `--info`. Charts now use a separate higher-chroma palette (`--chart-info`, `--chart-good`, `--chart-accent` defined in light/dark variants) and "Lukkede sager" gets a dashed line so the two series stay distinct even side-by-side. Legend swatches updated to match.
- Chart tooltips were rendering as Chart.js's default near-black box because the `display:none` color probe sometimes returned an empty string and `rgba()` fell back to `rgba(0,0,0,1)`. Tooltip surface, ink, border, and grid colors are now picked from explicit per-mode palettes — no probe needed — so contrast is reliable in both light and dark mode.

## 0.2.1 — 2026-04-30

### Removed
- Drop the non-functional "Søg ⌘K" search affordance from the top nav. It was a visual element from the design handoff with no backend behind it; pruned until a real search lands.

## 0.2.0 — 2026-04-30

Editorial redesign milestone. Rolls up every change from the 0.1.61 → 0.1.64 series — new OKLCH design tokens, Inter Tight + Instrument Serif + JetBrains Mono fonts, sticky blurred nav with brand mark and tweaks panel, editorial dashboard and weeklog headers, restyled rows and pills, density/accent toggles, retuned dark mode, and Chart.js color compatibility fixes — under a single minor version bump to mark the new design system as the baseline.

## 0.1.64 — 2026-04-30

### Fixed
- Dashboard header sub-line was showing the "Alle løst" pill from the incidents card instead of the intended "N hændelser denne uge" + on-call name; the broken `hx-select` indirection has been removed and `incident_count_week` + `oncall` are now rendered server-side from `DashboardView` context
- Stop the helpdesk-chart card from stretching to the height of the (much taller) incidents card by adding `items-start` to their grid row

## 0.1.63 — 2026-04-30

### Fixed
- Helpdesk and flow charts now render again. Edge's CanvasGradient color-stop parser doesn't accept `oklch(L C H / a)` either (after the previous fix removed the invalid `oklch(...)22` hex-alpha concatenation), so all chart colors are now probed through a hidden `<span>` to resolve them to RGB before being passed to `addColorStop` / borderColor / tooltip styles. This works in every browser that supports `getComputedStyle`.

### Changed
- Greeting in the dashboard editorial header now picks `Godmorgen` / `Goddag` / `Godaften` / `Godnat` from the local clock instead of being hardcoded to "Godmorgen".

### Removed
- Drop the leaky `\\U\\g\\e` escape pattern from the dashboard eyebrow `{% now %}` tag — Django template literals don't honor Python-style escaping, so the literal "Uge" now lives outside the format string.

## 0.1.62 — 2026-04-30

### Changed
- Lighten dark-mode surface lightness so the new editorial palette is more comfortable: `--paper` 0.16 → 0.225, `--surface-1` 0.205 → 0.275, `--surface-2` 0.185 → 0.250 (still slate-cool, but in Linear/Notion territory rather than near-black)
- Soften dark-mode `--ink-1` from 0.97 to 0.93 so headings no longer glare on the lighter bg, with matching nudges to `--ink-2/4/5` to preserve the contrast steps
- Lift dark-mode chip `--*-soft` backgrounds (0.30–0.32 → 0.34–0.36) and `--*-ink` text (0.85 → 0.86–0.88) so pills read as elevated against the new paper
- Reduce dark-mode card/popover shadow alphas (0.40/0.50 → 0.25/0.38) to suit the lighter surfaces

## 0.1.61 — 2026-04-30

### Changed
- Implement editorial Chronicle redesign from `chronicle.zip` design handoff: switch to Inter Tight + Instrument Serif + JetBrains Mono fonts, slate-cool OKLCH ink palette, normalized semantic color tokens (`--paper`, `--surface-1`, `--ink-1…5`, `--accent`, `--good`, `--warn`, `--bad`, `--info`)
- Rebuild navigation shell as sticky blurred top bar with brand mark, search affordance, theme toggle, density/accent tweaks panel, bell, and gradient-avatar user dropdown
- Rebuild dashboard with editorial header band ("Godmorgen, {name}. her er ugen."), live sync indicator, 4-card KPI strip, 1.7fr/1fr grid (flow chart + on-call/current-week rail), incidents list with severity rail
- Rebuild weeklog detail with breadcrumb, 64px Instrument Serif H1, KPI strip, pull-quote summary card, restyled priority/absence/incident rows (drag handle, custom check, gradient avatars, collapsible incidents)
- Recolor Chart.js helpdesk charts to use the new CSS-variable palette so they react to dark mode and accent changes
- Add `data-density="compact"` and `data-accent="sage|terracotta|ink"` modifiers wired via Alpine + localStorage

### Added
- `templates/components/{pill,avatar,kpi_card,section_head,segmented,tabs}.html` reusable partials
- `slideIn` and `pulseGlow` keyframes for inline-edit animations and live sync dot

## 0.1.60 — 2026-04-11

### Changed
- Apply Notion/Linear/Cal.com design refinements: multi-layer shadows, whisper borders, tighter heading typography, improved metric cards, badge micro-tracking
- Remove automatic version bumping from CI pipeline

## 0.1.57 — 2026-04-03

### Fixed
- Restore `beforeend` swap for incident create
- Disable localization on incident `occurred_at` field for datetime-local compatibility
- Correct datetime format for incident form to prevent data loss on edit
- Correct HTMX target for incident edit form submission

## 0.1.55 — 2026-03-26

### Added
- 56-week view option to on-call calendar

## 0.1.53 — 2026-03-16

### Fixed
- Add `run_scheduler` management command to sync service

## 0.1.50 — 2026-03-06

### Added
- Manual sync button for ServiceDesk stats on kontrolpanel
- Color-coded state segments in task timeline chart

### Changed
- Replace APScheduler with simple sleep loop for ServiceDesk sync

### Fixed
- Missing closing `>` on priority item form div tag

## 0.1.45 — 2026-03-05

### Added
- Opgaver (Tasks) feature with full task management, timeline chart, assignees, and approvers
- Auto-refresh oncall week cards via HTMX polling

### Fixed
- Task timeline x-axis anchored to oldest task start date
- Task timeline chart rewrite with production logging
- Task approvers changed from M2M users to free-text field with fixed checkbox choices
- Auto-scroll and focus form when adding priority items
- Workflow concurrency to prevent Docker Hub rate limits

## 0.1.40 — 2026-03-02

### Fixed
- Add `default=""` to meeting fields to prevent NOT NULL constraint error

## 0.1.38 — 2026-02-22

### Added
- Weekly average stats to all exports (PDF, Markdown, HTML, email)

## 0.1.28 — 2026-02-21

### Added
- Inline meeting minutes with pill-based attendees and live markdown preview
- Drag-and-drop reordering for priority items
- Microsoft Graph API email backend
- Viewer read-only user group with RBAC
- Login/logout tracking with read-only admin
- Grouped bar chart for new vs closed tickets on dashboard
- New vs closed bar chart in exports
- Matplotlib helpdesk trend chart in exports

### Fixed
- HTML export and email chart scaling
- Docs dark mode, added Graph email guide in Danish
- Outlook web paste compatibility (inline styles, table layouts, bgcolor)
- Export improvements: card-style rows, rounded corners, visible pills, stats spacing

## 0.1.25 — 2026-02-13

### Changed
- Rename Fravær to Bemanding and add Arbejder hjemme option

## 0.1.23 — 2026-02-11

### Added
- On-call duty (rådighedsvagt) planning feature

### Fixed
- Stack stat cards vertically in dashboard right column

## 0.1.21 — 2026-02-10

### Fixed
- Show full descriptions in PDF/Markdown/HTML exports

## 0.1.18 — 2026-02-09

### Added
- Auto-updating version with date in footer via HTMX
- Danish weekday range on dashboard absence entries
- "Flex fri" absence type

### Fixed
- Absence edit not saving and dates not populating

## 0.1.15 — 2026-02-05

### Added
- HTML export format

### Fixed
- Priority item edit

## 0.1.13 — 2026-02-03

### Added
- ServiceDesk Plus integration with auto-sync

### Fixed
- Dynamic version in footer and dashboard card height
- Documentation for ServiceDesk integration

## 0.1.8 — 2026-02-02

### Added
- Favicon (calendar/weekly log design)
- Improved markdown export to match PDF structure

### Fixed
- Dark mode support for form fields
- Cancel button row restoration when editing
- OOB swap to close form after creating new entry
- Docker image to include docs/ and LICENSE

## 0.1.0 — 2026-02-01

### Added
- Initial release of FynBus Chronicle
- Weekly IT logbook with helpdesk statistics tracking
- Priority items, absences, and incident management
- PDF and Markdown export
- Docker containerization with multi-stage build
- SQLite-only deployment option
- Django admin with staff management
