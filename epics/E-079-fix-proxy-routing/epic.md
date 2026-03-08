# E-079: Fix Bright Data Proxy Routing

## Status
`READY`

## Overview
All GameChanger API requests from GameChangerClient bypass the Bright Data residential proxy and go direct, exposing the user's home IP address. This is a critical privacy and operational risk. The proxy configuration was implemented in E-046 but never actually worked due to an environment variable loading gap between `dotenv_values()` (dict) and `os.environ` (where `get_proxy_config()` reads from).

## Background & Context
E-046 implemented dual-zone Bright Data proxy support: `PROXY_ENABLED`, `PROXY_URL_WEB`, and `PROXY_URL_MOBILE` env vars, `get_proxy_config()` in `src/http/session.py`, and `create_session()` with a `proxy_url` parameter. The design works when env vars are in `os.environ`.

The problem: `GameChangerClient.__init__()` calls `dotenv_values()`, which returns a dict but does NOT populate `os.environ`. When it then calls `create_session()` without an explicit `proxy_url`, the session factory calls `get_proxy_config()` which reads `os.environ.get("PROXY_ENABLED")` -- where the proxy vars do not exist. Result: proxy is silently disabled on every request.

Additionally, Bright Data's residential proxy uses a self-signed certificate in the CONNECT tunnel, requiring `verify=False` on the httpx client when proxy is enabled.

**Mandatory consultations completed:**
- **Software Engineer**: Recommended Option B (explicit proxy_url forwarding from dotenv dict). Designed `bb proxy check` as a diagnostic command using ipify.org. Identified SSL and credential-logging risks.
- **Claude Architect**: Identified 3 context-layer updates needed (CLAUDE.md Proxy Boundary restructuring, Commands section, env var documentation). No agent/rule/skill changes needed.

## Goals
- All GameChangerClient API requests route through the Bright Data proxy when `PROXY_ENABLED=true` in `.env`
- SSL verification is automatically disabled when proxy is configured (Bright Data requirement)
- Operator can verify proxy routing is working via `bb proxy check`
- CLAUDE.md accurately documents the Bright Data proxy configuration

## Non-Goals
- Changing the mitmproxy (traffic capture) proxy -- that system is separate and working
- Adding proxy support to non-GameChangerClient HTTP callers (future work if needed)
- Making `bb proxy check` a gate or pre-condition for other commands -- it is purely diagnostic

## Success Criteria
- Running `bb proxy check` from a proxied environment shows different IPs for proxied vs direct requests
- GameChangerClient requests go through the proxy when `PROXY_ENABLED=true` is set in `.env`
- Existing tests continue to pass (no regressions)
- CLAUDE.md Proxy Boundary section distinguishes mitmproxy from Bright Data

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-079-01 | Fix env var gap and SSL behavior in GameChangerClient | TODO | None | - |
| E-079-02 | Add bb proxy check diagnostic command | TODO | E-079-01 | - |
| E-079-03 | Update CLAUDE.md proxy documentation | TODO | E-079-01, E-079-02 | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### Root Cause
`GameChangerClient._load_credentials()` calls `dotenv_values()` which returns a dict. `create_session()` defaults to calling `get_proxy_config()` which reads `os.environ`. The dotenv dict is never merged into `os.environ`, so proxy vars are invisible to the session factory.

### Fix Approach (from SE consultation)
**Option B -- explicit proxy_url forwarding**: `GameChangerClient.__init__()` already has the dotenv dict in `self._credentials`. Extract proxy config from that dict and pass `proxy_url` explicitly to `create_session()`. The `create_session()` function already has a `proxy_url` parameter with an `_UNSET` sentinel designed for exactly this use case. No `os.environ` mutation needed.

A private method on GameChangerClient should replicate the `get_proxy_config()` logic but read from the credentials dict instead of `os.environ`. This keeps the existing `get_proxy_config()` function unchanged for any future callers that do have env vars in `os.environ`.

### SSL Behavior
Bright Data's residential proxy uses a self-signed certificate in the CONNECT tunnel. `create_session()` must pass `verify=False` to `httpx.Client` when a proxy is configured. This should be derived automatically from whether a proxy URL is present -- not exposed as a standalone parameter. A WARNING-level log should be emitted when SSL verification is disabled.

