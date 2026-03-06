# E-055: Unified Operator CLI

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Replace the current collection of standalone scripts (`scripts/*.py`, `scripts/*.sh`, `proxy/*.sh`) with a single unified CLI entry point (`bb`) that groups related operations under discoverable subcommands. The operator should be able to type `bb --help` and immediately see all available operations grouped by domain, eliminating the need to remember script names, file paths, and flag combinations.

## Background & Context
The project has accumulated 13+ operator-facing scripts across two directories (`scripts/` and `proxy/`), each with its own argparse interface, invocation pattern, and flag conventions. The operator must remember:

- Which script to run for a given task (`refresh_credentials.py` vs `check_credentials.py` vs `bootstrap.py`)
- The correct invocation path (`python scripts/X.py` vs `./proxy/Y.sh` vs `./scripts/Z.sh`)
- The right order of operations (refresh creds -> check creds -> crawl -> load, or just bootstrap)
- Flag names that differ across scripts (`--crawler NAME` vs `--loader NAME` vs `--profile mobile`)

This creates unnecessary cognitive overhead for the single operator (Jason) who runs the system. A unified CLI makes operations self-documenting and reduces the gap between "what do I need to do?" and "how do I do it?".

**Expert consultation**: UX designer consulted for CLI interaction design (command grouping, help text, discoverability). Software engineer consulted for implementation approach (framework selection, entry point configuration, migration strategy).

### UX Designer Consultation Summary

The UX designer recommends organizing commands around **operator tasks** rather than technical components. The key insight: the operator thinks "I need to refresh my data" not "I need to run crawl.py then load.py". Grouping should follow the operator's mental model:

**Recommended command groups:**
- `bb creds` -- credential lifecycle (refresh, check)
- `bb data` -- data pipeline (crawl, load, bootstrap/sync)
- `bb proxy` -- proxy analysis (report, endpoints, refresh-headers, review)
- `bb db` -- database operations (backup, reset)
- `bb status` -- quick health check (creds valid per-profile? last crawl time? DB info?)

**Key UX principles for CLI design:**
1. **Progressive disclosure**: `bb` alone shows groups. `bb data` shows data subcommands. `bb data crawl --help` shows crawl options.
2. **Sensible defaults**: `bb data sync` (the common case) should require zero flags. Power-user flags exist but are not required.
3. **Consistent flag names**: `--profile`, `--dry-run` should work identically everywhere they appear.
4. **Actionable error messages**: When creds are expired, tell the operator exactly what to run next.
5. **Color and formatting**: Use color for status output (green=healthy, red=error, yellow=warning) but degrade gracefully when piped.

**One-command status check**: The designer strongly recommends a `bb status` command that shows the overall system health at a glance -- credential validity, proxy state, last crawl timestamp, database size. This is the "dashboard for the operator" and should be the first thing Jason runs each morning.

### Software Engineer Consultation Summary

The SE recommends **Typer** over Click or raw argparse:

- **Why Typer**: Type-hint driven (aligns with project style), automatic `--help` generation, built-in subcommand groups via `app.add_typer()`, shell completion support, less boilerplate than Click. Typer is built on Click under the hood so it inherits Click's reliability.
- **Why not Click**: More boilerplate (decorators + explicit types), no type-hint integration. Typer wraps Click, so we get Click's power with less code.
- **Why not argparse**: Already proven painful at scale -- each script reimplements its own parser with no shared conventions.

**Implementation approach:**
1. Create `src/cli/` package with `__init__.py` (main app) and one module per command group (`creds.py`, `data.py`, `proxy.py`, `db.py`).
2. Each module defines a `typer.Typer()` sub-app that the main app mounts.
3. Existing `scripts/*.py` retain their `run()` functions as importable library code. The CLI modules are thin wrappers that call these functions.
4. Entry point registered in `pyproject.toml` under `[project.scripts]`: `bb = "src.cli:app"`.
5. Proxy analysis commands (`report`, `endpoints`, `review`) shell out to the existing bash scripts via `subprocess.run()`. Proxy lifecycle commands (start/stop/status/logs) are excluded -- the proxy runs on the Mac host, not inside the devcontainer.
6. Add `typer[all]` to `requirements.txt` (the `[all]` extra includes `rich` for colored output and `shellingham` for shell detection).

