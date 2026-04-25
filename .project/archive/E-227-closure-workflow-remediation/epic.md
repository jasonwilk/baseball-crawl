# E-227: Closure Workflow Structural Remediation

## Status
`COMPLETED`

## Overview
Restructure the implement skill's Phase 5 closure sequence to produce a single atomic commit (feat changes + archive rename + PM memory update) — eliminating a cycle dependency with the `.claude/hooks/epic-archive-check.sh` pre-commit hook and the structural fragility exposed during E-226's own closure. Also add a committed-plan check to the implement skill's Prerequisites so dispatch cannot create an epic worktree from a HEAD that lacks the plan.

## Background & Context

During E-226 closure on 2026-04-20, four workflow failures surfaced while executing the very approval gate E-226 was codifying:

1. **Plan commit missing.** Planning PM for E-226 wrote the epic files and updated PM memory but never committed them. Dispatch created the epic worktree from main HEAD, which did not contain the plan files — dispatch PM could not find her own epic files. Main session improvised by committing on main and destroying + rebuilding the worktree.
2. **Hook vs. Phase 5 ordering conflict.** `.claude/hooks/epic-archive-check.sh` denies any `git commit` while an unarchived `COMPLETED`/`ABANDONED` epic sits under `/epics/`. Phase 5 Step 2 flips status to COMPLETED; Step 8 then tries to commit before Step 9 archives — so Step 8's commit is structurally blocked by the hook. Main session improvised by moving `git mv` before the commit, folding Step 9 into Step 8 and making Step 11 (archive commit) a no-op.
3. **Worktree cleanup skipped.** `git worktree remove` + `git branch -D epic/E-NNN` is buried as sub-step 9 inside Step 8's closure merge sequence. When the outer step got improvised around failure #2, the buried sub-step was dropped — E-226's worktree and branch remained on disk until manually cleaned up during E-227 planning.
4. **Pre-closure approval gate near-miss.** The very pattern E-226 was codifying was nearly skipped during E-226's own closure.

Root-cause classification:
- **F2 and F3 are structural.** The Phase 5 step sequence is incompatible with the hook's invariant, and buried sub-steps do not survive sequence improvisation.
- **F1 is a codification gap.** Plan skill Step 2a is correctly designed (atomic planning commit with user approval); the implement skill's Prerequisites does not backstop the invariant that the plan must be committed before the epic worktree is created.
- **F4 is a symptom of F2 + F3 cycle dependencies.** Resolved by fixing the structure.

**Expert consultation:** claude-architect consulted with context-fundamentals discipline on the skill/hook interaction; proposed the 2-story shape and design decisions (option A over option B, archive-before-commit, worktree cleanup as first-class step). PM framed ACs against CA's design.

## Goals
- Eliminate the structural conflict between Phase 5's closure sequence and `.claude/hooks/epic-archive-check.sh` so Phase 5 executes without requiring main-session improvisation.
- Prevent dispatch from creating an epic worktree that branches from a HEAD lacking the plan files.
- Reduce Phase 5's top-level step count and remove nested sub-steps for critical mechanics (worktree cleanup, approval gate), so each step is independently verifiable after completion.

## Non-Goals
- **Modifying `.claude/hooks/epic-archive-check.sh`.** The "epic-aware hook" option (parsing commit messages to exempt a specific epic) was rejected as fragile — commit messages can arrive via `-m`, `-F`, or template, and the two-commit pattern was a skill-writing artifact, not a design goal. Archive-before-commit fixes the root cause structurally.
- **Adding a defense-in-depth closure checklist.** Structural promotion of worktree cleanup to a first-class step is sufficient to prevent F3 recurrence. Mixing discipline-based enforcement on top of structural enforcement adds complexity without proportional benefit. Revisit only if F3 recurs.
- **Modifying plan skill Step 2a.** The plan skill's atomic planning commit is correctly designed (user approval, skip behavior, compound-dispatch downgrade). The fix for F1 lives at the implement-skill backstop.
- **Modifying per-story CR + PM gate in Phase 3.** This works correctly; not a problem area.

## Success Criteria
- Phase 5 produces exactly one commit per epic closure — a `feat(E-NNN): <epic title>` commit containing the closure merge patch, the archive `git mv`, and the PM memory update. No separate `chore(E-NNN): archive epic` commit exists.
- `.claude/hooks/epic-archive-check.sh` does not fire on the restructured Phase 5 sequence, because the archive rename runs before `git commit`.
- Worktree cleanup (`git worktree remove <path>` and `git branch -D epic/E-NNN`) runs as a first-class numbered Phase 5 step, not a nested sub-step. After closure, neither the worktree directory nor the branch exists.
- Dispatch via standalone "implement E-NNN" refuses to proceed when `git status --porcelain -- epics/E-NNN-slug/` is non-empty. The refusal message lists the uncommitted files and provides a concrete remediation command.
- Dispatch via the plan skill's compound-trigger handoff path continues to work unchanged (skip condition for the committed-plan check).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-227-01 | Phase 5 closure restructure (atomic single-commit) | DONE | None | claude-architect |
| E-227-02 | Dispatch prerequisites: committed-plan check | DONE | None | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: E-226 closure failure sequence (source of truth)

