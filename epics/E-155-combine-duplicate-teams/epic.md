# E-155: Combine Duplicate Teams

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Provide an admin "combine teams" feature that detects and merges duplicate opponent rows in the `teams` table. Duplicate teams destroy coaching trust: a coach sees "Lincoln East" twice, one with stats and one blank, and doesn't know which to trust. This epic gives the operator (Jason) the tools to spot duplicates and merge them into a single canonical team, reassigning all FK references atomically.

## Background & Context
The same real-world opponent can appear as multiple `teams` rows due to four independent creation paths:
1. The schedule loader (E-153-02) creates stub teams when `resolved_team_id` is NULL in `opponent_links`
2. OpponentResolver creates resolved teams with real GC UUIDs via a separate code path
3. Manual admin linking via the opponent connect page can create yet another entry
4. Different `root_team_id` values in GameChanger can map to the same real school

The result: a coach sees "Lincoln East" multiple times in their schedule/opponents view. The completed game against Lincoln East doesn't link to the scouted version. There is currently no way to fix this.

**Expert consultations:**
- **baseball-coach**: Duplicate teams destroy coaching trust fast. Pre-game review (the night before or 30 minutes before first pitch) is when coaches notice and it's the worst possible time. Auto-detection is a MUST HAVE. Season year is the merge guard -- same-season teams merge, cross-year teams are distinct. Coaches should never see or deal with duplicates; this is purely an admin task.
- **data-engineer**: Full FK chain analysis across 16 references in 13 tables. Single atomic transaction required. Canonical team wins on conflicts (never sum stats). UNIQUE constraint conflicts must be resolved before FK reassignment. Self-reference guards needed for `opponent_links` and `team_opponents`. Hard delete the duplicate after merge.

## Goals
- Admin can identify potential duplicate teams via exact-name matching on the admin team list
- Admin can merge any two teams (pick canonical, absorb duplicate) with full FK reassignment
- All 16 FK references across 13 tables are correctly handled in a single atomic transaction
- Pre-merge validation prevents data-loss scenarios (self-reference violations, member-team guard)
- After merge, coaches see one unified team with all games, stats, and scouting data

## Non-Goals
- Fuzzy name matching (follow-up idea: IDEA-043)
- Prevention of duplicate creation at the source (follow-up idea: IDEA-044)
- Season stats recomputation after merge (next pipeline sync handles this)
- Audit trail / admin_events table (low-volume operation, skip for MVP)
- Merging member teams (blocked by default; future consideration)

## Success Criteria
- An admin viewing the team list sees a "Potential Duplicates" banner when exact-name matches exist among tracked teams in the same season year
- The admin can select two teams and execute a merge that atomically reassigns all FK references from the duplicate to the canonical team and hard-deletes the duplicate
- Pre-merge validation blocks unsafe merges (nonexistent teams, self-merge, member teams) and auto-removes self-referencing rows during conflict resolution
- A pre-merge summary shows the admin exactly what will happen (game count, conflict count, identifier status) before confirmation
- Existing tests pass; new tests cover the merge logic and edge cases

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-155-01 | Team merge core logic | TODO | None | - |
| E-155-02 | Duplicate detection query | TODO | E-155-01 | - |
| E-155-03 | Admin merge UI | TODO | E-155-01, E-155-02 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: FK Reference Chain
The complete set of tables referencing `teams.id` (16 FK columns across 13 tables):

