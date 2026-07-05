# E-250-04: Context-layer prose de-scope

## Epic
[E-250: Root-Level Cross-Season / Multi-Season De-Scope](../E-250-cross-season-descope/epic.md)

## Status
`DONE`

## Description
After this story is complete, no context-layer file (CLAUDE.md, rules, agent definitions) frames the project as supporting multi-season rollups, longitudinal tracking, or cross-team athlete identity as a live capability, and no reference to the non-existent `PlayerTeamSeason` table remains. The `bb data dedup-players` command sentence and the E-249 known-limitation note are updated to reflect the single-season-scoped behavior shipped in E-250-01/E-250-02.

## Context
Stale multi-season prose in the context layer is not cosmetic: it is loaded into every agent's context and acts as a hallucination anchor (the `PlayerTeamSeason` table named in `data-engineer.md` does not exist and never has). This story excises the cross-season/longitudinal framing and aligns the command/known-limitation prose with the de-scoped reality. Per the domain-expert-designs convention (Technical Notes TN-7), claude-architect owns the exact wording; this story frames grep-verifiable outcomes and names the files.

## Acceptance Criteria
- [ ] **AC-1**: `CLAUDE.md` — the multi-season scope bullet (vetting pass cited ~L27; CA inventory has the current line) is corrected to state the single-season reality (no multi-season tracking); and the `bb data dedup-players` command sentence reflects that `season_id` is now derived/required (per E-250-01). BOUNDARY (CA Flag A resolution): trimming this CLAUDE.md bullet is authorized (it is in the user-approved scope brief). `docs/VISION.md` and `docs/vision-signals.md` are explicitly OUT of this story — they are curation-governed (PM stewardship, a separate "curate the vision" session) and MUST NOT be edited here.
- [ ] **AC-2**: `.claude/rules/data-model.md` — the E-249 known-limitation bullet is replaced with a single-season-scoped statement (no unscoped cross-season execute path remains), and the "awaits E-104" note (vetting pass cited ~L32) is reworded to reflect that the identity anchor is dropped (E-250-02) and E-104 is abandoned (E-250-07).
- [ ] **AC-3**: `.claude/rules/key-metrics.md` — the "Longitudinal" framing (vetting pass cited ~L25) is corrected or removed so no metric is described as longitudinal/cross-season.
- [ ] **AC-4**: `.claude/agents/baseball-coach.md` — cross-season identity / longitudinal framing is excised so the agent's domain no longer describes cross-season DATA-USAGE as in-scope. In scope: ~L34/57 and the L83-90 "relevance decay framework" + "pull-based history" prior-season-data-usage prose (CA's sweep caught L83-90 beyond the initial ~L34/57). KEEP (do NOT excise): L81 "Each season is a fresh start" and L32 "Seasons are sequential" — these are the fresh-start philosophy and accurate single-season domain, not cross-season data-usage claims. Excise only the cross-season DATA-USAGE, not the fresh-start framing.
- [ ] **AC-5**: `.claude/agents/data-engineer.md` — cross-season identity framing AND every reference to the NON-EXISTENT `PlayerTeamSeason` table (vetting pass cited ~L39/67/111; CA inventory has current lines) are removed; a grep for `PlayerTeamSeason` across the context layer returns zero hits. SCOPE BOUNDARY (CA Flag B resolution): remove ONLY the cross-season / `PlayerTeamSeason` cells that are in scope. The DE Core Entities table is broadly stale beyond these cells (other rows also mismatch the live schema), but a full agent-def rewrite is OUT of scope for E-250 — that broader cleanup is captured as a separate idea (IDEA-092). Do not let this story sprawl into a table rewrite.
- [ ] **AC-6**: A grep across the context layer (CLAUDE.md, `.claude/rules/**`, `.claude/agents/**`) for multi-season/longitudinal/cross-season-identity framing surfaces no remaining statement that presents those as live capabilities (single-season partition mentions of `season_id`, and the deliberate KEEP items in the epic, are expected and correct).
- [ ] **AC-7**: (grep-verifiable) `.claude/rules/architecture-subsystems.md`'s description of `is_team_eligible_for_cleanup`'s guards is corrected to the post-E-250-02 guard set — TWO surviving guards: Guard 1 (`is_active = 0`) and Guard 2 (no OTHER report references the team). This matches E-250-02 AC-7's code-side renumbering (the old Guard 3 becomes Guard 2 once Guards 2 and 4 are removed) — the prose and the code docstring MUST use the same 1-2 numbering (Codex #7). SE flagged the current prose ("not member, not tracked opponent, no public_id, no gc_uuid") as MIS-describing the guards, stale versus the actual code even before this epic. A grep for the stale guard phrasing returns none.
- [ ] **AC-8**: (grep-verifiable) `team_opponents` no longer appears as a live schema element in the context layer: `.claude/rules/data-model.md:20`'s `team_opponents` entry and the Cleanup-Detection-Mirror-Invariant references are removed/corrected to reflect the dropped table. A grep for `team_opponents` across `.claude/rules/**` returns no statement presenting it as a present table.
- [ ] **AC-9**: (grep-verifiable) `seasons.season_type` is no longer framed as a live column in the context layer: `.claude/rules/architecture-subsystems.md:38`'s `season_type` parenthetical is corrected to reflect the dropped column. Additionally, `.claude/rules/data-model.md:105`'s E-241 "two writers must agree on `season_type`" lesson is REFRAMED as historical — the general multi-writer-agreement principle SURVIVES (do not delete it), but the `season_type` instance is moot post-drop (CA soft catch). A grep for a live-column `season_type` reference across `.claude/rules/**` returns none.