### bb proxy check Design (from SE consultation)
- New module `src/http/proxy_check.py` with a `check_proxy_routing(profile)` function (HTTP-layer diagnostic, not GameChanger-specific)
- New `@app.command()` in `src/cli/proxy.py` as `bb proxy check`
- Uses `create_session()` directly -- NOT GameChangerClient (works without GC credentials)
- Reads proxy config from `dotenv_values()` and passes resolved URL to `create_session(proxy_url=...)`
- Hits `https://api.ipify.org?format=json` through each configured profile's proxy session + once direct
- Compares IPs: proxy IPs must differ from the real (direct) IP
- Exit code 0 always (diagnostic, not a gate). Clear status lines per profile.
- Proxy URL contains credentials -- never log the actual URL

### Shared Proxy Resolution
Both `GameChangerClient` (E-079-01) and `proxy_check.py` (E-079-02) need to resolve proxy config from a dotenv dict. The resolution logic (read `PROXY_ENABLED` + `PROXY_URL_{profile}` from a dict) should be extracted into a reusable function rather than duplicated. Location is an SE implementation decision -- could live in `session.py`, `client.py`, or a shared utility.

### Callers of create_session() (Current and Post-Epic)
- `GameChangerClient` -- proxy routing via dotenv dict (current; fixed in E-079-01)
- `team_resolver.py` -- explicitly passes `proxy_url=None` for public API calls (current; correct, no change needed)
- `proxy_check.py` -- passes resolved URL explicitly (new in E-079-02; does not exist until then)

### Context-Layer Updates (from CA consultation)
1. CLAUDE.md "Proxy Boundary" section: restructure to distinguish mitmproxy (traffic capture, Mac host) from Bright Data (IP anonymization, env vars, used by GameChangerClient)
2. CLAUDE.md Commands section: add `bb proxy check`
3. Document `PROXY_ENABLED`, `PROXY_URL_WEB`, `PROXY_URL_MOBILE` env vars in CLAUDE.md
4. `src/cli/proxy.py` module docstring: broaden from "mitmproxy session commands" to cover both proxy types

### Key Source Files
- `src/http/session.py` -- `create_session()`, `get_proxy_config()`
- `src/gamechanger/client.py` -- `GameChangerClient`, `_load_credentials()`
- `src/cli/proxy.py` -- existing `bb proxy` commands
- `tests/test_http_session.py` -- existing session/proxy tests

## Open Questions
None -- root cause confirmed, fix approach agreed, consultations complete.

## History
- 2026-03-08: Created. Mandatory consultations completed with software-engineer (fix approach, story breakdown, risk assessment) and claude-architect (context-layer impact analysis). Set to READY.
- 2026-03-08: Codex spec review (gpt-5.4, xhigh reasoning). 1 P1, 3 P2, 2 P3 findings. PM+SE triage: ACCEPT P1 (result matrix for AC-2), ACCEPT P2-2 (add test_cli_proxy.py to file list), ACCEPT P2-3 (rename "Existing Callers" section), DEFER P2-1 (shared resolution -- SE decides at implementation), REJECT P3-4 (overview correctly scoped), ACCEPT P3-5 (docs-only DoD). Softened "private" in E-079-01 file list per P2-1 deferral. Spec reviewed -- all findings resolved.
- 2026-03-08: Refinement with PM and SE. Findings applied: (1) Fixed E-079-03 dependency in epic table (was missing E-079-02); (2) Corrected wave structure to sequential 01→02→03; (3) Moved `proxy_check.py` from `src/gamechanger/` to `src/http/` (HTTP-layer, not GC-specific); (4) Clarified AC-4/AC-5 in E-079-01 to reference "after sentinel evaluation"; (5) Fixed AC-8 in E-079-01 (removed reference to non-existent test file); (6) Split AC-9 test targets by file; (7) Added `team_resolver.py` note to E-079-01; (8) Rewrote AC-1/AC-2 in E-079-02 for partial config and explicit pass/fail definitions; (9) Added shared proxy resolution note to Technical Notes; (10) Added AC-10 (rate-limit override) to E-079-02; (11) Added SSL rationale and credential sensitivity notes to E-079-03 ACs; (12) Reduced Technical Approach prescription in E-079-01 per PM anti-pattern 6.
