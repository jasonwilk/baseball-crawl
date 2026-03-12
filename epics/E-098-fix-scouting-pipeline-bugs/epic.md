# E-098: Fix Scouting Pipeline Bugs

## Status
`ACTIVE`

## Overview
Fix confirmed bugs in the opponent scouting pipeline (E-097) before scouting reports are used for game prep. Two data-correctness bugs (cross-season stat bleed, silent load failures), two test gaps that allowed them, and three crawler status-lifecycle bugs (freshness gate missing season scope, premature 'completed' marking, zero-boxscore crawls marked successful).

## Background & Context
A Codex code review of the completed E-097 Opponent Scouting Pipeline found four defects. A triage team of data-engineer, software-engineer, and baseball-coach unanimously recommended FIX for all four, with zero dismissals or deferrals. The bugs fall into two independent clusters that can be fixed in parallel.

No expert consultation required -- all findings were pre-triaged by the relevant domain experts (DE, SE, baseball-coach) and the fix approaches are well-defined.

## Goals
- Season aggregate queries produce correct per-season stats, even when the same opponent is scouted across multiple seasons
- Load failures in `bb data scout` are visible to the operator and reflected in exit codes and scouting run status
- Scouting run status lifecycle is correct end-to-end: crawler writes intermediate status, CLI owns final status after load
- Freshness gate respects season scope when explicit `--season` is provided
- Zero-boxscore crawls are marked 'failed', not 'completed'
- Regression tests exist for all bug classes

## Non-Goals
- New scouting features or additional stat columns
- Schema changes to `player_game_batting`/`player_game_pitching` (the fix uses JOINs, not column additions)
- Refactoring the scouting pipeline beyond the minimum needed to fix these bugs

## Success Criteria
- Multi-season scouting of the same opponent produces correct per-season aggregates (no cross-season data bleed)
- `bb data scout` exits non-zero when loading fails, and scouting run status reflects the failure
- Scouting run status is 'completed' only after both crawl and load succeed; 'failed' when either fails
- Freshness gate respects season scope when `--season` is explicit
- Zero-boxscore crawls are detected and marked 'failed'
- All new and existing scouting tests pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-098-01 | Fix cross-season aggregate bleed + regression test | DONE | None | se-098-01 |
| E-098-02 | Fix silent load failures in bb data scout + CLI failure test | DONE | None | se-098-02 |
| E-098-03 | Fix crawler status lifecycle and freshness gate | DONE | E-098-02 | se-098-03 |
| E-098-04 | Fix completed_at timestamp on intermediate status rows | DONE | E-098-03 | se-098-04 |
| E-098-05 | Fix roster-fail commit gap, load-path completed_at, and test assertions | DONE | E-098-04 | se-098-05 |

## Dispatch Team
- software-engineer

## Technical Notes

### Story A context (E-098-01): Season aggregate JOIN pattern
The `player_game_batting` and `player_game_pitching` tables have NO `season_id` column. Both `_compute_batting_aggregates` and `_compute_pitching_aggregates` in `scouting_loader.py` currently filter only on `team_id`. The fix requires JOINing through the `games` table to get `season_id`:
```
FROM player_game_batting pgb
JOIN games g ON pgb.game_id = g.game_id
WHERE pgb.team_id = ? AND g.season_id = ?
```
Same pattern applies to pitching. This was confirmed by the data-engineer during triage.

### Story B context (E-098-02): Two distinct issues
1. **Premature status marking** (`scouting.py:160`): The crawler marks `scouting_runs.status = completed` before loading happens. If loading subsequently fails, the freshness check in future runs suppresses re-scouting because the run looks "completed."
2. **Ignored LoadResult** (`data.py:297, :325`): `_load_scouted_team` and `_load_all_scouted` ignore the return value from `loader.load_team()`. The exit code in `_run_scout_pipeline` (line 261) checks only `crawl_result.errors`. The operator sees "Load complete" even when DB writes failed.

### Story C context (E-098-03): Crawler status lifecycle and freshness gate

Three related bugs in the crawler's `scouting_runs` state machine:

1. **Freshness gate missing season_id** (`scouting.py:406-428`): `_is_scouted_recently()` queries `WHERE team_id = ? AND status = 'completed'` without filtering by `season_id`. Scouting the same opponent for a different season is incorrectly skipped. Complication: `scout_all()` calls freshness check before season is derived. Fix: optional `season_id` param -- full protection on `--season` explicit path, team-only on auto-derive path.

2. **Premature 'completed' status** (`scouting.py:160-163`): Crawler writes 'completed' at end of crawl phase; loading happens afterward in CLI. Fix: crawler writes 'running', CLI owns final 'completed'/'failed' transition after load.

3. **Zero-boxscore crawl = success** (`scouting.py:158-165`): When `_fetch_boxscores()` returns 0, run is still marked 'completed'. Fix: check `games_crawled == 0 and len(completed_games) > 0` → mark 'failed'. Narrow scope (total failure only); partial success (25/28 games) remains valid.

E-098-02 fixed the CLI side (LoadResult propagation). E-098-03 completes the fix on the crawler side and wires the load outcome back into `scouting_runs.status`.

## Open Questions
None.

## History
- 2026-03-12: Created from Codex code review findings on E-097. All four findings unanimously triaged as FIX by DE, SE, and baseball-coach.
- 2026-03-12: Added E-098-03 (crawler status lifecycle and freshness gate) after second Codex code review found 3 additional P1 bugs in the same area. SE and DE both assessed and recommended FIX. Single story because all three touch the same state machine. Epic scope expanded from 4 to 7 bugs total.
- 2026-03-12: Added E-098-04 (completed_at timestamp fix) after final Codex code review. P2 finding: `_upsert_run_end()` sets `completed_at` unconditionally, including for 'running' rows. Also triaged P1 (GameSummaryEntry wrong ID) as DISMISS and P3 (flow doc vs schema mismatch) as DEFER to IDEA-022.
- 2026-03-12: Added E-098-05 (roster-fail commit gap, load-path completed_at, test assertions) after Codex review of E-098-03/04 implementation. Three findings: missing commit on roster-fail path (P1-A), `update_run_load_status()` missing `completed_at` (P1-B), load-phase tests missing timestamp assertions (P2). SE and DE both confirmed FIX.
