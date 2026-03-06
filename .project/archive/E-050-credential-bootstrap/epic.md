# E-050: Credential Validation and Crawl Bootstrap

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Give the operator a single command to validate GameChanger credentials, verify system readiness, and run the full crawl-and-load pipeline. Today, the operator must manually check whether credentials are valid, run crawl.py, then run load.py -- with no early warning if tokens have expired. This epic closes that gap with a credential health check, a profile-aware API client, and a unified bootstrap script that chains the entire workflow.

## Background & Context
Two credential ingest paths already exist and work:
1. **Proxy capture**: `cd proxy && ./start.sh` on the Mac host runs mitmproxy. When iPhone or browser traffic flows through, the `credential_extractor` addon auto-writes `gc-token`, `gc-device-id`, and `gc-app-name` to the project root `.env`.
2. **Curl paste**: The operator saves a curl command to `secrets/gamechanger-curl.txt` and runs `python scripts/refresh_credentials.py`, which parses the curl and merges credentials into `.env`.

What is missing is the step between "credentials are in `.env`" and "data is flowing." Today, the operator has no way to verify credentials are valid without attempting a crawl and hitting a `CredentialExpiredError`. There is also no single command to run the full pipeline (crawl + load) as a unit.

**E-049-05 (DONE)**: The dual-header system (E-049-05) added `MOBILE_HEADERS` and a `profile` parameter to `create_session()`. This epic builds on that by making `GameChangerClient` profile-aware, so the bootstrap can use whichever credential type the operator captured (web or mobile). E-049-05 is complete -- all infrastructure is in place.

**Dependency on E-042**: E-042 (Admin Team Management) moves team configuration from `config/teams.yaml` into the database and admin UI. This epic does NOT depend on E-042 -- it works with whichever team config source is active (YAML today, DB after E-042-06). The bootstrap script reports whether teams are configured but does not configure them -- that is the admin UI's job (E-042).

**Expert consultation**: User directed collaboration with software-engineer. PM reviewed the codebase thoroughly in lieu of live SE consultation (no Task tool available): `scripts/crawl.py`, `scripts/load.py`, `src/gamechanger/client.py`, `src/http/session.py`, `src/http/headers.py`, `proxy/addons/credential_extractor.py`, `scripts/refresh_credentials.py`, and `config/teams.yaml`. The implementation approach is straightforward and builds on well-understood patterns. No api-scout consultation required -- all API behavior referenced (`/me/user` response schema, Accept headers, auth header semantics) is already documented in `docs/gamechanger-api.md`.

## Goals
- Operator can verify credential validity with a single command before starting a crawl
- `GameChangerClient` can use either web or mobile header profiles
- Operator can run the entire pipeline (validate -> crawl -> load) with one command
- Clear operator documentation ties both credential paths to the bootstrap workflow

