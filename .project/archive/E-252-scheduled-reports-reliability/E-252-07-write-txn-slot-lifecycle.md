# E-252-07: Fix morning-run write-transaction & slot-lifecycle model

## Epic
[E-252: Scheduled-Reports Reliability (Cron-Grade Morning-Run)](../E-252-scheduled-reports-reliability/epic.md)

## Status
`DONE`

## Description
After this story is complete, the morning run no longer holds a SQLite write lock across the multi-team network crawl, no longer loses its own-team INSERTs on a no-games team, records each slot's audit row inside per-slot error isolation (one slot's DB error can't abort the rest), and reserves each slot before generation so an overlap/SIGKILL can't double-generate. This is the transaction-discipline half of the third-writer contention fix (paired with E-252-06).

## Context
Per data-engineer's source-verified analysis (Technical Notes TN-5), four coupled slot-lifecycle/transaction defects in `src/reports/morning_run.py`:
1. **Write-txn held across network I/O** (`morning_run.py:477`): `ensure_team_row` opens an implicit write transaction (it does NOT commit) that stays open across `fetch_schedule`/`fetch_opponents` (network I/O). Under WAL this holds the single write lock for the whole multi-team crawl — so E-252-06's `busy_timeout` alone can't save a competing writer (a >30s-held lock times out the contender anyway). **This story is the OTHER HALF of the contention fix; without it, 06's busy_timeout is false safety.** Fix: `conn.commit()` immediately after `ensure_team_row`, before any network fetch.
2. **No-slot rollback** (the second half of the :477 finding): only the first slot's `_upsert_slot` commits (L318). A no-games team produces zero slots → nothing commits → the default-isolation `conn.close()` ROLLS BACK the own-team INSERT → it is re-INSERTed every morning. The commit-after-`ensure_team_row` fix (item 1) also makes the own-team row durable for no-games teams.
3. **`_upsert_slot` call outside per-slot isolation** (`morning_run.py:539-540`): the audit-write call sits OUTSIDE the per-game try/except, so one slot-recording DB error aborts all remaining teams. Fix: wrap the `_upsert_slot` call in its own try/except that logs and continues (with the TN-10 rollback).
4. **Slot reservation race** (`morning_run.py:387`, LOW): slot idempotency is read-then-act, recorded only AFTER generation, so an overlap/SIGKILL double-generates. Fix: reserve the slot before generation.

Two invariants bind this story:
- **TN-5:** never hold an open write transaction across an HTTP fetch on the shared cross-process SQLite file. Keep default deferred isolation (do NOT switch to autocommit) + this discipline.
- **TN-10 (E-245 partial-commit footgun):** the per-slot audit-write isolation runs on the shared `conn`, so its except branch must `conn.rollback()` before continuing.

The reserve-before-generate change (item 4) interacts with E-252-01's idempotency/skip predicate (`_prior_success` and the skip branch's carry-prior-slug/id fix): the reservation write MUST reconcile with E-252-01's "carry prior slug/id on skip" so a reservation does not itself null the report linkage or defeat the skip. This story must build on E-252-01, not revert it.

