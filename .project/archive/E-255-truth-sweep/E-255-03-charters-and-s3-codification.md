# E-255-03: Agent charter corrections + §3 curation-decision codification

## Epic
[E-255: Truth Sweep — Context Layer, API Docs, Runbooks](epic.md)

## Status
`DONE`

## Description
After this story is complete, the agent charters (`ux-designer`, `docs-writer`, `product-manager`, `baseball-coach`, `data-engineer`) describe current responsibilities against surviving surfaces, and the three Jason-approved §3 curation decisions (agent-roster refocus, context-growth counterweight, memory-lifecycle policy) are codified in the context layer.

## Context
Third claude-architect cluster: agent definitions plus `.claude/rules/context-layer-assessment.md`. File-disjoint from E-255-01/02 (TN-3). The ux-designer repurpose-or-retire question — flagged in the audit as a user decision — is DECIDED (refocus both ux-designer and docs-writer, retire neither; 2026-07-05 curation). The source text for all three §3 codifications is `.claude/agent-memory/product-manager/project_ce5_curation_handoff.md`; CA codifies the recorded rationale, does not re-decide (TN-4, Non-Goals).

## Acceptance Criteria
- [ ] **AC-1** (ux decision RESOLVED 2026-07-07: REPURPOSE): Given the ux-designer charter still framed around the deleted coaching dashboard, when refocused, then `.claude/agents/ux-designer.md` describes report-layout / trust-surface / tools-hub IA work as the agent's forward docket (not dashboard UI), and the agent is NOT marked retired (matches VISION D4). This includes the frontmatter `description:` field, which still reads "coaching dashboard" (line 3) — it is refocused to the surviving report/serving surfaces in the same edit. This decided form is the charter E-255-09 aligns its memory rewrite to.
- [ ] **AC-1b** (frontmatter model right-size — AGENTIC-FLOW-REVIEW.md §2.1, ~line 36): Given the ux-designer frontmatter is `model: opus[1m]` / `effort: high` while the agent has 3 lifetime spawns with the shortest prompts and text-wireframe deliverables, when re-verified in the same edit that refocuses the charter (AC-1), then the frontmatter is changed to `model: sonnet` with the `effort` override dropped to default. Same-edit-as-the-scope-fix per §2.1.
- [ ] **AC-1c** (item 15 remainder — model/effort + routing, AGENTIC-FLOW-REVIEW.md §2.1; routed here 2026-07-07 as a scope-add since this story already edits agent frontmatter): Given the two other §2.1 edge misallocations and the routing addendum, when corrected, then (a) `.claude/agents/claude-architect.md` frontmatter `model: opus` → `model: opus[1m]` (it is the heaviest context-layer reader and the only judgment agent without the 1M window; `effort: high` is KEPT); (b) `.claude/agents/api-scout.md` gains an explicit `effort: medium` (it is the only agent with implicit effort — declare it for reproducibility; `model: opus` is KEPT); and (c) `.claude/rules/agent-routing.md` gains a one-line addendum that read-only tracing/diagnosis routes to the built-in `Explore` agent (no new investigator agent — Explore already fits).
- [ ] **AC-2**: Given the docs-writer charter's dashboard framing, when refocused, then `.claude/agents/docs-writer.md` describes admin runbooks + coaching how-tos for reports and morning-run as its docket (not dashboard docs).
- [ ] **AC-3**: Given the PM charter's stale wording (audit: `Task-tool` / `D1 migrations` phrasing), the coach charter's USSSA persona line, and the data-engineer charter's Core Entities pointer, when re-verified and corrected, then each reflects current reality — and the data-engineer.md Core Entities correction is limited to the cross-season/ghost pointer-replacement (naming only real tables, never the ghost `Lineup`/`PlateAppearance`/`PitchingAppearance`), consistent with DE memory (E-255-08) and coach memory (E-255-07) per epic TN-7. The broader table refresh is IDEA-092, out of scope per Non-Goals; flag any residual charter-vs-memory divergence to PM at closure.
- [ ] **AC-4**: Given §3 decision #2 (one-directional context-layer growth), when codified per the handoff source text, then `.claude/rules/context-layer-assessment.md` carries a closure-assessment counterweight (a review prompt asking what was compressed or retired to offset net growth) — NOT a hard line-count cap.
- [ ] **AC-4b** (trigger-count propagation — Codex iter-3; extended 2026-07-07 for the §5.1 behavioral-lesson trigger): Given the AC-4 context-growth counterweight and/or the AC-5 behavioral-lesson closure gate may each be added as a numbered trigger (CA's design call), when codified, then NO context-layer file is left with a stale trigger count. The final count depends on how many of the two candidate triggers CA lands as numbered triggers: six → **seven** if exactly one is numbered, six → **eight** if both are numbered (in which case they are numbered 7 and 8, per AC-5). Whichever the final count, the FIVE live "six triggers"/"all six"/"six verdicts" references are all updated to match (CA design review 2026-07-07 expanded the enumeration from three to five) — `.claude/rules/context-layer-assessment.md:15` ("All six verdicts are recorded"), `.claude/rules/context-layer-assessment.md:26` ("the six triggers above"), `.claude/rules/workflow-discipline.md:90` ("all six triggers"), `.claude/agents/product-manager.md:158`, and `.claude/skills/implement/SKILL.md:483` ("Six triggers, explicit yes/no verdicts"); if a candidate is added as a separate (non-numbered) review prompt rather than a numbered trigger, it does not raise the count. Testable: a grep for `six trigger`/`all six`/`six verdicts` (and `seven`/`eight` variants) across the LIVE context layer (excluding `.project/archive/**` + `.claude/agent-memory/product-manager/archived-epics.md`, which are frozen history) shows no reference contradicting the assessment's actual structure. (Line numbers are approximate and may drift — the grep, not the line number, is authoritative.)
- [ ] **AC-5** (source spec UPGRADED to AGENTIC-FLOW-REVIEW.md §5.1, ~lines 184-192 — 2026-07-07; supersedes the simpler handoff phrasing for the lifecycle policy only): Given §3 decision #3 (agent-memory lifecycle), when codified **in `.claude/rules/context-layer-assessment.md`** (the handoff's stated home; keep it a section there simple-first unless CA judges a dedicated rule warranted), then the promote-to-rule pipeline lands event-driven per §5.1: (a) the always-firing closure gate — a reusable behavioral lesson that RECURRED this epic OR GENERALIZES beyond one agent is promoted to its load target now; this REPLACES the uncountable "cited across 2+ epics" criterion (which had no counter); (b) Load-Target Classification — every codified lesson is typed: universal-behavioral → `paths:"**"` rule / CLAUDE.md; role-scoped → agent def or MEMORY.md top-200; path-scoped rule; workflow skill; reference-only topic file — and only the reference-only type may terminate in a non-auto-loading file (recorded-but-dormant is the default failure the classification prevents); (c) deletion-side eviction — the closure procedure gains "for each file/flag/table this epic DELETED, grep rules/agents/MEMORY.md and strike or annotate references"; (d) memory retirement — PM greps Pending-Work for the archived epic's ID at closure. Per-agent review cadence, not a hard KB cap. NOTE the trigger collision: this behavioral-lesson closure gate (§5.1 item 1) and the AC-4 context-growth counterweight are DISTINCT triggers — if CA lands BOTH as numbered triggers they MUST be numbered 7 and 8 (never collapsed into one); AC-4b governs the count propagation.
- [ ] **AC-5b** (two immediate promotions proving the pipeline — §5.1 item 3): Given the pipeline is being codified, when this story completes, then two high-value behavioral lessons are promoted from non-auto-loading PM topic memory into `.claude/rules/tool-output-integrity.md` (a `paths:"**"` rule, so they load for every agent): (i) the grep-match trap — "never rule on a grep / OR-pattern match; Read and quote the literal line" — is ELEVATED from a cross-reference aside (it currently appears only as a parenthetical inside the Related-discipline paragraph at `.claude/rules/tool-output-integrity.md:36`) to a first-class numbered Prohibition in that file (matching how AC-5b(ii) is framed); (ii) "read reviewer findings to completion before characterizing" is promoted from the Related-discipline aside into a numbered Response-protocol step. Source of the two lessons: `.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md` and `.claude/agent-memory/product-manager/feedback_read_findings_before_triage.md`.
- [ ] **AC-6**: Given the §3 decisions are Jason-approved, when codified, then the codification matches the recorded rationale in the PM curation handoff and does not re-open or alter the decisions.

## Technical Approach
Read `project_ce5_curation_handoff.md` as the source for AC-1/AC-4. For the memory-lifecycle policy (AC-5) and the two immediate promotions (AC-5b), the source spec is UPGRADED to `AGENTIC-FLOW-REVIEW.md` §5.1 (~lines 184-192, repo root, uncommitted reference) — read that section as the authoritative spec. Read each agent def in full; re-verify per TN-1. Keep the counterweight and lifecycle policy simple-first (review prompt + lightweight event-driven policy, no hard caps).

## Dependencies
- **Blocked by**: None (ux repurpose-or-retire decided 2026-07-07: REPURPOSE — AC-1 is unblocked).
- **Blocks**: E-255-09 (ux-designer own-memory rewrite reflects the refocused charter set by AC-1)

## Files to Create or Modify
- `.claude/agents/ux-designer.md`
- `.claude/agents/claude-architect.md` (AC-1c: `model: opus` → `opus[1m]`)
- `.claude/agents/api-scout.md` (AC-1c: add explicit `effort: medium`)
- `.claude/rules/agent-routing.md` (AC-1c: one-line Explore-routing addendum)
- `.claude/agents/docs-writer.md`
- `.claude/agents/product-manager.md` (AC-3 charter wording; AC-4b: `:158` count → "seven"/"eight" IF numbered trigger(s) added)
- `.claude/agents/baseball-coach.md`
- `.claude/agents/data-engineer.md`
- `.claude/rules/context-layer-assessment.md` (AC-4 counterweight + AC-5 lifecycle/promote-to-rule pipeline; AC-4b: `:15` + `:26` counts → "seven"/"eight" IF numbered trigger(s) added)
- `.claude/rules/tool-output-integrity.md` (AC-5b: two immediate promotions — grep-match trap into Prohibitions + read-findings-first as a numbered Response-protocol step)
- `.claude/rules/workflow-discipline.md` (AC-4b ONLY: `:90` "all six triggers" → "seven"/"eight" IF numbered trigger(s) added; no edit if separate review prompt)
- `.claude/skills/implement/SKILL.md` (AC-4b ONLY: `:483` "Six triggers" → "seven"/"eight" IF numbered trigger(s) added; no edit if separate review prompt)

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
Source of truth for the three §3 decisions: `.claude/agent-memory/product-manager/project_ce5_curation_handoff.md`. The ~60-day stale-READY re-confirmation rule was initially SKIPped then ADOPTED by Jason (2026-07-07 reversal, after agentic-flow-review §2.2 evidence). Its codification lives in E-255-06 AC-6 (rule text likely in `.claude/rules/workflow-discipline.md` + plan/implement SKILL Prerequisites, routed to claude-architect) — NOT in this story.
