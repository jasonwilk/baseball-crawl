# E-271-01: implement-skill hardening — task-state completion, finding-routing, closure-evidence ref, independent-review mode

## Epic
[E-271: Workflow / Process Redesign](../E-271-workflow-process-redesign/epic.md)

## Status
`TODO`

## Description
After this story is complete, `.claude/skills/implement/SKILL.md` will make task state the completion source of truth, route pre-classified findings without adjudicating code the main session cannot read, reference the new Closure Evidence block, and run a two-mode closure review that spawns a fresh independent no-continuity reviewer for destructive-path epics. This is the skill-side half of items 1, 3, 5, and 7; the code-reviewer-side halves land in E-271-02.

## Context
This story owns the ONLY edits to `.claude/skills/implement/SKILL.md` for this epic (file-ownership clustering, epic TN-1). It pairs with E-271-02 (code-reviewer.md), which reconciles to the orchestration finalized here — hence E-271-02 is blocked-by this story. See epic Technical Notes TN-2 (item 1 skill side), TN-4 (item 3), TN-6 (item 5 ref), TN-8 (item 7 Step 1c two-mode).

## Acceptance Criteria
- [ ] **AC-1** (item 1, TN-2): The Phase 3 completion instruction (~Step 4) directs the implementer to run `TaskUpdate` marking its story task done BEFORE sending the completion report; Step 5 directs the orchestrator to confirm completion by polling task state (`TaskList`/`TaskGet`), NOT by inferring from message arrival. Single-sourced in the spawn/completion template (no per-agent-definition edits). Cites P-6.
- [ ] **AC-2** (item 3, TN-4): The finding-validity adjudication of EXTERNAL (Codex) findings is relocated so the main session only ROUTES — valid → implementer, invalid → dismiss with the code-reviewer's code-grounded reason — and no longer adjudicates validity itself (which would require reading source the dispatch-pattern bars it from). Per TN-4, this covers BOTH occurrences in `implement/SKILL.md`: the Phase 3 Step 5 item 3 DEFINITION (~:278-284) AND the Phase 4 Step 3 item 2 Codex-code-review triage (~:363). The :278-284 rewrite REMAINS the single shared DEFINITION covering BOTH per-story-routing (route what the CR emits) AND external-adjudication-routing (route the CR's valid/invalid tag on Codex findings) — it must NOT collapse to pure per-story routing, or the passes that point at it would dangle (CR S-1). Because that definition is referenced by the phrase "same triage rules as Phase 3 Step 5 item 3", the implementer MUST GREP that phrase across the file and reconcile every referencing pass — the TN-4 line list (Step 1a/1b/1c/1d) is ILLUSTRATIVE and omits sites (CR found ~:460/:634); trust the grep, not the list. The TN-4(a) distinction is preserved (per-story CR findings are valid by construction → routed; only external-finding validity is adjudicated) and TN-4(b) is respected (the plan-skill spec-review triage is NOT touched — that's PM-readable, not the defect). The "every finding reaches FIXED or DISMISSED; no deferral path" invariant is preserved. Cites P-7. Coheres with E-271-02 AC-1.
- [ ] **AC-3** (item 5, TN-6): The Step 2 scorecard area (~:530) carries a ONE-LINE reference — "PM records the Closure Evidence block per the epic template" — and does NOT duplicate the schema (which lives in the template, E-271-03). Cites P-4/P-5.
- [ ] **AC-4** (item 7, TN-8): Step 1c (Closure CR Integration Review) is rewritten into TWO modes gated on the epic's `Destructive-Path` Technical-Notes field (read as the exact literal `Destructive-Path: yes`/`no` per TN-8(a)): `yes` → spawn a FRESH `code-reviewer-independent` instance (that reviewed no story in this epic) with the withheld-rationale + adversarial-charge assignment per TN-8(b), REPLACING the dispatch reviewer for THIS pass; `no` → today's integration review, unchanged. The `yes` mode's assignment explicitly withholds the Technical-Notes safety prose, the story why-correct manifest, and the accumulated finding lists, and includes the adversarial-falsification charge verbatim per TN-8(b). Per TN-8(c): the independent mode SUBSUMES both of Step 1c's conditional obligations by name — the doc-sweep auto-load for context-layer epics and the surface-removal repo-wide grep for route/symbol deletions — plus the cross-story naming/import sweep; and the fresh instance runs Step 1c ONLY (Steps 1a/1b/1d stay with the dispatch reviewer, being mechanical execution passes). The rewrite PRESERVES the slot NAME "Closure CR Integration Review" for BOTH modes, so the live external reference in `.claude/rules/doc-sweep.md:19` (which names that slot as a trigger context) stays valid WITHOUT editing it (claude-architect F1). Cites P-1. Coheres with E-271-02 AC-3.
- [ ] **AC-5** (observable form, Codex P2-3): outside the item-1/3/5/7 edits, the named invariant regions are UNCHANGED — the circuit breaker, the staging boundary, the Full-Suite-Green closure gate, the worktree-guard interaction, and all three COMPLETED-on-disk-vs-committed restatements (~:462/:529/:630) are byte-identical to their pre-edit text (verify by diffing those regions: only the intended item-1/3/5/7 changes appear). The COMPLETED-dance consolidation offset is DECLINED per epic TN-10 — those three restatements MUST remain intact and uncompressed in this story.

## Technical Approach
Edit `.claude/skills/implement/SKILL.md` only, per the designs in epic Technical Notes TN-2 (skill side), TN-4, TN-6, TN-8. All four are text edits to existing Phase 3 / Phase 5 / Step-1c prose; no new file. For AC-4, the two-mode Step 1c reads the `Destructive-Path` field (a permitted-artifact read, added to the template by E-271-03) and, in the `yes` branch, assembles the independent reviewer's assignment from the withheld-rationale payload defined in TN-8(b). Keep the skill's existing section numbering coherent. Do not touch `dispatch-pattern.md` (TN-4: its principle already supports the relocation; only the skill's contradictory instruction changes). This is a context-layer file → claude-architect per the Routing Precedence rule.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-271-02 (its CR-side halves of items 3 and 7 reconcile to this story's finalized orchestration)
- **No 01↔03 edge (deliberate, Codex P2-1):** this story CONSUMES the `Destructive-Path: yes|no` literal that E-271-03 defines in the template. That coupling is on the PINNED LITERAL (TN-8(a)), not on 03's execution output — 01 needs the exact literal from TN-8(a), which AC-4 quotes verbatim — so there is NO 01-blocked-by-03 edge (it would over-serialize a pinned token; identical literal + closure verification make producer/consumer drift structurally impossible).

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md` (modify — items 1b/1c, 3, 5-ref, 7 Step-1c two-mode)

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-271-02**: the finalized finding-routing contract (Step 5 item 3) and the Step-1c two-mode independent-review orchestration. E-271-02's CR-side classification format and independent-review mode must match this story's routing and assignment shape.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Context-layer story (claude-architect). Every AC cites its P-finding (meta-freeze). Item 7's `code-reviewer-independent` is a freshly-spawned INSTANCE of the existing code-reviewer, NOT a new agent definition (epic Non-Goals).
