# E-260: Dispatch Cost Accounting

## Status
`DRAFT`

## Overview
The agent configuration has grown for four months and has never shrunk. It contains standing instructions that require expensive behavior — most importantly, a mandate that agents relay findings verbatim rather than summarize. Nothing in the configuration prices that behavior, and nothing removes a rule once added.

This epic is mostly deletions. It removes the instructions that require the expense, then adds two mechanisms — one to measure the layer's size, one to count messages — so the growth becomes visible instead of invisible.

## Background & Context
Source: two auditor reports on the E-256 dispatch, commissioned by the operator (2026-07-10).

**What was measured.** `.claude/rules/` plus `.claude/agents/` grew from 1,652 to 4,061 lines in four months. Every commit added lines; none removed a net line. The growth continued through E-239, which deleted about 59,000 lines of product code, and through E-255, an epic named "Truth Sweep." The E-256 dispatch itself produced roughly 640,000 characters of agent-to-agent prose, and spent seven review rounds on a `.dockerignore` file — several of them correcting mistakes the review process had introduced.

**Why deletions come first.** An earlier version of this epic proposed keeping the instructions and adding a counter to catch overuse. That does not work. `never summarize` is a standing instruction: an agent obeying it produces the messages the counter would penalize. A counter that fires on required behavior is an enforcement mechanism at war with the instruction set, and it gets reinterpreted away — which is how the two-round circuit breaker died during E-256. The instructions have to go first.

**The soft version of this epic already exists, and it failed for four months.**

`.claude/rules/context-layer-assessment.md` trigger 7 is already a counterweight rule. It asks, at every epic closure: *"Did this epic grow the context layer net-positive? If so, what was compressed, consolidated, or retired to offset it — or, if nothing, why is the net growth load-bearing?"* And it explicitly refuses to become a ratchet: *"This is a review prompt, NOT a hard line-count or KB cap — a line budget is density-gameable."*

That rule was in force for the entire 1,652 → 4,061 growth. Every closure answered it. Not one produced a net shrink — including E-239, which deleted 59,000 lines of product code, and E-255, called "Truth Sweep."

**So the objection to a hard ratchet is already answered by the evidence: the ungameable version never fired.** A soft prompt loses to whoever is doing the growing, because trigger 7's verdict is rendered by that same party. A third soft mechanism exists too — `context-layer-guard.md` sets a CLAUDE.md target of ~150 lines and a MEMORY.md target of under 150, and recommends consolidating small rules. It did not hold either.

**The amplification pump is written down as policy.** Trigger 8 of the same file mandates *promote-to-load-target*: a reusable behavioral lesson that recurred or generalizes must be codified into an auto-loading rule **now**. The file cites its own proof: *"The two immediate promotions proving this pipeline landed in `.claude/rules/tool-output-integrity.md`."* The E-230 incident → PM memory file → universally-loaded rule is not something that merely happened. It is the documented, intended behavior of trigger 8, offered as evidence the pipeline works.

Two brakes and a pump, in one file. The pump fires on every epic; the brakes ask a question and accept any answer.

**The configuration's own guidance about context is stale.** `.claude/skills/context-fundamentals/SKILL.md` was not consulted during E-256, and would not have helped. Its ambient-budget table (`:74`, `:83`) cites "~614-886 lines," dated at `:85` as "measured post-E-213 (2026-04-05)." The layer is now 4,061 lines. Its model measures files *loaded into* a session; the E-256 leak was prose *generated out of* one, which no table in the skill anticipates.

Its line `:195` says verbatim relay is the right choice even when summarizing would save tokens. **That sentence is scoped to the dispatch context block — the story file and epic Technical Notes pasted into a spawn prompt.** It is not about relaying review findings between live agents, which is what `implement/SKILL.md` mandates and what the auditor measured. It should be struck or scoped, because it will be read as a blanket endorsement. But it is not the source of the finding-relay mandate, and a story that deletes it for that reason will leave the real problem in place.

## Goals
- Remove the standing instructions that require expensive relay.
- Make the size of the configuration visible and bounded.
- Make the volume of dispatch messages visible and bounded.
- Distinguish a defect from a wording preference in the reviewer's own vocabulary.

## Non-Goals
- **Weakening acceptance-criteria verification.** Reading the tree rather than the completion report was not the problem.
- **Removing pre-assignment spec review.** Reading a story file before dispatching it, and fixing what is found, prevented rework four times in E-256 and costs a minute.
- Relitigating E-256's findings. Its code is sound.
- Adding prose rules. This epic adds two mechanisms and no new instructions.

## Scope

