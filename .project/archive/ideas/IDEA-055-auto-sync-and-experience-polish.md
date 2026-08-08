# IDEA-055: Auto-Sync and Experience Polish

## Status
`PROMOTED`
Promoted to E-181.

## Summary
Automatic stat updates after team add and merge, plus dashboard experience improvements: data freshness timestamps, "Not scouted" links to admin, richer opponent detail empty states, and a welcome state for new users. Deferred from E-178 to ship terminology and UX polish first.

## Why It Matters
Auto-sync removes the most common manual step (clicking "Update Stats" after adding or merging teams). Dashboard polish items reduce friction for coaching staff who navigate between admin and dashboard views. Together these make the system feel proactive rather than requiring the coach to know the next step.

## Rough Timing
After E-178 ships. The terminology and UX polish in E-178 establishes the consistent language that auto-sync flash messages will use. Promote when E-178 is complete.

## Dependencies & Blockers
- [ ] E-178 (terminology + UX overhaul) must be complete -- auto-sync flash messages use the new terminology

## Open Questions
- Does auto-sync after merge need a crawl_jobs guard (what if a job is already running for the canonical team)?
- What should data freshness timestamps look like on dashboard pages? Per-team or per-page-load?
- What does the welcome state for new users show? Empty teams list with a CTA?

## Notes
Items deferred from E-178 per UXD recommendation (ship polish first, features second):
1. Auto-first-sync on team add -- trigger background sync after insert
2. Auto-sync after merge -- trigger background sync on canonical team
3. Data freshness timestamps on dashboard pages
4. "Not scouted" → link to admin on schedule cards
5. Richer empty states on opponent detail
6. Welcome state for new users

These were originally scoped as E-178-02 (auto-sync stories) before the scope was revised. UXD's holistic design includes specifications for all 6 items.

---
Created: 2026-03-29
Last reviewed: 2026-03-29
Review by: 2026-06-27
