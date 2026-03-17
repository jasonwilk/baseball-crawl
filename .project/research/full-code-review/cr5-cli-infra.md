# Code Review: CLI, Scripts & Infrastructure

## Critical Issues

### C-1: PII scanner `api_key_assignment` regex does not match unquoted YAML values -- test failure confirms
- **File**: `src/safety/pii_patterns.py:67`, `tests/test_pii_scanner.py:230-236`
- **Issue**: The `api_key_assignment` regex requires the value to be wrapped in quotes (`["\']`):
  ```
  (?:api[_-]?key|secret[_-]?key|access[_-]?token)["\']?\s*[=:]\s*["\'][^\s"\']{16,}
  ```
  This means `secret_key: xKfake_value_long_enough` (YAML-style, no quotes) is not detected. The test `test_secret_key_colon` expects 1 violation but gets 0 -- **this test is currently failing**.
- **Impact**: Real YAML config files with unquoted API key assignments would pass the PII scanner undetected. This is a gap in the safety net.
- **Recommendation**: Either fix the regex to optionally match unquoted values (e.g., make the opening quote optional and adjust the value class), or update the test to match the intended detection scope and document the limitation.

### C-2: `proxy/addons/credential_extractor.py` imports from `src/` -- mitmproxy runtime boundary concern
- **File**: `proxy/addons/credential_extractor.py:26-27`
- **Issue**: The addon imports `from src.gamechanger.credential_parser import _decode_jwt_type, merge_env_file`. The proxy addons run inside the mitmproxy container (not the devcontainer), where `src/` is mounted at `/app/src/`. This works because the `proxy/` container mounts the project root, but the `_decode_jwt_type` function is prefixed with `_` (private by convention) -- importing a private function across module boundaries is fragile.
- **Impact**: If `_decode_jwt_type` is refactored or renamed (which is more likely for private functions), the proxy addon breaks silently at runtime (not caught by test suite since mitmproxy is not running during tests).
- **Recommendation**: Either make `_decode_jwt_type` public (rename to `decode_jwt_type`) or move the logic into the addon itself.

## High Priority

### H-1: `src/cli/proxy.py:48-54` -- `_load_refresh_headers_module()` uses `importlib.util` to load from `scripts/`
- **File**: `src/cli/proxy.py:48-54`
- **Issue**: The function dynamically loads `scripts/proxy-refresh-headers.py` using `importlib.util.spec_from_file_location()`. While this avoids a direct `import` from `scripts/`, it effectively creates a runtime import dependency from `src/` to `scripts/`, circumventing the documented import boundary (`src/` modules MUST NOT import from `scripts/`). The hyphenated filename prevents a normal import, but the dependency is real.
- **Impact**: If the script is moved, renamed, or its `run()` signature changes, the CLI command breaks. This is the only place in `src/` that reaches into `scripts/`.
- **Recommendation**: Extract the `run()` function from `scripts/proxy-refresh-headers.py` into a module under `src/` (e.g., `src/proxy/refresh_headers.py`) and have both the CLI command and the script wrapper import from there. This follows the same pattern used by `crawl.py` / `load.py` / `bootstrap.py` where the script is a thin wrapper and business logic lives in `src/`.

### H-2: `src/cli/status.py:196` -- PII-adjacent string manipulation on credential check message
- **File**: `src/cli/status.py:196`
- **Issue**: The line `display = msg.replace("valid -- logged in as ", "valid (logged in as ") + ")"` does string manipulation on the credential check message to convert `"valid -- logged in as Jason Smith"` to `"valid (logged in as Jason Smith)"`. This is brittle -- if the upstream message format changes (e.g., changes `--` to `-` or modifies the phrasing), the replace fails silently and produces malformed output like `"valid -- logged in as Jason Smith)"` (trailing parenthesis with no opening match).
- **Impact**: Display corruption if the upstream message format changes. Not a security issue but poor coupling.
- **Recommendation**: Have `check_single_profile()` return structured data (name, status) rather than a pre-formatted string, or use the existing `ProfileCheckResult` dataclass for the status command.

### H-3: `src/cli/status.py:29-35` -- `_human_size()` loses precision due to integer division
- **File**: `src/cli/status.py:31-35`
- **Issue**: The function uses `num_bytes //= 1024` (integer floor division), which truncates all fractional parts. A 2,560,000-byte file shows as "2.0 MB" instead of "2.4 MB". The `.1f` format specifier suggests decimal precision was intended but the integer division defeats it.
- **Impact**: Misleading size display for the operator. Not functionally harmful but reduces diagnostic value.
- **Recommendation**: Use float division (`num_bytes / 1024`) and track as a float:
  ```python
  value = float(num_bytes)
  for unit in ("B", "KB", "MB", "GB"):
      if value < 1024:
          return f"{value:.1f} {unit}"
      value /= 1024
  return f"{value:.1f} TB"
  ```

