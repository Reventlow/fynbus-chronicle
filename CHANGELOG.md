# Changelog

All notable changes to FynBus Chronicle are documented here.

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
