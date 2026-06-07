# E-231-05: Relay-Integrity Rule (No Relay of Unread Content)

## Epic
[E-231: Harness Output-Reliability -- Detect, Defend, and Report](../E-231-harness-output-reliability/epic.md)

## Status
`TODO`

## Description
After this story is complete, `.claude/rules/dispatch-pattern.md` will carry a no-relay-of-unread-content rule: before relaying review findings -- or any tool-derived claim -- the relayer MUST have read the persisted source to completion, and MUST NOT relay content composed from output that was empty, truncated, or garbled. The rule is peer-checkable (a teammate receiving a relay may require the relayer to confirm the read) and is cross-pointed from the two skill triage-relay steps. This closes the orchestrator-relay failure class that no in-skill triage gate or always-loaded assert-unseen prohibition currently covers.

## Context
The worst failure of the E-231 planning session itself was on the **relay path**: the main session composed review findings it had not cleanly read and relayed them as if from Codex -- twice -- mischaracterizing valid findings before the real output had been read to completion. This failure is different in KIND from the two failures the epic already addresses, and lives on a different surface:

- **E-231-03** gates triage INSIDE the two review skills (`codex-review`, `codex-spec-review`) -- it does not cover the plan/implement RELAY path where the orchestrator pastes findings to PM for triage.
- **E-231-01** is the always-loaded general prohibition on asserting unseen content -- it states the principle but is not anchored to the specific relay surface (plan SKILL Phase 4 Step 3; implement SKILL Phase 4b Step 3 / Phase 3 Step 5) where the fabrication happened.

E-231-05 is the relay-surface-specific defend mitigation. The relay actor is the main-session orchestrator, which is structurally barred from file operations and cannot be hook-gated on relays -- so the honest mechanism is **discipline plus peer-checkability**, not a deterministic gate. `.claude/rules/dispatch-pattern.md` is the natural home: it is loaded on `paths: "**"` and already owns the relay channel convention ("main-session relay is the default channel for substantive content" at line 19).

## Acceptance Criteria
- [ ] **AC-1**: A no-relay-of-unread-content rule is added to `.claude/rules/dispatch-pattern.md`: before relaying review findings or any tool-derived claim, the relayer MUST have read the persisted source to completion; content composed from empty, truncated, or garbled output MUST NOT be relayed. Written in imperative MUST-language, not advisory.
- [ ] **AC-2**: The rule is explicitly peer-checkable: a teammate receiving a relay of findings MAY require the relayer to confirm the read (e.g., the persisted-file path plus its line count) before acting on the relayed content.
- [ ] **AC-3**: A one-line cross-pointer to the rule is added at the codex-findings triage relay in `.claude/skills/plan/SKILL.md` Phase 4 Step 3 (the "Route the findings to PM ... [full codex findings]" step), and at the review-finding relay points in `.claude/skills/implement/SKILL.md` Phase 4b Step 3 and Phase 3 Step 5.
- [ ] **AC-4**: The rule references E-231-01's output-integrity taxonomy (empty / truncated / garbled) and the committed PM memory `.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md` rather than restating them inline (per Technical Notes "do not duplicate").
- [ ] **AC-5**: The rule explicitly states it is a discipline aid plus peer-checkable convention, NOT a deterministic gate -- the orchestrator cannot be hook-gated on relays (honesty framing, mirroring E-231-03 AC-1's "not a cryptographic guarantee" admission).
- [ ] **AC-6**: Bloat tripwire -- the change is ONE paragraph in `.claude/rules/dispatch-pattern.md` plus the skill cross-pointers in AC-3 (three insertion points across the two skill files). It MUST NOT introduce a parallel receipt mechanism, a new rule file, or duplicate the E-231-01 taxonomy.

## Technical Approach
This is a context-layer change to one existing rule file and two existing skill files; claude-architect owns rule and skill content. The rule text lives as a single tight paragraph in `.claude/rules/dispatch-pattern.md`, placed near the existing relay-channel convention it extends (line 19 area). The two skills gain one-line cross-pointers at their finding-relay steps so the relayer encounters the rule at the moment it applies. The rule anchors to the committed PM memory `.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md` and to the E-231-01 output-integrity rule for the failure taxonomy -- it must reference, not restate, both. Coordinate with the separate live advisory load-notice line being added to the same file (Addition B): that line concerns serializing agent activity under harness load notices; this rule concerns relay integrity -- they are distinct content and must not be merged.

Context-budget tension (per epic Technical Notes, Context-fundamentals governing constraint, and `.claude/skills/context-fundamentals/SKILL.md`): `dispatch-pattern.md` is `paths: "**"` always-loaded -- the addition must be minimal to justify its permanent per-session token cost. One paragraph plus two one-line cross-pointers is the budget; anything larger fails AC-6.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/dispatch-pattern.md` (add the no-relay-of-unread-content rule paragraph)
- `.claude/skills/plan/SKILL.md` (add one-line cross-pointer at Phase 4 Step 3)
- `.claude/skills/implement/SKILL.md` (add one-line cross-pointers at Phase 4b Step 3 and Phase 3 Step 5)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (N/A -- rule/skill content; verification by inspection of the rule paragraph and skill cross-pointers per ACs)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Added post-READY (2026-06-01) for the relay-fabrication gap surfaced during the E-231 planning session itself; did NOT go through the original Codex spec-review pass (the scorecard's Codex row reflects the original four-story pass). Structural complement to E-231-03 (in-skill triage gate) and E-231-01 (always-loaded assert-unseen prohibition); committed sibling anchor: `.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md`. Distinct from the live Addition-B advisory load-notice line in the same rule file.
