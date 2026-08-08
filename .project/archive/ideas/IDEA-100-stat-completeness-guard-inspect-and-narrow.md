# IDEA-100: Inspect-and-Narrow the Three-State `stat_completeness` Provenance Guards

## Status
`CANDIDATE`

## Summary
The `stat_completeness` provenance model has three states (`full` / `supplemented` / `boxscore_only`) and a set of guards that protect member-authoritative (`full`/`supplemented`) rows from being overwritten by `boxscore_only` recomputes. Post-E-239, the member-write path is deleted and only the `boxscore_only` opponent-scouting path remains live — so the guards no longer fire on the forward path. This idea is to **inspect** which of those guards still earn their keep and **narrow** the model to what remains load-bearing — deliberately, not by blind deletion.

## Why It Matters
This surfaced from the 2026-07-03 platform audit's decision review (§3, "Three-state `stat_completeness` provenance retained post-E-239"). The decision to *retain* the guards was upheld — the defense held — but the audit's residual action was explicitly to "capture a targeted inspect-and-narrow cleanup idea; do not delete the guards blind." The carrying cost is dead-branch complexity: guards, provenance columns, and a mental model that all reason about a `full`/`supplemented` member-write path that no longer exists in the code. Narrowing reduces the footgun surface (mixed-provenance scope hazards, the E-247 wipe-hazard class) that agents must keep in mind on every recompute/dedup change.

## Why NOT to Just Delete (the guardrail on this idea)
- **Member rows are API-authoritative and NOT re-derivable.** The member-sync writer AND the member re-fetch path were both deleted in E-239. If any `full`/`supplemented` rows still exist on the live DB, a `boxscore_only` recompute that overwrites them destroys data that cannot be regenerated — there is no source to re-pull it from.
- **The guards never fire on the forward path today**, but retention was a **deliberate, recorded E-239 decision** (data-engineer finding S3), not an oversight. Any narrowing must first establish what provenance actually exists on the live DB before removing the protection.
- Therefore the work is *inspect first, then narrow* — not delete.

## Rough Timing
Someday / low urgency. Natural to fold into E-256 (CE-6, post-descope simplification & foundations), which already owns the related dead-table sweep and the query-time-aggregate REVISIT cutover — if that cutover retires the stored `player_season_*` tables, this provenance question may be substantially answered or reshaped by it. Reassess this idea's fate when E-256 is refined.

## Dependencies & Blockers
- [ ] A live-DB inspection of which `stat_completeness` states actually exist in `player_season_batting` / `player_season_pitching` (needs DB access — an operator follow-up, not a worktree task).
- [ ] Coordinate with E-256's query-time-aggregate REVISIT cutover — if the stored aggregate tables are retired, this changes shape or becomes moot.

## Open Questions
- Do any `full`/`supplemented` rows remain on the live DB, and for which teams/seasons? (Determines whether any guard still protects real data.)
- If none remain, is the correct move to (a) collapse to a two-state or single-state model, (b) keep the columns but drop the guard branches, or (c) leave as-is with a data-model.md note? Decide only after inspection.
- Does the E-256 aggregate cutover subsume this entirely?

## Notes
- Audit reference: PLATFORM-AUDIT.md §3 (SOUND_BUT_UNDERDOCUMENTED / REVISIT — defense held), "Three-state `stat_completeness` provenance retained post-E-239."
- Provenance-ownership rules are documented in CLAUDE.md (Architecture, `canonical_recompute` provenance ownership) and `.claude/rules/data-model.md` (Season-Aggregate Parity, mixed-provenance scope footgun).
- Related: the E-256 (CE-6) query-time-aggregate REVISIT cutover; the dead-table sweep in the same epic.

---
Created: 2026-07-06
Last reviewed: 2026-07-06
Review by: 2026-10-04
