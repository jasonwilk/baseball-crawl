# IDEA-061: Derive season_id from Team Context, Not Filesystem Path

## Status
`PROMOTED`

Promoted to E-197.

## Summary
Loaders (game_loader, plays_loader, season_stats_loader, and others) derive `season_id` from the crawl directory path (e.g., `2026-spring-hs`). This is wrong for teams whose real season context differs from the directory they were crawled into -- e.g., a 2025 summer USSSA team crawled under `2026-spring-hs/` gets all its data tagged with the wrong season_id.

## Why It Matters
1. **Cross-team player stat merging**: Players on multiple teams (e.g., Kadyn Lichtenberg on both Rebels 14U and Freshman Grizzlies) have plays from different real seasons lumped under the same `season_id`, making per-season validation and display impossible.
2. **Incorrect season context**: The Rebels 14U's 92 games are tagged as 2026 spring HS when they're actually 2025 summer USSSA.
3. **Validation false positives**: The FPS/QAB validation script groups by `(player_id, season_id)` but gets wrong groupings because season_id doesn't reflect reality.
4. **Multi-program expansion**: As more non-HS teams are onboarded (Legion, USSSA), this problem will multiply. Every team whose real season differs from the crawl directory gets wrong season_id.

## Rough Timing
- **Now**: The pain is real -- Rebels 14U data is already mis-tagged in production.
- **Trigger**: This became visible when validating plays data across teams with shared players. It will get worse as more programs and seasons are onboarded.

## Dependencies & Blockers
- [ ] Need to define how season_id should be constructed from team context (e.g., `{season_year}-{season_type}-{program_type}` derived from `teams.season_year` + program metadata)
- [ ] Need to understand the full set of loaders that use the directory-path derivation pattern
- [ ] May need a data migration to fix existing mis-tagged rows (games, plays, play_events, season stats, spray charts)

## Open Questions
- What is the canonical season_id format? Currently it's `{year}-{season_type}-{program_type}` (e.g., `2026-spring-hs`). Should this remain the format but be derived from team metadata instead of filesystem?
- Should the crawl directory structure also change to match, or is filesystem organization a separate concern from DB season_id?
- How should the `seasons` table interact with this? Is there a seasons row per team-year, or per program-year?
- What about teams with NULL `season_year`? The current fallback is calendar year -- is that acceptable for season_id derivation too?
- Scope of data migration: how many rows need season_id correction, and can it be done in a single pass or does it need per-table handling?

## Notes
- Root cause: `season_id` should come from the **team's season context** (via `teams.season_year` and the team's program type), not from the filesystem path where data was crawled. The crawl directory is an operator convenience for organizing raw files -- it should not be the source of truth for season identity in the database.
- Affects: `game_loader`, `plays_loader`, `season_stats_loader`, `spray_chart_loader`, and potentially other loaders that touch `season_id`.
- Related: IDEA-039 (Game Metadata Enrichment) touches adjacent concerns but is about adding new metadata, not fixing existing derivation.

---
Created: 2026-04-01
Last reviewed: 2026-04-01
Review by: 2026-06-30
