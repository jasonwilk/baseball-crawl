# E-152: Schedule-Based Opponent Discovery

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Populate `opponent_links` from schedule data so that ALL opponents -- past and upcoming -- are discovered automatically when a member team syncs. Currently, the opponent resolver exists but is not wired into the sync pipeline, and schedule-based opponents (especially future games) are never extracted. After this epic, every team sync discovers every opponent on the schedule and records them in `opponent_links` with clear linked/unlinked status.

## Background & Context
The user (a HS freshman baseball coach) identified a critical gap: "The entire point of this is that I run a team. And I can see my future opponents so that I can scout them." Currently, `opponent_links` has at most a few manually-inserted rows for SB Freshman (team 89) because the `OpponentResolver` has never run automatically for that team, and there is no code that extracts opponents from `schedule.json`.

Two data sources contain opponent information:
1. **`opponents.json`** (from `GET /teams/{team_id}/opponents`): Contains ~20 entries with `root_team_id`, `name`, and optionally `progenitor_team_id`. The existing `OpponentResolver` handles this but isn't wired into the sync pipeline.
2. **`schedule.json`** (from `GET /teams/{team_id}/schedule`): Contains ~38 events with `pregame_data.opponent_id` and `opponent_name`. No code currently reads this for opponent discovery.

**Expert consultation completed:**
- **Baseball Coach**: Discovery must run automatically on every sync -- it is a side effect of having a schedule, not a separate action. Discovery and scouting are distinct phases; this epic is discovery only. No fuzzy name matching (manual admin linking only).
- **Data Engineer**: Schema already supports linked and name-only opponents (nullable `resolved_team_id`/`public_id`). No migration needed. Identified critical compatibility risk with `resolve_unlinked()` flow (see iteration 1 review).
- **Software Engineer**: `OpponentResolver` exists at `src/gamechanger/crawlers/opponent_resolver.py` (~461 lines), handles auto (~86%) and unlinked (~14%) resolution. Schedule-based discovery would be entirely new code. Confirmed `OpponentResolver` is NOT wired into `run_member_sync()` (`crawl.py` runs `OpponentCrawler` for fetch/cache only). Recommends adding a sibling seeder.
- **API Scout**: Definitively confirmed `schedule.pregame_data.opponent_id == opponents.root_team_id` (100% match across 54 opponents in real data). These are local registry keys, NOT canonical UUIDs. `progenitor_team_id` is the canonical UUID (= `teams.gc_uuid`). No shortcut to `public_id` from schedule alone. `GET /search/opponent-import` endpoint exists as potential name-only fallback but response schema not yet captured.
- **UX Designer**: Admin Opponents tab is salvageable (needs framing + label cleanup). Teams page needs member/tracked split. Coaching schedule view belongs in `/dashboard/`, not `/admin/`. UI changes scoped to a separate epic.

## Goals
- Every member team sync automatically discovers all opponents from the schedule (past and upcoming) and populates `opponent_links`
- Both "linked" opponents (real GC team with `progenitor_team_id`) and "name-only" opponents (just a typed name) are recorded in `opponent_links`
- Discovery is idempotent -- re-syncing does not create duplicate rows

## Non-Goals
- Coaching-facing schedule view or opponent detail pages (separate epic -- needs UX design)
- Admin Opponents tab redesign or Teams page cleanup (separate epic)
- Automatic scouting triggers (fetching roster/stats for discovered opponents)
- Fuzzy name matching for name-only opponents
- Manual admin linking UI for name-only opponents
- New database migrations or schema changes

