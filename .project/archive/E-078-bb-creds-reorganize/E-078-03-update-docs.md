# E-078-03: Update docs for creds command reorganization

## Epic
[E-078: Reorganize bb creds CLI Commands](epic.md)

## Status
`DONE`

## Description
After this story is complete, all documentation referencing the old `bb creds refresh` command will be updated to use `bb creds import` (for curl-parsing) or `bb creds refresh` (for programmatic token refresh) as appropriate. CLAUDE.md Commands section will list the new commands with accurate descriptions.

## Context
E-078-01 renamed the curl-parsing command to `bb creds import`. E-078-02 created a new `bb creds refresh` for programmatic token refresh. Documentation still references the old command names and does not mention the new programmatic refresh command.

## Acceptance Criteria
- [ ] **AC-1**: `CLAUDE.md` CLI Commands section lists `bb creds import` with description "import GameChanger credentials from curl command" (or equivalent), replacing the old `bb creds refresh` entry.
- [ ] **AC-2**: `CLAUDE.md` CLI Commands section lists `bb creds refresh` with description "programmatic token refresh via POST /auth" (or equivalent) as a new entry.
- [ ] **AC-3**: `docs/api/error-handling.md` line 65 references `bb creds import` instead of `bb creds refresh` (this is about re-capturing credentials after a 401, which is the curl-import workflow).
- [ ] **AC-4**: `docs/admin/bootstrap-guide.md` lines 14 and 107 reference `bb creds import` instead of `bb creds refresh`.
- [ ] **AC-5**: `docs/admin/operations.md` lines 125 and 226 reference `bb creds import` instead of `bb creds refresh`.
- [ ] **AC-6**: `docs/admin/getting-started.md` line 154 references `bb creds import` instead of `bb creds refresh`.
- [ ] **AC-7**: Add `python scripts/refresh_credentials.py` to the Script Aliases section in `CLAUDE.md`, noting `bb creds import` as the preferred CLI equivalent. (This entry was previously missing from Script Aliases.)
- [ ] **AC-8**: `docs/admin/architecture.md` credential capture step (line 47) updated to mention `bb creds import` as the preferred CLI command for extracting auth tokens into `.env`.

## Technical Approach
Straightforward find-and-replace across documentation files. Each reference to `bb creds refresh` needs context assessment: if it refers to importing credentials from a curl command, replace with `bb creds import`. The CLAUDE.md Commands section needs both the renamed entry and the new entry added.

Key files to update:
- `/workspaces/baseball-crawl/CLAUDE.md` -- CLI Commands section and Script Aliases
- `/workspaces/baseball-crawl/docs/api/error-handling.md`
- `/workspaces/baseball-crawl/docs/admin/bootstrap-guide.md`
- `/workspaces/baseball-crawl/docs/admin/operations.md`
- `/workspaces/baseball-crawl/docs/admin/getting-started.md`

## Dependencies
- **Blocked by**: E-078-01, E-078-02 (docs must reflect final command names)
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md`
- `docs/api/error-handling.md`
- `docs/admin/bootstrap-guide.md`
- `docs/admin/operations.md`
- `docs/admin/getting-started.md`
- `docs/admin/architecture.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing tests
- [ ] All references to old `bb creds refresh` in docs are updated appropriately

## Notes
The `scripts/refresh_credentials.py` script name is NOT changed -- it remains as a legacy alias. The docs should reference it with `bb creds import` as the preferred equivalent.
