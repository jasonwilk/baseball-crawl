# E-237-01: Payload-first PlaysLoader: remove the plays tempdir bridge

## Epic
[E-237: Payload-First Loaders + Aggregate Integrity](epic.md)

## Status
`DONE`

## Description
After this story is complete, the report generator passes its in-memory plays data directly to `PlaysLoader` with no temp files. `PlaysLoader` exposes a batch `load_payload(plays_by_game)` entry point; `load_all(Path)` survives as a thin file-reading wrapper over the same per-game logic. No report stat value changes.

## Context
`src/reports/generator.py::_crawl_and_load_plays` fetches plays in-memory into `plays_data: dict[game_id -> raw dict]`, then writes each game's JSON into a `tempfile.TemporaryDirectory()` (block at `generator.py:921-932`) solely so `PlaysLoader.load_all(Path)` can glob it back off disk. The generator is the only caller using this tempdir BRIDGE; the member pipeline (`src/pipeline/load.py:199`, loader constructed at `:193`) also calls `PlaysLoader.load_all` over real `data/raw/` and MUST keep working unchanged. All other call sites are tests. `PlaysLoader`'s only file-coupling is `_read_json` at `plays_loader.py:161`; all real work (FK guard, idempotency, parse, insert, per-game transaction) already operates on the parsed dict. This is the plays half of the two-bridge removal (`docs/ROADMAP.md` §5-C, §2). See Technical Notes TN-1, TN-2, TN-3, TN-6 in the epic.

## Acceptance Criteria
- [ ] **AC-1**: Given the generator holds `plays_data` in memory, when `_crawl_and_load_plays` loads plays, then it calls `PlaysLoader.load_payload(plays_data)` directly and NO `tempfile`/`TemporaryDirectory` is used anywhere in that function — the `generator.py:921-932` tempdir block AND the now-dead function-local `import tempfile` at `generator.py:859` are both removed.
- [ ] **AC-2**: Given a batch dict of `game_id -> raw plays dict`, when `PlaysLoader.load_payload(plays_by_game)` runs, then it produces the same `LoadResult` and the same `plays`/`play_events` DB rows as loading the equivalent files via `load_all`, preserving per-game error isolation, whole-game idempotency, deterministic iteration order, and empty/`{}`-entry skipping (per Technical Notes TN-1, TN-2).
- [ ] **AC-3**: Given a directory of plays files, when `PlaysLoader.load_all(Path)` runs, then it behaves identically to before this story (reads JSON and delegates to the shared per-game logic); all existing `tests/test_plays_loader.py` tests pass unmodified AND the member-pipeline caller `src/pipeline/load.py:199` keeps working unchanged (per Technical Notes TN-3).
- [ ] **AC-4**: Given every plays INSERT, when `load_payload` writes rows, then `perspective_team_id` is set from `self._team_ref.id` exactly as the path method does (per `.claude/rules/perspective-provenance.md` and Technical Notes TN-2).
- [ ] **AC-5**: A focused test calls `PlaysLoader.load_payload` directly with an in-memory dict and asserts identical `LoadResult` + DB rows versus the file path (per Technical Notes TN-6).
- [ ] **AC-6**: Epic A golden stat tables (`tests/test_report_golden.py`) and aggregate parity remain green; the reconciliation accumulator wiring in `_crawl_and_load_plays` (`recon_out.plays_load_errors += load_result.errors`) is preserved.

## Technical Approach
The only file-coupling to remove is the `_read_json` read. Add a batch payload entry point to `PlaysLoader` that applies the existing per-game logic to each in-memory entry, and refactor the directory path (`load_all`) to read files then delegate to that same shared per-game logic. In the generator, delete the tempdir block and call the batch payload method with the dict already in memory. Preserve the per-game commit, error isolation, idempotency, iteration order, and empty-skip behavior described in the epic's Technical Notes (TN-1, TN-2). Do not introduce a shared base class with the other loader (TN-1).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/reports/generator.py` (remove tempdir bridge in `_crawl_and_load_plays`; call `load_payload`)
- `src/gamechanger/loaders/plays_loader.py` (add `load_payload`; refactor `load_all` to a thin wrapper over shared per-game logic)
- `tests/test_plays_loader.py` (add the direct-payload test per AC-5; existing tests unchanged)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
SE-verified live locations supersede the roadmap's stale §2 line numbers. The plays tempdir block is `generator.py:921-932`; `PlaysLoader.load_all` is `plays_loader.py:77`; the `_read_json` coupling is `plays_loader.py:161`.