| Table | FK Column(s) | UNIQUE Constraint | Conflict Resolution |
|-------|-------------|-------------------|---------------------|
| `team_opponents` | `our_team_id`, `opponent_team_id` | UNIQUE(our_team_id, opponent_team_id), CHECK(our != opponent) | Delete duplicate's conflicting rows |
| `team_rosters` | `team_id` | PK(team_id, player_id, season_id) | Delete duplicate's conflicting rows |
| `games` | `home_team_id`, `away_team_id` | None | Direct UPDATE |
| `player_game_batting` | `team_id` | UNIQUE(game_id, player_id) -- team_id not in UNIQUE | Direct UPDATE |
| `player_game_pitching` | `team_id` | UNIQUE(game_id, player_id) -- team_id not in UNIQUE | Direct UPDATE |
| `player_season_batting` | `team_id` | UNIQUE(player_id, team_id, season_id) | Delete duplicate's conflicting rows |
| `player_season_pitching` | `team_id` | UNIQUE(player_id, team_id, season_id) | Delete duplicate's conflicting rows |
| `spray_charts` | `team_id` | None (nullable FK) | Direct UPDATE |
| `opponent_links` | `our_team_id`, `resolved_team_id` | UNIQUE(our_team_id, root_team_id) | Delete duplicate's conflicting rows; auto-delete self-referencing rows |
| `scouting_runs` | `team_id` | UNIQUE(team_id, season_id, run_type) | Delete duplicate's conflicting rows |
| `user_team_access` | `team_id` | UNIQUE(user_id, team_id) | Delete duplicate's conflicting rows |
| `coaching_assignments` | `team_id` | UNIQUE(user_id, team_id) | Delete duplicate's conflicting rows |
| `crawl_jobs` | `team_id` | None | Direct UPDATE |

### TN-2: Merge Transaction Protocol
All merge operations execute in a single `BEGIN IMMEDIATE` transaction. Order of operations:

1. Read duplicate's `gc_uuid`, `public_id`, `name` for identifier copying
2. Run all blocking pre-merge checks (may be outside transaction)
3. `BEGIN IMMEDIATE`
4. Clear duplicate's identifiers to avoid partial unique index collision: `UPDATE teams SET gc_uuid = NULL, public_id = NULL WHERE id = :duplicate_id`
5. Copy identifiers to canonical: `UPDATE teams SET gc_uuid = COALESCE(gc_uuid, :dup_gc_uuid), public_id = COALESCE(public_id, :dup_public_id) WHERE id = :canonical_id`
6. Delete conflicting rows from each UNIQUE-constrained table (canonical wins)
7. UPDATE all FK columns in all 13 tables (`duplicate_id` → `canonical_id`)
8. `DELETE FROM teams WHERE id = :duplicate_id`
9. `COMMIT`

Rollback on any exception = nothing happened.

### TN-3: Pre-Merge Validation

**Blocking checks** (merge refused if any fail):
1. Both `canonical_id` and `duplicate_id` exist in `teams`
2. `canonical_id != duplicate_id`
3. Member-team guard: if duplicate has `membership_type = 'member'`, block the merge

**Self-reference auto-deletion** (handled in conflict-resolution step, not blocking):
Self-referencing rows in `opponent_links` and `team_opponents` are auto-deleted during the conflict-resolution step (TN-2 step 6) rather than blocking the merge. These rows are semantically nonsensical after merge (a team cannot be its own opponent or resolve to itself) and blocking would prevent exactly the merges this epic exists to enable (e.g., canonical member team has the duplicate stub listed as a tracked opponent).

Both tables require **bidirectional** detection:
- `opponent_links`: (a) rows where `resolved_team_id = duplicate_id AND our_team_id = canonical_id`, and (b) rows where `our_team_id = duplicate_id AND resolved_team_id = canonical_id`. Note: no CHECK constraint exists -- this is a **logical correctness** cleanup.
- `team_opponents`: (a) rows where `opponent_team_id = duplicate_id AND our_team_id = canonical_id`, and (b) rows where `our_team_id = duplicate_id AND opponent_team_id = canonical_id`. Note: `CHECK(our_team_id != opponent_team_id)` exists -- failing to auto-delete these would cause a SQL error during the FK UPDATE step.

The preview (E-155-01 AC-2) surfaces the count of self-referencing rows that will be removed.

**Warning checks** (shown to admin, require confirmation):
1. Per-table conflict counts (rows that will be dropped because canonical already has data for that slot)
2. `gc_uuid` or `public_id` mismatch between canonical and duplicate (may not be the same team)
3. Game count being reassigned
4. Duplicate has `our_team_id` entries in `opponent_links` (was treated as member)
5. Games between canonical and duplicate: if any games exist where one team is `home_team_id` and the other is `away_team_id`, this is a strong signal the two teams are NOT the same real-world team (they played each other). Display: "These teams have N game(s) against each other. Are you sure they represent the same real-world team?"

