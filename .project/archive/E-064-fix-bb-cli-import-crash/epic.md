# E-064: Fix bb CLI Import Crash

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
The `bb` CLI crashes immediately on invocation with `ModuleNotFoundError: No module named 'scripts'`. Three CLI modules (`creds.py`, `status.py`, `db.py`) use top-level `from scripts.X import Y` imports, but `scripts/` is not a Python package and is not on `sys.path` when `bb` runs as a console script entry point. This blocks ALL operator CLI usage.

## Background & Context
E-055 delivered the `bb` CLI with 125+ tests passing. The tests pass because pytest adds the project root to `sys.path`, making `scripts/` importable as a namespace package. But when `bb` is invoked as a console script (via the `pyproject.toml` `[project.scripts]` entry point), Python only adds site-packages to `sys.path` -- not the project root. The `from scripts.X` imports fail at module load time.

The error was not caught because:
1. Tests run under pytest, which manipulates `sys.path` (adds CWD/rootdir)
2. The editable install (`pip install -e .`) maps only `src` -> project root. The editable finder's mapping is `{'src': '/workspaces/baseball-crawl/src'}` -- `scripts` is NOT in the mapping.
3. No test exercises the actual `bb` entry point or validates that the CLI module tree can be imported without pytest's `sys.path` additions

**Expert consultation**:
- SE consulted (2026-03-07): Confirmed root cause, recommended Option C (move reusable functions into `src/`, make scripts thin wrappers), flagged additional issues.
- SE + UXD consulted (2026-03-07, code review follow-up): SE clarified path rebasing strategy, migrations packaging, subprocess test approach, and working-directory independence. UXD clarified output format: keep human-readable output, upgrade `print()` to Rich Console (not logging).

## Goals
- `bb` and all its subcommands work when invoked as a console script entry point, from any working directory
- Reusable business logic lives in `src/` (importable via the editable install and console scripts)
- Scripts in `scripts/` become thin CLI wrappers that import from `src/`
- `migrations/` becomes a proper package so `src/db/reset.py` can import it
- A subprocess smoke test of the actual `bb` entry point prevents this class of regression

## Non-Goals
- Redesigning the CLI module structure or command interface
- Changing the `scripts/` standalone invocation interface (`python scripts/check_credentials.py` must still work)
- Refactoring script internals beyond what's needed for the move
- Adding `sys.path.insert()` calls in any `src/` module (solves symptom, not cause)

## Success Criteria
- `bb --help` works without errors when invoked as a console script from any working directory
- `bb status`, `bb creds check`, `bb db backup`, `bb data crawl --help` all work
- All `scripts/` can still be invoked directly (e.g., `python scripts/check_credentials.py`)
- A subprocess-based test of the actual `bb` entry point catches import regressions
- All existing tests continue to pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-064-01 | Move reusable logic to src/ and fix CLI imports | DONE | None | software-engineer |
| E-064-02 | Codify E-064 lessons in the context layer | DONE | E-064-01 | claude-architect |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### Root Cause (SE-confirmed, 2026-03-07)

- The editable install's mapping only contains `{'src': '/workspaces/baseball-crawl/src'}` -- `scripts` is NOT in the mapping
- When `bb` runs as a console script, `sys.path` has only site-packages + editable finder. No project root, no `scripts/__init__.py`
- pytest masks this by adding project root to `sys.path` before tests run
- ALL four CLI modules are affected: `creds.py` (line 11), `status.py` (line 12), `db.py` (lines 12-13) are top-level imports that crash on ANY `bb` invocation including `bb --help`. `data.py` defers imports inside functions (crash at call time only)
- Additional issue: `status.py` imports `_check_single_profile` (private symbol) across module boundary -- fragile coupling

### Fix Approach: Option C (SE-recommended)

Move reusable functions from `scripts/` into `src/`, make scripts thin wrappers. CLI modules import from `src/` directly. No `sys.path` manipulation in any `src/` module.

SE reasoning against other options:
- Option A (importlib.util.spec_from_file_location): Verbose, breaks type checking, only appropriate for unhyphenatable filenames like `proxy.py`'s case
- Option B (sys.path mutation at CLI startup): Global import system mutation, solves symptom not cause
- Option D (make scripts/ a package): Conceptually wrong -- scripts are operator tools not library code

