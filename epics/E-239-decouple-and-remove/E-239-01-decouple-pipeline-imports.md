# E-239-01: Extract the Surviving Admin Surface; Delete `admin.py` (Sever Chain 1)

## Epic
[E-239: Decouple Pipeline Imports, Then Remove the Unused Surfaces](epic.md)

## Status
`TODO`

## Description
After this story is complete, the surviving admin routes (reports admin + user management) live in a focused new module, `src/api/main.py` registers that module instead of `src/api/routes/admin.py`, and the doomed `admin.py` is deleted. This severs coupling chain 1 (`main.py → admin.py → trigger → crawl/load`, plus the `bridge`/`team_resolver`/`db.merge` imports) so the pipeline and member/opponent modules become deletable without breaking app startup. The reports admin surface and login continue to work; the dead team-management/opponent/programs routes and their templates are gone.

## Context
This is the **gate story** for chain 1 (§6 rule 2: decouple imports before deleting modules). Per the SE recon (`.project/research/E-239-deletion-inventory.md` §1), extraction-then-delete is the lowest-risk approach: it is purely additive + re-registration, severs all four problem imports at once (they stay behind with the deleted file), and avoids re-editing the 3400-line `admin.py` across every removal story. The surviving keep-set is reports + user-management (user admin is auth/E-023 infrastructure, NOT quarantined); the programs routes are scoped OUT per the PM ruling (Technical Notes §J) but the `programs` **table** stays. Extraction inherently removes the dead admin routes, so this story also handles their template deletion, the `_subnav` rebuild, the `base.html` "Admin" nav retarget, and the now-dead admin route tests.

## Acceptance Criteria
- [ ] **AC-1**: The surviving admin routes (reports list/generate/delete + their helpers; user-management routes) are extracted into a focused new module that imports the canonical `user_is_admin` from `src.api.auth`; the new module imports none of `src.pipeline.trigger`, `src.gamechanger.bridge`, `src.gamechanger.team_resolver`, or `src.db.merge`. `src/api/main.py` registers the new router.
- [ ] **AC-2**: `src/api/routes/admin.py` is deleted (`git rm`). After deletion, `import src.api.main` no longer transitively imports `src.pipeline` (verified by a test asserting the pipeline package is absent from `sys.modules` after a fresh app import, or equivalent).
- [ ] **AC-3**: The reports admin surface and login work: `login → /admin/reports → generate → delete report` (in-suite report/route tests green). The in-suite check RENDERS `/admin/reports` (asserts the template renders, not merely a 200 status code) — because `reports.html` includes `_subnav.html`, a render assertion is what catches a leftover `get_unresolved_opponent_count()` call (`UndefinedError`) or a broken include. The report-delete cascade delegation to `cascade_delete_team`/`_delete_report` (generator.py) is preserved and functional (Technical Notes §E).
- [ ] **AC-4**: The orphaned admin templates are deleted (`confirm_delete`, `confirm_team`, `edit_team`, `merge_teams`, `opponent_resolve`, `opponents`, `teams.html`, `programs.html`); `reports.html`, `users.html`, `edit_user.html` remain; `_subnav.html` is rebuilt to only surviving tabs AND no longer calls `get_unresolved_opponent_count()` (the `_subnav.html:4` `{% set %}` call). The `get_unresolved_opponent_count` module-level import (`admin.py:60`) and its `templates.env.globals[...]` registration (`admin.py:90`) vanish with the `git rm` of `admin.py` (AC-2); the `db.py` helper itself is deleted later in E-239-05. `base.html`'s "Admin" link is retargeted off `/admin/teams` → `/admin/reports` (per SE artifact §5).
- [ ] **AC-5**: The deleted team-management/opponent/programs routes return 404; the `programs` table is untouched (Technical Notes §J).
- [ ] **AC-6**: Tests are handled per the discrimination rule (Technical Notes §F / SE §4): the dead admin route tests (`test_admin_teams`, `test_admin_opponents`, `test_admin_connect`, `test_admin_resolve`, `test_admin_merge`, `test_admin_programs`, `test_admin_gc_uuid_edit`) are deleted; `test_admin.py`/`test_admin_routes.py` are adjusted to the surviving surface; `test_admin_reports.py` and the report tests pass. Epic A goldens + parity unchanged/green (Technical Notes §A). Full suite green.

## Technical Approach
Create the new module with the surviving routes/helpers and the route guard (delegate to `user_is_admin`). Re-point `main.py`. `git rm admin.py`. Delete the orphaned templates, rebuild `_subnav.html`, retarget `base.html`. Note: the now-dead `api/db.py` opponent helpers (`finalize_opponent_resolution` et al.) and `src/db/merge.py` become unreferenced after this story but are deleted in E-239-05 (they are harmless dead code in the interim). Add the import-isolation test. Re-grep live line numbers per Technical Notes §B.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-239-02, E-239-03, E-239-04, E-239-05, E-239-06

## Files to Create or Modify
- CREATE the new surviving-admin module under `src/api/routes/` (e.g. `reports_admin.py`; final name at implementer's discretion — it carries reports + user-management)
- MODIFY `src/api/main.py` (register the new router; drop the admin import)
- DELETE `src/api/routes/admin.py`
- DELETE admin templates: `confirm_delete.html`, `confirm_team.html`, `edit_team.html`, `merge_teams.html`, `opponent_resolve.html`, `opponents.html`, `teams.html`, `programs.html` (under `src/api/templates/admin/`)
- MODIFY `src/api/templates/admin/_subnav.html` (rebuild to surviving tabs)
- MODIFY `src/api/templates/base.html` ("Admin" link retarget)
- DELETE / ADJUST admin route test files per SE §4
- ADD an import-isolation test (no `src.pipeline` in `sys.modules` after app import)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-239-04**: chain 1 severed — `trigger`/member crawlers/loaders have no app importer.
- **Produces for E-239-05**: `db.merge`, `team_resolver`, and the `api/db.py` opponent helpers are now unreferenced (admin.py was their consumer) and ready to delete.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written/adjusted and passing (incl. import-isolation test)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Extraction is additive + re-registration (low risk per SE §1). The full operator-run canary (Technical Notes §A) is an epic-closure gate; this story's ACs assert the in-suite guards only.
