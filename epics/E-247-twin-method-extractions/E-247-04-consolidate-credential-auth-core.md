# E-247-04: Consolidate GC credential/auth core duplications

## Epic
[E-247: Twin-Method & Duplicated-Block Extractions](epic.md)

## Status
`TODO`

## Description
After this story is complete, four duplicated blocks in the GC credential/auth core — the .env line-reconstruction loop, the profile-check error ladder, the JWT base64url decode, and the proxy-config resolution — will each be expressed once. These are credential-bearing/never-log paths where silent drift is most dangerous.

## Context
The sweep's M4 finding, in the credential/auth core:
- `merge_env_file` / `atomic_merge_env_file` duplicate the .env line-reconstruction loop (`src/gamechanger/credential_parser.py:652-718`).
- `check_single_profile` re-implements `run_api_check`'s error ladder and inlines display-name logic that `_extract_display_name` already owns (`src/gamechanger/credentials.py:422-453`).
- The JWT base64url decode exists twice with two different padding techniques (`src/gamechanger/credentials.py:55-73`).
- `get_proxy_config` duplicates `resolve_proxy_from_dict` verbatim (`src/http/session.py:92-194`).

Drift in credential-bearing / never-log paths is the most dangerous kind, which is why these are consolidated together under careful, behavior-preserving constraints.

## Acceptance Criteria
- [ ] **AC-1**: Given the .env line-reconstruction loop is duplicated, when the story completes, then it exists once (the sweep suggests `_parse_env_lines` — illustrative) and both `merge_env_file` and `atomic_merge_env_file` use it, producing byte-identical .env output.
- [ ] **AC-2**: Given `check_single_profile` re-implements the error ladder and display-name logic, when the story completes, then it delegates to `run_api_check` and `_extract_display_name` instead of re-implementing them.
- [ ] **AC-3**: Given the JWT base64url decode exists twice, when the story completes, then a single decode helper is used by both call sites and decodes the same tokens to the same payloads (the padding technique is unified without changing the decoded result).
- [ ] **AC-4**: Given `get_proxy_config` duplicates `resolve_proxy_from_dict`, when the story completes, then `get_proxy_config` delegates to `resolve_proxy_from_dict` and resolves the same proxy config for the same inputs.
- [ ] **AC-5**: Given these are credential-bearing paths, when the story completes, then no credential, token, or secret value is logged, displayed, or otherwise newly exposed by the consolidated code (a review confirms logging behavior is unchanged), per the security rules in CLAUDE.md and `.claude/rules/auth-module.md`.
- [ ] **AC-6**: Given the consolidations, when the credential/auth-core test modules (`tests/test_credential_parser.py`, `tests/test_credentials.py`, `tests/test_http_session.py`) run, then they pass. (The full-suite-green check across `tests/` is the epic-level closure gate — Technical Notes "Closure Gate (blocking)" — not a per-story AC, because the whole-suite run is only authoritative in the merged main checkout, not the worktree.)

## Technical Approach
Report locations (re-verify before acting): `src/gamechanger/credential_parser.py:652-718`, `src/gamechanger/credentials.py:422-453`, `:55-73`, `src/http/session.py:92-194`. Each of the four items is independent. The overriding constraint is behavior preservation on credential-bearing paths: the .env output, the profile-check result, the decoded JWT payload, and the resolved proxy config must all be identical before and after, and nothing secret may be newly logged. The auth-module constraints in `.claude/rules/auth-module.md` apply.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/credential_parser.py`
- `src/gamechanger/credentials.py`
- `src/http/session.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No new exposure of credential/token/secret values (review-confirmed)
- [ ] .env output, profile-check result, JWT payload, and proxy config verified unchanged
- [ ] claude-architect review-time security pass completed on this diff
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md, `.claude/rules/auth-module.md`)

## Notes
Security-sensitive (credential-bearing / never-log paths). Per the user's decision (epic Open Questions), **claude-architect performs a review-time security pass** on this story's diff. This remains a `src/` implementation story routed to software-engineer; the CA pass is an advisory security review at review time.
