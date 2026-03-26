# IDEA-045: Detect Main-Branch Divergence Before Epic Closure Patch

## Status
`CANDIDATE`

## Summary
During epic dispatch, main can advance (concurrent sessions landing other epics) while the worktree is running. The closure procedure's `git diff --cached main` then shows those intervening commits as apparent "deletions" — correct git behavior, but a silent footgun. Add a divergence check before generating the closure patch so the operator gets an explicit warning instead of a confusing diff.

## Why It Matters
Without a warning, the closure diff looks like the epic is deleting code it never touched. The operator must manually reason about whether those deletions are regressions or just main-branch drift. An explicit heads-up ("main advanced N commits since dispatch started") turns this from a debugging puzzle into an expected condition with a known workaround (path-filtered patch).

## Rough Timing
- Small enough to fold into the implement skill's context-layer assessment during a future dispatch
- No urgency — the targeted-patch workaround already handles it
- Trigger: next time someone encounters this during closure and is confused

## Dependencies & Blockers
- [ ] None — purely a context-layer enhancement to `.claude/skills/implement/SKILL.md`

## Open Questions
- Should the check auto-switch to a path-filtered patch, or just warn and let the operator decide?
- Should the warning include the list of intervening commits for context?

## Notes
- Discovered during E-160 dispatch (2026-03-26): main advanced 3 commits (E-158 landed concurrently) while the E-160 worktree was running
- The fix is a `git log epic/E-NNN..main --oneline` check in Phase 5 of the implement skill's closure sequence, before generating the patch
- Routes to claude-architect (context-layer change)

---
Created: 2026-03-26
Last reviewed: 2026-03-26
Review by: 2026-06-24
