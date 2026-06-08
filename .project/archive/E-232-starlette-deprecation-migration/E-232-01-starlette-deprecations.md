# E-232-01: Migrate Starlette Deprecations (TemplateResponse arg order + per-request cookies)

## Epic
[E-232: Clear the Test-Suite Deprecation Warning Surface (Starlette + pytest-asyncio)](../E-232-starlette-deprecation-migration/epic.md)

## Status
`DONE`

## Description
After this story is complete, the app's two error-handler render calls in `src/api/main.py` use the request-first `TemplateResponse` signature instead of the deprecated name-first form, and the four deprecated per-request `cookies=` calls in `tests/test_admin_merge.py` set their CSRF cookie on the test-client instance instead. The two Starlette deprecation-warning families are eliminated without any framework version change.

## Context
These are the two Starlette deprecation families surfaced once E-229 removed RTK's output compression and E-230 made the suite green. Both name APIs slated for removal in a future Starlette release, so migrating now avoids a forced break during a later dependency bump. The surface is small and AST-verified: only 2 production call sites and 4 test call sites carry the deprecated forms (see epic Technical Notes "Surface inventory"). The migrated request-first `TemplateResponse` signature is confirmed supported on the pinned Starlette 0.41.3, so this is a pure call-site rewrite with no requirements change.

## Acceptance Criteria
- [ ] **AC-1**: Given the error handlers in `src/api/main.py`, when this story is complete, then both the 404 and 500 handlers render via the request-first `TemplateResponse` form (per epic Technical Notes "TemplateResponse migration shape"), each preserving its existing `status_code`, and `src/api/main.py` contains zero name-first `TemplateResponse(name, {...})` calls.
- [ ] **AC-2**: Given the four per-request `cookies=` POSTs in `tests/test_admin_merge.py` (lines 386, 482, 654, 807 at planning time), when this story is complete, then each sets `csrf_token` on the `TestClient` instance before the POST (per epic Technical Notes "Per-request cookies migration shape"), and `tests/test_admin_merge.py` contains zero per-request `.post(..., cookies={...})` calls.
- [ ] **AC-3 (cookies family verification)**: Given the per-request cookies migration, when `pytest tests/test_admin_merge.py -W "error::DeprecationWarning:starlette.testclient"` is run, then it FAILS before migration and PASSES after (per epic Technical Notes "Verification"). The module-scoped filter promotes only the per-request `cookies=` warning (attributed to `starlette.testclient`) to an error, so dependency-internal and unrelated deprecation warnings — including the pytest-asyncio warning, which is a `DeprecationWarning` subclass — do not affect this command.
- [ ] **AC-4 (TemplateResponse 500-handler verification)**: Given the 500 error-handler migration, when `pytest tests/test_auth.py::TestFailClosedMissingAuthTables::test_non_table_operational_error_propagates -W "error::DeprecationWarning:starlette.templating"` is run, then it FAILS before migration and PASSES after (per epic Technical Notes "Verification"). The module-scoped filter promotes only the `TemplateResponse` arg-order warning (attributed to `starlette.templating`) to an error.
- [ ] **AC-5 (TemplateResponse 404-handler verification)**: Given the 404 error-handler migration, when this story is complete, then the 404 handler's migration is verified statically by AC-1 (zero name-first calls in `src/api/main.py`). A route-driven `-W error::DeprecationWarning` test of the 404 handler is explicitly NOT required, because no test in the suite reaches the custom 404 handler (per epic Technical Notes "Verification"). A direct-call unit test invoking `not_found_handler(request, exc)` under `-W error::DeprecationWarning` MAY be added but is optional.
- [ ] **AC-6**: Given this story's changes, when the story's targeted tests are run during dispatch — `tests/test_admin_merge.py`, the named `test_auth.py` test from AC-4, and any test files that import from `src/api/main.py` (discovered per the testing rule on changed contracts) — then they report 0 failed (no regressions in the affected surface), and `requirements.in`, `requirements.txt`, and `pyproject.toml [project.dependencies]` are unchanged. Full-suite-green (`python -m pytest tests/` in the main checkout, 0 failed) is asserted at epic closure per the Full-Suite-Green Closure Gate, not as a per-story acceptance run.

## Technical Approach
Both `TemplateResponse` call sites are in the `src/api/main.py` exception handlers and have `request: Request` in scope; convert each to the request-first form described in the epic Technical Notes, keeping the `status_code` argument. The four test call sites are in `tests/test_admin_merge.py`, each inside a `with TestClient(app) as c:` block where the CSRF token is already read from an earlier GET; move the cookie from the per-request `.post()` call onto the client instance per the epic Technical Notes. Do not change the surrounding block structure, the `csrf` derivation, or any assertion. Verify each warning family per its AC and the epic Technical Notes "Verification" section, using the module-scoped `-W` filters so each command promotes only its own targeted warning: the cookies family via the `starlette.testclient`-scoped run on `tests/test_admin_merge.py` (AC-3), the 500 handler via the `starlette.templating`-scoped run on the named `test_auth.py` test (AC-4), and the 404 handler statically via AC-1 plus an optional direct-call unit test (AC-5) — do NOT attempt a route-driven 404 test, which is unreachable via the auth-middleware redirect. Per the testing rule on changed contracts, discover and run any test files that import from `src/api/main.py` in addition to the named paths.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/main.py` (modify — 2 error-handler call sites)
- `tests/test_admin_merge.py` (modify — 4 per-request cookie call sites)

## Agent Hint
software-engineer

## Definition of Done
- [ ] Both error handlers in `src/api/main.py` migrated to the request-first `TemplateResponse` form (zero name-first calls remain); each preserves its `status_code`
- [ ] All 4 per-request `cookies=` POSTs in `tests/test_admin_merge.py` moved to set `csrf_token` on the `TestClient` instance (zero per-request `cookies=` POSTs remain)
- [ ] Module-scoped verification commands pass: AC-3 (`starlette.testclient`) and AC-4 (`starlette.templating`) each fail before / pass after migration
- [ ] No regressions in the affected surface (targeted tests + test files importing from `src/api/main.py`); `requirements.in` / `requirements.txt` / `pyproject.toml [project.dependencies]` unchanged
- [ ] Code follows project style (see CLAUDE.md)

## Notes
This story does NOT touch `pyproject.toml`'s pytest config — the pytest-asyncio loop-scope deprecation is handled independently in E-232-02 (different file, different warning family, no overlap).
