# E-229: Plays in `bb data scout` parity

## Status
`COMPLETED`

## Overview
Wire plays crawl + load + reconcile into `bb data scout` (CLI) and `run_scouting_sync` (web) so both paths produce equivalent data artifacts after their post-spray dedup sweep. Today, the standalone reports flow patches around this by running plays inline at report-generation time -- meaning dashboards see stats with plays-derived signals (FPS%, QAB%, pitches-per-PA -- all defined in `.claude/rules/key-metrics.md`) missing or stale. After this epic, scouting-pipeline-parity is restored as the canonical contract per CLAUDE.md, and the inline duplicate in `src/reports/generator.py` is deleted.

## Background & Context
The scouting-pipeline-parity invariant in CLAUDE.md is currently violated: both `run_scouting_sync` (web, `src/pipeline/trigger.py`) and `_scout_live` (CLI, `src/cli/data.py`) skip plays crawl/load post-spray. The standalone reports flow patches around this in `src/reports/generator.py:524-643` (private `_crawl_and_load_plays`) and the inline call at `src/reports/generator.py:1091-1110`. Once this epic ships, the report-time duplicate is deleted and replaced with a call to the new shared helper.

This epic was originally story **E-228-02** ("Wire plays into `bb data scout` -- CLI + web parity") inside the matchup strategy report epic. During E-228 v1 refinement (2026-04-28), it was split into its own epic because the parity invariant has independent value beyond matchup and a cleaner agent fit (data-engineer + software-engineer working on pipeline orchestration). E-229 is **independent of E-228 v1**; it ships on its own value (scout-pipeline hygiene + dashboard parity).

**Discovery decisions locked (from E-228 planning 2026-04-27 + E-229 planning 2026-04-29):**
- **Shared helper `src/gamechanger/pipelines/plays_stage.py`**: crawls plays + loads + invokes `reconcile_game()` per game in scout result. Reused by `_scout_live`, `run_scouting_sync`, AND the report generator -- the parity invariant is encoded by all three paths invoking the same helper with equivalent inputs.
- **Whole-game idempotency** is already enforced by the plays loader's `SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1` per perspective-provenance rule. The shared helper does NOT add an outer idempotency check; it relies on the loader's per-game gate. Re-running scout is safe.
- **Auth-expiry handling**: shared helper catches `CredentialExpiredError` internally and returns `auth_expired=True` in `PlaysStageResult.deferred_game_ids`. Both CLI and web wrappers log a warning and continue -- plays auth-expiry is non-fatal in BOTH paths. The CLI's existing spray re-raise pattern (`src/cli/data.py:337-338`) is documented as a known inconsistency but explicitly out of scope for E-229.
- **`crawl_jobs` step counters**: deferred. No schema change. Helper returns a `PlaysStageResult` dataclass; CLI uses typer.echo + scouting_runs (no `crawl_jobs` write); web logs at INFO and prefixes `crawl_jobs.error_message` on partial failure with a structured plays-stage summary.
- **Sequencing**: plays slots after step 5 (post-spray dedup sweep) in both paths. Plays follows spray's additive-enrichment pattern in the web path -- the pre-existing timing oddity (`_mark_job_terminal('completed')` written at lines 727-728 before spray and dedup run) is preserved as-is. Fixing that timing oddity was opportunistic scope per the SE Y2 retraction (see History entry); captured as a follow-up idea instead.
- **`game_perspectives` upstream invariant**: `PlaysLoader._load_game()` does not currently INSERT into `game_perspectives` after a successful load (verified 2026-04-29 -- the only writer is `src/gamechanger/loaders/game_loader.py:640-647`). Per DE Q3, this is fine for E-229 because in all three caller paths (CLI scout, web scout, report generator) the boxscore load runs BEFORE the plays stage, so `game_perspectives` is populated for every game by the time the plays helper runs. The shared helper does NOT itself write to `game_perspectives` -- doing so would widen the helper from orchestration into loader-internal behavior. Migrating the INSERT into `PlaysLoader._load_game()` itself is captured as a separate idea (the standalone `bb data load --loader plays` path retains the gap until that idea ships).

**Promotion trigger**: Independent of E-228 v1; ships on its own value (scout-pipeline hygiene + dashboard parity). Ready to plan immediately.

## Goals
- Both `_scout_live` (CLI) and `run_scouting_sync` (web) crawl + load + reconcile plays for every game in the scout result, after the post-spray dedup sweep, via the shared helper.
- The shared helper `src/gamechanger/pipelines/plays_stage.py` is the single point of pipeline orchestration; CLI scout, web scout, and the report generator all invoke it with equivalent inputs.
- The standalone reports flow's inline plays load (`_crawl_and_load_plays` and the call site at lines 1091-1110) is deleted -- one mechanism, not three.
- Dashboards see fresh plays-derived signals (FPS%, QAB%, pitches-per-PA -- all defined in `.claude/rules/key-metrics.md` and surfaced today by `_query_plays_pitching_stats`/`_query_plays_batting_stats` in `src/reports/generator.py`) for tracked opponents without requiring a separate report run.
- The scouting-pipeline-parity invariant for plays is encoded as an executable test (`tests/test_scout_plays_parity.py`).

## Non-Goals
- Refactoring `PlaysLoader` to accept in-memory dicts (eliminating the tempdir hack the helper inherits from the existing report flow). Captured as an idea for a follow-up epic.
- Adding `crawl_jobs` step counter columns or a `step_summary` JSON blob. Captured as an idea if operator UX surfaces a need.
- Fixing the CLI's pre-existing `CredentialExpiredError` re-raise pattern from spray (`src/cli/data.py:337-338`). Documented as a known inconsistency; out of scope for E-229.
- Migrating the `game_perspectives` INSERT into `PlaysLoader._load_game()` itself. In all E-229 caller paths the upstream boxscore load (`src/gamechanger/loaders/game_loader.py:640-647`) populates `game_perspectives` before plays runs, so the new code paths are unaffected. The standalone `bb data load --loader plays` path retains the gap until a separate idea ships. Captured as an idea per DE Q3 recommendation.
- Schema changes to `plays`, `play_events`, `crawl_jobs`, or `game_perspectives`.
- Backfilling plays for already-scouted teams (separate operator command, not pipeline scope).
- Web/CLI feature parity beyond plays (other parity gaps tracked separately).

