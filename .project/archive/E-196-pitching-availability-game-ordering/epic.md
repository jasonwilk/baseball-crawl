# E-196: Pitching Availability and Game Chronological Ordering

## Status
`COMPLETED`

## Overview
Add pitching staff availability columns (Rest/Last and 7-day rolling workload) to all pitching display surfaces, and fix non-deterministic game ordering for same-day games by loading start_time and timezone from API responses into the games table. Together these give coaches workload-aware scouting intelligence with games displayed in correct chronological order.

## Background & Context
Scouting reports and opponent dashboards show season aggregate pitching stats but nothing about recent workload or availability. Coaches need to know who threw recently and how much -- critical for game planning against tournament opponents who may have burned their top arms.

Games currently display in non-deterministic order for same-day games (tournament doubleheaders) because the `games` table only has `game_date` (no time). The raw API JSON already contains start times -- we just truncate them during loading.

This epic was designed through a consultation session with baseball-coach (coaching requirements), ux-designer (display format), api-scout (data source verification), and the user. All design decisions are locked in.

**Expert consultation**: baseball-coach (coaching value of Rest/P(7d) columns, generation date annotation requirement), ux-designer (display formats, JS/PDF/print behavior), api-scout (confirmed data source fields across authenticated/public/game-summaries endpoints). All decisions locked prior to epic creation -- no further consultation required.

## Goals
- Coaches can see days since last outing and 7-day pitch workload for every opposing pitcher
- Same-day games (doubleheaders) display in correct chronological order across all surfaces
- Parity between standalone report path and opponent dashboard flow

## Non-Goals
- Pitch count rules or automated availability flags (future work)
- Historical workload tracking beyond the 7-day window
- Modifying any crawlers -- all data already exists in cached JSON or is queryable from DB
- New API calls or new crawl stages

## Success Criteria
- Every pitching display surface shows Rest/Last and P(7d) columns with correct data
- Doubleheader games on the same date display in correct chronological order (tiebroken by start_time per TN-3)
- Standalone report JS correctly transforms dates to days-rest in web view, falls back to formatted date in PDF/print
- All existing tests continue to pass; new tests cover the added functionality

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-196-01 | Add start_time and timezone to games table and loaders | DONE | None | - |
| E-196-02 | Fix game chronological ordering across all surfaces | DONE | E-196-01 | - |
| E-196-03 | Pitching workload query function | DONE | None | - |
| E-196-04 | Dashboard pitching availability columns | DONE | E-196-03 | - |
| E-196-05 | Standalone report pitching availability columns | DONE | E-196-03 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Migration 010

New migration `migrations/010_add_game_start_time.sql`:
- `ALTER TABLE games ADD COLUMN start_time TEXT` -- ISO 8601 datetime string
- `ALTER TABLE games ADD COLUMN timezone TEXT` -- IANA timezone identifier (e.g., `America/Chicago`)

Both columns are nullable. Existing rows remain NULL until next sync populates them.

### TN-2: API Data Sources for Start Time

| Endpoint | Time field | Timezone field | Full-day field |
|----------|-----------|---------------|----------------|
| `GET /teams/{team_id}/schedule` (authenticated) | `event.start.datetime` (ISO 8601) | `event.timezone` (IANA) | `event.full_day` (boolean) |
| `GET /public/teams/{public_id}/games` (public) | `start_ts` (ISO 8601) | `timezone` (IANA) | `is_full_day` (boolean) |
| `GET /teams/{team_id}/game-summaries` (authenticated) | **Not available** | **Not available** | N/A |

The game loader (game-summaries path) does NOT have start time data. It must preserve any existing `start_time`/`timezone` values during upsert rather than overwriting them with NULL.

### TN-3: Game Ordering Convention

Every `ORDER BY` clause that includes `game_date` must add `start_time` as a same-direction tiebreaker with `NULLS LAST`:
- **DESC queries** (e.g., recent form, game history): `ORDER BY game_date DESC, start_time DESC NULLS LAST`
- **ASC queries** (e.g., upcoming schedule, nearest game): `ORDER BY game_date ASC, start_time ASC NULLS LAST`

The tiebreaker preserves each query's existing sort direction. Games with NULL `start_time` sort after timed games on the same date in both directions. Applies to:
- `src/reports/generator.py` (standalone reports)
- `src/api/db.py` (dashboard queries)
- Any other query that orders games by `game_date`

### TN-4: Pitching Workload Data Model

Per-pitcher workload data computed from `player_game_pitching` joined to `games`:

| Field | Computation | NULL when |
|-------|------------|-----------|
| `last_outing_date` | `MAX(games.game_date)` from `player_game_pitching` | No appearances |
| `last_outing_days_ago` | `julianday(reference_date) - julianday(last_outing_date)` | No appearances |
| `pitches_7d` | `SUM(pitches)` where `game_date >= date(reference_date, '-6 days')` | 0 when no appearances in window; NULL when appearances exist but all pitch counts are NULL |
| `span_days_7d` | `julianday(MAX(game_date)) - julianday(MIN(game_date)) + 1` in 7d window | No appearances in 7d |

**7-day window boundary**: `game_date >= date(reference_date, '-6 days')` produces a 7-calendar-day inclusive window (reference_date back through reference_date minus 6). This ensures `span_days_7d` never exceeds 7, matching the "P (7d)" column header. Do NOT use `reference_date - 7` which creates an 8-day window.

