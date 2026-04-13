# IDEA-068: Evaluate main-session dispatch behaviors for codification

## Status
`CANDIDATE`

## Summary
Main session (team-lead / Claude Opus 4.6) developed operational behaviors during the E-220 → E-221 → E-222 recovery arc that the user believes influenced dispatch quality. This idea catalogs 15 observed behaviors grouped into 6 themes and asks "should any of these be codified into CLAUDE.md, plan skill, implement skill, dispatch-pattern rule, or elsewhere?" — NOT to decide codification now, but to preserve the behaviors for deliberate later evaluation.

## Why It Matters
Behaviors that emerge from crisis response can feel like "common sense" to the agent that developed them but are invisible to a fresh instance. Codification into the context layer is the forcing function for continuity. At the same time, over-codification leads to rule bloat — E-222 was the cautionary tale. The right move is to list the behaviors now, evaluate each on its merits later, and accept that some won't warrant codification at all.

## The 15 observed behaviors (grouped into 6 themes)

### Theme A — Ground-truth verification discipline
1. **Verification before action**. Main session probes ground truth (reads actual files, runs `git diff`, checks real state) rather than trusting assumptions from prior context. Example: when told "E-221 is at READY", verified via `git log` + reading the committed epic file.
2. **Parallel probes for diagnosis**. Runs multiple independent checks in parallel rather than sequentially. Example: during session-crash recovery, ran team config read + worktree git status + TaskList simultaneously.
3. **Pre-flight cleanliness checks**. Before major actions (dispatch, commit), verifies the tree is clean and no stray state exists. Example: confirmed no stray worktrees before beginning Phase 2 dispatch.

### Theme B — Decision surfacing
4. **Option A/B/C framework**. When a non-obvious decision emerges, presents 3 options with tradeoffs, makes a recommendation, and asks for explicit user input rather than making unilateral calls. Examples: 15-file grandfather decision on E-221-03; minimal-patch-vs-refactor decision on E-221-05 Phase 2 finding.
5. **Pause-before-dispatch when scope expands**. When new information changes story scope during dispatch, pauses dispatch and raises the decision with the user before touching the next story. Examples: pausing E-221-03 dispatch after PM found 15 pre-existing drift files; pausing E-221-05 after the Phase 2 finding.

### Theme C — Agent coordination discipline
6. **Structured review briefs with priority focus areas**. CR/PM review requests include a "priority focus areas" section naming specific items worth attention. Emerged from wanting reviewers to do specific verification rather than generic review.
7. **Verbatim substantive content in relay messages**. Story assignments and review requests include full story file text + full Technical Notes verbatim, not summaries. *(CA note: already in implement skill Phase 3. Low codification value — this is already codified.)*
8. **Sanity-check directives in dispatch briefs**. SE dispatch briefs include re-grep / re-verify instructions with explicit failure protocols (e.g., "if the 15-file grep returns a different count, pause for adjudication"). Emerged from the worry that enumerations captured during planning can drift from reality at dispatch time.
9. **Proactive context health monitoring**. Tracks estimated context growth per agent, flags respawn checkpoints in advance (e.g., "CR should be respawned before Phase 4a integration review"). *(CA note: risky to codify — could become cargo-cult. Judgment-dependent.)*

### Theme D — Recovery discipline
10. **Diagnostic probe before treatment**. When something goes wrong (silent agents, crashes), runs probes to understand the state before proposing recovery. Example: after 4 simultaneous silences, ran parallel probes before concluding in-process agents died.
11. **Honest failure naming**. Names the specific failure mode rather than hand-waving. Example: "your session crashed; in-process agents died with it (backendType: in-process is the smoking gun); the task list was lost; the worktree is intact."

### Theme E — Rule-fidelity observation
12. **Tracking agent format compliance across multiple messages**. Counted PM's Anti-Pattern 7 echo-back compliance across 4 substantive relays, noted the pattern to the user each time. *(CA note: risky to codify — judgment-dependent. Good as an observation discipline, bad as a mechanical rule.)*
13. **Willingness to recommend revising a newly-shipped rule based on observed behavior**. Phase 1 recovery landed Anti-Pattern 7 on 2026-04-12; by later that same day, main session was recommending letter-vs-spirit revision based on PM's actual behavior. Treated the rule as provisional until proven by operational reality.

