# IDEA-019: Retroactive Opponent Stat Crawling

## Status
`PROMOTED`

**Promoted to**: E-097 (Opponent Scouting Data Pipeline) on 2026-03-12. Combined with IDEA-020.

## Summary
Once opponents are resolved to real GC teams (via the opponent data model), crawl their full stat profiles -- season stats, game summaries, player stats, box scores -- using the authenticated API. This is the payoff of the resolution chain: scouting reports built from the opponent's own data, not your scorekeeper's version.

## Why It Matters
The core scouting insight: your team's opponent entry is your scorekeeper's representation of the game. The opponent's own GC page has their version -- their stats, their roster, their perspective. For pre-game scouting reports, you want the opponent's self-reported data. The resolution chain (progenitor_team_id -> public_id) makes this possible programmatically.

## Rough Timing
After the opponent data model epic establishes the resolution chain and link tracking. This is the natural second phase: resolve first, then crawl.

## Dependencies & Blockers
- [ ] Opponent data model epic (E-088) must be complete -- need resolved opponent links
- [ ] Crawl orchestration patterns established (may overlap with IDEA-012)
- [ ] Rate limiting and credential management must handle the increased API call volume

## Open Questions
- How much data per opponent? Full season stats + all game summaries + all player stats could be substantial
- Crawl frequency? Once per opponent per season? Incremental?
- Storage model -- same tables as own-team data, or separate opponent-specific schema?
- Priority ordering -- crawl upcoming opponents first for pre-game scouting?

## Notes
- Confirmed 2026-03-09: ALL `/teams/{id}/*` endpoints work with opponent `progenitor_team_id` (55 player-stats calls, all 200 OK in mobile session)
- Public endpoints also available via `public_id` (no auth needed) but authenticated endpoints provide richer data
- This is where the opponent data model investment pays off for coaching

---
Created: 2026-03-09
Last reviewed: 2026-03-09
Review by: 2026-06-07
