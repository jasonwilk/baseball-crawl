# E-167: Opponent Dedup Prevention and Resolution

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Prevent the opponent pipeline from creating duplicate tracked team rows and give the admin a search-powered workflow to resolve ambiguous opponents. Today, 34 team names have 2-5 duplicate rows because 8 independent team-INSERT locations across 7 modules each use different dedup keys. This epic consolidates all paths into a single shared function with a deterministic cascade, adds a CLI tool to auto-merge existing duplicates, and replaces the blank "connect opponent" form with a GC-search-powered suggestion workflow.

## Background & Context
The same real-world opponent can appear as multiple `teams` rows due to four root causes:

1. **GC upstream duplication**: Coaches add opponents via manual name entry (root_team_id only) AND GC team lookup (root_team_id + progenitor_team_id). GC creates separate opponent entries with different root_team_ids. ~14% of opponents are manual-only (no progenitor_team_id). Some games are split across both IDs.
2. **Bare→Resolved duplication**: `schedule_loader._find_or_create_stub_team()` creates rows keyed by name only; `opponent_resolver._ensure_opponent_team_row()` creates rows keyed by gc_uuid/public_id only. Neither checks the other's namespace.
3. **Resolved→Resolved duplication**: The resolver's public_id lookup requires `gc_uuid IS NULL`, missing rows that already have a different gc_uuid but the same public_id (cross-schedule contexts).
4. **Self-tracking**: Member teams (Freshman, JV, Varsity) appear as tracked opponents in scrimmages. The resolver creates tracked duplicates instead of linking to existing member rows.

**Scale**: 155 tracked teams total, 44 with no gc_uuid, 132 with no public_id. 34 team names with duplicates (2-5 rows each). 4 member teams.

**Design philosophy**: "Prevent what's obvious, ask about what's ambiguous." Three tiers:
- **Certain match → auto-prevent**: same gc_uuid, same public_id, or same name+season_year among tracked teams. Handled silently by the shared function.
- **Probable match → surface to admin**: ambiguous opponents surfaced with GC search suggestions for admin resolution.
- **Unknown → leave separate**: genuinely ambiguous cases stay separate until the admin acts.

**Prior art**: E-155 (Combine Duplicate Teams) delivered the merge infrastructure (`merge_teams()`, `find_duplicate_teams()`, admin merge page). This epic builds on E-155 by preventing future duplicates and resolving existing ones. E-162 (OpponentResolver gc_uuid fix) addresses a narrower sub-bug and is independent of this epic.

**Expert consultations:**
- **software-engineer**: Recommended single shared `ensure_team_row()` function replacing all 8 INSERT locations. Cascade: gc_uuid → public_id → name+season_year+tracked → INSERT. Self-tracking guard. Drop `gc_uuid IS NULL` from public_id lookup. 8 INSERT locations identified across 7 modules.
- **data-engineer**: One new COLLATE NOCASE index on name+season_year. No new tables or columns needed. Auto-merge script with dry-run for existing duplicates. opponent_links consolidation unnecessary (multiple root_team_ids → same resolved_team_id is correct). Name+season_year lookup is safe without UNIQUE constraint (best-effort heuristic).
- **api-scout**: `progenitor_team_id` is 100% reliable as single-season dedup signal when non-null. `root_team_id` is a completely separate namespace (confirmed -- NEVER store in gc_uuid). `is_hidden=true` entries are coach-identified junk. GC search endpoint (`GET /search/opponent-import`) supports name + sport + year + state + city + age_group filters. Response schema inferred but not captured -- needs verification.
- **ux-designer**: Enhance existing opponents page with unresolved banner + search-powered resolve flow (replaces blank connect form). Three-step: opponents list → suggestion page (auto-search + refine) → confirm page (with duplicate detection). "No match" as first-class outcome. Queue-optimized redirect for work-through-the-list flow.