### Theme F — Pattern propagation
14. **Passing operator preferences through the chain**. When user said "use rtk proxy for pytest", main session propagated that guidance into every subsequent SE dispatch brief, not as a one-time note.
15. **Burn-number discipline on epic abandonment**. When abandoning E-222, correctly burned the number (never reused) and advanced PM memory's "next available". *(CA note: already codified in project-management.md "NEVER reuse an epic or story number". Low codification value.)*

## CA's observations (from the blocked draft attempt)

**Already covered implicitly** (low codification value): #7 verbatim relay, #15 burn-number discipline.

**Most novel and load-bearing**: **#4 Option A/B/C framework and #5 pause-before-dispatch-on-scope-expansion.** Not in any current rule or skill. Most directly tied to the user's observation that E-221 dispatch "felt different."

**Risky to codify** (cargo-cult risk): #9 context health monitoring, #12 format compliance tracking. Judgment-dependent; a rule saying "always do this" could produce noise on small dispatches.

**Best candidates for minimum-viable codification**: **#1 verification before action and #10 diagnostic probe before treatment.** Both could likely be single-line additions to dispatch-pattern.md without adding bulk.

**Self-observation blind spot**: behavior #13 (willingness to revise a newly-shipped rule) cuts *against* the idea of codifying behaviors. If codified rules should be provisional until validated by operational reality, then this very idea should explicitly defer codification until after more dispatch evidence accumulates — which matches the "defer evaluation" framing.

## Evaluation criteria for later promotion
When this idea gets promoted and evaluated, use these criteria per-behavior:

1. **Observability**: Is the behavior observable across multiple dispatches, or was it a one-time situational response? (Codify the former; leave the latter to judgment.)
2. **Gap-filling**: Does the behavior fill a gap that existing rules/skills don't already cover? (Cross-reference against CLAUDE.md, plan/SKILL.md, implement/SKILL.md, dispatch-pattern.md, workflow-discipline.md, agent-team-compliance.md.)
3. **Counterfactual impact**: Would codifying it meaningfully change a fresh main-session instance's behavior, or is it already implicit in good judgment?
4. **Minimum viable codification**: What's the smallest artifact that captures the behavior (single line in CLAUDE.md vs. new rule file vs. skill update)? Prefer smallest.
5. **Rule-bloat risk**: Does the codification risk the E-222 anti-pattern (ceremony-without-forcing-function)?

## Rough Timing
Defer evaluation to:
- **Context-layer assessment gate at E-221 closure** (earliest opportunity), OR
- **90-day idea review** (2026-07-12), whichever comes first.

## Dependencies & Blockers
- [ ] None. Evaluation can happen any time — earliest natural moment is E-221 closure's context-layer assessment gate.

## Open Questions
- What blind spots does the main session have on its own behaviors? Self-observation is unreliable — user or code-reviewer review of a future dispatch transcript may surface things the main session didn't notice about itself.
- Is the right venue for these behaviors CLAUDE.md (loaded by every agent), dispatch-pattern.md (loaded during dispatch), plan/SKILL.md, or a new rule file? Probably a mix, one per theme.
- Should behavior #13 (willingness to revise rules based on observation) be codified as an explicit pattern, or is it incompatible with any codification at all?

## Notes
Origin: claude-architect drafted this during active E-221 dispatch on 2026-04-12 via consultation-mode Agent spawn. Worktree-isolation hook correctly blocked a direct write to `/workspaces/baseball-crawl/.project/ideas/` (main-checkout writes restricted to `.claude/agent-memory/*` during dispatch). Main session stashed the draft to its memory directory for durability; PM-v2 promoted it to a proper idea file when the admin/generator cascade consolidation idea was renumbered from IDEA-068 to IDEA-069.

Related:
- E-220 (source of the recovery arc)
- E-221 (dispatch where behaviors were observed)
- E-222 (anti-pattern of over-codification — the cautionary tale this idea must avoid)
- Phase 1 recovery commit c8ead59 (context-layer precedent; 5 small fixes shipped 2026-04-12)
- IDEA-069 (the cascade consolidation follow-up that originally held the 068 slot)

---
Created: 2026-04-12
Last reviewed: 2026-04-12
Review by: 2026-07-12