### TN-4: Canonical Wins Rule
When both the canonical and duplicate team have rows for the same slot (same player+season, same user, etc.), the canonical team's row is kept and the duplicate's conflicting row is deleted. Stats are never summed or merged -- that would double-count games. Non-conflicting rows from the duplicate are reassigned to the canonical team.

### TN-5: Duplicate Detection
Exact name match among tracked teams (`membership_type = 'tracked'`) with the same `season_year` (or both NULL). Member teams are excluded from auto-detection. The query groups teams by normalized name (case-insensitive) and season year, returning groups with 2+ matches.

**Known limitation**: Teams with NULL vs non-NULL `season_year` are NOT flagged as duplicates (e.g., a stub with `season_year=NULL` and a resolved team with `season_year=2026`). This is a likely real-world scenario since stubs created by the schedule loader may lack `season_year`. The admin must spot these manually. Fuzzy matching (IDEA-043) will address this gap.

### TN-6: Identifier Gap-Filling
Before deleting the duplicate, copy its `gc_uuid` and `public_id` to the canonical team where the canonical's value is NULL. If both are non-null and different, surface the mismatch as a warning -- it's a signal the two rows might not be the same team.

**Critical implementation detail**: The `teams` table has partial unique indexes on `gc_uuid` and `public_id` (`WHERE ... IS NOT NULL`). Copying the duplicate's identifier to the canonical while the duplicate row still exists would violate the unique index. The merge transaction must first NULL out the duplicate's identifiers (TN-2 step 4), then copy to canonical (TN-2 step 5). The duplicate's values are captured in Python variables before the transaction begins (TN-2 step 1).

## Open Questions
None -- all resolved during discovery.

## History
- 2026-03-25: Created. Expert consultation with baseball-coach and data-engineer complete.
- 2026-03-25: Review iteration 1. Incorporated 12 findings from CR, coach, DE, PM. Fixed FK count (16/13), identifier gap-fill UNIQUE violation (split-step in TN-2), symmetric self-reference guard (TN-3), games-against-self warning (TN-3), NULL season_year gap (TN-5), post-merge sync prompt (E-155-03), stat richness signal (E-155-02/03).
- 2026-03-25: Review iteration 2. Incorporated 5 findings (3 PM + 2 CR). Converted self-reference checks from blocking to auto-delete (product decision: blocking would prevent the primary merge scenario). Added bidirectional language to team_opponents. Added has_stats to E-155-02 AC-1. Fixed sync button to form-POST. Added server-side reload pattern for preview page. Blocking checks reduced from 5 to 3.
- 2026-03-25: Review iteration 3 (circuit breaker). Incorporated 2 stale-wording fixes (CR-1: TN-1 opponent_links conflict resolution column, PM-6: Success Criteria bullet). Consistency sweep clean.
- 2026-03-25: Codex spec review iteration 1. Incorporated 3 findings: P1-1 (3+ team group UX -- pairwise merge from N-team list), P1-2 (AC-7 reworded to account for deleted rows), P2-1 (TN-3 warning #4 surfaced in preview payload and UI).
- 2026-03-25: Set to READY. 24 findings across 7 review passes, all accepted, 0 dismissed.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 6 | 6 | 0 |
| Internal iteration 1 -- Holistic (Coach+DE+PM) | 7 | 7 | 0 |
| Internal iteration 2 -- CR spec audit | 3 | 3 | 0 |
| Internal iteration 2 -- Holistic (PM+DE) | 3 | 3 | 0 |
| Internal iteration 3 -- CR spec audit | 1 | 1 | 0 |
| Internal iteration 3 -- Holistic (PM) | 1 | 1 | 0 |
| Codex iteration 1 | 3 | 3 | 0 |
| **Total** | **24** | **24** | **0** |
