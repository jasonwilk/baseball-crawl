# E-245-04: Fix self-game (`home == away`) opponent-resolution corruption

## Epic
[E-245: High-Fidelity Play Ingestion](epic.md)

## Status
`DONE`

## Description
After this story is complete, no completed game will have `home_team_id == away_team_id`. Two
halves: a forward fix at game load so the opponent always resolves to a distinct team (by name, or
an "Unknown Opponent" sentinel) with a home≠away invariant guard; and a one-time re-ingest of the 23
existing self-games so their `games` rows and collapsed `batting_team_id` rollups are corrected.

## Context
DE confirmed the root cause empirically (epic TN-6): the scouting path hardcodes `opponent_id=""`
(`src/gamechanger/loaders/scouting_loader.py:393/426`); the 23 affected opponents never used GC
scorekeeping, so their boxscore carries only the scouted team's key → `opp_key=None` →
`opp_team_id_result=None` → `game_loader.py:580-584` sets `opp_team_id = own_team_id` (the
"placeholder, not used" comment is wrong — it IS used) → `_resolve_home_away` returns `(own, own)`.
Downstream, the plays parser derives `batting_team_id` from `half`, so both halves collapse onto one
team id — corrupting team rollups and over-attributing pitchers. Verified on `ca04a524` (only
team-133 players; 0 of 23 self-games have a second batting team — not a name collision).

Correcting the 23 games' `games` rows requires re-fetching the boxscore for the 5 affected teams (the
opponent name was discarded at ingest and is unrecoverable from the DB) and re-running the fixed
loader — an API re-fetch, unlike Story 02's offline reparse. But `plays`/`play_events` are NOT cleared
and NOT re-fetched: once the `games` row is corrected to `home != away`, the collapsed
`batting_team_id` is re-derived IN PLACE via E-245-02's reusable in-place reload entry point (epic
TN-3b / TN-6). There is NO "clear tool" — clearing `play_events` would destroy `raw_template` (epic
TN-3/M1), and 04 does not re-fetch plays.

## Acceptance Criteria
- [ ] **AC-1**: Given a boxscore that lacks the opponent stat block, when the game loads, then the
      opponent team is resolved by NAME (`opponent_team.name`) to a distinct `opp_team_id` (the
      opponent has no per-player stat rows — truthful), so `home_team_id != away_team_id` (epic TN-6).
- [ ] **AC-2**: Given an opponent that is truly unresolvable, when `_resolve_home_away` / `_upsert_game`
      runs, then it NEVER emits `home_team_id == away_team_id` — it uses an "Unknown Opponent"
      sentinel stub rather than `own_team_id`, and the misleading `game_loader.py:580-584` comment is
      removed (epic TN-6 invariant guard).
- [ ] **AC-3** (dispatch-verifiable, fixture): Given a fixtured already-loaded self-game
      (`home == away`, empty opponent stat block), when the corrective path runs (boxscore re-ingest
      via the fixed loader sets `home != away`, then E-245-02's in-place reload re-reads the corrected
      games row and re-derives `batting_team_id` per `half` — story E-245-02 AC-9 / epic TN-3b), then
      the `games` row becomes `home != away` and the plays' `batting_team_id` is re-derived correctly,
      with NO `play_events` clear (epic TN-6). Verified on a fixture, no live data.
- [ ] **AC-4**: Given the corrective rewrite, when it re-ingests/re-derives affected rows, then it
      respects perspective scoping and the Cleanup-Detection Mirror Invariant
      (`.claude/rules/data-model.md`) — no member/`full` rows are deleted or downgraded, no
      cross-perspective data is mis-scoped.
- [ ] **AC-5** (operator-verified, post-merge): Given the live corrective run over the 5 affected
      teams, when it completes against the real DB, then the axis-3 self-game counter goes 23 → 0 (no
      completed game has `home_team_id == away_team_id`, each resolves to a distinct opponent). This
      pass needs GC credentials and cannot run in the worktree — it is operator-verified post-merge
      (epic TN-9), not a dispatch gate.

## Technical Approach
DE implements the two-part `game_loader.py` fix (by-name opponent resolution when the opponent stat
block is absent + the home≠away invariant guard with sentinel). For the 23 existing games, the
correction re-fetches the boxscore for the 5 affected teams and re-runs the fixed boxscore game-load
(corrects the `games` row home/away and creates the opponent by name), then re-derives the affected
plays' `batting_team_id` IN PLACE via E-245-02's reusable reload entry point — NO `play_events` clear,
no plays re-fetch (epic TN-6). Coordinate with E-245-02 on that in-place entry point. Verify the
loader fix, invariant, and the in-place correction via fixtures; the live 23 → 0 run is
operator-verified post-merge.

## Dependencies
- **Blocked by**: E-245-02 — reuses E-245-02's per-game reload entry point for ONE step only: the
  POST-correction plays re-derivation (after this story's boxscore re-ingest sets `home != away`).
  This story is BROADER than 02 — it also re-runs the boxscore game-load and requires an API re-fetch
  (the opponent name is unrecoverable from the DB), unlike E-245-02's offline reparse.
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` (by-name opponent resolution + home≠away invariant guard + sentinel; remove the misleading "placeholder, not used" comment at `:580-584` — exact site per DE: the `opp_team_id = own_team_id` assignment at `:580-584` and `_resolve_home_away`)
- `src/cli/data.py` (a DISTINCT new `bb data` subcommand that orchestrates the 5-team corrective re-ingest — re-fetch via the existing scouting crawl→load pipeline, then the post-correction plays re-derivation via E-245-02's entry point; it REUSES 02's entry point, it does NOT edit 02's command)
- Tests under `tests/` (empty-opponent-stat-block → home≠away; invariant guard / sentinel; perspective scoping)

## Agent Hint
data-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] Test scope discovery run for every modified module (per `.claude/rules/testing.md`)

## Notes
The +23 BF game `e283438c` is NOT a self-game (home=220, away=100) — it is a distinct cause-4
multi-pitcher-boundary issue and is OUT of scope (epic Non-Goals). Do not claim to fix it here. The
existing-data correction requires an API re-fetch (unlike E-245-02's offline reparse) — this
asymmetry is deliberate (epic TN-6).
