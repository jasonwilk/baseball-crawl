# IDEA-013: cmux Evaluation for Agent Teams

## Status
`CANDIDATE`

## Summary
Evaluate whether cmux adds meaningful value beyond iTerm2 + tmux for heavy Agent Teams sessions. cmux positions itself as a terminal app built for coding agents with workspace organization, hooks, and notifications. The consensus plan (DISCUSSION-terminal-setup.md) explicitly deferred this as Phase 5.

## Why It Matters
If cmux provides better multi-agent session visibility, crash recovery, or workspace organization than raw iTerm2 + tmux, it could reduce cognitive overhead during heavy dispatches with 3-5+ agents. The operator currently uses in-process Agent Teams mode and has not yet adopted tmux-based sessions.

## Rough Timing
After the operator has used the iTerm2 + tmux workflow for at least a few heavy Agent Teams sessions. The trigger is: "I can describe one concrete problem cmux solves better than iTerm2 + tmux." If no such problem surfaces, this idea should be discarded.

## Dependencies & Blockers
- [ ] E-066 (devcontainer terminal setup) must be complete -- tmux installed and configured
- [ ] Operator must have run at least a few Heavy-mode Agent Teams sessions via iTerm2 + tmux
- [ ] cmux must still be actively maintained at evaluation time

## Open Questions
- Does cmux support attaching into a devcontainer shell, or does it assume direct host execution?
- Does cmux's workspace model conflict with the existing project structure?
- Is cmux stable enough for a single-developer project, or is it still early-stage?

## Notes
- Source: Phase 5 of the consensus plan in `DISCUSSION-terminal-setup.md`
- Both proposals (Claude Code and Codex) agreed to defer cmux
- cmux site: https://cmux.dev/

---
Created: 2026-03-07
Last reviewed: 2026-03-07
Review by: 2026-06-07
