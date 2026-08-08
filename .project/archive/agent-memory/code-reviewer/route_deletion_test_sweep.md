---
name: route-deletion-test-sweep
description: Removal-epic review must sweep for tests that reference a deleted asset by ANY mechanism — import, route request (client.get/post), OR file read / parametrize list — not just imports; never truncate a completeness grep.
metadata:
  type: feedback
---

# Deleting an asset: sweep ALL reference mechanisms, not just imports

**Rule:** When an epic deletes an asset (an HTTP route, a module, a template file, a script), the integration sweep MUST find every surviving test that references it by ANY of three mechanisms — an import is only the most obvious one:
1. **Import** — `from src.deleted import X` (import-graph sweep catches this).
2. **Route request** — `client.get("/dashboard")` then `assert status_code == 200` (no deleted symbol imported → import sweep misses it; FAILS once the route 404s).
3. **File read / parametrize over a path list** — e.g. `test_template_gs_guard.py`'s `_GS_TEMPLATES = [... "dashboard/team_pitching.html" ...]` then `(_TEMPLATES_DIR / path).read_text()` → `FileNotFoundError` once the template file is deleted. No import, no route — a literal path string in a parametrize/data list. This slipped E-239 Phase 4a/4b and only fired at the Phase 5 full-suite gate (12 failures).

A test referencing a deleted asset via mechanism 2 or 3 does NOT import any deleted symbol, so an import-graph sweep misses it entirely — yet it FAILS the closure suite (404 assert, or FileNotFoundError on the deleted file).

**Why:** In E-239 (D2) Phase 4a I verified "no surviving test imports a deleted module" and grepped `/dashboard` in tests/ but piped through `| head`, which truncated the output — I reported the remaining mentions were "intentional canary absence-assertions." Phase 4b Codex then found surviving `GET /dashboard` → `assert 200` tests in `test_admin_routes.py` and `test_auth.py` (the latter touched by NO story). Then the Phase 5 gate found a THIRD form: `test_template_gs_guard.py` parametrized over deleted template file paths and `read_text()`-ed them → FileNotFoundError. Each form was in a file NO story's Files Changed touched.

**How to apply (removal-epic integration review checklist):**
- For each deleted ASSET, also grep for literal-path references beyond imports/routes: `grep -rn "<deleted-filename-or-path>" tests/` (e.g. template filenames in parametrize lists, script names in `subprocess` calls, fixture paths). Confirm each surviving hit's target still exists on disk.
- For each deleted route, grep ALL of tests/ for request-sites: `grep -rnE '\.(get|post|put|delete)\("?<path>' tests/` — and read EVERY hit's assertion, classified:
  - `assert status_code == 200` / asserts deleted-page content → **FAILS** (route now 404). Delete or retarget.
  - `assert status_code == 302` + redirect-to-login, or `== 503` (DB-unavailable) → often still PASS (session/error middleware runs BEFORE route resolution).
  - bare request with no response assertion (used for session/cookie side-effects) → usually passes (middleware sets cookies before the 404), but verify each.
- NEVER pipe a completeness/absence sweep through `| head` (or any truncator). Truncation turns "I saw everything" into a false negative. If output is large, count first (`grep -c`) or read the full list.
- Retarget nuance after a surface removal: there may be NO equivalent endpoint for the same auth level. In E-239, `/dashboard` was the only non-admin 200 page; `/admin/reports` is admin-only (403 for non-admins). So auth tests asserting "valid session reaches a 200 page" can't blind-swap the path — rework the intent (e.g. assert `status_code != 302` / not-redirected-to-login).
- Cross-story ownership trap: a test file "owned" by story N (its nav tests) can contain tests exercising story M's deleted surface (e.g. `test_admin_routes.py` held `/dashboard` page tests). Per-story diff review sees only the changed hunks; the unchanged-but-now-broken tests slip through to the integration pass. Files touched by NO story (`test_auth.py`) are the highest risk.

Related: [[tool-output-integrity]] (clean-read before asserting), the testing.md test-scope discovery pattern.
