# E-084: Fix resolve_proxy_from_dict None Value Crash

## Status
`COMPLETED`

## Overview
Fix an `AttributeError` crash in `resolve_proxy_from_dict()` when `dotenv_values()` returns `None` for valueless `.env` keys. A bare `PROXY_ENABLED` line (no `=` sign) causes `dotenv_values()` to return `{'PROXY_ENABLED': None}`, and `.strip()` on `None` raises `AttributeError`.

## Background & Context
Discovered as finding F2 during the E-080 Codex code review. The bug is in E-079 proxy code (`src/http/session.py`). SE confirmed the bug is real and reproduced it. The fix is two lines plus tests.

The root cause: `dict.get("KEY", "")` returns the default `""` only when the key is absent. When `dotenv_values()` maps a key to `None` (valueless entry), `.get()` returns `None` and `.strip()` crashes.

No expert consultation required -- this is a straightforward defensive-coding fix with clear reproduction steps.

## Goals
- Eliminate `AttributeError` crash when `.env` contains valueless proxy keys
- Add test coverage for `None` values in the env dict

## Non-Goals
- Refactoring `get_proxy_config()` (reads `os.environ`, which never returns `None`)
- Changing `dotenv_values()` behavior or switching to `load_dotenv()`

## Success Criteria
- `resolve_proxy_from_dict({"PROXY_ENABLED": None}, "web")` returns `None` without raising
- `resolve_proxy_from_dict({"PROXY_ENABLED": None, "PROXY_URL_WEB": "http://x"}, "web")` returns `None` (disabled)
- `resolve_proxy_from_dict({"PROXY_ENABLED": "true", "PROXY_URL_WEB": None}, "web")` returns `None` with warning
- All existing tests pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-084-01 | Guard against None values in resolve_proxy_from_dict | DONE | None | - |

## Dispatch Team
- software-engineer

## Technical Notes
- The fix applies the `(value or "")` pattern instead of relying on `.get(key, "")`, because `dotenv_values()` can map keys to `None`.
- Only `resolve_proxy_from_dict()` is affected. `get_proxy_config()` reads from `os.environ`, which never stores `None` values.
- Two callsites need the fix: the `PROXY_ENABLED` check (line 128) and the `PROXY_URL_{profile}` check (line 133).

## Open Questions
- None

## History
- 2026-03-09: Created from E-080 Codex code review finding F2
- 2026-03-09: E-084-01 dispatched and completed. Two-line fix in resolve_proxy_from_dict() + 3 new tests. Code-reviewer APPROVED with no findings. Documentation assessment: No documentation impact. Context-layer assessment: (1) New convention: no. (2) Architectural decision: no. (3) Footgun: no -- the `(value or "")` pattern is standard Python. (4) Agent behavior: no. (5) Domain knowledge: no. (6) New CLI/workflow: no. Epic COMPLETED.
