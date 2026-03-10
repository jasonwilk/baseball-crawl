# E-075-01: Align Credential Env Var Names

## Epic
[E-075: Mobile Profile Credential Capture and Validation](epic.md)

## Status
`DONE`

## Description
After this story is complete, all credential-related code will use `GAMECHANGER_REFRESH_TOKEN_*` consistently instead of the stale `GAMECHANGER_AUTH_TOKEN_*` name. The `GAMECHANGER_SIGNATURE_*` capture will be removed entirely (signatures are now computed, not stored). This resolves a pre-existing naming split between `.env.example` (which already uses the correct names) and the code (which still uses the old names).

## Context
When the gc-signature algorithm was cracked (2026-03-07), the `.env.example` and auth docs were updated to `GAMECHANGER_REFRESH_TOKEN_*` and the signature env var was dropped. But the client code, credential parser, and proxy addon were not updated to match. This story closes that gap before the addon is upgraded in E-075-02, so the addon writes the correct names from the start.

## Acceptance Criteria
- [ ] **AC-1**: `src/gamechanger/client.py` loads credentials from `GAMECHANGER_REFRESH_TOKEN_*` instead of `GAMECHANGER_AUTH_TOKEN_*`. The `_PROFILE_SCOPED_KEYS` tuple no longer includes `GAMECHANGER_AUTH_TOKEN` or `GAMECHANGER_SIGNATURE`.
- [ ] **AC-2**: `src/gamechanger/credential_parser.py` maps `gc-token` to `GAMECHANGER_REFRESH_TOKEN_WEB` instead of `GAMECHANGER_AUTH_TOKEN_WEB`. The validation check references `GAMECHANGER_REFRESH_TOKEN_WEB`.
- [ ] **AC-3**: `proxy/addons/credential_extractor.py` maps `gc-token` to `GAMECHANGER_REFRESH_TOKEN` (base name, suffix applied at runtime). The `gc-signature` entry is removed from `_BASE_CREDENTIAL_HEADERS`.
- [ ] **AC-4**: All existing tests pass after the rename. Test files that reference the old names are updated to use the new names.
- [ ] **AC-5**: `.env.example` is unchanged (it already uses the correct names). This is a verification, not a modification.
- [ ] **AC-6**: The docstrings in `client.py` and `credential_extractor.py` are updated to reflect the new env var names.

## Technical Approach
This is a mechanical rename across a known set of files. The old base name `GAMECHANGER_AUTH_TOKEN` becomes `GAMECHANGER_REFRESH_TOKEN` in every location. The old `GAMECHANGER_SIGNATURE` entry is deleted (signatures are computed at runtime, not captured/stored).

Key constraint: the `.env` file on the operator's machine uses `GAMECHANGER_AUTH_TOKEN_WEB` today (written by the addon). After this change, the operator will need to rename the key in their `.env` file -- or the code could support both names with a fallback during a transition period. The implementing agent should decide the migration approach, but the story's ACs require the code to read the NEW name as the primary.

Reference files:
- `/workspaces/baseball-crawl/docs/api/auth.md` (lines 246-261 document the old-to-new mapping)
- `/workspaces/baseball-crawl/.env.example` (already uses new names)

## Dependencies
- **Blocked by**: None
- **Blocks**: E-075-02 (addon must write correct names), E-075-03 (validation must check correct names)

## Files to Create or Modify
- `src/gamechanger/client.py` -- rename AUTH_TOKEN to REFRESH_TOKEN in _PROFILE_SCOPED_KEYS, _required_keys, __init__, docstring
- `src/gamechanger/credential_parser.py` -- rename AUTH_TOKEN to REFRESH_TOKEN in header mapping and validation
- `proxy/addons/credential_extractor.py` -- rename AUTH_TOKEN to REFRESH_TOKEN, remove SIGNATURE entry, update docstring
- `tests/test_credential_extractor.py` -- update env var names in test assertions
- `tests/test_credential_parser.py` -- update env var names in test assertions
- `tests/test_client.py` -- update env var names in test fixtures/assertions

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-075-02**: Consistent env var naming. E-075-02 can assume all credential code uses `GAMECHANGER_REFRESH_TOKEN_*` base names.
- **Produces for E-075-03**: Consistent env var naming. E-075-03 can assume `check_credentials` and `GameChangerClient` read `GAMECHANGER_REFRESH_TOKEN_*`.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `docs/api/auth.md` "Deprecated variables" table (lines 256-261) already documents this rename. The code is just catching up.
- This story is in Wave 1 alongside R-01 -- they are independent and can execute in parallel.
