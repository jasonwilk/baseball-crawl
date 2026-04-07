# E-215-02: Duplicate Player Detection Query and CLI

## Epic
[E-215: Fix Player-Level Duplicates from Cross-Perspective Boxscore Loading](epic.md)

## Status
`DONE`

## Description
After this story is complete, a detection function will identify same-team duplicate player pairs using the prefix-matching signal described in TN-2. A CLI command `bb data dedup-players --dry-run` will report all detected pairs with their canonical/duplicate assignment per TN-3. The `--dry-run` flag is the default (no data modification).

## Context
Before merging duplicates, we need reliable detection. The matching signal (same team roster, same last name, first name is prefix of the other) has been validated against production data showing 120 same-team pairs and 527 total pairs. This story builds the detection layer that E-215-03 depends on for its merge targets.

## Acceptance Criteria
- [ ] **AC-1**: A function `find_duplicate_players(db, team_id=None, season_id=None)` in `src/db/player_dedup.py` returns a list of distinct `(canonical_player_id, duplicate_player_id, team_id, reason)` tuples following the detection signal in TN-2. Results are deduplicated to unique (canonical, duplicate) pairs -- if a pair appears across multiple seasons on the same team, it is returned once. When `team_id` and/or `season_id` are provided, results are scoped to that team/season only.
- [ ] **AC-2**: Canonical selection follows TN-3: longer first_name wins; ties broken by total stat row count, then alphabetical player_id.
- [ ] **AC-3**: Given two players on the same team with last_name="Holbein", first_names "O" and "Oliver", the function returns the pair with "Oliver" as canonical.
- [ ] **AC-4**: Given two players on the same team with last_name="Smith" and first_names "Rob" and "Robert", the function correctly flags them as duplicates ("Rob" is a prefix of "Robert"). Given two players with last_name="Smith" and first_names "Mike" and "Mark", the function does NOT flag them (neither is a prefix of the other).
- [ ] **AC-5**: Given two players with the same last_name but on DIFFERENT teams, the function does NOT flag them as duplicates.
- [ ] **AC-6**: `bb data dedup-players` CLI command exists with `--dry-run` (default) that prints detected pairs in a human-readable table format showing: canonical name, duplicate name, team name, reason, and a confidence indicator. Pairs with zero overlapping game appearances are flagged as "low confidence" to help the operator spot potential false positives (e.g., brothers on the same team).
- [ ] **AC-7**: `bb data dedup-players --dry-run` exits cleanly with a summary count (e.g., "Found 120 duplicate pairs across N teams").
- [ ] **AC-8**: Unit tests cover true-positive (prefix match), true-negative (different teams), true-negative (same last name but unrelated first names), and the canonical selection tiebreaker logic.

## Technical Approach
Create `src/db/player_dedup.py` with the detection query. The query joins `team_rosters` to itself on `(team_id, season_id)` and `players` on both sides, filtering by case-insensitive last_name match and first_name prefix relationship (using LIKE with the shorter name as pattern). Canonical selection is inline in the query using LENGTH comparison and stat-count subqueries. The CLI wrapper goes in `src/cli/data.py` as a new `dedup-players` subcommand following the pattern of the existing `dedup` command.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-215-03

## Files to Create or Modify
- `src/db/player_dedup.py` (CREATE)
- `src/cli/data.py` (MODIFY -- add `dedup-players` command)
- `tests/test_player_dedup.py` (CREATE -- unit tests for detection)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-215-03**: The `find_duplicate_players()` function provides the list of (canonical, duplicate) pairs that the merge function iterates over.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The detection query should be efficient enough to run on the full database (thousands of players). The team_rosters self-join scoped by (team_id, season_id) keeps the search space small.
- The detection query must guard `LENGTH(first_name) > 0` on the shorter name to avoid empty/blank first names matching as a prefix of everything (per TN-2).
- AC-4 clarification: "Rob" IS a 3-character prefix of "Robert" (starts with "Rob"), so this would correctly be flagged. But "Mike" and "Mark" would not be flagged since neither is a prefix of the other.
- **Confidence indicator definition** (AC-6): "Overlapping game appearances" means both player_ids in the pair have rows in `player_game_batting` or `player_game_pitching` for at least one common `game_id`. Pairs with zero overlap may be false positives (e.g., brothers on the same team) since there is no game-level evidence that both UUIDs represent the same person.
