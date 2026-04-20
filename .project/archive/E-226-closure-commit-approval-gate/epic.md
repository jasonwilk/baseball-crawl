# E-226: Closure Commit Approval Gate Enforcement

## Status
`COMPLETED`

## Overview
Restructure the implement skill's Phase 5 closure sequence so the user-approval gate before the closure `git commit` is a first-class, visually distinct numbered step -- not a compressed prose aside. Add a preflight anomaly check to the archive commit to surface unexpected files before they ride along (the archive commit itself remains a mechanical follow-up to the already-approved closure commit and does not get its own approval gate). Prevents the main session from interpreting the closure sequence as a continuous 8-step pipe-through that auto-commits without explicit user sign-off.

## Background & Context
During E-225 dispatch, the main session ran `git commit` at epic closure without pausing to present the staged diff (`git diff --cached --stat main`) and wait for explicit user approval. The user flagged this as a cornerstone workflow violation -- approval before the closure commit is non-negotiable.

The approval rule already exists in the skill, but it is not structurally enforced inside the numbered closure sequence:

- In `.claude/skills/implement/SKILL.md` Phase 5 Step 8, the current sequence lists `git add -A` and `git commit` as consecutive numbered steps (step 6 and step 7). The approval-gate language lives in a trailing prose paragraph ("User must explicitly approve before commit. Only 'yes', 'commit', 'approve', 'go ahead' proceed.") below the numbered list.
- Anti-Pattern #5 ("Do not commit automatically") reinforces the rule but is far from the step where the violation occurs.
- User memory `feedback_closure_commit_approval.md`: "Always pause before the closure `git commit` and present the staged diff summary (`git diff --cached --stat main`) to the user for explicit approval."

Consultation with claude-architect confirmed the minimal fix: promote the pause to a first-class numbered step parallel to the other steps in the closure sequence. The gate step names the exact command, enumerates the required approval words, and spells out what counts as non-approval (silence, questions, ambiguous acks). A lighter refinement is applied to Phase 5 Step 11 (archive commit), which currently chains `git add -A && git commit` on one line: unchain the commit, add a preflight `git status --porcelain` anomaly check, and document that the archive commit is a mechanical follow-up to the already-approved closure commit. The archive commit does NOT get its own approval gate -- team-lead confirmed the archival is deterministic (only captures Step 9's `git mv` and Step 10's PM memory update) and gating it would add friction without safety value.

## Goals
- Make the closure-commit approval gate a structurally enforced numbered step in the implement skill, not a prose aside.
- Add a preflight anomaly check to the archive commit (Phase 5 Step 11) and unchain `git commit` from `git add -A` so anomalies can be surfaced between staging and committing.
- Keep the Workflow Summary and Anti-Pattern cross-references aligned with the restructured sequence.

## Non-Goals
- No changes to `.claude/rules/dispatch-pattern.md` (it defers procedure to the skill).
- No changes to Phase 4 review remediation, Phase 3 staging boundary, or Step 7a (ancillary file sweep). Step 7a already has the correct shape -- new Step 7 mirrors its template for consistency, but Step 7a is not touched.
- No new hooks, scripts, or enforcement infrastructure outside the skill text itself.

## Success Criteria
After this epic, a main session re-reading the closure sequence must not be able to interpret it as a continuous run-through:

- The closure-commit approval gate is a distinct numbered step, not a prose aside.
- The closure gate names the exact command to present (`git diff --cached --stat main`) and the exact approval words.
- The closure gate states explicitly that silence, questions, or ambiguous acknowledgments are not approval.
- The closure `git commit` appears only after the gate step -- never chained with `git add -A`.
- The archive `git commit` is no longer chained with `git add -A` via `&&` on a single line; Step 11 includes a preflight `git status --porcelain` anomaly check and a one-line clarification that it inherits the Step 8 approval.
- Workflow Summary and Anti-Pattern #5 reference the new structure accurately.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-226-01 | Enforce closure commit approval gate in implement skill | DONE | None | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

**TN-1: Current Phase 5 Step 8 sequence (the surface to change).**

In `.claude/skills/implement/SKILL.md`, the "Closure merge sequence" under Phase 5 Step 8 currently reads (paraphrased for reference; implementer must verify against the live file):

