# IDEA-127: Report generator stamps `name_only` identity-match before it back-fills the team's anchors (false-positive wrong-team badge)

## Status
`PROMOTED` (2026-07-12) — folded into E-262 (story E-262-03, live source bugs).

## Summary
The report generator records `identity_match_method='name_only'` on the `report_generation_runs` row BEFORE it back-fills the team's `public_id` and `gc_uuid` anchors within the SAME run. So the FIRST direct report for any team that already exists as a pre-scouted opponent stub always shows the operator "name-only match" wrong-team-risk badge on `/admin/reports`, even though the team is fully resolvable and self-heals during that same run. It is a sequencing bug, not a data-integrity problem -- no stats are misattributed.

## Why It Matters
The "name-only match" badge is a trust / wrong-team-risk signal shown to the operator. Firing it as a false positive on a team that IS correctly resolved erodes the badge's credibility for the real wrong-team case it exists to catch. A badge that cries wolf on correctly-resolved teams trains the operator to ignore it.

## Rough Timing
Someday / low urgency -- no data corruption, and the team self-heals (a re-run of the same report renders `anchor`, not `name_only`). Promote when the operator trust-surface / badge credibility is being worked, or if the false positive starts causing the operator to distrust or ignore the badge in practice.

## Dependencies & Blockers
- [ ] None hard. Self-contained within the report generator's identity-cascade + anchor back-fill sequence.

## Open Questions
- Which fix is cleanest (design call left to the epic):
  - (a) Back-fill the matched row's `public_id` BEFORE stamping `identity_match_method`, so the identity cascade's Step 2 (public_id match) succeeds instead of falling through to Step 3 (name match).
  - (b) Re-evaluate / re-stamp the match method AFTER the `gc_uuid` + `public_id` back-fill completes within the run.
  - (c) Pass the resolved `gc_uuid` into the cascade so Step 1 (gc_uuid match) can match.
- Does re-stamping (option b) risk masking a genuine name-only match that never resolves an anchor? (I.e., ensure the fix only downgrades the badge when a real anchor was actually established.)

## Notes
Root cause verified against live DB + code (2026-07-12 session):

- The operator badge "name-only match" renders on `/admin/reports` when `report_generation_runs.identity_match_method == 'name_only'` -- `src/api/templates/admin/reports.html:117-120`.
- That value is stamped in the report generator's `_ensure_team_row` at `src/reports/generator.py:1821-1830`, which calls `ensure_team_row_with_provenance()` passing `public_id` + `name` + `season_year` but **never a `gc_uuid`**. So the identity cascade (`src/db/teams.py:119-176`) can only match on `public_id` (Step 2) or name (Step 3); Step 1 (gc_uuid match) is dead code for this caller.
- When a team was first materialized as a **name-only opponent stub by the game loader** (`src/gamechanger/loaders/game_loader.py:1617-1623`, which inserts with `gc_uuid=None` and no `public_id` -- by design, to avoid contaminating the `gc_uuid` column), its `teams` row has NULL `public_id` at cascade time. So the generator misses Step 2, falls to Step 3 (name match) -> `name_only`.
- The SAME report run then back-fills the anchors AFTER the verdict is already stamped: `public_id` at `generator.py:1844-1853`, and `gc_uuid` (resolved via `POST /search`) at `generator.py:2168-2179`, which also sets `gc_uuid_status='resolved'`. This is why the live row looks fully anchored yet the run shows `name_only` + `gc_uuid resolved` together.
- Net effect: the FIRST direct report for any team that already exists as a scouted opponent always shows the wrong-team-risk badge, even though the team self-heals and a re-run would render `anchor`.
- Confirmed on a live game-loader-sourced opponent (team id=42; a scouted-opponent `public_id`, a generated report slug, source=game_loader) — real name/public_id/slug redacted here as PII.

---
Created: 2026-07-12
Last reviewed: 2026-07-12
Review by: 2026-10-12
