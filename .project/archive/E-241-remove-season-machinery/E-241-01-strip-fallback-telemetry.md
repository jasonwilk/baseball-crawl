# E-241-01: Strip the season_fallback telemetry chain (generator / db / admin)

## Epic
[E-241: Remove the cross-season machinery residue from the core](epic.md)

## Status
`DONE`

## Description
After this story is complete, the `season_fallback` telemetry no longer exists
anywhere in the application code: the generator no longer captures or writes it, the
admin-list read no longer SELECTs it, and the `/admin/reports` "season fallback"
badge is gone. The generator derives its season via the plain
`derive_season_id_for_team` wrapper (no fallback capture). The
`report_generation_runs.season_fallback` column is left physically present but
unreferenced (its drop is E-241-02), and the season-derivation internals are left
intact (their collapse is E-241-06). No report's stat values change.

## Context
This is the first of the two SE code stories and runs first by design (per Technical
Notes TN-4): stripping the telemetry removes the generator's only *direct* call to
`derive_season_id_for_team_with_fallback`, which lets E-241-06 then delete that
variant against zero direct callers without a red boundary. The orange "season
fallback" badge — the exact thing the operator pointed at — fires on every report
because every scouted opponent yields the year-only fallback; removing the telemetry
chain deletes the signal at its surfaces. This story leaves the column present (so
its own staging boundary stays green) and does NOT touch `tests/test_migrations.py`
(E-241-02 owns it) or the derivation internals (E-241-06 owns them). Per Technical
Notes TN-3, TN-4, TN-7.

## Acceptance Criteria
- [ ] **AC-1**: The generator no longer captures or writes `season_fallback` — the
  `self.season_fallback` init, the `derivation.fallback_used` capture, the
  `season_fallback` argument in the run-record write, AND the now-stale
  degraded-confidence comment block at `generator.py:2217-2220` (which still names
  `season_fallback` and falsely claims "It stays as operator-only telemetry") are
  removed/corrected. The generator derives its season via `derive_season_id_for_team`
  (the 2-tuple wrapper), and the `season_id_used` run-record write is preserved. Per
  Technical Notes TN-4.
- [ ] **AC-2**: `grep -n season_fallback` over THIS story's owned files
  (`src/reports/generator.py`, `src/api/db.py`, `src/api/templates/admin/reports.html`,
  `src/api/routes/reports_admin.py`) returns no matches — the generator
  capture/write/comment (AC-1), the `api/db.py` admin-list SELECT, the `reports.html`
  badge block, and the `reports_admin.py` docstring reference are all removed. (The
  src-WIDE `grep -rn season_fallback src/` zero-match is E-241-06's AC-7, because the
  last remaining reference — the `SeasonDerivation` docstring at
  `loaders/__init__.py:52` — is removed when 06 deletes that dataclass; this story
  must NOT touch `loaders/__init__.py`, per AC-5.)
- [ ] **AC-3**: `/admin/reports` renders no "season fallback" badge; the
  name-only-match badge and every other admin-list trust signal are unchanged.
- [ ] **AC-4**: `report_generation_runs.season_fallback` is still physically present
  in the schema and no code reads or writes it; `tests/test_migrations.py` is NOT
  modified by this story. Per Technical Notes TN-7.
- [ ] **AC-5**: The season-derivation internals in `src/gamechanger/loaders/__init__.py`
  (the `_with_fallback` variant, `SeasonDerivation`, `_PROGRAM_TYPE_SUFFIX`) are NOT
  modified by this story (E-241-06 owns them).
- [ ] **AC-6**: All affected unit tests pass. Tests asserting the
  `season_fallback`-drives-degraded coupling, the badge, or the column write are
  updated to the new contract; no report stat-value assertion changes. Per Technical
  Notes TN-3.
- [ ] **AC-7**: `tests/test_report_golden.py` passes with the golden JSON
  (`tests/fixtures/golden/report_stats.json`) un-regenerated, and
  `tests/test_aggregate_parity.py` passes — these are the in-suite zero-stat-change
  gate (the `bb report verify-aggregates` CLI needs `data/` and cannot run
  in-worktree; `test_aggregate_parity.py` is its in-suite proxy). This de-scope must
  not perturb stat computation. Per Technical Notes TN-3.

## Technical Approach
In `src/reports/generator.py`, switch the season-derivation call to the plain
`derive_season_id_for_team` wrapper and remove the `season_fallback` capture/write
(keep `season_id_used`). Remove the column from the `api/db.py` admin-list SELECT,
delete the `reports.html` badge block, and correct the `reports_admin.py` docstring.
Update the affected report/admin tests to the new contract. See Technical Notes TN-4
for the sequencing rationale and the full reference set. Do not touch
`loaders/__init__.py`, `tests/test_migrations.py`, or any fixture.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-241-02, E-241-05, E-241-06

## Files to Create or Modify
- `src/reports/generator.py`
- `src/api/db.py`
- `src/api/templates/admin/reports.html`
- `src/api/routes/reports_admin.py`
- `tests/test_report_generator.py`
- `tests/test_report_renderer.py`
- `tests/test_report_e2e_degraded.py`
- `tests/test_admin_reports.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-241-02**: a codebase with no reader/writer of
  `report_generation_runs.season_fallback`, so the column can be dropped safely.
- **Produces for E-241-06**: a generator that no longer calls
  `derive_season_id_for_team_with_fallback` directly, so the variant can be deleted
  against zero direct callers.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The sole consumer of `SeasonDerivation.fallback_used` is this generator write
(`generator.py:1682-1697`), so after this story the field is computed but unread;
E-241-06 deletes the computation. The degraded-confidence comment at
`generator.py:2217-2220` is removed/corrected in this story (AC-1): it still names
`season_fallback` and falsely says "It stays as operator-only telemetry" — the epic
removes that telemetry, so leaving the comment would both contradict reality and
defeat the AC-2 `grep` zero-match gate. No scoring MATH changes (the
`degraded_confidence` term already excludes season_fallback) — only the stale comment
is cleaned. Filename slug retains "collapse-derivation" from the original combined
draft; the story header and the epic Stories table are authoritative — this story is
the telemetry strip only.
