# IDEA-017: API Relationship and Chain Documentation

## Status
`CANDIDATE`

## Priority
HIGH -- this gap is felt now, not hypothetical.

## Summary
Extend api-scout's documentation model to capture cross-endpoint relationship chains and entity resolution flows, not just individual endpoint schemas. When exploring intricate multi-step API flows (opponent resolution, game cross-referencing, player identity mapping), the knowledge currently scatters across individual endpoint docs. There's no single place that documents "here's how you get from A to Z through endpoints X, Y, and Z."

## Why It Matters
Individual endpoint docs answer "what does this endpoint return?" but not "how do I resolve an opponent's local entry to their real team's public data?" The latter requires chaining 3-4 endpoints with specific ID field mappings (root_team_id vs progenitor_team_id vs public_id). Without a dedicated relationship doc, agents and operators must reconstruct the chain from scattered caveats across multiple files -- or go back to epic/conversation history to find it.

## What It Would Look Like
- A new doc type in `docs/api/` (e.g., `docs/api/flows/` or `docs/api/chains/`) that documents multi-endpoint flows end-to-end
- Each flow doc maps: the starting point, each step (endpoint + which field feeds the next step), the ending point, and edge cases (null fields, 403s, fallback paths)
- api-scout's ingestion workflow would be extended to recognize when a proxy session reveals a multi-step flow and produce a relationship doc alongside endpoint docs
- A taxonomy/naming convention for these docs

## Example: Opponent Resolution Chain (from current epic work)
The opponent resolution flow discovered during the opponent data model exploration (2026-03-09) would be the first instance:
1. `GET /teams/{team_id}/opponents` → `progenitor_team_id`
2. `GET /teams/{progenitor_team_id}` → `public_id`
3. `GET /public/teams/{public_id}` → opponent's self-reported data

Plus the search-based alternative:
1. `GET /search/opponent-import?name=...` → opponent team UUID
2. `GET /teams/{uuid}` → `public_id`
3. Public endpoints

Plus the import flow:
1. Search → preview (`import-summary`) → import (`POST /opponent/import`) → verify → roster

This example should be used as a model even if the format evolves.

## Rough Timing
Now. We're actively feeling this gap during opponent data model work. The opponent resolution chain doc should be written as part of the current epic, and the broader pattern/model should be established so api-scout produces these going forward.

## Dependencies & Blockers
- [x] docs/api/ structure exists (E-062)
- [x] api-scout agent exists and ingests sessions
- [ ] No blockers -- this can be done immediately

## Recommended Structure
- Location: `docs/api/flows/` -- separate from `docs/api/endpoints/`, visually distinct
- Naming: descriptive flow names, not HTTP paths (e.g., `opponent-resolution.md`, `game-cross-reference.md`, `player-identity-chain.md`)
- Frontmatter: flow-oriented schema (steps, starting entity, ending entity, edge cases) rather than endpoint-oriented (method, path, response_shape)
- Cross-linking: endpoint docs should reference relevant flows in their `see_also`, and flow docs should link to each endpoint they use
- Index: `docs/api/flows/README.md` listing all documented flows

## Open Questions
- Should api-scout auto-detect flow patterns during ingestion, or is this always a manual/prompted activity?
- What's the right frontmatter schema for flow docs? (Design during first implementation)

## Notes
- The opponent resolution chain is the motivating example, but other chains exist or will exist: game cross-referencing (same game from two teams' perspectives), player identity across teams/seasons, schedule-to-boxscore-to-plays drill-down
- This idea emerged from a conversation where we realized api-scout was documenting individual endpoints well but the relationship knowledge was only in conversation history

---
Created: 2026-03-09
Last reviewed: 2026-03-09
Review by: 2026-06-07