### H-4: `src/cli/data.py:6` -- `import os` used alongside `pathlib` for `_resolve_db_path()`
- **File**: `src/cli/data.py:6,432`
- **Issue**: `_resolve_db_path()` uses `os.environ.get("DATABASE_PATH")` which is fine, but the function mixes `os.environ` with `pathlib.Path` for path resolution. The python-style rules say "Prefer `pathlib.Path` over `os.path` for all file operations." While `os.environ` is not `os.path`, the `import os` at the top could be replaced with direct `os.environ` usage if needed, but this is a minor style note -- the actual path operations use `Path`.
- **Impact**: Minor style inconsistency.

### H-5: `scripts/seed_dev.py:100-101` -- `sys.exit(1)` inside a library-like function
- **File**: `scripts/seed_dev.py:100-101`
- **Issue**: The `load_seed()` function calls `sys.exit(1)` directly when the database doesn't exist. This makes the function non-reusable and non-testable for that code path -- callers cannot catch and handle this failure. The test `test_seed.py` imports `load_seed` from `src.db.reset` (not from this script), so this specific code path is untested.
- **Impact**: The function in the script cannot be safely imported by other code since it calls `sys.exit()` on an expected condition.
- **Recommendation**: Raise `FileNotFoundError` instead and let the `__main__` block handle the exit.

## Medium Priority

### M-1: Missing `from __future__ import annotations` in multiple files
- **Files**:
  - `src/cli/__main__.py` (line 1)
  - `proxy/addons/loader.py` (line 1)
  - `proxy/addons/gc_filter.py` (line 1)
  - `src/safety/pii_patterns.py` (line 1)
  - `tests/test_http_headers.py` (line 1)
- **Rule**: python-style.md: "Use `from __future__ import annotations` at the top of each module for modern type syntax"
- **Impact**: Convention violation. These files work fine without it since they don't use forward references, but it's a documented project standard.

### M-2: `src/safety/pii_scanner.py:39-41` -- `os.path` usage in `src/` module
- **File**: `src/safety/pii_scanner.py:39-41`
- **Issue**: The fallback import path uses `os.path.dirname(os.path.abspath(__file__))`. This is inside an `except ImportError` block that fires when the module is run as a standalone script (not via the editable install).
- **Rule**: python-style.md: "Prefer `pathlib.Path` over `os.path` for all file operations"
- **Impact**: Minor convention violation, but this code path is specifically for standalone script execution, making it somewhat justifiable.

### M-3: `src/safety/pii_scanner.py:39` -- `sys.path` manipulation in `src/` module
- **File**: `src/safety/pii_scanner.py:39-40`
- **Issue**: `sys.path.insert(0, os.path.dirname(...))` in an `src/` module. The python-style rules explicitly state: "No `sys.path` manipulation in `src/` modules."
- **Mitigation**: This is in a fallback `except ImportError` block for when the module is run as a standalone script from a pre-commit hook. The module docstring even explains this. However, the rule is absolute ("Never"), so this is technically a violation.
- **Recommendation**: Consider moving the standalone-script entry point to a thin wrapper in `scripts/` that does the path setup, keeping `src/safety/pii_scanner.py` clean.

### M-4: `proxy/addons/header_capture.py:28-29` -- `sys.path` manipulation in `proxy/` module
- **File**: `proxy/addons/header_capture.py:28-29`
- **Issue**: `sys.path.insert(0, str(_PROJECT_ROOT))` to enable imports from `src/`. The python-style rule targets `src/` modules specifically, and `proxy/addons/` is not under `src/`, so this is not technically a violation. However, the same concern applies -- this addon runs in the mitmproxy container where the project root is mounted at `/app/`.
- **Impact**: Acceptable for proxy addons since they run in a container context, not as installed packages.

### M-5: DRY violation between `scripts/refresh_credentials.py` and `src/cli/creds.py` `import_creds()`
- **Files**: `scripts/refresh_credentials.py:131-152`, `src/cli/creds.py:74-125`
- **Issue**: Both implement the same credential import flow: read curl command from file or flag, parse with `parse_curl()`, write with `merge_env_file()`, print summary. The CLI version adds Rich formatting and profile support, but the core logic is duplicated.
- **Impact**: Changes to the import flow need to be applied in two places. The CLI version is the primary interface (`bb creds import`), making the script version a legacy path.
- **Recommendation**: Consider deprecating `scripts/refresh_credentials.py` or making it a thin wrapper that calls the CLI logic.

