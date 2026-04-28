# E-229: Plays in `bb data scout` parity

## Status
`DRAFT`

## Overview
Wire plays crawl + load + reconcile into `bb data scout` (CLI) and `run_scouting_sync` (web) so both paths produce equivalent data artifacts after their post-spray dedup sweep. Today, the standalone reports flow patches around this by running plays inline at report-generation time -- meaning dashboards see stats with plays-derived signals (FPS%, count-based outcomes, batted-ball type) missing or stale. After this epic, scouting-pipeline-parity is restored as the canonical contract per CLAUDE.md.

## Background & Context
The scouting-pipeline-parity invariant in CLAUDE.md is currently violated: both `run_scouting_sync` (web, `src/pipeline/trigger.py`) and `_scout_live` (CLI, `src/cli/data.py`) skip plays crawl/load post-spray. The standalone reports flow patches around this in `src/reports/generator.py:1091-1110` (runs plays inline at report time). Once this epic ships, the report-time plays load becomes redundant.

This epic was originally story **E-228-02** ("Wire plays into `bb data scout` -- CLI + web parity") inside the matchup strategy report epic. During E-228 v1 refinement (2026-04-28), it was split into its own epic because the parity invariant has independent value beyond matchup and a cleaner agent fit (data-engineer + software-engineer working on pipeline orchestration). E-229 is **independent of E-228 v1**; it ships on its own value (scout-pipeline hygiene + dashboard parity).

**Discovery decisions locked (from E-228 planning 2026-04-27):**
- **Shared helper `src/gamechanger/pipelines/plays_stage.py`** (per SE-C4): crawls plays + loads + invokes `reconcile_game()` per game in scout result. Reused by both `_scout_live` AND `run_scouting_sync` -- the parity invariant is encoded by both paths invoking the same helper with equivalent inputs.
- **Whole-game idempotency** is already enforced by the plays loader's `SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1` per perspective-provenance rule. Re-running scout is safe.
- **Auth-expiry handling**: mirrors the report-flow pattern (`generator.py:1099-1110`). `CredentialExpiredError` is caught + logged; plays stage is non-fatal to scout overall. The scout completes (with whatever plays were successfully loaded) and the operator gets a clear warning.
- **`crawl_jobs` row** gets new `plays_crawled` / `plays_loaded` step counters OR carries them in existing step counters (implementer judgment during planning).
- **Sequencing**: After step 5 (post-spray dedup sweep) in both paths, before scout marks itself complete.

**Promotion trigger**: Independent of E-228 v1; ships on its own value (scout-pipeline hygiene + dashboard parity). Ready to plan immediately.

## Goals
- Both `_scout_live` (CLI) and `run_scouting_sync` (web) crawl + load + reconcile plays for every game in the scout result, after the post-spray dedup sweep.
- The shared helper `src/gamechanger/pipelines/plays_stage.py` is the single point of pipeline orchestration; both paths invoke it with equivalent inputs.
- The standalone reports flow's inline plays load can be deprecated (plays will already be loaded by the time a report is generated for any tracked opponent) -- but the v1 of this epic decides whether to remove the report-time inline path or keep it as resilience.
- Dashboards see fresh plays-derived signals (FPS%, count-based outcomes, batted-ball type) for tracked opponents without requiring a separate report run.

## Non-Goals
- Refactoring the existing report-time plays load (`src/reports/generator.py:1091-1110`) is decided during planning -- this epic does NOT pre-commit to deprecating it.
- Schema changes to `plays`, `play_events`, or `crawl_jobs` (beyond the new step counters if planning chooses that route).
- Backfilling plays for already-scouted teams (a separate operator command, not pipeline scope).
- Web/CLI feature parity beyond plays (other parity gaps are tracked separately).

## Success Criteria
- After `bb data scout <team_id>` completes for any tracked opponent, the `plays` table has rows for every game in the opponent's recent schedule that the GC API exposes plays for.
- After `run_scouting_sync` completes for the same team, the same outcome holds.
- The `test_cli_and_web_paths_produce_equivalent_artifacts` test (or its equivalent during planning) passes -- the parity invariant is encoded as an executable test.
- Auth expiry mid-scout does NOT crash the scout; plays loaded before expiry are persisted; remaining plays are deferred and the operator gets a clear warning.
- Re-running scout on a team with already-loaded plays is a no-op for the plays stage (whole-game idempotency).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| | To be written during planning | | | |

## Dispatch Team
- software-engineer
- data-engineer