`reference_date` is `date('now')` for dashboard queries, generation date for standalone reports (passed as parameter).

**Important**: The `games` table PK is `game_id` (TEXT), not `id`. Use `g.game_id` in joins.

### TN-5: Display Formats

**Rest/Last column:**
| Surface | Format | Column header |
|---------|--------|---------------|
| Dashboard (live web) | `Xd` (days since last, "Today" for 0) | Rest |
| Standalone report (web/JS enabled) | `Xd` (JS-computed from `data-date`) | Rest (JS swaps from "Last") |
| Standalone report (PDF/print/JS disabled) | `Mar 28` (formatted date) | Last |
| Opponent print view | `Mar 28` (formatted date) | Last |

**P(7d) column:**
| Surface | Format | Column header |
|---------|--------|---------------|
| All surfaces | `{pitches}/{span}d` (e.g., `85/5d`) | P (7d) |
| No appearances in 7d | `--` (em dash) | P (7d) |
| Appearances exist but all pitch counts NULL | `?/{span}d` | P (7d) |

**"Their Pitchers" card (opponent_detail.html):**
- Sub-line under existing stats: `Last: 3d ago * 60/2d`
- No appearances: `No recent outings`

**Annotation line (standalone report pitching section):**
- Web: "Data through [date]" (JS swaps from "Generated [date]")
- PDF/print: "Generated [date]"

### TN-6: JS Snippet Conventions (Standalone Report Only)

- Inline `<script>` at bottom of report `<body>`
- Uses `var` (not `let`/`const`) for max browser compatibility
- Targets elements via CSS classes: `.last-outing-cell`, `.last-outing-header`, `.pitching-annotation`
- Reads `data-date` attribute from `.last-outing-cell` elements to compute days-ago
- Falls back gracefully: if JS disabled, server-rendered date and "Last"/"Generated" headers remain valid
- No external dependencies

### TN-7: Parity Requirement

The report path (`src/reports/`) and opponent flow (`src/api/routes/dashboard.py` + templates) must show identical pitching data. Both paths use the same query function from `src/api/db.py` (TN-4). Display format differences (TN-5) are intentional per-surface adaptations, not data divergence.

## Open Questions
None -- all design decisions locked in from consultation session.

## History
- 2026-03-31: Created from consultation session with baseball-coach, ux-designer, api-scout, and user
- 2026-04-01: Incorporated 13 accepted review findings (CR spec audit + coach holistic + UXD holistic). 1 dismissed (P/Xd format tradeoff -- user locked in). Key changes: migration 010→009, renderer.py→generator.py refs, span formula fix, NULL pitch count display, shared-file notes, key-player workload sub-line AC, vague AC-3 tightened.
- 2026-04-01: Incorporated 5 accepted Codex spec review findings (of 9 total; 4 dismissed). Key changes: migration 009→010 (E-195 committed 009), ORDER BY direction-preserving convention (not hardcoded DESC), ace-box dual-mode rendering specified, 7-day window boundary fixed (−6 days not −7), TN-4 pitches_7d NULL consistency fix, db.py shared-file annotations.
- 2026-04-01: Final polish (3 minor fixes): Success Criteria ordering language aligned with TN-3, mixed NULL pitch count edge case added to E-196-03, format parentheticals removed from E-196-04/05 AC-2 (TN-5 is authoritative). Status set to READY.
- 2026-04-03: Completed. All 5 stories delivered. Migration numbered 014 (not 010 as spec'd -- 011-013 shipped by E-197/E-198/E-200 during review pause). 62 new tests across 5 test files. Review scorecard below.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR — E-196-01 | 3 | 3 | 0 |
| Per-story CR — E-196-02 | 1 | 1 | 0 |
| Per-story CR — E-196-03 | 0 | 0 | 0 |
| Per-story CR — E-196-04 | 1 | 1 | 0 |
| Per-story CR — E-196-05 | 2 | 2 | 0 |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 4 | 4 | 0 |
| **Total** | **11** | **11** | **0** |

### Documentation Assessment
New feature (pitching availability columns on all surfaces), new migration (014), new display behavior (JS dual-mode rendering), new game ordering convention. **Triggers docs update**: coaching docs should explain Rest/Last and P(7d) columns; admin docs should note migration 014.

### Context-Layer Assessment
| Trigger | Verdict | Details |
|---------|---------|---------|
| T1: New convention established? | **YES** | TN-3 game ordering convention: every `ORDER BY game_date` must include `start_time` as same-direction tiebreaker with `NULLS LAST`. Project-wide SQL convention. |
| T2: New footgun discovered? | **YES** | Game loader must preserve existing `start_time`/`timezone` via COALESCE (game-summaries lacks time data). 7-day window boundary must use `-6 days` not `-7` (8-day window bug). |
| T3: Agent capability changed? | **NO** | No agent definitions or capabilities modified. |
| T4: New domain knowledge codified? | **YES** | Pitching workload data model (TN-4: 4-field computation, 3-way pitches_7d semantics). Display format conventions (TN-5: per-surface rendering rules). JS snippet conventions for standalone reports (TN-6). Data parity requirement (TN-7). |
| T5: Process or workflow changed? | **NO** | No workflow changes. |
| T6: New integration pattern established? | **YES** | `get_pitching_workload()` shared query function pattern for dashboard/report data parity. Dual-mode rendering pattern (server-rendered fallback + JS upgrade) for standalone reports. `_enrich_pitchers_with_workload()` enrichment pattern reusable for future stat columns. |
