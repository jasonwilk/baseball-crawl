# E-058: Fix Relative Path Bug in Proxy Scripts

## Status
`READY`

## Overview
Three proxy scripts (`proxy-review.sh`, `proxy-report.sh`, `proxy-endpoints.sh`) use hardcoded relative paths that resolve incorrectly when the scripts are invoked from any directory other than the repo root. This causes "does not exist" errors even when session data is present.

## Background & Context
The user reported that `scripts/proxy-review.sh list` outputs "No sessions found (proxy/data/sessions/ does not exist)" despite sessions existing at `proxy/data/sessions/`. The root cause: all three scripts set `SESSIONS_DIR="proxy/data/sessions"` and `CURRENT_LINK="proxy/data/current"` as bare relative paths. These resolve relative to the caller's CWD, so running from `scripts/` looks for `scripts/proxy/data/sessions/` instead of `<repo-root>/proxy/data/sessions/`.

All three scripts were created in E-052 (Proxy Data Lifecycle) and share the same pattern.

SE consulted on fix approach (see History). Confirmed `BASH_SOURCE[0]` pattern over `$0` for consistency with existing scripts (`codex-review.sh`, `codex-spec-review.sh`).

## Goals
- All three proxy scripts work correctly regardless of the caller's working directory

## Non-Goals
- Changing script behavior, output format, or flags
- Modifying the proxy addons or proxy lifecycle scripts (those run on the Mac host and are not affected)

## Success Criteria
- Running `scripts/proxy-review.sh list` from the `scripts/` directory (or any other directory) correctly finds `proxy/data/sessions/` relative to the repo root
- Same for `scripts/proxy-report.sh` and `scripts/proxy-endpoints.sh` with all their flags
- Existing tests (if any) continue to pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-058-01 | Fix relative paths in proxy scripts | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Fix Pattern
Use `${BASH_SOURCE[0]}` (not `$0`) to match the existing project convention in `codex-review.sh` and `codex-spec-review.sh`. This also handles the sourcing edge case correctly.

Each script should add this preamble after `set -euo pipefail`:
```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SESSIONS_DIR="${REPO_ROOT}/proxy/data/sessions"
CURRENT_LINK="${REPO_ROOT}/proxy/data/current"
```

All three scripts live in `scripts/` (one level below the repo root), so `SCRIPT_DIR/..` reaches the repo root.

### Affected Scripts
1. `scripts/proxy-review.sh` -- lines 14-15
2. `scripts/proxy-report.sh` -- lines 11-12
3. `scripts/proxy-endpoints.sh` -- lines 12-13

### Usage strings
The `usage()` functions in `proxy-report.sh` and `proxy-review.sh` reference the relative paths in their help text. These should continue to show the user-friendly relative path (e.g., `proxy/data/sessions/`) rather than an absolute path -- the usage text is documentation, not runtime logic.

## Open Questions
None.

## History
- 2026-03-06: Created from user bug report