## Success Criteria
- After running a member team sync for SB Freshman, `opponent_links` contains a row for every unique opponent that appears in the team's schedule
- After OpponentResolver runs (wired in by E-152-02), linked opponents have `resolution_method='auto'` and `resolved_team_id` populated
- Name-only opponents have a row with `opponent_name` set and `resolved_team_id` NULL
- Re-running the sync does not create duplicate rows
- The correct identifier mapping is used per Technical Notes "GC Identifier Mapping" section

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-152-01 | Schedule opponent seeder | DONE | None | - |
| E-152-02 | Wire opponent discovery into member sync | DONE | E-152-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### GC Identifier Mapping (Confirmed)
API Scout cross-referenced real data and confirmed the identifier relationships:

| ID Field | Namespace | Use For |
|---|---|---|
| `schedule.pregame_data.opponent_id` | = `root_team_id` (local registry key) | Joining schedule games to `opponent_links` |
| `opponents.root_team_id` | Local registry key | Dedup key in `opponent_links` UNIQUE constraint |
| `opponents.progenitor_team_id` | Canonical GC UUID | `GET /teams/{id}` for metadata + `public_id`; store as `teams.gc_uuid` |
| `public_id` | Public slug | All `/public/` scouting endpoints |

**Verified**: `schedule.pregame_data.opponent_id == opponents.root_team_id` for 54/54 opponents (100%). These are NOT canonical UUIDs -- the schedule endpoint doc note claiming "usable as `team_id`" is misleading (api-scout will correct the doc).

**Insertion path**: Use `pregame_data.opponent_id` directly as `root_team_id` in `opponent_links`. Cross-reference `opponents.json` by `root_team_id` for richer `opponent_name`. The seeder does NOT use `progenitor_team_id` for any DB write -- resolution (including `gc_uuid` population from `progenitor_team_id`) is OpponentResolver's job.

**Null progenitor**: ~14% of opponents have `progenitor_team_id: null`. These get name-only rows in `opponent_links` (no `resolved_team_id`, no `public_id`). `GET /search/opponent-import` is a potential future fallback but response schema is not yet captured -- out of scope for this epic.

### Division of Labor: Seeder vs. OpponentResolver
The schedule seeder and OpponentResolver have distinct responsibilities:

- **Seeder (E-152-01)**: Seeds identity rows in `opponent_links` with `resolution_method=NULL` and `resolved_team_id=NULL` for ALL opponents. The seeder does NOT populate `resolved_team_id` or set any resolution method -- it is a pure identity seeder. Its upsert always updates `opponent_name` regardless of existing resolution state. For all other fields, writes are suppressed when the existing row has a non-NULL `resolution_method` (`'auto'`, `'follow-bridge'`, `'manual'`) -- those rows are protected from overwrite. **No auth, no network, fast.**
- **OpponentResolver `resolve()` (wired in by E-152-02)**: Runs AFTER the seeder. Makes **live API calls** (NOT reading cached `opponents.json`): `GET /teams/{team_id}/opponents` (paginated) + `GET /teams/{progenitor_team_id}` per linked opponent (~18+ calls with 1.5s delay each). Upgrades linked rows to `resolution_method='auto'` with `resolved_team_id` and `public_id`. **Requires valid auth context** (gc-token already refreshed at sync start). Only `resolve()` should be called -- `resolve_unlinked()` is experimental and must NOT be wired into the automatic sync pipeline.

Name-only rows retain `resolution_method=NULL` for forward compatibility with potential future `resolve_unlinked()` manual runs.

### Resolution Method Values
Existing values: `'auto'` (progenitor bridge), `'follow-bridge'` (experimental), `'manual'` (human override, protected from auto-overwrite). The seeder does NOT introduce a new value -- it seeds with `NULL`, and OpponentResolver upgrades to `'auto'` where possible.

### Two Data Sources, One Pipeline Step
The schedule seeder should cross-reference both `schedule.json` and `opponents.json`:
1. Parse `schedule.json` for all events with `pregame_data.opponent_id`
2. Look up each opponent in `opponents.json` by `root_team_id` for `opponent_name`
3. **Name precedence**: `opponents.json` `name` field is primary; `schedule.json` `pregame_data.opponent_name` is fallback (used when opponent is absent from opponents.json)
4. Opponents found in schedule but NOT in opponents.json get name-only rows (using schedule name)
5. Opponents found in both use opponents.json name

