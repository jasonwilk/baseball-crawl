# E-079-02: Add bb proxy check diagnostic command

## Epic
[E-079: Fix Bright Data Proxy Routing](epic.md)

## Status
`TODO`

## Description
After this story is complete, the operator can run `bb proxy check` to verify that API requests are routing through the Bright Data proxy. The command makes HTTP requests through each profile's proxy session and one direct request, compares the returned IP addresses, and reports whether proxy routing is working. This is a diagnostic tool -- it always exits 0 and does not gate other operations.

## Context
With E-079-01 fixing the proxy routing plumbing, the operator needs a way to verify it actually works. The existing `bb proxy` namespace covers mitmproxy session analysis commands. This adds a Bright Data verification command to the same namespace. The command uses `create_session()` directly (not GameChangerClient) so it works without GameChanger credentials -- it only needs the proxy env vars.

## Acceptance Criteria
- [ ] **AC-1**: Running `bb proxy check` with `PROXY_ENABLED=true` in `.env` makes one direct request (no proxy) plus one request per profile that has a configured proxy URL. Each request hits an IP-echo service and reports the returned IP.
- [ ] **AC-2**: For each profile, the output reports one of four outcomes: PASS (proxy IP differs from direct IP -- proxy is routing); FAIL (proxy IP matches direct IP -- proxy not routing); ERROR (proxy request failed -- connection refused, timeout, or other network error); or PASS-UNVERIFIED (proxy request succeeded but direct IP baseline unavailable -- direct request failed). If the direct request fails, proxy results are still displayed but the IP comparison is skipped.
- [ ] **AC-3**: Running `bb proxy check` with `PROXY_ENABLED` unset or `false` reports that proxy is not enabled and skips the IP comparison.
- [ ] **AC-4**: Running `bb proxy check` with `PROXY_ENABLED=true` but a missing or invalid `PROXY_URL_WEB` or `PROXY_URL_MOBILE` reports the specific problem per profile without crashing.
- [ ] **AC-5**: The command always exits with code 0 regardless of results (diagnostic, not a gate).
- [ ] **AC-6**: The command never logs or displays the actual proxy URL (it contains credentials).
- [ ] **AC-7**: Network errors (timeout, connection refused) are caught and reported as descriptive error messages per profile, not stack traces.
- [ ] **AC-8**: Unit tests verify the check logic using mocked HTTP responses (no real network calls in tests).
- [ ] **AC-9**: The `src/cli/proxy.py` module docstring is updated to reflect the broader scope (not just mitmproxy session commands).
- [ ] **AC-10**: Sessions created for the check use `min_delay_ms=0, jitter_ms=0` (diagnostic requests, not sustained crawling).

## Technical Approach
The check logic belongs in a new module at `src/http/proxy_check.py` (HTTP-layer diagnostic, not GameChanger-specific). The module provides a function that accepts a profile, reads proxy config from `dotenv_values()`, passes the resolved URL to `create_session(proxy_url=...)`, hits an IP-echo endpoint, and returns the result. The CLI command in `src/cli/proxy.py` orchestrates: one direct call (no proxy) + one call per profile, then compares and displays results.

The proxy config resolution logic (reading `PROXY_ENABLED` and `PROXY_URL_{profile}` from a dict) should be reusable -- both `GameChangerClient` (E-079-01) and this module need it. The implementer should extract or share the resolution logic so both callers use the same pattern.

The IP-echo service (`https://api.ipify.org?format=json`) is a well-known, stable, free endpoint. The check function should use a short timeout (e.g., 10 seconds) and handle failures gracefully. Note: a failed direct request (e.g., due to network filtering) does not invalidate proxy results.

Relevant context:
- `/workspaces/baseball-crawl/src/cli/proxy.py` -- existing proxy commands, module docstring to update
- `/workspaces/baseball-crawl/src/http/session.py` -- `create_session()` with proxy support

## Dependencies
- **Blocked by**: E-079-01 (proxy routing must work before it can be checked)
- **Blocks**: None

## Files to Create or Modify
- `src/http/proxy_check.py` -- new module with check logic (HTTP-layer, not GameChanger-specific)
- `src/cli/proxy.py` -- new `check` command, updated module docstring
- `tests/test_proxy_check.py` -- unit tests for check logic
- `tests/test_cli_proxy.py` -- add test for `bb proxy check` command; update help text assertion

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- ipify.org is a free service with no rate limits for reasonable use. A single diagnostic check makes 3 requests total -- well within acceptable use.
- The command should use `create_session()` with `min_delay_ms=0, jitter_ms=0` since it is making single diagnostic requests, not sustained API crawling.