```
1. cd <epic-worktree-path> && git add -A
2. cd <epic-worktree-path> && git diff --binary --cached main > /tmp/E-NNN-epic.patch
3. cd /workspaces/baseball-crawl && git apply --check --3way /tmp/E-NNN-epic.patch
4. If dry-run succeeds: git apply --3way /tmp/E-NNN-epic.patch
5. PII scan (pre-commit hook covers this automatically)
6. git add -A, present staged changes, ask for explicit user approval
7. git commit -m "feat(E-NNN): <epic title>"
8. git worktree remove <epic-worktree-path> && git branch -D epic/E-NNN

**User must explicitly approve** before commit. Only "yes", "commit", "approve", "go ahead" proceed.

**If the user rejects the commit**: Pause. Epic worktree preserved. User can: ...
```

**TN-2: Target Phase 5 Step 8 sequence.**

Restructure so the approval gate is a first-class numbered step parallel to the others. The target shape (implementer has final authority on exact prose):

```
1. cd <epic-worktree-path> && git add -A (stage all accumulated changes)
2. cd <epic-worktree-path> && git diff --binary --cached main > /tmp/E-NNN-epic.patch
3. cd /workspaces/baseball-crawl && git apply --check --3way /tmp/E-NNN-epic.patch (dry-run)
4. If dry-run succeeds: git apply --3way /tmp/E-NNN-epic.patch (apply for real)
5. PII scan (pre-commit hook covers this automatically)
6. git add -A (stage applied patch on main checkout)
7. **Pause for explicit user approval.** Run `git diff --cached --stat main` and present the file count and insertion/deletion totals to the user. Wait for "yes" / "commit" / "approve" / "go ahead". Any other response -- including silence, questions, or ambiguous acknowledgments -- is not approval. Do not proceed to step 8 until an explicit approval word is received.
8. git commit -m "feat(E-NNN): <epic title>"
9. git worktree remove <epic-worktree-path> && git branch -D epic/E-NNN
```

Delete the trailing "User must explicitly approve" prose paragraph -- its content is now inside step 7. Preserve the "If the user rejects the commit" paragraph as a sub-bullet under step 7.

Mirror Step 7a's existing structural template (bold "Present staged changes" / "User approval" / "User rejects" sub-headers) at the new Step 7. This unifies the two approval gates by having the new step conform to Step 7a's shape. Step 7a itself is NOT modified.

**TN-3: Target Phase 5 Step 11 (archive commit).**

Current state: Step 11 is a single line reading roughly `git add -A && git commit -m "chore(E-NNN): archive epic"`. No preflight, no anomaly detection.

Target: Step 11 is NOT given a separate approval gate -- it is a deterministic, mechanical follow-up to the already-approved closure commit. It only captures Step 9's `git mv` and Step 10's PM memory update. Instead, restructure into sub-steps that add a preflight anomaly check:

- **Preflight**: Run `cd /workspaces/baseball-crawl && git status --porcelain`. Report any staged/unstaged file whose path does NOT start with `.project/archive/` or `.claude/agent-memory/product-manager/` to the user before proceeding. If any anomalies are reported, pause for user direction (do NOT proceed with `git add -A` on anomalous files).
- Stage the archive changes (`git add -A`).
- `git commit -m "chore(E-NNN): archive epic"`.

Add a one-line clarification above or below the sub-steps: "No separate approval gate -- the archive commit is a mechanical follow-up to the approved closure commit (Step 8). The preflight check exists to catch unexpected files; it is not a blanket diff review."

The archive commit is no longer chained via `&&` on a single line (so anomalies can be surfaced between staging and committing), but it is NOT gated by the explicit approval words from Step 7.

**TN-4: Workflow Summary update.**

The Workflow Summary near the bottom of the skill currently includes a closure-sequence line of the form `patch -> dry-run -> apply -> single commit`. Update it to reflect the approval gate, e.g., `patch -> dry-run -> apply -> approval gate -> single commit`. Verify the full closure-sequence line still matches the restructured Phase 5 -- including archive references if present.

**TN-5: Anti-Pattern #5 cross-reference.**

Anti-Pattern #5 ("Do not commit automatically. The user must explicitly approve the closure commit.") stays structurally correct. Add a pointer to the numbered gate step so a reader following the anti-pattern lands at the enforcement point, e.g., "See Phase 5 Step 8's step 7 approval gate."

**TN-6: Approval wording (closure gate only).**