## Goals
- All pipeline team-INSERT paths use a single shared function with a deterministic dedup cascade
- The cascade prevents duplicates from same gc_uuid, same public_id, or same name+season_year among tracked teams
- Member teams are never re-created as tracked opponents (self-tracking guard)
- Existing 34 duplicate sets can be auto-merged via CLI with dry-run safety
- Hidden opponents (`is_hidden=true`) are filtered from the active pipeline
- Admin has a search-powered workflow to resolve unresolved opponents (replacing blank URL-paste form)
- Admin can dismiss unresolvable opponents ("no match") so they stop appearing as work items

## Non-Goals
- Fuzzy name matching algorithms (IDEA-043 remains CANDIDATE -- not needed at current scale)
- Cross-season team dedup (fresh-start philosophy: each season is separate)
- Roster-overlap-based dedup (post-scoring signal -- future idea)
- Coach-facing resolution workflow (admin-only for now)
- Admin add-team path dedup (user-initiated with URL input -- different expectations)
- Batch resolution UI (one-at-a-time with queue-optimized redirect is sufficient)
- Automated resolution without admin confirmation for ambiguous cases

## Success Criteria
- Running the full pipeline (crawl + load + resolve) on all 4 member teams produces zero new duplicate team rows for opponents that are already in the database
- The `bb data dedup --dry-run` command identifies all exact-name duplicate groups and previews what merges would do
- The `bb data dedup --execute` command auto-merges safe duplicates (same name, same season_year, no games between them)
- The admin opponents page shows an "Unresolved Opponents" banner with a count and "Start resolving" link
- Clicking "Resolve" on an unresolved opponent shows GC search suggestions pre-filled with the opponent's name
- The admin can select a suggestion, confirm the connection, and the opponent_link + team row are updated
- When a selected suggestion matches an existing team row, the confirm page warns about the duplicate and offers a merge link
- The admin can dismiss an opponent as "no match" (sets `is_hidden = 1`) and it stops appearing as unresolved; this is reversible via an "Unhide" button
- Existing tests pass; new tests cover the shared function cascade, auto-merge safety, and resolution flow

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-167-01 | Shared `ensure_team_row()` function and name index migration | DONE | None | - |
| E-167-02 | Migrate pipeline INSERT paths to shared function | DONE | E-167-01 | - |
| E-167-03 | Auto-merge CLI and enhanced duplicate detection | DONE | None | - |
| E-167-04 | Admin opponent resolution workflow with GC search suggestions | DONE | E-167-01 | - |
| E-167-05 | Documentation Update for E-167 | DONE | E-167-01, E-167-02, E-167-03, E-167-04 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Dedup Cascade

The shared `ensure_team_row()` function implements a deterministic lookup cascade. All identifier parameters are optional -- callers pass what they have:

```
ensure_team_row(db, *, name=None, gc_uuid=None, public_id=None, season_year=None, source=None) -> int
```

**Lookup order:**
1. **gc_uuid match** (`WHERE gc_uuid = ?`): Strongest signal. If found, back-fill `public_id` and `name` where NULL on the existing row. Return existing row's `id`.
2. **public_id match** (`WHERE public_id = ?`): Second strongest. If found, back-fill `gc_uuid` where NULL (using collision-safe write). Log warning if gc_uuid mismatch. Return existing row's `id`. NOTE: No `gc_uuid IS NULL` filter -- this is the fix for Root Cause 3.
3. **name+season_year match** (`WHERE name = ? COLLATE NOCASE AND COALESCE(season_year, -1) = COALESCE(?, -1) AND membership_type = 'tracked'`): Weakest signal. If multiple rows match, return the one with the lowest `id` (oldest row). If found, back-fill `season_year` and `name` (UUID-as-name stub only) where NULL. Do NOT back-fill `gc_uuid` or `public_id` on name-only matches -- the name match is a heuristic and could be wrong; attaching an identifier to the wrong row is harder to undo than a duplicate.
4. **No match → INSERT**: Create new row with all available identifiers. `membership_type = 'tracked'`, `source` from caller.

