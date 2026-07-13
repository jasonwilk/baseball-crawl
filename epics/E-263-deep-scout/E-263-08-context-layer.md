# E-263-08: Context layer — catalog activation + scouting-ethics rule + subsystem/command docs

## Epic
[E-263: Deep Scout v1 — Opponent-Intelligence Report Sections](epic.md)

## Status
`TODO`

## Description
After this story is complete, the context layer reflects the shipped Deep Scout v1: the signal catalog is activated with updated validation statuses, the new command surface and fact-sheet/synthesis subsystem are documented, and the minors-safety ethics split is codified as a durable agent-binding rule. This is the claude-architect-owned closure of the epic's context-layer footprint (design owned by CA; ACs framed here per the context-layer-epic convention).

## Context
claude-architect authored the catalog structure and the Discovery-Pass method and confirmed the shape of this story during consultation. Key decisions carried into the ACs: the living catalog STAYS in `.project/research/` (it is a growing superset — the discovery pass keeps adding entries; `docs/` implies committed stability and would fight that); the product-reference coaching doc is a SEPARATE docs-writer artifact (E-263-09), not this story; the discovery pass stays a documented method, NOT a new `.claude/` skill/rule in v1 (Simple First). The fact-sheet schema is code-canonical (E-263-02a) and this story adds only a POINTER to it, per the E-257 `recon_scoreboard.py` precedent. The ethics split (Technical Notes TN-8) is a hard safety invariant about materials describing minors — the durable, agent-binding rule class that belongs in `.claude/rules/`, analogous to `pii-safety.md`.

## Acceptance Criteria
- [ ] **AC-1**: `.project/research/scouting-signal-catalog.md` is flipped from DRAFT to active; the `Validation status` of each signal E-263 actually shipped is updated (e.g. `computed` → `validated-live` ONLY where a signal was graded against a finished game during the epic — shipping a signal into a report is NOT grading it, so a build epic may leave most entries at their prior status while marking v1-built ones active); every catalog entry NOT built in v1 (incl. SIG-022..028) is marked "deferred to v2"; the SIG-004 entry's Computation + `Fact-sheet key` are updated to include swinging-strike/whiff% (per Technical Notes TN-4); and the catalog's "Connection to E-263" section is reconciled to reflect that IDEA-131 now exists and the epic shipped (CA-F3). The catalog is NOT moved to `docs/`.
- [ ] **AC-2**: A new `.claude/rules/scouting-ethics.md` codifies the ethics split per Technical Notes TN-8 as a durable agent-binding invariant: coach-facing = full names/full data; player-facing = team-tendency/number only, never a named opposing minor next to a weakness; the steal light (named opposing catcher) is coach-facing only; SIG-007 alignment is the one number-only player-safe carve-out. It reads as a safety rule (analogous to `.claude/rules/pii-safety.md`), not a restatement of an AC.
- [ ] **AC-3**: `CLAUDE.md` Commands section documents that `bb report generate` now emits the Deep Scout sections (v1 adds NO new flags — it is opponent-only; the `--vs`/`--date` matchup seam is a v2 item per the epic), consistent with what actually shipped.
- [ ] **AC-4**: `.claude/rules/architecture-subsystems.md` gains a Deep Scout subsystem note covering the fact-sheet builder + deterministic section synthesis, and a code-canonical POINTER to the fact-sheet schema module (naming the `src/reports/deep_scout/` schema file per the E-257 precedent — code is canonical, the note mirrors), plus a pointer that the catalog's `Fact-sheet key` column mirrors the code contract.
- [ ] **AC-5**: The context-layer additions are internally consistent — the command surface documented in CLAUDE.md, the schema path in the subsystem note, and the catalog's fact-sheet keys all agree with what E-263-02a/02b/04/05/06/07 actually shipped (a consistency sweep, not a from-memory description).

## Technical Approach
claude-architect designs the exact wording and placement (per the context-layer-epic convention: CA leads design in their domain, PM frames ACs). Read the shipped modules (`src/reports/deep_scout/`), the shipped command surface (v1 is opponent-only, no new flags — from E-263-02a), and the design doctrine (`.project/research/deep-scout-design-2026-07-12.md` §5 ethics, §6 fact-sheet). Model the new `scouting-ethics.md` on the existing safety-rule shape (`.claude/rules/pii-safety.md`). Verify against the actual shipped code, not the plan — the schema filename is whatever E-263-02a landed.

## Dependencies
- **Blocked by**: E-263-04, E-263-05, E-263-06, E-263-07 (the shipped signals + command surface the catalog/docs describe)
- **Blocks**: None

## Files to Create or Modify
- `.project/research/scouting-signal-catalog.md` (modify — DRAFT→active, validation-status update, v2 deferrals)
- `.claude/rules/scouting-ethics.md` (new — minors-safety ethics-split invariant)
- `CLAUDE.md` (modify — Commands section, Deep Scout surface)
- `.claude/rules/architecture-subsystems.md` (modify — Deep Scout subsystem note + code-canonical schema pointer)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Context-layer additions verified against the shipped code (not the plan)
- [ ] Consistency sweep across CLAUDE.md / subsystem note / catalog keys
- [ ] No regressions in existing tests

## Notes
Routes to claude-architect (context-layer paths: `.claude/rules/**`, `CLAUDE.md`, `.project/research/` catalog). The ethics rule is the highest-value durable output — it graduates a per-epic AC into a standing safety invariant covering minors, so future scouting work inherits it without re-litigation.
