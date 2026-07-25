# E-270-03: True end-to-end destructive-path test (generate_report twice, real ScoutingLoader)

## Epic
[E-270: Harden Reconcile-at-Load and Purge](../E-270-reconcile-purge-hardening/epic.md)

## Status
`DONE`
<!-- DONE 2026-07-24. PM AC verdict 6/6, code-reviewer APPROVED 6/6. AC-1 was
     verified CONDITIONALLY (the respx-vs-client-patch seam deviation) and the
     condition resolved: cr established TN-6's literal form is WEAKER, not
     equivalent. AC-3 was re-confirmed against the `all` form after the
     any->all fix, not inherited from the `any` verdict.
     Two spec defects this story surfaced were amended in-flight: TN-6's
     unimplementable `data/raw/` payload source, and AC-1's over-specified
     injection seam. AC-6's attribution guarantee depends on an EXTERNAL seam
     (generator.py:1518 borrowing the patched connection into the reclamation,
     since lifecycle.py:32 imports get_connection at module level) -- see epic
     History; the test now carries that reasoning inline. -->
<!-- was: IN_PROGRESS -->

## Description
After this story is complete, a test will drive `generate_report()` itself twice against a real temporary database — with NO `ScoutingLoader` mock — where the second crawl drops one entry from EACH of the three grains (a game, a player line, a roster entry), and it will assert that each grain's reconcile-at-load retire actually fires (the dropped rows are gone) AND the report still renders successfully. This closes the audit's most serious testing gap: report generation became destructive in E-267, yet no test exercises that destruction through the real generation entry point. Since 2026-07-24 (E-273) the same entry point also runs an orphan-reclamation hard-delete, covered separately by `tests/test_orphan_reclamation.py`; this story stays scoped to the reconcile-at-load axis, and AC-6 pins the boundary between the two.

## Context
Every test in `TestGenerateReportE2E` (`tests/test_report_generator.py`) patches `ScoutingLoader` out (`patch("src.reports.generator.ScoutingLoader", ...)`), so the retire path — which lives inside `ScoutingLoader.load_team` — never runs through `generate_report()`. The audit flagged this as annotation-as-coverage: the destructive path is "tested" only at the unit level, never end-to-end. The fix drives the test through the REAL producer (the injected `GameChangerClient`), per the testing.md "drive the test through the real producer" guidance. See epic Technical Notes TN-6 for the injection seam and the mandatory fixture-sizing caveat.

