# E-100-06: Context-Layer Updates

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`DONE`

## Description
After this story is complete, all context-layer files will reflect the new team model: programs, membership_type replacing is_owned, classification/Division replacing level, team_opponents junction, INTEGER PK for teams, TeamRef pattern, enriched stat columns, spray_charts table, and the two-phase add-team flow. CLAUDE.md sections on data model, admin UI, and key metrics will be updated. Migration rules will reflect the new numbering.

## Context
Final story in the epic — ensures the context layer accurately describes the implemented reality. Multiple CLAUDE.md sections reference the old model. This is a clean update, not a nuanced migration — the old model is gone.

## Acceptance Criteria
- [ ] **AC-1**: `CLAUDE.md` data model references updated: `is_owned` -> `membership_type`, `level` -> `classification`/Division, programs documented, team_opponents documented, INTEGER PK for teams documented, TeamRef pattern noted, enriched columns (game_stream_id, batting_order, pitches/strikes, bats/throws, split columns, spray_charts) documented.
- [ ] **AC-2**: `CLAUDE.md` admin UI references reflect the two-phase add-team flow and flat team list.
- [ ] **AC-3**: `/.claude/rules/migrations.md` updated to reflect the clean schema rewrite: migration 001 is the complete schema, old 001-008 archived, next migration number is `002`, unused-slot language removed.
- [ ] **AC-4**: Run `grep -rn 'is_owned\|\.level\b\|is_owned_team' CLAUDE.md .claude/agents/ .claude/rules/` and update every match that describes the old team model (`teams.is_owned`, `teams.level`, `is_owned_team_public_id`, TEXT PK convention). Agent memory files (`.claude/agent-memory/`) are excluded — historical context in completed-epic entries does not need updating. The AC is done when the grep returns no matches in the named paths.
- [ ] **AC-5**: The PM's MEMORY.md updated: (a) "Key Architectural Decisions" section updated with programs/membership_type/classification model, team_opponents, INTEGER PK, enriched stat columns; (b) "Active Epics" E-100 entry updated to reflect the completed implementation.

## Technical Approach
Read all context-layer files referencing team model concepts and update to reflect the new reality. CLAUDE.md describes current implemented state, not future plans.

## Dependencies
- **Blocked by**: E-100-03, E-100-04, E-100-05 (all implementation must be complete)
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md`
- `.claude/rules/migrations.md`
- `.claude/agent-memory/product-manager/MEMORY.md`
- Any other context-layer files referencing team model concepts (discovered during implementation)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- The PM MEMORY.md update (AC-5) is an exception to the normal "main session updates PM memory" rule — explicitly assigned here because the data model section needs a comprehensive rewrite.
- Do NOT update dashboard or coaching docs with program-awareness — out of scope. Only update for INTEGER PK and is_owned -> membership_type changes.
- Document enriched columns as "schema-ready, not yet populated" to avoid implying they contain data.
