# E-248-02: Extract shared send-with-retries helper across the 4 live verbs

## Epic
[E-248: GC API Client Error-Ladder Refactor](epic.md)

## Status
`TODO`

## Description
After this story is complete, the 401/403/429/5xx error/retry ladder will live in a single shared helper, and each of the 4 LIVE client verbs (`get`, `get_public`, `get_paginated`, `post_json`) will be a thin wrapper over it. This is a pure behavior-preserving dedup — the dead verbs `post()`/`delete()` are already removed by E-246-07, so there is no 5xx-gap to close and no sanctioned behavior change.

## Context
Under the resolved Option-A scope (see epic Background), `post()`/`delete()` are deleted as dead code by E-246-07 (dispatches first). What remains is 4 live verbs that re-implement near-identical status handling. Extracting one shared helper makes a future retry-policy change a single edit. The 4 live verbs already share consistent 5xx handling, so the consolidation must be **byte-for-byte behavior-preserving**: the E-248-01 characterization tests must keep passing with NO assertion changes. The verbs' contracts differ (see epic Technical Notes "Per-verb status matrix"), so the shared helper must be parameterizable enough to express `get_public`'s no-auth contract alongside the full ladder of the other three.

## Acceptance Criteria
- [ ] **AC-1**: Given the 4 live verbs re-implement the status ladder, when the story completes, then a single shared send-with-retries helper owns the 401/403/429/5xx handling and each of `get`, `get_public`, `get_paginated`, `post_json` delegates to it as a thin wrapper. The helper is parameterized so `get_public`'s no-401-auth contract and the others' full ladder both route through it without changing either's behavior.
- [ ] **AC-2**: Given the helper, when the verbs are reduced to wrappers, then each verb keeps its existing public signature and success-path response shape (no caller of the client changes).
- [ ] **AC-3**: Given there is no sanctioned behavior change (the only 5xx gap was the deleted `post()`), when the refactor lands, then the E-248-01 characterization tests pass **with no assertion changes** — the test suite, unchanged, is the artifact of record proving equivalence.
- [ ] **AC-4**: Given the refactor (HARD GATE — stats-collection integrity, per epic Technical Notes; a regression here drops/misses games), when the E-248-01 per-verb tests run, then they ALL pass unchanged. If any assertion must change for them to pass, the refactor altered behavior and is cut/deferred rather than shipped.
- [ ] **AC-5**: Given the refactor, when `tests/test_client.py` runs in full (the E-248-01 characterization suite plus all pre-existing client tests), then it passes. (The full-suite-green check across `tests/` is the epic-level closure gate, not a per-story AC — it is only authoritative in the merged main checkout, not the worktree.)
- [ ] **AC-6**: Given the HTTP-discipline rule, when the verbs send requests, then headers, session behavior, and rate-limiting are unchanged — only the error/retry handling was consolidated (per `.claude/rules/http-discipline.md`).

## Technical Approach
Verified locations (re-confirm before acting): live verbs at `src/gamechanger/client.py:233` (`get_paginated`), `:389` (`get`), `:426` (`get_public`), `:611` (`post_json`); private helper `_get_with_retries` at `:512` may be subsumed by the new shared helper. The sweep suggests extracting `_send_with_retries(method, url, *, success_codes, parse_json, requires_auth, ...)` (or at minimum `_raise_for_error_status`) with verbs as thin wrappers (illustrative — the implementing agent owns the final shape). The helper must accommodate `get_public`'s no-auth path. Do not change request construction, headers, or session/rate-limit behavior. Assumes `post()`/`delete()` are already deleted by E-246-07.

## Dependencies
- **Blocked by**: E-248-01
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/client.py`
- `tests/test_client.py` (should NOT need assertion changes — if the refactor is behavior-preserving, the E-248-01 suite passes as-is; file exists today)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] E-248-01 characterization tests pass with NO assertion changes (proof of equivalence)
- [ ] Headers/session/rate-limit behavior unchanged
- [ ] Code follows project style (see CLAUDE.md, `.claude/rules/http-discipline.md`)

## Notes
High blast radius — every crawl flows through this client. The E-248-01 test suite is the safety net; this story must not begin until those tests pass against the un-refactored client. Pure dedup, zero behavior change (the dead verbs that carried the only 5xx gap are removed by E-246-07).