### M-6: `src/cli/creds.py:391` -- Accessing private `Text._spans` attribute
- **File**: `src/cli/creds.py:391,533`
- **Issue**: `Text(t.plain.rstrip("\n"), spans=t._spans)` accesses Rich's private `_spans` attribute. This is used to strip trailing newlines from a `Text` object while preserving spans.
- **Impact**: May break on Rich library upgrades if the internal representation changes. Used in two places (`_render_profile_report` and `_print_capture_result`).
- **Recommendation**: Use `t.right_crop(len(t) - len(t.plain.rstrip("\n")))` or build the `Text` without the trailing newline in the first place.

### M-7: `scripts/validate_api_docs.py` uses cwd-relative paths
- **File**: `scripts/validate_api_docs.py:24-26`
- **Issue**: Uses `Path("docs/api/endpoints")` and `Path("docs/api/README.md")` which are cwd-relative. The script works when run from the project root but fails from any other directory.
- **Rule**: python-style.md: "Repo-root resolution convention: Use `Path(__file__).resolve().parents[N]`"
- **Impact**: Script fails if invoked from a different working directory (e.g., CI with a different cwd). The test in `test_validate_api_docs.py` uses `pytest.skip` when the paths don't exist, masking this issue.

### M-8: `proxy/addons/header_capture.py:246` -- Module-level addon instantiation
- **File**: `proxy/addons/header_capture.py:246`
- **Issue**: `addons = [HeaderCapture()]` at module level creates an addon instance at import time. This is also present in `proxy/addons/loader.py:12`. The `loader.py` addon list includes `HeaderCapture()` via its own import, meaning if both `loader.py` and `header_capture.py` are loaded by mitmproxy, two `HeaderCapture` instances exist.
- **Impact**: If both modules are loaded, each instance captures independently, potentially writing conflicting reports. In practice, mitmproxy loads `loader.py` (which creates all three addons), and `header_capture.py`'s standalone `addons` list is only used if loaded directly.

### M-9: No error-path test for `bb creds refresh` when `TokenManager.force_refresh()` raises
- **File**: `tests/test_cli_creds.py`
- **Issue**: The `bb creds refresh` command handles multiple exception types (`ConfigurationError`, `CredentialExpiredError`, `AuthSigningError`, generic `Exception`), but the test file has no tests for this command at all. The refresh command is a critical operator workflow.
- **Rule**: testing.md: "write at least one test where that function fails"
- **Impact**: Regression risk for the refresh flow. Any of the five catch blocks could silently break.

### M-10: No error-path test for `bb data resolve-opponents` when `resolver.resolve()` raises
- **File**: `tests/test_cli_data.py:276-303`
- **Issue**: There's a happy-path test for `resolve-opponents` but no test where the resolver raises an exception. The command has an explicit `except Exception` handler (line 477-480 of `data.py`) that should exit 1 -- this path is untested.
- **Rule**: testing.md: "For any new CLI command or pipeline orchestration function that delegates to fallible operations, verify at least one test exercises a failure path"

### M-11: `scripts/smoke_test.py` makes real HTTP requests when run
- **File**: `scripts/smoke_test.py:60-74`
- **Issue**: The `_call()` function makes real API calls without any rate limiting beyond what the session provides. When called from `run_smoke_test()`, it hits three endpoints in sequence. The `time.sleep()` rate limiting is handled by the session hook, which is correct, but the script has no `--dry-run` flag to test the CLI flow without network calls.
- **Impact**: Running the smoke test against the live API in rapid succession during development could trigger rate limiting. No test coverage exists for this script beyond the `--help` entry point test.

## Low Priority

### L-1: `src/cli/data.py:423` -- `type: ignore[attr-defined]` comments for duck-typed config
- **File**: `src/cli/data.py:423-426`
- **Issue**: `_echo_dry_run_config()` accepts `object` as the type for `config` and uses `# type: ignore[attr-defined]` to access `.season` and `.member_teams`. This function should accept the actual config type (likely `TeamConfig` or similar).
- **Impact**: No runtime issue; type checker cannot verify correctness.

### L-2: `scripts/seed_dev.py:105-116` -- SQLite connection not using context manager
- **File**: `scripts/seed_dev.py:105-116`
- **Issue**: Uses manual `try/finally/close()` pattern instead of `with sqlite3.connect(...) as conn:` context manager.
- **Rule**: python-style.md: "Use context managers (`with`) for file and network resources"
- **Impact**: Minor style issue. The `finally: conn.close()` is correct but verbose.

