# P1 — Fix the reconcile-at-load health gate (CRITICAL: live data loss on routine generate)

Plan an epic for this fix (plan skill; PM + SE + DE; glob `epics/` AND `.project/archive/`
for the next epic number — do not trust any remembered number), then dispatch with review
after I authorize. Keep scope TIGHT: this epic is the gate fix + its tests + the prose it
falsifies. Nothing else rides along.

## The defect (verified by execution, 2026-07-25 independent audit)

`src/db/reconcile_at_load.py` — the retire-absent health gate reads its "prior" set
AFTER the same run's fresh rows are upserted (producer ordering:
`src/gamechanger/loaders/game_loader.py:679` — `_load_team_stats` writes fresh rows at
:661-671, the reconcile reads "prior" at :679). So `prior ∩ fresh` counts rows the run
just wrote, and the gate the code executes is `|fresh| >= |stale|`, NOT the documented
`|matching| >= |stale|`.

Executed consequences (no mocks, real `ScoutingLoader.load_team` against a migrated
temp DB):
1. **Player-line grain, UNCAPPED**: a payload carrying 9 brand-new player ids (zero
   overlap with the 9 stored rows — GC id churn, the exact input `dedup-players` exists
   to merge) hard-deletes all 9 prior batting lines. The docstring at :962-968 says this
   input "should REFUSE rather than delete." WARN observed:
   "hard-deleted 9 stale batting line(s) ... (9 comparable fresh vs 18 prior)" —
   prior=18 is the tell (9 old + the 9 just inserted).
2. **Game grain**: stale=2, surviving_old=1 → 0 retired; add 5 newly-completed games in
   the same run → 2 retired. The comment at :596-603 explicitly claims newly-completed
   games are not in prior; a spy on `_prior_loaded_game_ids` during a real two-run load
   shows them present. Blast radius capped at 2 only by `MAX_GAME_RETIREMENTS`
   (added in E-270 for unrelated reasons).
3. Boundary sweep (zero matching ids in all cases): stale=9/fresh=8 → refused;
   stale=9/fresh=9 → 9 deleted; stale=9/fresh=10 → 9 deleted.

Why 72 existing tests miss it: `test_truncated_array_padded_with_upcoming_games_retires_nothing`
(`tests/test_game_grain_reconcile.py:691`) pads with UPCOMING games, which genuinely
never enter prior. The reachable padding shape — newly-completed games — is untested.

## Required fix shape

Capture the prior id-set BEFORE the grain's fresh upsert (or otherwise restore true
`|prior-as-of-run-start ∩ fresh|` semantics). Both grains: game and player-line. Also
verify the roster grain's `previously_rostered_ids` is captured pre-upsert by its caller
(`scouting_loader.py`) — the audit did not clear that ordering.

## Acceptance criteria the epic MUST carry

- New tests that FAIL against current code before the fix, PASS after:
  (a) player-line full id churn (9 new vs 9 stored) → refuses, 0 deletions;
  (b) game grain: stale absences + newly-completed games loaded same run → still refuses;
  (c) the boundary sweep above encoded as parametrized cases.
- The existing 72 reconcile tests stay green
  (test_game_grain_reconcile / test_player_line_reconcile / test_roster_grain_reconcile).
- Prose corrections IN THE SAME EPIC: comments at reconcile_at_load.py:596-603 and
  :962-968; and replace CLAUDE.md's "KNOWN DEFECT (2026-07-25 audit, fix in flight)"
  paragraph (commit b106b79, reconcile-at-load bullet) with the corrected description.
- Audit the E-270-03 e2e tests in tests/test_report_generator.py for the same prior
  pollution (the auditor flagged: if they drive a full re-scout, their "prior" is
  polluted the same way — they may be passing for the wrong reason).

Optional if trivially cheap, else file nothing: restore a `not_final ∩ fresh` defense
inside `retire_absent_games` (E-270-05 removed the caller-side intersection at
scouting_loader.py:393-407; protection now rests on a comment in another module).

## Reference material

The audit harness with the failing inputs (reusable):
/tmp/claude-1000/-workspaces-baseball-crawl/4aca143d-2d11-40ae-ae02-d8924803b063/scratchpad/recon_audit/

Guardrails: never touch data/app.db (report generation is destructive); synthetic DBs
from migrations/ only; no real crawls.

## Report back to the operator when done

Story list; the executed before/after refusal demonstration (id-churn input refusing);
full-suite result; the CLAUDE.md paragraph as rewritten.
