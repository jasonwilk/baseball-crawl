---
name: reclamation-guard-gotchas
description: Why executing a predicate clause cannot prove it is a no-op, the 250000 variable limit that makes chunking tests vacuous, and the two commits in cleanup_expired_reports that launder a dirty borrowed connection
metadata:
  type: project
---

Four gotchas found by execution while verifying the E-273 reclamation sweep
(`src/reports/lifecycle.py`) during E-277 planning. Each one had already survived a
review pass in the form of prose asserting the opposite.

## Executing a predicate clause CANNOT establish that it is a no-op

`_TEAM_BASE_PRED` excludes teams referenced by any "keep root" via `NOT EXISTS`.
The obvious way to check whether a root is load-bearing — run the pass with the
clause present, then with it removed — **cannot distinguish a dead root from a live
one.** Seed the root's own column and every root produces the same signature:
present → team survives, removed → team deleted. That is what a clause in a
conjunctive predicate DOES. Measured this for both roots that genuinely never fire
(`opponent_links.resolved_team_id`, `user_team_access.team_id`) and got the identical
result to the load-bearing `opponent_links.our_team_id`.

**The discriminator is a PRODUCTION-WRITER AUDIT, not a run:** can any code path in
`src/` populate this column for a row inside the predicate's base set? Execution
establishes the clause's MECHANISM; only the writer enumeration establishes whether it
fires on real data. Verdicts as of E-277: `our_team_id` live (opponent_ladder writes it
on the morning-run path), `scheduled_report_runs.own_team_id` live (`_upsert_slot`),
`resolved_team_id` DEAD — **no writer anywhere in `src/`**, only lifecycle's own
cascade NULLs it — and `user_team_access.team_id` dead because
`_get_available_teams()` offers only `membership_type='member'` teams for grants.

Generalizes past this predicate: any "is this guard dead code?" question answered by
running the guard gives a confident wrong answer. Related: [[module-global-seams]].

## `SQLITE_LIMIT_VARIABLE_NUMBER` is 250000 here — chunking tests go vacuous

`_RECLAIM_CHUNK = 900` exists to stay under SQLite's variable limit, and its docstring
cites 999. **This build (SQLite 3.45.1) reports 250000**, and an unchunked
`IN (?, ...)` with 100000 bound params executes fine. So the obvious chunking test —
seed >2 chunks of orphans, assert they all delete — **passes with the chunking
removed.** A test green against the mutant it exists to catch is worse than none,
because it also reports the path as covered.

Fix: `conn.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 999)` on the test connection
before invoking the pass. Verified both halves under that limit — 1000 params raise
`too many SQL variables`, and the chunked `_delete_where_in` still deletes all 1801.
Assert the precondition inside the test too, or its validity rests silently on
`setlimit` having taken effect. The limit is build-dependent (999 pre-3.32.0, 32766
from 3.32.0, 250000 here), so never write a specific number into a docstring as a fact.

## `cleanup_expired_reports` commits a BORROWED connection twice, independently

Two separate commits launder a caller's uncommitted DML on a borrowed connection, and
either one alone is sufficient: `reap_stale_generating_reports`' unconditional
`conn.commit()` (fires even at `reaped=0`), and `cleanup_expired_reports`' OWN
unconditional `conn.commit()` after its expiry loop. Verified by neutralizing the reap
to a no-op — the caller's uncommitted `INSERT INTO teams` was still committed and then
deleted as an orphan by the reclaim, with the caller's later `rollback()` recovering
nothing. So "guard the reap" closes neither commit on that path.

Live callers are all clean today (generator opens a dedicated fresh connection for the
cleanup call; the CLI passes `conn=None`), so this is latent — but `in_transaction` is
the signal, and it is False after a bare SELECT and True after DML.

Related: `BEGIN IMMEDIATE` does NOT implicit-commit pending statements on Python 3.13 —
it raises `cannot start a transaction within a transaction`. Any claim that it silently
commits is wrong.

## A guard that raises inside a swallowing `try` is not a guard

`cleanup_expired_reports` wraps its reap call in a bare `except Exception` that logs and
continues. A precondition check placed inside that block raises, gets swallowed with a
WARNING, and execution proceeds into the very commit the check existed to prevent —
while satisfying any review question phrased as "is there a guard at entry?" Place a
precondition check ABOVE the swallowing block, and when writing the AC say "outside its
exception handler" rather than "at entry". Same family as
[[testing-gotchas]]' precondition-check-whose-alarm-is-discarded.
