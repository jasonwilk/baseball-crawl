# UX Designer Memory

## Established UI Patterns

### Base Layout
- `base.html`: `max-w-4xl mx-auto`, `bg-blue-900` nav, `bg-gray-50` body, `pb-16` main (for bottom nav clearance)
- Bottom fixed nav bar with 4 tabs: Batting, Pitching, Games, Opponents
- Admin pages do NOT show the bottom nav (admin templates extend base.html but are not linked from the bottom nav)

### Admin Sub-Nav Pattern
- Horizontal link bar below h1, above content
- `flex gap-4 border-b border-gray-300 pb-2 text-sm`
- Active tab: `font-bold underline text-blue-900`
- Inactive tab: `font-medium text-gray-600 hover:text-blue-900`
- Current tabs: Users | Teams | (Opponents -- proposed in E-088 design)

### Table Pattern
- `min-w-full text-sm bg-white rounded shadow` on table
- `bg-blue-900 text-white` on thead
- Alternating rows: `{% if loop.index is even %}bg-gray-50{% endif %}`
- `border-b border-gray-200` on rows
- `py-2 px-3` on th/td
- Always wrap in `overflow-x-auto` div
- Most important columns leftmost

### Card Pattern (dashboard detail pages)
- `bg-white rounded shadow border border-gray-200 p-4` for content cards
- `text-base font-bold text-blue-900 mb-3` for card headings

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

## Coach-Friendly Language (Current Conventions — E-178, supersedes E-088)

### Terminology (E-178 replacements)

These terms replaced E-088 / pre-E-178 equivalents. Use the E-178 term in all new work.

| Old Term (E-088 / pre-E-178) | Current Term (E-178) | Context |
|---|---|---|
| "Discovered" (gc_uuid badge) | "Connected" | Consequence-oriented: tells coach they get full stats |
| "Not available (403)" (gc_uuid badge) | "Limited access" | Consequence-oriented: tells coach data is partial |
| "Sync" / "Sync Now" (action button) | "Update Stats" | Unified verb for all data refresh actions |
| "Last Synced" (column/label) | "Last Updated" | Consistent with "Update Stats" verb |
| "Syncing..." / "Running..." (status) | "Updating..." | Consistent with "Update Stats" verb |
| "Sync failed" (status badge) | "Update failed" | Consistent with "Update Stats" verb |
| "Resolve" (duplicate banner link) | "Merge" | User decision: merge duplicates, not "resolve" them |
| "Canonical" (merge page labels) | "keep" / "remove" | Plain English for merge page decisions |
| "Resolved" (flash messages) | "Linked" | Opponent connection language |
| "Unresolved — map first" (inline text) | "Not linked — find on GameChanger first" | Action-oriented, explains what to do |
| "Stats not loaded yet" (empty state) | "Stats aren't ready yet" | Softer, less technical |

### Retained terms (unchanged by E-178)

These E-088 terms remain current:
- "Scoresheet only" (yellow badge)
- "Full stats" (green badge)
- "Connect to GameChanger" (opponent link action)
- "Disconnect" (opponent unlink action)

### Opponent link state badges

- Auto-linked: "Full stats" (green badge) + "auto" micro-label (gray, secondary)
- Manual-linked: "Full stats" (green badge) + "manual" micro-label (gray, secondary)
- Unlinked: "Scoresheet only" (yellow badge)

Key principle: Coaches care about "do I have their real stats?" not HOW the connection was made.

## Status Badge Component (E-088)

Designed for opponent link state. Uses filled/unfilled dot + colored pill pattern:
- Green pill + filled green dot = full stats available
- Yellow pill + filled yellow dot = scoresheet only
- Auto/manual distinction shown as gray micro-text BESIDE the badge, not inside it

See E-088 design advisory for full HTML/Tailwind markup.

## Reference Implementations

- `src/api/templates/admin/reports.html` — auto-refresh (meta tag) and error tooltip patterns. Reference this page when designing similar async-status or error-detail UX.

## Topic Files

- [Design Principles](design_principles.md) — Consequence-oriented labels, question-as-heading, unified verbs, coach modes (E-178)

## Feedback

- [Coach async workflow reality](feedback_coach_async_workflow.md) -- Coaches trigger actions and come back later; design for "return" not "wait"

## Key File Paths

- Base template: `src/api/templates/base.html`
- Admin teams page: `src/api/templates/admin/teams.html`
- Dashboard opponent list: `src/api/templates/dashboard/opponent_list.html`
- Dashboard opponent detail: `src/api/templates/dashboard/opponent_detail.html`
- Dashboard routes: `src/api/routes/dashboard.py`
