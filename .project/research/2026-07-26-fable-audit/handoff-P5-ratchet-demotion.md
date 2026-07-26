# P5 — Demote the reconciliation ratchet to a plain diagnostic (operator decision:
# "the ratchet has become a distraction")

Invoke product-manager + claude-architect (PM owns the scope call, CA owns the layer
edits). The operator has decided the E-257 ratchet machinery costs more attention than
it returns. Reshape it as follows unless PM surfaces a blocking objection:

## Keep
- `bb report reconcile-scoreboard` (and `--json`) as a pure read-only diagnostic — the
  table itself is useful before/after ingestion changes.
- The North Star principle in docs/VISION.md and CLAUDE.md's Data Philosophy (the
  direction stands; only the mechanical gate goes).

## Remove / demote
- The one-way ratchet GATE: no more exit-1-on-regression against a committed baseline,
  no baseline-freshness obligation, no `--update-baseline` operator debt, no closure
  ratchet-exception bookkeeping (currently 2-of-3 closures carried exceptions, and the
  baseline is ~4 epics stale — the gate is mostly generating paperwork).
  Either delete the baseline diff entirely or keep it behind an optional
  `--baseline <path>` with no committed default. PM decides which; deleting is simpler.
- The E-256 closure-smoke coupling that consumes the --json axis counters, if that
  coupling forces baseline maintenance (verify what the smoke actually reads before
  cutting; keep `self_games == 0` as a standalone assertion if it's load-bearing —
  that one is a hard invariant, not a ratchet).
- CLAUDE.md: collapse the reconcile-scoreboard passage in Commands and the
  "Operating Principle" paragraph's gate-mechanics sentences to ~3 lines (diagnostic
  exists, principle stands, gate retired <date> by operator decision). This paragraph
  is one of the largest single blocks in CLAUDE.md — the trim is a real context win.
- `.claude/rules/` and agent-memory references to baseline snapshots/ratchet
  exceptions (grep `ratchet`, `reconcile-scoreboard`, `--update-baseline`, AND sweep
  semantically per doc-sweep.md — closure skills and PM memory carry
  ratchet-exception procedure that must not survive as orphaned process).

## Sequencing note
P1 (health-gate fix) may legitimately IMPROVE plays-derived fidelity; with the gate
demoted, no baseline re-snapshot is owed afterward — one less coupling. If this lands
before P1, P1's prompt line about the scoreboard becomes moot.

## Report back
The diff summary (expect net-negative lines in CLAUDE.md + rules + skills), what the
E-256 smoke consumes now, and one sentence on where `self_games == 0` enforcement
lives after the change.
