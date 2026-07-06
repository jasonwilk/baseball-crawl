# E-252-06: Extend get_connection() with busy_timeout; route the scheduled-reports writers through it + contention test

## Epic
[E-252: Scheduled-Reports Reliability (Cron-Grade Morning-Run)](../E-252-scheduled-reports-reliability/epic.md)

## Status
`DONE`

## Description
After this story is complete, every SQLite writer **in the scheduled-reports path** — the admin UI (uvicorn workers), the interactive report CLI (`bb report`, incl. `map-opponent` per E-252-03 AC-7), and the morning-run cron — opens its connection through the single `get_connection()` factory, which sets a `busy_timeout` so a lock overlap WAITS instead of immediately raising `database is locked`. The morning-run CLI no longer hand-rolls its own bare connection. This is the foundation half of the third-writer contention fix (paired with E-252-07).

**Scope note (P5, corrected during Phase 4b):** the earlier "every SQLite writer" / "route all writers" wording OVER-CLAIMED. This story covers only the scheduled-reports triad above. The `bb data` maintenance writers (`cli/data.py` ×5) and the loader/crawler modules also write the same WAL file but are OUT of scope here — broader `busy_timeout` coverage for them is a captured follow-up idea (closure-idea C), not a gap in this story's delivery.

## Context
The morning-run CLI is a THIRD SQLite writer on one WAL file alongside the admin UI (uvicorn workers) and the interactive CLI. Per data-engineer's source-verified analysis (Technical Notes TN-5):
- The CLI opens `sqlite3.connect(str(db_path))` + `PRAGMA foreign_keys=ON` ONLY (`src/cli/report.py:438-439`) — it does NOT use `get_connection()`, sets NO `busy_timeout`, and uses default (legacy) isolation.
- `get_connection()` (`src/api/db.py:39`) sets WAL + FK but ALSO no `busy_timeout`. So ALL THREE writers have zero `busy_timeout` → any lock overlap is an immediate `SQLITE_BUSY`, not a wait.

The fix is a single-factory change: extend `get_connection()` (do NOT add a second factory — a parallel factory re-introduces the exact divergence this epic fixes) with `busy_timeout=30000` (30s) and `synchronous=NORMAL` (the correct/safe WAL pairing — loses only the last commit on OS/power crash, and cuts fsync stalls that lengthen the write-lock hold), plus an optional `db_path` parameter so the CLI/cron pass their `resolve_db_path(override)` and stop hand-rolling. The app path adopting the same `busy_timeout` is IN scope — it is the same one-line change and a cron-grade three-writer epic REQUIRES the admin-UI connection to WAIT on the cron writer rather than 500.

**GAP A (SE):** routing the morning-run CLI call site (`src/cli/report.py:438`) through the factory is owned by THIS story — otherwise the epic ships a `busy_timeout`-capable factory the morning run never uses and the fix never reaches production.

This story is the foundation; the transaction-discipline half (commit-after-`ensure_team_row`, no-slot-rollback, per-slot isolation) is E-252-07. Per Technical Notes TN-5, `busy_timeout` WITHOUT E-252-07's commit-before-network is false safety — 06 must land before 07 and 07 must not slip.