## Acceptance Criteria
- [ ] **AC-1**: Given a team being processed, when `run_morning` inserts the own-team row via `ensure_team_row`, then it `conn.commit()`s immediately — before `fetch_schedule`/`fetch_opponents` — so no open write transaction is held across the network fetch. Test mechanism (per data-engineer): the mocked `fetch_schedule` opens a FRESH connection INSIDE the mock and asserts the own-team `teams` row is already visible at that point — proving the commit landed before the network fetch (the write lock is released before the fetch).
- [ ] **AC-2** (no-slot durability, per Technical Notes TN-5): Given a team whose schedule yields ZERO target-date slots, when `run_morning` finishes and the connection is closed, then the own-team `teams` row remains visible from a FRESH connection (it is NOT rolled back). A functional test drives `run_morning` with a zero-slot schedule and asserts the row persists.
- [ ] **AC-3**: Given the per-slot audit write (`_upsert_slot`) raising a DB error for one slot, when the run continues, then that error is caught, logged, and the remaining slots/teams are still processed (the audit write is inside per-slot isolation) — one slot-recording error no longer aborts the run.
- [ ] **AC-4** (Technical Notes TN-10): EVERY shared-connection catch-and-continue branch in the run loop calls `conn.rollback()` before the next iteration — the per-slot `_upsert_slot` isolation this story adds AND the PRE-EXISTING per-game `except` at `morning_run.py:513`. For the :513 branch this is defense-in-depth (per TN-10: the only shared-conn writer reachable there, `opponent_ladder.resolve_opponent`, self-commits its `opponent_links` writes, so there is no uncommitted DML to leak today). Because no leak exists today, a "partial-not-persisted" fixture has no teeth; instead the test asserts `conn.in_transaction is False` after the :513 path runs (or spies that `conn.rollback()` was invoked) — a real-teeth assertion that stays meaningful regardless of the ladder's commit behavior. The :513 rollback carries a one-line code comment (see Technical Approach) so it is not later removed as dead code.
- [ ] **AC-5** (slot reservation race): Given a slot for an auto-resolved opponent, when generation is about to run, then the slot is reserved (its audit row is written/marked) BEFORE generation, so a second overlapping run (or a crash mid-generation) does not double-generate the same slot. The reservation reconciles with E-252-01's skip predicate: a prior non-expired success is still skipped, and the reservation does not null an existing `report_id`/`report_slug`.
- [ ] **AC-6**: The audit-row invariants in Technical Notes TN-3 are preserved throughout (non-NULL 3-column key with the `unknown-{event_id}` fallback; FK `ON DELETE SET NULL`; the crash-slot `error_message` discriminator). The F-H2 fix from E-252-01 is preserved (no regression of the skip-path linkage carry).
- [ ] **AC-7**: Tests (per Technical Notes TN-8) cover: lock-release-before-crawl (AC-1); no-slot durability (AC-2); per-slot audit-write error isolated (AC-3); the :513-branch `conn.in_transaction is False` / rollback assertion (AC-4); reserve-before-generate prevents double-generation and reconciles with the skip predicate (AC-5). This story's lock-release test (AC-1) is SEPARATE from E-252-06's contention-primitive test — do not let 06's test stand in for 07's lock-release assertion.

## Technical Approach
In `run_morning`: `conn.commit()` immediately after `ensure_team_row` and before the schedule/opponents fetch (items 1 & 2). Wrap the `_upsert_slot` call in per-slot try/except with a `conn.rollback()` in the except (item 3 & TN-10), and add a `conn.rollback()` to the PRE-EXISTING per-game `except` at `morning_run.py:513` — with a one-line code comment stating it is defense against a FUTURE ladder change that introduces write→network→commit ordering on the shared connection (so it is not later "cleaned up" as dead code; the ladder self-commits today, verified `opponent_ladder.py:179/205`). Reserve the slot before generation (item 4), reconciling the reservation write with E-252-01's skip/carry-prior-slug-id predicate so idempotency and the F-H2 fix both hold. Keep default deferred isolation. Verify the slot-lifecycle region (`_process_opponent`, `_upsert_slot`, `_prior_success`, the run loop) against the current `morning_run.py` and the `scheduled_report_runs` contract in `.claude/rules/data-model.md`.

## Dependencies
- **Blocked by**: E-252-05 (same file `src/reports/morning_run.py`; the chain is 01→02→05→07 — 01's F-H2 fix is inherited transitively and must be preserved), E-252-06 (this is the transaction-discipline half of the contention fix; the factory + busy_timeout must be in place, and this story completes the protection — Technical Notes TN-5)
- **Blocks**: None

## Files to Create or Modify
- `src/reports/morning_run.py` (`run_morning` commit-after-`ensure_team_row`; per-slot audit-write isolation + rollback; reserve-before-generate in the slot lifecycle)
- `tests/test_morning_run.py` (or the existing morning-run test module) — the AC-7 tests (incl. the separate lock-release + no-slot durability tests)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
**Sizing rationale (bundled deliberately):** the four behaviors (commit-after-`ensure_team_row`, no-slot-rollback, per-slot audit-write isolation, reserve-before-generate) are bundled because they all operate on ONE lifecycle region — the `run_morning` per-team/per-slot transaction and the `_process_opponent`/`_upsert_slot` slot write. Splitting any of them (e.g. reserve-before-generate) would create a fresh same-lines serialization dependency for marginal benefit; they are cohesive and interdependent, so they ship together.

Audit one-liners: "Morning-run holds an open write transaction across network I/O; no-slot runs roll the own-team INSERTs back on close" — `morning_run.py:477`; "`_upsert_slot` outside per-slot isolation" (part of the merged A3+A5+A7 MEDIUM) — `morning_run.py:540`; "Morning-run slot idempotency is read-then-act, recorded only after generation — overlap/SIGKILL double-generates" (LOW) — `morning_run.py:387`. DE flagged that commit-after-`ensure_team_row` is the mandatory second half of the E-252-06 contention fix — this story must not slip past E-252-06.
