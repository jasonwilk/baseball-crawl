# E-260: Dispatch Cost Accounting

## Status
`COMPLETED`

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
- [ ] **AC-1**: E-260 lands with a **net-negative diff to `.claude/`** (`rules` + `agents` + `skills` + `agent-memory`), measured against `$(git merge-base epic/E-260 main)` (E-260's branch point), excluding only the baseline JSON and the counter hook. **The E-256 session's memory prune does not count toward this.** Reverting an unreviewed addition is table stakes, not offset budget.
- [ ] **AC-2**: E-260 is **not** run through the planning, spec-review, or codex machinery. One `claude-architect` story set; the operator hand-reads the diff. The reviewer stack has a conflict of interest reviewing its own constraints, and the planning ceremony is where this behavior originates.

## Falsifiers
Recorded now, so a future reader can tell whether this epic worked. Any one of them means it did not:

1. The layer exceeds its baseline a year from now beyond signed exceptions — **or** exceptions are signed at half or more of closures, which makes the ratchet a rubber stamp.
2. Median sends-per-story reaches 14 or more, **or** a story crosses the hard stop with no recorded operator escalation.
3. **An epic is written to sharpen E-260's own machinery, authored by agents rather than by the operator.** That is the loop re-entering through the brake.
4. The first hard stop is resolved by reinterpreting the rule in-session rather than by an operator decision.

## Stories

| ID | Title | Status | Agent | Blocked by |
|----|-------|--------|-------|-----------|
| E-260-01 | Remove the verbatim-relay mandate apparatus (+ closure-diff merge-base fix) | DONE | claude-architect | — |
| E-260-02 | Correct the false Test Execution Constraint (all sites, 3 files) | DONE | claude-architect | 01 |
| E-260-03 | Replace the code-reviewer severity test with a two-tier floor | DONE | claude-architect | 02 |
| E-260-04 | Scope-correct context-fundamentals (relay sentence + budget table) | DONE | claude-architect | — |
| E-260-05 | Drop the worktree-guard mode-1 agent-memory exemption + relocate closure-time own-memory writes | DONE | claude-architect | 02 |
| E-260-06 | Add the SendMessage counter hook (mechanism 2) | DONE | claude-architect | — |
| E-260-07 | Add the context-layer ratchet tool + wire triggers 7/8 (mechanism 1) | DONE | claude-architect | — |
| E-260-08 | Bootstrap the ratchet baseline + verify AC-1 net-negative | DONE | claude-architect | 01,02,03,04,05,07 |

Same-file ordering is staging-boundary hygiene on disjoint line regions, not a logical dependency. `implement/SKILL.md` is edited by 01, 02, and 05 → run **01 → 02 → 05** (05 last, so its large closure-sequence rewrite lands after the smaller edits settle). `code-reviewer.md` is edited by 02 and 03 → **02 → 03**. Every deletion/correction story (01-05, 07) is snapshot-first per the Operating Rule; the first to run creates `.project/archive/E-260-removed/`.

## Dispatch Team
- **Implementers**: claude-architect (all eight stories are context-layer / hook work — one hand-read story set).
- **Infrastructure**: product-manager (status owner + AC verifier), code-reviewer (quality gate).

Per AC-2 this epic is NOT run through the planning-ceremony spec review or codex machinery; the operator hand-reads the full closure diff. Whether the per-story code-reviewer gate still runs during dispatch (vs. being replaced by the operator's hand-read) is an operator call at dispatch authorization.

## Operating Rule
**Snapshot before deleting unreviewed material.** During E-256, 1,088 lines of agent memory were deleted on instruction with no snapshot taken; they are recoverable only by accident of transcript capture. Any deletion under this epic writes the removed text somewhere durable first.

## Notes
- **Accepted trade-off (no action).** With verbatim relay deleted and no persist-then-message replacement added — correctly, since that would be a new instruction this epic exists to avoid — SendMessage drops revert to being possible; recovery stays manual (re-request, or read the story file directly). This is the deliberate deal: a small annoyance returns, a large standing rulebook goes away.

## Open Questions
All four resolved by operator directive (2026-07-11); recorded here rather than deleted so the reasoning survives.
- ~~Who owns the ratchet baseline, and what does the operator's sign-off physically look like?~~ **RESOLVED (decision 1)**: The baseline is operator-owned. No baseline exists yet — E-260-08 bootstraps it via `context-ratchet.sh --update-baseline` (snapshotting post-deletion counts), mirroring E-257's `reconcile-scoreboard` convention: `--update-baseline` is operator-only, no agent auto-refreshes it, and the committed JSON diff is the human review point the operator signs at closure.
- ~~Does the severity floor need a third tier, or does SHOULD FIX absorb everything below MUST?~~ **RESOLVED (decision 2)**: Two tiers only. MUST FIX must name a functional consequence (behavior, security, data integrity, or test validity); everything else is SHOULD FIX — one message, no round. (E-260-03.)
- ~~Where does the dispatch log live, and who reads it?~~ **RESOLVED (decision 3)**: Worktree-local, rides the closure patch — no committed cross-epic aggregate. Columns degrade to what the hook can observe (epic ID + staging-boundary sequence index + sends; 'rounds' best-effort/blank), adding no new instruction (decision 7). (E-260-06.)
- ~~**Does the ratchet price agent-memory *content*, and who signs an increase?**~~ **RESOLVED (decision 4)**: The ratchet prices all four subtrees including `agent-memory`; the operator signs any increase past baseline. The structure/content ownership split (`context-layer-assessment.md:76`) still governs WHO edits memory (owning agents author content), but the operator's signature is what authorizes growing the layer past baseline. E-260-05 additionally drops the `worktree-guard.sh` mode-1 agent-memory exemption so dispatch-time memory writes land in the worktree and appear in the operator-approved closure diff.

## History
- 2026-07-10: Created as a DRAFT stub from the auditor reports, at operator request.
- 2026-07-10: Reshaped. Deletion-dominant rather than addition-dominant, after the auditor refuted the counter-plus-ratchet version: a counter that fires on behavior the configuration requires gets reinterpreted away, as the two-round breaker was. Two decisive ACs added; falsifiers recorded; the aphorism ban and the generated-output dimension dropped.
- 2026-07-10: Added the strongest evidence, verified against the file: `context-layer-assessment.md` trigger 7 is already a soft counterweight that ran for the whole 1,652 → 4,061 growth and never produced a shrink; trigger 8 is the promotion pump, citing its own E-230 → `tool-output-integrity.md` lap as proof it works. Trigger 7 → the ratchet; trigger 8 → deleted or gated. Open Question added on whether the ratchet prices agent-memory content, given the structure/content ownership split (`:76`) that forced the E-256 prune to be routed. No stories. Not READY.
- 2026-07-11: **READY.** Decomposed into 8 claude-architect stories (E-260-01..08) — the two mechanisms (ratchet tool, SendMessage counter) plus the deletion/correction set, one hand-read story set. All four Open Questions resolved by operator directive: (1) operator-owned ratchet baseline, bootstrapped by E-260-08 on the E-257 `--update-baseline` convention; (2) two-tier severity floor, MUST FIX names a functional consequence; (3) worktree-local dispatch log riding the closure patch, degraded columns, no new instruction; (4) ratchet prices all four subtrees incl. agent-memory, operator signs increases. Plus three mechanism decisions: trigger 8 gated (not deleted) on the ratchet keeping eviction+retirement hygiene (decision 6); dispatch-log columns = epic ID + staging index + sends, rounds best-effort (decision 7); ratchet tool at `.claude/hooks/context-ratchet.sh` as a MANUAL diagnostic with a pinned `*.md`+`*.sh` glob (decision 8). Operator-directed addition to E-260-01: correct closure sub-step 3 to diff against `$(git merge-base epic/E-NNN main)` not `main`, so a parked epic's closure cannot revert later-landed work (the live E-256/E-260 landmine). Per AC-2, NOT run through spec-review/codex — operator hand-reads the closure diff. Story files + this READY flip live on the epic/E-260 worktree branch and ride E-260's own closure commit into main (main's epic.md stays DRAFT until closure). Awaiting dispatch authorization.
- 2026-07-11: **Operator approved.** Four operator-directed amendments applied (no scope beyond this set): (A) grew E-260-05 to fix the FULL closure-time own-memory-write class — the de-exempted hook denies every closure-time own-memory write while the worktree exists, so all enumerated `implement/SKILL.md` closure-sequence sites (:32/:466/:476/:556/:575/:581/:583/:591-605/:609/:631) relocate PM's + CA's closure-time memory writes into the sub-step-3 worktree patch, one defect / one citation; hook change + skill rewrite are atomic in story 05 (E-260 closes under the OLD hook); staging order for `implement/SKILL.md` is now 01 → 02 → 05 (05 blocked-by 02). (B) E-260-06 reset matcher keyed on the worktree prefix `/tmp/.worktrees/baseball-crawl-E-` AND a `git add` invocation, so main-checkout closure adds don't fire phantom rows. (C) E-260-06 deny-at-25 message pinned to exact operator-decision-point text (Falsifier 4). (D) accepted-trade-off note added; E-260-02 title de-undercounted. Epic remains READY.
- 2026-07-12: **Dispatch in progress; AC-1 measurement base amended (operator-directed).** Stories 01-07 all DONE. The literal `5e710c2` pin in AC-1 was stale: E-260 actually branched from **bac7e21**, which added +351/-2 non-E-260 lines inside `.claude/agent-memory` (the SE/CR-learnings commit) — those sit in a measured path and cannot be excluded by path, so a `5e710c2` base folds exactly the E-256 churn AC-1 says to exclude INTO the diff. Operator ruled the base be `$(git merge-base epic/E-260 main)` (= bac7e21). This unifies the epic AC-1 text, story-08's AC-1/AC-2/AC-4 + Technical Approach, and the E-260-01/AC-6 closure patch on ONE base (the branch point) and mechanically excludes non-E-260 churn. All `5e710c2` references in the epic and story 08 updated to the merge-base form.
- 2026-07-12: **All 8 stories DONE — closure bookkeeping (Steps 2-5).** 8 claude-architect stories, deletion-dominant. The two mechanisms added (`.claude/hooks/context-ratchet.sh`, `.claude/hooks/send-message-counter.sh`) sit OUTSIDE the four measured subtrees, so the epic's net change to the four subtrees is a shrink. **AC-1 met** — net **−9** to the four subtrees (`rules`/`agents`/`skills`/`agent-memory`) vs the merge-base (bac7e21), verified by CR reproduction (63 ins / 72 del). **AC-2 met** — no spec-review/Codex ran at planning or closure; the operator hand-reads the closure diff. **Zero MUST FIX findings across the epic.** Falsifiers status at closure: #3 (an epic authored by agents to sharpen E-260's own machinery) held — E-260 was operator-commissioned and operator-directed; no agent re-expanded the deletions. COMPLETED status flip is authored in the worktree at Step 8 sub-step 3 (per E-260-05's own just-shipped closure-time-own-memory-in-worktree relocation — self-applying).
- 2026-07-12: **Operator-authorized ratchet re-snapshot at closure.** Baseline 12079→12081 to absorb E-260's own +2 closure-ledger writes (archived-epics.md +1, ce5 annotation +1; MEMORY.md +0, in-place); AC-1 final net **−7** (still net-negative) vs merge-base (68 ins / 75 del); ratchet PASS/exit-0 at 12081 (the accepted floor). Per decision 1 the operator reviews the baseline JSON diff in the closure hand-read.

## Review Scorecard
E-260 was **not** run through spec-review or Codex at planning or closure (AC-2 — the reviewer stack has a conflict of interest reviewing its own constraints, and the planning ceremony is where this behavior originates; the operator hand-reads the diff). Planning refinement was PM-internal + four operator-directed amendments. Dispatch used per-story code-review + PM AC-verification on every story; no Closure CR Integration Review, no Codex passes.

| Story | Review | Rounds | Findings | Accepted | Dismissed |
|-------|--------|--------|----------|----------|-----------|
| E-260-01 | Per-story CR + PM AC-verify | 2 | 1 | 1 | 0 |
| E-260-02 | Per-story CR + PM AC-verify | 1 | 0 | 0 | 0 |
| E-260-03 | Per-story CR + PM AC-verify | 1 | 0 | 0 | 0 |
| E-260-04 | Per-story CR + PM AC-verify | 1 | 0 | 0 | 0 |
| E-260-05 | Per-story CR + PM AC-verify | 1 | 0 | 0 | 0 |
| E-260-06 | Per-story CR + PM AC-verify | 1 | 0 | 0 | 0 |
| E-260-07 | Per-story CR + PM AC-verify | 1 | 0 | 0 | 0 |
| E-260-08 | Per-story CR + PM AC-verify | 1 | 0 | 0 | 0 |
| **Total** | | | **1** | **1** | **0** |

Note: E-260-01's single finding was **PM-AC-verification-sourced** (not CR): the `plan/SKILL.md:390` AC-5 orphan — a dangling relay-integrity blockquote citing the `no-relay-of-unread-content` rule that AC-3 deleted. Remediated in round 1 (struck, snapshot-first), then PM re-verified AC-5 PASS + CR APPROVED. Every per-story CR returned APPROVED with zero CR-sourced findings; PM AC-verification found the one orphan. Two PM judgment calls in E-260-05 (`:160` 6th-site, `:526` Step-7a narrowing) and the E-260-04 `:28` scope call were ruled without changing scope.

## Closure Assessments

### Documentation Assessment (Step 3)
**No documentation impact.** E-260 touches no `docs/admin/` or `docs/coaching/` files — all changes are context-layer config/prose + hooks + `.project/` artifacts. No update trigger fires.

### Context-Layer Assessment (Step 3a) — eight per-trigger verdicts
No ADDITIONAL claude-architect codification is spawned: **E-260 IS the codification** (its stories are context-layer edits authored by claude-architect), and the operator's post-E-260 meta-layer freeze plus Falsifier #3 bar re-expansion of this machinery by agents.
1. **New convention — YES.** The context-layer ratchet, the two-tier severity floor, closure-time-own-memory-in-worktree, and the SendMessage counter. Codified in-epic.
2. **Architectural decision — YES.** The ratchet as the context-layer size mechanism; the merge-base closure/measurement base. Codified in-epic.
3. **Footgun/boundary — YES.** The closure-time own-memory-write denial landmine (fixed in E-260-05); the multi-worktree `head -1` attribution + E-256 resume-guard hazards (→ IDEA-116). Codified in-epic + follow-up idea.
4. **Agent behavior/coordination — YES.** Closure-sequence own-memory relocation, the severity floor, the relay-mandate removal, the SendMessage counter. Codified in-epic.
5. **Domain knowledge — NO.** No baseball/API/data-model domain knowledge surfaced (the worktree-pytest truth was corrected in-config by E-260-02, not carried as new domain knowledge).
6. **New tool/procedure — YES.** `context-ratchet.sh` + `send-message-counter.sh`. Per the meta-layer freeze + Falsifier #3, these are NOT further codified into CLAUDE.md prose (the operator hand-reads the tools; trigger 7 already references the ratchet). **Flagged to the operator** for a CLAUDE.md/workflow-help mention decision.
7. **Net-growth offset — SATISFIED (shrink).** Net **−9** to the four subtrees vs the merge-base; the ratchet baseline `.project/baselines/context-layer-ratchet.json` (total 12079) is now the established floor, awaiting operator sign-off. Trigger 7's own new mechanism (the ratchet) exits 0 against that fresh baseline.
8. **Reusable-lesson promotion (gated) — NO new promotion.** The worktree-pytest lesson was corrected in-config (E-260-02); the deferred consistency/attribution items are captured as follow-up ideas (IDEA-116/117/118), not promoted. Deletion-Side Eviction fired: `project_ce5_curation_handoff.md:15`'s trigger-7 soft-prompt description is superseded by E-260-07's ratchet — PM annotated it (worktree copy, at Step 4) with a SUPERSEDED-by-E-260-07 note.

### Vision Signals (Step 5)
`docs/vision-signals.md` checked — E-260 is a meta-layer/dispatch-cost epic and surfaced **no new product vision signals**. The 14 signals parked since the 2026-07-05 curation remain; nothing to append or advise.

### Follow-up Ideas Filed (Step 4)
IDEA-116 (cwd-based worktree attribution for the dispatch hooks + E-256 resume guard), IDEA-117 (scope `multi-agent-patterns:24`'s "Never summarize" to the dispatch context block), IDEA-118 (refresh `context-fundamentals` `:28`/`:185`/`:193` ambient figures). Indexed in `.project/ideas/README.md`.
