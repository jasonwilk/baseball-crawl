# E-256-01: Delete the disk-based twin load flow

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`TODO`

## Description
After this story is complete, the loaders have a single in-memory entry path. The production-dead disk-based load surfaces (`load_all`/`load_dir`/`load_file`/`_load_team_from_disk` and the `Path`-branch dispatch inside the loaders) are gone, along with the ~10 tests whose assertions are about filesystem behavior. The ~149 disk-entry tests that assert on loader *logic* are re-pointed at the in-memory `load_payload` / `load_from_data` entry points and continue to pass.

## Context
Nothing writes `data/raw/` anymore (the scouting and reports pipelines are in-memory crawl-to-load), yet the loaders still carry a full disk twin and ~150 pinning tests. The E-247 near-miss — a stat-wiping regression on the LIVE path introduced *purely to preserve parity with this dead path* — is the concrete carrying cost. See Technical Notes §4 for the delete-vs-re-point split; the ~10 dying tests are enumerated there.

## Acceptance Criteria
- [ ] **AC-1**: Given the loaders (`GameLoader`, `PlaysLoader`, `ScoutingLoader`, `ScoutingSprayChartLoader`), when this story is complete, then the disk-entry surfaces (`load_all`/`load_dir`/`load_file`/`_load_team_from_disk` and any `isinstance(x, Path)` disk-branch dispatch) are removed and no `src/` module reads `data/raw/`.
- [ ] **AC-2**: Given the ~149 disk-entry tests that assert on loader logic (boxscore parsing, team-key detection, `_find_duplicate_game` dedup, perspective tagging, roster upsert), when the disk surfaces are removed, then they are re-pointed at `load_payload` / `load_from_data` and continue to pass. Net suite delta ≈ **−9** (the filesystem-asserting deletions), not −159, per Technical Notes §4.
- [ ] **AC-3**: Given a candidate test for deletion, then **the gate is the criterion, not a count**: a test is deleted ONLY if its assertion is about filesystem behavior (absent `games/` dir, missing `game_summaries.json`, unreadable boxscore path, malformed/absent `roster.json`, empty `plays/` dir, disk-vs-in-memory parity); any test whose assertion is about loader *logic* PORTS to `load_payload`/`load_from_data`. `test_unknown_public_id_skips_directory` is committed to **PORT** (its subject is `public_id` resolution, which `load_from_data` also performs — SE's lean), so the filesystem-asserting deletions number **nine**, not ten (Technical Notes §4). No test whose assertion does not mention the filesystem is deleted.
- [ ] **AC-4**: Given the full suite, when this story is complete, then it is green in the worktree scope for the affected loader test files, with the nine filesystem tests removed and all logic tests (including the ported `test_unknown_public_id_skips_directory`) passing via the in-memory entry points.
- [ ] **AC-5**: Given the disk surfaces are removed, when this story is complete, then `grep -rl '\.load_file(\|\.load_all(\|\.load_dir(' tests/` returns **zero files** — the mechanical guard that no test still calls a deleted disk method (a residual call surfaces as a closure-time `AttributeError`/collection error at the Step-8 gate, not a per-story catch, so this grep must be clean before the story is DONE).

## Technical Approach
Remove the disk-reading wrappers and their `Path`-branch dispatch; keep the in-memory `load_payload` / `load_from_data` cores that the report generator already drives. Re-point each surviving test at the in-memory entry point rather than deleting it. Consult Technical Notes §4 for the enumerated dying tests and the re-point rule. The E-237 "payload core + thin file-reading wrapper" convention in `architecture-subsystems.md` becomes actively misleading after this change — its eviction is story 15's job (do not edit context-layer files here).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-256-15 (context-layer eviction references the deleted surfaces)

## Files to Create or Modify
- `src/gamechanger/loaders/scouting_loader.py`
- `src/gamechanger/loaders/game_loader.py` (or wherever `GameLoader.load_all`/`load_file` live)
- `src/gamechanger/loaders/plays_loader.py`
- `src/gamechanger/loaders/scouting_spray_loader.py`
- `tests/test_scouting_loader.py`
- `tests/test_loaders/test_game_loader.py` (note the `test_loaders/` subdir — SE-verified path)
- `tests/test_loaders/test_game_dedup.py` (SE-surfaced: ~14 `load_file`/`load_all` sites; all logic tests that PORT)
- `tests/test_game_start_time.py` (SE-surfaced: ≥2 `load_file` tests, e.g. `test_load_file_passes_start_time_from_summary`; logic tests that PORT)
- `tests/test_plays_loader.py`
- `tests/test_scouting_spray_loader.py`

(The six-file set is exactly what `grep -rln '\.load_file(\|\.load_all(\|\.load_dir(' tests/` returns — SE's initial census used a column-0-anchored `^def test_` and missed indented class-method tests, so `test_game_dedup.py`/`test_game_start_time.py` were absent from the first draft. The −10 die / ~149 port ratio is UNCHANGED: every newly-surfaced test is a logic test that ports; none asserts on the filesystem, so none joins §4's ten dying tests.)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-256-15**: the set of deleted symbols (`load_all`, `load_dir`, `load_file`, `_load_team_from_disk`) that the context-layer eviction sweep must strike from `architecture-subsystems.md`.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (re-pointed logic tests green; nine filesystem tests removed; `test_unknown_public_id_skips_directory` ported)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Per Technical Notes §4, four of the ten dying tests are E-247's own `test_e247_disk_*` disk/in-memory parity guards — the tightest confirmation that the twin is exactly what E-247 was defending.
