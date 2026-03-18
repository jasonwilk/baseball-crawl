# E-128-07: Production Runbook Credential Step

## Epic
[E-128: Credential Workflow Redesign](epic.md)

## Status
`TODO`

## Description
After this story is complete, `docs/production-deployment.md` will include a GameChanger credential setup step with current variable names and a reference to `bb creds setup web`. The deprecated variable names (`GC_TOKEN`, `GC_COOKIE`) will be removed. An operator following the production runbook will have a complete path from stack deployment to authenticated API access.

## Context
The docs-writer audit (2026-03-18) found that `docs/production-deployment.md` step 2.3 creates `.env` from `.env.example` but only lists infrastructure variables. It references deprecated variable names (`GC_TOKEN`, `GC_COOKIE`) and never mentions the current `GAMECHANGER_*` credential variables. A new production operator following the runbook gets a running stack with no API access.

## Acceptance Criteria
- [ ] **AC-1**: `docs/production-deployment.md` includes a numbered step for GameChanger credential setup, positioned between `.env` creation and `docker compose up`.
- [ ] **AC-2**: The credential step lists the minimum required variables (`GAMECHANGER_USER_EMAIL`, `GAMECHANGER_USER_PASSWORD`) and references `bb creds setup web` as the bootstrap command.
- [ ] **AC-3**: All deprecated variable references (`GC_TOKEN`, `GC_COOKIE`, `scripts/refresh_credentials.py`) are removed or corrected.
- [ ] **AC-4**: The credential step is self-contained: it lists the minimum required `.env` variables and the `bb creds setup web` command inline. It does NOT link to `docs/admin/bootstrap-guide.md` (that doc will be stale until E-128-09 updates it). If additional context is needed, link to `docs/api/auth.md` which remains current.

## Technical Approach
Read `docs/production-deployment.md` to identify the exact location and deprecated references per Technical Notes TN-6. The update is a targeted edit -- add one step, update one step, remove stale references.

Key files to study: `docs/production-deployment.md` (step 2.3 and surrounding context), `docs/admin/bootstrap-guide.md` (cross-reference target).

## Dependencies
- **Blocked by**: E-128-02 (the runbook references `bb creds setup web`, which must exist first)
- **Blocks**: None

## Files to Create or Modify
- `docs/production-deployment.md` -- add credential step, remove deprecated references

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No broken internal links
- [ ] No credential values in documentation