The approval words in the new Step 7 (closure commit gate) MUST be exactly "yes" / "commit" / "approve" / "go ahead" -- from the user feedback memory. Step 11 (archive commit) does NOT have an approval gate under this epic, so the approval-wording constraint does not apply to it. Step 7a (ancillary file sweep) is NOT modified; if its existing approval wording diverges from the canonical set, note the divergence in the story completion report for possible follow-up capture, but do NOT modify Step 7a (out of scope).

**TN-7: Scope discipline.**

Only `.claude/skills/implement/SKILL.md` is modified. No rule files, no other skills, no hooks. If the implementer identifies related cleanup opportunities (e.g., inconsistencies elsewhere in the skill), report them for follow-up capture rather than modifying them in this epic.

## Open Questions
- None.

## History
- 2026-04-19: Created after E-225 dispatch closure-commit violation. Team-lead briefed; CA consulted on skill edit shape; plan approved; set to READY.
- 2026-04-20: COMPLETED. Single story E-226-01 implemented by claude-architect; PM verified all 12 ACs PASS. Phase 4a CR integration review and Phase 4b Codex review both run with remediation. What was accomplished:
  - Restructured Phase 5 Step 8 closure merge sequence — the user-approval gate is now a first-class numbered step (the new step 7) parallel to the other numbered steps. The gate names the exact command `git diff --cached --stat main`, the four required approval words ("yes", "commit", "approve", "go ahead"), and the explicit non-approval list (silence, questions, ambiguous acknowledgments).
  - Restructured Phase 5 Step 11 archive commit — `git add -A` and `git commit` are unchained (no longer `&&`-joined on a single line), and a preflight `git status --porcelain` anomaly check was added with tight rename-record validation (allow-listed paths only: `.project/archive/`, `.claude/agent-memory/product-manager/`). Documented as a mechanical follow-up to the approved closure commit; no separate approval gate.
  - Workflow Summary closure-sequence line updated to include the approval gate ("...apply -> approval gate -> single commit incl. ancillary files").
  - Anti-Pattern #5 ("Do not commit automatically") cross-references the new step 7 approval gate.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-226-01 | 0 | 0 | 0 (context-layer only, skipped) |
| PM AC verification | 12 | 12 PASS | 0 |
| CR integration review (Phase 4a) | 3 | 3 | 0 |
| Codex code review (Phase 4b) | 2 | 1 | 1 |
| **Total** | **17** | **16** | **1** |

**Review notes:**
- Phase 4a CR: 3 SHOULD FIX — all valid, all fixed. (1) disambiguated "step 8" reference; (2) reworded Anti-Pattern #5 cross-reference; (3) added rename-record handling to the Step 11 preflight.
- Phase 4b Codex: 2 findings — 1 Priority 1 (rename exception too broad) fixed by tightening to a both-sides path constraint; 1 Priority 5 (staged epic/story file edits violate AC-12) dismissed as false positive per user memory `feedback_staged_diff_verification.md` — PM status updates to story/epic files are normal dispatch workflow artifacts, not implementation changes governed by AC-12.

**Follow-up observation (out of scope this epic):** Step 7a's existing approval words at line ~501 are "yes", "approve", "go ahead" (no "commit") — differs from the new Step 7's four-word set ("yes", "commit", "approve", "go ahead"). Per epic Technical Notes TN-6, Step 7a was explicitly out of scope for this epic. A future epic could align Step 7a's wording with Step 7 if desired (low-priority consistency cleanup).

### Documentation Assessment (2026-04-20)
No documentation impact. Internal dispatch workflow change, not user-facing. `docs/admin/` and `docs/coaching/` unaffected.

### Context-Layer Assessment (2026-04-20)
1. New convention, pattern, or constraint established: **NO.** The approval-before-commit rule already existed; this epic restructured its presentation, did not introduce a new convention.
2. Architectural decision with ongoing implications: **NO.**
3. Footgun, failure mode, or boundary discovered: **YES.** The E-225 auto-commit violation is the discovered footgun. Codification is the epic's own output — the skill edit (Step 7 approval gate, Anti-Pattern #5 cross-reference) IS the context-layer safeguard. No additional claude-architect dispatch needed.
4. Change to agent behavior, routing, or coordination: **NO.**
5. Domain knowledge discovered that should influence agent decisions: **NO.**
6. New CLI command, workflow, or operational procedure introduced: **NO.**

Trigger 3 fires but the epic's deliverable IS the codification. No additional context-layer work required.
