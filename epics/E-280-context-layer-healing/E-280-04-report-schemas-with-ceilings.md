# E-280-04: Report schemas with ceilings and code-reviewer tier keying

## Epic
[E-280: Context-Layer Healing](./epic.md)

## Status
`TODO`
<!-- Unblocked 2026-08-02: OQ-A ruled (E-280 dispatches first, E-271 demoted to DRAFT), so the E-271-02 AC-6 rubric conflict is dissolved. TRIM 2 moved out of this story to E-280-08 the same day. -->

## Description
After this story, every agent definition carries a named report schema with sections and a stated ceiling, and `code-reviewer.md`'s rubric keys off the tier E-280-02 introduces. Two trims land here because they share one directory and are file-disjoint from everything else: TRIM 4 and TRIM 3's keying, both in `.claude/agents/`.

**TRIM 2 (the batched audit-cadence line) was carried here and moved out on 2026-08-02.** It lives in **E-280-08** now, because the operator's gate-retirement ruling landed on the same file this story would have edited for one line (`.claude/rules/context-layer-assessment.md`), and a dedicated cadence story is the file-disjoint home for both. Nothing was dropped in the move; TRIM 2's four criteria are E-280-08's AC-1 through AC-4.

Opus 5 stays; the report cap is the cheaper lever the wall-clock analysis identified in its place.

## Context
The one clearly model-attributable regression in the data is output per turn, and the replication scopes it precisely: the "2x more verbose" figure holds for **subagent report-writing turns**, not for all traffic, where per-call means show only +11% (TN-2). So the cap belongs on reports and would be mis-scoped as a cap on output generally. The E-279 dispatch produced **891k output tokens across five stories** (TN-3).

Two placement calls from the design owner, both of which the acceptance criteria enforce:

**This is a role contract, not a model adapter.** The cost is paid by the reader's context regardless of which model wrote the message, and three agents — baseball-coach, docs-writer, ux-designer — pin Sonnet and have no Model Adapter section at all, so adapter placement would miss them entirely.

**The vendor line already in the six Opus 5 adapters governs written documents on disk; this governs SendMessage reports.** Different surfaces. Conflating them would create exactly the instruction-pair-in-tension that this epic is treating.

The form must be structure, not vigilance prose. "Be concise" is what the vendor mandate forbids and it does not work. Two working instances already exist in this repo: the implementer completion schema in `implement/SKILL.md` — the block beginning *"**Completion**: Report with `## Files Changed`"* (Files Changed / Test Results / Behavioral Changes) — and `code-reviewer.md`'s `## Structured Findings Format`. This story extends that pattern to the agents lacking one. (Re-anchored by phrase 2026-08-02: the line citation this sentence carried points into a file E-280-02 edits, and TN-6 commits this epic's stories to phrase citation for exactly that reason.)

## Acceptance Criteria

