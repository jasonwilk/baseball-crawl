# IDEA-086: Plays-Stage Rerun Re-Reconciles Already-Loaded Games

## Status
`CANDIDATE`

## Summary
Rerunning `bb data scout` should re-reconcile already-loaded plays, not skip them. The current `run_plays_stage` helper applies a "rerun = zero work" idempotency optimization that pre-fetch-skips games with existing `plays` rows -- that pre-skip excludes those games from reconcile too, leaving derived pitcher attribution stale after backfills or other changes to reconcile inputs.

## Why It Matters
`reconcile_game()` rewrites `plays.pitcher_id` based on `appearance_order` from the boxscore. After the documented `bb data backfill-appearance-order` workflow (CLAUDE.md lists this as a footgun: "after backfill, run `bb data scout` to recompute scouting season aggregates"), rerunning `bb data scout` will not actually revisit plays for already-loaded games, so `plays.pitcher_id` and any derived pitching metrics remain stale.

This is in tension with the project rule "Pipeline data quality steps must be automatic" -- right now, the operator-facing instruction to rerun scout silently no-ops on the plays-stage reconcile path for already-loaded games. After any schema correction or change to boxscore-derived inputs, reconcile-on-rerun would automatically refresh attribution; today it does not.

## Rough Timing
Not blocking anything in the short term. Promote when:
- Operator next hits a backfill scenario where `plays.pitcher_id` staleness becomes visible, OR
- A reconcile-engine change ships that would benefit from auto-refresh across already-loaded games.

Lower priority than IDEA-082 (run_id clustering -- improves visibility into reconcile output) and IDEA-085 (crawl_jobs status timing); those should land first.

## Dependencies & Blockers
- [ ] None hard. `run_plays_stage` is the canonical entry point now (E-229 closed 2026-04-29) so the change has a single site to land in.

## Open Questions
- Should the helper just always reconcile (cost: ~30 `reconcile_game()` calls per scout per team -- DB-only, probably negligible), or should it detect when reconcile inputs have changed (more complex, e.g., compare `appearance_order` between current boxscore state and prior reconcile run)?
- Does this affect the CLI `loaded/skipped` counters in `PlaysStageResult`? Pre-fetch-skipped games would still count toward `skipped` (no HTTP, no load), but reconcile would still run. Need to think through counter semantics so the verbose summary stays meaningful.
- Should there be a `--reconcile-only` flag for the case where the operator just wants to re-reconcile without re-fetching plays?

## Notes
- Source: Codex round-6 review during E-229 closure (2026-04-29).
- Related ideas: IDEA-082 (optional `run_id` clustering on `reconciliation_discrepancies` -- improves visibility into reconcile output), IDEA-085 (fix `crawl_jobs.status='completed'` timing in `run_scouting_sync`).
- Relevant context: CLAUDE.md scouting-pipeline-parity invariant; `run_plays_stage` at `src/gamechanger/pipelines/plays_stage.py` (single canonical orchestrator, established by E-229).

---
Created: 2026-04-29
Last reviewed: 2026-04-29
Review by: 2026-07-28 (90 days from created)