**Self-tracking guard** (runs before step 4): Check `WHERE gc_uuid = ? AND membership_type = 'member'` and `WHERE public_id = ? AND membership_type = 'member'`. If either matches, return the member team's `id` without creating a tracked duplicate. When both gc_uuid and public_id are NULL (name-only callers like the schedule loader), also check `WHERE name = ? COLLATE NOCASE AND membership_type = 'member'`. If a member row matches by name, return its id. This ensures scrimmage opponents that are actually member teams are not re-created as tracked rows.

**Back-fill rules** (applied when enriching an existing row):
- `gc_uuid`: Steps 1-2 only. Write only when existing row has NULL. Collision-safe: check `SELECT id FROM teams WHERE gc_uuid = ? AND id != ?` before writing; skip and log warning on collision. NOT written on step-3 name matches.
- `public_id`: Steps 1-2 only. Write only when existing row has NULL. Collision-safe: same pattern as gc_uuid. NOT written on step-3 name matches.
- `name`: Steps 1-3. Update only if existing name equals the gc_uuid string (UUID-as-name stub pattern). Real names are preserved.
- `season_year`: Steps 1-3. Write only when existing row has NULL.

### TN-2: Module Location

The shared function lives in `src/db/teams.py` (new module). This follows the existing pattern where `src/db/merge.py` contains team merge logic. The function is a pure database operation (takes a db connection, returns an integer PK), with no API client or config dependencies.

### TN-3: Pipeline Migration Map

Each INSERT path maps to the shared function with specific available data:

| Current Path | Module | Available Data | Shared Function Call |
|-------------|--------|---------------|---------------------|
| `_find_or_create_stub_team` | schedule_loader | name, season_year (derivable from `self._season_id`) | `ensure_team_row(db, name=name, season_year=..., source='schedule')` |
| `_ensure_opponent_team_row` | opponent_resolver | gc_uuid, public_id, name, season_year | `ensure_team_row(db, gc_uuid=..., public_id=..., name=..., season_year=..., source='resolver')` |
| `_ensure_team_row` | game_loader | gc_uuid, name | `ensure_team_row(db, gc_uuid=..., name=..., source='game_loader')` |
| `_ensure_team_row` | scouting.py | gc_uuid or public_id, name | `ensure_team_row(db, gc_uuid=..., public_id=..., name=..., source='scouting')` |
| `_ensure_team_row` | roster.py | gc_uuid | `ensure_team_row(db, gc_uuid=..., source='roster')` |
| `_ensure_team_row` | season_stats_loader | gc_uuid | `ensure_team_row(db, gc_uuid=..., source='season_stats')` |
| INSERT OR IGNORE | scouting_loader | gc_uuid, name (from cached schedule data) | `ensure_team_row(db, gc_uuid=..., name=..., source='scouting_loader')` |
| INSERT OR IGNORE | scouting.py (line 537) | gc_uuid | `ensure_team_row(db, gc_uuid=..., source='scouting')` |

The opponent_resolver's `_ensure_opponent_team_row` has additional logic beyond team creation (writing gc_uuid/public_id with collision checks, UUID-as-name stub pattern). The resolver-specific logic that doesn't fit the shared function should remain in the resolver as a thin wrapper that calls `ensure_team_row()` and then applies resolver-specific updates.

### TN-4: is_hidden Filtering

The opponent seeder (`seed_schedule_opponents`) and resolver (`OpponentResolver._resolve_team`) should skip `is_hidden=true` entries. The seeder reads from cached `opponents.json` files and should filter entries where `is_hidden=true` before upserting into `opponent_links`. The resolver iterates the opponents list from the API and can filter before processing.

Filtering happens at the pipeline level (seeder/resolver), not in the shared function -- the shared function doesn't know about opponent registry metadata.

### TN-5: Auto-Merge Safety Guardrails