- [ ] **AC-1**: Every agent definition in `.claude/agents/` has a named report schema with enumerated sections, **and every one except `code-reviewer` also has a stated ceiling**. **RED**: any agent with no schema; any agent other than code-reviewer with a schema and no ceiling; or a ceiling on code-reviewer's findings output. (⚠️ **The code-reviewer carve-out is AC-18's, and it is stated here too because otherwise these two ACs contradict each other** — AC-1 originally required a ceiling on *every* agent, which would have made AC-18's exclusion a RED under AC-1. An instruction pair in tension is the named cause of the harm this epic treats, so it does not get to survive inside the epic. **Code-reviewer still gets a schema**; only the length ceiling is withheld.)
- [ ] **AC-2**: Each agent file gets a **written verdict**, `already has one, unchanged` included. **RED**: an agent file in `.claude/agents/` with no verdict recorded. (Naming the coverage set does not enforce it; the per-file written verdict does.)
- [ ] **AC-3**: The three Sonnet-pinned agents are covered on the same terms as the six with Model Adapter sections. **RED**: any of them lacking a schema or a ceiling.
- [ ] **AC-4**: The vendor written-document line inside every existing `## Model Adapter` section is **unchanged**. **RED**: any diff hunk touching that line. (The two surfaces stay separate; this is checkable directly from the diff.)
- [ ] **AC-5**: No agent file carries a bare exhortation — "be concise", "keep it brief", "avoid verbosity" — as its mechanism. **RED**: such a sentence present as the sole length control for that agent.
- [ ] **AC-6**: The ceiling is stated in a unit a reader can check against a message without knowing the author's intent. **RED**: a ceiling expressed only as a judgment ("short", "proportionate") with no checkable unit.
- [ ] **AC-16**: **The ceiling is 6,000 characters (~1,500 tokens) for long-lived agents, and it is a TAIL guard: above every covered role's measured p50, below the measured max.** **RED**: a ceiling at or below any covered role's measured p50 — it would bind normal traffic, which is not what the measurement supports; **or** at or above the measured max of 13,882 — it would bind nothing. (⚠️ **This AC was rewritten 2026-08-02 and previously required the opposite** — *"each ceiling is BELOW the observed status quo"* — which assumed a report-length regression existed. **The measurement in epic TN-19 shows it does not:** E-279's report payloads sit inside the peak-4.8-era range and below that era's heaviest session on every statistic. A cap below p50 would throttle traffic that was never inflated.)
- [ ] **AC-17**: **The ceiling is labelled an ESTIMATE, and the story states plainly that no report-length regression was measured** — this is a guardrail against future drift, not a repair of observed inflation. **RED**: the figure presented as measured or as derived from the wall-clock analyses; or the no-regression-measured statement absent. (The 2x verbosity finding is **per-turn** and does not transfer to reports; epic TN-19 carries both measured tables and the bounds. Coherent with the primary analysis rating TRIM 4's expected saving **"small"**, alone among the four trims. This repo's specific failure mode is figures acquiring false provenance by restatement, and the honest label is what prevents it.)
- [ ] **AC-18**: **`code-reviewer` is EXCLUDED from the ceiling, and the exclusion states the review-bar-literalism reason in the file.** **RED**: a ceiling applied to code-reviewer's findings output, or an exclusion recorded with no reason a later editor could evaluate. (Not politeness — a documented failure mode of the model code-reviewer pins: it may follow a conservatism instruction literally and report less, the vendor's own remedy being to *"ask it to report everything and filter in a separate pass instead."* **A length ceiling is a conservatism instruction wearing different clothes.** CR's length is structurally driven by finding count, making it the most tempting target and the one where truncation costs most. An implementer who applies the cap uniformly for consistency has produced the exact defect this AC exists to prevent.)
- [ ] **AC-7**: The schema governs SendMessage reports and says so. **RED**: a schema whose scope is unstated, or stated so as to also govern on-disk documents.

**TRIM 3 keying (code-reviewer.md):**

- [ ] **AC-8**: `code-reviewer.md`'s rubric application keys off the tier E-280-02 defines, and the tier-to-depth mapping is authored here rather than restated in the routing seam. **RED**: the routing seam restating rubric content, or the rubric naming path classes independently of the seam's table (two places defining one classification is the restatement defect).
- [ ] **AC-9**: Every review priority in the rubric is assigned to at least one tier. **RED**: a priority appearing in no tier — an orphaned priority is a check silently deleted rather than tiered.

**Review-surface invariant (this story owns `code-reviewer.md`):**

