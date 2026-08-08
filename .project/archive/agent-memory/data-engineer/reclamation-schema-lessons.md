---
name: reclamation-schema-lessons
description: Two durable lessons from E-277 -- cascade-target and reachability-root are INDEPENDENT axes, and any chunked-IN test is vacuous on this build unless it lowers SQLITE_LIMIT_VARIABLE_NUMBER
metadata:
  type: project
---

From E-277 planning (2026-07-26/27), both established by execution against synthetic
DBs. Neither is derivable from reading the code.

## 1. Cascade target and reachability root are INDEPENDENT axes

The recurring confusion in `src/reports/lifecycle.py`. Two different questions:

- **Cascade**: when a team dies, do its child rows die? (`_delete_team_scoped_data`,
  `_TEAM_PIN_TABLES`)
- **Reachability root**: does a child row count as a reason the team is still ALIVE?
  (`_TEAM_BASE_PRED`'s `NOT EXISTS` clauses)

A table can be BOTH -- `opponent_links` and `user_team_access` already are, and E-277
added `scheduled_report_runs` as a third. Migration 005 answers only the cascade
question; it is silent on the root question because E-273's sweep (which INFERS
unreachability, unlike the two deleters that act on a decision already made) did not
exist when it was written. **Reading a cascade requirement as an answer to the root
question is how the 2026-07-25 audit derived a contradiction that was not there.**

Corollary for retention: **keep a pin entry even after a keep-root makes it
unreachable.** It is the FK-safety net if the root is ever weakened, and it is what
keeps the sweep compliant with the CASCADE MIRROR INVARIANT in that future. Removing
a pin entry WITHOUT the keep-root already in place raises `IntegrityError: FOREIGN KEY
constraint failed` and rolls back the ENTIRE sweep. Same disposition and same reasoning
as the `_TEAM_STAT_EXISTS` belt-and-suspenders clause -- follow that house precedent,
and always comment WHY a vacuous clause is retained, or the next reader deletes it as
dead code.

## 2. A chunked-`IN` test is VACUOUS on this build unless it lowers the limit

`_RECLAIM_CHUNK = 900` exists to stay under SQLite's bound-variable limit. **That limit
is BUILD-DEPENDENT, and this build's is 250,000** (Python 3.13.13 / SQLite 3.45.1) --
999 was the default only before 3.32.0, 32766 from 3.32.0. An unchunked `IN` with
100,000 params succeeds here.

Consequence, measured as a four-cell matrix against the real pass with 1,801 orphans:

| | chunking INTACT | chunking REMOVED |
|---|---|---|
| default limit | PASS | **PASS** |
| `setlimit(..., 999)` | PASS | RAISES `too many SQL variables` |

So the obvious test **passes against the mutant it exists to catch**, while also
reporting the path as covered. Any test of a chunked-`IN` path MUST call
`conn.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 999)` first, and should assert its
own precondition (that an unchunked `IN` over the same ids raises under the lowered
limit) -- otherwise its validity rests silently on `setlimit` having taken effect, and
deleting that one line restores the vacuity invisibly.

**Never "fix" the docstring by writing this build's number.** It rots on the next image
rebuild and implies the chunking is unnecessary -- a reader who checks `getlimit()`,
sees 250,000 against a docstring citing 999, could delete the guard. Describe the limit
as build-dependent and say why 900 is safe across builds.

## 3. Index note (E-277 Option A)

A `NOT EXISTS` keep-root on `scheduled_report_runs.own_team_id` needs **no new index and
no migration**: `EXPLAIN QUERY PLAN` gives `SEARCH srr USING COVERING INDEX
idx_scheduled_report_runs_slot (own_team_id=?)` -- migration 005's UNIQUE
`(own_team_id, opponent_root_team_id, game_date)` serves it on its leading column, and
covers it. Check for a leading-column prefix before proposing an index.

Related: [[migration-immutability-basis]], [[season_aggregate_writers]].