## Success Criteria
- After `bb data scout <team_id>` completes for any tracked opponent, the `plays` table has rows for every game in the opponent's recent schedule that the GC API exposes plays for. (`game_perspectives` is populated by the upstream scouting load via `game_loader.py`; not the responsibility of the plays helper.)
- After `run_scouting_sync` completes for the same team, the same outcome holds.
- The `tests/test_scout_plays_parity.py` test passes -- the parity invariant is encoded as an executable test.
- The `_crawl_and_load_plays` private function in `src/reports/generator.py` no longer exists; the report generator invokes the shared helper.
- Auth expiry mid-scout does NOT crash the scout in either path; plays loaded before expiry are persisted; remaining plays are deferred and the operator gets a clear warning.
- Re-running scout on a team with already-loaded plays is a no-op for the plays stage (whole-game idempotency).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|--------------|----------|
| E-229-01 | Implement `run_plays_stage` shared helper module | DONE | -- | software-engineer |
| E-229-02 | Wire `run_plays_stage` into `_scout_live` (CLI) | DONE | E-229-01 | software-engineer |
| E-229-03 | Wire `run_plays_stage` into `run_scouting_sync` (web) | DONE | E-229-01 | software-engineer |
| E-229-04 | Migrate report generator to `run_plays_stage`; delete `_crawl_and_load_plays` | DONE | E-229-01 | software-engineer |
| E-229-05 | Parity-invariant test `test_scout_plays_parity.py` | DONE | E-229-01, E-229-02, E-229-03 | software-engineer |

## Dispatch Team
- software-engineer
- data-engineer

(DE owns no migration work in this epic per Q3 decision; remains on the team as advisory consultant for any reviewer-flagged schema concerns and for closure-time perspective-provenance review.)

## Technical Notes

### One mechanism, not three options
The framing question of "deprecate / keep / hybrid the report-time inline plays load" collapses to one mechanism: a shared helper with whole-game idempotency in the loader. Three callers invoke it; the helper does the right thing for each:
- CLI scout (E-229-02): full crawl/load/reconcile after dedup; idempotent on rerun.
- Web scout (E-229-03): same, plus Y2 status-timing fix.
- Report generator (E-229-04): same call shape; cheap when scout has already loaded plays for a tracked team, full work for non-tracked-team reports.

There is no separate "report-time inline" path after this epic. The private `_crawl_and_load_plays` in `src/reports/generator.py` is deleted.

### Shared helper signature
File: `src/gamechanger/pipelines/plays_stage.py`. New package; `__init__.py` may re-export `run_plays_stage` and `PlaysStageResult` for clean imports.

Field-name convention: bare names matching `LoadResult`'s style (`loaded`, `skipped`, `errors`); `attempted` aligns with this convention. **Field order matters** -- defaulted fields (`deferred_game_ids` with `default_factory=list`) MUST appear AFTER non-defaulted fields per Python dataclass rules. Reordering for "readability" without preserving this rule will raise a `TypeError` at class definition time.

```python
from dataclasses import dataclass, field

@dataclass
class PlaysStageResult:
    attempted: int
    loaded: int
    skipped: int
    errored: int
    reconcile_errors: int
    auth_expired: bool
    deferred_game_ids: list[str] = field(default_factory=list)

def run_plays_stage(
    client: GameChangerClient,
    conn: sqlite3.Connection,
    *,
    perspective_team_id: int,
    public_id: str,
    game_ids: list[str],
) -> PlaysStageResult:
    ...
```

Internals:
1. For each `game_id` in `game_ids`: HTTP fetch `/game-stream-processing/{game_id}/plays` with the existing `_PLAYS_ACCEPT` header (`application/vnd.gc.com.event_plays+json; version=0.0.0`). Pre-fetch DB skip (`SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1`) avoids redundant HTTP traffic on rerun.
2. Catch `CredentialExpiredError`: stop iteration, set `auth_expired=True`, append remaining game_ids to `deferred_game_ids`, break to load step with whatever was fetched.
3. Catch any other `Exception` per game during HTTP fetch: log WARNING with `exc_info=True`, increment `errored`, continue.
4. Write fetched JSON to `tempfile.TemporaryDirectory()` as `{game_id}.json`.
5. Instantiate `PlaysLoader(conn, owned_team_ref=TeamRef(id=perspective_team_id, gc_uuid=None, public_id=public_id))` and call `loader.load_all(tmp_dir)`.
6. **LoadResult mapping**: the loader returns aggregate `LoadResult(loaded, skipped, errors)`. `LoadResult.loaded` is a sum of plays inserted (record count) and is NOT mapped onto `PlaysStageResult.loaded` directly -- the helper computes its own `loaded` as a games count from a post-load DB probe (see step 7). `LoadResult.skipped` is added to `PlaysStageResult.skipped`, and pre-fetch-skipped games (already-loaded games detected before the HTTP call) are also folded into `PlaysStageResult.skipped`. Loader-reported errors (`LoadResult.errors`) are ADDED to `PlaysStageResult.errored` (which has already been incremented for HTTP-fetch failures in step 3). Loader errors and HTTP errors aggregate into the same field.
7. **Loaded-games selection + reconcile selection (post-load DB probe)**: `LoadResult` is aggregate -- it does not expose per-game outcomes. After `load_all()` returns, the helper performs a per-game DB probe (`SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1`) over `plays_data.keys()` -- the games actually fetched this run, EXCLUDING pre-fetch-skipped games. The set of game_ids whose probe returns a row is the loaded set; `PlaysStageResult.loaded = len(loaded_game_ids)` (games count, matching the operator-facing format `"plays: {loaded}/{attempted} loaded"`). The helper then iterates the same loaded set and calls `reconcile_game(conn, game_id, dry_run=False, perspective_team_id=perspective_team_id)` per game. Catch any reconcile exception per game; log WARNING; increment `reconcile_errors`. Continue. Pre-fetch-skipped, deferred, and HTTP-errored games are already excluded from the loaded set because they never appear in `plays_data`.
8. Return the populated `PlaysStageResult`. The helper does NOT write to `game_perspectives` -- see "`game_perspectives` upstream invariant" section below.

### Parameter naming
The perspective-tagging argument is named `perspective_team_id`, NOT `team_id`. Per DE Q2 footgun-prevention: inside the helper, this value flows into `PlaysLoader(owned_team_ref=...)` AND into `reconcile_game(perspective_team_id=...)`. Naming it `perspective_team_id` at the helper boundary forces correct caller mental model and matches the perspective-provenance MUST constraint terminology. Callers (CLI, web, report generator) hold the scouted team's `teams.id` in a local variable typically named `team_id` and pass it as the keyword argument: `run_plays_stage(..., perspective_team_id=team_id, ...)`.