### Deletions (the bulk of the work)
- `implement/SKILL.md` — the `never summarize` mandate at `:237` and `:687`; the round-one-findings-verbatim instruction at `:292`; the "PM AC rejection does NOT have its own circuit breaker" carve-out at `:303`.
- `dispatch-pattern.md` — the substantive-content-relay default, and the relay-integrity read-receipt paragraph.
- `code-reviewer.md:226` — replace the three-condition downgrade test with a single severity floor: a MUST FIX must name a functional consequence (behavior, security, data integrity, or test validity). Everything else is a SHOULD FIX — one message, no round.
- `tool-output-integrity.md` — delete the expansive framing ("binds every agent on every session") and the Related-discipline tail. **Scope it by deleting text, not by appending a caveat.**
- `context-fundamentals/SKILL.md:195` — strike or scope, per the Background note. Re-derive the stale budget table and put its regenerating command beside it.
- `code-reviewer.md` **Test Execution Constraint — it is false.** It asserts that worktree pytest tests the main checkout's code. Measured during E-256: pytest resolves to the worktree, because `tests/__init__.py` causes pytest to prepend the repo root to `sys.path`, where it shadows the editable-install finder. The configuration currently contradicts an agent memory file that proves it wrong.
- `context-layer-assessment.md` — **trigger 7 becomes the ratchet.** It is currently a review prompt that accepts any answer; the ratchet (addition 1) is the mechanism it declined to be. And **trigger 8's promote-to-load-target mandate is deleted, or gated on the ratchet.** As written, trigger 8 requires codifying a lesson into an auto-loading rule at every closure that surfaces one; gated, a promotion must cite the defect it demonstrably caught and fit inside the budget. The `context-layer-guard.md` targets (~150 CLAUDE.md, <150 MEMORY.md) fold into the ratchet's baseline rather than standing as unenforced numbers.
- One hook line: `worktree-guard.sh` mode 1 — drop the `agent-memory` exemption. The configuration already says that carve-out is consultation-only, and the hook cannot tell the modes apart. With it gone, dispatch-time memory writes land in the worktree, ride the closure patch, and appear in the diff the operator approves. Consultation writes (no worktree present) are unaffected.

### Additions (exactly two)
1. **A ratchet over the context layer.** A committed baseline JSON of line counts for `.claude/rules`, `agents`, `skills`, and `agent-memory`. Any codification must cite the specific defect it demonstrably caught. The layer does not grow past baseline without the operator signing the exception. Same instrument as E-257's reconciliation scoreboard, pointed at the configuration.
2. **A SendMessage counter.** A `PreToolUse` hook on `SendMessage`, writing a counter file in the epic worktree, reset on `git add -A`. Warn at 15 sends, deny at 25. Appends one row per story to a dispatch log: story ID, sends, rounds.

   **Both thresholds carry their provenance in the hook's comment.** 15 is derived from the existing two-round breaker's implied budget of roughly 12-14 sends. **25 is a placeholder calibrated on a single epic.** The comment names the operator as the only person who may edit either number.

### Dropped from earlier drafts
- **Banning the aphorism register.** Unenforceable — only stateable. A rule that can only be declared is the thing this epic exists to stop producing. It dies for free once the deletions land: a ten-line verdict has no room for one.
- **Adding a generated-output dimension to `context-fundamentals`.** That grows a skill to do the counter's job.

## Acceptance Criteria (epic-level; decide the epic without anyone's judgment)
- [ ] **AC-1**: E-260 lands with a **net-negative diff to `.claude/`** (`rules` + `agents` + `skills` + `agent-memory`), measured against commit `5e710c2`, excluding only the baseline JSON and the counter hook. **The E-256 session's memory prune does not count toward this.** Reverting an unreviewed addition is table stakes, not offset budget.
- [ ] **AC-2**: E-260 is **not** run through the planning, spec-review, or codex machinery. One `claude-architect` story set; the operator hand-reads the diff. The reviewer stack has a conflict of interest reviewing its own constraints, and the planning ceremony is where this behavior originates.

## Falsifiers
Recorded now, so a future reader can tell whether this epic worked. Any one of them means it did not:

1. The layer exceeds its baseline a year from now beyond signed exceptions — **or** exceptions are signed at half or more of closures, which makes the ratchet a rubber stamp.
2. Median sends-per-story reaches 14 or more, **or** a story crosses the hard stop with no recorded operator escalation.
3. **An epic is written to sharpen E-260's own machinery, authored by agents rather than by the operator.** That is the loop re-entering through the brake.
4. The first hard stop is resolved by reinterpreting the rule in-session rather than by an operator decision.

## Operating Rule
**Snapshot before deleting unreviewed material.** During E-256, 1,088 lines of agent memory were deleted on instruction with no snapshot taken; they are recoverable only by accident of transcript capture. Any deletion under this epic writes the removed text somewhere durable first.

## Open Questions
- Who owns the ratchet baseline, and what does the operator's sign-off physically look like?
- Does the severity floor need a third tier, or does SHOULD FIX absorb everything below MUST?
- Where does the dispatch log live, and who reads it?
- **Does the ratchet price agent-memory *content*, and who signs an increase?** `context-layer-assessment.md:76` splits ownership: `claude-architect` owns `.claude/agent-memory/**` *structure*, individual agents own *content*. That split is why the E-256 memory prune had to be routed to owning agents rather than executed centrally. A ratchet over the layer has to decide whether memory content counts toward the budget, and if so, whose signature authorizes growing it — the owning agent's, or the operator's.

## History
- 2026-07-10: Created as a DRAFT stub from the auditor reports, at operator request.
- 2026-07-10: Reshaped. Deletion-dominant rather than addition-dominant, after the auditor refuted the counter-plus-ratchet version: a counter that fires on behavior the configuration requires gets reinterpreted away, as the two-round breaker was. Two decisive ACs added; falsifiers recorded; the aphorism ban and the generated-output dimension dropped.
- 2026-07-10: Added the strongest evidence, verified against the file: `context-layer-assessment.md` trigger 7 is already a soft counterweight that ran for the whole 1,652 → 4,061 growth and never produced a shrink; trigger 8 is the promotion pump, citing its own E-230 → `tool-output-integrity.md` lap as proof it works. Trigger 7 → the ratchet; trigger 8 → deleted or gated. Open Question added on whether the ratchet prices agent-memory content, given the structure/content ownership split (`:76`) that forced the E-256 prune to be routed. No stories. Not READY.
