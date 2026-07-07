# E-255-03: Agent charter corrections + §3 curation-decision codification

## Epic
[E-255: Truth Sweep — Context Layer, API Docs, Runbooks](epic.md)

## Status
`TODO`

## Description
After this story is complete, the agent charters (`ux-designer`, `docs-writer`, `product-manager`, `baseball-coach`, `data-engineer`) describe current responsibilities against surviving surfaces, and the three Jason-approved §3 curation decisions (agent-roster refocus, context-growth counterweight, memory-lifecycle policy) are codified in the context layer.

## Context
Third claude-architect cluster: agent definitions plus `.claude/rules/context-layer-assessment.md`. File-disjoint from E-255-01/02 (TN-3). The ux-designer repurpose-or-retire question — flagged in the audit as a user decision — is DECIDED (refocus both ux-designer and docs-writer, retire neither; 2026-07-05 curation). The source text for all three §3 codifications is `.claude/agent-memory/product-manager/project_ce5_curation_handoff.md`; CA codifies the recorded rationale, does not re-decide (TN-4, Non-Goals).

## Acceptance Criteria
- [ ] **AC-1** (ux decision RESOLVED 2026-07-07: REPURPOSE): Given the ux-designer charter still framed around the deleted coaching dashboard, when refocused, then `.claude/agents/ux-designer.md` describes report-layout / trust-surface / tools-hub IA work as the agent's forward docket (not dashboard UI), and the agent is NOT marked retired (matches VISION D4). This decided form is the charter E-255-09 aligns its memory rewrite to.
- [ ] **AC-2**: Given the docs-writer charter's dashboard framing, when refocused, then `.claude/agents/docs-writer.md` describes admin runbooks + coaching how-tos for reports and morning-run as its docket (not dashboard docs).
- [ ] **AC-3**: Given the PM charter's stale wording (audit: `Task-tool` / `D1 migrations` phrasing), the coach charter's USSSA persona line, and the data-engineer charter's Core Entities pointer, when re-verified and corrected, then each reflects current reality — and the data-engineer.md Core Entities correction is limited to the cross-season/ghost pointer-replacement (naming only real tables, never the ghost `Lineup`/`PlateAppearance`/`PitchingAppearance`), consistent with DE memory (E-255-08) and coach memory (E-255-07) per epic TN-7. The broader table refresh is IDEA-092, out of scope per Non-Goals; flag any residual charter-vs-memory divergence to PM at closure.
- [ ] **AC-4**: Given §3 decision #2 (one-directional context-layer growth), when codified per the handoff source text, then `.claude/rules/context-layer-assessment.md` carries a closure-assessment counterweight (a review prompt asking what was compressed or retired to offset net growth) — NOT a hard line-count cap.
- [ ] **AC-4b** (trigger-count propagation — Codex iter-3): Given the counterweight may be added as a numbered "trigger 7" (CA's design call), when codified, then NO context-layer file is left with a stale trigger count. If added as trigger-7, the THREE live "six triggers"/"all six" references are all updated to seven — `.claude/rules/context-layer-assessment.md:26`, `.claude/rules/workflow-discipline.md:90`, `.claude/agents/product-manager.md:158`; if added as a separate (non-numbered) review prompt, the six-trigger count legitimately stays. Testable: a grep for `six trigger`/`all six` across the LIVE context layer (excluding `.project/archive/**` + `.claude/agent-memory/product-manager/archived-epics.md`, which are frozen history) shows no reference contradicting the assessment's actual structure. (Enumeration is complete: a PM repo-wide grep found only these three live sites.)
- [ ] **AC-5** (target named — Codex iter-3): Given §3 decision #3 (agent-memory lifecycle), when codified per the handoff source text, then a lightweight lifecycle policy is recorded **in `.claude/rules/context-layer-assessment.md`** (the handoff's stated home — "a short new rule or a section in context-layer-assessment.md"; keep it a section there, simple-first, unless CA judges a dedicated rule warranted): promote-to-rule when cited across 2+ epics or generalizes; strike-on-staleness when the named code/flag/decision is deleted; per-agent review cadence rather than a hard KB cap.
- [ ] **AC-6**: Given the §3 decisions are Jason-approved, when codified, then the codification matches the recorded rationale in the PM curation handoff and does not re-open or alter the decisions.

## Technical Approach
Read `project_ce5_curation_handoff.md` as the source for AC-1/AC-4/AC-5. Read each agent def in full; re-verify per TN-1. Keep the counterweight and lifecycle policy simple-first (review prompt + lightweight policy, no hard caps).

## Dependencies
- **Blocked by**: None (ux repurpose-or-retire decided 2026-07-07: REPURPOSE — AC-1 is unblocked).
- **Blocks**: E-255-09 (ux-designer own-memory rewrite reflects the refocused charter set by AC-1)

## Files to Create or Modify
- `.claude/agents/ux-designer.md`
- `.claude/agents/docs-writer.md`
- `.claude/agents/product-manager.md` (AC-3 charter wording; AC-4b: `:158` "six triggers" → "seven" IF trigger-7 is added)
- `.claude/agents/baseball-coach.md`
- `.claude/agents/data-engineer.md`
- `.claude/rules/context-layer-assessment.md` (AC-4 counterweight + AC-5 lifecycle policy; AC-4b: `:26` "six triggers" → "seven" IF trigger-7 is added)
- `.claude/rules/workflow-discipline.md` (AC-4b ONLY: `:90` "all six triggers" → "seven" IF the counterweight is added as trigger-7; no edit if it's a separate review prompt)

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-255-09**: The refocused ux-designer charter (report-layout/trust-surface/tools-hub) that the ux-designer own-memory rewrite must align to.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] §3 codifications match the Jason-approved handoff rationale
- [ ] No hard line-count/KB caps introduced (simple-first per handoff)
- [ ] Discharged-already items recorded in story notes

## Notes
Source of truth for the three §3 decisions: `.claude/agent-memory/product-manager/project_ce5_curation_handoff.md`. The ~60-day stale-READY re-confirmation rule was considered and Jason decided to SKIP it (2026-07-07) — no CA rule-creation sub-item here.
