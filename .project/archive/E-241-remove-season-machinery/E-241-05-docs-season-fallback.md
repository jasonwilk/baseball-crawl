# E-241-05: Update `architecture.md` + `operations.md` season_fallback documentation

## Epic
[E-241: Remove the cross-season machinery residue from the core](epic.md)

## Status
`DONE`

## Description
After this story is complete, the admin documentation no longer describes the
`season_fallback` flag, badge, or column, and no longer documents the
`program_type`→season-suffix taxonomy. The docs reflect year-only season derivation
and the post-006 `report_generation_runs` schema.

## Context
`docs/admin/architecture.md` and `docs/admin/operations.md` document the
`season_fallback` run-record column, the admin badge, a troubleshooting recipe that
names `derive_season_id_for_team_with_fallback()`, and the `program_type` value
list — all of which this epic removes. This is the documentation half of the
removal, routed to docs-writer via the doc gate. Blocked by E-241-01 (telemetry
strip), E-241-06 (derivation collapse — the troubleshooting recipe names the deleted
`derive_season_id_for_team_with_fallback()`), and E-241-02 (the column drop) so the
docs describe the settled end state. Per Technical Notes TN-9.

## Acceptance Criteria
- [ ] **AC-1**: `docs/admin/architecture.md` — the trust-flags table no longer
  lists `season_fallback` (≈L105), and the `program_type` value list (≈L180)
  reflects current reality (the column still exists for pitch-rule selection, but no
  season-suffix mapping is documented). Per Technical Notes TN-9.
- [ ] **AC-2**: `docs/admin/operations.md` — the `season_fallback` run-record column
  entry, the badge meaning, the troubleshooting recipe naming
  `derive_season_id_for_team_with_fallback()`, and the change-log references
  (≈L531, L554, L601, L607, L830) are removed or corrected to the year-only,
  post-006 reality. Per Technical Notes TN-9.
- [ ] **AC-3**: No remaining reference to `season_fallback` or the
  `program_type`→season-suffix taxonomy survives in `docs/admin/architecture.md` or
  `docs/admin/operations.md` (verify by grep).
- [ ] **AC-3b**: The stale compound-slug `season_id` EXAMPLES are updated to the
  year-only end state — `docs/admin/architecture.md:163` (`e.g., 2026-spring-hs`) and
  `docs/admin/operations.md:416` (`e.g., 2026-spring-hs`), plus any other
  `2026-spring-hs`-style example surfaced by a grep of both files for `spring-hs` /
  `summer-legion` / `summer-usssa`. (Per codex iteration-1 finding C4 — a
  season_fallback-only sweep leaves these contradicting the year-only reality.)
- [ ] **AC-4**: The `season_id_used` run-record field and other surviving trust
  signals (e.g. `identity_match_method = 'name_only'`) remain documented and
  accurate.

## Technical Approach
Edit the two admin docs per Technical Notes TN-9. The line numbers are recon
anchors — re-grep for `season_fallback` and `program_type` within the two files
before editing, since line numbers drift. Preserve documentation of the surviving
run-record fields and badges.

## Dependencies
- **Blocked by**: E-241-01, E-241-02, E-241-06
- **Blocks**: None

## Files to Create or Modify
- `docs/admin/architecture.md`
- `docs/admin/operations.md`

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Routed to docs-writer (the `docs/admin/` surface). Blocked by both code stories so
the docs describe the final state including the column drop.
