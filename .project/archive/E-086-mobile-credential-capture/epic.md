# E-086: Mobile Credential Capture

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Make mobile credential capture seamless: the operator starts mitmproxy and uses the GameChanger iOS app, then runs a single `bb` command that scans the proxy session, extracts mobile credentials, validates them, and writes them to `.env`. The system takes over from the moment traffic is captured. This absorbs the remaining E-075 stories (02 + 03) into a cohesive operator-facing workflow.

## Background & Context
The web profile has a fully automatic credential chain: programmatic token refresh, no manual intervention needed once the initial refresh token is in `.env`. The mobile profile has none of this -- the mobile client key is unknown (embedded in the iOS binary), so programmatic signing and token refresh are blocked.

What the mobile profile DOES have:
- **Access tokens**: ~12 hours lifetime (vs ~60 min web). Long enough for any crawl session.
- **Refresh tokens**: 14 days lifetime. Sent as `gc-token` in POST /auth refresh calls. Usability for general GET endpoints is unverified.
- **Proxy capture**: mitmproxy captures all iOS traffic including auth headers and POST /auth response bodies.

The gap: there is no automated path from "proxy captured mobile traffic" to "credentials in `.env` ready to use." Today the operator would need to manually find tokens in mitmweb, copy them, and paste them into `.env`. E-086 closes that gap.

**Relationship to E-075**: E-075 (Mobile Profile Credential Capture and Validation) completed R-01 (research) and 01 (env var naming alignment). Stories 02 (addon upgrade) and 03 (validation script) remain TODO. E-086 absorbs and supersedes them with a richer, integrated workflow. E-075-02's addon plumbing becomes E-086-01. E-075-03's validation is absorbed into the `bb creds capture` workflow (E-086-03). E-075 should be marked COMPLETED with remaining stories ABANDONED (superseded by E-086) after this epic is set to READY.

**Consultation completed (2026-03-09)**: claude-architect, ux-designer, api-scout, and software-engineer all consulted. Key findings:
- CA: Update CLAUDE.md mobile profile note to describe the supported workflow. `bb creds import --from-proxy` or `bb creds capture` mode. No self-healing for mobile -- "just as easy" means seamless after capture.
- UXD: `bb creds capture --profile mobile` command. When no sessions found: inline numbered setup guide. When sessions found but no mobile auth: guidance to force-quit and reopen app. After capture: `bb creds check --profile mobile` shows 12h countdown with `[!!]`.
- api-scout: Focus on reliable capture. Extract access token (HIGH), refresh token (HIGH), device-id (HIGH), client-id (already known). Mobile client key extraction out of scope.
- SE: `parse_curl()` is hardcoded to web. Mobile import must save ACCESS tokens (not reject them). `_decode_jwt_type()` already distinguishes token types. `--profile` flag recommended for MVP.

## Goals
- Proxy addon captures all mobile credentials from iOS traffic: access token, refresh token, device ID, client ID
- Single `bb` command scans proxy sessions and imports mobile credentials to `.env`
- `bb creds import --profile mobile` supports manual curl-paste path for mobile
- Mobile credentials are validated automatically after capture (GET /me/user)
- Operator gets clear guidance when capture fails or credentials are incomplete
- 12-hour access token window is communicated honestly (no false promise of auto-refresh)

## Non-Goals
- Mobile client key extraction (requires IPA binary analysis -- separate effort)
- Programmatic mobile token refresh (blocked on unknown client key)
- Mobile-specific crawlers or data pipelines (downstream work)
- Changes to the web credential workflow (this is mobile-only)
- Full feature parity with web credentials (web has auto-refresh; mobile does not, and the UI should be honest about that)

## Success Criteria
- Given a proxy session with iOS GameChanger traffic, `bb creds capture --profile mobile` extracts credentials and writes them to `.env` without manual intervention
- Given the credentials are written, `bb creds check --profile mobile` validates them successfully
- Given no proxy sessions exist or no mobile traffic is found, the command provides clear, actionable guidance (not just an error)
- The proxy addon captures all credential headers from iOS traffic including `gc-client-id` and POST /auth response tokens
- `bb creds import --profile mobile --curl "..."` works for the manual curl-paste path as a fallback

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-086-01 | Proxy Addon: gc-client-id and Response Body Capture | DONE | None | SE |
| E-086-02 | `bb creds import --profile mobile` | DONE | None | SE |
| E-086-03 | `bb creds capture --profile mobile` | DONE | E-086-01, E-086-02 | SE |
| E-086-04 | Context-Layer Mobile Credential Workflow | DONE | E-086-02, E-086-03 | CA |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### Proxy Addon Upgrade (Story 01)

