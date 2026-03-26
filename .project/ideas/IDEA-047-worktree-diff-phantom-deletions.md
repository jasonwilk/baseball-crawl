# IDEA-047: Epic Worktree `git diff main` Shows Phantom File Deletions

## Status
`CANDIDATE`

## Summary
During E-161 dispatch, `git diff main` from the epic worktree showed deletions for E-162/E-163 directories and modifications to PM memory/IDEA-046/README that don't exist in the worktree's staging area. `git status` correctly showed only 8 staged files, but `git diff main` reported 19 files changed including phantom deletions. Root cause unclear -- possibly related to rtk proxy rewriting git output, or a subtle git worktree state issue.

## Why It Matters
Misleading diff output wastes review cycles -- both Codex and code-reviewer investigated phantom changes during E-161 review, generating a false-positive P1 regression flag. Could cause real data loss if the closure merge ever includes phantom deletions, though the current closure merge uses `git diff --binary --cached main` which appears correct (only staged files).

## Rough Timing
Low urgency. The actual closure merge path is not affected (uses `--cached`), so the risk is limited to review noise. Worth understanding when a convenient investigation window opens.

## Dependencies & Blockers
- [ ] None -- investigation can happen anytime

## Open Questions
- Is rtk (token-optimized CLI proxy) rewriting git diff output in a way that changes the file list?
- Is this a known git worktree behavior when main has untracked/uncommitted files that the worktree branch doesn't have?
- Does `git diff main` vs `git diff --cached main` account for the full discrepancy, or is there something else at play?
- Should the implement skill's closure sequence use a different diff command for review validation?

## Notes
- Discovered during E-161 dispatch (2026-03-26)
- The closure merge sequence already uses `git diff --binary --cached main` (correct), so the operational risk is low
- Codex flagged this as a P1 "regression" during code review -- it was a false positive caused by the misleading diff

---
Created: 2026-03-26
Last reviewed: 2026-03-26
Review by: 2026-06-24
