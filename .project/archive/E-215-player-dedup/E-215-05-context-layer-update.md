# E-215-05: Context-Layer Update for Player Dedup Patterns

## Epic
[E-215: Fix Player-Level Duplicates from Cross-Perspective Boxscore Loading](epic.md)

## Status
`DONE`

## Description
After this story is complete, the context layer (CLAUDE.md, scoped rules, agent memory) will document the patterns, conventions, and rough edges discovered during E-215. This ensures all agents and the operator understand the cross-perspective UUID behavior, the new canonical player upsert pattern, the dedup CLI command, and the known gaps in the self-healing pipeline.

## Context
E-215 introduced several conventions and discovered several API/pipeline behaviors that agents working with player data need to know. Without codifying these, future epics risk re-discovering the same issues or building on incorrect assumptions (e.g., assuming `gc_athlete_profile_id` works, or being surprised by the merge-every-run cycle).

## Acceptance Criteria
- [ ] **AC-1**: CLAUDE.md Architecture section documents `ensure_player_row()` in `src/db/players.py` as the canonical path for all player INSERTs, analogous to `ensure_team_row()` for teams. Includes the constraint that new player-INSERT paths MUST use this function.
- [ ] **AC-2**: CLAUDE.md Commands section documents `bb data dedup-players` with `--dry-run` (default) and `--execute` flags, including a brief description of what it does.
- [ ] **AC-3**: A scoped rule or CLAUDE.md note documents the GC cross-perspective player UUID behavior: the API returns different `player_id` UUIDs for the same human depending on which team's boxscore is viewed. This is a permanent API property, not a bug. All agents working with player data must account for this.
- [ ] **AC-4**: A scoped rule or CLAUDE.md note documents that `players.gc_athlete_profile_id` exists in the schema but is never populated by any loader. It awaits E-104 probe results. Agents must not assume it contains data.
- [ ] **AC-5**: A scoped rule or CLAUDE.md note documents the merge-every-run cycle as expected behavior: the post-load dedup sweep re-detects and re-merges pairs on every scouting run because crawled data still contains cross-perspective UUIDs. This is self-healing, not a bug.
- [ ] **AC-6**: A scoped rule or CLAUDE.md note documents the plays pipeline dedup gap: plays are loaded independently from `bb data scout`. Cross-perspective player stubs from plays data are cleaned up by the next `bb data scout` run or manual `bb data dedup-players --execute`.

## Technical Approach
The claude-architect reads the epic Technical Notes (TN-1 through TN-9) and the completed story artifacts, then decides the optimal placement for each item across CLAUDE.md, scoped rules, and agent memory. The architect owns context-layer file placement decisions per the project's context-layer guard rule.

## Dependencies
- **Blocked by**: E-215-04 (all implementation stories must be complete before codifying patterns)
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md` (MODIFY -- Architecture section: canonical player upsert; Commands section: dedup-players CLI)
- `.claude/rules/data-model.md` or new scoped rule (MODIFY/CREATE -- cross-perspective UUID behavior, gc_athlete_profile_id status, merge-every-run cycle, plays pipeline gap)
- `.claude/agent-memory/product-manager/MEMORY.md` (MODIFY -- update data model notes with player dedup patterns)

## Agent Hint
claude-architect

## Handoff Context
N/A -- this is the final story in the epic.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Context-layer files updated per the architect's placement decisions
- [ ] No regressions in existing context-layer content

## Notes
- The architect has final authority on where each item is placed (CLAUDE.md vs scoped rule vs agent memory). The ACs specify WHAT must be documented, not WHERE exactly.
- Items AC-3 through AC-6 document behaviors that are permanent (AC-3, AC-5, AC-6) or long-lived (AC-4, until E-104 ships). They are not ephemeral findings.
