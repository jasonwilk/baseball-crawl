# E-256-04: Extract a client-free lifecycle module + relocate the season fetch from generator.py

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

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

## PM AC-Verification (2026-07-09)
**ALL SEVEN ACs PASS.** Verified in the worktree, AC-6 first per PM's stated order.

- **AC-6 PASS.** `tests/test_report_golden.py` zero-diff (empty `git diff --stat` and `git status --porcelain`), 4 passed. The bracket holds through the relocation, as §14 requires.
- **AC-3/AC-4 PASS.** PM read `get_season_pitching` (`src/api/db.py:491-524`): raw SUM columns only — **no `era`/`k9`/`whip`/`strike_pct`**; **no `perspective_team_id` filter** (E-259's); `ORDER BY COALESCE(psp.ip_outs,0) DESC, p.last_name ASC` over the stored aggregate columns, exactly the pre-move clause §14 records. `_query_batting`/`_query_pitching` remain in `generator.py:392,407` as wrappers; `_compute_pitching_rates`/`_apply_name_cascade` remain at `:423,446`. `batting_recompute_select`/`pitching_recompute_select` intact.
- **AC-5 PASS, both edges.** `src/api/db.py`'s only `src.*` import is `src.db.paths` (`:22`) — the fetch added **zero** imports, so `db.py` is still a leaf. `lifecycle.py` imports (`:31-33`) `src.api.db`, `src.api.helpers`, `src.util.timezone` — and **nothing from `src.reports.*`**, so PM's unwritten back-import edge holds too.
- **AC-1/AC-2 PASS.** `lifecycle.py` imports none of the heavy set. Its module docstring (`:10-13`) states the one-way direction as an invariant, not just a fact.
- **AC-7 PASS.** 3803, RC=0, unchanged.

**Ruling — cohesion over line range: APPROVED. `_fail_report` and `_update_report_failed` correctly stay in `generator.py`.** §13's `:2577-3034` was a *description* of where the code sat, not a specification of the split; the Technical Approach says outright *"do not prescribe the internal module layout beyond the client-free constraint."* And the line range was stale regardless (real tail `:2574`, file 3,031 lines). SE's reasoning is exactly right and lands on the edge PM added mid-story: moving `_fail_report` would force `generator` to import a generation-internal helper **back out of** `lifecycle`, which is the backward import AC-5's unwritten edge forbids. **Cohesion is what the constraint implies; the line range was only where the constraint happened to fall.** AC-1's "contiguous tail plus scattered lifecycle helpers" is satisfied — its operative gate is client-freeness, not line arithmetic.

**Ruling — the two out-of-list files are MANDATORY, not optional.** `src/api/main.py:78` (FastAPI lifespan imports `reap_stale_generating_reports`) and `src/cli/report.py:37` (`bb report list` / `cleanup`) would be `ImportError` without them. Found by AST-walking every `ImportFrom` targeting `src.reports.generator` and intersecting with the move set — enumerating, not trusting the list. **Tenth undercount.**

**Ruling — the two non-identical moved symbols: both ACCEPTED.** The Sphinx cross-ref demotion is correct (the target left the module). `_get_base_url()` → `get_app_url()` is not merely acceptable but *better*: `get_app_url()` is CLAUDE.md's canonical APP_URL seam, and `_get_base_url` is a two-line wrapper over it that stays in `generator.py` only for its two remaining callers. Moving a wrapper into a new module and having it delegate upward would have been the wrong shape.

**PM-surfaced: a canonical entry point moved, and CLAUDE.md still names the old module.** `cascade_delete_team` (`lifecycle.py:489`) and `cleanup_orphan_teams` (`:545`) are named by CLAUDE.md's Architecture bullet as living in `src/reports/generator.py`. Routed to **story 15 as AC-6** (re-point the path; the rule itself is unchanged and still true). Not story 04's edit to make — CLAUDE.md is CA's.

**PM-surfaced hazard for CR — the two path constants are now INDEPENDENT module globals.** `_REPO_ROOT`/`_REPORTS_DIR` are canonical in `lifecycle.py:37-38`; `generator.py:58-59` imports them, binding *copies* into its own namespace. So `patch("src.reports.generator._REPORTS_DIR")` rebinds only generator's name, and `patch("src.reports.lifecycle._REPORTS_DIR")` only lifecycle's. SE's module docstring (`:15-19`) states this precisely and correctly. **But `generate_report` opportunistically calls `cleanup_expired_reports()` (CLAUDE.md, Commands), which now reads *lifecycle's* constant.** A test that patches only `generator._REPORTS_DIR` and runs `generate_report` therefore lets the expiry sweep resolve against the **real repo root**. It is safe today only because the sweep and reaper are DB-driven and the test DB holds no matching rows — a second-order guard, not the patch. Worth CR confirming no test exercises both sides with one side patched, and worth a comment at the `generate_report` call site, since the safety comes from the DB, not from the seam.

## PM AC-Verification Round 2 (2026-07-09)
**AC-1, AC-2, AC-7 re-verified: PASS.** (AC-3/4/5/6 undisturbed — the fix touches only the connection seam.)

- **AC-1/AC-2 PASS.** `lifecycle.py:44-66` adds `_conn_scope`; `reap_stale_generating_reports(conn=None)` and `cleanup_expired_reports(conn=None)` both accept an injected connection. Imports unchanged — still nothing from `src.reports.*`. `generator.py:1460-1462` opens through **its own** `get_connection` and injects.
- **AC-7 PASS.** 3804 (3803 + the falsifier), RC=0. Golden test still zero-diff.

**PM's round-1 hazard was real, and PM's own framing was one call too shallow.** PM wrote *"the guard is the database, not the seam."* CR found **the database in that sentence is not the test database**: `get_connection` detaches by the same mechanism *one call earlier* than `_REPO_ROOT`, so the sweep never opens the test DB — it calls the real `resolve_db_path()`, and `_REPO_ROOT` is never reached. Corrected: safe only because the **live** `data/app.db` happened to hold zero qualifying rows, and because `generate_report`'s by-design exception swallow hid that the sweep ran at all. 43 tests drive `generate_report` with zero lifecycle-side patches.

CR's verdict on PM's proposed remedy is right, and PM adopts it: *"Should the call site carry a comment recording why it's safe? No — because it isn't."* A comment documenting a second-order property that rests on live-DB contents is the wrong artifact. **The fix deletes the property.** PM's instinct (name the second-order guard) was correct; PM's prescription (document it) was not.

**Ruling — `list_reports` (`lifecycle.py:688`, still resolving `lifecycle.get_connection`): CLOSE IT, do not flag it.** Flag-don't-fix is the right default and PM would normally uphold it. It loses here on three counts:
1. **The fix is smaller than the flag.** `conn: sqlite3.Connection | None = None` plus the `_conn_scope` already in the file, defaulting to today's behavior. Its only caller (`bb report list`) passes nothing — **zero caller changes, zero behavior change.** The paragraph explaining why one of three lifecycle entry points is asymmetric is longer than the patch.
2. **An asymmetric seam is an invitation.** Two of three entry points take a connection; one resolves a module global. The next reader must reconstruct why — and that reconstruction is exactly the reasoning that cost CR two rounds and a falsifier.
3. **Same class, still open.** CLAUDE.md's *"Prevention over cleanup"* applies literally. SE's named residual — "someone later calls `list_reports()` from inside a sandboxed path" — is not hypothetical: `reports_admin.py` already renders an admin list off the same `list_reports_with_runs` join, and consolidating it onto `lifecycle.list_reports` is the obvious next step.

This does **not** contradict flag-don't-fix. That principle guards against widening a diff to chase *adjacent* problems. This is not adjacent — it is the same defect, in the same module, found by the same falsifier, left half-closed.

**On the falsifier.** SE disabling falsifier #1 to confirm #2 fires independently is *enumerate-don't-aggregate* applied to its own test: two assertions are an aggregate until each is shown to fire alone. Its stated reason — *"a test with one real assertion and one dead one is the shape I shipped last round"* — is the epic's discipline turned on its author. The revert-and-run happened in a scratchpad `tar` copy: the out-of-worktree constraint's first real use, on the one falsification that genuinely required reverting `src/`.

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
