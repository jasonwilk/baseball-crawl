# E-256-01: Delete the disk-based twin load flow

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

## Description
After this story is complete, the loaders have a single in-memory entry path. The production-dead disk-based load surfaces (`load_all`/`load_dir`/`load_file`/`_load_team_from_disk` and the `Path`-branch dispatch inside the loaders) are gone, **together with the private disk helpers they orphan** (`_build_opponent_name_lookup`, `_build_summaries_index`, `_parse_summary_record`, `_load_boxscore_file`, the `_read_json`/`_read_json_list` readers), along with the tests whose assertions are about filesystem behavior or about those now-deleted helpers (~20). The remaining disk-entry tests (~140) assert on loader *logic that still ships* and are re-pointed at the in-memory `load_payload` / `load_from_data` entry points, where they continue to pass.

## Context
Nothing writes `data/raw/` anymore (the scouting and reports pipelines are in-memory crawl-to-load), yet the loaders still carry a full disk twin and ~159 pinning tests. The E-247 near-miss — a stat-wiping regression on the LIVE path introduced *purely to preserve parity with this dead path* — is the concrete carrying cost. See Technical Notes §4 for the delete-vs-re-point split.

**Scope correction (2026-07-09, PM ruling during dispatch).** §4's enumeration of nine dying tests **undercounts**. It censused only the tests calling the *public* disk entry points; deleting those entry points also orphans their *private* disk helpers, which carry their own direct test coverage and have no in-memory counterpart to port to. The true figure is ~20. **The criterion in AC-3 controls, not any count.** The undercount is the same hand-list-versus-grep failure §15 records for the `backfill-appearance-order` eviction (IDEA-115) — a seed list read as a ceiling.

