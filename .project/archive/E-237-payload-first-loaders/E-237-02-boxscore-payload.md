# E-237-02: Payload-first GameLoader: remove the boxscore temp-file bridge

## Epic
[E-237: Payload-First Loaders + Aggregate Integrity](epic.md)

## Status
`DONE`

## Description
After this story is complete, `ScoutingLoader` passes its in-memory boxscore dicts directly to `GameLoader` with no temp files. `GameLoader` exposes a per-call `load_payload(raw, summary, opponent_name=None)` entry point; `load_file(Path, ...)` survives as a thin file-reading wrapper. The member pipeline and all existing loader tests are unaffected; no report stat value changes.

## Context
`src/gamechanger/loaders/scouting_loader.py::_load_boxscores_from_data` (`460-496`) holds `boxscores: dict[game_stream_id -> dict]` in memory but writes each to a temp file (`:491`) so the path-only `GameLoader.load_file` (`game_loader.py:299`) can read it. `GameLoader`'s only file-coupling is `_read_json` at `game_loader.py:491` inside `_load_boxscore_file`; everything else (the `isinstance(raw, dict)` guard, `_detect_team_keys`, `_resolve_team_ids`, `_resolve_home_away`, `_find_duplicate_game` dedup at `:529`, `_upsert_game_and_stats` at `:541`) operates on the parsed dict. `load_file` also does a per-call `self._db.commit()` (`:321`). The member pipeline calls `GameLoader.load_all(team_dir)` over `data/raw/`, and many tests call `load_file`/`load_all` directly — all must keep working. This is the boxscore half of the two-bridge removal (`docs/ROADMAP.md` §5-C, §2). See Technical Notes TN-1, TN-2, TN-3, TN-6 in the epic.

## Acceptance Criteria
- [ ] **AC-1**: Given `ScoutingLoader` holds boxscores in memory, when `_load_boxscores_from_data` loads them, then it calls `GameLoader.load_payload(boxscore_data, summary, opponent_name=...)` per game directly and NO `tempfile`/`TemporaryDirectory` is used anywhere in that function (the `TemporaryDirectory` machinery and per-game temp-file write at `scouting_loader.py:478-491` are removed; the surviving `for game_stream_id, boxscore_data in sorted(...)` loop body de-indents — the loop is NOT deleted).
- [ ] **AC-2**: Given a parsed boxscore dict + its `GameSummaryEntry`, when `GameLoader.load_payload(raw, summary, opponent_name)` runs, then it produces the same `LoadResult` and the same DB rows (games + per-player stat rows) as `load_file` on the equivalent file, preserving the behaviors in Technical Notes TN-2 (the `isinstance(raw, dict)` guard, `_find_duplicate_game` dedup, per-game error isolation, sorted iteration order) and the per-call commit boundary (TN-10); and `_load_boxscores_from_data` keeps its sorted iteration + LoadResult loaded/skipped/errors tally order.
- [ ] **AC-3**: Given a boxscore file, when `GameLoader.load_file(Path, summary, opponent_name)` runs, then it behaves identically to before this story (reads JSON, guards None, delegates to the shared payload logic, commits per call) and all existing `tests/test_loaders/test_game_loader.py` and `tests/test_loaders/test_game_dedup.py` tests pass unmodified; the member-pipeline `load_all(team_dir)` path is unchanged (per Technical Notes TN-3). The per-call commit on both `load_file` and `load_payload` is preserved (option (b), TN-10).
- [ ] **AC-4**: Given every per-player stat INSERT, when `load_payload` writes rows, then `perspective_team_id` is threaded exactly as today (set at `GameLoader` construction via `scouting_loader.py:125`) — no tagging change (per `.claude/rules/perspective-provenance.md` and Technical Notes TN-2).
- [ ] **AC-5**: A focused test calls `GameLoader.load_payload` directly with an in-memory dict and asserts identical `LoadResult` + DB rows versus the file path (per Technical Notes TN-6).
- [ ] **AC-6**: Epic A golden stat tables (`tests/test_report_golden.py`), aggregate parity, and the scouting-loader test suite (`tests/test_scouting_loader.py`) remain green; the LoadResult aggregation in `_load_boxscores_from_data` (loaded/skipped/errors tallying) is preserved.

## Technical Approach
The only file-coupling to remove is the `_read_json` read inside `_load_boxscore_file`. Extract the dict-processing body (from the `isinstance(raw, dict)` guard onward) into a payload path; make `load_file` read JSON, guard the None/non-dict cases, delegate, and commit per call (preserving its per-call commit boundary for the member single-file path + tests). Add a public `load_payload(raw, summary, opponent_name=None)` over the same payload path that ALSO commits per call (option (b), DECIDED — TN-10: the per-game writes stay upstream of and outside the dedup→recompute→commit segment; do NOT make `load_payload` non-committing). In `ScoutingLoader._load_boxscores_from_data`, delete the per-game temp-file write and call `game_loader.load_payload(...)` with the dict already in memory, keeping the existing sorted iteration and LoadResult aggregation. Do not introduce a shared base class with the plays loader (TN-1). Be mindful of the disk-backed `db`-fixture self-`backup()` deadlock trap when writing report-adjacent tests (`.claude/rules/testing.md`).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-237-03 (shared file `scouting_loader.py`)

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` (add `load_payload`; refactor `load_file` to read + guard + delegate + commit)
- `src/gamechanger/loaders/scouting_loader.py` (remove temp-file bridge in `_load_boxscores_from_data`; call `load_payload`)
- `tests/test_loaders/test_game_loader.py` (add the direct-payload test per AC-5; existing tests unchanged)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-237-03**: the boxscore-bridge changes to `scouting_loader.py` land first; Story 03 then modifies the aggregate-recompute call in the same file. Story 03 must rebase its `scouting_loader.py` edits onto this story's result.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
SE-verified live locations supersede the roadmap's stale §2 line numbers. The boxscore bridge is `scouting_loader.py:460-496` (temp-file write at `:491`); `GameLoader.load_file` is `game_loader.py:299`; the `_read_json` coupling is `game_loader.py:491`; the per-call commit is `game_loader.py:321`.