**Concrete moves**:

| From (scripts/) | To (src/) | Functions |
|-----------------|-----------|-----------|
| `scripts/check_credentials.py` | `src/gamechanger/credentials.py` (new) | `check_credentials()`, `check_single_profile()` (renamed from `_check_single_profile`) |
| `scripts/backup_db.py` | `src/db/backup.py` (new) | `backup_database()` and helpers |
| `scripts/reset_dev_db.py` | `src/db/reset.py` (new) | `reset_database()` and helpers |
| `scripts/bootstrap.py` | `src/pipeline/bootstrap.py` (new) | `run()` and helpers |
| `scripts/crawl.py` | `src/pipeline/crawl.py` (new) | `run()` and helpers |
| `scripts/load.py` | `src/pipeline/load.py` (new) | `run()` and helpers |

### Path Rebasing (SE, code review follow-up)

Scripts currently derive repo-root paths using `Path(__file__).resolve().parent.parent` (one level deep in `scripts/`). When functions move to `src/X/Y.py` (three levels deep), the same `.parent.parent` resolves incorrectly.

**Required pattern**: `Path(__file__).resolve().parents[2]` for all modules at the `src/X/Y.py` depth. This is the established project convention (see `/workspaces/baseball-crawl/src/gamechanger/config.py` line 43 and `/workspaces/baseball-crawl/src/cli/proxy.py` line 14). Do NOT build a "walk up to find pyproject.toml" utility.

**Caller-provided paths**: Keep the existing optional-parameter-with-default pattern (e.g., `backup_database(db_path=None)`) where module-level `_DEFAULT_*` constants computed from `__file__` serve as defaults. Callers may override.

**Hard rule**: Never `sys.path.insert()` at module import time in a `src/` module.

### Migrations Packaging (SE, code review follow-up)

`reset_dev_db.py` imports `from migrations.apply_migrations import run_migrations` (deferred). `migrations/` is not a Python package -- same class of bug as `scripts/`.

**Fix**: Make `migrations/` a proper package:
1. Add `migrations/__init__.py` (empty)
2. Add `"migrations*"` to `pyproject.toml`'s `[tool.setuptools.packages.find]` include list
3. Fix `apply_migrations.py` line 56: change `_DEFAULT_DB_PATH = Path("./data/app.db")` (cwd-relative) to `_DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "app.db"` (repo-root-relative)

SE reasoning: `apply_migrations.py` locates SQL files via `Path(__file__).resolve().parent` which still works correctly when `migrations/` is a package. importlib-by-file-path would be inconsistent and break type checking. Moving the runner into `src/` creates an architectural problem since SQL files belong with the migration runner.

### Bootstrap Output Format (UXD, code review follow-up)

The earlier SE recommendation to "replace `print()` with `logging`" is **superseded** by UXD guidance:

- Keep human-readable output. Do NOT switch to structured logging for pipeline output.
- Upgrade `print()` to Rich `Console` in the moved `src/pipeline/bootstrap.py`. This matches every other CLI module (`creds.py`, `status.py`, `db.py` all use Rich Console).
- Use color: green for success stages, yellow for warnings, red for errors.
- The summary block should match `bb status` color-coded style.
- The caller (`data.py`) just calls `run()` and exits -- that clean boundary stays.
- Thin script wrappers also get Rich Console output (consistent operator experience across `bb` commands and direct script invocation).

### Working Directory Independence (SE, code review follow-up)

`bb` must work from any working directory. All file resolution uses `Path(__file__).resolve().parents[N]` -- never cwd-relative paths. The one known cwd-relative path is in `apply_migrations.py` line 56 (fixed as part of migrations packaging above).

### Smoke Test Approach (SE, code review follow-up)

The existing `test_cli.py` uses `typer.testing.CliRunner` which runs in-process and inherits pytest's `sys.path`. These tests passed while the actual `bb` entry point was broken.

