# IDEA-107: Normalize `/game-stream-processing/` Endpoint-Doc Path-Variable Naming

## Status
`PROMOTED` (2026-07-12) — folded into E-262 (story E-262-09, docs/api cleanup).

## Summary
Sibling `docs/api/` endpoint files name the `/game-stream-processing/{id}/` path variable inconsistently — `get-game-stream-processing-game_stream_id-boxscore.md` uses `{game_stream_id}` while `get-game-stream-processing-event_id-plays.md` uses `{event_id}` — even though BOTH endpoints take `event_id` as the path parameter (verified: `game_stream.id` returns HTTP 500 on both). The filenames and their frontmatter `path:` placeholders + `see_also` link entries carry the legacy `game_stream_id` name, which can mislead a reader into thinking boxscore takes a different id than plays.

## Why It Matters
E-255-04 corrected all the PROSE routing claims (every doc that ASSERTS which id an endpoint takes now agrees on `event_id`), but the filename-derived placeholder naming is a separate, coupled change it left out of scope. A `path: /game-stream-processing/{game_stream_id}/boxscore` placeholder that disagrees with the doc's own caveats ("the parameter is event_id, NOT game_stream.id") is a latent inconsistency, even though the caveat resolves it in-file.

## Scope (the coupled rename)
- Rename `get-game-stream-processing-game_stream_id-boxscore.md` → `-event_id-boxscore.md` (and any other `game_stream_id`-named file whose endpoint actually takes `event_id`).
- Update the frontmatter `path:` placeholder in the renamed files.
- Update every inbound `see_also` `path:` entry across `docs/api/` that references the old filename/placeholder (README + several endpoint docs).

## Rough Timing
Low priority — cosmetic/consistency. Bundle with any future `docs/api/` structural pass. Both PM (E-255-04 flag 2) and code-reviewer (E-255-04 SHOULD FIX) flagged it as deferrable.

## Dependencies & Blockers
- [ ] None technical. It is a mechanical rename + link sweep; do it atomically (file rename + frontmatter + all see_also refs) so no half-renamed state is left.

## Notes
- Surfaced during E-255-04 (docs/api endpoint-doc accuracy corrections); this was the un-addressed residual when E-073 (API Documentation Validation Sweep) was archived in E-255-06, captured here so it is not lost.
- api-scout owns `docs/api/**`.

---
Created: 2026-07-08
Last reviewed: 2026-07-08
Review by: 2026-10-06