## Acceptance Criteria
- [ ] **AC-1**: `get_connection()` in `src/api/db.py` is extended to set, on every connection it returns: WAL (existing), `foreign_keys=ON` (existing), `busy_timeout=30000`, and `synchronous=NORMAL`. It accepts an optional `db_path: Path | None = None` that defaults to the factory's existing resolution — `get_db_path()` (the thin wrapper `get_connection()` already uses, which delegates to `resolve_db_path()`) — so callers can pass an explicit override.
- [ ] **AC-2**: The morning-run CLI (`src/cli/report.py`) opens its connection through `get_connection(...)` (passing its `resolve_db_path(override)` result) instead of the hand-rolled `sqlite3.connect(...)` + inline `PRAGMA foreign_keys=ON` — GAP A. The morning-run connection therefore carries `busy_timeout` and the shared pragmas.
- [ ] **AC-3**: No second connection factory is introduced; `get_connection()` remains the single factory, and the change does NOT switch to `isolation_level=None` (full autocommit) — default deferred isolation is preserved, per Technical Notes TN-5.
- [ ] **AC-4** (the one required contention test, per Technical Notes TN-5): using a real on-disk file in `tmp_path` (NOT `:memory:`), WAL set once up front, two connections to the same file: connection A acquires a write lock via `BEGIN IMMEDIATE`; a worker thread holds it a fixed `HOLD_MS` (≈300ms) then commits/releases; connection B (with `busy_timeout=TIMEOUT_MS`, ≈2000ms) issues an INSERT and records wall-clock — assert B SUCCEEDS and its elapsed time is ≥ the hold (it WAITED, not raised). Determinism mechanics (per data-engineer, both required to avoid flakes): (a) a `threading.Event` that the worker SETS after A's `BEGIN IMMEDIATE` has returned (the lock is actually held), which the main thread WAITS on before issuing B's insert — so B cannot race ahead of A's lock acquisition and record `elapsed≈0`; (b) observe the `check_same_thread` rule — create each connection IN the thread that uses it, or open with `check_same_thread=False` — else a spurious `ProgrammingError`. Use named constants `HOLD_MS`/`TIMEOUT_MS`; use 2000ms (not 30000) in the test so the suite stays fast.
- [ ] **AC-5** (companion, same fixture): with `busy_timeout=0` while A holds the lock, connection B's INSERT raises `sqlite3.OperationalError` with "database is locked" in the message, and fails FAST (elapsed well under the hold) — pinning that the pragma is load-bearing in both directions.
- [ ] **AC-6**: The admin-UI/app path continues to work through the same extended `get_connection()` (adopting `busy_timeout` is intended, per Technical Notes TN-5) — no regression in the existing app connection behavior or the existing `get_connection()` callers.
- [ ] **AC-7** (factory-contract pragma readback, per data-engineer): a test opens a connection via `get_connection()` (the factory OUTPUT, not a hand-set raw connection) and reads back all four pragmas — `PRAGMA busy_timeout` == 30000, `PRAGMA foreign_keys` == 1, `PRAGMA journal_mode` == `'wal'`, `PRAGMA synchronous` == 1 (NORMAL). This pins the factory contract so a regression that drops or lowers `busy_timeout` fails here (AC-4/AC-5 use hand-set pragmas on raw connections and would stay green through such a regression).

## Technical Approach
Extend `get_connection()` in `src/api/db.py`: add `PRAGMA busy_timeout=30000;` and `PRAGMA synchronous=NORMAL;` after the existing WAL/FK pragmas, and an optional `db_path: Path | None = None` parameter defaulting to the factory's existing resolution (`get_db_path()`, the thin wrapper that delegates to `resolve_db_path()`). Before swapping the default, confirm `get_db_path()` ≡ `resolve_db_path()` (it is a thin wrapper) so the factory's default path is unchanged for existing callers. Swap the morning-run CLI's hand-rolled connect at `src/cli/report.py:438` to `get_connection(db_path=...)` passing the already-resolved override (GAP A). Do not add a parallel factory; do not change isolation level. Write the DE-specified contention test (AC-4/AC-5) with the `BEGIN IMMEDIATE` + threaded-hold + `busy_timeout` shape, named `HOLD_MS`/`TIMEOUT_MS` constants, the lock-acquired `threading.Event` gate, and the `check_same_thread` discipline; add the AC-7 factory-output pragma-readback test. Confirm the path helpers against `src/db/paths.py` and the existing `get_connection()` callers.

Coordinate with E-252-03 (which also restructures the `cli/report.py:438` block into a try/finally) — this story lands first; E-252-03 builds on the factory-routed connection.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-252-03 (both touch `src/cli/report.py:438`), E-252-07 (the transaction-discipline half; busy_timeout without commit-before-network is false safety — Technical Notes TN-5)

## Files to Create or Modify
- `src/api/db.py` (`get_connection()` — busy_timeout, synchronous=NORMAL, optional db_path)
- `src/cli/report.py` (morning-run connection opened via `get_connection(...)` — GAP A)
- `tests/test_db.py` (or a new/existing DB test module) — the contention test (AC-4) + companion (AC-5)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-252-07**: The `busy_timeout`-capable factory and the factory-routed morning-run connection. E-252-07 adds the transaction discipline (commit-before-network) that makes the `busy_timeout` actually protective.
- **Produces for E-252-03**: The factory-routed `cli/report.py:438` connection block that E-252-03 wraps in try/finally.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Audit one-liner (MEDIUM, merges A3+A5+A7): "`_upsert_slot` outside per-slot isolation; no `busy_timeout` on any connection; ad-hoc connection setup — one slot-recording DB error aborts all remaining teams; zero contention tests exist" — `morning_run.py:540`, `src/api/db.py:52`. This story owns the connection-factory + busy_timeout + contention-test portion; the `_upsert_slot`-inside-isolation portion is E-252-07.
