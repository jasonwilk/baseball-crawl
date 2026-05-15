# IDEA-076: Coverage-Cue Full-Fidelity Restoration

## Status
`CANDIDATE`

## Summary
Restore the full "Through {date} ({N} games)" freshness cue on the opponent-dashboard "Defensive Positioning" card by persisting the displayed report's coverage snapshot (latest game date + game count) on the `reports` row at generation time. E-228 shipped a degraded "Through {Mon Day}" form (Option A) after Phase 4b finding #3 caught the original wiring threading live team coverage (which can drift past the displayed report's actual coverage). The shipped cue is honest given today's schema but loses the game-count and the full date.

## Why It Matters
The full "Through {date} ({N} games)" form is what the E-228-04 design spec specified (§8.3 (b)) and what coaches are getting elsewhere in the system -- the dashboard's other freshness cues use this format. Showing a different, abbreviated form on the positioning card creates a small but real inconsistency that coaches will notice ("why is this date format different?"), and the lost game count means a coach can't tell at a glance how many games of evidence back the cards. Once the operator runs the system against real data and the cards become part of the regular workflow, the inconsistency will read as system rough-edge rather than intentional.

## Rough Timing
After the first-real-opponent calibration pass (epic E-228 Rollout section) -- if the operator confirms the abbreviated form is in fact a rough edge during real use. Not urgent if the operator doesn't feel the gap. Trigger: operator says "the date format on the positioning card looks weird" OR the project does a wider pass on freshness-cue consistency across surfaces.

## Dependencies & Blockers
- [ ] E-228 archived and the degraded cue is in operator use long enough to assess whether the inconsistency is felt
- [ ] Schema change to `reports`: add nullable `coverage_latest_game_date TEXT` and `coverage_game_count INTEGER` columns (or a `coverage_snapshot JSON` column) populated at report generation time
- [ ] Backfill: existing `ready` reports would either need a migration that re-derives coverage from the team's `games` table as of `generated_at` (best-effort) or accepts NULL (the abbreviated form remains for pre-IDEA-076 reports)

## Open Questions
- Single columns vs. JSON snapshot? Single columns are simpler and queryable; JSON is more extensible if the freshness cue ever needs richer data (e.g., "through inning 5 of game N"). For v1 of this idea, single columns are likely sufficient.
- Backfill scope -- does the project care enough about historical reports' cue fidelity to do a best-effort backfill, or is "going forward only" acceptable?
- Where does the snapshot get computed? Most natural seam is inside `generate_report()` after the data queries run, before the report row is written to `ready` status -- the same connection scope that builds the report.

## Notes
Source: E-228 Phase 4b Codex post-dev review finding #3 (2026-05-15). Captured as part of E-228 closure ideas backlog review. The epic's TN-7 documents the degraded "Through {Mon Day}" form as "Option A" with this idea as "Option B" (the full restoration path). E-228-04 §8.3 (b) is the original spec contract this idea restores.

---
Created: 2026-05-15
Last reviewed: 2026-05-15
Review by: 2026-08-15 (suggest 90 days from created)