### Existing OpponentResolver
The `OpponentResolver` at `src/gamechanger/crawlers/opponent_resolver.py` already handles resolution via live API calls (`GET /teams/{team_id}/opponents` + per-opponent metadata calls). It is confirmed NOT wired into the sync pipeline (`src/pipeline/crawl.py` runs `OpponentCrawler` which fetches/caches `opponents.json`, but NOT `OpponentResolver` which makes live API calls to resolve opponents). Story E-152-02 must wire in both the seeder and the resolver.

**Single-team filtering**: `OpponentResolver.__init__` takes a `CrawlConfig`, and `resolve()` iterates ALL `config.member_teams`. When called from a per-team sync, the config MUST be filtered to just the syncing team before passing to OpponentResolver. The same pattern used in `crawl.py` (filter `config.member_teams` to match `team_id`) applies here. Without filtering, every per-team sync would trigger resolution for ALL member teams (4x API calls).

### Pipeline Execution Order
The required order within `run_member_sync()` after crawl completes:
1. **Schedule seeder** (E-152-01) -- seeds identity rows from local JSON with `resolution_method=NULL`
2. **OpponentResolver** -- upgrades linked rows to `'auto'` with `resolved_team_id`, `public_id`

If reversed, the seeder's upsert protection logic would need to be more complex. Seeder-first is the simple, correct design.

### Data File Path Discovery
Schedule and opponents JSON files live at `data/raw/{season_slug}/teams/{gc_uuid}/schedule.json` (and `opponents.json`), where `season_slug` is a TEXT value like `"2026-spring-hs"` from `seasons.season_id` (NOT the INTEGER `teams.season_year`). Using `season_year` would produce `data/raw/2026/...` which doesn't exist; the actual directories use the full slug.

Since E-152-02 must load `CrawlConfig` for OpponentResolver anyway, use `config.season` (which comes from `SELECT season_id FROM seasons ORDER BY year DESC LIMIT 1`) for path construction. Query `teams WHERE id = team_id` only for `gc_uuid`. Construct: `data/raw/{config.season}/teams/{gc_uuid}/schedule.json`. This avoids the NULL risk from `season_year` and uses the same season source as the crawlers that wrote the files.

### Idempotency
The `UNIQUE(our_team_id, root_team_id)` constraint combined with `ON CONFLICT DO UPDATE` upsert logic handles idempotency. No special deduplication code needed beyond correct upsert SQL.

## Open Questions
- None remaining (identifier mapping is a verification task in E-152-01, not an open question)

