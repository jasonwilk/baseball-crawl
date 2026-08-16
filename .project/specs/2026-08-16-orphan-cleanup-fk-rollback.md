<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; teams by id/role only. -->

# Orphan cleanup FK failure rolls back the whole phase and leaks unreclaimable teams

**Date**: 2026-08-16 · **Status**: `STUB` — root-caused from the restore-run log; needs a small
code chunk. **Recommended to land BEFORE the counted rebuild** — it degrades every generation
until fixed (leaked rows plus silently lost cleanup).
**Source**: trainer log sweep of `ephemeral/2026-08-16-report-restore/regenerate-20260816-204714.log`
(evidence at snapshot lines 10167–10176; re-derive from the log, do not inherit).

## The defect, two layers

1. **Predicate mismatch.** `cleanup_orphan_teams` (`src/reports/lifecycle.py`, the
   `remaining_rows` query ~794–802) computes deletability ONLY from
   `games.home_team_id`/`away_team_id`. The reclamation path also checks game-CHILD tables
   (its own warning says so: "excluded from reclamation despite no games -- game-child row in
   player_game_batting"). A team with zero games but a surviving `player_game_batting`
   reference passes cleanup's filter, then `DELETE FROM teams` raises
   `sqlite3.IntegrityError: FOREIGN KEY constraint failed`.
2. **Blast radius: the rollback eats the good work too.** Neither
   `_delete_game_scoped_data_for_perspectives` nor `_delete_team_scoped_data` commits
   internally (verified: no commit in `lifecycle.py:442-500` or `:668-706`), and the exception
   fires before the `conn.commit()` at ~line 812 — so phases 1 and 2 of the cleanup roll back
   for ALL teams in the batch, not just the undeletable one. The generator then logs
   "Orphan cleanup failed for 5 team(s); report continues" and moves on.

Observed 2026-08-16: 5 team rows leaked in one failure (ids 1465/1468/1469 first appear
immediately after the traceback), then fire "excluded from reclamation" on every subsequent
generation — 10+ times each in one run. They are permanent residue: reclamation refuses them
by design, and cleanup crashes on them.

## Fix shape (spec decides)

Align the predicates (cleanup uses the same game-child test reclamation uses), AND/OR wrap the
per-team delete in a savepoint so one undeletable id cannot discard the batch's other work.
The savepoint half is the higher-value fix: it converts "one bad row poisons five teams" into
"one bad row is skipped and named".

## Verification sketch

RED test: a team with no games but one `player_game_batting` row, batched with a genuinely
deletable team — assert the deletable one IS deleted and the other is skipped-and-logged, not
crashed. Post-fix live check: the three leaked ids from this run stop firing the exclusion
warning after their next touching generation, or are explicitly adjudicated.

## Progress log

- **2026-08-16** — Stubbed from the trainer's log sweep during the 71-team restore run.
  No code touched.
