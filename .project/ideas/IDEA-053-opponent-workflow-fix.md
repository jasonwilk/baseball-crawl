# IDEA-053: Fix Opponent Scouting Workflow End-to-End

## Status
`CANDIDATE`

## Summary
Fix the broken opponent scouting workflow so that resolving an opponent in the admin UI causes stats to appear in the dashboard. Currently, resolution updates `opponent_links` but never propagates to `team_opponents` (which the dashboard queries), leaving coaches with empty scouting reports. Includes: resolution write-through, auto-scout after resolution, unified resolve page, dashboard sort by next game date, terminology cleanup, and one-time data repair.

## Why It Matters
Coaches cannot see scouting stats for resolved opponents because of a data layer disconnect between `opponent_links` and `team_opponents`. The admin workflow requires 5 manual steps across 3 UI surfaces + CLI. This is the core opponent data pipeline fix — without it, the main dashboard's opponent system doesn't work end-to-end.

## Rough Timing
After E-172 (standalone scouting report generator) ships — the standalone report is a bridge feature providing immediate value while this systemic fix is planned. Promote when the operator starts relying on the main dashboard opponent flow rather than standalone reports.

## Dependencies & Blockers
- [ ] E-172 (standalone report) should ship first as the quick path
- [ ] E-162 (OpponentResolver duplicate gc_uuid fix) should be resolved or its fix absorbed
- [ ] E-170 (opponent connect public_id collision) should be resolved or absorbed

## Open Questions
- Should this absorb E-171 (enrich resolve search results) or keep it separate?
- Does E-167's `ensure_team_row()` dedup cascade need further refinement before this work?
- How much of the old E-172 epic content (6 stories, 4 expert consultations) can be reused vs. needs re-planning?

## Notes
Full epic content (6 stories with ACs, 4 expert consultations) was written under the original E-172 scope and is preserved in git history (commit before 2026-03-28 scope change). The expert consultations (coach, DE, SE, UXD) and Technical Notes are reusable. Key stories: resolution write-through to team_opponents, auto-scout after resolution, unified resolve page, dashboard sort + data status, terminology cleanup, data repair command.

---
Created: 2026-03-28
Last reviewed: 2026-03-28
Review by: 2026-06-26