The auto-merge CLI (`bb data dedup`) uses existing E-155 infrastructure:

**Safe-merge predicate** (all must be true):
1. Same name (case-insensitive) AND same season_year (or both NULL, or one NULL and one non-NULL) -- from `find_duplicate_teams()`
2. Both teams have `membership_type = 'tracked'` -- already enforced by `find_duplicate_teams()`
3. `games_between_teams == 0` -- from `preview_merge()`. If teams played each other, they are NOT the same team.
4. No member team in the group -- already enforced by `merge_teams()`.

**Canonical selection heuristic** (in priority order):
1. Team with `has_stats = True` wins (has real data)
2. Higher `game_count` wins (more games linked)
3. Lower `id` wins (older row, likely first created)

**Enhanced detection**: Extend `find_duplicate_teams()` to also catch NULL-vs-non-NULL season_year pairs. A stub with `season_year=NULL` and a resolved team with `season_year=2026` sharing the same name are likely duplicates.

### TN-6: Admin Resolution Workflow

**Routes** (all under `/admin/opponents/`):
- `GET /admin/opponents/{link_id}/resolve` -- Suggestion page with auto-search results
- `GET /admin/opponents/{link_id}/resolve` with `?q=...&state=...&city=...` -- Refined search
- `POST /admin/opponents/{link_id}/resolve` -- Confirm connection (sets resolved_team_id, public_id, gc_uuid on the opponent_link and team rows)
- `POST /admin/opponents/{link_id}/skip` -- Mark as "no match" (sets `is_hidden = 1` on the opponent_link row)

**GC Search Integration**:
- Pre-fill search with opponent's `opponent_name` + `sport=baseball` + `year={season_year}` (member team's `season_year`, falling back to current calendar year)
- Display results as cards: team name (required minimum), plus location (city/state), age group, record, public_id when available in the response
- Admin selects a result → confirm page shows full team profile + duplicate detection

**Duplicate Detection at Confirm Time**:
- After admin selects a GC team, check if that team's `public_id` already exists in our `teams` table
- If match found: show yellow warning with team name + link to merge page (`/admin/teams/merge?team_ids=...`)
- If no match: proceed with normal connection flow

**"No Match" Outcome**:
- `POST /admin/opponents/{link_id}/skip` sets `is_hidden = 1` on the `opponent_links` row
- Opponents with `is_hidden = 1` are excluded from the unresolved count and banner (they are also filtered out by the pipeline per TN-4, so the flag has dual purpose)
- This is reversible -- a new `hidden` filter tab on the opponents page shows only hidden rows, each with an "Unhide" button that sets `is_hidden = 0`

**Race Condition Guard (Confirm Step)**:
- Between the admin selecting a GC team and clicking "Confirm," another pipeline run could create a row for the same team. The confirm POST must use `ensure_team_row()` (which handles this atomically) rather than a raw INSERT.
- The confirm step unconditionally sets `resolution_method = 'search'` on the opponent_link row (overwriting any previous value including 'auto' or 'manual') -- the admin's explicit action is the most authoritative resolution.

