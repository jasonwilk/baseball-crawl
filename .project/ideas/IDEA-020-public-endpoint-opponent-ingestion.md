# IDEA-020: Public Endpoint Opponent Data Ingestion

## Status
`PROMOTED`

**Promoted to**: E-097 (Opponent Scouting Data Pipeline) on 2026-03-12. Combined with IDEA-019.

## Summary
Ingest opponent data via the public API endpoints (no auth required) as a complement or fallback to authenticated crawling. Four confirmed public endpoints provide team profile, game schedule with scores, game details with line scores, and roster -- all accessible with just a `public_id` slug.

## Why It Matters
Public endpoints require no authentication, never expire, and carry no rate-limit risk from credential rotation. For opponents where we have a `public_id` but limited authenticated access (or want to minimize authenticated API usage), public endpoints provide a solid baseline of scouting data.

## Rough Timing
After opponent data model establishes the resolution chain (which provides `public_id` values). Could be implemented alongside or after IDEA-019 (authenticated crawling) as a fallback/complement.

## Dependencies & Blockers
- [ ] Opponent data model epic (E-088) must be complete -- need `public_id` resolution
- [ ] Public endpoint schemas fully documented (most are, some response bodies still unknown)

## Open Questions
- Should public crawling be the default (safer, no auth) with authenticated crawling as enrichment?
- Or authenticated first (richer data) with public as fallback?
- How to deduplicate/merge data from both sources for the same team?

## Notes
- Four confirmed public endpoints: `/public/teams/{public_id}`, `/public/teams/{public_id}/games`, `/public/game-stream-processing/{game_stream_id}/details`, `/teams/public/{public_id}/players` (note inverted URL pattern)
- The `/public/teams/{public_id}/games/preview` endpoint is near-duplicate of `/games` -- prefer `/games`
- Public endpoints use `public_id` slugs, not UUIDs
- Game details endpoint also accepts `event_id` directly (confirmed 2026-03-09)

---
Created: 2026-03-09
Last reviewed: 2026-03-09
Review by: 2026-06-07
