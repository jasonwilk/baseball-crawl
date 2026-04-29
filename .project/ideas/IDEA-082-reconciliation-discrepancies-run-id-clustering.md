# IDEA-082: Optional run_id Clustering on reconciliation_discrepancies

## Status
`CANDIDATE`

## Summary
Allow operators to filter `reconciliation_discrepancies` rows by scout run via an optional `run_id` UUID that is shared across all rows produced by one scout invocation. Mirrors the existing pattern at `src/reconciliation/engine.py:451` (`reconcile_all`) where the bulk reconciler already clusters its rows under one UUID.

## Why It Matters
Today the per-game `reconcile_game(...)` calls inside `run_plays_stage` produce `reconciliation_discrepancies` rows that are not clustered by scout invocation. An operator looking at a discrepancy row cannot easily ask "what other discrepancies came from the same scout run?" -- they have to filter by `created_at` window and team, which is fragile. Clustering by `run_id` makes "show me all discrepancies from yesterday's bulk scout" a one-WHERE-clause query.

## Rough Timing
Promote when: (a) coaches or operators ask for run-clustered discrepancy filtering, OR (b) the dashboard needs to surface "this scout run produced N discrepancies" as a metric.

## Dependencies & Blockers
- [x] E-229 must be complete (the shared helper is the natural place to plumb the `run_id` through to `reconcile_game`)
- [ ] Confirm coaching value before promoting -- this is a coaching/operator-UX question, not a pure-engineering one

## Open Questions
- Should `run_id` be assigned by the helper (one per `run_plays_stage` call) or by the caller (one per scout pipeline invocation, shared across all teams in bulk mode)?
- Does the existing `reconcile_all` UUID format align, or is there a reason to differ?
- Is the value of clustering enough to justify a schema migration adding a new column, or can we use an existing column (e.g., a derived prefix on `error_message`)?

## Notes
Surfaced during E-229 planning -- one of the resolved Q4 sub-questions ("punted -- separate idea if reconcile-clustering becomes a coaching ask"). Filed at E-229 closure per Closure Tasks section.

---
Created: 2026-04-29
Last reviewed: 2026-04-29
Review by: 2026-07-28
