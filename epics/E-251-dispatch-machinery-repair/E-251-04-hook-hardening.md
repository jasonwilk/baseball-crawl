# E-251-04: Hook hardening — worktree-guard normalization, commit-regex gaps, pii-check labeling

## Epic
[E-251: Dispatch-Machinery Repair](../E-251-dispatch-machinery-repair/epic.md)

## Status
`TODO`

## Description
After this story is complete, three hook correctness defects are fixed: `worktree-guard.sh` normalizes paths so a double-slash form cannot bypass the guard, the commit-interception logic covers `git -C` invocation forms, and `pii-check.sh` distinguishes a scanner infrastructure failure from an actual PII detection in its reporting.

## Context
These are three independent audit §2 findings clustered in `.claude/hooks/`. Each defeats a control's intent: a path-normalization gap lets a write slip past the worktree guard, a regex gap lets a `git -C` commit form evade interception, and mislabeling every scanner crash as "PII detected" trains operators to distrust or ignore the signal (and hides real scanner breakage). Per epic TN-5.

## Acceptance Criteria
- [ ] **AC-1** (worktree-guard normalization): `worktree-guard.sh` normalizes the target path before its guard comparison so that a double-slash path form (e.g. `src//foo.py`) is treated identically to its single-slash form in BOTH modes (dispatch-active and no-dispatch). Verifiable outcome: a double-slash path that maps to a guarded location is blocked where the single-slash form would be blocked.
- [ ] **AC-2** (commit-interception `git -C`): the commit-interception logic covers `git -C <dir> commit` invocation forms, not only plain `git commit`. The epic-archive gate (`epic-archive-check.sh`) and any companion commit-interception hook no longer have a `git -C` blind spot. Verifiable outcome: a `git -C` commit form is intercepted where the plain form would be.
- [ ] **AC-3** (pii-check labeling): `pii-check.sh` reports a scanner infrastructure failure (scanner crash, missing interpreter, unexpected non-zero from the scanner itself) with a message distinct from an actual PII detection — it does not label an infra failure as "PII detected." CA determines the exact wording and whether the exit semantics for the two cases should differ.
- [ ] **AC-4**: Each fix preserves the hook's existing intended enforcement (no control is loosened) and the hooks still pass their own smoke behavior; the code-reviewer confirms the normalization, regex, and labeling changes do what the ACs describe.

## Technical Approach
Per epic TN-5. Three localized edits across `worktree-guard.sh`, the commit-interception hook(s) / `epic-archive-check.sh`, and `pii-check.sh`. CA determines the normalization approach, the regex form for `git -C`, and the failure-labeling wording. Do not change what the hooks enforce — only close the bypass/labeling gaps.

**Implementation guidance from CA's design review (2026-07-04):**
- The commit-interception regex lives in BOTH `pii-check.sh` AND `epic-archive-check.sh` — the `git -C` coverage fix must land in BOTH (the Files-to-Modify list already reflects this).
- For AC-3, the PII scanner exits `1` for an actual violation AND also exits non-zero when it CRASHES (infra failure) — so exit code alone cannot distinguish "found a credential" from "the scanner broke." The infra-failure-vs-detection fix must pattern-match the scanner's OUTPUT, not rely on the exit code.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/hooks/worktree-guard.sh` — path normalization before guard comparison
- `.claude/hooks/epic-archive-check.sh` — commit-interception `git -C` coverage (carries the same `git\s+commit` interception regex as pii-check.sh)
- `.claude/hooks/pii-check.sh` — commit-interception `git -C` coverage (same regex as epic-archive-check.sh) AND distinguish scanner infra failure from PII detection in reporting

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Self-contained fixes (audit file is uncommitted). Audit ref: §2 LOW "Context layer" cluster — "worktree-guard does no path normalization (double-slash bypass in both modes); commit-interception regexes miss `git -C` forms (epic-archive gate has no second layer); pii-check.sh reports every scanner infra failure as 'PII detected'."
