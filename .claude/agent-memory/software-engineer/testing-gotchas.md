---
name: testing-gotchas
description: Non-obvious pytest/SQLite test gotchas in this repo — db-fixture backing differs per test file (db.backup deadlock), and never trust a piped pytest exit code
metadata:
  type: feedback
---

# Testing gotchas (project-specific)

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
