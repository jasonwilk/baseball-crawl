# IDEA-074: Migrate Starlette Deprecations Before a Framework Upgrade Breaks Them

## Status
`PROMOTED`

Promoted to E-232 (2026-06-07). SE's AST-verified discovery audit corrected this idea's sketch: the real surface is 3 warning families (not 2) — the `TemplateResponse` arg-order half is only 2 call sites in `src/api/main.py` (not 3, and not in route modules), the per-request `cookies=` half is only 4 call sites in `tests/test_admin_merge.py` (not 11), plus a third pytest-asyncio loop-scope config nit. No Starlette/FastAPI version bump required.

## Summary
One-line: Migrate the soon-to-be-removed Starlette APIs the test suite currently warns about (`TemplateResponse` arg order; per-request test-client `cookies=`) so a future Starlette upgrade does not break the app.

## Problem / Opportunity
The full pytest suite emits 14 `DeprecationWarning`s, all from Starlette and all pre-existing (not introduced by E-230, surfaced once RTK's output compression was removed). They are currently non-gating (pytest exits 0), but each names a Starlette API slated for removal — a future Starlette upgrade will turn these into hard breakages. Migrating now is cheap maintenance hygiene; deferring risks a forced scramble during a dependency bump.

Observed in the E-230 closure green-gate run (`/tmp/E-230-green-gate.log`):
1. **11× `starlette/templating.py` / `testclient.py:484` — per-request `cookies=` deprecated**: "Set cookies directly on the client instance instead." Triggered by `tests/test_admin_merge.py`. (Test-side fix.)
2. **3× `starlette/templating.py:161` — `TemplateResponse(name, {"request": request})` arg order deprecated**: replace with `TemplateResponse(request, name)`. Surfaced via `tests/test_admin_opponents.py` (2) + `tests/test_auth.py` (1), but the call sites originate in the app render paths in `src/api/` — so this half is a real (small) production code change, not test-only.

## Why Deferred / Not Now
- Non-gating today: the suite passes (RC=0); the warnings do not fail any test.
- It is maintenance hygiene, not a coaching-value or correctness fix — lower priority than feature/scouting work.
- The user wants it on the backlog to plan as a fast-follow, but not blocking E-230 closure.

## Possible Scope (sketch)
- Audit and migrate the `TemplateResponse(name, {...})` call sites in `src/api/` to the `TemplateResponse(request, name, ...)` signature.
- Move per-request `cookies=` in the affected tests onto the test-client instance (set cookies on the client, not per `.get()`/`.post()` call).
- Re-run the full suite to confirm 0 DeprecationWarnings (or document any residual warnings that originate inside dependencies and are not ours to fix).
- Small epic: touches `src/api/` routes (production) + a few test files; not test-only.

## Related
- E-230 (Fix the 56 Post-RTK Test-Suite Failures — these warnings surfaced once RTK's output compression was removed in E-229 and the suite was made green)
- IDEA-072 (RTK Compression Retrospective Audit — the broader "what else did RTK hide" backward-looking counterpart)

## Notes
Captured 2026-05-31 during E-230 closure (warnings observed in the dogfood green-gate run). User intends to plan this as a fast-follow. Review by 2026-08-29.
