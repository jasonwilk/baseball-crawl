---
name: testing-gotchas
description: Non-obvious pytest/SQLite/ruff gotchas in this repo — db-fixture backing differs per test file (db.backup deadlock), never trust a piped pytest exit code, worktree-pytest src-resolution (pytest DOES see worktree src), and ruff parsing `# noqa` inside prose comments
metadata:
  type: feedback
---

# Testing gotchas (project-specific)

## In an epic worktree, `pytest` exercises the WORKTREE src — but plain `python` does NOT (verified E-247-03)
**Rule:** During dispatch the spawn prompt warns "pytest tests the main checkout's code (not worktree changes) due to the editable install." In practice the resolution depends on HOW you invoke Python, and I verified (E-247-03) it is the OPPOSITE for `pytest`:
- `python -m pytest ...` from the worktree → `import src.*` resolves to the **WORKTREE** source (pytest puts rootdir/cwd on `sys.path` ahead of the editable `.pth`). So pytest DOES exercise your refactored worktree code directly. Verified via `python -c "import src...; print(mod.__file__)"` run *through pytest* → worktree path; a worktree-only new symbol imports fine under pytest.
- plain `python script.py` from the worktree → `import src.*` resolves to the **MAIN** checkout (`/workspaces/baseball-crawl`, the editable install). A worktree-only new symbol raises ImportError.

**Why:** I assumed (per the spawn note) pytest couldn't see my changes and built an importlib harness to compensate; then `test_url_parser.py` importing a brand-new `is_gc_uuid` PASSED under pytest, proving pytest was loading worktree src.

**How to apply:** (1) You can usually just run `pytest` in the worktree to validate refactors directly — don't assume it's testing stale main code. (2) For a genuine PRE-vs-POST byte-identical diff (HARD-GATE stories), exploit the asymmetry: a plain-`python` importlib script gets PRE from normal `from src...` imports (main/editable) and POST by `importlib`-loading the worktree files (inject into `sys.modules` under the canonical name so cross-imports resolve to worktree). That gave a real main-vs-worktree resolver/predicate diff in E-247-03. (3) Don't over-trust either assumption blindly — confirm with `module.__file__` in the exact invocation you're using.

**RE-CONFIRMED E-256-08, and the MECHANISM is now known — it is CONDITIONAL, so do not carry
"pytest sees the worktree" forward unconditionally.**

The editable install is a `MetaPathFinder` whose `MAPPING` really does hardcode
`{'src': '/workspaces/baseball-crawl/src'}` — that half of the old caveat is TRUE. But `install()`
**appends** `_EditableFinder` to `sys.meta_path`, *after* `PathFinder`. `PathFinder` searches
`sys.path` and is consulted first, so whenever the repo root is on `sys.path` the local `src/` wins
and the editable finder is never reached. Counterfactual: repo root ON `sys.path` → worktree; OFF →
`/workspaces/baseball-crawl/src`.

**Two load-bearing conditions:**
1. **`tests/__init__.py` must exist** — pytest's `prepend` import mode walks up past every
   `__init__.py` to find basedir, landing the repo root on `sys.path`. Delete it and bare `pytest`
   falls through to the editable finder → main's `src/`.
2. **cwd / `sys.path` must contain the repo root.**

Confirmed for BOTH `python -m pytest` and bare `pytest` in `/tmp/.worktrees/baseball-crawl-E-256`.
It mattered: story 08 deleted a DB read from a live auth path, and the suite genuinely exercised it.

