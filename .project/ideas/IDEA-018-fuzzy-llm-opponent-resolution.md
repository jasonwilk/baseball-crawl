# IDEA-018: Fuzzy LLM Opponent Resolution

## Status
`CANDIDATE`

## Summary
Use a lightweight LLM (Haiku) to fuzzy-match unlinked opponents to real GC teams by comparing rosters (player names, jersey numbers), cross-referencing shared game scores, and confirming "these are the same team" when the automated progenitor_team_id chain is unavailable.

## Why It Matters
~14% of opponents have no `progenitor_team_id` -- they were hand-created by coaches without linking to the real GC team. Manual URL paste works but requires coach technical savvy. An LLM-assisted matcher could propose candidates ("did you mean this team?") by comparing roster overlap, shared opponents, and game score matches, dramatically reducing the unlinked percentage with minimal operator effort.

## Rough Timing
After the opponent data model epic is complete and we have real data flowing through the resolution chain. We need to feel the pain of unlinked opponents in practice before investing in fuzzy matching.

## Dependencies & Blockers
- [ ] Opponent data model epic (E-088) must be complete -- need the `opponent_links` table and resolution tracking
- [ ] Need at least one season of crawled opponent data to validate matching quality
- [ ] Haiku API access (or equivalent lightweight model)

## Open Questions
- What's the minimum roster overlap threshold to propose a match with confidence?
- Should this run automatically during crawl or be an on-demand admin action?
- Cost model -- how many Haiku calls per unresolved opponent?
- Could simpler heuristics (exact roster name matches, shared game scores) handle most cases without LLM?

## Notes
- Vision signal captured in `docs/vision-signals.md` (2026-03-09)
- The operator said they're "probably okay manually mapping these for now" -- this is a nice-to-have, not urgent
- Three resolution tiers: (1) progenitor_team_id auto (~86%), (2) search by name, (3) fuzzy LLM match -- this idea is tier 3

---
Created: 2026-03-09
Last reviewed: 2026-03-09
Review by: 2026-06-07
