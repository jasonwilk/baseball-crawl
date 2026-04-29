# IDEA-085: Fix crawl_jobs.status='completed' Timing in run_scouting_sync

## Status
`CANDIDATE`

## Summary
Move `_mark_job_terminal('completed')` and `_update_last_synced` in `src/pipeline/trigger.py:run_scouting_sync` from their current position (immediately after the load phase, before spray/dedup/plays run) to AFTER all enrichment stages so the row's `status` actually reflects pipeline completion.

## Why It Matters
Today `crawl_jobs.status='completed'` is written before spray, dedup, and (post-E-229) plays additive-enrichment stages run. An operator querying the table at the wrong moment sees status=completed when half the pipeline still has work to do. This contradicts the column's natural meaning. The current arrangement is a pre-existing timing oddity preserved as-is during E-229 to keep scope tight; fixing it was opportunistic scope per the SE Y2 retraction.

## Rough Timing
Promote when: (a) operators report confusion about scout completion timing, OR (b) the next epic that touches `run_scouting_sync` for unrelated reasons -- moving the writes is mechanical and small.

## Dependencies & Blockers
- [x] E-229 must be complete (the plays additive-enrichment pattern depends on the existing timing; once this idea ships, the plays wrapper's `error_message` UPDATE pattern can be revisited too)
- [ ] None -- the change is mechanical (move two function calls from one spot to another)

## Open Questions
- Should `error_message` aggregation be reworked at the same time, since the plays wrapper currently UPDATEs `error_message` directly because `_mark_job_terminal` already ran with `error_message=None`? (After this idea ships, the wrapper could pass the prefix into `_mark_job_terminal` instead.)
- What about partial-failure cases where the load succeeded but spray failed? Should that be reflected in `status` (e.g., `completed_with_warnings`) or stay in `error_message` only?

## Notes
Surfaced as SE Y2 push during E-229 planning, then retracted by SE during iter-1 review. SE quote: "PM's auth-error proposal is exactly right and I retract my earlier Y2 push... The pre-existing timing oddity (status marked before spray runs today) is not E-229's problem to fix." Captured here as a clean follow-up. Filed at E-229 closure per Closure Tasks section.

---
Created: 2026-04-29
Last reviewed: 2026-04-29
Review by: 2026-07-28
