---
name: plays-boxscore-reconciliation-baseline
description: Plays→boxscore fidelity is 98-100% (coverage, not fidelity, is the gap); self-games (home==away) integrity bug; correct reconciliation grain
metadata:
  type: project
---

# Plays→Boxscore reconciliation baseline (E-245 north-star)

Measured 2026-06-28 (DB `data/app.db`, 597 games). Anchors the byte-identical-play-ingestion
north-star (CLAUDE.md "Operating Principle"; E-245). Full inventory:
`/.project/research/E-245-plays-boxscore-reconciliation-baseline.md`. Repro: `recon.sql`.

**Headline:** outcome-derived stats (batting AB/H/BB/SO/HBP; pitching BF/SO/BB/H/HBP) reconcile
**98.4–100% exact** once you exclude players with no plays at all. **The gap is COVERAGE, not
fidelity.** Batting BB/SO are perfect (0–1 disagreements / 11,807). Whole-season gap = 3
independent axes: (1) pitch-type-suffix drop [[pitch-type-annotation-parser-gap]] — pitch_count/
FPS only, 5,841 events/29 games, team-concentrated; (2) coverage/perspective misalignment —
95 pitcher + 377 batter no-plays units, ~30% are perspective-join misses (boxscore under persp B,
plays under persp A), not true loss; (3) residual fidelity drift — small ±1, a few attribution
outliers.

**Why:** new standing direction — every play-ingestion change must move plays-derived stats
closer to official boxscores, never regress. The scoreboard IS the success metric.

**How to apply (reusable reconciliation recipe):**
- **Grain = player-level**: `game_id + perspective_team_id + player_id`, match on
  `pitcher_id`/`batter_id`. Do NOT use a team-level grain (counting opponent PAs as a team's BF):
  it gives a false 96% with huge −45/−36 outliers that are pure **self-game artifacts**.
- All main boxscore stats are fully populated (0 NULLs in pgp.bf/so/bb/h/ip_outs,
  pgb.ab/h/bb/so/hbp) — reconciliation is clean.
- Plays-derived defs: SO=`Strikeout`+`Dropped 3rd Strike`; BB=`Walk`+`Intentional Walk`;
  H=`Single/Double/Triple/Home Run`; AB=PA−(BB+IBB+HBP+`Sacrifice Bunt`+`Sacrifice Fly`+
  `Catcher's Interference`).
- Always report BOTH "all-units exact%" and "fidelity-only exact% (excl. no-plays)" — the
  coverage column otherwise masks that the parser is accurate.

## Self-game integrity bug (home_team_id = away_team_id)

**23 of 597 games (3.9%) have `games.home_team_id = games.away_team_id`** — the opponent identity
collapsed onto the scouted team (an opponent-resolution failure at GameLoader time). Symptoms:
plays show only ONE distinct `batting_team_id`; team-level BF attribution breaks (the −45/−36
team-grain deltas); pitcher **over-attribution** outliers (BF plays-over of +11/+23 — a starter
absorbing the opponent's PAs). Player-level reconciliation survives it, but team rollups and the
pitcher-workload view are corrupted. Clean enumerable set (`SELECT game_id FROM games WHERE
home_team_id=away_team_id`) — a targeted data fix candidate. **How to apply:** any team-rollup or
pitcher-attribution query must account for these; don't trust `batting_team_id` attribution on
self-games.