**Migration strategy**: The old `scripts/*.py` files stay as-is during the transition. The CLI wraps them. Once the CLI is proven, a follow-up epic can deprecate direct script invocation. This is non-breaking.

## Goals
- Single entry point (`bb`) for all operator commands
- Commands grouped by domain with consistent flag conventions
- Self-documenting: `bb --help` reveals all operations, `bb <group> --help` reveals group commands
- Zero-flag common paths: `bb data sync` and `bb status` work without any flags
- Existing `scripts/*.py` remain importable as library code (non-breaking)

## Non-Goals
- Deprecating or removing existing `scripts/*.py` files (follow-up work)
- Interactive/TUI mode (menus, prompts, wizards)
- Shell completion installation (Typer supports it, but auto-install is out of scope)
- Changing proxy bash scripts to Python (they manage Docker Compose and must run on the Mac host)
- Managing proxy lifecycle (start/stop/status/logs) -- the proxy runs on the Mac host, not inside the devcontainer where the CLI runs
- Installing the CLI in the production Docker image (the production container runs the API server only; operator CLI is devcontainer-only)
- Windows support

## Epic-Level Dependencies
This epic MUST execute after E-042, E-052, E-053, and E-054 because it wraps their final script interfaces:
- **E-042** (Admin Interface and Team Management): E-042-06 adds `--source db|yaml` flag to `scripts/crawl.py` and `scripts/load.py`. The CLI must expose this flag on `bb data crawl` and `bb data load`.
- **E-052** (Proxy Data Lifecycle): Adds session flags (`--session`, `--all`, `--unreviewed`) to proxy report/endpoint scripts.
- **E-053** (Profile-Scoped Credentials): Adds `--profile` to credential check.
- **E-054** (Header Parity Refresh): Creates `scripts/proxy-refresh-headers.py`.

E-051 is independent (no script interface changes).

**Recommended execution order:**
```
E-051 (cert persistence)       ─┐
E-042 (admin + team mgmt)      ─┤
E-053 (profile-scoped creds)   ─┼── parallel
E-054 (header parity refresh)  ─┘
E-052 (proxy data lifecycle)   ─── after E-051
E-055 (unified CLI)            ─── LAST
```

## Success Criteria
- `bb --help` shows all command groups with descriptions
- `bb <group> --help` shows all commands within a group
- Every devcontainer-compatible script operation is accessible through `bb` (proxy lifecycle excluded -- runs on Mac host)
- `bb status` shows credential health (per-profile), last crawl info, and database info in one output
- All existing tests continue to pass (non-breaking migration)
- New CLI commands have tests for argument parsing and error paths

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-055-01 | CLI skeleton with Typer and entry point | TODO | None | - |
| E-055-02 | Credential commands (`bb creds`) | TODO | E-055-01 | - |
| E-055-03 | Data pipeline commands (`bb data`) | TODO | E-055-01 | - |
| E-055-04 | Proxy commands (`bb proxy`) | TODO | E-055-01 | - |
| E-055-05 | Database commands (`bb db`) | TODO | E-055-01 | - |
| E-055-06 | Status dashboard command (`bb status`) | TODO | E-055-02 | - |
| E-055-07 | CLAUDE.md commands section update | TODO | E-055-01 through E-055-06 | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### Framework
- **Typer** (`typer[all]`) for CLI framework. The `[all]` extra includes `rich` for colored output.
- Entry point: `bb = "src.cli:app"` in `pyproject.toml` `[project.scripts]`.
- After `pip install -e .` (or `pip install .`), the `bb` command is available globally.

### Package Structure
```
src/cli/
    __init__.py      # Main Typer app, mounts sub-apps
    creds.py         # bb creds refresh, bb creds check
    data.py          # bb data crawl, bb data load, bb data sync
    proxy.py         # bb proxy report, bb proxy endpoints, bb proxy refresh-headers, bb proxy review
    db.py            # bb db backup, bb db reset
    status.py        # bb status (top-level command via @app.command(), not a sub-app)
```