Captured by team-lead during E-226 closure on 2026-04-20. See Background & Context for the four observed failures. The main session's improvisations (committing the plan on main, destroying + rebuilding the E-226 worktree; folding `git mv` into Step 8's commit) are the working models this epic codifies structurally. E-226's own completion summary already flagged the two-commit structure as an approximate pattern and a low-priority refinement candidate; E-227 is that follow-up.

### TN-2: Design decision — option A (archive-before-commit) vs. option B (epic-aware hook)

**Option A (chosen):** Move `git mv` archive rename before the closure commit so the epic is no longer under `/epics/*/epic.md` by the time `git commit` runs. Collapse old Steps 8/9/10/11 into one atomic commit. The hook sees a clean state and passes; no hook change needed.

**Option B (rejected):** Parse the commit message in `.claude/hooks/epic-archive-check.sh` to extract `E-NNN` and exempt that epic from the stale-epic check. Rejected because commit messages can be supplied via `-m`, `-F`, a template, or a commit-msg hook — parsing is fragile, and the two-commit pattern (`feat` then `chore`) was a skill-writing artifact rather than a design goal.

Git history is cleaner with one `feat(E-NNN): <title>` commit per epic. The archive directory at `.project/archive/` is the navigational anchor for completed epics, not the commit log, so losing the `chore(E-NNN): archive epic` convention has no downstream tooling impact.

### TN-3: Restructured Phase 5 sequence (Story 1 specification)

The restructure affects only the existing top-level Steps 8-12 of Phase 5. Steps 1-7a (validate, epic completion + review scorecard, doc + context-layer assessments, ideas + vision review, present summary, implementer shutdown, ancillary file sweep) are unchanged.

**New Step 8 — Closure merge and commit** (atomic single-commit sequence):
1. Migration merge-time scan (preserved from current Step 8).
2. Clean-tree preflight: verify the main checkout has no unstaged or untracked changes (preserved from current Step 8 — ensures Step 7a captured all loose files).
3. From the epic worktree: `git add -A` (stage accumulated changes), then `git diff --binary --cached main > /tmp/E-NNN-epic.patch`.
4. From the main checkout: `git apply --check --3way /tmp/E-NNN-epic.patch` (dry-run), then `git apply --3way /tmp/E-NNN-epic.patch` (apply for real).
5. `git mv epics/E-NNN-slug/ .project/archive/E-NNN-slug/` — the archive rename happens on disk in the main checkout before staging.
6. PM updates `.claude/agent-memory/product-manager/MEMORY.md` (move epic from Active Epics to Archived Epics). PM writes to the main checkout path; this is allowed by `.claude/hooks/worktree-guard.sh:57` which exempts `.claude/agent-memory/*` from the dispatch-active denylist.
7. `git add -A` in the main checkout (stage the applied patch + archive rename + PM memory update).
8. **Explicit user approval gate** (preserved verbatim from E-226): present `git diff --cached --stat main`, wait for exactly one of "yes", "commit", "approve", or "go ahead". Any other response — including silence, questions, "looks good", "ok", "sure", "👍" — does NOT count as approval.
9. `git commit -m "feat(E-NNN): <epic title>"`. The `.claude/hooks/epic-archive-check.sh` hook passes because the epic file is no longer at `epics/*/epic.md` (it was renamed in sub-step 5).

**New Step 9 — Worktree cleanup** (first-class top-level step):
- `cd /workspaces/baseball-crawl && git worktree remove /tmp/.worktrees/baseball-crawl-E-NNN && git branch -D epic/E-NNN`.
- Independently verifiable: after this step, `ls /tmp/.worktrees/` does not include `baseball-crawl-E-NNN/` and `git branch --list 'epic/E-NNN'` is empty.

**New Step 10 — Shut down PM and delete team** (renumbered from current Step 12):
- Send `shutdown_request` to PM, wait for confirmation, delete team.

Old top-level Steps 9 (archive), 10 (PM memory), and 11 (archive commit) no longer exist as separate top-level steps. The `chore(E-NNN): archive epic` commit convention is removed.

Phase 5 goes from 12 top-level steps to 10.

### TN-4: PM memory timing and hook compatibility

