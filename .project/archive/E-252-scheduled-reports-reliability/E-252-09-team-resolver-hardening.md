# E-252-09: Harden team_resolver against ConnectError

## Epic
[E-252: Scheduled-Reports Reliability (Cron-Grade Morning-Run)](../E-252-scheduled-reports-reliability/epic.md)

## Status
`DONE`

## Description
After this story is complete, a connection-level HTTP failure (not just a timeout) in the public `team_resolver` calls is caught and surfaced as a handled `GameChangerAPIError` rather than propagating as an unhandled `httpx` exception — so a transient network blip during opponent display-profile resolution cannot crash the morning run.

## Context
`resolve_team` and `discover_opponents` in `src/gamechanger/team_resolver.py` call the public GC endpoints and catch only `httpx.TimeoutException`, re-raising it as `GameChangerAPIError`. Any other transport-level failure — most commonly `httpx.ConnectError` (DNS, connection refused, TLS) — is a broader `httpx.RequestError` that escapes uncaught. The audit flags that such an uncaught error can crash the whole morning run. (Within `_process_opponent` the display-profile `resolve_team` call is wrapped in a best-effort `except Exception`, but hardening the resolver at the source makes every caller — including `map-opponent` and any future caller — robust, and keeps the exception contract honest: the function's docstring promises `GameChangerAPIError` on non-200/transport failure.)

This is a LOW-severity hardening item. It also raises a question about whether these public calls should respect the proxy/pacing HTTP posture (they currently pass `proxy_url=None`, `min_delay_ms=0`) — see the note below; that posture change is NOT required by this story unless the implementer and reviewer agree it is in-scope.

## Acceptance Criteria
- [ ] **AC-1**: Given `resolve_team` (and `discover_opponents`) where the underlying HTTP call raises a connection-level error (`httpx.ConnectError` / the broader `httpx.RequestError` family, not only `TimeoutException`), when the call is made, then the error is caught and re-raised as `GameChangerAPIError` with a clear message — matching the function's documented exception contract — rather than propagating as a raw `httpx` exception.
- [ ] **AC-2**: The existing behaviors are unchanged: a 404 still raises `TeamNotFoundError`; a non-200/non-404 still raises `GameChangerAPIError`; a successful 200 still returns the populated `TeamProfile` / opponent list; the timeout path still maps to `GameChangerAPIError`.
- [ ] **AC-3**: A morning-run-level test (or a focused resolver test) demonstrates that a `ConnectError` during opponent resolution no longer produces an unhandled crash — it is surfaced as the handled `GameChangerAPIError` (and, within the run, isolated per E-252-02 rather than aborting the run).
- [ ] **AC-4**: Tests cover the new catch for both `resolve_team` and `discover_opponents` (per Technical Notes TN-8, HTTP mocked at the transport layer — no real network).

## Technical Approach
Broaden the `except httpx.TimeoutException` clauses in `resolve_team` and `discover_opponents` to the appropriate `httpx.RequestError` supertype (which covers `TimeoutException`, `ConnectError`, and other transport failures), re-raising as `GameChangerAPIError` with a message that names the failure and the `public_id`. Keep the 404 → `TeamNotFoundError` and non-200 → `GameChangerAPIError` branches intact. Do NOT change the proxy/pacing posture as part of this story unless separately agreed (see Notes). Confirm the exception types against `src/gamechanger/exceptions.py` and the current `team_resolver.py` contract.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/team_resolver.py` (`resolve_team`, `discover_opponents` catch clauses)
- `tests/test_team_resolver.py` (or the existing resolver test module) — ConnectError/RequestError catch tests

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Audit one-liner (LOW): "`team_resolver` catches only `TimeoutException` and bypasses the proxy/pacing posture — a `ConnectError` crashes the whole morning run" — `src/gamechanger/team_resolver.py:93`. Anchor correction: the actual `except httpx.TimeoutException` clauses are at L104 (`resolve_team`) and L180 (`discover_opponents`), not :93 (the audit's :93 anchor is off). The proxy/pacing-posture half of that finding (public calls currently pass `proxy_url=None`, `min_delay_ms=0`) is a separate HTTP-discipline question; it is intentionally deferred out of this story's required scope. If the implementer/reviewer judge the posture change belongs here, flag it to PM before expanding scope.
