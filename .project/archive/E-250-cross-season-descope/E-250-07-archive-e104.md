# E-250-07: Archive E-104 as ABANDONED

## Epic
[E-250: Root-Level Cross-Season / Multi-Season De-Scope](../E-250-cross-season-descope/epic.md)

## Status
`DONE`

## Description
After this story is complete, the still-READY athlete-profile identity-probe epic E-104 is marked ABANDONED (with reason) and archived from `/epics/` to `/.project/archive/`, closing the cross-team-identity direction that this epic's schema removals (E-250-02) foreclose.

## Context
E-104 (Athlete Profile Endpoint Probe) was the exploratory epic for cross-team player identity. That direction is a permanent non-goal (reports-first reframe, CLAUDE.md, `docs/ROADMAP.md`), and E-250-02 drops its schema anchor (`players.gc_athlete_profile_id`). `docs/ROADMAP.md:205` already directs "close the idea/epic." Leaving E-104 READY would leave a dispatchable epic for an abandoned direction. This is a PM housekeeping story — no code, no tests.

## Acceptance Criteria
- [ ] **AC-1**: `epics/E-104-athlete-profile-opponent-probe/epic.md` status is set to `ABANDONED` with a History entry stating the reason (cross-team identity permanently de-scoped; schema anchor dropped in E-250-02).
- [ ] **AC-2**: The entire `epics/E-104-athlete-profile-opponent-probe/` directory is moved to `/.project/archive/E-104-athlete-profile-opponent-probe/` (archive, never delete).
- [ ] **AC-3**: The PM memory index (`.claude/agent-memory/product-manager/MEMORY.md` Active Epics, and `archived-epics.md`) is updated to move E-104 from active to archived.

## Technical Approach
PM sets the ABANDONED status + History entry, then moves the directory to the archive. During dispatch this happens in the epic worktree; the move rides the closure patch into main. This is a status/archival action only.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-250-04 and E-250-05 (both write prose asserting E-104 IS abandoned; this archive must complete first so the assertion is true when those stories are DONE — Codex #3)

## Files to Create or Modify
- `epics/E-104-athlete-profile-opponent-probe/epic.md` — status → ABANDONED + History entry (moved to archive)
- `.claude/agent-memory/product-manager/MEMORY.md` — move E-104 active → archived
- `.claude/agent-memory/product-manager/archived-epics.md` — add E-104 abandonment line

## Agent Hint
product-manager

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
PM-owned housekeeping. Writes to PM's own agent-memory directory are the own-memory carve-out to the context-layer routing rule, so this stays with PM rather than routing to claude-architect.
