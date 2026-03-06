# E-053: Profile-Scoped Credentials

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Separate GameChanger credentials by traffic profile (web vs. mobile) so the operator can capture both browser and iOS app sessions through mitmproxy without one overwriting the other. Today all credentials land in flat `.env` keys -- whoever came through last wins. After this epic, each profile's credentials are stored under profile-scoped keys and consumed by the correct profile in `GameChangerClient`.

## Background & Context
The credential extractor addon (`proxy/addons/credential_extractor.py`) already calls `gc_filter.detect_source(user_agent)` which returns `"ios"`, `"web"`, or `"unknown"` -- but it writes to flat env keys (`GAMECHANGER_AUTH_TOKEN`, `GAMECHANGER_DEVICE_ID`, etc.) regardless of source. When the operator captures mobile traffic and then web traffic (or vice versa), the second capture silently overwrites the first.

Meanwhile, `GameChangerClient` already accepts a `profile` parameter (`"web"` or `"mobile"`) that controls header selection and proxy routing -- but credential loading is profile-unaware. It reads the same flat keys regardless of profile.

The operator wants to run the proxy, capture both web and mobile sessions (simultaneously or across separate sessions), and have the right credentials automatically available when crawling with `--profile web` or `--profile mobile`.

No expert consultation required -- this is a well-understood credential routing problem. The profile detection logic already exists; the env key naming is the only design decision, and it follows the existing `PROXY_URL_WEB`/`PROXY_URL_MOBILE` pattern already established in E-046.

## Goals
- Credentials from web and mobile traffic are stored in separate env keys
- `GameChangerClient` reads profile-scoped credentials matching its `profile` parameter
- `check_credentials.py` validates credentials for a specific profile (or both)
- `bootstrap.py` uses the correct profile's credentials automatically
- Flat (unsuffixed) keys are removed -- profile-scoped keys are the only supported format

## Non-Goals
- Changing the credential extraction for `gc-signature` handling (signature remains profile-scoped like other credentials, but its usage patterns are not changed)
- Auto-detecting which profile to use for crawling (operator still passes `--profile` explicitly)
- Multi-credential rotation or expiry tracking (future work, see IDEA-012)
- Changes to the proxy addon architecture or session lifecycle (see E-052)
- Making `refresh_credentials.py` (curl paste workflow) profile-aware -- that path remains web-only and writes flat keys; the proxy capture is the primary credential path now

## Success Criteria
- Capturing web traffic through mitmproxy writes `GAMECHANGER_AUTH_TOKEN_WEB`, `GAMECHANGER_DEVICE_ID_WEB`, etc.
- Capturing iOS traffic writes `GAMECHANGER_AUTH_TOKEN_MOBILE`, `GAMECHANGER_DEVICE_ID_MOBILE`, etc.
- `GameChangerClient(profile="web")` reads `_WEB` keys; `GameChangerClient(profile="mobile")` reads `_MOBILE` keys
- No fallback to unsuffixed keys -- `ConfigurationError` if the profile-scoped key is missing
- `check_credentials.py` can validate a specific profile or report on all available credentials
- Existing tests are updated to use profile-scoped keys; new tests cover the profile-scoped loading

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-053-01 | Profile-scoped credential extractor | TODO | None | - |
| E-053-02 | Profile-aware credential loading in GameChangerClient | TODO | None | - |
| E-053-03 | Profile-aware check_credentials and bootstrap | TODO | E-053-02 | - |
| E-053-04 | Update .env.example and documentation | TODO | E-053-01, E-053-02 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Env Key Naming Convention

Follows the existing `PROXY_URL_WEB`/`PROXY_URL_MOBILE` pattern. No flat (unsuffixed) keys -- profile-scoped keys only.

| Header | Web key | Mobile key |
|--------|---------|------------|
| `gc-token` | `GAMECHANGER_AUTH_TOKEN_WEB` | `GAMECHANGER_AUTH_TOKEN_MOBILE` |
| `gc-device-id` | `GAMECHANGER_DEVICE_ID_WEB` | `GAMECHANGER_DEVICE_ID_MOBILE` |
| `gc-app-name` | `GAMECHANGER_APP_NAME_WEB` | `GAMECHANGER_APP_NAME_MOBILE` |
| `gc-signature` | `GAMECHANGER_SIGNATURE_WEB` | `GAMECHANGER_SIGNATURE_MOBILE` |

### Source-to-Profile Mapping

`detect_source()` returns `"ios"`, `"web"`, or `"unknown"`. The mapping to env key suffixes:

- `"ios"` -> `_MOBILE` (aligns with `profile="mobile"` everywhere else in the codebase)
- `"web"` -> `_WEB`
- `"unknown"` -> log a warning and **drop** the credentials (do not write). There are no flat keys to write to, and guessing is worse than skipping.

### Credential Loading (No Fallback)

`GameChangerClient(profile="web")` reads `GAMECHANGER_AUTH_TOKEN_WEB` directly. If the key is missing, `ConfigurationError` is raised naming the expected key. No fallback chain. Same for `_MOBILE`.

`GAMECHANGER_BASE_URL` remains unsuffixed -- it is the same API host regardless of profile.

### Migration Notes

Existing `.env` files with flat keys (`GAMECHANGER_AUTH_TOKEN`, etc.) will stop working after this epic. The operator must re-capture credentials through the proxy (which now writes profile-scoped keys) or manually rename keys in `.env`. Since there is only one operator and the proxy is the primary credential path, this is a clean break.

`refresh_credentials.py` (curl paste workflow) continues to write flat keys. It is a web-only manual fallback. If the operator uses it, they must manually rename the keys or accept that only `--profile web` will work by setting the `_WEB` suffixed keys. This is documented but not automated -- keeping the manual path simple.

### E-055 Note

The scripts modified by this epic (`check_credentials.py`, `bootstrap.py`) will eventually be wrapped by E-055's unified `bb` CLI. That is a separate epic; no dependency here.

### File Impact Summary

| File | Stories |
|------|---------|
| `proxy/addons/credential_extractor.py` | 01 |
| `src/gamechanger/client.py` | 02 |
| `src/gamechanger/credential_parser.py` | 01 (env key mapping update) |
| `scripts/check_credentials.py` | 03 |
| `scripts/bootstrap.py` | 03 |
| `.env.example` | 04 |
| `tests/test_credential_extractor.py` | 01 |
| `tests/test_client.py` | 02 |
| `tests/test_credential_parser.py` | 01 |
| `tests/test_check_credentials.py` | 03 |
| `tests/test_bootstrap.py` | 03 |

## Open Questions
None -- all resolved during refinement (see History).

## History
- 2026-03-06: Created (DRAFT). No expert consultation required -- credential routing follows existing profile-scoped patterns (PROXY_URL_WEB/PROXY_URL_MOBILE from E-046).
- 2026-03-06: Refined to READY. Resolved: (1) `refresh_credentials.py` stays flat-key, web-only -- not worth the scope. (2) Flat keys removed entirely -- no backward compatibility fallback. Profile-scoped keys only. Clean break while there is one operator.
