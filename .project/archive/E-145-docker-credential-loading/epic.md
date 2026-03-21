# E-145: Fix Docker Credential Loading for Optional Env Vars

## Status
`COMPLETED`

## Overview
Fix `GameChangerClient._load_credentials()` so that ALL credential environment variables -- not just the required ones -- fall back to `os.environ` when absent from the `.env` file. This unblocks the UI Sync feature (E-143) inside Docker, where env vars are injected by Docker Compose and no `.env` file exists.

## Background & Context
E-143 shipped admin UI sync triggers that call `trigger.py` → `_refresh_auth_token()` → `TokenManager.force_refresh(allow_login_fallback=True)`. When the refresh token expires (14-day lifetime), the login fallback requires `GAMECHANGER_USER_EMAIL` and `GAMECHANGER_USER_PASSWORD`. These optional keys are correctly set in Docker Compose's environment block, but `_load_credentials()` only falls back to `os.environ` for keys returned by `_required_keys()`. Optional keys are silently lost, causing login fallback to fail with "Auto-recovery requires GAMECHANGER_USER_EMAIL and GAMECHANGER_USER_PASSWORD in .env."

The root cause is in `src/gamechanger/client.py:628-636`: the env-var fallback loop iterates only over `_required_keys(profile)`, skipping optional keys entirely.

Other optional keys similarly affected (read from `self._credentials` dict downstream but never populated via `os.environ`):
- `GAMECHANGER_ACCESS_TOKEN_{WEB|MOBILE}` -- manual access token fallback path
- `GAMECHANGER_APP_NAME_{WEB|MOBILE}` -- mobile app-name header
- `PROXY_ENABLED`, `PROXY_URL_WEB`, `PROXY_URL_MOBILE` -- proxy configuration (read by `resolve_proxy_from_dict`)
- For mobile profile: `GAMECHANGER_CLIENT_ID_MOBILE`, `GAMECHANGER_CLIENT_KEY_MOBILE`, `GAMECHANGER_REFRESH_TOKEN_MOBILE` (optional for mobile)

## Goals
- All credential env vars load correctly inside Docker containers (no `.env` file)
- Login fallback works when refresh token expires in production Docker deployment
- No behavior change for the devcontainer or local-dev path (`.env` file present)

## Non-Goals
- Refactoring the credential loading architecture beyond the fallback fix
- Adding new credential keys or changing what is required vs. optional
- Modifying Docker Compose configuration or `.env.example`

## Success Criteria
- `_load_credentials()` returns optional keys from `os.environ` when `.env` file is absent or missing those keys
- Login fallback succeeds in Docker when `GAMECHANGER_USER_EMAIL` and `GAMECHANGER_USER_PASSWORD` are set as env vars (not in `.env`)
- Existing tests pass without modification
- New test verifies the env-var fallback covers all credential keys

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-145-01 | Fix env-var fallback to cover all credential keys | DONE | None | - |
| E-145-02 | Update auth-module rule for corrected fallback behavior | DONE | E-145-01 | - |
| E-145-03 | Document Docker credential auto-recovery in admin docs | DONE | E-145-01 | - |

## Dispatch Team
- software-engineer
- claude-architect
- docs-writer

## Technical Notes

### Root Cause Detail
`_load_credentials()` (client.py:628-636) does:
```
env_values = {**dotenv_values(_DEFAULT_ENV_PATH)}
for key in _required_keys(profile):
    if not env_values.get(key):
        val = os.environ.get(key)
        if val:
            env_values[key] = val
```

The fallback loop iterates only over `_required_keys(profile)`. Any key NOT in that tuple is invisible to `os.environ`. In Docker (no `.env` file), `dotenv_values()` returns an empty dict, so optional keys are always `None`.

### Fix Constraint
The fix must preserve the existing precedence: `.env` values take priority over `os.environ`. The simplest approach is to expand the fallback to cover all keys the method's consumers need. The implementing agent decides the exact code pattern -- the constraint is that behavior must be identical when a `.env` file is present and complete.

### Affected Consumers
The `_credentials` dict returned by `_load_credentials()` is consumed by:
1. `__init__` (client.py:148-165) -- reads `GAMECHANGER_BASE_URL`, `GAMECHANGER_DEVICE_ID_{suffix}`, `GAMECHANGER_APP_NAME_{suffix}`, proxy keys via `resolve_proxy_from_dict`
2. `_build_token_manager` (client.py:190-201) -- reads `GAMECHANGER_CLIENT_ID_{suffix}`, `GAMECHANGER_CLIENT_KEY_{suffix}`, `GAMECHANGER_REFRESH_TOKEN_{suffix}`, `GAMECHANGER_ACCESS_TOKEN_{suffix}`, `GAMECHANGER_APP_NAME_{suffix}`, `GAMECHANGER_USER_EMAIL`, `GAMECHANGER_USER_PASSWORD`