### Command Map
| CLI Command | Wraps | Notes |
|-------------|-------|-------|
| `bb creds refresh` | `scripts/refresh_credentials.py` | Same flags: `--curl`, `--file` |
| `bb creds check` | `scripts/check_credentials.py` | Flag: `--profile` (validate specific profile or all) |
| `bb data crawl` | `scripts/crawl.py` | Flags: `--dry-run`, `--crawler NAME`, `--profile`, `--source db\|yaml` (default: yaml, per E-042-06) |
| `bb data load` | `scripts/load.py` | Flags: `--dry-run`, `--loader NAME`, `--source db\|yaml` (default: yaml, per E-042-06) |
| `bb data sync` | `scripts/bootstrap.py` | Flags: `--check-only`, `--profile`, `--dry-run`. Alias for bootstrap (validate + crawl + load). |
| `bb proxy report` | `scripts/proxy-report.sh` | Flags: `--session`, `--all`. Shells out to bash. No `--unreviewed` (header reports are point-in-time snapshots). |
| `bb proxy endpoints` | `scripts/proxy-endpoints.sh` | Flags: `--session`, `--all`, `--unreviewed`. Shells out to bash. |
| `bb proxy refresh-headers` | `scripts/proxy-refresh-headers.py` | Flag: `--apply` (dry-run by default). Wraps Python script. |
| `bb proxy review` | `scripts/proxy-review.sh` | Marks sessions as reviewed. Shells out to bash. |
| `bb db backup` | `scripts/backup_db.py` | Flag: `--db-path` |
| `bb db reset` | `scripts/reset_dev_db.py` | Flags: `--db-path`, `--force` |
| `bb status` | New (composite) | Checks creds (per-profile), last crawl, DB info, latest proxy session |

### Wrapper Pattern
CLI modules are **thin wrappers** that import and call existing `run()` / `main()` functions. Example:

```python
# src/cli/data.py
import typer
app = typer.Typer(help="Data pipeline commands.")

@app.command()
def sync(
    check_only: bool = typer.Option(False, "--check-only", help="Validate only, no crawl/load."),
    profile: str = typer.Option("web", help="HTTP header profile (web or mobile)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without API calls or DB writes."),
):
    """Validate credentials, crawl data, and load into database."""
    from scripts.bootstrap import run
    raise SystemExit(run(check_only=check_only, profile=profile, dry_run=dry_run))
```

### Proxy Command Pattern
Proxy analysis commands shell out to bash scripts or call Python scripts. Proxy lifecycle commands (start/stop/status/logs) are excluded -- the proxy runs on the Mac host, not inside the devcontainer where `bb` runs.

```python
# src/cli/proxy.py
import subprocess
import typer
app = typer.Typer(help="Proxy analysis commands.")

@app.command()
def report(
    session: str = typer.Option(None, help="Session ID to report on."),
    all: bool = typer.Option(False, "--all", help="Report across all sessions."),
):
    """Show header parity report from proxy captures."""
    cmd = ["scripts/proxy-report.sh"]
    if session:
        cmd.extend(["--session", session])
    if all:
        cmd.append("--all")
    result = subprocess.run(cmd, check=False)
    raise SystemExit(result.returncode)
```

### Entry Point Configuration and Installation

**pyproject.toml changes:**
```toml
[project]
name = "baseball-crawl"
version = "0.1.0"  # version is REQUIRED for pip install -e . to work
requires-python = ">=3.13"

[project.scripts]
bb = "src.cli:app"
```

The `version` field is mandatory -- `pip install -e .` will fail without it. The current `pyproject.toml` lacks a `version`; this must be added.

**`__main__.py` fallback:** Create `src/cli/__main__.py` so `python -m src.cli` also works as an alternative invocation (useful for debugging or when `bb` is not on PATH):
```python
from src.cli import app
app()
```

**Devcontainer (`postCreateCommand`):** Append `&& pip install -e .` after `pip install -r requirements.txt`. Editable mode means code changes are live immediately -- no reinstall needed after editing CLI modules. The devcontainer PATH already includes `/home/vscode/.local/bin` (where pip installs entry points), so `bb` will be on PATH after install.

**Production Docker image:** The CLI is NOT installed in the production image. The production container runs `uvicorn` only. The `bb` CLI is an operator tool available only in the devcontainer.

**Order of operations (devcontainer):** `pip install -r requirements.txt` first (installs deps), then `pip install -e .` (registers the entry point). The two are complementary, not redundant.

**Why editable mode in dev?** `pip install -e .` creates a `.egg-link` that points back to the source directory. Any changes to `src/cli/` modules take effect immediately without re-running `pip install`. This is critical for the iterative development cycle.

### Color Output Convention
Use `rich` (included with `typer[all]`) for colored status output:
- Green: healthy / success
- Yellow: warning / degraded
- Red: error / failure
- Plain text when stdout is not a terminal (piped to file/grep)

