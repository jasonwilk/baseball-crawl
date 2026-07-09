# E-256-04: Extract a client-free lifecycle module + relocate the season fetch from generator.py

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`TODO`

## Description
After this story is complete, `generator.py` (3,034 lines) is restructured two ways: (1) its lifecycle/deletion stack moves to a new client-free `src/reports/lifecycle.py` (~640 lines), so the admin delete path no longer imports httpx/jinja2 transitively; and (2) the pure SQL season fetch is relocated to `src/api/db.py` as `get_season_batting`/`get_season_pitching`, with `_query_batting`/`_query_pitching` staying in `generator.py` as thin presentation wrappers. The report renders identically — `tests/test_report_golden.py` is zero-diff.

## Context
This story does two restructurings of one file, kept together to avoid a same-file collision and to let one reviewer see the whole change. The lifecycle extraction is Technical Notes §13; the season-fetch relocation is Technical Notes §14 (DE's relocation contract — the resolved E-256/E-259 seam). The relocation is a **prerequisite** for E-259, which later rewrites only the SQL body inside `get_season_*` in place. The load-bearing constraints: the fetch returns **raw SUM columns** (NOT the display strings `era`/`k9`/`whip`/`strike_pct`, which `_compute_pitching_rates` produces in the wrapper); the presentation helpers `_apply_name_cascade`/`_compute_pitching_rates` **stay in `src/reports/`** — moving them into `db.py` would create an import cycle (`generator.py:29-35` already imports from `src.api.db`).

## Acceptance Criteria
- [ ] **AC-1**: Given the deletion/lifecycle stack (the contiguous tail `generator.py:2577-3034` plus the scattered lifecycle helpers), when this story is complete, then it lives in a new `src/reports/lifecycle.py` that imports **none** of `GameChangerClient`, crawlers, loaders, `render_report`, `reconcile_game`, `parse_team_url`, or `CredentialExpiredError` (SE verified zero references across the moved regions).
- [ ] **AC-2**: Given the admin delete path (`reports_admin.py::_delete_report`), when this story is complete, then it imports the deletion cascade from `src/reports/lifecycle.py` and no longer pulls httpx/jinja2 transitively through the generation stack.
- [ ] **AC-3**: Given the season fetch, when this story is complete, then `src/api/db.py` contains `get_season_batting(conn, team_id, season_id) -> list[dict]` and `get_season_pitching(conn, team_id, season_id) -> list[dict]` returning the **raw SUM columns** (per Technical Notes §14 — `get_season_pitching` returns rows WITHOUT `era`/`k9`/`whip`/`strike_pct`), and `_query_batting`/`_query_pitching` remain in `generator.py` as thin wrappers composing the fetch with `_apply_name_cascade` and (pitching) `_compute_pitching_rates`.
- [ ] **AC-4**: Given the relocation, when this story is complete, then it is a **pure move** — the SQL bodies, dict keys, and both ORDER BY clauses are byte-unchanged from the pre-move code; **no** `perspective_team_id` filter is added (that is E-259); `_apply_name_cascade`/`_compute_pitching_rates` stay in `src/reports/` (not moved to `db.py`); and `batting_recompute_select()`/`pitching_recompute_select()` are not deleted.
- [ ] **AC-5**: Given the import graph, when this story is complete, then no import cycle exists — `src/api/db.py` remains a stdlib + `src.db.paths` leaf, and `generator.py` still imports from `src.api.db` one-way (verified by the suite importing cleanly).
- [ ] **AC-6**: Given `tests/test_report_golden.py`, when this story is complete, then it is **zero-diff** — no import edits, no expectation edits. It exercises the `_query_*` wrappers, whose composed output is unchanged across the relocation.
- [ ] **AC-7**: Given the full suite, when this story is complete, then it is green.

## Technical Approach
Depends on story 03's single public `utcnow_iso`. SE requests **two commits** for the lifecycle extraction — the contiguous deletion tail first — because `generate_report` sits at `:1655` *between* the deletion tail and the scattered lifecycle helpers. The fetch relocation is a third logical change in the same file; sequence it so the golden test stays green throughout. The relocation is a pure move — resist the pull to "clean up" the SQL or return computed rates from the fetch (that would drag the formatter along and re-introduce the cycle). Do not prescribe the internal module layout beyond the client-free constraint (§13) and the raw-columns/no-cycle constraint (§14).

## Dependencies
- **Blocked by**: E-256-03 (single public `utcnow_iso`)
- **Blocks**: E-256-05 (rest-day fix touches the same file); E-256-15 (eviction sweep)

## Files to Create or Modify
- `src/reports/lifecycle.py` (create)
- `src/api/db.py` (add `get_season_batting`/`get_season_pitching` — raw SUM columns)
- `src/reports/generator.py` (remove the moved lifecycle regions; move the fetch SQL out; keep `_query_*` wrappers + the presentation helpers)
- `src/api/routes/reports_admin.py` (import cascade from lifecycle.py)
- Any test file importing the moved lifecycle helpers (re-point imports; do NOT touch `test_report_golden.py`)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-259**: `get_season_batting`/`get_season_pitching` in `src/api/db.py`, whose SQL bodies E-259 rewrites in place (against `player_game_*`, adding the perspective filter, reproducing the ORDER BY over the new projection); and the zero-diff golden invariant E-259 must also preserve.
- **Produces for E-256-05**: the settled `generator.py` structure and `utcnow_iso` usage the rest-day fix builds on.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests updated and passing (golden zero-diff; clean import)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The zero-diff golden bracket is the deliberate win: E-256 relocates (golden zero-diff via the wrapper) and E-259 substitutes the SQL body (golden zero-diff via the wrapper). The relocation being a *pure move* is what makes E-259's diff a legible old-SQL-vs-new-SQL comparison — the whole reason (c) was rejected. See Technical Notes §14.
