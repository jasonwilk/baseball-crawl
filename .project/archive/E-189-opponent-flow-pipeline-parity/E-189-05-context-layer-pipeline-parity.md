# E-189-05: Context-layer: codify pipeline parity requirement

## Epic
[E-189: Opponent Flow Pipeline and Display Parity](epic.md)

## Status
`DONE`

## Description
After this story is complete, the context layer will document the requirement that the web scouting pipeline (`run_scouting_sync`) and CLI scouting pipeline (`bb data scout`) must produce equivalent data artifacts. Future changes to either pipeline must maintain parity.

## Context
The web and CLI scouting pipelines diverged silently because there was no documented requirement for parity. Story 01 and 02 fix the current divergence; this story prevents future drift by codifying the convention in the context layer.

## Acceptance Criteria
- [ ] **AC-1**: CLAUDE.md Architecture section documents that `run_scouting_sync` and `bb data scout` must produce equivalent data artifacts (scouting stats + spray charts + gc_uuid resolution)
- [ ] **AC-2**: CLAUDE.md Architecture section documents the auto-scout trigger pattern: when opponents are resolved (whether via admin UI, search, or auto-resolver during member sync), scouting is triggered automatically
- [ ] **AC-3**: The `bb data scout` command description in CLAUDE.md Commands section reflects the full pipeline stages (crawl, load, gc_uuid resolution, spray crawl, spray load)

## Technical Approach
Update CLAUDE.md's Architecture section and Commands section. May also update the background pipeline trigger description or add a scoped rule if appropriate.

## Dependencies
- **Blocked by**: E-189-01, E-189-02 (context documents implemented behavior)
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md` -- update Architecture and Commands sections
- Possibly `.claude/rules/` -- add a scoped rule for pipeline parity if the architect deems it appropriate

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Context layer accurately reflects the implemented pipeline behavior
- [ ] No stale references to previous pipeline state
