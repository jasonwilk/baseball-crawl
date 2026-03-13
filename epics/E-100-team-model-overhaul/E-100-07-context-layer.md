# E-100-07: Context-Layer Updates

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, all context-layer files will reflect the new team model: programs as a first-class entity, membership_type replacing is_owned, classification/Division replacing level, team_opponents junction table, INTEGER PK for teams, TeamRef pattern, and the two-phase add-team flow. CLAUDE.md sections on data model, admin UI, and key metrics will be updated. Migration rules will reflect the new migration numbering.

## Context
This is the final story in the epic, ensuring the context layer accurately describes the implemented reality. Multiple CLAUDE.md sections reference the old model: the data model section references `is_owned`, the architecture section uses TEXT team_id patterns, and the migration rules need the updated sequence.

## Acceptance Criteria
- [ ] **AC-1**: `CLAUDE.md` data model references updated: `is_owned` → `membership_type`, `level` → `classification`/Division, programs concept documented, team_opponents table mentioned alongside opponent_links, INTEGER PK for teams documented, TeamRef pattern noted.
- [ ] **AC-2**: `CLAUDE.md` admin UI references reflect the two-phase add-team flow and program-grouped team list (if any such references exist).
- [ ] **AC-3**: `/.claude/rules/migrations.md` numbering section updated to reflect the clean schema rewrite (migration 001 is the complete schema; old 001-008 archived).
- [ ] **AC-4**: Any agent definitions or rules that reference `is_owned`, `level`, or the old team model are updated to reflect the new terminology.
- [ ] **AC-5**: The PM's MEMORY.md "Key Architectural Decisions" section is updated with the programs/membership_type/classification model, team_opponents split, and INTEGER PK for teams.

## Technical Approach
Read all context-layer files that reference team model concepts and update them to reflect the new reality. Focus on accuracy — CLAUDE.md describes current implemented state, not future plans.

## Dependencies
- **Blocked by**: E-100-01 through E-100-06 (all implementation must be complete)
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
- [ ] No regressions in existing tests (N/A — no code changes)

## Notes
- The PM MEMORY.md update (AC-5) is an exception to the normal "main session updates PM memory" rule — it's explicitly assigned here because the data model section needs a comprehensive rewrite that's better done by the agent reading the full migration.
- Do NOT update dashboard or coaching docs with program-awareness — that's out of scope (Non-Goals). Only update to reflect INTEGER PK and is_owned→membership_type changes.