PM has always written memory updates to the main-checkout path `.claude/agent-memory/product-manager/MEMORY.md` (not the epic worktree). This is documented in the existing PM spawn context: "Exception: `.claude/agent-memory/product-manager/` (your persistent memory in the main checkout)".

`.claude/hooks/worktree-guard.sh:55-59` explicitly exempts `.claude/agent-memory/*` from the dispatch-active denylist. PM's Write/Edit to this path passes the hook even while the epic worktree exists.

The only behavioral change introduced by Story 1 is the **timing** of the PM memory update: it moves from "between two commits" (current Step 10 sitting between Steps 8 and 11) to "before `git add -A` inside the single atomic commit" (new Step 8 sub-step 6). The write target and hook behavior are unchanged.

### TN-5: Committed-plan check specification (Story 2)

Add a new clause to the implement skill's Prerequisites section, after the existing epic-status check and before Phase 0:

> **3. The epic's plan is committed.** Run `cd /workspaces/baseball-crawl && git status --porcelain -- epics/E-NNN-slug/`. If the output is non-empty, the plan has uncommitted changes and dispatching would create the epic worktree from a HEAD that lacks the plan files. Refuse dispatch with a message that:
> - Lists each uncommitted file path from the `git status --porcelain` output
> - Provides a concrete remediation command (e.g., `git add epics/E-NNN-slug/ && git commit -m "feat(E-NNN): plan <title> (READY)"`) before retrying
>
> **Handoff exception:** This check is skipped when the implement skill was loaded via plan skill Phase 5 Step 3c handoff (the compound-trigger "plan and dispatch" path). On that path, plan skill Step 2a already owns the commit invariant. The check runs on the standalone "implement E-NNN" invocation path.

The check does NOT auto-commit. User approval for planning commits is preserved at plan skill Step 2a.

### TN-6: `handoff_from_plan` is narrative — verification strategy

The `handoff_from_plan` flag is set by plan skill at `.claude/skills/plan/SKILL.md:598` and read in 6 places in the implement skill (lines 22, 32, 75, 77, 86, 88, 575). Enforcement is instruction-level — the main session tracks the flag across skill loads; there is no shell variable, file, or runtime container for it.

Story 2 AC-3 is therefore framed in terms of the **trigger pattern** ("loaded via plan skill Phase 5 Step 3c handoff / compound trigger 'plan and dispatch'") rather than the abstract flag. This makes verification trigger-pattern-based: during code review, verify that the Prerequisites clause's skip condition is documented in terms of the trigger pattern; during actual dispatch, the main session applies the skip by narrative convention — which is how every other `handoff_from_plan` branch in the implement skill works today.

### TN-7: Expected file touches

Story 1 touches:
- `.claude/skills/implement/SKILL.md` — Phase 5 rewrite (current Steps 8-12 consolidated to new Steps 8-10); Workflow Summary block (~lines 568-595); Anti-Pattern #5 cross-reference ("Phase 5 Step 8's closure merge sequence (sequence step 7)" updated to the new approval-gate location).
- `.claude/rules/dispatch-pattern.md` — line 42's "Git commands for archive (`git mv`, `git add`, `git commit`)" bullet is removed or merged into the closure-merge bullet at line 40, because the archive rename is now part of the closure merge and no separate archive commit exists. Lines 8 and 12's main-session operation paragraphs may need a light touch if they reference separate archive-commit mechanics.

Story 2 touches:
- `.claude/skills/implement/SKILL.md` — Prerequisites section adds a third numbered clause (committed-plan check). Workflow Summary's Prerequisites block updated if it enumerates prerequisite checks.

Both stories touch `.claude/skills/implement/SKILL.md`, so they have file overlap. Running Story 1 first (larger Phase 5 rewrite) followed by Story 2 (small Prerequisites addition) minimizes merge friction within the epic.

### TN-8: Workflow Summary and Anti-Pattern #5 cross-references

The implement skill's Workflow Summary currently reads (at Phase 5):
```
Phase 5: Validate -> PM completes epic -> doc + context-layer assessments -> summary
  -> shut down implementers + CR -> ancillary file sweep (stage session artifacts, user approval)
  -> closure merge (patch -> dry-run -> apply -> approval gate -> single commit incl. ancillary files)
  -> archive -> PM memory -> archive commit -> shut down PM + delete team
```

This needs to be rewritten to reflect the new sequence. Target shape:
```
Phase 5: Validate -> PM completes epic -> doc + context-layer assessments -> summary
  -> shut down implementers + CR -> ancillary file sweep (stage session artifacts, user approval)
  -> closure merge and commit (patch -> dry-run -> apply -> archive mv -> PM memory -> approval gate -> single commit)
  -> worktree cleanup -> shut down PM + delete team
```

