---
name: module-global-seams
description: Moving a function to a new module silently re-binds every module global it reads (get_connection, _REPO_ROOT); seams guarded by a swallowed exception detach invisibly
metadata:
  type: project
---

# Module-global seams break silently when a function moves

A function resolves module globals in the module where it is **defined**, not where it is
called. Move it and every global it reads re-binds to the new module's namespace —
including the ones tests patch.

**Why this matters here:** `src/reports/generator.py` is the patched surface. ~43 tests do
`patch("src.reports.generator.get_connection", ...)` to sandbox the DB to `tmp_path`, and
~50 patch `._REPO_ROOT` / `._REPORTS_DIR`. Extracting `cleanup_expired_reports` into
`src/reports/lifecycle.py` (E-256-04) detached **both** seams at once.

**The two seams behave completely differently, and that is the trap:**

- `_REPO_ROOT` / `_REPORTS_DIR` detaching produced **11 test failures**. Loud. Found.
- `get_connection` detaching produced **zero failures** — `generate_report` wraps the
  opportunistic sweep in `try/except Exception` and swallows it by design (E-238-07 AC-3:
  "a cleanup failure must NEVER block generation"). The sweep silently ran against the
  real `data/app.db`. In the main checkout that is a 17 MB live DB with 48 report HTML
  files, and it is where the closure gate runs `pytest`. Only two accidental zeros (no
  expired-with-path rows, no `generating` rows) prevented real data loss.

**Never use test failures as the search method for this class of defect.** They find only
the seams that can fail. Instead: for every moved function, list every module global it
reads, and check whether any caller's test patches that name on the OLD module.

**Fixes, in order of durability:**
1. **Inject the dependency** — make `conn` an explicit parameter (`_conn_scope(conn)`
    yields the caller's connection, or opens and owns one when `None`). The caller's
    sandbox then travels with the argument across the module boundary. This is the only
    remedy that survives the *next* move.
2. Patch the new module's name too — restores the sandbox, leaves the trap armed.
3. Calling it as `newmodule.fn()` does **not** help; the global lookup happens inside
    the callee either way.

**Related:** two path constants can be kept canonical in the NEW module and imported by
the old one — the import binds them as the old module's attributes, so existing
`patch("old_module.CONST")` sites keep working untouched. That trick works for values,
not for functions the callee invokes.

**Corollary — an exception handler that has never fired is indistinguishable from one
that fires every run.** If a swallow guards a cross-module call, log at ERROR and give
the path a test that asserts the guarded work actually happened.
