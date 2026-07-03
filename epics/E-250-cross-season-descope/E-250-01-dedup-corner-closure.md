# E-250-01: Player-dedup cross-season-execute corner closure

## Epic
[E-250: Root-Level Cross-Season / Multi-Season De-Scope](../E-250-cross-season-descope/epic.md)

## Status
`TODO`

## Description
After this story is complete, `bb data dedup-players` will auto-derive its `season_id` scope from the data (with an explicit `--season-id` override), and a cross-season merge will be unreachable by construction: `season_id` will be a required (non-`Optional`) argument on both `plan_player_dedup` and `find_duplicate_players`, so `season_id=None` cannot flow into the planner. This closes the one remaining E-249 corner where an unscoped CLI run could union prefix-pairs across seasons.

## Context
E-249 replaced the stale up-front merge worklist with per-`(team_id, season_id)` connected-components grouping, but a Phase-4b Codex finding noted that the CLI could still be invoked without a season scope. On the live single-season (2026) DB this is unreachable, but the input shape (`season_id=None`) is still representable in code. This story removes the representable-but-invalid shape at the root: the CLI derives the season, and the planner refuses `None`. The load path is unaffected — `scouting_loader` always passes a concrete `season_id`.

## Acceptance Criteria
- [ ] **AC-1**: Given a DB with exactly one distinct `season_id` in `team_rosters`, when `bb data dedup-players` runs without `--season-id`, then it derives and uses that season with no change in output or UX versus today (zero-UX-change on the live one-season DB).
- [ ] **AC-2**: Given a DB with zero distinct `season_id` values in `team_rosters`, when `bb data dedup-players` runs without `--season-id`, then it exits 0 (nothing to do) without error.
- [ ] **AC-3**: Given a DB with two or more distinct `season_id` values in `team_rosters`, when `bb data dedup-players` runs without `--season-id`, then it errors with a message listing the available seasons and exits non-zero; supplying `--season-id` selects that season and proceeds.
- [ ] **AC-4**: `season_id` is a required `str` parameter (not `Optional`/`None`-defaulted) on BOTH `plan_player_dedup` and `find_duplicate_players` in `src/db/player_dedup.py`; `season_id=None` is no longer a representable input.
- [ ] **AC-5**: The per-`(team_id, season_id)` partition structure and the `seen_collapse_keys` guard are RETAINED. The `seen_collapse_keys` comment is rewritten to state that it also prevents a cross-TEAM identical-collapse within one season (the `collapse_key` excludes `team_id`) — not only a cross-season collapse.
- [ ] **AC-6**: `TestCrossSeasonPartition` (`tests/test_player_dedup.py:1947`) is deleted (its input shape — `season_id=None` reaching the planner — is now unreachable). `TestSeasonDedup` (`tests/test_player_dedup.py:252`) is deleted or converted to a still-valid single-season contract.
- [ ] **AC-7**: The unscoped CLI test at `tests/test_cli_data.py:273` is replaced with the new contract: a single-season DB auto-derives (AC-1), and a multi-season DB without `--season-id` exits non-zero listing the seasons (AC-3, an error-path test).
- [ ] **AC-8**: The load path is verified unaffected — `dedup_team_players` / `scouting_loader` continue to pass a concrete `season_id`, and existing load-path dedup tests pass unchanged.
- [ ] **AC-9**: The E-249 CLI footguns are preserved (not regressed): the default-isolation recompute path retains its trailing `conn.commit()`, and the command exits non-zero on any failure (a merge failure, or the multi-season-without-`--season-id` error in AC-3).
- [ ] **AC-10**: Every existing call site of `plan_player_dedup` and `find_duplicate_players` is updated to pass a concrete `season_id` matching its fixture. SE enumerated 14 unscoped sites in `tests/test_player_dedup.py` across 7 classes — lines 159, 180, 193, 212 (TestPrefixMatch / PrefixVsNonPrefix / DifferentTeams), 303, 307 (TestFilters), 347, 366 (TestConfidenceIndicator), 385, 396, 401, 413 (TestEdgeCases), 1484, 1527 (TestCrossPerspectiveOverlapDetection) — none named by AC-6 (which covers only TestSeasonDedup:252 and TestCrossSeasonPartition:1947). Per the testing.md "contract change → stale tests are MUST-FIX" rule, each is updated deliberately, not left to surface as a red suite. A grep confirms no call to either function omits `season_id`, and the full suite is green.
- [ ] **AC-11**: When `--team-id` is passed, the distinct-`season_id` derivation is scoped to that team's `team_rosters` rows (not global); the 0/1/2+ rule (AC-1–AC-3) then applies within that team's scope. `--team-id` together with `--season-id` selects exactly that (team, season) scope.

## Technical Approach
The season derivation reads the distinct `season_id` set from `team_rosters` and applies the 0/1/2+ rule in AC-1–AC-3. Keep `--season-id` as an explicit override that short-circuits derivation. Making `season_id` required on the two `player_dedup` functions is a signature change; update the CLI call site (`src/cli/data.py`) accordingly so it always passes the derived-or-overridden season. The `seen_collapse_keys` guard stays exactly as-is behaviorally — only its comment changes. Do not alter the connected-components / fork-refusal logic.

Note: the context-layer edits this change implies (the `bb data dedup-players` sentence in CLAUDE.md, the E-249 known-limitation bullet in `.claude/rules/data-model.md`) are NOT in this story — they are owned by claude-architect in E-250-04 to respect the context-layer routing rule.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-250-02 (E-250-02 edits `test_player_dedup.py`/`test_cli_data.py` for `season_type`-fixture removal — same files this story edits; must run after, CR F4), E-250-04 (context-layer prose documents this story's shipped behavior)

## Files to Create or Modify
- `src/cli/data.py` — season auto-derivation + 0/1/2+ handling in `dedup-players`; `--team-id`-scoped derivation (AC-11)
- `src/db/player_dedup.py` — `season_id` required on `plan_player_dedup` and `find_duplicate_players`; `seen_collapse_keys` comment rewrite
- `tests/test_player_dedup.py` — delete `TestCrossSeasonPartition`; delete/convert `TestSeasonDedup`; AND add a concrete `season_id` to the 14 unscoped `plan_player_dedup`/`find_duplicate_players` call sites across 7 classes (AC-10 line list)
- `tests/test_cli_data.py` — replace the unscoped test with the new derive/error contract
- Any remaining call sites of `plan_player_dedup` / `find_duplicate_players` (SE: ~14 unscoped sites across CLI, load path, and tests) — updated to pass a concrete `season_id` (AC-10). Enumerate via grep; the exact file set is discovered during implementation.

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-250-04**: The final `bb data dedup-players` behavior (season derived/required) that CLAUDE.md's command sentence and the data-model.md E-249 bullet must describe.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This is the "E-249 corner root-closure" story: self-contained, no schema, do FIRST. See epic TN-1.

DESIGN LOCK: the required shape is auto-derive → exactly-1-season use it → 2+-seasons ERROR and require explicit `--season-id`. This is the USER-APPROVED decision that authorized the epic. Do NOT substitute a season-sequenced / self-healing multi-season execute LOOP (an alternative SE raised) — keeping a multi-season execute loop alive runs directly against the single-season de-scope this epic exists to deliver. When `--season-id` is explicitly passed it is a single season → one plan, no cascade.
