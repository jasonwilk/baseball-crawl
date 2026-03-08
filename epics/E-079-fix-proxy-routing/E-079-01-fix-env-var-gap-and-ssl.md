# E-079-01: Fix env var gap and SSL behavior in GameChangerClient

## Epic
[E-079: Fix Bright Data Proxy Routing](epic.md)

## Status
`TODO`

## Description
After this story is complete, `GameChangerClient` will read proxy configuration from its already-loaded dotenv dict and pass the proxy URL explicitly to `create_session()`, eliminating the gap where proxy env vars exist in the dict but not in `os.environ`. When a proxy URL is configured, `create_session()` will automatically disable SSL verification (required by Bright Data's self-signed CONNECT tunnel certificate) and log a warning.

## Context
`GameChangerClient._load_credentials()` calls `dotenv_values()` which returns a dict but does not set `os.environ`. The session factory's `get_proxy_config()` reads `os.environ`, so proxy vars are invisible. The fix is to extract proxy config from the credentials dict and pass it explicitly to `create_session()`, which already has a `proxy_url` parameter with an `_UNSET` sentinel designed for this.

Additionally, Bright Data's residential proxy requires `verify=False` on the httpx client. This must be added to `create_session()` and derived automatically from whether a proxy URL is present.

## Acceptance Criteria
- [ ] **AC-1**: Given `PROXY_ENABLED=true` and `PROXY_URL_WEB=http://proxy.example.com:1234` in the dotenv dict, when `GameChangerClient(profile="web")` is instantiated, then the underlying httpx session is configured with the proxy URL from the dict (not from `os.environ`).
- [ ] **AC-2**: Given `PROXY_ENABLED=true` and `PROXY_URL_MOBILE=http://proxy.example.com:5678` in the dotenv dict, when `GameChangerClient(profile="mobile")` is instantiated, then the underlying httpx session is configured with the mobile proxy URL.
- [ ] **AC-3**: Given `PROXY_ENABLED` is absent or not `"true"` in the dotenv dict, when `GameChangerClient` is instantiated, then no proxy is configured on the session (same as current behavior).
- [ ] **AC-4**: Given the resolved proxy URL (after sentinel evaluation in `create_session()`) is a non-None string, when the httpx client is created, then `verify=False` is passed to the client constructor.
- [ ] **AC-5**: Given the resolved proxy URL (after sentinel evaluation) is None, when the httpx client is created, then `verify` is not set to False (default SSL verification applies).
- [ ] **AC-6**: Given a proxy URL is resolved, when the session is created, then a WARNING-level log message is emitted indicating SSL verification is disabled and including the profile name (e.g., "SSL verification disabled: proxy configured for web profile"). The log message MUST NOT contain the proxy URL itself.
- [ ] **AC-7**: The existing `get_proxy_config()` function in `src/http/session.py` remains unchanged (it still reads `os.environ` for any future callers that set env vars there).
- [ ] **AC-8**: All existing tests in `tests/test_http_session.py` continue to pass without modification (unless a test explicitly tests the old broken behavior).
- [ ] **AC-9**: New unit tests: AC-1, AC-2, AC-3 (proxy forwarding) in a new `tests/test_gamechanger_client.py`; AC-4, AC-5, AC-6 (SSL/verify behavior) in `tests/test_http_session.py`.

## Technical Approach
The core problem is that `GameChangerClient.__init__()` has proxy config available in its `self._credentials` dict but does not forward it to `create_session()`. The `create_session()` function already accepts an explicit `proxy_url` parameter with an `_UNSET` sentinel -- this parameter was designed for exactly this use case.

The credentials dict contains `PROXY_ENABLED`, `PROXY_URL_WEB`, and `PROXY_URL_MOBILE`. The resolved proxy URL must be forwarded to `create_session(proxy_url=...)`. See epic Technical Notes for the SE consultation recommendation on implementation approach.

For SSL, `create_session()` needs to pass `verify=False` to `httpx.Client()` when the resolved proxy URL is non-None. This is derived from the resolved proxy value -- no new parameter needed.

**Note**: `src/gamechanger/team_resolver.py` explicitly passes `proxy_url=None` to `create_session()` for public API calls that need no proxy. This is correct and intentional -- do not change it.

Relevant context:
- `/workspaces/baseball-crawl/src/gamechanger/client.py` -- `GameChangerClient.__init__()` at line 111, `_load_credentials()` at line 461
- `/workspaces/baseball-crawl/src/http/session.py` -- `create_session()` at line 114, `get_proxy_config()` at line 53
- `/workspaces/baseball-crawl/tests/test_http_session.py` -- existing proxy tests

## Dependencies
- **Blocked by**: None
- **Blocks**: E-079-02 (proxy check command needs working proxy routing), E-079-03 (docs describe working behavior)

## Files to Create or Modify
- `src/gamechanger/client.py` -- add proxy resolution method, pass proxy_url to create_session()
- `src/http/session.py` -- add verify=False when proxy is configured, add warning log
- `tests/test_gamechanger_client.py` -- new tests for proxy forwarding
- `tests/test_http_session.py` -- new tests for SSL behavior with proxy

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-079-02**: Working proxy routing. The proxy check command depends on `create_session()` correctly routing through the proxy when a proxy_url is provided (either explicitly or via env vars).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Proxy URLs contain credentials (username:password in the URL). Never log the actual URL value -- only log the env var name or a generic "proxy configured" message.
- The `_UNSET` sentinel in `create_session()` was specifically designed for this forwarding pattern (see docstring).
