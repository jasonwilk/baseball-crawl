# E-247-07: Consolidate API middleware/auth-route duplication + APP_URL

## Epic
[E-247: Twin-Method & Duplicated-Block Extractions](epic.md)

## Status
`DONE`

## Description
After this story is complete, the API middleware/auth-route duplications — the "no such table"→503 handler copy-pasted 3×, the cookie→sessions→user lookup reimplemented 3×, the function-local `json`/`base64` re-imports, and the `APP_URL` read in three live places with two divergent default values — will each be consolidated. Unifying the `APP_URL` default is an intended, flagged behavior change to the report-link default when the env var is unset.

## Context
The sweep's M3 finding, in the API layer:
- The "no such table"→503 handler is copy-pasted 3× with inline imports (`src/api/auth.py:368-418`, `src/api/routes/auth.py:160-189`).
- The cookie→sessions→user lookup is reimplemented 3× — `get_login` re-implements what `_get_authenticated_user` already does (`src/api/routes/auth.py:243-257`).
- `json` / `base64` are re-imported function-locally.
- `APP_URL` is read in **three** live places with two divergent default values: `src/reports/generator.py:226` (default `http://localhost:8001`, const at `:65`), `src/api/routes/reports_admin.py:543` (inline default `http://localhost:8001`), and `src/api/routes/auth.py:92`/`:569` (default `http://baseball.localhost:8001`, const at `:73`). Codex spec review surfaced the generator.py site as the third helper missed in the original scoping. Unifying to one default (decided value REVISED at closure to `baseball.localhost:8001` — see epic Open Questions) changes the link default at the sites that currently default to `localhost:8001` (generator.py + reports_admin.py report-links) — the auth.py helper already defaults to `baseball.localhost:8001` and is unchanged.

This is security-relevant (auth/session paths); behavior must stay identical except the sanctioned `APP_URL`-default unification. **The single default is decided: `baseball.localhost:8001`** (epic Open Questions, resolved 2026-06-29 as `localhost:8001`, REVISED at closure 2026-06-30 to `baseball.localhost:8001` for auth-origin coherence with the dev WebAuthn/passkey host) — production sets `APP_URL` explicitly so only the dev unset-default is affected. In practice this moves generator.py + reports_admin.py report-link defaults from `localhost:8001` to `baseball.localhost:8001`; the auth.py magic-link helper already defaulted to `baseball.localhost:8001` and is unchanged.

## Acceptance Criteria
- [ ] **AC-1**: Given the "no such table"→503 handler is copy-pasted 3×, when the story completes, then it is one shared helper used by all three sites, returning the identical 503 response.
- [ ] **AC-2**: Given `get_login` re-implements the authenticated-user lookup, when the story completes, then it delegates to `_get_authenticated_user` (the cookie→sessions→user lookup exists once), preserving identical authentication behavior.
- [ ] **AC-3**: Given `json` / `base64` are re-imported function-locally, when the story completes, then those imports are hoisted to module level and the function-local re-imports are removed.
- [ ] **AC-4**: Given `APP_URL` is read in three live places with two divergent default values, when the story completes, then one `_get_app_url` helper with the single decided default **`baseball.localhost:8001`** is the source, and **all three former sites** (`src/reports/generator.py:226`, `src/api/routes/reports_admin.py:543`, `src/api/routes/auth.py`) use it — no inline `APP_URL` read or local default constant survives at any of the three. When `APP_URL` is unset, every link resolves to `http://baseball.localhost:8001` (dev only — production sets `APP_URL` explicitly).
- [ ] **AC-5**: Given the auth/session paths, when the story completes, then authentication, session lookup, and admin semantics behave identically to before (no auth bypass, no changed session handling) — verified against existing auth tests, per the security rules in CLAUDE.md.
- [ ] **AC-6**: Given the consolidations, when the auth/admin test modules (`tests/test_auth.py`, `tests/test_auth_routes.py`, `tests/test_admin_reports.py`, plus the report-link path in `tests/test_report_generator.py`) run, then they pass. (The full-suite-green check across `tests/` is the epic-level closure gate — Technical Notes "Closure Gate (blocking)" — not a per-story AC, because the whole-suite run is only authoritative in the merged main checkout, not the worktree.)

## Technical Approach
Report locations (re-verify before acting): `src/api/auth.py:368-418`, `src/api/routes/auth.py:160-189`, `:243-257`, `:569`/`:92`, `src/api/routes/reports_admin.py:543`, and the **third APP_URL site** `src/reports/generator.py:226` (default const at `:65`). The sweep suggests `_missing_table_503(...)`, reusing `_get_authenticated_user` from `get_login`, one `_get_app_url` helper, and hoisting imports (illustrative). The single `_get_app_url` helper must cover all three APP_URL read sites including the generator.py one; note the import boundary — if the shared helper lives under `src/api/`, `src/reports/generator.py` importing it is fine (both are `src/`), but the implementing agent owns where the canonical helper lives. The `APP_URL` default unification is the one sanctioned behavior change — the decided single default is **`baseball.localhost:8001`** (REVISED at closure 2026-06-30; the dev WebAuthn/passkey + Traefik host, so APP_URL / WEBAUTHN_ORIGIN / WEBAUTHN_RP_ID stay coherent). All auth/session behavior is otherwise behavior-preserving; do not alter the admin predicate or team-access semantics (CLAUDE.md canonical admin-predicate / team-access rules). **Review-time security pass:** claude-architect reviews this story's diff for auth/session/middleware security regressions (per the user's decision — see epic Open Questions).

## Dependencies
- **Blocked by**: E-247-05 (both touch `src/api/routes/reports_admin.py`)
- **Blocks**: None

## Files to Create or Modify
- `src/api/auth.py`
- `src/api/routes/auth.py`
- `src/api/routes/reports_admin.py`
- `src/reports/generator.py` (the third APP_URL site at `:226` + default const at `:65`)
- `tests/test_auth.py`, `tests/test_auth_routes.py`, `tests/test_admin_reports.py` (extend — assert the unified 503/auth-lookup/APP_URL behavior per AC-5/AC-6; all exist today)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] APP_URL unified to the decided default `baseball.localhost:8001` (AC-4; revised at closure 2026-06-30)
- [ ] Auth/session/admin behavior verified identical (existing auth tests green)
- [ ] claude-architect review-time security pass completed on this diff
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes
The `APP_URL` default is decided: `baseball.localhost:8001` (REVISED at closure 2026-06-30 from the original `localhost:8001`; affects the dev report-link default only when the env var is unset; production sets `APP_URL` explicitly). Runs after E-247-05 (shared `reports_admin.py`). Security-sensitive — claude-architect performs a review-time security pass on this diff (user decision, epic Open Questions).
