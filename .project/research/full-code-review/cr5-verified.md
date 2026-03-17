# CR5 (CLI, Scripts & Infra) — Verified Findings

**Verifier**: software-engineer
**Date**: 2026-03-17

---

## Critical Issues

### C-1 — PII scanner `api_key_assignment` regex doesn't match unquoted YAML values — test failure confirms
**Verdict**: CONFIRMED
**Evidence**: `src/safety/pii_patterns.py:67` — regex requires value to be wrapped in quotes (`["\']`). The test `tests/test_pii_scanner.py:228-236` (`test_secret_key_colon`) expects 1 violation for `secret_key: xKfake_secret_value_here_long_enough` but gets 0. **Test is actively failing** — confirmed by running `pytest tests/test_pii_scanner.py -v` which shows `assert 0 == 1` at line 235.
**Notes**: Not covered by E-122. This is a real safety gap — unquoted YAML API key assignments bypass the PII scanner. The test was written correctly but the regex never matched.

### C-2 — `proxy/addons/credential_extractor.py` imports private `_decode_jwt_type` from `src/`
**Verdict**: CONFIRMED
**Evidence**: `proxy/addons/credential_extractor.py:26` — `from src.gamechanger.credential_parser import _decode_jwt_type, merge_env_file`. `_decode_jwt_type` is a private function (leading underscore). This is a cross-module-boundary import of a private function that runs in the mitmproxy container context.
**Notes**: Not covered by E-122. The reviewer correctly identified the fragility — renaming this private function would silently break the proxy addon (not caught by test suite). However, the proxy addons are a secondary system and `_decode_jwt_type` is a small, stable utility function.

---

## High Priority

### H-1 — `src/cli/proxy.py` uses `importlib.util` to load from `scripts/`
**Verdict**: CONFIRMED
**Evidence**: `src/cli/proxy.py:48-54` — `_load_refresh_headers_module()` uses `importlib.util.spec_from_file_location("proxy_refresh_headers", script_path)` to load `scripts/proxy-refresh-headers.py`. This creates a runtime import dependency from `src/` to `scripts/`, violating the import boundary.
**Notes**: **Covered by E-122-03** — "proxy.py import boundary fix" explicitly addresses this.

### H-2 — `src/cli/status.py:196` — brittle string manipulation on credential check message
**Verdict**: CONFIRMED
**Evidence**: `src/cli/status.py:196` — `display = msg.replace("valid -- logged in as ", "valid (logged in as ") + ")"`. This string replacement is coupled to the exact format of `check_single_profile()`'s return string. If the upstream format changes, the replacement silently produces malformed output.
**Notes**: Not covered by E-122. Brittle coupling but not a bug under current code. Would break if `check_single_profile` message format changes.

### H-3 — `src/cli/status.py:29-35` — `_human_size()` loses precision due to integer division
**Verdict**: CONFIRMED
**Evidence**: `src/cli/status.py:34` — `num_bytes //= 1024` uses floor division. A 2,560,000-byte file: after first `//= 1024`, `num_bytes` becomes `2500` (correct for KB), then `//= 1024` gives `2` (should be ~2.4 MB). The `:.1f` format on line 33 is meaningless since `num_bytes` is always an integer after the division.
**Notes**: Not covered by E-122. Real display bug — sizes shown as "2.0 MB" when they should be "2.4 MB". Low impact since this is just the `bb status` display.

### H-4 — `src/cli/data.py:6` — `import os` alongside `pathlib`
**Verdict**: CONFIRMED (trivial)
**Evidence**: `os.environ.get()` usage is standard and not related to the `os.path` prohibition. The reviewer acknowledged this is a minor style note, not a real violation.
**Notes**: Not covered by E-122. Not a real issue — `os.environ` is the standard way to read env vars.

### H-5 — `scripts/seed_dev.py:100-101` — `sys.exit(1)` inside function
**Verdict**: CONFIRMED
**Evidence**: `scripts/seed_dev.py:100` — `sys.exit(1)` inside `load_seed()` when db doesn't exist. Makes the function non-testable for that code path.
**Notes**: Not covered by E-122. This is a script, not `src/` code. The function is only called from the `__main__` block. Low priority.

---

## Medium Priority

### M-1 — Missing `from __future__ import annotations` in multiple files
**Verdict**: CONFIRMED
**Evidence**: Reviewer lists `src/cli/__main__.py`, `proxy/addons/loader.py`, `proxy/addons/gc_filter.py`, `src/safety/pii_patterns.py`, `tests/test_http_headers.py`. Convention violation. None use forward references, so no runtime impact.
**Notes**: Not covered by E-122. Trivial convention fix.

### M-2 — `src/safety/pii_scanner.py:39-41` — `os.path` usage in `src/` module
**Verdict**: CONFIRMED (justified)
**Evidence**: `src/safety/pii_scanner.py:39` — `os.path.dirname(os.path.abspath(__file__))` inside `except ImportError` block. This fallback fires when the module runs as a standalone script from a pre-commit hook. The fallback is documented.
**Notes**: Not covered by E-122. Justified exception — the pre-commit hook context doesn't have the editable install.

