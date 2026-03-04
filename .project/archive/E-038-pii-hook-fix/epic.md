# E-038: Fix PII Pre-Commit Hook Silent Failure

## Status
`COMPLETED`

## Overview
The PII pre-commit hook is silently failing in the devcontainer because `install-hooks.sh` stores an absolute path in `core.hooksPath`. When the repo is cloned on macOS and then opened in a devcontainer, the host path does not exist inside the container, so git silently skips the hook. No `[pii-scan]` confirmation appears, and no error is raised -- the safety net is disabled without warning.

## Background & Context
The `scripts/install-hooks.sh` script runs `git config core.hooksPath "$REPO_ROOT/.githooks"`, which resolves `$REPO_ROOT` to an absolute path at execution time. Jason ran this on his macOS host, so `.git/config` contains `core.hooksPath = /Users/jason/Documents/code/baseball-crawl/.githooks`. Inside the devcontainer, the repo lives at `/workspaces/baseball-crawl/`, so the stored path does not exist and git silently skips hook execution.

The fix is simple: use a relative path (`git config core.hooksPath .githooks`). Git resolves relative `core.hooksPath` values from the repo root, so `.githooks` works in any environment -- macOS host, Linux devcontainer, any clone location. The devcontainer should also auto-run hook setup so new containers get the hook without manual intervention.

**Expert consultation:** No expert consultation required -- this is a bug fix to shell scripting and devcontainer configuration. No coaching data, API, database, or agent architecture involved.

## Goals
- PII pre-commit hook works reliably in both host and devcontainer environments
- Hook setup happens automatically in new devcontainers (no manual step required)
- `[pii-scan]` confirmation appears on every commit

## Non-Goals
- Changing the hook logic itself (`.githooks/pre-commit` is fine)
- Changing the PII scanner (`src/safety/pii_scanner.py`)
- Adding CI-based PII scanning (separate concern)

## Success Criteria
1. `scripts/install-hooks.sh` uses a relative path for `core.hooksPath`
2. Running `install-hooks.sh` inside the devcontainer results in `core.hooksPath = .githooks` in `.git/config`
3. Running `install-hooks.sh` on any host produces a portable `core.hooksPath` value
4. New devcontainers automatically have the hook configured (no manual `./scripts/install-hooks.sh` needed)
5. A test commit inside the devcontainer shows `[pii-scan]` or `[pii-hook]` confirmation in output

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-038-01 | Fix hooksPath to use relative path and auto-setup in devcontainer | DONE | None | general-dev |

## Technical Notes

### Root Cause
`install-hooks.sh` line 11: `git config core.hooksPath "$REPO_ROOT/.githooks"` expands `$REPO_ROOT` to an absolute path at execution time. This path is stored in `.git/config` and is not portable across environments.

### Fix Details (E-038-01)
Two changes in one story (they are tightly coupled and touch related files):

**1. Fix `scripts/install-hooks.sh`:**
- Change line 11 from `git config core.hooksPath "$REPO_ROOT/.githooks"` to `git config core.hooksPath .githooks`
- The `chmod +x` line can stay as-is (absolute path for chmod is fine -- it runs at execution time, not stored)
- Update the echo messages if needed for clarity

**2. Add hook setup to devcontainer `postCreateCommand`:**
- Append `&& ./scripts/install-hooks.sh` to the existing `postCreateCommand` in `.devcontainer/devcontainer.json`
- This ensures every new devcontainer gets the hook configured automatically
- The `postCreateCommand` runs from the workspace root, so `./scripts/install-hooks.sh` resolves correctly

**3. Verify the fix:**
- After running the updated `install-hooks.sh`, confirm `git config core.hooksPath` returns `.githooks` (not an absolute path)
- Confirm the hook is executable
- Run a test commit to verify `[pii-hook]` output appears

### User Action Required After Fix
The user will need to re-run `./scripts/install-hooks.sh` on their macOS host to overwrite the stale absolute path in `.git/config` with the new relative path. This is a one-time manual step. The CLAUDE.md documentation already says to run this after cloning, so no doc change is needed for that instruction.

### File Ownership
- `scripts/install-hooks.sh` -- modified by E-038-01
- `.devcontainer/devcontainer.json` -- modified by E-038-01
- `.githooks/pre-commit` -- NOT modified
- `CLAUDE.md` -- NOT modified (existing docs already say to run install-hooks.sh)

## Open Questions
- None.

## History
- 2026-03-04: Created. Single-story bug fix epic. Root cause: absolute path in core.hooksPath breaks cross-environment portability. Fix: relative path + devcontainer auto-setup.
- 2026-03-04: COMPLETED. E-038-01 DONE. Changed `git config core.hooksPath "$REPO_ROOT/.githooks"` to `git config core.hooksPath .githooks` in install-hooks.sh. Added `&& ./scripts/install-hooks.sh` to devcontainer postCreateCommand. No documentation impact. User reminder: re-run `./scripts/install-hooks.sh` on macOS host to overwrite stale absolute path in `.git/config`.
