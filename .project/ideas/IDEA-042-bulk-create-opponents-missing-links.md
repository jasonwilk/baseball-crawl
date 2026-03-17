# IDEA-042: bulk_create_opponents Should Create team_opponents Links

## Status
`CANDIDATE`

## Summary
`bulk_create_opponents` (called by the scouting crawler) creates `teams` rows for discovered opponents but does not insert `team_opponents` junction rows linking them to the discovering team. Auto-discovered opponents aren't actually linked as opponents -- operators must manually re-add them via the Add Team flow, defeating the purpose of automated opponent discovery.

## Why It Matters
The scouting pipeline's opponent discovery is supposed to automate linking opponents to member teams. Without `team_opponents` entries, discovered opponents are invisible in the opponents UI (which is driven by `opponent_links` / `team_opponents`). This creates a silent failure where the crawler appears to work but the data doesn't flow through to the coaching dashboard.

## Rough Timing
Promote when the scouting pipeline is actively used for game prep -- likely after E-117 (loader stat population) ships and coaches start relying on scouting data.

## Dependencies & Blockers
- [ ] None blocking -- standalone code fix in the scouting loader
- [ ] Practical value increases after E-117

## Open Questions
- Should `bulk_create_opponents` also populate the `first_seen_year` column in `team_opponents`?
- Should existing placeholder `teams` rows (created without links) be retroactively linked?

## Notes
Discovered during E-116 post-dev Codex review (finding 3). The doc side was fixed inline; this is the code follow-up.

---
Created: 2026-03-17
Last reviewed: 2026-03-17
Review by: 2026-06-15
