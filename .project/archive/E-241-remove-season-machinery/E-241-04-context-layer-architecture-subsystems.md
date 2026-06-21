# E-241-04: Rewrite the season-machinery sections of `architecture-subsystems.md`

## Epic
[E-241: Remove the cross-season machinery residue from the core](epic.md)

## Status
`DONE`

## Description
After this story is complete, `.claude/rules/architecture-subsystems.md` describes
the year-only season derivation (no suffix taxonomy, no `season_fallback` telemetry —
but the current-year fallback survives), the additive-extension pattern entry retains
only its surviving worked example, and the filesystem/DB season_id-decoupling section
is revised (not retired) to the year-only-DB reality.

## Context
The context-layer documentation describes the season machinery this epic removes,
so it becomes factually wrong once E-241-06 (the derivation collapse) lands. This is
a context-layer file, so it routes to claude-architect (per the agent-routing
precedence). The exact sections and dispositions were scoped during discovery by
claude-architect. Per Technical Notes TN-8.

## Acceptance Criteria
- [ ] **AC-1**: The "Season_id Derivation (Detail)" section (≈L36-38) is rewritten
  to describe year-only derivation, crisply distinguishing REMOVED from SURVIVING:
  - REMOVED — the `program_type`→suffix mapping (`hs`→`spring-hs`,
    `usssa`→`summer-usssa`, `legion`→`summer-legion`) and the `season_fallback`
    telemetry flag/chain.
  - SURVIVING (load-bearing kernel) — the current-year fallback
    (`season_year IS NULL → current year`, i.e. `season_id = str(season_year or now().year)`).

  The rewrite must NOT state "no fallback" in the absolute — the current-year fallback
  is preserved. Per Technical Notes TN-8 / TN-4.
- [ ] **AC-2**: The "Canonical-Function Additive Extension Pattern" section (≈L28-30)
  is TRIMMED — the `derive_season_id_for_team_with_fallback` / `SeasonDerivation`
  worked example is removed, the surviving `ensure_team_row_with_provenance` /
  `EnsureTeamResult` example is kept, and the pattern guidance itself stays intact.
- [ ] **AC-3**: The "Filesystem vs DB Season_id Decoupling" section (≈L40-42) is
  REVISED (not retired) to the post-epic reality per the content target + stale-phrasing
  fixes in Notes (arch D2 confirm, 2026-06-20). The decoupling is a SURVIVING live
  invariant, but NOT "crawler writes compound, DB writes year-only" — post-06 the
  crawler writes year-only directories too. The real invariant: the DB `season_id` is
  derived from TEAM METADATA and is NEVER parsed from the directory name (loaders glob
  the season path component as an opaque `*`), so a legacy compound on-disk tree and the
  year-only DB rows MAY DIFFER — that divergence IS the decoupling. Do NOT retire the
  section (it carries a live rule a loader could violate).
- [ ] **AC-4**: `CLAUDE.md` is left byte-untouched for the "Season_id derivation"
  and "Canonical season-aggregate recompute" entries (the tuple return shape is
  unchanged, so the wording stands), and `.claude/rules/data-model.md` is left
  byte-untouched. Both are out of scope — do NOT edit them. (Pre-confirmed: arch
  recon 2026-06-20 verified data-model.md has no `season_fallback` enumeration; its
  only two `report_generation_runs` mentions, L59-62, sit inside the
  `scheduled_report_runs` (migration 005) entry by contrast only — the
  CASCADE-vs-SET-NULL mirror — not a schema/column block, so the migration-006 drop
  does not touch it.) Per Technical Notes TN-8.

## Technical Approach
Edit `.claude/rules/architecture-subsystems.md` per Technical Notes TN-8 — it is the
ONLY file this story modifies. `CLAUDE.md` and `.claude/rules/data-model.md` are
verify-only and confirmed out of scope (the E-238-02 naive-grep-trap lesson — do not
edit them by reflex).

## Dependencies
- **Blocked by**: E-241-06
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/architecture-subsystems.md`
<!-- data-model.md and CLAUDE.md are deliberately NOT listed — verify-only, confirmed
     byte-untouched by arch recon 2026-06-20 (TN-8 / AC-4). -->

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Routed to claude-architect because the modified file is a context-layer rule
(`.claude/rules/**`), per the routing precedence in `.claude/rules/agent-routing.md`.

**D2 (codex iter-2) — arch-confirmed REVISE-only + content target (2026-06-20).**
Correction to the earlier "filesystem stays compound" read: 06 collapses BOTH producers
to year-only — a single `_derive_season_id` value (`scouting.py:180`) names BOTH the
on-disk `data/raw/{season_id}/scouting/...` directory AND the DB writes, so NEW scouting
output writes a year-only directory too. The decoupling survives for a STRONGER reason:
the DB `season_id` is derived from team metadata, never parsed from the directory name;
loaders glob the season path component as an opaque literal (`*`). Proven live:
`scouting_spray_loader.py:334-335` ("Derive DB season_id from team metadata (not the
filesystem path)" → `derive_season_id_for_team`), `:133` (`season_glob = season_id if not
None else "*"`), and `test_scouting_spray_loader.py:707`
`test_season_id_derived_from_team_metadata` (DB `2025` vs crawl-dir `2025-spring-hs`).

REVISED-CONTENT TARGET for the section (arch rewrites from this at dispatch):
1. The `data/raw/{season}/...` directory slug is an OPAQUE organizational name; loaders
   glob it as a literal and never parse the DB `season_id` from it.
2. The DB `season_id` is derived independently from team metadata via
   `derive_season_id_for_team`, now YEAR-ONLY.
3. The two are separately produced and MAY DIFFER — a LEGACY on-disk tree may carry a
   compound `2025-spring-hs` directory while loaded DB rows are year-only `2025`. That
   divergence is the decoupling, and it is WHY a loader must never infer the DB
   `season_id` from the path.

THREE stale phrasings in the CURRENT section the rewrite MUST fix (all false post-06):
- The "data live in `data/raw/2026-spring-hs/` but tagged `2025-summer-usssa` in DB"
  example uses the now-deleted program-type taxonomy → replace with a year-only-DB example.
- "`scouting_runs.season_id` ... does NOT necessarily match the DB season_id" → post-06
  the crawler writes `scouting_runs.season_id` year-only AND loaders write game/player rows
  year-only, so for the scouting path they now DO match → correct or drop that caveat.
- "Crawlers write to filesystem paths (derived from crawl config)" → post-06 the scouting
  crawler derives its dir from `_derive_season_id` (year-only), not a separate crawl-config
  suffix → reword.

This is claude-architect's own section (it self-corrected its earlier OBS-2 retireable
read) and it does the rewrite at dispatch.
