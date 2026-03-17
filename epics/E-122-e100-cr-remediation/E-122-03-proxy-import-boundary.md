# E-122-03: proxy.py Import Boundary Fix

## Epic
[E-122: E-100 Family Code Review Remediation (Wave 2)](epic.md)

## Status
`TODO`

## Description
After this story is complete, `src/cli/proxy.py` will import reusable proxy logic from a proper `src/` module instead of using `importlib` to load `scripts/proxy-refresh-headers.py`. The `scripts/` file becomes a thin wrapper, preserving its standalone usability while fixing the import boundary violation.

## Context
CR-6-10 confirmed that `src/cli/proxy.py` uses `importlib.util.spec_from_file_location` to load `scripts/proxy-refresh-headers.py`. This violates the project's import boundary rule: `src/` modules MUST NOT import from `scripts/`. The hyphenated filename in `scripts/` forced the importlib pattern, but the fix is to move the reusable logic into `src/` with a proper module name. See `/.project/research/cr-e100-family/verified-findings.md` finding CR-6-10 for exact lines.

## Acceptance Criteria
- [ ] **AC-1**: `src/cli/proxy.py` does not use `importlib` to load anything from `scripts/`.
- [ ] **AC-2**: The reusable logic previously in `scripts/proxy-refresh-headers.py` lives in a properly-named module under `src/` (e.g., `src/http/` or `src/cli/`).
- [ ] **AC-3**: `scripts/proxy-refresh-headers.py` still works as a standalone script (thin wrapper importing from `src/`).
- [ ] **AC-4**: `bb proxy refresh-headers` executes without import errors and produces expected output.
- [ ] **AC-5**: All existing tests pass.

## Technical Approach
See epic Technical Notes TN-3 for the import boundary fix strategy. Identify what functions/logic `proxy.py` actually uses from the script, move that logic to a `src/` module, update both `proxy.py` and the script to import from the new location. See `/.project/research/cr-e100-family/verified-findings.md` finding CR-6-10.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/cli/proxy.py`
- `scripts/proxy-refresh-headers.py`
- New module under `src/` (e.g., `src/http/proxy_refresh.py` — exact location at implementer's discretion)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
