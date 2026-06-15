# E-236-03: Boxscore-crawl honesty + all-blocked failed outcome (#2 + SQ1)

## Epic
[E-236: Report Self-Reporting Integrity Hardening](epic.md)

## Status
`TODO`

## Description
After this story is complete, the run record will carry `boxscores_fetched` and an honest `crawl_status` (`completed`/`partial`/`failed`) derived from boxscores-fetched vs completed-games (M), and the all-boxscores-blocked case (M>0, zero fetched) will produce a hard `failed` outcome instead of silently slipping to `no_games`. This closes finding #2 and the SQ1 product gap.

## Context
`_finalize_crawl` (`scouting.py:220-224`) records `"completed"` whenever `games_crawled != 0`; per-game 403/API failures are `continue`'d (`scouting.py:290-303`). Today an all-blocked team (every boxscore 403s) returns `games_crawled == 0` and the dormant tier-1 fatal gate (`generator.py:1460`) does NOT fire because it keys off an `errors` count that is always 0 — so the report silently proceeds to `no_games`, masquerading "we were blocked" as "no data exists". See epic Technical Notes TN-1, TN-2 (`boxscores_fetched`), TN-6 (the SQ1 decision + default), and TN-7 (use the existing `games_crawled` count; no tuple-arity change).

## Acceptance Criteria
- [ ] **AC-1**: The run record records `boxscores_fetched` (= `ScoutingCrawlResult.games_crawled`, which already exists), and `crawl_status` is derived via `classify_stage_status` from `boxscores_fetched` vs `completed_games` (M), per Technical Notes TN-1/TN-7. No `_fetch_boxscores_in_memory` tuple-arity change is introduced (TN-7).
- [ ] **AC-2**: Given a crawl where some but not all boxscores are fetched (M>0, `0 < boxscores_fetched < M`), when the report generates, then `crawl_status == "partial"`.
- [ ] **AC-3**: Given an all-blocked crawl (M>0, `boxscores_fetched == 0`), when the report generates, then `crawl_status == "failed"`, `overall_status == "failed"`, `GenerationResult.outcome == "failed"`, and the CLI exits non-zero with NO shareable page produced — per the SQ1 resolution in Technical Notes TN-6 (FINAL, Jason signed off 2026-06-14; repairing the dormant fatal gate at `generator.py:1460`).
- [ ] **AC-4**: Given a fully-fetched crawl (`boxscores_fetched == M`, M>0), when the report generates, then `crawl_status == "completed"`.
- [ ] **AC-5**: Given an all-blocked crawl, the FAILURE branch is taken — `crawl_status == "failed"`, `overall_status == "failed"`, `outcome == "failed"` — NOT the no_games branch. (This story asserts only its own all-blocked → failed terminal state. The cross-comparison "failed value ≠ no_games value" requires both terminal values to exist and is asserted in story 05 and the story 08 E2E, where the `no_games` value is set — Codex P1-b; keeps this story self-contained against its blocked-by set.) NOTE (DE F4): a PARTIALLY-blocked crawl (`0 < boxscores_fetched < M`) whose fetched boxscores are all empty can coherently produce `crawl_status == "partial"` AND a `no_games` outcome simultaneously — this is honest (some fetches errored; the ones that succeeded had no data), not a contradiction.
- [ ] **AC-6**: An error-path test (testing.md Error-Path Testing) proves the all-blocked case surfaces as `failed`, not a misleading `no_games` / exit-0.

## Technical Approach
Write `boxscores_fetched` from the existing `crawl_result.games_crawled` to the run record where the crawl stage status is recorded; derive `crawl_status` via the classifier. Repair the tier-1 fatal gate (`generator.py:1460`) so it fires on `games_crawled == 0 AND completed_games > 0`. If the implementer finds `games_crawled` insufficient to express the honest crawl status (TN-7), flag before adding a separate error tally. SQ1 is FINAL (TN-6; Jason signed off 2026-06-14) — implement the `failed` outcome.

## Dependencies
- **Blocked by**: E-236-01, E-236-02
- **Blocks**: E-236-04, E-236-07, E-236-08

## Files to Create or Modify
- `src/reports/generator.py` (modify — run-record crawl-status write, fatal gate at ~1460, no_games-vs-failed branching)
- `src/gamechanger/crawlers/scouting.py` (modify only if needed to surface `games_crawled` to the run-record write; prefer no signature change per TN-7)
- Crawl-stage / fatal-gate tests (modify/add — locate via `grep -rl` per testing.md)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (including the all-blocked error-path test)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
SE S3 + DE D2; PM reconciled to DE's count approach (TN-7). SQ1 = `failed` — FINAL (Jason signed off 2026-06-14, TN-6).
