# UX Designer Memory

Charter is report-layout / trust-surface / tools-hub (E-255-03). The coaching
dashboard, member-team sync, and tracked-opponent surfaces were removed in
E-239 (reports-first reframe). Only the reports serving surfaces and the small
admin tools-hub survive — design for those, not for dashboard machinery.

## Surviving Surfaces (design targets)

- **Scouting report** (`reports/scouting_report.html`, rendered by
  `src/reports/renderer.py`) — the primary design surface. Self-contained HTML:
  all CSS/JS inlined, spray charts embedded as base64, served from disk with no
  serve-time templating. Print/PDF-oriented base styles (`9pt`, `0.5in` padding,
  heat-map levels `.heat-0`..`.heat-4`).
- **Tools-hub admin** (`admin/reports.html`, `admin/users.html`,
  `admin/edit_user.html`) — the operator surface. Extends `base.html`, uses the
  2-tab sub-nav. `admin/reports.html` is the reference implementation for
  async-status / error-detail UX.
- Supporting: `auth/*`, `errors/*`.

## Established UI Patterns

### Base Layout
- `base.html`: `max-w-4xl mx-auto` container, `bg-blue-900` top nav, `bg-gray-50`
  body, `p-4 ... pb-16` main.
- **Top nav only** — brand text "Baseball Stats" on the left, a single "Admin"
  link (`/admin/reports`) on the right, plus a `{% block header_extras %}` slot
  (admin pages inject a Logout form there). There is NO bottom nav bar (the old
  4-tab Batting/Pitching/Games/Opponents bottom nav was a dashboard artifact,
  removed in E-239).

### Admin Sub-Nav Pattern (`admin/_subnav.html`)
- Horizontal link bar below the h1, above content.
- `mb-6 flex gap-4 border-b border-gray-300 pb-2 text-sm`
- Active tab: `font-bold underline text-blue-900`
- Inactive tab: `font-medium text-gray-600 hover:text-blue-900`
- **Two tabs: Reports | Users.** Included via
  `{% with active_tab='reports' %}{% include "admin/_subnav.html" %}{% endwith %}`.

### Table Pattern
- `min-w-full text-sm bg-white rounded shadow` on table
- `bg-blue-900 text-white` on thead
- Alternating rows: `{% if loop.index is even %}bg-gray-50{% endif %}`
- `border-b border-gray-200` on rows
- `py-2 px-3` on th/td
- Always wrap in `overflow-x-auto` div
- Most important columns leftmost

### Action Buttons in Tables
- Small inline actions: `text-xs text-blue-700 hover:underline`
- Destructive inline actions: `text-xs text-red-600 hover:underline`
- Form POST buttons inline: `<form ... class="inline"><button ...>`

### Primary Button
- `bg-blue-900 text-white px-4 py-2 rounded text-sm hover:bg-blue-800`

### Form Fields
- `w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500`

### Flash Messages
- Success: `p-3 bg-green-100 text-green-800 rounded border border-green-300`
- Error: `p-3 bg-red-100 text-red-800 rounded border border-red-300`
- Warning/info: `p-3 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-900`

### Back Link Pattern
- `text-blue-900 hover:underline text-sm` with `&larr;` arrow prefix

## Reference Implementations

- `src/api/templates/admin/reports.html` — auto-refresh (meta tag) and error
  tooltip / per-stage status patterns. Reference this page when designing
  similar async-status or error-detail UX.
- `src/api/templates/reports/scouting_report.html` — the self-contained report
  layout. Reference for report information hierarchy, heat-map treatment, and
  print/PDF-oriented styling.

## Superseded (do NOT present as current design guidance)

The following memories were retired in E-255 because the flows they described
were removed in E-239. They are tombstoned here only so future work does not
re-derive them as live targets:

- **E-178 "Coach-Friendly Language" terminology table** (Sync/Update Stats,
  Resolve/Merge, opponent Connect/Disconnect, Last Synced/Last Updated, etc.) —
  governed the member-sync and opponent-link flows, which no longer exist. Not a
  current terminology standard.
- **E-088 status-badge component** (green/yellow pill + dot for opponent
  "full stats" vs "scoresheet only" link state) — built for the removed
  tracked-opponent surface. Not a current component.

If a genuine terminology or badge need arises on a *surviving* surface, design it
fresh against that surface — do not resurrect these.

## Topic Files

- [Design Principles](design_principles.md) — consequence-oriented labels,
  question-as-heading, unified-verbs discipline, coach modes. All are
  surface-agnostic; the unified-verbs principle no longer carries the removed
  member-sync / opponent-link verb registry.

## Feedback

- [Coach async workflow reality](feedback_coach_async_workflow.md) — Coaches
  trigger actions and come back later; design for "return" not "wait".

## Key File Paths

- Base template: `src/api/templates/base.html`
- Scouting report (primary design surface): `src/api/templates/reports/scouting_report.html`
- Report renderer (self-contained HTML): `src/reports/renderer.py`
- Tools-hub admin (reference impl): `src/api/templates/admin/reports.html`
- Admin sub-nav partial: `src/api/templates/admin/_subnav.html`
- Admin users page: `src/api/templates/admin/users.html`
- Admin routes: `src/api/routes/reports_admin.py`
