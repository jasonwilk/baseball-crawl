# E-037: Codex Review Remediation

## Status
`COMPLETED`

## Overview
Fix bugs and spec inconsistencies discovered by Codex code review of commits 321c592 (E-003 schema) and a7bc374 (E-002 refinement). Two code bugs silently break the dashboard on migrated databases. Two spec bugs make loader stories impossible to implement under FK enforcement. One minor spec clarification improves dependency clarity. Stale "soft referential integrity" language in context-layer files is corrected to match the actual FK-enforced schema.

## Background & Context
Codex reviewed two commits and produced six findings. PM validation (2026-03-03) confirmed four valid findings, one false positive, and one partially valid finding.

**Validated findings:**
1. **P1 (code)**: `src/api/db.py` queries `psb.season` but the column was renamed to `season_id` in E-003-01. Dashboard silently returns empty results.
2. **P2 (code)**: `src/api/routes/dashboard.py` passes `"2026"` as the season value, but the schema uses slugs like `"2026-spring-hs"`. No rows match even after fixing the column name.
3. **P1 (spec)**: E-002-07a AC-4 requires writing orphan-player game stats, but `player_game_batting` has an FK to `players(player_id)` and `PRAGMA foreign_keys=ON` rejects the insert.
4. **P1 (spec)**: E-002-07b AC-4 has the same FK conflict for `player_season_batting` and `player_season_pitching`.
5. **P2 (spec)**: E-002-08 Notes reference `RosterLoader` from E-002-06 but E-002-06 is not a listed dependency.

**False positive (no action):**
- Finding 5 (E-023-05 `require_admin`): Codex claimed returning Response from `Depends()` doesn't short-circuit. In the shipped code, `_require_admin` is NOT a FastAPI dependency -- it is called manually with explicit `isinstance(guard, Response)` checks. The implementation is correct.

No expert consultation required -- these are straightforward bug fixes and spec corrections against existing code and story files.

## Goals
- Dashboard query returns correct results on migrated databases with seed data
- Dashboard uses the season_id slug format matching the schema
- E-002-07a and E-002-07b AC-4 are implementable given FK enforcement
- E-002-08 dependency list is complete
- Context-layer files (agent defs, agent memory) describe the correct orphan-player handling strategy

## Non-Goals
- Redesigning the dashboard season selection UX (future E-004 work)
- Changing the FK enforcement strategy globally
- Modifying any E-023 (auth) code or specs (Finding 5 was false positive)

## Success Criteria
- `get_team_batting_stats()` query uses `season_id` column name and the dashboard passes a season_id slug
- After rebuilding and seeding, `curl http://localhost:8001/dashboard` returns player rows (not empty)
- E-002-07a AC-4 and E-002-07b AC-4 are rewritten to be compatible with FK constraints
- E-002-08 dependencies mention E-002-06 as a soft dependency for load.py
- No live context-layer files contain "soft referential integrity" language (grep verification)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-037-01 | Fix dashboard query column name and season_id format | DONE | None | general-dev |
| E-037-02 | Fix E-002 loader stories FK conflict in orphan-player ACs | DONE | None | general-dev |
| E-037-03 | Add E-002-06 soft dependency to E-002-08 | DONE | None | general-dev |
| E-037-04 | Update context-layer references from "soft referential integrity" to stub-player pattern | DONE | None | claude-architect |

## Technical Notes

### Finding 1+2: Dashboard column name and season format
The root cause is that E-003-01 renamed `season TEXT` to `season_id TEXT REFERENCES seasons(season_id)` across all tables, but the dashboard code in `src/api/db.py` and `src/api/routes/dashboard.py` was not updated to match.

Two changes required:
1. `src/api/db.py` line 85: `psb.season` -> `psb.season_id`
2. `src/api/routes/dashboard.py` line 85: The `season = str(datetime.date.today().year)` pattern must produce a season_id slug. The simplest fix that matches the current data model: derive the default season_id from the current year and the `spring-hs` season type (the primary use case). This produces `"2026-spring-hs"`. A more sophisticated season selector belongs in E-004 (dashboard epic), not here.
3. The `get_team_batting_stats` function signature should change `season` parameter to `season_id` with a matching default.

### Finding 3+4: FK enforcement vs. orphan-player soft writes
The schema has FK constraints on `player_id` in `player_game_batting`, `player_game_pitching`, `player_season_batting`, and `player_season_pitching`. The `get_connection()` function enables `PRAGMA foreign_keys=ON`. AC-4 in both E-002-07a and E-002-07b says "the stat row is still written" for orphan players -- this is impossible with FKs enabled.

The correct resolution (consistent with the project's "automate what a coach does" philosophy): when a loader encounters a player_id not in `players`, it should INSERT a stub row into `players` (player_id, first_name="Unknown", last_name="Unknown") before inserting the stat row. This preserves referential integrity while not losing stat data. A WARNING is still logged so the operator knows a player needs to be backfilled.

This is a spec-only change -- rewrite AC-4 in both story files.

### Finding 6: E-002-08 loader dependency
E-002-08 Notes say `scripts/load.py` "Initially includes the roster loader (E-002-06)" but the Dependencies section does not mention E-002-06. The fix is to add a note in the Dependencies section clarifying that `load.py` benefits from E-002-06 being DONE but should gracefully handle its absence.

### Context-layer staleness: "soft referential integrity"
Multiple agent definition and memory files describe an orphan-player handling pattern ("soft referential integrity -- accept orphaned player IDs with WARNING, do not reject") that is incompatible with the delivered schema. These must be updated to describe the stub-player pattern. Files affected: `.claude/agents/general-dev.md`, `.claude/agents/data-engineer.md`, and four agent memory files. Archived files are frozen and not modified.

### False Positive Documentation: E-023-05 require_admin
Finding 5 claimed `_require_admin` returns Response objects from a `Depends()`, which would not short-circuit. In the shipped code (`src/api/routes/admin.py`), `_require_admin` is called manually (not via `Depends()`), and every route checks `isinstance(guard, Response)` before proceeding. The implementation is correct. No action required.

## Open Questions
None.

## History
- 2026-03-03: Created from Codex review findings. PM validated 4 valid, 1 partially valid, 1 false positive. Set to READY.
- 2026-03-04: All 4 stories dispatched in parallel (no inter-story dependencies). All completed and verified.
  - E-037-01 (DONE): Fixed `psb.season` -> `psb.season_id` in db.py query, changed season default from `"2026"` to `f"{year}-spring-hs"` in dashboard route. Updated 2 test files. 385 tests pass.
  - E-037-02 (DONE): Rewrote AC-4 in E-002-07a and E-002-07b from impossible "soft write" to FK-safe stub-player pattern. Updated DoD test descriptions.
  - E-037-03 (DONE): Added soft dependency note for E-002-06 to E-002-08 Dependencies section.
  - E-037-04 (DONE): Updated 6 context-layer files (2 agent defs, 4 agent memory files) from "soft referential integrity" to stub-player pattern. Grep verification confirms zero stale matches. Also updated ABANDONED E-002-07.md.
  - No documentation impact (no new features, no architecture changes, no schema changes, no new agents).
  - Epic set to COMPLETED and archived.