### Test Strategy
No existing tests cover `_load_credentials()` env-var fallback behavior. The fix covers all credential keys; tests should verify representative keys from each category (login credentials, profile-scoped optional keys, proxy keys) rather than exhaustively testing every key. Use `monkeypatch.setenv()` for env vars and point `_DEFAULT_ENV_PATH` at a nonexistent path to simulate Docker (no `.env` file). Existing tests in both `tests/test_client.py` and `tests/test_token_manager.py` must pass without modification.

### Context-Layer Update (CA consultation)
`.claude/rules/auth-module.md` line 36 currently says "falls back to `os.environ` only for Docker container compatibility" -- after the fix, update to clarify the fallback applies to **all** keys. One-line change. No CLAUDE.md update needed (it already points to auth-module.md at the right abstraction level).

### Documentation Updates (docs consultation + spec review propagation)
Updates needed (single docs story):
1. `docs/admin/operations.md` Credential Rotation section -- add note that `GAMECHANGER_USER_EMAIL` and `GAMECHANGER_USER_PASSWORD` in the Docker environment enable automatic login fallback when tokens expire.
2. `docs/production-deployment.md` Step 2.4 -- add note that retaining email/password vars in production `.env` is recommended for ongoing auth resilience (not just one-time bootstrap).
3. `docs/admin/credential-refresh.md` lines 85, 95, 109, 227 -- update ".env"-only references to acknowledge environment variables (Docker context).
4. `docs/api/auth.md` line 210 -- update login fallback description to include env var context.
5. `docs/admin/credential-refresh.md` line 229 and `docs/api/auth.md` line 210 -- correct the stale claim that "`force_refresh()` does not attempt login." Since E-143, `trigger.py:99` calls `force_refresh(allow_login_fallback=True)`, which does attempt login via `_handle_401_with_fallback()`.

### Error Message Propagation (spec review)
`token_manager.py` error messages at lines 316 and 650 reference ".env" as the sole credential source. After E-145-01 makes env vars work in Docker, these messages should say ".env or environment" (or equivalent). Included in E-145-01 scope since they're in the same source file area.

## Open Questions
- None (root cause verified by code reading)

### Consultation Log
- **SE**: Consulted. Confirmed full optional key inventory, recommended merge approach, provided test strategy. Findings incorporated.
- **CA**: Consulted. One-line auth-module.md update needed. Separate story (E-145-02) per context-layer routing.
- **docs-writer**: Consulted. Two doc files need auto-recovery notes. Single story (E-145-03).
- **api-scout**: Not consulted. This bug is about Python `dotenv_values()` vs `os.environ` loading (filesystem/runtime behavior), not API auth protocol, endpoint schemas, or credential patterns. api-scout's domain is API exploration and endpoint documentation. The auth-module rule (CA's domain) already covers the loading pattern.

## History
- 2026-03-21: Created. Bug blocks E-143 UI Sync in production Docker deployment.
- 2026-03-21: Spec review complete. 3 iterations (2 codex + 1 code-reviewer), 8 findings accepted, 2 dismissed. All consistency sweeps clean. Status set to READY.
- 2026-03-21: Dispatch started. Epic set to ACTIVE. E-145-01 assigned to SE.
- 2026-03-21: All stories implemented and reviewed. Codex found 1 finding (client.py error message) -- remediated. Integration CR clean. Epic COMPLETED.

### Documentation Assessment
Documentation impact addressed by E-145-03 (dedicated docs story updating operations.md, production-deployment.md, credential-refresh.md, and auth.md).

### Context-Layer Assessment
Context-layer impact addressed by E-145-02 (dedicated CA story updating auth-module.md).

| Trigger | Verdict | Notes |
|---------|---------|-------|
| New agent or agent role change | NO | No agent changes |
| New rule, skill, or hook | NO | No new rules/skills/hooks |
| CLAUDE.md update needed | NO | CLAUDE.md already points to auth-module.md at correct abstraction |
| Agent memory update needed | NO | PM memory updated separately during closure |
| Existing rule/skill content invalidated | NO | E-145-02 already updated auth-module.md |
| New convention or workflow pattern | NO | No new conventions introduced |