**Required approach**: A subprocess test invoking the actual `bb` entry point:
- `subprocess.run(["bb", "--help"], capture_output=True, text=True)`, assert returncode 0
- `bb` is on PATH during pytest (editable install puts it in the same `bin/` as python)
- Use `shutil.which("bb")` guard to skip gracefully if not installed
- Do NOT cd to a temp directory (path resolution is `__file__`-based, not cwd-based)

### Additional Cleanup (SE, initial consultation)

1. Rename `_check_single_profile` -> `check_single_profile` (public API when moved to `src/`)
2. `db.py` has duplicated production guard logic with `reset_dev_db.py` -- consolidate to one place in `src/db/reset.py`
3. `data.py` deferred imports can become top-level once imports are from `src.*`

### New Packages to Create
- `src/db/` (new package: `__init__.py`, `backup.py`, `reset.py`)
- `src/pipeline/` (new package: `__init__.py`, `bootstrap.py`, `crawl.py`, `load.py`)
- `src/gamechanger/credentials.py` (new module in existing package)

### Dependency Notes
- `scripts/bootstrap.py` imports from `scripts/check_credentials`, `scripts/crawl`, and `scripts/load`. When moved to `src/pipeline/bootstrap.py`, these become imports from `src.gamechanger.credentials`, `src.pipeline.crawl`, and `src.pipeline.load`.
- `scripts/crawl.py` and `scripts/load.py` already import from `src/gamechanger/*` -- the moved versions continue this pattern.
- `scripts/crawl.py` uses module-level name resolution for crawler classes (lazy via `_build_crawlers()`) so tests can patch. This pattern should be preserved in the moved version.

### Context Layer Codification Targets (E-064-02)

Five lessons from E-064 need codification so they survive archival:

1. **`scripts/` -> `src/` import boundary**: `src/` modules MUST NOT import from `scripts/`. Scripts are standalone operator tools that import from `src/`. The reverse is not allowed. Home: CLAUDE.md Architecture section + SE agent def scripts guidance.

2. **`parents[N]` convention**: Modules in `src/` use `Path(__file__).resolve().parents[N]` to derive repo-root-relative paths. Never cwd-relative paths, never `sys.path.insert()`. Home: CLAUDE.md Architecture section + `.claude/rules/python-style.md`.

3. **Subprocess smoke tests for console script entry points**: In-process test runners (CliRunner, pytest) add project root to `sys.path`, masking packaging/import errors. Console script entry points need subprocess-based tests that exercise the actual installed entry point. Home: `.claude/rules/testing.md`.

4. **No `sys.path.insert()` in `src/` modules**: Path manipulation belongs only in standalone scripts that need to bootstrap `src.*` imports. `src/` modules are always importable via the editable install. Home: `.claude/rules/python-style.md`.

5. **`migrations/` packaging**: `migrations/` is a proper Python package (has `__init__.py`, included in `pyproject.toml`) because `src/db/reset.py` imports from it. Home: CLAUDE.md Architecture section.

## Open Questions
- None

## History
- 2026-03-07: Created. Blocking bug -- `bb` CLI completely non-functional since E-055 delivery.
- 2026-03-07: SE consultation completed. Confirmed root cause, recommended Option C (move to src/), flagged 4 additional issues. Epic and story updated with SE assessment.
- 2026-03-07: Code review follow-up. SE + UXD consulted on 4 findings + 2 open questions. Key decisions: (1) path rebasing via `.parents[2]` convention, (2) make migrations/ a proper package, (3) subprocess smoke test of actual `bb` entry point, (4) upgrade print() to Rich Console (not logging) per UXD, (5) bb works from any directory, (6) no sys.path.insert in src/ modules. Epic and story updated.
- 2026-03-07: Added E-064-02 (context-layer codification) to prevent lessons from becoming ephemeral on archival. Dispatch Team expanded to include claude-architect.
- 2026-03-07: COMPLETED. E-064-01 moved reusable logic from scripts/ to src/ (9 new files, 14 modified files, subprocess smoke test added). E-064-02 codified 5 lessons into 4 context-layer files (CLAUDE.md, testing.md, python-style.md, software-engineer.md). bb CLI fully operational.
- 2026-03-07: Follow-up work identified via codex code review: double production guard in `bb db reset`, root logger mutation on import, missing standalone script subprocess tests. Captured as E-069.
