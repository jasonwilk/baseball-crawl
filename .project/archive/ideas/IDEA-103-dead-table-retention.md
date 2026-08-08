# IDEA-103: Dead-Table Retention — `crawl_jobs` + `coaching_assignments`

## Status
`CANDIDATE`

## Summary
Two tables survive in the schema but are inert on the forward (reports-first) path: **`crawl_jobs`** and **`coaching_assignments`**. Neither is ever INSERTed or SELECTed by live code — they are only referenced by DELETE statements in the team-deletion cascade. This idea records the retention rationale and the drop-blocker so a future removal epic can act deliberately rather than re-discovering the analysis.

## Why It Matters
Inert tables are cheap to keep but they are cruft: they appear in the schema, in the cascade DELETE set, and in any schema-comprehension pass. Dropping them is NOT free — it requires rewriting the cascade-deletion logic (`_delete_team_scoped_data` in `src/reports/lifecycle.py`) and a migration. *(⚰ This cited `src/reports/generator.py` until 2026-07-27 — a stale path, corrected during E-277 closure. The symbol moved; a reader following the old citation would land on a file where it does not exist. Found by `ca-2` during E-277 story 04, which correctly refused to fix it: `.project/ideas/` is PM-owned and an implementer editing another agent's domain is a routing violation even when the edit is right.)* Capturing the exact dead set + the drop-blocker now means the removal can be scoped in one clean pass (likely folded into E-256's post-descope simplification or a dedicated table-drop epic) instead of re-deriving which tables are truly dead each time.

## The Dead Set (DE + PM verified 2026-07-07)
- **`crawl_jobs`** — sole reference is one DELETE in the team-deletion cascade; never INSERT/SELECT. Member-sync crawl-job tracking; the member-sync pipeline was removed in E-239.
- **`coaching_assignments`** — 2 DELETEs in the cascade + a docstring mention; never INSERT/SELECT. Dead multi-user-permissions table (ROADMAP §7 non-goal: multi-user team-scoped permissions).

## Explicitly NOT in the dead set (exclusions baked in)
- **`user_team_access`** — LIVE. It is the non-admin team-access grant mechanism (W=3/R=7 across `auth.py` + `reports_admin.py`). Do NOT capture.
- **`team_opponents`** — already DROPPED in migration 008 (E-250). Gone, not retained.
- **`programs`** — unqueried in app code BUT FK-load-bearing: migration 001 bootstraps `lsb-hs` and `teams.program_id` FKs to it. "Unqueried-but-load-bearing" — keep OUT of the dead set. (See IDEA-091 for the broader `programs` machinery question.)

## Rough Timing
Fold into E-256 (post-descope simplification / aggregate cutover) if it does a schema pass, or a dedicated small table-drop epic. Not urgent — inert tables cost little.

## Dependencies & Blockers
- [ ] Drop requires rewriting the team-deletion cascade (`_delete_team_scoped_data`) to stop referencing the two tables.
- [ ] A migration to drop the tables (numbered after the current highest — glob `migrations/` at write time).
- [ ] Confirm no external/analytics consumer reads them (none found in app code as of 2026-07-07).

## Notes
- Set confirmed by data-engineer's `src/` sweep + PM verification during E-255 docket-confirmation (2026-07-07).
- This is the dead-table capture called for by E-255-06 AC-4.

---
Created: 2026-07-08
Last reviewed: 2026-07-08
Review by: 2026-10-06
