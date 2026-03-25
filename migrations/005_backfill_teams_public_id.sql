-- Migration 005: Backfill teams.public_id from opponent_links
--
-- Heals existing data inconsistencies where resolved opponents have a
-- public_id recorded in opponent_links but the corresponding teams row
-- is missing its public_id.
--
-- The manual SQL fix applied on 2026-03-25 patched 6 rows for the
-- Freshman Grizzlies. This migration generalises that fix to cover any
-- resolved opponents regardless of when they were resolved.
--
-- Safety properties:
--   - Idempotent: WHERE public_id IS NULL ensures already-populated rows
--     are never touched.
--   - Deterministic: ORDER BY resolved_at DESC, id DESC LIMIT 1 picks the
--     most-recent opponent_links row when multiple rows point to the same
--     resolved_team_id; the id tiebreaker handles NULL resolved_at.
--   - Collision guard: The NOT IN (...) clause skips rows where the target
--     public_id already exists on a different teams row, preventing UNIQUE
--     constraint violations for pre-existing slugs.
--   - Batch-duplicate guard: When two or more teams rows both map to the
--     same target slug, ALL of them are skipped (public_id stays NULL).
--     This is consistent with how _write_public_id handles collisions in
--     the resolver (skip + log) and avoids an ambiguous automatic pick
--     that would route scouting data to the wrong team row.

UPDATE teams SET public_id = (
    SELECT ol.public_id FROM opponent_links ol
    WHERE ol.resolved_team_id = teams.id
      AND ol.public_id IS NOT NULL
    ORDER BY ol.resolved_at DESC, ol.id DESC
    LIMIT 1
)
WHERE public_id IS NULL
  AND id IN (
    SELECT resolved_team_id FROM opponent_links
    WHERE public_id IS NOT NULL
  )
  AND (
    SELECT ol2.public_id FROM opponent_links ol2
    WHERE ol2.resolved_team_id = teams.id
      AND ol2.public_id IS NOT NULL
    ORDER BY ol2.resolved_at DESC, ol2.id DESC
    LIMIT 1
  ) NOT IN (
    SELECT t2.public_id FROM teams t2
    WHERE t2.public_id IS NOT NULL
  )
  -- Batch-duplicate guard: skip ALL rows when the target slug would be
  -- claimed by more than one teams row.  Only rows with a unique slug
  -- mapping (count = 1) are backfilled.
  AND (
    SELECT COUNT(DISTINCT t3.id) FROM teams t3
    WHERE t3.public_id IS NULL
      AND t3.id IN (
        SELECT ol3.resolved_team_id FROM opponent_links ol3
        WHERE ol3.public_id IS NOT NULL
      )
      AND (
        SELECT ol4.public_id FROM opponent_links ol4
        WHERE ol4.resolved_team_id = t3.id
          AND ol4.public_id IS NOT NULL
        ORDER BY ol4.resolved_at DESC, ol4.id DESC
        LIMIT 1
      ) = (
        SELECT ol5.public_id FROM opponent_links ol5
        WHERE ol5.resolved_team_id = teams.id
          AND ol5.public_id IS NOT NULL
        ORDER BY ol5.resolved_at DESC, ol5.id DESC
        LIMIT 1
      )
  ) = 1;
