# E-271-03: disjoint-file cluster — send-cap warn-only, Autonomy Gate, template Closure-Evidence + Destructive-Path field, Codex 1-round default

## Epic
[E-271: Workflow / Process Redesign](../E-271-workflow-process-redesign/epic.md)

## Status
`TODO`

## Description
After this story is complete: the SendMessage hook warns but never denies; `workflow-discipline.md` carries a decide-first Autonomy Gate; the epic template carries a required Closure Evidence block and a `Destructive-Path` Technical-Notes field; and the plan skill defaults to one Codex spec-review round. Four disjoint files, none shared with E-271-01 or E-271-02.

## Context
This story owns four files that no other story in the epic touches (file-ownership clustering, epic TN-1), so it carries no inter-story dependency. See epic Technical Notes TN-2 (item 1a hook), TN-3 (item 2 Autonomy Gate), TN-6 (item 5 template schema), TN-7 (item 6 Codex round), TN-8(a) (item 7 template field).

## Acceptance Criteria
- [ ] **AC-1** (item 1a, TN-2): In `.claude/hooks/send-message-counter.sh`, the warn-only conversion SWEEPS every DENY reference in the file, not a fixed line list (deletion-side reference sweep, per AC-7): the DENY branch (`if NEW >= DENY_AT` block, ~:66-85), the `DENY_AT=25` constant (~:31), the THRESHOLD PROVENANCE comment block that documents `DENY_AT` (~:21-24), the fail-open comment describing the denial JSON path (~:28), the header comment (~:11-12, "warn at 15, deny at 25"), and the warn message text (~:91, drop "of $DENY_AT") are all removed or reconciled to warn-only — so no comment documents a deleted constant or a nonexistent denial path (CR M-1). `WARN_AT=15` and the advisory warn (~:89-99) are KEPT; the Bash staging-boundary logging and counter reset are KEPT. `settings.json` is NOT changed (the hook stays registered). A SendMessage can never be denied by the counter. Cites P-6.
- [ ] **AC-2** (item 2, TN-3): `.claude/rules/workflow-discipline.md` gains an Autonomy Gate subsection enumerating what the main session MUST decide itself from permitted artifacts (routing, story sequencing/next-eligible, whether a declared trigger fired from a permitted-artifact FIELD read, staging-boundary mechanics), the decide-first test verbatim per TN-3, and the named escalation round-trip cost. Per the TN-3 permitted-artifact boundary (Codex P1-1): the decide-first list contains ONLY field/planning-artifact reads (e.g. the `Destructive-Path` token) — NOT diff/grep/code inspection, which is routed to the code-reviewer — so the gate itself does not recreate the orchestrator-adjudicates-code contradiction the epic deletes; and the subsection states this is the same line item 7 draws. The subsection explicitly scopes the Autonomy Gate as COMPLEMENTARY to the existing Dispatch Failure Protocol (decisions-from-permitted-artifacts vs genuine-failures) so the two do not read as contradictory. Cites P-7/P-9 and the DECISION-RULE half of P-10 (over-escalation). Per TN-3, P-10's "main session has no durable record surface" half is explicitly OUT of scope here (the Autonomy Gate gives the over-escalation behavior a decision rule; it does NOT create a record surface) — that half is captured as an idea, so the P-10 citation is not read as full closure (CR S-2).
- [ ] **AC-3** (item 5, TN-6): `.project/templates/epic-template.md` gains a required **Closure Evidence** block in the History schema: verbatim pytest summary line + exact command; smoke scope INCLUDING what it did NOT exercise; ratchet exit code + per-subtree deltas from the canonical `context-ratchet.sh` (no hand-derived figures). This is the single source for the schema (E-271-01 only references it). Cites P-4/P-5.
- [ ] **AC-3b** (item 4 artifact, TN-5 / Codex P1-2): `.project/templates/epic-template.md` ALSO gains — in the History schema, alongside Closure Evidence — a distinct **Annotation Exceptions** sub-block format: one entry per accepted destructive-path annotation, each naming the annotation location + why a discriminating test is genuinely infeasible + PM sign-off. This is the SINGLE SOURCE for that artifact shape (TN-5 and E-271-02 AC-2 reference it, do not redefine it); it is a distinct sub-block, NOT a Review-Scorecard row (different grain — per-finding justification vs. per-pass counts), and CONSPICUOUS by design. Cites P-2.
- [ ] **AC-4** (item 7, TN-8(a)): `.project/templates/epic-template.md` gains a required `Destructive-Path` field in the Technical Notes section — spelled as the exact top-level literal `Destructive-Path: yes` or `Destructive-Path: no` (the token E-271-01's Step-1c read consumes deterministically, per TN-8(a)) — with a one-line explanation that planning declares it and it gates the Step-1c closure-review mode. Cites P-1.
- [ ] **AC-5** (item 6, TN-7): `.claude/skills/plan/SKILL.md` Phase 4 Step 7 is RESTRUCTURED (not merely a `>=2` deletion, per TN-7): the `codex_review_iteration >= 2` circuit-breaker branch (~:449-460), the increment/reset logic (~:446, :459), and the iteration tracking (~:357) are removed, AND the surviving `<2` branch is rewritten so that after ONE round advance-to-READY is the DEFAULT path and re-run is an explicit operator OPT-IN (not the current co-equal "offer re-run vs proceed"). The restructure SWEEPS every description of the automatic second iteration across the whole file (deletion-side reference sweep, per AC-7), not just Step 7: the Edge Cases circuit-breaker summary (~:741-743), the ASCII flow diagram's Phase-4 loop-back arrow (~:670-676), and the Phase-5 planning scorecard row labels (~:483-489, "Codex iteration 1/2" vocabulary) are all reconciled to "one round default + explicit opt-in re-run" so nothing implies an automatic loop (CR M-2 + claude-architect F5). The result is one Codex spec-review round by default; the operator opt-in is a user-choice, NOT an automatic loop. Cites P-1/P-8.
- [ ] **AC-6** (observable form, Codex P2-3): each of the four files is edited independently; no edit depends on E-271-01 or E-271-02 (disjoint cluster). Verify by diff that behavior outside the ACs is unchanged: the hook still logs staging-boundary rows and resets the counter (only the DENY surface removed); the plan skill's Phase 3 is byte-identical and its Phase 5 change is ONLY the AC-5 scorecard-label reconciliation; `workflow-discipline.md`'s existing sections and the template's other sections are byte-identical outside the new additions.
- [ ] **AC-7** (deletion-side reference sweep — dogfoods this epic's own discipline): for EACH edited file, before closing the story, grep the file for every token this story deletes or renames (e.g. `DENY` / `DENY_AT` / "denial" / "deny" in the hook; the 2-round / "iteration 2" / circuit-breaker vocabulary in the plan skill) and reconcile ALL references, not only the enumerated regions — so no comment, summary, diagram, or scorecard label documents a deleted construct. This is the general form CR recommended; AC-1 and AC-5 are its two concrete instances, and it immunizes the `workflow-discipline.md` and `epic-template.md` edits against the same gap.

## Technical Approach
Four independent edits per the designs in epic Technical Notes TN-2 (1a), TN-3 (item 2), TN-6 (item 5), TN-7 (item 6), TN-8(a) (item 7 field). AC-1 is a ~22-line clean deletion in the hook (keep the WARN path and the Bash staging-boundary logging intact). AC-2 adds a rule subsection and MUST state the Dispatch-Failure-Protocol boundary. AC-3/AC-4 are template additions. AC-5 is a ~15-20 line deletion in the plan skill (preserve the operator opt-in). All four are context-layer files → claude-architect per the Routing Precedence rule. No `settings.json` change (AC-1).

## Dependencies
- **Blocked by**: None
- **Blocks**: None
- **No 01↔03 edge (deliberate, Codex P2-1):** this story PRODUCES the `Destructive-Path: yes|no` template field (AC-4) that E-271-01 consumes. The coupling is on the PINNED LITERAL (TN-8(a)), not on this story's execution output, so no dependency edge is warranted (would over-serialize a pinned token); AC-4 quotes the exact same literal E-271-01 AC-4 reads, making producer/consumer drift structurally impossible, and the closure review verifies coherence.

## Files to Create or Modify
- `.claude/hooks/send-message-counter.sh` (modify — drop DENY branch + constant, keep WARN)
- `.claude/rules/workflow-discipline.md` (modify — add Autonomy Gate subsection)
- `.project/templates/epic-template.md` (modify — Closure Evidence block + Destructive-Path field)
- `.claude/skills/plan/SKILL.md` (modify — Phase 4 one-round default)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Context-layer story (claude-architect). Every AC cites its P-finding (meta-freeze). The four files are disjoint from E-271-01/02, so this story can run in any order relative to them.