### L-3: `scripts/check_codex_rtk.py:78` -- f-string for command label is redundant
- **File**: `scripts/check_codex_rtk.py:78`
- **Issue**: `cmd = f"rtk {' '.join(args)}"` constructs a label string for error messages but is never used as a command -- the actual command uses `[str(rtk_bin)] + args`. The label is purely for error messages, which is fine, but it could be simplified.
- **Impact**: None -- cosmetic.

### L-4: `src/cli/proxy.py:63-68` -- `subprocess.run` without `check=True` or explicit error handling
- **File**: `src/cli/proxy.py:63-68,79-87,116-118`
- **Issue**: The `report()`, `endpoints()`, and `review()` commands call `subprocess.run(..., check=False)` and pass the returncode through to `SystemExit`. This is intentional -- the shell scripts handle their own errors and the CLI just forwards the exit code. However, if the script does not exist, `subprocess.run` raises `FileNotFoundError`, which would surface as an unhandled exception with a traceback rather than a clean error message.
- **Impact**: Poor UX if a proxy script is missing. This would only happen in a misconfigured environment.

### L-5: Inconsistent error output patterns across CLI commands
- **Files**: Various CLI modules
- **Issue**: Some commands use `typer.echo(f"Error: ...", err=True)` (e.g., `data.py:245`), some use `_err_console.print("[red]Error:[/red] ...")` (e.g., `creds.py:100`), and some use `err_console.print(f"[red]...``[/red]")` (e.g., `db.py:46`). The `_err_console` is module-private in `creds.py` but `err_console` is public in `db.py`.
- **Impact**: Inconsistent look-and-feel across commands. Not a functional issue.

### L-6: `src/cli/data.py:7` -- `import sqlite3` at top level for lazy-loaded commands
- **File**: `src/cli/data.py:7`
- **Issue**: `sqlite3` is imported at the top level but only used in the `scout`, `_scout_live`, and `resolve-opponents` commands. Other `data` commands (sync, crawl, load) don't use it. The `scout` command already uses lazy imports for heavy modules (`GameChangerClient`, `ScoutingCrawler`, etc.) but `sqlite3` is imported eagerly.
- **Impact**: Minor -- `sqlite3` is a stdlib module and imports quickly. The lazy-import pattern for heavier modules is well-applied.

## Positive Observations

### P-1: Clean separation of concerns in CLI architecture
The CLI layer (`src/cli/`) is consistently structured as a thin argument-mapping layer that delegates to business logic in `src/pipeline/`, `src/db/`, and `src/gamechanger/`. Each sub-command group has its own module with a `Typer` app, callback for bare invocation, and epilog. The pattern is uniform and easy to extend.

### P-2: Thorough credential security discipline
Credential handling is consistently safe across the entire codebase:
- No credential values appear in any CLI output (only key names and timing metadata)
- Proxy URLs are never logged (multiple tests verify this at every layer)
- `gc-token`, `gc-device-id` are excluded from header captures
- The PII scanner blocks commits containing credentials (with synthetic-test-data bypass for tests)
- `trust_env=False` prevents system proxy variables from leaking credentials

### P-3: Excellent test coverage for proxy addons
The `tests/test_proxy/` test suite is impressively thorough. Credential extractor tests cover domain filtering, source-based routing, deduplication, cache behavior on write failure, response body parsing, and log safety. Header capture tests cover diff logic, first-seen-wins aggregation, conflict logging, and session directory routing.

### P-4: Subprocess smoke tests catch real packaging issues
The `test_script_entry_points.py` and `test_cli.py` subprocess tests are a valuable safety net that catches import errors and packaging issues invisible to `CliRunner` tests (which inherit pytest's `sys.path`).

### P-5: Robust error handling in scouting pipeline
The `_scout_live()` / `_run_scout_pipeline()` / `_load_scouted_team()` / `_load_all_scouted()` chain in `data.py` demonstrates strong error handling:
- Each team load is wrapped in try/except
- Load failures update `scouting_runs.status` to `"failed"` before continuing
- Status is only set to `"completed"` AFTER the load succeeds (correct status lifecycle)
- Crawl errors and load errors both contribute to a non-zero exit code
- Tests verify both success and failure paths with real SQLite databases

### P-6: Well-designed dual header profile system
The HTTP session factory (`src/http/session.py`) cleanly supports web and mobile profiles with profile-aware proxy routing, rate limiting with jitter, and SSL verification management. The header profile files are auto-generatable from proxy captures via the refresh-headers pipeline, maintaining a verified browser fingerprint.

### P-7: Comprehensive `bb creds check` diagnostic output
The credential check command provides a multi-section diagnostic with credential presence, token health, client key validation, API health, and proxy status -- all with consistent indicator formatting (`[OK]`, `[!!]`, `[XX]`, `[--]`). No credential values are ever displayed.