The credential extractor addon (`proxy/addons/credential_extractor.py`) currently:
- Has only a `request()` handler -- captures headers from outbound requests
- Captures: `gc-token` (refresh tokens only -- access tokens are rejected), `gc-device-id`, `gc-app-name`
- Does NOT capture: `gc-client-id` (needed for mobile profile completeness)
- Does NOT capture POST /auth response bodies (where fresh access + refresh tokens are returned)

Story 01 adds:
1. `gc-client-id` header capture in `request()` handler (simple addition to `_BASE_CREDENTIAL_HEADERS`)
2. A `response()` handler for POST /auth responses that extracts access and refresh tokens from the response body

The `response()` handler parses `{type: "token", access: {data: "..."}, refresh: {data: "..."}}` and writes:
- Access token (from `access.data`) -> `GAMECHANGER_ACCESS_TOKEN_{PROFILE}` (NEW env key for mobile)
- Refresh token (from `refresh.data`) -> `GAMECHANGER_REFRESH_TOKEN_{PROFILE}` (existing key, updated with fresh value)

For web profile, the refresh token from response bodies is the most valuable capture (enables self-renewing chain). For mobile profile, the access token is critical (direct API access for ~12 hours).

### Mobile Import via curl (Story 02)

`parse_curl()` in `credential_parser.py` is currently hardcoded to produce `_WEB` suffixed keys. Story 02 adds a `profile` parameter:
- `parse_curl(curl_command, profile="web")` -- existing behavior
- `parse_curl(curl_command, profile="mobile")` -- produces `_MOBILE` suffixed keys

Key difference: for mobile, access tokens MUST be saved (not rejected). The current logic rejects tokens with `type == "user"` (access tokens) and only saves refresh tokens. For mobile, both token types are valuable:
- Access tokens -> `GAMECHANGER_ACCESS_TOKEN_MOBILE` (direct API access, ~12 hours)
- Refresh tokens -> `GAMECHANGER_REFRESH_TOKEN_MOBILE` (14-day, used in POST /auth refresh calls)

The `bb creds import` CLI command also needs the `--profile` flag.

### Proxy Session Scanning (Story 03)

The `bb creds capture --profile mobile` command is the "system takes over" experience. It:
1. Checks `.env` for mobile credentials already written by the addon during the proxy session
2. If credentials present: validates them via `GET /me/user` and reports token health
3. If credentials missing: scans `proxy/data/sessions/` for recent sessions (or current session via `proxy/data/current`) to detect whether iOS auth traffic occurred, and provides actionable guidance
4. Displays a summary showing what was captured and the token's remaining lifetime

**When no sessions found**: Print an inline numbered setup guide (start mitmproxy, configure iPhone proxy, open GameChanger app).

**When sessions found but no mobile auth**: Guide operator to force-quit and reopen the GameChanger app (the app only sends POST /auth on cold start, not on resume).

**When validation fails**: Clear error with retry guidance.

**After successful capture**: Show token health with `[!!]` yellow indicator for the 12-hour access token window. Recommend recapture cadence.

The command reads from TWO sources:
1. `.env` file -- the addon writes credentials via its `request()` and `response()` hooks during the proxy session. This is the primary path.
2. Endpoint log JSONL -- fallback for **detection and guidance only**. The endpoint log contains request/response metadata (`method`, `path`, `source`, `status_code`) but NOT credential values (tokens, IDs). The fallback can detect that iOS auth traffic occurred and guide the operator, but it cannot recover credentials from the log.

Priority: check `.env` first. If mobile credentials are missing, scan the endpoint log to determine what guidance to show (e.g., "Auth traffic was captured but credentials are missing -- re-run the proxy session" vs. "No iOS traffic found -- force-quit and reopen the GameChanger app").