**GC Search Parameter Passthrough**:
- The suggestion page pre-fills the search with `opponent_name + sport=baseball + year={season_year}` (member team's `season_year`, falling back to current calendar year). The "Refine Search" form allows the admin to override `name`, `state`, and `city`.
- The refine form submits as GET params (`?q=...&state=...&city=...`); these are passed through to the GC search endpoint in addition to the fixed `sport=baseball` and `year` params.

**Error Handling**:
- If the GC search call fails (auth expired, network error, 500): show a flash error message and fall back to the manual-paste link prominently. Do NOT crash the page.

**public_id Contingency**:
- The GC search response may not include a `public_id` field. If `public_id` is absent from the selected result, the confirm step writes only `gc_uuid` (from the search result's team ID) and sets `resolution_method = 'search'`. The opponent remains partially resolved but usable.

**Queue-Optimized Redirect**:
- After successful resolution or skip, redirect to `/admin/opponents?filter=unresolved` so the next unresolved opponent is immediately visible

**Template**: `opponent_resolve.html` (new) with two modes: `suggestions` (search results + refine form) and `confirm` (selected team profile + duplicate warning). Follows the existing pattern in `opponent_connect.html`.

### TN-7: Search Endpoint Schema Verification

The GC search endpoint (`GET /search/opponent-import`) response schema is inferred but not captured. Story E-167-04 must verify the actual response body before building the UI. The implementer should execute a test search call and document the response shape. If the response differs significantly from the inferred schema in `docs/api/endpoints/get-search-opponent-import.md`, the implementer should update the endpoint doc and adapt the UI accordingly.

### TN-8: Migration

**Migration 007**: Add a case-insensitive name+season_year index on the teams table:

```sql
CREATE INDEX IF NOT EXISTS idx_teams_name_season_year
    ON teams(name COLLATE NOCASE, season_year);
```

This serves both the dedup detection query in `find_duplicate_teams()` and the name-based lookup step in `ensure_team_row()`.

## Open Questions
- **GC search endpoint response schema**: The `/search/opponent-import` response body is inferred but unverified. E-167-04 includes adaptive ACs ("or whatever fields the actual response provides") and a stop-and-report protocol if schema differs materially. This does not block READY -- the story handles the unknown.

## History
- 2026-03-27: Created. Expert consultations with SE, DE, api-scout, and UXD complete. Promotes IDEA-044 (Prevent Duplicate Team Creation). Partially addresses IDEA-043 scope (exact-match detection) without fuzzy matching.
- 2026-03-27: Set to READY after holistic team review and two Codex spec review iterations.
- 2026-03-27: Dispatch started.
- 2026-03-27: All 4 stories DONE (01: shared ensure_team_row + migration, 02: 8-module pipeline migration + is_hidden filtering, 03: auto-merge CLI + enhanced duplicate detection, 04: admin resolution workflow with GC search). Epic COMPLETED. Key findings fixed during dispatch: TeamProfile dataclass vs dict mismatch (CR), test fixture season_year column regression (Codex), is_active default regression (Codex), public_id collision in confirm POST (Codex). Documentation and context-layer assessments complete.

**Documentation assessment**: DONE -- docs-writer updated `docs/admin/operations.md` (dedup CLI, opponent resolution workflow) and `docs/admin/architecture.md` (migration 007).

**Context-layer assessment**:
1. New convention (ensure_team_row canonical path): **YES** -- codified in CLAUDE.md Architecture
2. Architectural decision (dedup cascade): **YES** -- codified in CLAUDE.md Architecture
3. Footgun (template test scope): **YES** -- noted (not codified as rule, CR practice insight)
4. Agent behavior change: **NO**
5. Domain knowledge (GC opponent duality): **YES** -- codified in CLAUDE.md GameChanger API
6. New CLI command (bb data dedup): **YES** -- codified in CLAUDE.md Commands

### Review Scorecard

**Spec reviews (pre-dispatch):**

| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 8 | 5 | 3 |
| Internal iteration 1 -- Holistic team (PM+SE+DE+api-scout+UXD) | 12 | 12 | 0 |
| Codex iteration 1 | 6 | 6 | 0 |
| Codex iteration 2 | 5 | 4 | 1 |
| **Spec total** | **31** | **27** | **4** |

**Code reviews (dispatch):**

| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-167-01 | 1 | 1 | 0 |
| Per-story CR -- E-167-02 | 2 | 2 | 0 |
| Per-story CR -- E-167-03 (2 rounds) | 6 | 6 | 0 |
| Per-story CR -- E-167-04 (2 rounds) | 5 | 4 | 1 |
| CR integration review (2 rounds) | 1 | 1 | 0 |
| Codex code review | 5 | 4 | 1 |
| **Code total** | **20** | **18** | **2** |