### Helper docstring invariants
The helper's docstring MUST document four caller invariants:
1. **`PRAGMA foreign_keys=ON` is the caller's responsibility.** The helper does NOT silently set it. A defensive helper-side `PRAGMA foreign_keys=ON` would mask caller bugs by silently turning the FK enforcement on for connections that should have had it from the start.
2. **The helper does NOT close the connection.** Caller owns the connection lifecycle. Spray-stage pattern (`_run_spray_stages`) is the precedent.
3. **`game_perspectives` rows for every input `game_id` MUST already be present.** The helper assumes upstream boxscore load has populated `game_perspectives` (via `src/gamechanger/loaders/game_loader.py:640-647`). Callers that bypass boxscore load -- if any exist outside the standard scout pipeline -- will produce `plays` rows tagged with a perspective that is NOT yet recorded in `game_perspectives`, breaking perspective-provenance MUST #5 for that path.
4. **Pass a clean connection.** The first per-game `PlaysLoader.commit()` will commit any uncommitted writes from earlier scout steps (e.g., dedup). In current code paths this is fine (dedup commits before plays starts), but future callers that pass a dirty connection would have those writes silently committed. The helper does NOT own connection state and cannot guarantee atomicity across stages.

### Idempotency
The helper does NOT add an outer idempotency check. `PlaysLoader._load_game()` already gates on `SELECT 1 FROM plays WHERE game_id = ? AND perspective_team_id = ? LIMIT 1` per perspective-provenance rule (`src/gamechanger/loaders/plays_loader.py:148-156`). The first-run gate is in the loader; the helper aggregates `LoadResult` per game.

The whole-game gate composes correctly with the HTTP fetch: a re-run still issues the HTTP request (no caching at fetch time), but the loader skips the load. To avoid the redundant HTTP fetch on rerun, the helper SHOULD do its own per-game `SELECT 1 ... LIMIT 1` check before calling `client.get(...)` -- this is the existing pattern in `src/reports/generator.py:556-565`. Story E-229-01 implements this. The double-check is cheap and prevents wasted HTTP traffic.

Three idempotency points compose: helper's pre-fetch DB check, loader's pre-insert DB check, reconcile's perspective-aware idempotency. The unit test in E-229-01 AC-6 exercises the full composition (zero HTTP, zero rows, zero reconcile work on second call).

### Connection management
The helper accepts an open `sqlite3.Connection` and does NOT close it. Caller controls lifetime. Per DE Q5:
- Web path: connection opened with `WAL` + `foreign_keys=ON` already (`src/pipeline/trigger.py:682-683`); shared across crawl + load + spray + dedup + plays.
- CLI path: same shape (`src/cli/data.py:284-286`).
- Report path: opened by `get_connection()` per-step today; the helper accepts whichever connection the caller is currently inside.