### M-3 — `src/safety/pii_scanner.py:39` — `sys.path` manipulation in `src/` module
**Verdict**: CONFIRMED (justified)
**Evidence**: Same code as M-2. `sys.path.insert(0, ...)` inside `except ImportError` fallback. Technically violates the "No sys.path manipulation in src/ modules" rule, but the module documents why.
**Notes**: Not covered by E-122. Same justification as M-2.

### M-4 — `proxy/addons/header_capture.py:28-29` — `sys.path` manipulation in proxy module
**Verdict**: CONFIRMED (acceptable)
**Evidence**: Not in `src/`, so not a rule violation. Proxy addons run in a container context.
**Notes**: Not covered by E-122. Not a real issue.

### M-5 — DRY violation between `scripts/refresh_credentials.py` and `src/cli/creds.py`
**Verdict**: CONFIRMED
**Evidence**: Reviewer states both implement the same credential import flow. The CLI version (`bb creds import`) is the primary interface. The script is legacy.
**Notes**: Not covered by E-122. The script is a legacy path. Deprecation would be nice but not urgent.

### M-6 — `src/cli/creds.py:391` — accessing private `Text._spans` attribute
**Verdict**: CONFIRMED
**Evidence**: `src/cli/creds.py:391` — `Text(t.plain.rstrip("\n"), spans=t._spans)` accesses Rich library's private `_spans`. Could break on Rich upgrades.
**Notes**: Not covered by E-122. Fragile but functional. Low priority.

### M-7 — `scripts/validate_api_docs.py` uses cwd-relative paths
**Verdict**: CONFIRMED
**Evidence**: `scripts/validate_api_docs.py:24-25` — `Path("docs/api/endpoints")` and `Path("docs/api/README.md")` are cwd-relative. Script fails if not run from project root.
**Notes**: Not covered by E-122. Common in scripts. Low priority.

### M-8 — `proxy/addons/header_capture.py:246` — module-level addon instantiation
**Verdict**: CONFIRMED (acceptable)
**Evidence**: Reviewer describes the dual-instantiation concern. In practice, mitmproxy loads `loader.py` which creates all addons. `header_capture.py`'s standalone list is for direct loading only.
**Notes**: Not covered by E-122. Not a real issue in practice.

### M-9 — No error-path test for `bb creds refresh`
**Verdict**: CONFIRMED
**Evidence**: Reviewer states no tests exist for the refresh command. This is a test gap for a critical operator workflow.
**Notes**: Not covered by E-122. Test gap, medium priority.

### M-10 — No error-path test for `bb data resolve-opponents`
**Verdict**: CONFIRMED
**Evidence**: Reviewer states only happy-path test exists. The `except Exception` error handler is untested.
**Notes**: Not covered by E-122. Test gap, low priority.

### M-11 — `scripts/smoke_test.py` makes real HTTP requests
**Verdict**: CONFIRMED (by design)
**Evidence**: The smoke test is designed to make real API calls — that's its purpose. No `--dry-run` flag exists but one isn't needed for a smoke test.
**Notes**: Not covered by E-122. Not a real issue — this is expected behavior for a smoke test.

---

## Low Priority

### L-1 — `src/cli/data.py:423` — `type: ignore[attr-defined]` for duck-typed config
**Verdict**: CONFIRMED (trivial)
**Evidence**: Type hint uses `object` and ignores mypy warnings. Same class of issue as CR3's H-3.

### L-2 — `scripts/seed_dev.py:105-116` — SQLite connection not using context manager
**Verdict**: CONFIRMED (trivial)
**Evidence**: Manual `try/finally/close()` instead of `with`. The `with` form is preferred by convention but the current code is correct.

### L-3 — `scripts/check_codex_rtk.py:78` — cosmetic f-string
**Verdict**: CONFIRMED (non-issue). Cosmetic only.

### L-4 — `src/cli/proxy.py:63-68` — subprocess.run without FileNotFoundError handling
**Verdict**: CONFIRMED (acceptable)
**Evidence**: Script references are correct in normal operation. FileNotFoundError would only surface in a misconfigured environment.

### L-5 — Inconsistent error output patterns across CLI commands
**Verdict**: CONFIRMED
**Evidence**: Different CLI modules use different error formatting (typer.echo, Rich console, etc.). Style inconsistency, not a bug.

### L-6 — `src/cli/data.py:7` — eager `import sqlite3`
**Verdict**: CONFIRMED (non-issue). `sqlite3` is stdlib, imports quickly.

---

## E-122 Overlap Summary

| Finding | Covered by E-122? |
|---------|-------------------|
| H-1 (proxy.py importlib boundary) | Yes — **E-122-03** |
| All others | No |

## Actionable Findings Not in E-122

**Bugs (should fix)**:
- C-1: PII scanner regex gap — unquoted YAML values bypass detection; test actively failing
- H-3: `_human_size()` integer division produces wrong display values

**Security/safety gaps**:
- C-2: Private function import across module boundaries (proxy addon)

**Code quality (significant)**:
- H-2: Brittle string manipulation in status display
- M-9: No tests for `bb creds refresh` error paths
