# P3 — E-273 reclamation follow-ups (audit findings; small epic or single-story fix set)

Plan a SMALL epic (plan skill; PM + SE + DE; glob `epics/` AND `.project/archive/` for
the next number). All findings below are from the 2026-07-25 independent audit of
`src/reports/lifecycle.py` (commit a74dfd5), each verified by execution against a
synthetic DB unless noted. The reclamation core is sound — do not redesign it; these
are targeted repairs.

## MAJOR-1 (reachable from routine morning-run): audit rows hard-deleted

`_TEAM_PIN_TABLES` (lifecycle.py:890) contains `("scheduled_report_runs", "own_team_id")`,
so an own-team row whose only morning-run slots were placeholder deferrals — shape:
`membership_type='tracked'`, `is_active=0`, no reports/games row, and NO
`opponent_links` row, because opponent_ladder rung (b) persists no row while
`_upsert_slot` (morning_run.py:395-432) still commits the audit row — is swept by the
generate-start reclamation, deleting its `scheduled_report_runs` history. Executed
end-to-end: ReclaimResult(teams_deleted=1), audit rows 1 → 0. This contradicts
`migrations/005_scheduled_report_runs.sql:123` ("audit row OUTLIVES report cleanup").
Exposure concentrates on first runs, post-purge-scouting runs, and tournament days
(any non-placeholder slot creates a permanent opponent_links pin thereafter).

Decision for PM+DE: either add `scheduled_report_runs.own_team_id` as a fourth
keep-root (audit rows pin their team), or accept-and-document the deletion in the
migration comment and docs/admin. The status quo — migration says one thing, pass does
the other — is the only wrong option.

## MAJOR-2: false rationale guarding a live guard

lifecycle.py:820-826 comment: "All three [keep-roots] are provable no-ops on real
data... fire only in a bent-invariant case" — FALSE, executed both directions: the
`opponent_links.our_team_id` root is the ONLY thing keeping morning-run own-team rows
alive (src/db/teams.py:236 hardcodes membership_type='tracked', so own teams ARE in the
base set). Rewrite the comment to state the real function; a reader trusting it could
delete the load-bearing root as dead code.

## MAJOR-3 (latent, two modules): borrowed-connection commit trap

`reap_stale_generating_reports` (lifecycle.py:185) commits UNCONDITIONALLY on a
borrowed connection (even 0 rows reaped); `reclaim_orphan_reference_data` invokes it
at :1136-1137 and `BEGIN IMMEDIATE` at :1140 also implicit-commits pending statements.
Executed: a caller's uncommitted INSERT INTO teams became visible and was then DELETED
as an orphan by the same reclaim call. No live caller passes a dirty connection today.
Fix cheaply: document the clean-connection precondition in both docstrings AND add a
fail-fast `assert not conn.in_transaction` (or refuse-with-error) at entry to the two
public passes.

## MINORs (fix if cheap, else explicitly decline in the epic)

- Rollback handler at lifecycle.py:1191-1193 raises "cannot rollback - no transaction
  is active" when SQLite already auto-rolled back (SQLITE_FULL/IOERR/BUSY), masking the
  real cause in the swallowed log.
- One refused empty schedule emits one WARN PER PRIOR GAME (30 WARNs observed) —
  retire_absent_games' "exactly one WARN" docstring is per-absence, not per-cause;
  collapse to one WARN per cause with a count.
- No test exercises the >900-id chunking path (`_RECLAIM_CHUNK`, `_delete_where_in`)
  though the constant's own docstring cites a 681/14,326 backlog; audit executed 1,500
  rows correctly — pin it with a test.
- Fixture drift (test-only, document or restore): a74dfd5 flipped three
  tests/test_report_generator.py fixture teams tracked→member to survive the new sweep;
  the public_id-collision test no longer covers the production (tracked) shape, and the
  IDEA-127 identity-downgrade tests exercise owns-conn branches production never uses.

Guardrails: synthetic DBs from migrations/ only; never touch data/app.db.

## Report back: the MAJOR-1 decision made (pin vs document), diff summary, new test
names, and the executed re-run of the MAJOR-1 scenario showing the chosen behavior.