- [ ] **AC-15**: `.claude/agents/code-reviewer.md` no longer defines the review surface as unstaged working-directory state. Every site is enumerated and carries a **written verdict**, `no change needed` included. **RED**: any surviving sentence equating unstaged content with the current story's changes, or an enumerated site with no verdict. **Four** sites are known and are a **floor, not the list**: the *"The current story's changes are **unstaged** in the epic worktree. Prior stories' changes are staged."* passage, the *"the staging boundary protocol isolates per-story changes"* sentence, the *"in the current unstaged diff"* clause, and — **the one no token sweep reaches** — the untracked-file warning opening *"Run `git status` too, because the review loop is structurally BLIND to an UNTRACKED file."*
  - **That fourth site is a judgement resting on the invariant and shares none of its tokens** (no "unstaged", no "staging boundary"), which is precisely the `doc-sweep.md` retired-claim shape. **Reconcile it, do not delete it, and note the freeze changes its premise in the HELPFUL direction:** `git add -A` plus `git write-tree` captures untracked files, so the blindness it warns about is **cured by the mechanism**. Its E-276 instance (a closure assessment block nearly dropped) is **evidence of what was observed** and is preserved verbatim; only the still-blind framing is stale.
  - At least four further sites in this file carry the invariant routinely and each still takes a written verdict under this AC: the `git diff` command directly beneath the first quoted passage (leaving it while rewriting that sentence would self-contradict the section), the "all accumulated changes" / `git diff main` merge-base pair, the Test Execution Constraint's *"the worktree's own uncommitted `src/`"*, and anti-pattern 5's listing of `git diff` as permitted. The last two are likely `no change needed` — but likely is not a verdict. (⚠️ **This AC exists because E-280-07 AC-1c verifies the invariant is gone layer-wide and cannot itself edit this file.** Without an AC here the epic demanded a state no story produced — the defect the spec audit caught. Match `implement/SKILL.md`'s post-E-280-02 freeze wording; cite by phrase, since these anchors move.)

**Trigger-count de-restatement (this story owns the agents tree):**

- [ ] **AC-14**: `.claude/agents/product-manager.md` states **no numeric count** of the context-layer assessment's triggers. Its closure-checklist item refers to them without a number. **RED**: any numeral or number-word quantifying the triggers in that file. (One of four sites carrying the count; the edit lands here because this story owns the agents tree, and E-280-08 AC-11 verifies globally that no site survives. See epic TN-16.)

**TRIM 2 moved to E-280-08 on 2026-08-02.** Its four criteria are that story's AC-1 through AC-4. No criterion was dropped.

**Why this story's AC numbers jump 9 → 14 → 15.** AC-10 through AC-13 were TRIM 2's and left with it; numbers are never reused, so the later additions took 14 (trigger-count de-restatement) and 15 (review-surface invariant). Recorded here because the tombstone that used to explain the gap is being deleted before the planning commit.

## Technical Approach
Follow the two existing in-repo schemas rather than inventing a third shape. A schema with a ceiling is subtractive — it removes the decision about what to include; an exhortation is additive and has no red state.

The notable gaps are product-manager and claude-architect, neither of which has a report schema today. The six agents with `## Model Adapter (Claude Opus 5)` sections are claude-architect, data-engineer, api-scout, product-manager, software-engineer, and code-reviewer; the three Sonnet-pinned are baseball-coach, docs-writer, and ux-designer. Verify that split against the files rather than taking it from this story — it was measured on 2026-08-01 and agent frontmatter changes.

## Dependencies
- **Blocked by**: E-280-02 (the tier table AC-8 keys off). OQ-A is closed.
- **Blocks**: **E-280-07** — its AC-1c verifies layer-wide that the "unstaged = current story" invariant is gone, and AC-15 here removes this file's instances. **E-280-08** — its AC-11 verifies layer-wide that no numeric trigger count survives, and AC-14 here removes `product-manager.md`'s. Both are verification stories that read what this one writes.

## Files to Create or Modify
- `.claude/agents/code-reviewer.md` (modify — report schema + tier keying)
- `.claude/agents/product-manager.md` (modify)
- `.claude/agents/claude-architect.md` (modify)
- `.claude/agents/software-engineer.md` (modify)
- `.claude/agents/data-engineer.md` (modify)
- `.claude/agents/api-scout.md` (modify)
- `.claude/agents/baseball-coach.md` (modify)
- `.claude/agents/docs-writer.md` (modify)
- `.claude/agents/ux-designer.md` (modify)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The AC-2 per-file verdict list is committed as an artifact
- [ ] No regressions in existing tests

## Notes
This story adds lines to `.claude/agents`, forecast at roughly +40. **Record the delta as a diagnostic reading and nothing more.** The context-layer size gate was retired by operator ruling on 2026-08-02 (epic OQ-1/OQ-B), so there is no baseline to clear, no offset owed, and no exception to seek — and specifically, **do not manufacture deletions elsewhere in `.claude/agents/` to pay for the schemas.** The delta feeds the epic's closure reading per TN-4(a); OQ-2 is closed.
