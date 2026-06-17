# E-239-02: Remove the Dashboard Surface + Dashboard-Only Season Machinery

## Epic
[E-239: Decouple Pipeline Imports, Then Remove the Unused Surfaces](epic.md)

## Status
`DONE`

## Description
After this story is complete, the dashboard surface is gone: `src/api/routes/dashboard.py`, the dashboard Jinja templates, the dashboard router registration in `main.py`, the dashboard bottom-nav links in `base.html`, and the dashboard-only season-selection + cross-season-career machinery in `src/api/db.py` are deleted, along with the tests that exclusively exercise them. The season-derivation primitive, the `seasons` table, and the `player_season_*` tables are untouched, and login + the reports admin surface continue to work.

## Context
The dashboard is a complete unused surface (quarantined in D1) and the largest single cleanup. The subtlety this story must get right is the **season machinery** (Technical Notes §C): the removal target is the dashboard's season-SELECTION + cross-season-CAREER layer (all dashboard-only, zero non-dashboard consumers per the DE artifact Q1), NOT the single-season `derive_season_id_for_team()` primitive — there is no multi-season path inside that function to strip. There is also a protected-core auth caveat (Technical Notes §G): `_get_permitted_teams()` in `src/api/auth.py` reads `user_team_access` for non-admin access, so this story must confirm auth + login still work after the dashboard is gone without breaking or blind-editing that read path.

## Acceptance Criteria
- [ ] **AC-1**: `src/api/routes/dashboard.py` and the dashboard templates (`src/api/templates/dashboard/**`, all 10) are deleted; the dashboard import and `include_router` in `src/api/main.py` are removed; the dashboard bottom-nav links in `src/api/templates/base.html` are removed (per SE artifact §5). `GET /dashboard*` returns 404 and the app starts cleanly.
- [ ] **AC-2**: The dashboard-only season machinery is deleted from `src/api/db.py` — `get_available_seasons`, `get_player_profile`, `get_team_batting_stats`, `get_team_pitching_stats` — and `_pick_season_for_year` is removed with `dashboard.py`. After deletion, grep confirms zero remaining importers of each removed symbol.
- [ ] **AC-2b** (GREP-DRIVEN, per epic Technical Notes §D / DE finding S2 / Codex C2): after the dashboard routes are removed, delete every `src/api/db.py` query function left with ZERO remaining importers — grep `src/` + `scripts/` + `tests/`, and delete each only after confirming it is NOT reports/charts-shared. **Re-grep at execution time; do not trust the cited names/lines** (the hand-list was already wrong pre-dispatch). Non-binding examples verified 2026-06-16: `get_schedule_games`, `get_opponent_scouting_report`, `get_opponent_scouting_status`, `get_player_spray_events`, `get_players_spray_events_batch`, `get_player_spray_bip_counts` (dashboard-consumed `dashboard.py:1681`), `get_player_spray_bip_count` (singular, zero-consumer dead), and the dashboard-only `get_teams_by_ids` / `get_team_games` / `get_last_meeting`. `get_teams_with_data` / `get_opponents_for_team` are ALREADY ABSENT (no action). E-239-05 runs the FINAL sweep as the last `api/db.py` editor.
- [ ] **AC-3**: The season-derivation primitive is untouched — `derive_season_id_for_team()`/`_with_fallback()`, `ensure_season_row()`, the `seasons` table, and the reports' single-fixed-season filters in `generator.py` are unchanged (Technical Notes §C). The within-season dedup guards are untouched.
- [ ] **AC-4**: Login and the admin reports surface still work; `_get_permitted_teams()`/auth in `src/api/auth.py` continues to function (the `user_team_access` read path is not broken). Auth/login tests pass (Technical Notes §G).
- [ ] **AC-5**: Protected-core seams preserved — `src/charts/spray.py` is untouched (the deleted `/dashboard/charts/*` routes consumed it, but reports inline its PNGs directly); `src/api/helpers.py` untouched. Epic A goldens + `bb report verify-aggregates` parity unchanged/green (Technical Notes §A).
- [ ] **AC-6**: Tests handled per the discrimination rule (Technical Notes §F / SE §4): the 8 `test_dashboard*` files are deleted. **`tests/test_db.py` is a SHARED file (kept), but every test class that exercises a helper this story removes (AC-2/AC-2b, incl. sweep removals) is deleted** (Codex C3 / SE verification — these characterize dead dashboard-only surfaces). At minimum the 9 classes (re-grep live lines per §B): `TestGetTeamBattingStats` (≈:125), `TestGetTeamsByIds` (≈:215), `TestGetTeamPitchingStats` (≈:276), `TestSeasonDefault` (≈:328), `TestGetTeamGames` (≈:421), `TestGetOpponentScoutingReport` (≈:807), `TestGetOpponentScoutingReportJerseyNumber` (≈:859), `TestGetLastMeeting` (≈:1018), `TestScoutingReportNameCascade` (≈:1840). The `TestGetOpponentLinkCountForTeam` class is handled in E-239-05 (its helper is deleted there). Full suite green (0 failed) — the closure-gate-blocking break Codex flagged is closed.
- [ ] **AC-6b** (coverage-loss gate, CR finding 6): `test_strike_pct.py` is deleted ONLY AFTER confirming report-side strike_pct coverage survives — i.e. `test_report_workload.py` / `test_report_generator.py` exercise the reports' own `_compute_pitching_rates` (`generator.py:484`) strike_pct path. If that coverage does not already exist, it is added before `test_strike_pct.py` is removed (no silent protected-core coverage loss).

## Technical Approach
Delete the dashboard route module, templates, `main.py` registration, and `base.html` bottom-nav. Remove the four dashboard-only `db.py` functions (re-grep live line numbers per the DE artifact Q1). Confirm via grep that nothing outside the dashboard imported them. Verify the auth read path and login by running the auth/login tests. Apply the test-discrimination rule, including the `test_strike_pct.py` coverage check. Do NOT touch the derivation primitive, `seasons`, or `player_season_*`.

## Dependencies
- **Blocked by**: E-239-01 (serializes the shared `main.py`/`base.html` edits; chain 1 already severed)
- **Blocks**: E-239-04, E-239-05 (shared `api/db.py` + `tests/test_db.py`; Codex C1), E-239-06

## Files to Create or Modify
- DELETE `src/api/routes/dashboard.py`
- DELETE `src/api/templates/dashboard/**` (10 templates)
- MODIFY `src/api/main.py` (remove dashboard import + `include_router`)
- MODIFY `src/api/templates/base.html` (remove dashboard bottom-nav links)
- MODIFY `src/api/db.py` (delete `get_available_seasons`, `get_player_profile`, `get_team_batting_stats`, `get_team_pitching_stats`)
- MODIFY `src/api/auth.py` only if required to keep login working after dashboard removal (preserve the `user_team_access` read path)
- DELETE `tests/test_dashboard*.py` (8 files), `tests/test_strike_pct.py`
- MODIFY `tests/test_db.py` (delete/adjust the `get_team_batting_stats`/`get_team_pitching_stats`/`get_opponent_scouting_report` blocks per AC-6; the `get_opponent_link_count_for_team` block is E-239-05's — serialized via 05 blockedBy 02)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-239-04/05**: no surviving dashboard caller references the soon-deleted member/opponent modules or the season-selection layer.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests deleted/adjusted and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
`api/db.py` is also edited by E-239-05 (dead opponent helpers) and `main.py`/`base.html` by E-239-01 — the dependency ordering serializes those shared-file edits.