`PlaysLoader._load_game()` issues per-game `conn.commit()` / `conn.rollback()`. The helper must NOT wrap `BEGIN ... COMMIT` around the per-game loop (would conflict with loader's own transactions). Per-game commits provide error isolation; a batch commit would make auth-expiry mid-scout worse (already-loaded plays would be lost on rollback).

**Subtle gotcha to document in the helper docstring**: the first plays-loader commit will commit any uncommitted writes from earlier scout steps (e.g., dedup). In current code paths this is fine (dedup commits before plays starts), but future callers that pass a dirty connection would have those writes silently committed. The docstring states: "Pass a clean connection -- any uncommitted writes will be committed by the first per-game plays load."

### `game_perspectives` upstream invariant
`PlaysLoader._load_game()` (verified at `src/gamechanger/loaders/plays_loader.py:118-194` on 2026-04-29) does NOT INSERT into `game_perspectives` after a successful load. The only writer is `src/gamechanger/loaders/game_loader.py:640-647`, which writes the row after boxscore load.

**Scope decision (per DE Q3)**: in all three E-229 caller paths (CLI scout, web scout, report generator), the boxscore load runs BEFORE the plays stage. The `game_perspectives` row is therefore already populated by the time the plays helper runs. The helper does NOT itself write to `game_perspectives` -- doing so would widen the helper from orchestration into loader-internal behavior, contrary to the lift-and-shift scope of E-229.

The helper's docstring documents this assumption explicitly (see "Helper docstring invariants"). The standalone `bb data load --loader plays` path (which calls `PlaysLoader.load_all()` directly, bypassing the shared helper) retains the gap. Migrating the INSERT into `PlaysLoader._load_game()` itself would close it everywhere -- captured as a separate idea per DE Q3.

### Auth-error handling
The shared helper catches `CredentialExpiredError` internally. It does NOT re-raise. Behavior:
- The HTTP fetch loop stops at the first `CredentialExpiredError`.
- All games already fetched continue through load + reconcile.
- The remaining game_ids (not yet fetched) are appended to `PlaysStageResult.deferred_game_ids`.
- `PlaysStageResult.auth_expired` is `True`.
- The helper returns normally.

Both CLI and web wrappers receive the same `PlaysStageResult` shape. Each logs a WARNING line per "Operator visibility" rules below:
- CLI: typer.echo summary with per-team prefix `Plays stage for {public_id}:` plus the auth-expiry append clause `-- run \`bb creds setup web\` to refresh credentials and re-run scout (re-running scout is idempotent)`.
- Web: `logger.warning("Plays stage: auth expired; %d games deferred for team_id=%d", len(deferred), team_id)` and structure the deferred count into `crawl_jobs.error_message` per "Operator visibility" rule below.

Both paths continue to scout completion (CLI exits per existing exit_code logic; web marks `crawl_jobs.status='completed'`). Plays auth-expiry is non-fatal in BOTH paths.

**Auth-error parity gap (documented, not fixed)**: the CLI's existing `_scout_live` re-raises `CredentialExpiredError` from spray crawl (`src/cli/data.py:337-338`), crashing the CLI before dedup runs. This is inconsistent with the web path (which catches and continues) and inconsistent with this epic's plays helper contract. E-229 does NOT fix the spray re-raise -- scope discipline. Captured as an idea for a future cleanup; the right pattern is "catch and report" everywhere (matching this epic's plays helper).

### Web path sequencing (additive enrichment)
The plays stage slots into `run_scouting_sync` after the post-spray dedup sweep at line 737-750. The web path's existing terminal status writes at lines 727-728 (`_mark_job_terminal('completed')` and `_update_last_synced`) are NOT moved -- plays follows spray's established additive-enrichment pattern. The pre-existing timing oddity (status marked `completed` before spray/dedup/plays run) is preserved as-is; fixing it was opportunistic scope per the SE Y2 retraction (see History) and is captured as a follow-up idea (#6) in E-229-05 AC-10.

The early-return failure path at lines 705-707 ("crawl_result.errors > 0 and games_crawled == 0") is preserved -- it correctly marks the job `failed` before any of the additive stages run.

Plays errors do NOT change the terminal status. The wrapper UPDATEs `crawl_jobs.error_message` directly when plays returns non-clean (per "Operator visibility" below). The structured prefix in `error_message` records the partial failure for operator visibility.

### Game ID sourcing
Game IDs come from `crawl_result.boxscores.keys()` -- the in-memory crawl result from `ScoutingCrawler.scout_team()`. NOT from filesystem globs (legacy path), NOT from a separate DB query. The in-memory pattern matches the existing report generator (`src/reports/generator.py:1097`) and scouting-pipeline in-memory invariant per `.claude/rules/architecture-subsystems.md`.

**Sort mandate**: all three call sites (CLI scout, web scout, report generator) MUST pass `sorted(crawl_result.boxscores.keys())` -- not the raw unordered key view. Determinism is required for the parity test (E-229-05) to compare row sets reliably and for fixture-friendly test stability. The existing report generator already uses `sorted(...)`; CLI and web call sites adopt the same.

**Game ID semantics**: the value in `crawl_result.boxscores.keys()` is the `id` field returned by `GET /public/teams/{public_id}/games`. This is the working pattern the report flow already uses against the plays endpoint (`GET /game-stream-processing/{event_id}/plays`) -- both endpoints accept this value. Per `.claude/rules/perspective-provenance.md`, this value is perspective-specific (the same real-world game scouted from team A's perspective vs. team B's perspective produces two distinct values). Plays loaded from the scouted-opponent perspective are tagged with the opponent's `teams.id` as `perspective_team_id`, so cross-perspective collisions on `plays(game_id, perspective_team_id, play_order)` are prevented by the UNIQUE constraint at `migrations/001_initial_schema.sql`.

For multi-team scouts (CLI bulk mode), iterate per-team `crawl_result` in the existing scout loop and pass each team's `sorted(boxscores.keys())` to its own `run_plays_stage` call.

### Operator visibility
**CLI (E-229-02)**: typer.echo summary line after each per-team helper return (per-team prefix supports bulk-mode disambiguation):
```
Plays stage for {public_id}: loaded={loaded} skipped={skipped} errored={errored} reconcile_errors={reconcile_errors} deferred={len(deferred_game_ids)}
```
On auth-expiry, append: ` -- run `bb creds setup web` to refresh credentials and re-run scout (re-running scout is idempotent)`.

**Web (E-229-03)**: `logger.info` summary line after the helper returns. Plus, when `errored > 0` or `len(deferred_game_ids) > 0`, format a structured prefix per the rule below and execute `UPDATE crawl_jobs SET error_message = ? WHERE id = ?` directly. (The existing flow already wrote `error_message=None` via `_mark_job_terminal(... "completed", None)` at line 727 BEFORE plays ran -- per the Y2 retraction, that ordering is preserved; the wrapper's plays-failure surface is a follow-on `error_message` UPDATE, not a re-call of `_mark_job_terminal`.)

**Format-string rule (applies to web `crawl_jobs.error_message` prefix ONLY; CLI auth-expiry uses the literal append string above)**: comma-joined fragments. The base fragment is always `"plays: {loaded}/{attempted} loaded"`. Append `, {errored} errored` if `errored > 0`. Append `, {reconcile_errors} reconcile errors` if `reconcile_errors > 0` (per Codex-F6 -- a reconcile-only failure means the boxscore vs plays didn't agree; coaching-value signal that operators should see). Append `, {N} deferred (auth)` if `len(deferred_game_ids) > 0`. Multiple fragments appear in this order: errored, reconcile_errors, deferred. Examples:
- Clean: no prefix; `error_message=None` on web.
- Partial failure (load): `"plays: 12/14 loaded, 2 errored"`.
- Reconcile-only failure: `"plays: 14/14 loaded, 3 reconcile errors"`.
- Auth expiry: `"plays: 12/14 loaded, 2 deferred (auth)"`.
- All three: `"plays: 8/14 loaded, 2 errored, 2 reconcile errors, 2 deferred (auth)"`.

**CLI vs. web format split**: the CLI's `typer.echo` summary line already surfaces every counter (`loaded`, `skipped`, `errored`, `reconcile_errors`, `deferred`) in `key=value` form, so the auth-expiry append does NOT re-emit a fragment body -- it appends only the actionable operator message (`bb creds setup web` + idempotency reassurance). The web wrapper has no equivalent verbose surface (logs are operator-readable but `crawl_jobs.error_message` is the durable record), so the fragment format is the durable summary on that path. When the helper result is fully clean (all loaded, none deferred, none errored), the web wrapper issues no `error_message` UPDATE -- the existing `error_message=None` (set by `_mark_job_terminal` at line 727) stands. The CLI emits no auth-expiry append.

**Spray/dedup edge**: spray and post-spray dedup pre-existing silent-swallow behavior is unchanged -- those errors do NOT contribute to the `error_message`. Only the plays-stage portion is included in the structured prefix.

**Report (E-229-04)**: `logger.info` summary line. Reports do not write to `crawl_jobs`; `error_message` formatting is unused.

### Test fixtures (factored into `tests/conftest.py`)
Per SE Q2 + DE Q2:
1. `mock_gc_client_with_plays` -- `MagicMock` `GameChangerClient` whose `.get(...)` returns canned plays JSON for known game_ids. Used by helper unit tests, CLI tests, web tests, parity test.
2. `seed_boxscore_for_plays` -- DB seed: minimum `games` row + `player_game_pitching` rows the reconciler needs as boxscore reference (rows include populated `appearance_order` column). Extracts the union from `tests/test_plays_loader.py` and `tests/test_reconciliation.py`.
3. `plays_json_factory(game_id, pitcher_id, batter_id, num_plays)` -- minimum plays JSON shape that `PlaysParser` accepts.
4. `seed_scout_result_skeleton` -- minimal in-memory `ScoutingCrawlResult` with `boxscores` keyed by `game_id`. Drives the parity test from one fixture.

### Test data sourcing
Per DE Q2 #1: mock plays JSON shape MUST be sourced from `docs/api/endpoints/get-game-stream-processing-event_id-plays.md` -- not hand-rolled. Test-validates-spec rule per `.claude/rules/testing.md`. Where the existing tests use shapes that don't match the endpoint doc, normalize them; do NOT mirror buggy-implementation shapes.

Per DE Q2 #2: fixture game IDs MUST be real `event_id` strings, not `game_stream_id`. Plays endpoint takes `event_id` as the path parameter.

Per DE Q2 #3: `games` rows MUST be seeded BEFORE the loader runs. The loader's FK guard (`src/gamechanger/loaders/plays_loader.py:138-142`) returns `LoadResult(skipped=1)` if the game row is missing -- a parity test that doesn't seed `games` would falsely pass.

### Boxscore seed (parity test specifically)
Per DE Q2 #4 + 2026-04-29 incorporation-time code verification: `reconcile_game` reads pitcher appearance order from `player_game_pitching.appearance_order` -- a DB column populated by the game loader from boxscore JSON during the upstream scouting load (`src/reconciliation/engine.py::_extract_pitcher_order` is a DB query, NOT a file read). The reconcile engine does NOT itself read boxscore JSON files; it relies on the column being populated by upstream stages.

For the parity test (E-229-05): the test seeds `player_game_pitching` rows with `appearance_order` populated via the `seed_boxscore_for_plays` fixture (signature in story 01 Handoff Context). Both paths see the same DB-stored ordering and produce identical reconcile output. No JSON file seed is needed.

The original DE finding correctly flagged that without proper boxscore-derived data, BF correction can't run and discrepancies diverge -- the resolution is DB-column seeding, not filesystem seeding. (The fixture signature in story 01 reflects this: it accepts `pitcher_appearances` and writes the rows directly.)

### Same `perspective_team_id`
Per DE Q2 #5: parity test uses a single seeded `teams.id` value on BOTH paths -- assert equality on `perspective_team_id` columns in the parity comparison.

### Parity assertion (E-229-05 specifically)
Per DE Q4 + Q2 #6. All column names below are pinned against the schema in `migrations/001_initial_schema.sql` (`plays`, `play_events`, `reconciliation_discrepancies` table definitions):
- `plays`: compare on `(game_id, perspective_team_id, play_order, batter_id, pitcher_id, outcome, is_first_pitch_strike, is_qab, pitch_count)`. Exclude `created_at`, autoincrement `id`.
- `play_events`: join to `plays` via natural key `(game_id, perspective_team_id, play_order, event_order)`. Compare `(event_type, pitch_result, is_first_pitch)`. NEVER compare on autoincrement `play_id`.
- `reconciliation_discrepancies`: compare on `(game_id, perspective_team_id, team_id, player_id, signal_name, category, boxscore_value, plays_value)`. Exclude `run_id` (UUID per run), `created_at`, autoincrement `id`.
- Use a clock fixture (freezegun) or strip timestamps before comparison.

**DB isolation**: per-test tmp_path SQLite files (NOT `:memory:` -- see E-229-05 AC-7). `:memory:` is per-connection and cannot be shared across two pipeline invocations. The test monkeypatches `_resolve_db_path` (CLI) and `get_db_path` (web) to return distinct tmp_path locations per run.

### Error-path testing
Per `.claude/rules/testing.md` and SE Q6 N6: each per-path test file (CLI E-229-02, web E-229-03) MUST include at least one test where the helper fails (raises an unexpected exception) and the caller still completes successfully (CLI exits 0, web stays `completed`). This encodes the additive-enrichment pattern in tests.

### Auth-expiry operator UX
Per SE Q5 + DE-acknowledged: when `PlaysStageResult.auth_expired = True`, the operator-facing message must:
1. Name the count of deferred games.
2. State the actionable command: `bb creds setup web`.
3. Confirm that re-running scout is safe (idempotent).

Both CLI typer.echo and web logger.warning include this language.

## Closure Tasks (PM-owned)

Before this epic can be marked `COMPLETED` and archived, the PM MUST file the following six follow-up ideas in `/.project/ideas/` per `.claude/rules/ideas-workflow.md`. These ideas surfaced during E-229 planning and review but are out of scope for the epic itself. Each idea is filed as `IDEA-NNN-short-slug.md` (next available number from PM memory), indexed in `/.project/ideas/README.md`, and the PM memory file is bumped with the new next-available number.

1. **`PlaysLoader` in-memory refactor** -- accept `dict[game_id, raw_json]` directly instead of reading from a tempdir; eliminates the tempdir hack the helper inherits from the existing report flow. Also covers cleaning up the `LoadResult.skipped` semantic conflation between idempotency-hit and FK-guard-skip outcomes (currently a single counter that conflates two distinct meanings).
2. **`PlaysLoader._load_game()` writes to `game_perspectives`** -- after a successful load, INSERT OR IGNORE the `(game_id, perspective_team_id)` row. Closes the gap for the standalone `bb data load --loader plays` path. The E-229 caller paths (CLI scout, web scout, report generator) are unaffected because upstream boxscore load already populates `game_perspectives` via `game_loader.py:640-647`.
3. **Optional `run_id` clustering on `reconciliation_discrepancies`** -- so all rows from one scout invocation share a UUID. Mirrors `reconcile_all`'s pattern at `src/reconciliation/engine.py:451`. Coaching-value question: do operators want to filter discrepancies by scout run?
4. **CLI `_scout_live` catches and reports `CredentialExpiredError` from spray** -- instead of re-raising at `src/cli/data.py:337-338`. Today's CLI crashes mid-scout on auth expiry; web path catches and continues. Parity fix to bring CLI in line with web and with this epic's plays helper contract.
5. **`crawl_jobs.games_crawled` cleanup** -- the column exists in `migrations/001_initial_schema.sql` but no code path writes to it (verified during E-229 iter-1 review). Either define semantics and start writing it, or drop the column in a future migration.
6. **Fix `crawl_jobs.status='completed'` timing in `run_scouting_sync`** -- today the terminal status writes happen at lines 727-728 BEFORE spray, dedup, and (post-E-229) plays additive-enrichment stages run. Move `_mark_job_terminal('completed')` and `_update_last_synced` to AFTER all enrichment stages so the row's status reflects actual pipeline completion. (E-229 retracted this fix per SE's revised analysis -- captured here as a future cleanup.)

Each filed idea includes a one-paragraph summary of the trigger and the user value, plus a "Review by" date 90 days from filing. Files modified during PM closure:
- `/.project/ideas/IDEA-NNN-*.md` (new -- six idea files)
- `/.project/ideas/README.md` (modify -- six new index rows)
- `/.claude/agent-memory/product-manager/MEMORY.md` (modify -- bump next available idea number)

This is PM closure work, not SE story work, per `.claude/rules/agent-routing.md` (agent-memory and ideas are PM-owned).

## Open Questions
All resolved during 2026-04-29 planning -- see History.

## Promotion Triggers
This epic is **immediately plannable**. No external trigger needs to clear:
- Independent of E-228 v1.
- Independent of any GC API changes.
- All discovery decisions locked.

**Independent of E-228 v1**: E-228 v1 consumes only opponent-side plays, which the existing inline patch at `src/reports/generator.py:1091` already loads before the query/render phase. LSB-side plays are not consumed by v1. E-229 is independently valuable scout-pipeline hygiene; if E-229 ships first, the inline patch becomes redundant (cleanup work in E-229-04). If E-228 v1 ships first, the inline patch stays in place until E-229 lands.

## History
- 2026-04-28: Created as DRAFT stub during E-228 v1 refinement. Discovery context preserved from E-228 planning sessions (2026-04-27 -- baseball-coach, api-scout, software-engineer, data-engineer consultations). Originally scoped as story E-228-02 inside the matchup epic; promoted to its own epic because the parity invariant has independent value and a cleaner agent fit (data-engineer + software-engineer pipeline work).
- 2026-04-28: Codex pass 5 fix on E-228 -- removed "blocks E-228 v1" claim. E-228 v1 consumes only opponent-side plays (already loaded by the existing inline patch in `src/reports/generator.py:1091`); LSB-side plays are not consumed by v1. E-229 is independent and ships on its own scout-pipeline-hygiene value.
- 2026-04-29: Phase 2 planning complete. PM consulted SE and DE; locked all three Open Questions and additional structural decisions.
  - **Q1 (report-time inline plays load): resolved as "one mechanism, not three options"** -- the shared helper supersedes the report generator's private `_crawl_and_load_plays`. Report generator migrates to call the shared helper; the private function and its inline call site at `src/reports/generator.py:524-643, 1091-1110` are deleted in story E-229-04. SE flagged this as in-scope for E-229 (not deferred) to prevent drift between two implementations.
  - **Q2 (test coverage equivalence): resolved as B (per-path + parity)** -- per-path test files (`tests/test_cli_data_scout_plays.py`, `tests/test_pipeline_scouting_sync_plays.py`) plus a separate parity test (`tests/test_scout_plays_parity.py`). Four shared fixtures factored into `tests/conftest.py`: `mock_gc_client_with_plays`, `seed_boxscore_for_plays`, `plays_json_factory`, `seed_scout_result_skeleton`. Test-data sourcing rules enforced (real `event_id` strings, sanitized real plays JSON, `games` rows seeded before loader, boxscore JSON seeded for reconcile, same `perspective_team_id` on both paths, clock fixture).
  - **Q3 (`crawl_jobs` step counters): resolved as B (defer schema)** -- helper returns a `PlaysStageResult` dataclass; CLI uses typer.echo, web logs at INFO and prefixes `crawl_jobs.error_message` on partial failure. No migration in this epic. DE strongly preferred deferral; SE acknowledged no code-shape blocker.
  - **Q4 (helper signature)**: `perspective_team_id: int` and `public_id: str` flat (no `TeamRef` -- helper does not need `gc_uuid`). No reconcile opt-out for v1. PlaysLoader in-memory refactor OUT of scope (separate idea); tempdir hack stays. Optional `run_id` punted (separate idea if reconcile-clustering becomes a coaching ask). **Parameter rename per DE Q2 footgun-prevention follow-up (2026-04-29 same day)**: helper's perspective-tagging argument is named `perspective_team_id` (not `team_id`) to force correct caller mental model -- the value flows into both `PlaysLoader(owned_team_ref=...)` AND `reconcile_game(perspective_team_id=...)`, and the shared name eliminates "which team_id?" ambiguity at call sites.
  - **Q5 (sequencing): resolved as Y2 (SE recommendation)** -- E-229-03 moves the web path's terminal status writes (`_mark_job_terminal('completed')` + `_update_last_synced`) to AFTER the plays stage, fixing the pre-existing oddity at `src/pipeline/trigger.py:727-728` where status was written before spray + dedup. Plays errors remain non-fatal (additive enrichment).
  - **Auth-error handling**: shared helper catches `CredentialExpiredError` internally and returns `auth_expired=True`. Both CLI and web wrappers log warning and continue. CLI's pre-existing spray re-raise pattern (`src/cli/data.py:337-338`) is documented as a known inconsistency but explicitly OUT of scope for E-229.
  - **`game_perspectives` invariant**: PM verified on 2026-04-29 that `PlaysLoader._load_game()` does NOT INSERT into `game_perspectives`; only `game_loader.py:640-647` does. **Initial scope decision** had the shared helper perform the `INSERT OR IGNORE` per loaded game. **DE Q3 follow-up (2026-04-29 same day) overrode this**: in all three E-229 caller paths the boxscore load runs BEFORE plays (so `game_perspectives` is already populated by upstream), and adding loader-internal behavior to an orchestration helper widens scope unnecessarily. Final decision: helper does NOT write to `game_perspectives`; documents the upstream-population assumption in its docstring. Migrating the INSERT into `PlaysLoader._load_game()` itself remains a separate idea (closes the gap for the standalone `bb data load --loader plays` path too).
  - Five stories created (E-229-01 through E-229-05). Status remains DRAFT pending Phase 3 internal review and Phase 4 Codex spec review.
- 2026-04-29: Phase 3 internal review iteration 1 complete. 32 findings consolidated from CR + SE + DE + PM holistic review; 27 ACCEPT (with 2 multi-source merges), 1 ACCEPT-NARROWED, 1 DISMISS (superseded by 2026-04-29 course correction), 1 NO-OP/INFORMATIONAL. Major changes incorporated:
  - Filename corrections: `tests/test_reconciliation_engine.py` → `tests/test_reconciliation.py`; `tests/test_reports_generator.py` → `tests/test_report_generator.py`; `tests/test_pipeline_trigger.py` → `tests/test_trigger.py`.
  - `LoadResult` mapping clarified: loader-reported errors are added to `PlaysStageResult.errored` (which has already been incremented for HTTP-fetch failures); loader returns aggregate result, so reconcile selection uses post-load DB probe per game.
  - Bulk-mode iteration explicitly captured: Story E-229-02 AC-1 reworded to iterate `crawl_results` per-team; new AC-9 added for bulk-mode E2E test.
  - Helper-raises-unexpected-exception test scenarios added to E-229-02 AC-8 and E-229-03 AC-9.
  - Story 04 dead-code removal: `except CredentialExpiredError` block at `src/reports/generator.py:1099-1110` is now explicitly DELETED (not preserved); only `except Exception` retained as defensive wrapper. Story 04 description tightened: "private function deleted; inline call site REPLACED by shared-helper call wrapped in `except Exception`-only defensive envelope."
  - `_PLAYS_ACCEPT` constant: defined module-private inside `src/gamechanger/pipelines/plays_stage.py` (story 01); explicitly deleted from `src/reports/generator.py:57` (story 04).
  - Parity-test fixes: parity test uses per-test tmp_path SQLite files (NOT `:memory:`); parity assertion column-set pinned against `migrations/001_initial_schema.sql`; the reconcile-engine boxscore source is the `player_game_pitching.appearance_order` DB column (verified via code reading -- NOT a JSON file as the original Tech Notes implied), so the parity test seeds via the `seed_boxscore_for_plays` fixture rather than seeding files.
  - Game ID sourcing: all three call sites use `sorted(crawl_result.boxscores.keys())` for determinism. Tech Notes "Game ID sourcing" section adds rationale for the perspective-specific `id` value used by both boxscore and plays endpoints.
  - Test mechanism pinning: idempotency-on-rerun test verification (E-229-01 AC-6), status-timing test mechanism (E-229-03 AC-9), monkeypatch invocation test (E-229-04 AC-6).
  - Goals language tightened: "FPS%, count-based outcomes, batted-ball type" → "FPS%, QAB%, pitches-per-PA" (all defined in `.claude/rules/key-metrics.md`).
  - Operator visibility: format-string rule pinned (comma-joined fragments); CLI summary uses per-team prefix `Plays stage for {public_id}: ...` for bulk-mode disambiguation; greppable failure token `PLAYS STAGE FAILED` required in WARNING log lines.
  - Helper docstring invariants: AC expanded from 3 to 4 invariants -- (a) `PRAGMA foreign_keys=ON` is caller's responsibility, (b) helper does NOT close the connection, (c) `game_perspectives` upstream-population is a caller invariant, (d) "pass a clean connection" footgun documented.
  - `PlaysStageResult` field naming: bare convention (`attempted` not `games_attempted`) matching `LoadResult`; field-order note added to Tech Notes warning that defaulted fields must appear after non-defaulted fields per Python dataclass rules.
  - `tests/conftest.py` fixture signatures pinned in Story 01 Handoff Context as a code block.
  - PM P2-4 incorporated as E-229-05 AC-10: closing AC requires four follow-up ideas to be filed before story DONE: (1) `PlaysLoader` in-memory refactor; (2) `PlaysLoader._load_game()` writes `game_perspectives`; (3) optional `run_id` clustering on `reconciliation_discrepancies`; (4) CLI catches+reports `CredentialExpiredError` from spray instead of re-raising. Subsequently expanded to 5 ideas (see next history entry).
  - Status remains DRAFT pending Phase 3 iteration 2 (or, if no further findings, Phase 4 Codex spec review).
- 2026-04-29: DE follow-up Q2 correction post-iter-1 incorporation. Earlier DE assertion that `crawl_jobs.games_crawled` "already exists" was verified narrowly (the column exists in the SQL schema) but DE corrected: NO code path writes to it. The `games_crawled` Python attribute everyone references in `trigger.py`/`cli/data.py`/`crawlers/scouting.py` is a dataclass field on `ScoutingCrawlerResult`/`ScoutingSprayChartResult`, completely separate from the SQL column. This aligns with the locked Q3 disposition (no new schema writes; plays stage adds zero `crawl_jobs` writes). Added a 5th follow-up idea to E-229-05 AC-10: "`crawl_jobs.games_crawled` cleanup -- either start writing with defined semantics or drop the column." DE-flagged `LoadResult.skipped` semantic conflation (idempotency-hit vs FK-guard-skip) folded into idea #1 (PlaysLoader in-memory refactor) since the in-memory refactor is the natural place to clean up loader-result semantics. Status unchanged: DRAFT.
- 2026-04-29: Codex spec review (iter-1) -- 6 findings, 3 P1 + 3 P2, all ACCEPTED. Major changes:
  - **Codex-F1**: AC-10 routing mismatch -- closing AC-10 was assigned to SE-owned story 05 but touched PM-owned files (`/.project/ideas/`, `/.claude/agent-memory/product-manager/`). Resolution: AC-10 removed from story 05; idea-filing requirement moved to a new epic-level "Closure Tasks (PM-owned)" section that enumerates the six follow-up ideas as PM closure work.
  - **Codex-F2**: parity-test monkeypatch seam wrong -- AC-7 originally said patch `src.api.db.get_db_path`, but `src/pipeline/trigger.py:24` imports the symbol into the trigger module; Python import-binding semantics require patching `src.pipeline.trigger.get_db_path` (the imported binding). Existing `tests/test_trigger.py:214` is the canonical pattern. AC-7 + Tech Approach updated; CLI side unchanged (`src.cli.data._resolve_db_path` is the correct seam).
  - **Codex-F3**: AC-10 count drift -- already obsoleted by in-flight 4→5→6 transition (DE follow-up + SE Y2 retraction); resolved by F1's AC-10 split.
  - **Codex-F4**: AC-9 "artificially broken" not bounded -- rewritten as testable contract for a diff-formatter helper. AC-9 now requires the helper + at least three deterministic unit tests (identical row sets, missing row, value mismatch).
  - **Codex-F5**: `tests/test_report_plays.py` missing from E-229-04 Files-to-Modify -- already covered by the in-flight SE follow-up.
  - **Codex-F6**: `reconcile_errors` not surfaced in operator output -- format-string rule + CLI summary template + E-229-02 AC-2 + E-229-03 AC-2 updated to surface `reconcile_errors` alongside `errored` and `deferred`. Reconcile-only failures (boxscore-vs-plays disagreement) are now visible to operators -- coaching-value signal for pitcher attribution accuracy.
- 2026-04-29: SE follow-up post-iter-1 -- **Y2 status-timing fix RETRACTED**. SE's earlier Y2 push (move `_mark_job_terminal('completed')` + `_update_last_synced` from `src/pipeline/trigger.py:727-728` to AFTER all enrichment stages including plays) was retracted by SE on review. Quote: "PM's auth-error proposal is exactly right and I retract my earlier Y2 push... My earlier Y2 (move the status write to the end of all stages) was scope creep. PM's framing -- 'plays follows the additive-enrichment pattern that spray already established' -- keeps the change small. The pre-existing timing oddity (status marked before spray runs today) is not E-229's problem to fix." Team-lead authorized Option A (accept retraction). **Changes applied to revert Y2 incorporation**: removed "Y2 status-timing fix" Tech Notes subsection (replaced with "Web path sequencing (additive enrichment)"); removed Y2 references from epic Goals, Success Criteria, Background discovery decisions, and E-229-03 Description/AC-2/Notes/Files-to-Modify; renamed E-229-03 from "Wire `run_plays_stage` into `run_scouting_sync` (web) + status-timing fix" to "Wire `run_plays_stage` into `run_scouting_sync` (web)"; rewrote E-229-03 ACs to reflect that the web wrapper UPDATEs `crawl_jobs.error_message` directly after plays returns (rather than passing the prefix to `_mark_job_terminal`, which already ran at line 727 in the existing flow). The fix is preserved as follow-up idea #6 in epic Closure Tasks (per Codex-F1 split, idea filing moved out of E-229-05 AC-10 into the epic-level Closure Tasks section). Plus other SE follow-ups: explicit `tests/test_report_plays.py` reference added to E-229-04 AC-7 + Files-to-Modify; test file naming (`test_cli_data_scout_plays.py` vs `test_cli_scout_plays.py`) deferred to implementer per SE recommendation; F-FIELD-NAMING locked Option A (bare names) per SE confirmation, with explicit dataclass docstring requirement added to E-229-01 AC-1 to prevent future renames.

- 2026-04-29: **Status set to READY**. Phase 4 Codex spec review complete; all incorporation deltas applied; consistency sweep clean. Epic ready for user authorization to dispatch.
- 2026-04-29 (during dispatch, between E-229-02 and E-229-03): Tech Notes "Operator visibility" clarified. Original "Format-string rule (applies to CLI auth-expiry append AND web error_message prefix)" parenthetical contradicted the "On auth-expiry, append:" literal which named only the actionable operator message without comma-joined fragments. Code-reviewer flagged the ambiguity after E-229-02 implementation chose the literal reading (CR-approved). PM ruling: **Reading (a) -- format-string rule applies to web `crawl_jobs.error_message` ONLY**; CLI auth-expiry append uses the literal actionable string above. Rationale: the CLI's verbose `key=value` summary line already surfaces every counter the fragment body would name, so adding the fragment to the auth-expiry suffix would duplicate information; the web wrapper has no equivalent verbose surface, so the fragment format is the durable summary on that path. Tech Notes updated; no implementation changes required for E-229-02 (already aligned). E-229-03 inherits the unambiguous spec.
- 2026-04-29: **Epic COMPLETED.** All five stories DONE. Final dispatch produced ~3,200 lines across 20 files (3,199 insertions). Deliverables: shared helper module `src/gamechanger/pipelines/plays_stage.py` with `PlaysStageResult` dataclass + four caller invariants documented; CLI scout (`_scout_live`) wired with bulk-mode iteration + verbose typer.echo summary including `reconcile_errors` (Codex-F6); web scout (`run_scouting_sync`) wired with structured `crawl_jobs.error_message` prefix + `_format_plays_error_message` helper + module-private `_run_plays_stage_for_sync` wrapper; report generator migrated -- `_crawl_and_load_plays` deleted (~120 lines), `_PLAYS_ACCEPT` constant removed, dead `except CredentialExpiredError` block deleted; parity-invariant test `tests/test_scout_plays_parity.py` encodes the CLAUDE.md scouting-pipeline-parity invariant for plays as an executable canary with column subsets pinned against `migrations/001_initial_schema.sql` and a diff-formatter helper. Four shared `tests/conftest.py` fixtures (`mock_gc_client_with_plays`, `seed_boxscore_for_plays`, `plays_json_factory`, `seed_scout_result_skeleton`) consumed by all five new test files.
  - **Closure note (E-229-04 review)**: deletion of `_crawl_and_load_plays` slightly improves auth-expiry behavior in reports -- partial-loaded plays now appear in the report rather than being discarded via `plays_game_ids = []` in the deleted `except CredentialExpiredError` block. The shift is intentional; the contract is unchanged for the clean and full-failure cases. Benign behavioral improvement, not a regression. Flagged by code-reviewer as informational-only during E-229-04 review.
  - **Closure note (out-of-spec change absorbed in E-229-04)**: SE applied a comment-only fix to `src/gamechanger/loaders/scouting_loader.py` to remove a dangling reference to the deleted `_crawl_and_load_plays`. PM approved as tightly-coupled cleanup forced by the deletion (same class as updating `_REMOVED_NAMES` in tests).
  - **Closure note (Tech Notes clarification mid-dispatch)**: between E-229-02 and E-229-03, code-reviewer flagged a Tech Notes ambiguity in the format-string rule scope. PM ruled Reading (a) -- format-string rule applies to web `error_message` ONLY; CLI auth-expiry uses the literal actionable string. Tech Notes updated; no implementation revision required.
  - Six follow-up ideas filed at closure per epic's "Closure Tasks (PM-owned)" section.

### Review Scorecard (Planning)

| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iter 1 -- CR spec audit | 12 | 12 | 0 |
| Internal iter 1 -- Holistic team (PM+SE+DE) | 20 | 19 | 1 |
| Codex iter 1 | 6 | 6 | 0 |
| **Total** | **38** | **37** | **1** |

**Notes**:
- Two multi-source merges: M1 (Story 04 dead-code) unified F-DEADCODE-01 (SE+DE) + PM P1-3; M2 (Story 05 boxscore JSON path) unified F-PARITY-02 (SE) + PM P1-4.
- One ACCEPT-NARROWED: F-LOADRESULT-01 (CR) -- only the reconcile-selection portion accepted; `game_perspectives` portion superseded by 2026-04-29 DE Q3 course correction (helper does NOT write `game_perspectives`).
- One DISMISS: F-LOADRESULT-02 (DE F1) -- the helper-writes-`game_perspectives` framing was superseded by DE's own Q3 course correction earlier in iter-1 (helper out of `game_perspectives`; loader-internal write captured as separate idea).
- One NO-OP/INFORMATIONAL: PM P3-1 (coaching-value gap check) -- documented in triage; no spec change.
- Two material decisions reversed mid-incorporation: SE Y2 retraction (status-timing fix scope creep) and DE Q3 follow-up (helper does NOT write `game_perspectives`). Both captured as follow-up ideas in epic Closure Tasks.
- Codex pass: 6 findings, 3 P1 + 3 P2, all ACCEPT. F1 routing-mismatch led to AC-10 split out of E-229-05 into epic-level Closure Tasks section (PM-owned).

### Review Scorecard (Dispatch)

| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-229-01 | 3 | 2 | 1 |
| Per-story CR -- E-229-02 | 3 | 2 | 1 |
| Per-story CR -- E-229-03 | 3 | 3 | 0 |
| Per-story CR -- E-229-04 | 1 | 0 | 1 |
| Per-story CR -- E-229-05 | 3 | 0 | 3 |
| Step 1a invariant audit | 0 | 0 | 0 |
| **Total** | **13** | **7** | **6** |

**Notes**:
- The "and review" modifier was NOT specified at dispatch, so no Phase 4 (Codex post-dev review) rows.
- Step 1a invariant audit returned **CLEAN** -- zero violations across all five grep audits (PlaysLoader instantiation, `_PLAYS_ACCEPT`, plays-endpoint HTTP, `reconcile_game` calls, `_crawl_and_load_plays` references). The "three callers, one orchestrator" invariant holds across the full codebase. Structural check, not finding-generating.
- E-229-02 Round 1 finding #1 (Tech Notes spec ambiguity) was resolved at the spec layer (PM ruling Reading (a)) rather than in code -- counted as ACCEPT against the spec, not the implementation.
- E-229-04's lone CR SHOULD FIX was framed by CR as "not a regression and not blocking" -- counted as DISMISS (informational only); the underlying behavioral note is captured in the closure entry above.
- E-229-05's three CR SHOULD FIX items were interpretive/cosmetic and explicitly framed as non-blocking -- all dismissed.
