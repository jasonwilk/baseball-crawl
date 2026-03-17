# E-122-05: Credentials Module — Publicize Private API Names

## Epic
[E-122: E-100 Family Code Review Remediation (Wave 2)](epic.md)

## Status
`TODO`

## Description
After this story is complete, `_ALL_PROFILES` and `_run_api_check` in the credentials module will be renamed to public names (no leading underscore), and all consumers will be updated. This eliminates the coupling risk of importing private names across module boundaries.

## Context
CR-6-W1 confirmed that `src/cli/creds.py` imports `_ALL_PROFILES` and `_run_api_check` from `src/gamechanger/credentials`. Leading underscore means module-private by Python convention. Cross-module import of private names creates fragile coupling — a maintainer could reasonably rename or remove a private name without checking external consumers. See `/.project/research/cr-e100-family/verified-findings.md` finding CR-6-W1.

## Acceptance Criteria
- [ ] **AC-1**: The credentials module exports `ALL_PROFILES` (no leading underscore) instead of `_ALL_PROFILES`.
- [ ] **AC-2**: The credentials module exports `run_api_check` (no leading underscore) instead of `_run_api_check`.
- [ ] **AC-3**: All consumers of the old private names are updated to use the new public names.
- [ ] **AC-4**: No remaining imports of `_ALL_PROFILES` or `_run_api_check` exist in the codebase (grep verification).
- [ ] **AC-5**: All existing tests pass.

## Technical Approach
Rename the symbols in the credentials module source, then find and update all import sites. The verified findings file at `/.project/research/cr-e100-family/verified-findings.md` (CR-6-W1) identifies `src/cli/creds.py` as the known consumer — grep for additional consumers before renaming.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/credentials.py` (or `src/gamechanger/credentials/__init__.py` — verify module structure)
- `src/cli/creds.py`
- `tests/test_cli_creds.py` (patches `_run_api_check` by string name at lines 654, 740, 743 — patch targets must be updated)
- Any other files importing `_ALL_PROFILES` or `_run_api_check`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