## Technical Notes

### Shared Helper Pattern (Per SE-C4 from E-228 planning)
`src/gamechanger/pipelines/plays_stage.py` exposes a function (final signature TBD during planning) that takes a list of `(game_id, perspective_team_id)` pairs from the scout result and:
1. Crawls plays via `PlaysCrawler` for each pair.
2. Loads plays via `PlaysLoader`.
3. Invokes `reconcile_game(conn, game_id)` per game.

Both `_scout_live` (CLI) and `run_scouting_sync` (web) invoke this helper after step 5 (post-spray dedup sweep). The helper is non-fatal: it logs and continues on per-game failures, returning a summary for the caller to record in `crawl_jobs`.

### Idempotency
Whole-game idempotency is already enforced by `PlaysLoader` via `SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1` (per perspective-provenance rule). Re-running scout on a team with already-loaded plays is a no-op for the plays stage.

### Auth-Expiry Handling
Mirrors the report-flow pattern at `src/reports/generator.py:1099-1110`:
- `CredentialExpiredError` raised during plays crawl is caught.
- Logged as a warning naming the game(s) deferred.
- Plays loaded BEFORE the expiry are persisted.
- Scout completes successfully (with the warning visible to operator).
- Operator's path forward: `bb creds setup web` then re-run scout (idempotent).

### Coordination With Existing Report-Time Plays Load
Today, `src/reports/generator.py:1091-1110` runs plays inline at report-generation time -- this is the patch around the parity gap that this epic closes. Planning must decide:
- **Option A**: Deprecate the report-time inline path. Reports rely on scout having already loaded plays. Pro: single code path. Con: a report generated for an opponent that has not been scouted recently sees stale plays (or none).
- **Option B**: Keep the report-time inline path as resilience. Pro: reports always see fresh plays. Con: dual code paths to maintain.
- **Option C**: Hybrid -- report-time inline runs only if `plays` rows are missing for the opponent's recent games.

Planning chooses one and documents the rationale.

### Test Strategy
Two test files (per existing pattern):
- `tests/test_cli_data_scout_plays.py` -- CLI path: subprocess + in-process tests covering golden path, auth expiry, idempotency, per-game error isolation.
- `tests/test_pipeline_scouting_sync_plays.py` -- web path: same coverage shape.
- A parity-invariant test (e.g., `test_cli_and_web_paths_produce_equivalent_artifacts`) runs both paths against identical fixture inputs and asserts equivalent DB outcomes. This test makes the CLAUDE.md parity invariant executable.

## Open Questions
1. **Deprecate report-time inline plays load OR keep as resilience?** (Coordination With Existing Report-Time Plays Load section above.) Planning decides.
2. **CLI vs web test coverage equivalence**: The web path uses a longer-lived `crawl_jobs` row with rich step tracking; the CLI path is shorter-lived. The test surface should cover both shapes equivalently -- planning decides whether a single shared fixture is sufficient or each path needs its own.
3. **`crawl_jobs` step counters**: New explicit `plays_crawled` / `plays_loaded` columns OR carried in existing counters? Planning decides; the choice has migration implications (may require migration 003 or equivalent next-available number).

## Promotion Triggers
This epic is **immediately plannable**. No external trigger needs to clear:
- Independent of E-228 v1.
- Independent of any GC API changes.
- All discovery decisions locked.

**Independent of E-228 v1**: E-228 v1 consumes only opponent-side plays, which the existing inline patch at `src/reports/generator.py:1091` already loads before the query/render phase. LSB-side plays are not consumed by v1. E-229 is independently valuable scout-pipeline hygiene; if E-229 ships first, the inline patch becomes redundant (cleanup work). If E-228 v1 ships first, the inline patch stays in place until E-229 lands.

## History
- 2026-04-28: Created as DRAFT stub during E-228 v1 refinement. Discovery context preserved from E-228 planning sessions (2026-04-27 -- baseball-coach, api-scout, software-engineer, data-engineer consultations). Originally scoped as story E-228-02 inside the matchup epic; promoted to its own epic because the parity invariant has independent value and a cleaner agent fit (data-engineer + software-engineer pipeline work).
- 2026-04-28: Codex pass 5 fix on E-228 -- removed "blocks E-228 v1" claim. E-228 v1 consumes only opponent-side plays (already loaded by the existing inline patch in `src/reports/generator.py:1091`); LSB-side plays are not consumed by v1. E-229 is independent and ships on its own scout-pipeline-hygiene value.