### Parallel Execution Strategy
Story 01 creates `src/cli/__init__.py` with **all sub-app mounts pre-wired** and stub files for each sub-module. This eliminates the `__init__.py` file conflict that would otherwise block parallel execution of stories 02-05. Each subsequent story overwrites its stub file and creates its own test file -- no shared files are modified.

**Dispatch order:**
1. E-055-01 (foundation -- must complete first)
2. E-055-02, E-055-03, E-055-04, E-055-05 (parallel -- no file conflicts)
3. E-055-06 (needs 02 for creds check pattern)
4. E-055-07 (needs all -- context-layer update, route to claude-architect)

### Testing Approach
- Use Typer's `CliRunner` (from `typer.testing`) for CLI argument parsing tests.
- Mock the underlying `run()` functions to test that the CLI correctly maps arguments.
- Do not re-test business logic already covered by existing tests -- only test the CLI layer.
- Each story creates its own test file (`tests/test_cli_*.py`) to avoid file conflicts during parallel execution.

### Scripts Excluded from CLI Scope
`smoke_test.py` and `seed_dev.py` are intentionally NOT wrapped by the CLI. `seed_dev.py` is already covered by `bb db reset` (which calls `reset_dev_db.py`, itself a superset of seeding). `smoke_test.py` could be a future addition (e.g., `bb status --smoke`) but is out of scope for E-055.

## Open Questions
- None -- all questions resolved during expert consultation.

## History
- 2026-03-06: Created. UX designer and SE consulted for CLI design and implementation approach.
- 2026-03-06: Refined E-055-01 installation/PATH story. SE consultation identified gotchas: (1) pyproject.toml needs `version` field for editable install, (2) Dockerfile needs `COPY pyproject.toml .` and `pip install .` (not `-e .` for production), (3) `pip install -e .` and `pip install -r requirements.txt` are complementary (order: deps first, then package). Added AC-3 version requirement, AC-6 Dockerfile specifics, AC-11 `__main__.py` fallback. Updated Technical Notes with full installation details.
- 2026-03-06: Applied holistic review triage findings: (1) P1-4: Removed `--unreviewed` from `bb proxy report` (header reports are point-in-time snapshots). (2) P1-5: Removed Dockerfile install -- CLI is devcontainer-only. Added to Non-Goals. (3) P2-1: Clarified `status` as top-level `@app.command()`, not a sub-app.
- 2026-03-06: Revised based on review findings. (1) Removed proxy lifecycle commands (start/stop/status/logs) -- proxy runs on Mac host, not inside devcontainer. (2) Added `bb proxy refresh-headers` (wraps E-054's `proxy-refresh-headers.py`), `bb proxy review` (wraps E-052's `proxy-review.sh`). (3) Added E-052 session flags (`--session`, `--all`, `--unreviewed`) to `bb proxy report` and `bb proxy endpoints`. (4) Added `--profile` flag to `bb creds check` per E-053. (5) Added epic-level dependencies on E-052, E-053, E-054. (6) Updated E-055-04 to remove lifecycle commands, add new analysis commands. (7) Updated E-055-06 to remove proxy detection, add per-profile creds and latest proxy session. (8) Updated E-055-07 to remove proxy lifecycle command docs. (9) Added non-goal for proxy lifecycle management.
- 2026-03-06: Added E-042 as epic-level dependency. E-042-06 adds `--source db|yaml` flag to `scripts/crawl.py` and `scripts/load.py`. Updated Command Map and E-055-03 ACs to expose `--source` on `bb data crawl` and `bb data load`. Updated execution order diagram. Set to READY after quality checklist passed. Note: dispatch blocked until E-042, E-052, E-053, and E-054 are COMPLETED.
- 2026-03-06: Implementation notes refinement pass (SE corner case analysis). Added advisory notes to stories -- no AC or status changes. (1) E-055-01: logging.basicConfig() import-order hazard and fix. (2) E-055-03: `bb data sync` intentionally has no `--source` flag (deferred to IDEA-012). (3) E-055-04: `cwd=PROJECT_ROOT` required in all subprocess.run() calls for bash scripts. (4) E-055-05: `backup_database()` raises FileNotFoundError, CLI must catch and convert. (5) Epic Technical Notes: `smoke_test.py` and `seed_dev.py` excluded from CLI scope.
