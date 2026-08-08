---
name: moved-function-resolves-new-module-globals
description: When a function moves between modules, EVERY name it resolves from module globals is a detached test seam — constants, and also get_connection. A swallowed exception hides the detachment.
metadata:
  type: feedback
---

A function moved to a new module reads its **new** module's globals. Every `patch("old.module.NAME")`
aimed at a name that function reads is now pointed at nothing. Implementers reliably spot this for
*constants* (`_REPO_ROOT`, `_REPORTS_DIR`) and reliably miss it for *imported callables*.

**E-256-04.** SE moved `cleanup_expired_reports` to `lifecycle.py` and correctly preserved the
constants seam (canonical in `lifecycle`, re-imported into `generator`, so the ~40 generation-path
patch sites still bind). It missed `get_connection`: the moved function calls `get_connection()`
from *lifecycle's* namespace, while **43 tests patch `src.reports.generator.get_connection`**. And
`generate_report` still calls `cleanup_expired_reports()` with **no conn argument**, so in those 43
tests the sweep opened the real `resolve_db_path()` database. In the worktree there's no `data/`, so
it raised; in the **main checkout** `data/app.db` (17 MB) and 48 report HTMLs exist — that's where
the Step-8 closure gate runs pytest.

**Why no test failed.** The call site wraps it in `try/except Exception:` and swallows by design
("cleanup must never block generation"). The seam fails *silently*. SE's otherwise-sound evidence —
"I saw exactly 11 failures, matching the 11 re-pointed sites" — could not have caught it.

## How to review a cross-module function move

1. For each moved function, list **every free name it resolves from module globals** — constants
   AND imported callables (`get_connection`, `get_app_url`, factory functions).
2. `grep -rno 'old\.module\.<NAME>' tests/` for each. Any hit is a candidate detachment.
3. AST-walk tests for `patches old.module.X` ∧ `calls a moved function`. **This catches direct
   calls only** — you must separately trace *indirect* paths (here: `generate_report` →
   `cleanup_expired_reports`), which is where the real one hid.
4. Check whether the call site swallows exceptions. If it does, "the suite is green" and "the seam
   is attached" are independent facts.
5. Prefer the fix that **removes the hidden global**: give the function an explicit `conn`
   parameter. Re-pointing patch targets restores the sandbox but leaves the trap for the next mover.
6. **The detachment can be more than one call deep.** In E-256-04 the escape was TWO: cleanup AND
   the reaper it calls each resolved their own `get_connection` out of lifecycle. The falsifying
   test's mock reported `Called 2 times`. A correct fix injects *and forwards* — verify the
   contextmanager yields a borrowed conn unchanged and only closes one it opened, that the callee
   is forwarded the conn **before** the caller enters its own scope, and that `commit()` still
   happens (a borrowed conn closed by `closing()` without commit silently discards the write).
7. Prefer the caller acquire the connection through **its own** patched factory and inject it —
   don't assume the caller already holds one (in E-256-04 the sweep was the first statement).
8. Before filing: rule out a global redirect (`conftest.py` autouse, `DATABASE_PATH`,
   `[tool.pytest.ini_options] env`, `pytest-env`) — otherwise the finding is a phantom. Measure
   blast radius against the live dev DB **read-only** (`file:...?mode=ro`) rather than asserting it.
