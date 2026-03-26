# IDEA-046: OpponentResolver Creates Duplicate gc_uuid Team Instead of Merging with Existing public_id Stub

## Status
`PROMOTED`

## Summary
`_ensure_opponent_team_row` in `src/gamechanger/crawlers/opponent_resolver.py` does `INSERT OR IGNORE INTO teams WHERE gc_uuid=?` without first checking whether any existing team already owns the target `public_id`. When a stub team already has the public_id (e.g., from a manual connect or earlier seeding), the resolver creates a NEW team row with the gc_uuid, hits a UNIQUE collision on public_id, logs a warning, and leaves the new team orphaned with a gc_uuid but no public_id.

## Why It Matters
Duplicate team rows cause data fragmentation: stats, opponent links, and scouting data split across two rows for the same real-world team. The operator must manually detect and clean up duplicates, which risks data loss (the gc_uuid on the orphaned row is not recoverable without log archaeology). Observed in production on 2026-03-26 when sync for Standing Bear Varsity created duplicate team id=454 for Bennington. Team 454 was deleted during cleanup, losing the gc_uuid until it was recovered from logs and manually written back to team 280.

## Rough Timing
- Promotable now -- the bug is actively causing production duplicates during routine syncs.
- Promote after E-160 ships (E-160 fixes the manual-connect duplicate path; this idea fixes the resolver duplicate path). Together they close the duplicate-team problem.

## Dependencies & Blockers
- [x] E-155 (opponent resolver) -- already complete, introduced the resolver code containing this bug
- [ ] E-160 (manual connect duplicate fix) -- complementary fix for a different code path; both should ship to fully close the duplicate-team problem

## Open Questions
- Should the merge also update other fields (e.g., team name, classification) from the resolver's API response, or only backfill gc_uuid onto the existing stub?
- Are there other code paths beyond the resolver and manual connect that can create duplicate teams? (IDEA-044 captures the broader prevention question.)

## Promotion
Promoted to E-162 on 2026-03-26.

## Notes
- **Relationship to E-160**: E-160 fixes the manual connect path (admin UI "connect" action). This idea fixes the resolver path (`OpponentResolver._ensure_opponent_team_row`). They are complementary fixes for different code paths that both produce the same symptom (duplicate team rows).
- **Relationship to IDEA-043 and IDEA-044**: IDEA-043 (fuzzy duplicate detection) and IDEA-044 (prevent duplicate creation) address the broader duplicate-team problem. This idea is a specific, well-understood bug fix for one confirmed code path.
- **Incident detail**: Bennington team id=454 created with gc_uuid `f911db1a-8134-4622-b543-d3426b747d14` as a duplicate of existing team 280 (which already had the public_id). Team 454 was deleted, gc_uuid recovered from logs, and manually written to team 280.

---
Created: 2026-03-26
Last reviewed: 2026-03-26
Review by: 2026-06-26