## Acceptance Criteria
- [ ] **AC-1**: Given the four loaders (`GameLoader`, `PlaysLoader`, `ScoutingLoader`, `ScoutingSprayChartLoader`), when this story is complete, then the disk-entry surfaces (`load_all`/`load_dir`/`load_file`/`_load_team_from_disk` and any `isinstance(x, Path)` disk-branch dispatch) are removed, together with the **private disk helpers they orphan** (`_build_opponent_name_lookup`, `_build_summaries_index`, `_parse_summary_record`, `_load_boxscore_file`, `GameLoader._read_json`, `PlaysLoader._read_json`, `ScoutingLoader._read_json_list`, `_build_opponent_name_index`, `_build_games_index`, and any helper whose sole caller is a deleted disk entry point), and **no file under `src/gamechanger/loaders/` reads `data/raw/`**. The epic-wide "no module under `src/` reads `data/raw/`" assertion is an **epic Success Criterion verified at closure**, not a story-01 gate — `backfill.py` is story 02's target and `crawlers/scouting_spray.py` + `cli/status.py` are story 03's (see that story's AC-6).
- [ ] **AC-2**: Given the disk-entry tests that assert on loader logic (boxscore parsing, team-key detection, `_find_duplicate_game` dedup, perspective tagging, roster upsert), when the disk surfaces are removed, then they are re-pointed at `load_payload` / `load_from_data` and continue to pass. The net suite delta is **whatever AC-3's criterion yields** — approximately −20 against a ~159-test disk-entry population, not −159. The count is an estimate; **AC-3's criterion is the gate**.
- [ ] **AC-3**: Given a candidate test for deletion, then **the gate is the criterion, not a count**: a test is deleted if and only if BOTH (a) its assertion is about filesystem behavior (absent `games/` dir, missing `game_summaries.json`, unreadable boxscore path, malformed/absent `roster.json`, empty `plays/` dir, directory globbing/filtering, disk-vs-in-memory parity) **OR its subject is a private disk helper that this story deletes**; AND (b) the behavior it asserts **does not survive on the in-memory path**. Any test whose assertion is about loader *logic that still ships* PORTS to `load_payload`/`load_from_data`. `test_unknown_public_id_skips_directory` is committed to **PORT** (its subject is `public_id` resolution, which `load_from_data` also performs). The implementer MUST enumerate every deleted test by name in the completion report with its clause-(a) and clause-(b) justification; PM verifies each against this gate.
- [ ] **AC-4**: Given the full suite, when this story is complete, then it is green in the worktree scope for the affected loader test files, with the AC-3-qualifying tests removed and all surviving logic tests (including the ported `test_unknown_public_id_skips_directory`) passing via the in-memory entry points.
- [ ] **AC-6**: Given the `_opt_int` NULL-preservation semantic (E-253-06 AC-3: missing scores preserve NULL rather than coercing to 0, so a scoreless doubleheader does not collapse under `_find_duplicate_game`'s natural-key dedup), which is asserted today against `_parse_summary_record` and is **re-implemented inline** on the surviving in-memory path at `scouting_loader.py:408-422` (`_build_games_index_from_data`), when `_parse_summary_record` and its tests are deleted, then an equivalent assertion **exists against `_build_games_index_from_data`** — ported from the deleted test if no such assertion exists today. This is the one place clause (b) of AC-3 bites: the *function* dies, the *semantic* ships. Additionally, the two comments at `scouting_loader.py:406` and `:414` that reference `_parse_summary_record` by name are re-pointed or rewritten, since they will otherwise cite a deleted function.
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
- `tests/test_post_load_validation.py` (PM-approved addition during dispatch: enters via `load_team(Path, …)`, invisible to the `.load_file(|.load_all(|.load_dir(` grep this list was derived from — the same seed-not-ceiling miss the count correction records. All six tests PORT; none is deleted.)

(The six-file set is what `grep -rln '\.load_file(\|\.load_all(\|\.load_dir(' tests/` returns. That grep is **necessary but not sufficient** — it finds tests entering through the *public* disk API, and misses tests that call the *private* disk helpers directly, e.g. `test_build_opponent_name_lookup_*` at `tests/test_loaders/test_game_loader.py:1506-1612`. The implementer's census MUST also grep for the private helper names named in AC-1. This is precisely why the count moved from nine to ~20.)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-256-15**, two things — the second is NOT derivable from the first:
  1. **The deleted symbol set**: the public disk entry points (`load_all`, `load_dir`, `load_file`, `_load_team_from_disk`) AND the private disk helpers they orphaned (`_build_opponent_name_lookup`, `_build_summaries_index`, `_parse_summary_record`, `_load_boxscore_file`, `_read_json`/`_read_json_list`, `_build_opponent_name_index`, `_build_games_index`).
  2. **A retired CONVENTION, not just retired names.** The E-237 "payload core + thin file-reading wrapper" split (`architecture-subsystems.md:72`) no longer describes this codebase and its closing guidance would instruct a future loader to rebuild the twin deleted here. Story 15 AC-1 must rewrite the paragraph, not strike its symbol names. **A token grep for the symbol set will NOT surface the closing guidance sentence** — this is the doc-sweep semantic-read case, and it is why the handoff names the convention explicitly. (CR-surfaced during story-01 review.)
- **Produces for E-256-15 (contract narrowing)**: `GameLoader.load_payload` no longer ensures the `seasons` row, so CLAUDE.md's "all loaders MUST use `ensure_season_row()`" rule is now false as written. Story 15 AC-5 records the narrowing.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (re-pointed logic tests green; the AC-3-qualifying filesystem tests removed; `test_unknown_public_id_skips_directory` ported)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## PM AC-Verification Round 1 (2026-07-09)
Verified against the worktree, not the completion report. **AC-1, AC-2, AC-4, AC-5, AC-6 PASS. AC-3 FAILS on one deletion of twenty-four.**

**Required change 1 — `test_e247_disk_missing_roster_no_error` must PORT, not die.** It satisfies AC-3 clause (a) but **fails clause (b)**: the outcome it asserts — *an absent roster does not count as an error* — **survives on the in-memory path** at `scouting_loader.py:281-283`, where an empty `roster_data` logs a warning and returns a bare `LoadResult()` (errors == 0). Its three sibling deletions (`malformed`/`non_array`/`disk_path_matches_in_memory`) are correct, because the `extra_errors` **read-error mechanism** they assert is genuinely disk-only and is now absent from the whole repo — but "missing" is not "malformed": the missing-roster branch has a live analogue. No surviving test asserts `errors == 0` for an empty roster (`roster=[]` appears at `test_scouting_loader.py:430` and `:1893`, but neither asserts on error count — `:1893`'s subject is the boxscoreless tail-skip). Port it as an empty-`roster_data` no-error assertion against `load_team`.

**Required change 2 — document the narrowed season-row contract.** `GameLoader.load_payload` no longer ensures the `seasons` row, and its docstring (`game_loader.py:271-285`) does not say so. In-tree this is safe (PM-verified: `scouting_loader.py:155` is the sole `GameLoader(...)` construction in `src/`, and it ensures the row first at `:130`), but the precondition is now invisible to the next caller and FK-fails at runtime. Add it to the `load_payload` docstring as a stated precondition. The CLAUDE.md "all loaders MUST use `ensure_season_row()`" rule now has an exception it does not record — that eviction is **story 15's** (claude-architect), not story 01's; PM has routed it.

**Accepted as-implemented (no change required):**
- `tests/test_post_load_validation.py` is **in scope** despite its absence from the original Files list. Same seed-not-ceiling miss; all six tests ported, none deleted. Files list amended.
- `TestMissingScoreNoCoercion` **PORTED rather than deleted — SE is right and PM's AC-6 expectation was wrong.** Its three tests were re-pointed at `load_payload` and now exercise `_upsert_game`'s NULL storage and `_find_duplicate_game`'s scoreless-doubleheader dedup, both of which survive; AC-3 clause (b) therefore forbids deleting them. This is **not** over-coverage: the `test_scouting_loader.py` additions assert *index construction* (`_build_games_index_from_data` emits `None` for a missing score key, `0` for a present zero), while these assert *storage and dedup* given such a summary. Different subjects. Keep both.
- The three behavioral changes are accepted. The `ScoutingLoader` boxscore-source guard's collapse to dict-truthiness removes a **disk-path asymmetry**, not a live behavior (the surviving tail-skip is pinned at `test_scouting_loader.py:1888-1903`); `PlaysLoader._load_game`'s narrowed signature is private.

## PM AC-Verification Round 2 (2026-07-09)
**ALL SIX ACs PASS.** Re-verified against the worktree.

- **AC-3 now PASSES.** `test_empty_roster_is_not_an_error` (`test_scouting_loader.py:1909`) asserts `result.errors == 0` **and** zero `team_rosters` rows. Read it: it has teeth (SE's mutation check — `LoadResult(errors=1)` fails it — is consistent with the assertion I read). The corrected ledger is confirmed against the tree: `test_load_all_returns_load_result_instance` and `test_load_all_no_dirs_returns_empty_result` are both absent from `tests/`; `test_build_opponent_name_index_empty_games_returns_empty` exists at `:1124`. **24 true deletions stands; composition moved by two each way.**
- **MUST-2 PASSES.** `game_loader.py:277-283` carries the `PRECONDITION:` block naming both INSERT sites, the FK failure mode, and `ScoutingLoader._load_team_core` as the discharging caller.
- **AC-1 re-confirmed** post-remediation: zero matches in `src/` for any disk entry point or orphaned private helper.
- **AC-5 re-confirmed** independently.
- **AC-2 / AC-4 / AC-6** undisturbed.

**Ruling — `ScoutingLoader.load_team`'s `season_id` parameter removal is IN SCOPE.** The parameter existed solely for backwards compatibility with `_load_team_from_disk`, which this story deletes; it is orphaned residue of this story's own deletion, exactly the class AC-1 requires removing. It needs **no story-15 note**: no context-layer file names `load_team`'s signature (`architecture-subsystems.md:74` names the method, not its parameters), and the removal does not touch CLAUDE.md's season-derivation rule — that rule's narrowing is `GameLoader.load_payload`'s, already routed to story 15 AC-5. The `TypeError`-over-silent-ignore change is the correct direction: a caller passing `season_id=` was passing a value the loader ignored while deriving its own.

**Routed, not dropped:** `.claude/agent-memory/data-engineer/season_aggregate_writers.md` cites `load_team` at `:159` and `_compute_season_aggregates` at `:643`; story 01 shifted both. Added to the epic §15 owning-agent closure-sweep row.

## Notes
Per Technical Notes §4, four of the ten dying tests are E-247's own `test_e247_disk_*` disk/in-memory parity guards — the tightest confirmation that the twin is exactly what E-247 was defending.
