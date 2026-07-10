---
name: worktree-pytest-loads-the-worktree-src
description: MEASURED — pytest run from an epic worktree loads the WORKTREE's src/, not the main checkout's, because PathFinder precedes the appended _EditableFinder on sys.meta_path.
metadata:
  type: project
---

**The Test Execution Constraint in `.claude/agents/code-reviewer.md` is FALSE as written.** It claims
per-story worktree pytest "tests main's code, not the worktree's changes." Measured in E-256 (2026-07-10),
all three invocations from `/tmp/.worktrees/baseball-crawl-E-256/` resolve `src.api.routes.auth` to the
**worktree** copy: `python -m pytest`, bare `pytest`, and `python -c`.

## Mechanism (this is what makes it a rule, not an observation)

The editable install's `MAPPING` really does hardcode `/workspaces/baseball-crawl/src` — that half of the
caveat is true. What it gets wrong is **precedence**. `install()` *appends* the finder:

```
sys.meta_path: [AssertionRewritingHook, DistutilsMetaFinder, BuiltinImporter,
                FrozenImporter, PathFinder, _EditableFinder]
                                ^^^^^^^^^^  ^^^^^^^^^^^^^^ appended, LOSES
```
`PathFinder` searches `sys.path` and is consulted **first**. Under pytest the repo root sits at
`sys.path[0]` because `tests/__init__.py` exists: with `prepend` import mode pytest climbs from the test
module past every `__init__.py`-bearing directory to find the "basedir," lands on the repo root, and
inserts it. `src/__init__.py` exists too, so `src` is a regular package `PathFinder` resolves locally.

Counterfactual (decisive): drop the repo root from `sys.path` and the finder finally serves main's copy.
Neutral cwd (`/tmp`) → main. Main checkout cwd → main.

## The condition is `tests/__init__.py` — NOT the invocation

A plausible rival hypothesis (PM's) was that the mechanism is cwd: `python -m pytest` prepends cwd,
bare `pytest` does not, so the two invocations would differ. **Both premises are true and the conclusion
is false.** Measured, holding invocation fixed and moving only the basedir:

```
cwd=worktree, bare pytest  tests/test_passkey.py        -> WORKTREE   (basedir = repo root)
cwd=worktree, bare pytest  <scratchpad>/test_x.py       -> MAIN       (basedir = scratchpad)
cwd=worktree, python -m pytest <scratchpad>/test_x.py   -> WORKTREE   (-m prepends cwd)
cwd=/tmp,     bare pytest  <scratchpad>/test_x.py       -> MAIN
```

So for anything under `tests/`, **both invocations load the worktree** — pytest's basedir insertion puts
the repo root on `sys.path` before cwd is ever consulted. The real dependency:

- **With `tests/__init__.py`** (today): both invocations → worktree. The constraint is simply FALSE.
- **Without it**: basedir becomes `tests/`, and bare `pytest` → main while `python -m pytest` → worktree.
  Only *then* is it invocation-dependent.

Re-verify before relying on this; a packaging or layout change silently flips it. And do not restate it as
"it depends on the invocation" — that is a **true statement that misleads**, the object this epic kept
producing. Name `tests/__init__.py`.

## Why the false caveat survived

It was **partly true** — the hardcoded `MAPPING` is real, and anyone who read that far would stop. I
relayed it in every verdict this epic and demanded file-inspection in place of test evidence that was
actually valid.

**Consequence:** per-story worktree pytest results ARE meaningful evidence. Weigh them. The closure
full-suite run against the main checkout remains right, but for a different reason — at closure the epic's
changes are in main, where cwd and the installed console script agree.
