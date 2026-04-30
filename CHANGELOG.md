# Changelog

All notable changes to FynBus Chronicle are documented here.

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