Anti-Pattern #5 currently reads: "Do not commit automatically. The user must explicitly approve the closure commit. See the approval gate in Phase 5 Step 8's closure merge sequence (sequence step 7)." The "sequence step 7" reference points at the current Step 8 sub-step numbering, which changes. The updated reference should point at the new approval-gate location in the restructured Step 8.

## Open Questions
- None. CA's design review converged on all design decisions before READY.

## History
- 2026-04-20: Created after E-226 closure exposed structural Phase 5 failures. CA (claude-architect) diagnosed root causes and proposed the 2-story shape; PM framed ACs.
- 2026-04-20: Set to READY after PM quality checklist passed and team-lead approved the plan summary. Two clarifications resolved before READY: PM memory timing (already covered by `.claude/hooks/worktree-guard.sh:57` exemption — only the *timing* of the write changes) and `handoff_from_plan` framing (narrative flag; Story 2 AC-3 framed in terms of the trigger pattern per TN-6). One additional Story 1 AC added for archive-directory happy-path verification (AC-10).

- 2026-04-25: **COMPLETED.** Phase 5 closure restructure (E-227-01) and Prerequisites committed-plan check (E-227-02) both delivered. Phase 5 shrinks from 12 to 10 top-level steps; closure produces a single atomic `feat(E-NNN)` commit instead of two; worktree cleanup is now a first-class numbered step; the `.claude/hooks/epic-archive-check.sh` cycle dependency is eliminated structurally; the implement skill backstops the plan-commit invariant on the standalone path while preserving the plan-skill handoff exception. Two Codex Priority 1 findings remediated during closure: `git worktree remove --force` (cleanup couldn't succeed without the flag because the worktree retains staged changes after the closure commit) and a documented reject-restoration sequence (the gate now sits after `git mv` + PM memory update, so 'abort' must restore via `git reset HEAD`, `git mv` back, and `git checkout -- .`).

  ### Dispatch process notes
  This epic's dispatch was severely degraded — it was paused for 4 days, then resumed under broken-agent conditions: claude-architect spawn went into a corrupted state on Story 2 (dumping minified JS internals instead of executing edits), software-engineer fallback exhibited the same failure, and the product-manager agent stopped sending text replies after Story 1's AC verification. The user explicitly authorized "limp through this" and the main session made E-227-02's edit and the two Codex remediations directly as a one-time exception. AC verification for E-227-02 and the Phase 4a CR integration review were both performed by the main session for the same reason. This violates the standard agent-routing pattern (Anti-Pattern #1) but was the only way to ship the structural fixes that protect future epics from the same dispatch-time failures.

  ### Review Scorecard
  | Review Pass | Findings | Accepted | Dismissed |
  |---|---|---|---|
  | Per-story CR -- E-227-01 | 0 | 0 | 0 (context-layer only, skipped) |
  | Per-story CR -- E-227-02 | 0 | 0 | 0 (context-layer only, skipped) |
  | PM AC verification -- E-227-01 | 10 | 10 PASS | 0 |
  | PM AC verification -- E-227-02 | 5 | 5 PASS | 0 (verified by main session due to agent failure) |
  | CR integration review (Phase 4a) | 0 | 0 | 0 (skipped due to agent failure) |
  | Codex code review (Phase 4b) | 2 | 2 | 0 |
  | **Total** | **17** | **17** | **0** |

  ### Documentation Assessment (2026-04-25)
  No documentation impact. Internal dispatch workflow change. `docs/admin/` and `docs/coaching/` unaffected.

  ### Context-Layer Assessment (2026-04-25)
  1. New convention, pattern, or constraint established: **YES**. Phase 5 single-commit closure is the new convention; old two-commit (`feat` + `chore`) pattern is removed. Plan-commit invariant codified at Prerequisites level.
  2. Architectural decision with ongoing implications: **YES**. Option A (archive-before-commit) over Option B (epic-aware hook parsing); aligns Phase 5 with the existing `.claude/hooks/epic-archive-check.sh` invariant rather than weakening it.
  3. Footgun, failure mode, or boundary discovered: **YES**. The skill/hook cycle dependency was the discovered footgun. Codification IS the epic's deliverable.
  4. Change to agent behavior, routing, or coordination: **NO**. Routing tables and agent definitions unchanged.
  5. Domain knowledge discovered that should influence agent decisions in future epics: **NO** (process knowledge, not domain).
  6. New CLI command, workflow, or operational procedure introduced: **NO**.

  Triggers 1, 2, 3 fire — but the epic's deliverable IS the codification. No additional claude-architect dispatch needed (and CA was non-functional anyway).