## Acceptance Criteria
- [ ] **AC-1**: A new test (e.g. `TestGenerateReportDestructiveReconcile` in `tests/test_report_generator.py`) drives `generate_report()` TWICE against a real disk-backed temp DB, the second call seeing a shrunk payload, with `ScoutingCrawler`, `ScoutingLoader`, AND `ensure_team_row_with_provenance` all REAL (per the keep-real set in TN-6). Every endpoint the live pipeline calls is served, including `POST /search` for the gc_uuid-resolve stage (zero hits is fine). **The fake may be injected at EITHER seam** (amended 2026-07-24 during dispatch; this AC originally mandated patching `src.reports.generator.GameChangerClient` with `side_effect=[fake_full, fake_shrunk]`): patching the client, or faking the HTTP transport beneath it. The transport seam is PREFERRED where the payloads are real-shaped, because it keeps a strict SUPERSET real — `GameChangerClient` itself, its URL construction, and its response handling all stay live — so it cannot be weaker on the property this AC protects, and it does not depend on `GameChangerClient` being constructed exactly once per run (a detail the `side_effect` list silently relies on). What is binding is the keep-real set, the endpoint coverage, and that the second call sees the shrunk payload — not the mechanism.
- [ ] **AC-2**: After run 1 the DB holds the full loaded set. After run 2 — a shrunk crawl dropping ALL THREE grains at once (one game absent from the full schedule array; one player absent from a still-present game's populated boxscore block; one roster entry absent) — each dropped entry's rows are GONE and the test asserts EACH grain's retire fired (game-grain, player-line-grain, roster-grain) through the real pipeline. Dropping all three (not "and/or") proves the whole destructive surface, since all three grains fire through `generate_report` (game+roster via `_load_team_core`; player-line via `GameLoader._retire_absent_player_lines`).
- [ ] **AC-3**: After run 2 `result.success is True` AND the report HTML rendered — the destructive re-run still produces a valid report.
- [ ] **AC-4**: The fixture is sized per TN-6 so each dropped entry classifies REMOVED (not TRANSIENT_ABSENT): concretely ≥ 4 completed games (drop 1), roster ≥ 4 players (drop 1), a still-present game's player-line block ≥ 3 players (drop 1); each drop stays inside `FLOOR_RATIO`, `MAX_GAME_RETIREMENTS` (from E-270-01), and `MAX_ROSTER_DEPARTURES`; the dropped game is genuinely absent from the full schedule array; `boxscores_complete` holds on run 2; the games are single-perspective. An undersized fixture that retires nothing FAILS this story's intent and must be corrected, not asserted around. The fixture MUST NOT pre-seed a bare `membership_type='tracked'` subject team, player, or roster row — E-273's reclamation sweeps exactly that shape at run-1 start (see TN-6); the subject rows are created by the real pipeline.
- [ ] **AC-5**: The test is in-process and network-free (the fake is injected at whichever seam AC-1 permits, real SQLite temp DB); it does not hang the disk-backed `db` fixture (no `db.backup()` self-backup — see `.claude/rules/testing.md`).
- [ ] **AC-6**: `generate_report()` runs TWO hard-deleting passes — reconcile-at-load, and E-273's `reclaim_orphan_reference_data` fired from `cleanup_expired_reports` at generation START. The test must ATTRIBUTE the AC-2 deletions to the RETIRE, not to the reclamation: bare absence of the dropped rows is not attribution. The test asserts the reclamation pass removed nothing during run 2. A test that asserts only that the rows are absent FAILS this AC. (Mechanism is the implementer's call.)

## Technical Approach
Reuse the `TestGenerateReportE2E` scaffolding (disk-backed `db` at `tmp_path/test.db`; patch `render_report`, `_crawl_and_load_spray`, `_crawl_and_load_plays`; `get_connection` → temp DB; repo-root/reports dir → `tmp_path`), but follow the explicit keep-real / patch sets in TN-6: do NOT patch `ScoutingCrawler`, `ScoutingLoader`, or `ensure_team_row_with_provenance` (the last is patched in the existing E2E class at ~:255 — leaving it patched means the real loader persists nothing, the reconcile finds no prior set, and AC-2/AC-4 pass vacuously). Inject the fake at the client seam OR the HTTP-transport seam beneath it (AC-1, amended — the transport seam is preferred and is what shipped), serving schedule / roster / per-game boxscore AND `POST /search` (gc_uuid-resolve stage; zero hits is fine, non-fatal). Source the canned payloads from `tests/fixtures/e2e/` — committed, anonymized, real-GC-shape, and already the source of truth for `tests/test_report_e2e.py`. *(Amended 2026-07-24: this originally said `data/raw/`, which is gitignored and does NOT exist in an epic worktree, so it was never an implementable instruction. See TN-6.)* Real-shaped payloads are what matters: the real `ScoutingCrawler` must parse them without raising, since a parse error aborts before the reconcile and silently defeats the test (Test-Validates-Spec, `.claude/rules/testing.md`). The two payloads (`fake_full`, then `fake_shrunk` dropping all three grains) drive the retire on the second call. Follow the sizing floor in TN-6 precisely — the one-per-grain drop is under `MAX_GAME_RETIREMENTS` (2) and under any cap ≥ 1, so the sizing is FLOOR-driven and this story carries NO hard dependency on E-270-01 (disjoint files; it asserts the retire FIRED, never on story 01's cap-refusal WARN).

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
