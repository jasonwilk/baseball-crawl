# E-247-05: Consolidate reports generator plays-scope SQL + literals

## Epic
[E-247: Twin-Method & Duplicated-Block Extractions](epic.md)

## Status
`TODO`

## Description
After this story is complete, the reports generator's three parallel plays-scope SQL blocks will share one scope builder, the hardcoded empty-result dict will be a single constant, and the inlined UTC-timestamp format will use one shared helper.

## Context
The sweep's M5 finding, in the reports layer:
- Three `_query_plays_*` functions carry parallel SQL differing only in `game_ids`-IN vs `games`-JOIN+season scope (~6+ blocks) — `src/reports/generator.py:1061-1099`, `:1135-1172`, `:1213-1335`. Scope-branch divergence causes silent denominator drift.
- `_query_plays_team_stats` hardcodes its 6-key empty dict twice (`:374-400`).
- `_utcnow_iso` format is inlined in two other modules (`src/reports/morning_run.py:277`, `src/api/routes/reports_admin.py:542`).
- `_query_record` / `_query_runs_avg` make two scans over the same games set (`:570-590`).

The SQL consolidation is the value here; the two-scan efficiency note is N=1/per-report and low value — address it only as a natural side effect, never as a goal.

## Acceptance Criteria
- [ ] **AC-1**: Given the three `_query_plays_*` functions carry parallel plays-scope SQL, when the story completes, then a single scope builder produces the FROM/WHERE + params for the `game_ids`-IN and `games`-JOIN+season cases, and the three functions compose their query around it (the scope SQL is expressed once).
- [ ] **AC-2**: Given the consolidated scope builder (HARD GATE — stats integrity, per epic Technical Notes; these queries produce stat denominators — charted-PA, perspective scoping, season scope — so scope-branch divergence is silent stat corruption), when each of the three plays queries runs against representative data via a golden-fixture/characterization `pytest` test, then its result set is byte-identical to the pre-story query (identical denominators and rows). Proven by test, not inspection. If equivalence cannot be proven for any of the three, that query is left unconsolidated rather than shipped on faith.
- [ ] **AC-3**: Given the 6-key empty dict is hardcoded twice, when the story completes, then it is a single named constant referenced by both sites.
- [ ] **AC-4**: Given `_utcnow_iso` is inlined in two other modules, when the story completes, then those modules use one shared timestamp helper producing the identical formatted string.
- [ ] **AC-5**: Given the consolidations, when the report-generator test modules (`tests/test_report_generator.py`, `tests/test_report_golden.py`, `tests/test_morning_run.py`, `tests/test_admin_reports.py`), including the AC-2 golden-fixture plays-scope test, run, then they pass. (The full-suite-green check across `tests/` is the epic-level closure gate — Technical Notes "Closure Gate (blocking)" — not a per-story AC, because the whole-suite run is only authoritative in the merged main checkout, not the worktree.)

## Technical Approach
Report locations (re-verify before acting): `src/reports/generator.py:1061-1099`, `:1135-1172`, `:1213-1335`, `:374-400`, `:570-590`; `src/reports/morning_run.py:277`; `src/api/routes/reports_admin.py:542`. The sweep suggests a `_plays_scope(...) -> (from_where_sql, params)` builder, one `_EMPTY_PLAYS_TEAM` constant, and promoting `_utcnow_iso` to a shared util (illustrative). The plays-scope consolidation must be provably SQL-equivalent — the denominators feed report stats, so any divergence is a correctness risk. The two-scan fold is optional and only if it falls out naturally.

## Dependencies
- **Blocked by**: E-247-03 (both touch `src/reports/generator.py`)
- **Blocks**: E-247-07 (both touch `src/api/routes/reports_admin.py`)

## Files to Create or Modify
- `src/reports/generator.py`
- `src/reports/morning_run.py`
- `src/api/routes/reports_admin.py` (only the inlined `_utcnow_iso` site at `:542`)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-247-07**: This story touches `src/api/routes/reports_admin.py` (the `_utcnow_iso` site at `:542`). E-247-07 also edits `reports_admin.py` (`:543`) and must run after this story.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Plays-scope queries verified SQL-equivalent (denominators unchanged)
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Runs after E-247-03 (shared `generator.py`) and before E-247-07 (shared `reports_admin.py`). Silent denominator drift is the hazard the SQL consolidation guards against — equivalence verification is mandatory.