### Token Lifetime Communication

Mobile access tokens expire in ~12 hours. The system must communicate this honestly:
- `bb creds capture` output: "Access token valid for ~N hours"
- `bb creds check --profile mobile`: Token health shows `[!!]` yellow with countdown
- No promise of auto-refresh -- the operator knows to recapture when needed
- The 14-day refresh token is available for POST /auth refresh calls (usability for general GET endpoints is unverified)

### File Ownership Map

| File | Story | Notes |
|------|-------|-------|
| `proxy/addons/credential_extractor.py` | 01 | Add gc-client-id capture + response() handler |
| `tests/test_proxy/test_credential_extractor.py` | 01 | Tests for new captures |
| `src/gamechanger/credential_parser.py` | 02 | Add profile parameter to parse_curl() |
| `src/cli/creds.py` | 02, 03 | Add --profile to import, add capture command |
| `tests/test_credential_parser.py` | 02 | Tests for mobile profile parsing |
| `tests/test_cli_creds.py` | 02, 03 | CLI tests |
| `CLAUDE.md` | 04 | Mobile credential workflow, new commands |
| `docs/admin/mitmproxy-guide.md` | 04 | Replace existing mobile capture section with updated proxy-based workflow |
| `docs/admin/getting-started.md` | 04 | Update credential section for mobile env vars and commands |
| `docs/admin/bootstrap-guide.md` | 04 | Update proxy workflow section and credential lifecycle table for mobile |

### Wave Structure
- **Wave 1** (parallel): E-086-01 (addon upgrade) + E-086-02 (import --profile mobile). No file conflicts.
- **Wave 2** (after wave 1): E-086-03 (bb creds capture). Depends on both E-086-01 (addon must be upgraded for capture to find data) and E-086-02 (shared file conflict on `src/cli/creds.py` and `tests/test_cli_creds.py`).
- **Wave 3** (after wave 2): E-086-04 (context-layer docs). Depends on knowing final commands and workflow.

## Open Questions
- None -- all questions resolved via consultation.

## History
- 2026-03-09: Created. Absorbs remaining E-075 stories (02 + 03) into a richer, integrated mobile credential workflow. All four consultations completed (CA, UXD, api-scout, SE).
- 2026-03-09: Codex spec review triage -- 6 findings, all accepted. Fixes: (P1-1) added E-086-03 dependency on E-086-02 for shared file conflict, (P1-2) clarified proxy session fallback as detection+guidance only (endpoint log has no credential values), fixed `current-session` -> `current` symlink reference, (P2-1) AC-10 changed from ambiguous "offers to run" to "prints a suggestion", (P2-2) fixed test file path to `tests/test_proxy/test_credential_extractor.py`, (P2-3) removed E-085 login fallback claim (still DRAFT), (P3-1) replaced contradictory DoD in E-086-04 with docs-specific verification.
- 2026-03-10: COMPLETED. All 4 stories implemented, reviewed, and merged. Proxy addon captures gc-client-id and POST /auth response tokens (01). `bb creds import --profile mobile` supports manual curl-paste path (02). `bb creds capture --profile mobile` provides the automated proxy-to-.env workflow with full decision tree guidance (03). CLAUDE.md, mitmproxy-guide.md, getting-started.md, and bootstrap-guide.md updated with mobile credential workflow (04). Code review findings: response() and _process_header() refactored to extract helpers for function length compliance; import_creds() accepted at exactly 50 lines via user override. SHOULD FIX noted: _run_api_check private import across module boundary (deferred), parse_curl() at 128 lines (predates this epic, deferred).
- 2026-03-10: All-agent refinement review. Fixes: (CRIT) corrected POST /auth response field name from `token` to `data` in epic TN + E-086-01 (api-scout), (P1) removed unverified refresh-token-for-GET-endpoints claim (api-scout), (P1) expanded E-086-04 scope to include getting-started.md + bootstrap-guide.md and clarified mitmproxy-guide.md replacement (docs-writer), (P2) added Mac-host callout to E-086-03 AC-5 (ux-designer). Agents consulted: PM, baseball-coach, api-scout, data-engineer, software-engineer, docs-writer, ux-designer, claude-architect.
