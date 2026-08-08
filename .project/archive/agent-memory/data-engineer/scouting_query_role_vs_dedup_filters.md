---
name: scouting-query-role-vs-dedup-filters
description: For scouting rollups, perspective_team_id is a DEDUP key (holds BOTH teams' rows), NOT a role filter; each source table needs a separate ROLE filter, and spray error-maps need chart_type as the wrong-team discriminator.
metadata:
  type: reference
---

# Scouting rollups: perspective_team_id is DEDUP, not ROLE

Established during E-263 (Deep Scout) planning, verified against `db.py`,
`scouting_spray_loader.py`, `plays_parser.py`, and `001_initial_schema.sql`
(2026-07-13). Codex caught the original TN-3 conflating the two.

**Core fact:** a scouting crawl keyed to team X loads ALL of X's games under
`perspective_team_id = X`, and each game carries BOTH teams' rows (X batting AND
X fielding). So `perspective_team_id = X` is a DEDUP filter (which crawl loaded
it — it neutralizes cross-perspective twin-game double-counts), NOT a role
filter. To select "whose players/events," every rollup needs a SEPARATE role
filter, on the column each source table carries:

| Signal | Source table | Dedup filter | ROLE filter |
|--------|-------------|-------------|-------------|
| Battery card (X on defense: CS, pickoff, WP/PB) | `play_events → plays` | `plays.perspective_team_id = X` | `plays.batting_team_id != X` (X fields ⇒ other team bats) + parse actor UUID from `raw_template` |
| Steal light (leaky-battery / "should WE run vs their battery") | `player_game_batting` or `play_events` | `perspective = X` | `team_id != X` / `batting_team_id != X` — the OPPOSING runners' SB success vs X's battery. `team_id = X` would be X's OWN offense (a DIFFERENT signal). |
| Alignment (X's hitters' spray) | `spray_charts` | `perspective_team_id = X` | `team_id = X` AND `chart_type='offensive'` |
| Error-map (X's own defensive errors) | `spray_charts` | `perspective_team_id = X` | `team_id = X` AND `chart_type='defensive'` |

## spray_charts column semantics (verified in `_insert_event`)
- `spray_charts.team_id` = the resolved team of the PLAYER the event describes
  (role), from `_resolve_player_team_id(player_uuid, ...)` against `team_rosters`.
- `spray_charts.perspective_team_id` = the scouted/crawl team (dedup).
- Under an X scouting crawl the payload covers X's OWN players only (api-scout
  spray asymmetry), so ALL rows are `team_id = X` AND `perspective_team_id = X`
  across both charts — which is why `team_id` alone can't separate X's own
  errors from the opponent's.

## The SIG-008 "wrong team" error-map trap (the non-obvious part)
`error` is read from `defenders[0]` (the fielder on the play). On the OFFENSIVE
chart (X's batter, so `team_id=X`), `defenders[0]` is the OPPONENT's fielder, so
an `error=1` there is the OPPONENT's error stored under `team_id=X`. Building the
error-map off the offensive chart therefore counts the OPPONENT's errors as X's.
**`chart_type='defensive'` is the MANDATORY discriminator** that selects X's own
fielders' errors — NOT `team_id`. This is the mechanism behind the historically
observed "counting the wrong team" error-map bug.

## CS% denominator (clean steals name no catcher)
`plays_parser.py` baserunner keywords include both `"steals"` (SB) and
`"caught stealing"` (CS). Per design-doc §2, ONLY caught-stealing names the
catcher; a clean steal names nobody. Consequences:
- Per-catcher CS% is NOT computable (no per-catcher SB denominator without
  reconstructing who was catching from substitution events — out of scope).
- Honest form: **TEAM-battery CS% = CS_events / (CS_events + SB_events)** over
  X-on-defense PAs (`batting_team_id != X`), + **raw per-catcher CS counts**
  (CS events name the catcher UUID). Backpicks: raw counts, flag at 2+.
- Compute SB and CS from the SAME source (both from `play_events`, or both from
  boxscore) — never mix event-CS with boxscore-SB in one ratio (→ CS% > 100%).

See [[season_aggregate_writers]] for the perspective-double-count history and
[[fixture_seed_not_rollup_consistent]] for perspective-filtered test fixtures.
Related: `.claude/rules/perspective-provenance.md`.