## Technical Approach
The self-contained authoritative spec for this story is the AC set itself (AC-1 through AC-9): each AC names its target file concretely (`CLAUDE.md`, `.claude/rules/data-model.md`, `.claude/rules/key-metrics.md`, `.claude/rules/architecture-subsystems.md`, `.claude/agents/baseball-coach.md`, `.claude/agents/data-engineer.md`) plus the specific stale content to remove and a grep-verifiable outcome — no external artifact is required to execute the story (Codex #1: the ACs do not depend on an unloadable inventory). The vetting-pass line numbers cited in the ACs are indicative and may have drifted; claude-architect (which owns these files) locates the current occurrences at implementation and the grep-verifiable checks confirm completeness. The single-season KEEP surface (`season_id` as partition key, `derive_season_id_for_team` year-only, `canonical_recompute` per-scope) must be left intact — this story removes cross-season *framing*, not single-season partition prose. Respect the two boundary resolutions: VISION.md/vision-signals.md OUT (AC-1), DE Core Entities table trimmed to cross-season/`PlayerTeamSeason` cells only, not rewritten (AC-5).

## Dependencies
- **Blocked by**: E-250-01 (dedup command behavior to describe), E-250-02 (schema removals + E-104 anchor drop to describe), E-250-07 (AC-2 prose asserts E-104 IS abandoned — that archive must happen first; Codex #3)
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md`
- `.claude/rules/data-model.md` (E-249 known-limitation bullet + "awaits E-104" note; `team_opponents` entry at ~:20 + Cleanup-Detection-Mirror-Invariant refs; the two-writers-`season_type` lesson at ~:105 reframed as historical)
- `.claude/rules/key-metrics.md`
- `.claude/rules/architecture-subsystems.md` (correct the stale `is_team_eligible_for_cleanup` guard description; correct the `season_type='default'` parenthetical at ~:38)
- `.claude/agents/baseball-coach.md` (excise cross-season data-usage incl. L83-90; KEEP L81 fresh-start + L32 sequential)
- `.claude/agents/data-engineer.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Routes to claude-architect per the context-layer routing rule (any story touching CLAUDE.md / `.claude/**` is CA's). Consolidates every context-layer prose edit the brief distributed across its stories 1, 2, and 5 into one CA-owned story, avoiding same-file cross-story conflicts. See epic TN-7.
