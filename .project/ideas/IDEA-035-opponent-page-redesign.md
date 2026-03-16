# IDEA-035: Opponent Page Redesign

## Status
`CANDIDATE`

## Summary
Redesign the `/admin/opponents` page for the new team model. E-100 kept the opponent page as-is, only adding opponent counts with filtered links to the team list.

## Why It Matters
The current opponent page was built for the old model. With the team_opponents junction table and the new membership model, the opponent management UX could be more useful — showing which member teams face which opponents, linking to scouting data, and providing opponent discovery/resolution status.

## Rough Timing
After the scouting pipeline is producing opponent data. Promote when:
- Coaches are using the dashboard and need a better opponent management view
- The current opponent page causes confusion or workflow friction

## Dependencies & Blockers
- [x] E-100 (team_opponents junction table) — DONE
- [ ] Scouting pipeline should be producing data for opponents

## Open Questions
- What should the redesigned opponent page show? Opponent list per member team? Cross-team opponent overlap?
- Should opponent management move to the team edit page (manage opponents per team) instead of a standalone page?
- UX designer consultation needed for the redesign.

## Notes
- E-100 Non-Goal: "Opponent page redesign: `/admin/opponents` stays as-is. Only opponent counts with filtered links added to team list."

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
