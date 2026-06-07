# E-232: Clear the Test-Suite Deprecation Warning Surface (Starlette + pytest-asyncio)

## Status
`READY`

## Overview
Migrate the small set of soon-to-be-removed framework APIs the pytest suite currently warns about — the legacy `TemplateResponse(name, {...})` arg order in the app's error handlers and the deprecated per-request `cookies=` form in one test file — and silence the unrelated pytest-asyncio loop-scope deprecation with a one-line config. This is maintenance hygiene that future-proofs the app against a forced scramble when Starlette (or pytest-asyncio) eventually removes these APIs.

## Background & Context
Promoted from **IDEA-074** (`/workspaces/baseball-crawl/.project/ideas/IDEA-074-starlette-deprecation-migration.md`). The full pytest suite emits a handful of `DeprecationWarning`s, all pre-existing — they were surfaced once E-229 removed RTK's output compression and E-230 made the suite green. They are non-gating today (the suite exits 0), but each names an API slated for removal, so a future dependency bump would turn them into hard breakages.

A complete AST-verified audit of the deprecation surface (performed by software-engineer during E-232 discovery) corrected the idea's original sketch. The real surface is **smaller and three-family**, not the two families the idea estimated:

1. **Legacy `TemplateResponse(name, {...})` arg order — 2 call sites.** Of 52 `TemplateResponse(` calls in `src/`, only 2 use the deprecated name-first signature; both are the error handlers in `src/api/main.py` (lines 115, 123). Every call in `auth.py` / `dashboard.py` / `admin.py` is already migrated to the request-first form. This is a production code change (small, mechanical).
2. **Per-request `cookies=` on TestClient — 4 call sites.** Of 351 `cookies=` occurrences in `tests/`, 347 are the non-deprecated constructor form `TestClient(app, cookies={...})`. Only 4 are the deprecated per-request `.post(..., cookies={...})` form, all in `tests/test_admin_merge.py` (lines 386, 482, 654, 807). No cross-request variance: in each case the `csrf` token is read from a GET earlier in the same `with TestClient(app) as c:` block and used for that block's single POST.
3. **pytest-asyncio loop-scope deprecation (NEW — beyond the idea's two).** `PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.` (pytest-asyncio 0.25.0). This is a pytest-asyncio warning, not Starlette. No asyncio config exists in `pyproject.toml` today. SE recommends folding it into this epic — same "clean the warning surface" goal, trivial.

**Key de-risk:** the request-first `TemplateResponse(request, name)` signature IS supported on the pinned Starlette 0.41.3 (verified by SE). This epic is a pure call-site rewrite — NO version bump, NO `requirements.in` / `requirements.txt` / `pyproject.toml` dependency change. The pins (`starlette~=0.41`, `fastapi~=0.115`) are untouched. All three warnings are deprecation warnings only (not errors) on the pinned versions — non-breaking today; this is future-proofing.

Already clean (no work needed): `@app.on_event` is not used — `main.py` already uses the modern `lifespan=` pattern.

## Goals
- Migrate the 2 legacy `TemplateResponse(name, {...})` error-handler call sites in `src/api/main.py` to the request-first signature.
- Migrate the 4 deprecated per-request `cookies=` call sites in `tests/test_admin_merge.py` to set cookies on the test-client instance.
- Add the `asyncio_default_fixture_loop_scope` pytest-asyncio config to silence the loop-scope deprecation.
- Prove the targeted Starlette warnings are gone via module-scoped `-W` filters (`error::DeprecationWarning:starlette.testclient` and `error::DeprecationWarning:starlette.templating`) on the affected paths, and the pytest-asyncio warning via config-key presence, with no new regressions.

## Non-Goals
- **No Starlette / FastAPI version bump.** The migrated signature already works on the pinned versions; touching `requirements.in`, `requirements.txt`, or `pyproject.toml [project.dependencies]` is out of scope.
- **No helper/wrapper refactor.** Only `main.py` carries legacy calls; the 4 `Jinja2Templates(...)` instances need no centralizing.
- **No audit of warnings that originate inside dependencies** (third-party-internal deprecations we cannot fix). If any such residual warning surfaces, it is documented, not chased.
- **No broader "what else did RTK hide" audit** — that is the separate IDEA-072 retrospective.

## Success Criteria
- `src/api/main.py` contains zero `TemplateResponse(name, {...})` name-first calls; both error handlers use the request-first form and preserve their `status_code`.
- `tests/test_admin_merge.py` contains zero per-request `.post(..., cookies={...})` calls; the 4 affected POSTs set `csrf_token` on the client instance instead.
- `pyproject.toml [tool.pytest.ini_options]` declares `asyncio_default_fixture_loop_scope`.
- The two Starlette families verify via module-scoped `-W` runs that each fail before and pass after migration (per Technical Notes "Verification"): the per-request `cookies=` family under `-W "error::DeprecationWarning:starlette.testclient"` on `tests/test_admin_merge.py`, and the `TemplateResponse` 500-handler family under `-W "error::DeprecationWarning:starlette.templating"` on the named `test_auth.py` test. The 404 handler is verified statically (zero name-first calls in `main.py`), as no test reaches the custom 404 handler.
- The pytest-asyncio family verifies via config-key presence in `pyproject.toml` as the authoritative check; the loop-scope warning's disappearance from a suite run is a best-effort secondary signal only (per Technical Notes "Verification").
- The full `python -m pytest tests/` suite is green (0 failed) at epic closure per the Full-Suite-Green Closure Gate — no regressions.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-232-01 | Migrate Starlette deprecations (TemplateResponse arg order + per-request cookies) | TODO | None | - |
| E-232-02 | Silence pytest-asyncio loop-scope deprecation via config | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Surface inventory (AST-verified)
| Family | Files | Lines | Type |
|--------|-------|-------|------|
| `TemplateResponse(name, {...})` arg order | `src/api/main.py` | 115, 123 | production |
| Per-request `cookies=` on TestClient | `tests/test_admin_merge.py` | 386, 482, 654, 807 | test |
| pytest-asyncio loop-scope unset | `pyproject.toml` | `[tool.pytest.ini_options]` (line 31) | config |

### TemplateResponse migration shape
The deprecated form is `TemplateResponse(name, {"request": request}, ...)`. The migrated request-first form takes `request` as the first positional argument and drops it from the context dict (it is no longer passed via the dict). The `status_code` keyword argument is preserved unchanged. Both call sites have `request: Request` in scope. This signature is supported on the pinned Starlette 0.41.3.

### Per-request cookies migration shape
The deprecated form passes `cookies={...}` as a keyword argument to a per-request call (`.post(...)`). The migrated form sets the cookie on the `TestClient` instance before the request, then issues the request without the per-request `cookies=` kwarg. The `csrf` value and surrounding `with TestClient(app) as c:` block structure are unchanged; only the cookie-delivery mechanism moves from the per-request call onto the client instance. (Note: httpx's TestClient already auto-persists the earlier GET's `Set-Cookie`, so the explicit cookie is arguably redundant — but the safe, behavior-preserving migration is to set it on the client instance, not to delete it.) Attribution detail: this deprecation warning is RAISED BY httpx (`httpx/_client.py:806`, `stacklevel=2`), not by Starlette — the stacklevel attributes the warning frame to the caller, `starlette.testclient`. So the module-scoped filter token for this family is `starlette.testclient` even though httpx is the code that calls `warnings.warn`.

### pytest-asyncio config
Add `asyncio_default_fixture_loop_scope` under the existing `[tool.pytest.ini_options]` table in `pyproject.toml` (which today contains only `timeout = 30`). A `"function"` loop scope is the conventional default and matches current implicit behavior. This is a config-only change — no dependency change.

### Verification
After migration, prove the targeted deprecation warnings are gone by promoting ONLY each targeted warning to an error using a MODULE-SCOPED `-W` filter on the path that exercises it. Module scoping (the `:module` field of the `-W` spec) promotes only warnings whose origin frame is attributed to that module, so dependency-internal and unrelated deprecation warnings do not affect the command. This matters here specifically because the pytest-asyncio `PytestDeprecationWarning` (E-232-02's target) IS A SUBCLASS of `DeprecationWarning` — a bare `-W error::DeprecationWarning` would also promote it and FAIL on the still-present asyncio warning if E-232-01 runs before E-232-02 (the two stories are order-independent). Module-scoped filters keep the two stories decoupled. The three families verify differently because they have different test coverage:

- **Per-request `cookies=` family** — `pytest tests/test_admin_merge.py -W "error::DeprecationWarning:starlette.testclient"` FAILS before migration and PASSES after. This file holds all 4 deprecated call sites; the filter token is `starlette.testclient` (the warning is raised by httpx but attributed there by stacklevel — see "Per-request cookies migration shape").
- **`TemplateResponse` 500 handler** — `pytest tests/test_auth.py::TestFailClosedMissingAuthTables::test_non_table_operational_error_propagates -W "error::DeprecationWarning:starlette.templating"` FAILS before migration and PASSES after. This is the ONE test in the suite that reaches the 500 handler: it forces a `sqlite3.OperationalError` that propagates to `ServerErrorMiddleware`, which invokes the custom 500 handler (`main.py` line 123). The filter token is `starlette.templating`.
- **`TemplateResponse` 404 handler** — verified STATICALLY via "zero name-first calls in `src/api/main.py`" (the AC-1 check). A route-driven `-W error` test is NOT required and MUST NOT be added as a gate, because no test can reach the custom 404 handler: there are zero `raise HTTPException(404)` call sites in the app; route-level 404s return a `Response`/`HTMLResponse` directly and bypass `@app.exception_handler(404)`; and unauthenticated requests to nonexistent paths are redirected to `/auth/login` by the auth middleware before routing ever reaches a 404. A direct-call unit test that invokes `not_found_handler(request, exc)` under `-W "error::DeprecationWarning:starlette.templating"` MAY optionally be added for belt-and-suspenders coverage, but is not mandatory and is not a gate.

The pytest-asyncio warning is suite-wide config and is verified by the config key's presence in `pyproject.toml` (the authoritative, unconditional check); its disappearance from a normal suite run is a best-effort secondary signal only (the warning fires only under certain async-fixture conditions, so its absence does not by itself prove the config is correct).

### Closure gate
The Full-Suite-Green Closure Gate applies: `python -m pytest tests/` must report 0 failed in the main checkout with the epic's changes applied. ACs must not break any existing test.

## Open Questions
- None. The surface is fully enumerated and AST-verified; the migrated signatures are confirmed supported on the pinned versions.

## History
- 2026-06-07: Created (DRAFT). Promoted from IDEA-074. Scope corrected from the idea's sketch by SE's AST-verified discovery audit: 3 warning families (not 2), 2 production lines + 4 test lines + 1 config line (not 11+3), no requirements/version change required.
- 2026-06-07: Set to **READY** after one internal review iteration and one Codex spec-review iteration, all accepted findings incorporated, two post-incorporation consistency sweeps run (the second caught one cascade-drift fix in epic Goals). Domain expert consulted: software-engineer (AST-verified deprecation-surface audit in discovery; module-scoped `-W` filter-token confirmation during Codex triage). No coaching-domain consultation required (maintenance hygiene, no coaching value surface).

  ### Review Scorecard

  | Review pass | Raised | Accepted | Dismissed / no-change | Notes |
  |---|---|---|---|---|
  | Internal iter 1 — CR spec audit | 3 | 2 (S-1 AC-3 vacuous-pass; S-2 AC-1-authoritative) | 1 (A-1 advisory — already prescribed) | Verdict CLEAN, no MUST-FIX. S-1 converges with SE MUST-FIX below. |
  | Internal iter 1 — Holistic team (SE) | 3 | 1 (MUST-FIX AC-3) | 2 (MINOR-1, MINOR-2 — confirmations) | SE MUST-FIX is the SAME finding as CR S-1 (AC-3 vacuous-pass), empirically verified. |
  | Codex iter 1 | 5 | 5 (P1 per-story full-suite; P2 AC-3 escape-hatch; P2 asyncio best-effort-AC; P3 DoD boilerplate; P2 Success-Criteria mismatch) | 0 | Exit 0. Findings P2/P3/P2 were fallout from the iter-1 AC-3 split. |
  | **Total** | **8 distinct** (AC-3 counted once across CR+SE convergence) | **7 distinct fixes** | **3 no-change** (A-1, SE MINOR-1, SE MINOR-2) | Raw raised = 11; dedup of the 1 CR↔SE convergent finding → 8 distinct; 7 distinct fixes applied (2 internal + 5 Codex). |