## History
- 2026-03-24: Created. Expert consultation: baseball-coach, data-engineer, software-engineer, api-scout, ux-designer. API Scout confirmed identifier mapping (opponent_id == root_team_id, 100% match). UX Designer recommendations captured for follow-up UI epic.
- 2026-03-24: Iteration 1 review. Accepted DE findings (upsert protection, resolve_unlinked compatibility, resolved_team_id division of labor, execution order) and SE findings (OpponentResolver confirmed absent, path discovery gap). Dropped `resolution_method='schedule'` -- seeder seeds with NULL, OpponentResolver handles all resolution. Added "Division of Labor", "Pipeline Execution Order", and "Data File Path Discovery" to Technical Notes. CR findings: 4/6 already fixed by DE/SE incorporations; accepted F-3 (handoff return type/error contract) and F-5 (error isolation specifics).
- 2026-03-24: Iteration 2 review. Accepted SE findings: OpponentResolver must be filtered to single team (added to "Existing OpponentResolver" section + E-152-02 AC-6); path construction must use `config.season` slug not `season_year` INT (rewrote "Data File Path Discovery"). Accepted DE finding (same path issue, confirmed with evidence from crawlers). Accepted CR N-1 (Technical Approach / Handoff Context API mismatch). Cleaned up AC-5 progenitor_team_id mention.
- 2026-03-24: Codex spec review. Accepted all 5 findings: P1-1 (tightened AC-3 to require ALL schedule opponents, fixed stale "empty" baseline in Background), P1-2 (OpponentResolver makes live API calls -- updated Division of Labor with auth/network requirements, specified only resolve() not resolve_unlinked(), CredentialExpiredError must propagate in AC-4), P2-1 (explicit name precedence: opponents.json primary, schedule.json fallback), P2-2 (fixed wrong crawl.py path), P3-1 (simplified AC-5 to reference TNs).
- 2026-03-24: Codex iteration 2. Accepted all 3 findings: P2-1 (Technical Approach contradicted AC-4 on resolver error isolation -- tightened to match), P2-2 (3 stale "cached opponents.json" references -- propagation failures from iter 1 fix, updated in E-152-01 Context, E-152-02 Context, and epic TN "Existing OpponentResolver"), P3-1 (split overloaded AC-4 into AC-4a seeder isolation / AC-4b resolver auth propagation / AC-4c pipeline continuation). Consistency sweep clean. Epic set to READY.
- 2026-03-24: Epic set to ACTIVE. Dispatch started.
- 2026-03-24: Codex iteration 3. Accepted all 3 findings: P1 (AC-8 wrongly treated missing opponents.json as no-op -- fixed to only no-op when schedule.json is missing; opponents.json absence still seeds schedule opponents as name-only rows; updated Handoff Context), P2 (AC-4c "regardless of discovery outcome" conflicted with AC-4b auth propagation -- clarified to "regardless of non-auth discovery errors"), P3 (standardized stale `schedule.opponent_id` to `schedule.pregame_data.opponent_id` in TN Verified line). Consistency sweep clean.

### Review Scorecard

| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR + holistic | ~12 | 10 | 2 |
| Internal iteration 2 -- CR + holistic | 5 | 5 | 0 |
| Codex iteration 1 | 5 | 5 | 0 |
| Codex iteration 2 | 3 | 3 | 0 |
| Final review -- CR spec audit | 2 | 2 | 0 |
| Final review -- Holistic (SE+DE) | 0 | 0 | 0 |
| Codex iteration 3 | 3 | 3 | 0 |
| **Total** | **~30** | **~28** | **2** |

- 2026-03-24: Dispatch completed. Both stories implemented by SE. Per-story CR (E-152-01: APPROVED round 1; E-152-02: NOT APPROVED round 1, APPROVED round 2 after 3 fixes). Holistic team review #1: clean. CR integration review: APPROVED. Holistic team review #2: 1 SHOULD FIX (gc_uuid lookup guard), remediated. Codex code review: 1 finding dismissed (pipeline ordering is correct as implemented). Epic COMPLETED.

### Dispatch Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-152-01 | 2 | 0 | 2 |
| Per-story CR -- E-152-02 | 3 | 3 | 0 |
| Holistic team review #1 | 0 | 0 | 0 |
| CR integration review | 0 | 0 | 0 |
| Holistic team review #2 | 1 | 1 | 0 |
| Codex code review | 1 | 0 | 1 |
| **Total** | **7** | **4** | **3** |

### Context-Layer Assessment
- New agent definition: NO
- New/modified rule: NO
- New/modified skill: NO
- New/modified hook: NO
- CLAUDE.md update needed: YES -- `run_member_sync()` behavioral change (now runs opponent discovery). Add to Architecture section under "Pipeline caller convention" or "Background pipeline trigger" noting that `run_member_sync` now includes opponent discovery (seeder + resolver).
- Agent memory update: NO (PM memory update handled separately at Step 10)

### Documentation Assessment
No documentation triggers fired. New internal pipeline code only -- no user-facing changes, no new CLI commands, no API endpoint changes, no admin UI changes.