**The dispatch spawn note and team-lead reminders assert the opposite** ("pytest tests the main
checkout's code"). They are wrong under the two conditions above. Confirm with `module.__file__` in
the exact invocation you are using before relying on either answer.

## Three ways a tool reported zero when the answer was not zero (all E-256-08, all verified)

1. **`files=$(git ls-files ...); ruff check $files` does not word-split** in this shell. ruff got
   **one** argument — a newline-joined mega-string — lint*ed nothing*, warned
   `Failed to lint tests/__init__.py\ntests/conftest.py\n...` on stderr, and **exited 0**. A single
   file yields 4 violations; the "whole tree" yielded 0. The same bug produced
   `python -m pytest $files -> RC=4, "no tests ran"`. **Use `git ls-files -z '<pathspec>' | xargs -0 <tool>`.**
   To check: `set -- $files; echo $#`.

2. **`include` in `pyproject.toml` filters directory walks, not explicitly-named paths.** With
   `[tool.ruff] include = ["src/**/*.py", "scripts/**/*.py"]`, `ruff check tests/` reports
   `All checks passed!` (vacuous), while `ruff check tests/test_cli_creds.py` reports its real
   violations. Count `tests/` with explicit paths or you get a confident zero.

3. **`.pyc` orphans under `__pycache__` are invisible to `git status`** (gitignored). After deleting
   a temp file, `ls` and `git status` said clean; `find . -name '<pattern>'` found the leftover
   `.pyc`. Use `find` for cleanup verification.

## `ruff` parses `# noqa` inside ordinary prose comments
**Rule:** Never write the literal token `# noqa` inside an explanatory comment, even in prose or backticks. ruff's directive scanner does not care that you were *talking about* suppression.

**Why:** In E-256-08 the comment explaining the `TYPE_CHECKING` fix said "...as opposed to a `# noqa` that would hide..." — ruff emitted `warning: Invalid # noqa directive on tests/test_cli_creds.py:24: expected ':' followed by a comma-separated list of codes`. I wrote a lint violation into the comment explaining why I was not writing a lint suppression.

**How to apply:** Say "a blanket suppression comment" instead. Same class as `grep -ci mypy pyproject.toml` → `1`, where the only match was the word "mypy" inside a comment I had just written.

## Never trust a `pytest | tail` exit code as a pass signal
**Rule:** Always capture pytest's OWN return code, never a pipeline's. `python -m pytest ... | tail` reports `tail`'s exit code (≈always 0), NOT pytest's — a hung or failing run can look like "exit 0".

**Why:** During E-236-04 I reported spray tests "passed, exit 0" based on `pytest | tail` background runs; when I re-ran capturing the real RC the truth was RC=124 (timeout/hang). The team lead called this out as exactly the tool-output-integrity trap the repo guards against.

**How to apply:** Run `python -m pytest ... > /tmp/out.txt 2>&1; echo "RC=$?" >> /tmp/out.txt` (RC appended WITHOUT a pipe), then read the file for the real RC and the `N passed`/`N failed` summary line. The harness "background command completed (exit code 0)" also reflects the whole compound command's last stage — not pytest — so don't rely on it either. Also: `-p no:cacheprovider` avoids cache contention; a `pytest-timeout` of 30s/test is configured, so a single hung test is killed at 30s but can still stall a shared run.

## The `db` fixture backing differs per test file — check before reusing `db.backup()`
**Rule:** Before copying a `db.backup(file_conn)` pattern between report test files, check what the source file's `db` fixture is backed by.
- `tests/test_report_plays.py` → `db` is **`:memory:`** → `db.backup(disk_conn)` copies memory→disk (correct).
- `tests/test_report_generator.py` → `db` is **disk-backed at `tmp_path/test.db`** (via `load_real_schema`) → calling `db.backup(file_conn)` where `file_conn` points at that **same path DEADLOCKS SQLite** (the run hangs).

**Why:** In E-236-04 I copied the plays-test backup pattern into a test_report_generator.py test; it deadlocked and stalled shared suite runs, which I initially (wrongly) blamed on environment WAL contention.

**How to apply:** In test_report_generator.py, the `db` fixture already persists committed rows to `tmp_path/test.db`, so a `_fresh_conn()` that opens that same path sees the data directly — NO backup needed. Only use `db.backup()` when the source `db` is `:memory:` and you need it on disk for a function that opens its own connections.
