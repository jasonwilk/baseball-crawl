# CR-6: Pipeline & CLI Review

**Files reviewed:**
- `src/pipeline/bootstrap.py`
- `src/pipeline/crawl.py`
- `src/pipeline/load.py`
- `src/cli/data.py`
- `src/cli/db.py`
- `src/cli/creds.py`
- `src/cli/proxy.py`
- `src/cli/__init__.py`

---

## Critical Issues

### 1. Import boundary violation: `proxy.py` imports from `scripts/` via importlib

**File:** `src/cli/proxy.py:48-54`

`_load_refresh_headers_module()` uses `importlib.util.spec_from_file_location()` to dynamically load `scripts/proxy-refresh-headers.py`. CLAUDE.md states: "Import boundary: `src/` modules MUST NOT import from `scripts/`." Dynamic loading via importlib is functionally equivalent to an import — the script's module-level code executes and its namespace is consumed by calling `module.run()`. Other proxy commands correctly use `subprocess.run()` to invoke scripts, which stays on the right side of the boundary.

**Recommendation:** Replace the importlib approach with `subprocess.run()` like the adjacent `report`, `endpoints`, and `review` commands. The `--apply` flag can be passed as a CLI argument.

### 2. Importing private names from `credentials` module

**File:** `src/cli/creds.py:23-26`

```python
from src.gamechanger.credentials import (
    ...
    _ALL_PROFILES,
    _run_api_check,
    ...
)
```

Two leading-underscore names (`_ALL_PROFILES`, `_run_api_check`) are imported from `src.gamechanger.credentials`. The underscore convention signals these are module-internal. `_run_api_check` is a function with a meaningful contract that `creds.py` depends on for the `capture` command's API validation section. These should either be made public (remove underscore) or a public wrapper should be provided.

**Severity:** Warning — not a bug, but creates fragile coupling to internal implementation details. A refactor of `credentials.py` internals could silently break `creds.py`.

---

## Warnings

### 1. Loose `object` type hints across pipeline modules

- `src/pipeline/load.py:29` — `_run_roster_loader(db, config: object, ...)` — should be `CrawlConfig`
- `src/pipeline/load.py:58` — `_run_game_loader(db, config: object, ...)` — should be `CrawlConfig`
- `src/pipeline/load.py:97` — `_run_season_stats_loader(db, config: object, ...)` — should be `CrawlConfig`
- `src/pipeline/load.py:128` — `_LOADERS: list[tuple[str, object]]` — the callable type should be specific
- `src/pipeline/crawl.py:43` — `_build_crawlers() -> list[tuple[str, object]]` — same issue

Using `object` defeats static analysis. The `config` parameter is always `CrawlConfig` and the runners/factories are callables with known signatures. At minimum, `config: CrawlConfig` would catch misuse. Python style rules require type hints for all function parameters in `src/`.

### 2. Missing type hints and null safety in `proxy.py`

**File:** `src/cli/proxy.py:48-54`

```python
def _load_refresh_headers_module():
```

- No return type annotation (style rules: "Use type hints for all function parameters and return types in `src/`").
- No null check on `spec` (returned by `spec_from_file_location`) or `spec.loader` before calling `spec.loader.exec_module()`. If the script file is missing or malformed, this will raise an unhelpful `AttributeError: 'NoneType' object has no attribute 'exec_module'`.

### 3. db_path resolution logic duplicated in three places

The pattern "check `DATABASE_PATH` env var → resolve relative to project root → fallback to default" appears in:
- `src/pipeline/crawl.py:121-129`
- `src/pipeline/load.py:158-164`
- `src/cli/data.py:430-436`

Each implementation is slightly different. `crawl.py` uses a local `default_db` and checks `db_path is not None` first; `load.py` falls back to the `db_path` parameter; `data.py:_resolve_db_path()` returns directly. A single shared helper would reduce drift risk.

### 4. `bootstrap.py` does not pass `source` or `db_path` to crawl/load stages

**File:** `src/pipeline/bootstrap.py:115,129`

The `sync` command (via `bootstrap.run()`) always uses YAML config (`source="yaml"`) for both crawl and load. This is documented behavior ("Uses YAML team config by default"), but the `load` stage will call `load_config(db_path=_DB_PATH)` which attempts a DB lookup for `internal_id`. If the DB doesn't exist yet during a first-time bootstrap, this silently leaves `internal_id=None`, and `_run_game_loader` will raise `ValueError` at line 74-77. This is caught by the broad `except Exception` in `load.py:207`, but the error message could be clearer about the prerequisite.

---

## Minor Issues

### 1. Unnecessary import alias in `data.py`

**File:** `src/cli/data.py:229`

```python
from src.gamechanger.loaders.scouting_loader import ScoutingLoader as _ScoutingLoader
```

The `_ScoutingLoader` alias with underscore prefix serves no purpose — `ScoutingLoader` is used only within the function scope and doesn't shadow anything. The `TYPE_CHECKING` import at module level (line 17) already uses the unaliased name.

### 2. `_echo_dry_run_config` uses `object` type and `type: ignore` comments

**File:** `src/cli/data.py:420-427`

```python
def _echo_dry_run_config(config: object) -> None:
    typer.echo(f"Season: {config.season}")  # type: ignore[attr-defined]
```

Three `type: ignore` comments are needed because `config` is typed as `object`. Typing it as `CrawlConfig` would eliminate these suppressions.

### 3. Bare `except Exception` without `noqa` comment in `creds.py`

**File:** `src/cli/creds.py:150` (inside `_decode_jwt_exp`)

```python
    except Exception:  # noqa: BLE001
```

This does have the noqa comment — confirmed OK. No issue here. (Self-correction during review.)

---

## Observations

1. **TeamRef propagation is correct for the game loader path.** `load.py:78-82` constructs `TeamRef` from `team.internal_id` (which comes from `CrawlConfig`) and passes it to `GameLoader`. The `internal_id is None` check at line 73 provides a clear error.

2. **Repo-root resolution is consistent.** All modules use `Path(__file__).resolve().parents[2]` with accurate comments explaining the depth. This follows the project convention.

3. **Error handling in scouting pipeline is thorough.** `data.py:241-248` wraps the entire pipeline in a try/except, and individual team loads in `_load_all_scouted` catch exceptions per-team (line 400) and continue, which is the right pattern for batch operations.

4. **`__init__.py` logging setup is well-placed.** Initializing `logging.basicConfig()` before any imports ensures the CLI's format wins over any module-level setup. The `# noqa: E402` comments are appropriate.

5. **CLI parameter validation is manual but consistent.** Both `crawl` and `load` commands validate `--crawler`/`--loader` against hardcoded choice lists rather than using Typer's enum pattern. This works but requires keeping `_CRAWLER_CHOICES`/`_LOADER_CHOICES` in sync with the actual crawler/loader registries.

6. **No parameter shadowing issues found (E-120-09).** All parameter names are distinct from module-level names and built-in functions across the reviewed files.

7. **Import boundaries are clean** (except for the `proxy.py` importlib issue noted above). No `src/` module imports directly from `scripts/`. CLI modules import from `src.pipeline.*` and `src.gamechanger.*` as expected.
