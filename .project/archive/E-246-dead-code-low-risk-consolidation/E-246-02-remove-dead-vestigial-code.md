# E-246-02: Remove dead/vestigial code (crawlers, API, signing, parser)

## Epic
[E-246: Dead-Code Removal & Low-Risk Consolidation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the grep-confirmed dead and vestigial code scattered across the crawlers, API helpers, signing, and plays parser will be removed, and the crawler docstrings that still describe a disk-write contract will be corrected to the current in-memory contract.

## Context
The sweep's M2 finding enumerates several independently-dead items, all grep-confirmed unreferenced or tests-only:
- `format_season_display` in `src/api/helpers.py:75-109` (orphaned E-241 compound-slug parser).
- `scouting._resolve_team_id` in `src/gamechanger/crawlers/scouting.py:338-353`.
- `freshness_hours` / `_is_scouted_recently` in `scouting.py:134-144`, `:403-430` (referenced only by tests — see Non-Goals: this epic deletes them and their tests-only callers rather than wiring freshness gating in).
- Unused `import json` + `data_root` plumbing + stale disk-write docstrings in both crawlers (`scouting.py:44` and the opponents crawler).
- An unreachable `None` branch in `src/gamechanger/signing.py:64-66`.
- A redundant `strikes < 2` guard in `src/gamechanger/parsers/plays_parser.py:748`.

This is several small, independent deletions bundled into one story because each is the same kind of low-risk "delete grep-confirmed dead code" change. Pre-existing idea IDEA-081 is effectively promoted into this work.

## Acceptance Criteria
- [ ] **AC-1**: Given each dead symbol named in Context, when the implementer greps `src/` and `tests/` for it before deletion, then it confirms the symbol is unreferenced (or referenced only by tests being removed alongside it). The grep results are recorded in the completion report.
- [ ] **AC-2**: Given confirmation, when the story completes, then each dead symbol/branch/import is removed, along with the orphaned `_is_scouted_recently`/freshness tests.
- [ ] **AC-3**: Given the crawler docstrings currently describe a disk-write contract, when the story completes, then those docstrings are corrected to describe the current in-memory crawl-to-load contract.
- [ ] **AC-4**: Given the redundant `strikes < 2` guard and the unreachable `None` branch are removed, when the affected parser/signing logic runs against existing tests, then behavior is unchanged (the removed code was provably unreachable/redundant).
- [ ] **AC-5**: Given all deletions, when the affected modules' test suites run (`tests/test_helpers.py`, `tests/test_scouting_crawler.py`, `tests/test_signing.py`, and the plays-parser coverage in `tests/test_validate_plays_stats.py`), then they pass, and a grep confirms no surviving reference to any removed symbol. (The full-suite-green check across `tests/` is the epic-level closure gate, not a per-story AC — it is only authoritative in the merged main checkout, not the worktree.)

## Technical Approach
Report locations (re-verify before acting): `src/api/helpers.py:75-109`, `src/gamechanger/crawlers/scouting.py:338-353`, `:134-144`, `:403-430`, `:44`, `src/gamechanger/signing.py:64-66`, `src/gamechanger/parsers/plays_parser.py:748`, plus the opponents crawler's `import json`/`data_root`/docstring residue. Each item is independent; confirm dead status per-item via grep. For the two "redundant/unreachable" items (signing `None` branch, parser `strikes < 2` guard), confirm via reading the surrounding control flow that the branch cannot be reached before removing.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/helpers.py`
- `src/gamechanger/crawlers/scouting.py`
- `src/gamechanger/crawlers/opponents.py` (docstring/import/plumbing residue only)
- `src/gamechanger/signing.py`
- `src/gamechanger/parsers/plays_parser.py`
- The `_is_scouted_recently`/freshness test file(s) (delete the orphaned tests — locate by grep)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Per-item grep confirmation recorded in completion report
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes
The opponents crawler appears in M2 only for `import json` / `data_root` plumbing and a stale disk-write docstring — do not touch its live crawl logic.
