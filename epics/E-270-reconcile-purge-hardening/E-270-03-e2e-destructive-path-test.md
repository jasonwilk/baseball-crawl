# E-270-03: True end-to-end destructive-path test (generate_report twice, real ScoutingLoader)

## Epic
[E-270: Harden Reconcile-at-Load and Purge](../E-270-reconcile-purge-hardening/epic.md)

## Status
`TODO`

## Description
After this story is complete, a test will drive `generate_report()` itself twice against a real temporary database — with NO `ScoutingLoader` mock — where the second crawl drops one entry from EACH of the three grains (a game, a player line, a roster entry), and it will assert that each grain's reconcile-at-load retire actually fires (the dropped rows are gone) AND the report still renders successfully. This closes the audit's most serious testing gap: report generation became destructive in E-267, yet no test exercises that destruction through the real generation entry point.

## Context
Every test in `TestGenerateReportE2E` (`tests/test_report_generator.py`) patches `ScoutingLoader` out (`patch("src.reports.generator.ScoutingLoader", ...)`), so the retire path — which lives inside `ScoutingLoader.load_team` — never runs through `generate_report()`. The audit flagged this as annotation-as-coverage: the destructive path is "tested" only at the unit level, never end-to-end. The fix drives the test through the REAL producer (the injected `GameChangerClient`), per the testing.md "drive the test through the real producer" guidance. See epic Technical Notes TN-6 for the injection seam and the mandatory fixture-sizing caveat.

## Acceptance Criteria
- [ ] **AC-1**: A new test (e.g. `TestGenerateReportDestructiveReconcile` in `tests/test_report_generator.py`) drives `generate_report("abc123")` TWICE against a real disk-backed temp DB, patching `src.reports.generator.GameChangerClient` with a fake client (`side_effect=[fake_full, fake_shrunk]`) and keeping `ScoutingCrawler`, `ScoutingLoader`, AND `ensure_team_row_with_provenance` REAL (per the keep-real / patch sets in TN-6). The fake client serves every endpoint the live pipeline calls, including `POST /search` for the gc_uuid-resolve stage (zero hits is fine).
- [ ] **AC-2**: After run 1 the DB holds the full loaded set. After run 2 — a shrunk crawl dropping ALL THREE grains at once (one game absent from the full schedule array; one player absent from a still-present game's populated boxscore block; one roster entry absent) — each dropped entry's rows are GONE and the test asserts EACH grain's retire fired (game-grain, player-line-grain, roster-grain) through the real pipeline. Dropping all three (not "and/or") proves the whole destructive surface, since all three grains fire through `generate_report` (game+roster via `_load_team_core`; player-line via `GameLoader._retire_absent_player_lines`).
- [ ] **AC-3**: After run 2 `result.success is True` AND the report HTML rendered — the destructive re-run still produces a valid report.
- [ ] **AC-4**: The fixture is sized per TN-6 so each dropped entry classifies REMOVED (not TRANSIENT_ABSENT): concretely ≥ 4 completed games (drop 1), roster ≥ 4 players (drop 1), a still-present game's player-line block ≥ 3 players (drop 1); each drop stays inside `FLOOR_RATIO`, `MAX_GAME_RETIREMENTS` (from E-270-01), and `MAX_ROSTER_DEPARTURES`; the dropped game is genuinely absent from the full schedule array; `boxscores_complete` holds on run 2; the games are single-perspective. An undersized fixture that retires nothing FAILS this story's intent and must be corrected, not asserted around.
- [ ] **AC-5**: The test is in-process and network-free (fake injected client, real SQLite temp DB); it does not hang the disk-backed `db` fixture (no `db.backup()` self-backup — see `.claude/rules/testing.md`).

## Technical Approach
Reuse the `TestGenerateReportE2E` scaffolding (disk-backed `db` at `tmp_path/test.db`; patch `render_report`, `_crawl_and_load_spray`, `_crawl_and_load_plays`; `get_connection` → temp DB; repo-root/reports dir → `tmp_path`), but follow the explicit keep-real / patch sets in TN-6: do NOT patch `ScoutingCrawler`, `ScoutingLoader`, or `ensure_team_row_with_provenance` (the last is patched in the existing E2E class at ~:255 — leaving it patched means the real loader persists nothing, the reconcile finds no prior set, and AC-2/AC-4 pass vacuously). Patch only `GameChangerClient` with a multi-endpoint URL-dispatch fake that serves schedule / roster / per-game boxscore AND `POST /search` (gc_uuid-resolve stage; zero hits is fine, non-fatal). Source the canned payloads from the existing redacted `data/raw/` samples so the real `ScoutingCrawler` parses them without raising (a parse error aborts before the reconcile and silently defeats the test — Test-Validates-Spec, `.claude/rules/testing.md`). The two payloads (`fake_full`, then `fake_shrunk` dropping all three grains) drive the retire on the second call. Follow the sizing floor in TN-6 precisely — the one-per-grain drop is under `MAX_GAME_RETIREMENTS` (2) and under any cap ≥ 1, so the sizing is FLOOR-driven and this story carries NO hard dependency on E-270-01 (disjoint files; it asserts the retire FIRED, never on story 01's cap-refusal WARN).

## Dependencies
- **Blocked by**: None (the fixture is floor-sized per TN-6; a one-per-grain drop is under `MAX_GAME_RETIREMENTS` and under any cap ≥ 1, and this story asserts the retire FIRED — never on story 01's cap-refusal WARN — so it carries no hard dependency on E-270-01; disjoint files)
- **Blocks**: None

## Files to Create or Modify
- `tests/test_report_generator.py` (modify — new destructive-reconcile E2E test class)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Test-only story. The genuine-retire RUNTIME smoke against live data is a closure-gate / dispatch concern noted in the epic verification plan, NOT this story (which is a unit/E2E in-process test). Injection seam and sizing per TN-6.