## Non-Goals
- Scheduled or recurring crawl execution (captured as IDEA-012)
- Credential rotation alerting or expiry prediction
- Team discovery or configuration (that is E-042's domain)
- Modifying the proxy addons or credential extraction logic (already working)
- Automatic profile detection from captured credentials (operator specifies)

## Success Criteria
- `python scripts/check_credentials.py` reports whether `.env` credentials are valid (makes one API call to verify)
- `GameChangerClient` accepts a `profile` parameter and passes it to `create_session()`
- `python scripts/bootstrap.py` validates credentials, runs all crawlers, runs all loaders, and reports results -- with early exit and clear messaging if credentials are expired
- `docs/admin/bootstrap-guide.md` documents both credential paths and the bootstrap workflow
- All existing tests pass (no regressions)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-050-01 | Credential health check script | DONE | None | software-engineer |
| E-050-02 | Profile-aware GameChangerClient | DONE | None | software-engineer |
| E-050-03 | Bootstrap pipeline script | DONE | E-050-01 | software-engineer |
| E-050-04 | Operator bootstrap guide | DONE | E-050-01, E-050-03 | docs-writer |

## Dispatch Team
- software-engineer (stories 01, 02, 03)
- docs-writer (story 04)

## Technical Notes

### Credential Health Check Design
The cheapest API call for validation is `GET /me/user` -- it returns minimal data (user profile) and is already documented in `docs/gamechanger-api.md`. The check script:
- Reads `.env` via `dotenv_values()` (same pattern as `GameChangerClient._load_credentials()`)
- Verifies required keys are present (`GAMECHANGER_AUTH_TOKEN`, `GAMECHANGER_DEVICE_ID`, `GAMECHANGER_BASE_URL`)
- Makes a single `GET /me/user` request (with vendor Accept header: `application/vnd.gc.com.user+json; version=0.3.0`)
- Reports: valid (with user email/name), expired (401/403), or missing credentials
- Exit code: 0 = valid, 1 = expired/error, 2 = missing credentials

### Profile-Aware Client Design
After E-049-05 lands, `create_session()` accepts `profile: Literal["web", "mobile"]`. The `GameChangerClient` change is minimal:
- Add `profile: str = "web"` parameter to `__init__`
- Pass `profile` to `create_session()`
- The `gc-app-name` header logic: if `GAMECHANGER_APP_NAME` is set in `.env`, use that value; if absent and profile is `"web"`, default to `"web"`; if absent and profile is `"mobile"`, omit the header. The credential extractor already captures `gc-app-name` from traffic, so whatever the proxy captured goes into `.env` as `GAMECHANGER_APP_NAME` and gets used.

### Bootstrap Pipeline Design
The bootstrap script chains existing scripts with validation gates:
1. **Check credentials** -- call the health check logic (imported, not subprocess)
2. **Check team config** -- verify `config/teams.yaml` has real team IDs (not placeholder `REPLACE_WITH_*`), or later verify DB has active teams
3. **Run crawl** -- invoke `crawl.run()` directly (already importable)
4. **Run load** -- invoke `load.run()` directly (already importable)
5. **Report summary** -- total files crawled, records loaded, errors

The script supports `--check-only` (validate without crawling), `--profile web|mobile` (header profile selection, default `web`), and `--dry-run` (pass through to crawl/load).

### Proxy Credential Flow (End-to-End)
For reference, the proxy credential flow after E-048:
1. Operator runs `cd proxy && ./start.sh` on the Mac host
2. Proxy docker container starts, mounts project root at `/app`
3. iPhone/browser traffic flows through `<mac-lan-ip>:8080`
4. `credential_extractor.py` detects GC traffic, extracts `gc-token`/`gc-device-id`/`gc-app-name`
5. Writes to `/app/.env` (= project root `.env`)
6. The devcontainer app reads `.env` at startup (or when `GameChangerClient` is instantiated)
7. Operator runs `python scripts/bootstrap.py` to validate and start crawling

### Existing Scripts Reference
- `scripts/crawl.py` -- `run(dry_run, crawler_filter, data_root) -> int` (0 = success, 1 = error)
- `scripts/load.py` -- `run(dry_run, loader_filter, data_root, db_path) -> int` (0 = success, 1 = error)
- `scripts/refresh_credentials.py` -- reads curl from `secrets/gamechanger-curl.txt`, writes to `.env`
- `src/gamechanger/client.py` -- `GameChangerClient(min_delay_ms, jitter_ms)`, reads from `.env`
- `src/gamechanger/config.py` -- `load_config(path)` reads `config/teams.yaml`

### Team Config Validation
The bootstrap script checks for placeholder team IDs in `config/teams.yaml` by looking for the `REPLACE_WITH_` prefix. If all teams are placeholders, it reports "No teams configured" with guidance to either:
- Edit `config/teams.yaml` manually, or
- Use the admin UI at `/admin/teams` (after E-042)

This check is a simple pre-flight validation, not team configuration logic.

## Open Questions
None -- all resolved during discovery.

## History
- 2026-03-06: Created. User confirmed scope split: small bootstrap epic now (E-050), broader crawl orchestration captured as IDEA-012. User confirmed team management belongs in admin UI (E-042), not in bootstrap scripts.
- 2026-03-06: Refinement pass -- triaged 18 findings from SE review + Codex spec review. 12 INCLUDED, 6 DISMISSED. Key changes: (1) E-050-02 unblocked (E-049-05 DONE), test file corrected to `tests/test_client.py`, AC-6 gc-app-name logic clarified, AC-9 updated to acknowledge mock signature change. (2) E-050-01 AC-4 field priority specified (first+last, fallback email), Accept header corrected to vendor format, timeout exception added. (3) E-050-03 AC-4 FileNotFoundError handling added, AC-8 states defined, AC-10 rewritten to single implementation path (crawl.run profile param), AC-13 expanded. (4) E-050-04 DoD contradiction fixed. (5) Epic dependencies updated.
- 2026-03-06: COMPLETED. All 4 stories DONE. Delivered: credential health check script (10 tests), profile-aware GameChangerClient (7 new tests, 34 total), bootstrap pipeline script (14 tests), and operator bootstrap guide. Documentation assessment: trigger 1 fires (new feature). E-050-04 (bootstrap-guide.md) is the documentation deliverable. Follow-up: CLAUDE.md Commands section should be updated to include `python scripts/check_credentials.py` and `python scripts/bootstrap.py` (context-layer update for claude-architect).
