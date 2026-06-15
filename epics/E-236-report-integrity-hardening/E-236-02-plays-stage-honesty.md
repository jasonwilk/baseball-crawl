# E-236-02: Plays-stage honesty — thread fetch/load errors into the run record (#1)

## Epic
[E-236: Report Self-Reporting Integrity Hardening](epic.md)

## Status
`TODO`

## Description
After this story is complete, a partial plays load (some games fetched or loaded successfully, others failed) will be recorded as `plays_status="partial"` with a non-NULL `plays_errors` count — not `"completed"` as it is today. Total failure stays `"failed"`; a genuinely-empty plays result stays `"completed"`. This closes finding #1 (HIGH).

## Context
Today per-game plays fetch errors are caught and skipped (`generator.py:807-812`) and `PlaysLoader` returns `LoadResult(errors=N)` without raising (logged at `generator.py:841-844`), but neither is threaded into `_ReconCounts`. `recon.failed` is only set in the outer except (`generator.py:875-881`, total failure), so `_plays_stage` (`generator.py:1712-1735`) writes `"completed"` on partial failure. See epic Technical Notes TN-1 (classifier), TN-2 (the `plays_errors` column), and TN-7 (the threading approach — keep the pinned `list[str]` return).

## Acceptance Criteria
- [ ] **AC-1**: Per-game plays fetch failures and plays load errors are threaded into `_ReconCounts` (new fields) without changing `_crawl_and_load_plays`'s `list[str]` return type, per Technical Notes TN-7.
- [ ] **AC-2**: `_plays_stage` derives `plays_status` from `classify_stage_status` using ERROR-driven inputs per Technical Notes TN-7 (plays): `loaded` = games whose plays fetch did NOT raise (`fetched_ok`); `errors` = fetch failures + `load_result.errors`; `expected` = games ATTEMPTED (`fetched_ok + fetch_failures`). It writes the summed error count to the `plays_errors` run-record column (Technical Notes TN-2). K (`plays_games_covered`, games with plays rows) is a SEPARATE informational coverage number and is NOT used as the classifier's `loaded`.
- [ ] **AC-3**: Given a plays stage where some games' plays fetch/load succeed and at least one ERRORS, when the report generates, then `plays_status == "partial"` and `plays_errors > 0` (was `"completed"` before this story).
- [ ] **AC-4**: Given a total plays failure (the existing `recon.failed` path), when the report generates, then `plays_status == "failed"` (the `recon.failed` signal maps to `"failed"` BEFORE the classifier, per Technical Notes TN-1 precedence — behavior preserved).
- [ ] **AC-5**: Given a plays stage where games are fetched successfully (200) but carry NO plays data and produce ZERO errors (the modal no-scorebook case), when the report generates, then `plays_status == "completed"` — NOT `"partial"`/`"failed"`. This is the key error-driven assertion (the false-alarm the epic must NOT introduce); a unit test MUST cover this fetched-but-empty/zero-error path (story 08's all-403 scenario exercises only the `failed` path — DE F2).
- [ ] **AC-6**: The plays stage stays non-fatal — `CredentialExpiredError` handling and the "continue without plays data" behavior are unchanged; report generation still completes.

## Technical Approach
Add count fields to `_ReconCounts` (`generator.py:92`); populate the fetch-failure count at the `except` block (`generator.py:807-812`, null-guarded) and fold `load_result.errors` (in scope at `generator.py:839-844`) into a load-error field. `_plays_stage` reads them and derives the ERROR-driven classifier inputs (AC-2 / TN-7): there is no direct "games loaded" count at `_plays_stage` time (`_crawl_and_load_plays` returns the input `game_ids` list, and K is computed later in `_query_render_save`), so derive `loaded`/`expected` from the attempted/error counts (e.g. `expected = fetched_ok + fetch_failures`, `loaded = fetched_ok`). Map the `recon.failed` total-failure signal to `"failed"` BEFORE calling the classifier (TN-1 precedence). Follow the E-235 out-parameter pattern. Discover and run all test files that import from the modified modules (testing.md scope discovery).

## Dependencies
- **Blocked by**: E-236-01
- **Blocks**: E-236-03, E-236-07, E-236-08

## Files to Create or Modify
- `src/reports/generator.py` (modify — `_ReconCounts`, `_crawl_and_load_plays`, `_plays_stage`)
- Plays-stage tests (modify/add — locate via `grep -rl` on the modified module per testing.md; likely `tests/test_report_*` covering the plays stage)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (including an error-path test per testing.md Error-Path Testing)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
SE S2. The single `plays_errors` column captures fetch-failures + load-errors summed (DE D2); the two-field split inside `_ReconCounts` is an internal implementation detail.
