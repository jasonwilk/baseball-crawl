# E-245 — Plays→Boxscore Reconciliation Baseline (gap inventory)

**Author:** data-engineer (consultation-mode research)
**Date:** 2026-06-28
**DB analyzed:** `/workspaces/baseball-crawl/data/app.db` (read-only)
**Purpose:** Anchor the byte-identical-play-ingestion north-star (CLAUDE.md "Operating
Principle"; `docs/VISION.md` North Star). This is the current-state baseline: per-stat
reconciliation scoreboard + ranked dominant-causes, scoping E-245 and its success metric.

---

## TL;DR

- **Outcome-derived stats already reconcile 98.4–100% once you exclude games/players with no
  plays at all.** The plays parser is faithful where it has data. The headline gap is
  **coverage, not fidelity.**
- The whole-season gap decomposes into **three independent axes**, in priority order:
  1. **Pitch-level drop (pitch_count / FPS% / P-PA)** — the pitch-type-suffix parser bug.
     Team-concentrated, catastrophic for affected teams (the report that triggered this:
     FPS 3.4% instead of ~60%). 5,841 dropped pitch events across 29 games.
  2. **Coverage / perspective misalignment (no-plays units)** — a player is in the boxscore
     but has zero matching plays rows. 95 pitcher + 377 batter units. Mostly a
     perspective-keyed join miss, not truly-missing data (0 games are wholly un-charted).
  3. **Residual outcome-fidelity drift** — small ±1 deltas + a few attribution outliers
     tied to self-games (home==away) and multi-pitcher boundaries. The smallest bucket.

---

## Reconcilable universe

| Measure | Value |
|---|---|
| Total games | 597 |
| Games with plays | 595 |
| Games with boxscore pitching | 595 |
| Games with boxscore pitching but ZERO plays | **0** (every boxscore game has some plays) |
| Boxscore pitcher-game units (player_game_pitching rows) | 2,874 |
| Boxscore batter-game units (player_game_batting rows) | 12,555 |
| Total plays rows | 35,198 |
| Total play_events rows | (pitch events classified: 121,048) |

**Grain choice:** the trustworthy reconciliation grain is **player-level**
(`game_id` + `perspective_team_id` + `player_id`), matching on `pitcher_id`/`batter_id`.
A team-level grain (counting opponent PAs as a team's BF) gives a *false* 96.3% with huge
−45/−36 outliers that are pure **self-game artifacts** (see Cause 3) — do NOT use team-level
attribution for the scoreboard. All numbers below are player-level.

Plays-derived stat definitions used (from `plays.outcome`):
- SO = `Strikeout` + `Dropped 3rd Strike`; BB = `Walk` + `Intentional Walk`;
  H = `Single`+`Double`+`Triple`+`Home Run`; HBP = `Hit By Pitch`; BF/PA = row count;
  AB = PA − (BB + IBB + HBP + Sac Bunt + Sac Fly + Catcher's Interference).
- All main boxscore stats are fully populated (0 NULLs in pgp.bf/so/bb/h/ip_outs and
  pgb.ab/h/bb/so/hbp), so reconciliation is clean.

---

## Scoreboard — PITCHING (2,874 pitcher-game units)

| Stat | Exact% (all units) | plays-over | plays-under | no-plays units | Exact% (fidelity only*) | abs-Δ (fidelity) |
|------|-------------------:|-----------:|------------:|---------------:|------------------------:|-----------------:|
| BF   | 95.2% | 21 | 118 | 95 | **98.4%** | 120 |
| SO   | 97.8% |  2 |  61 | 61 | **99.9%** |   2 |
| BB   | 96.4% | 17 |  86 | 73 | **98.9%** |  33 |
| H    | 96.1% | 17 |  94 | 80 | **98.9%** |  51 |
| HBP  | 98.4% |  4 |  42 | 42 |  — |  65 |

\* *fidelity only* = excludes the no-plays (coverage) units; measures parser accuracy where
plays exist.

## Scoreboard — BATTING (12,555 batter-game units)

| Stat | Exact% (all units) | plays-over | plays-under | no-plays units | Exact% (fidelity only*) | abs-Δ (fidelity) |
|------|-------------------:|-----------:|------------:|---------------:|------------------------:|-----------------:|
| AB   | 96.7% | 30 | 380 | 377 | **99.7%** | 34 |
| H    | 98.4% |  4 | 201 | 192 | **99.9%** | 13 |
| BB   | 98.8% |  0 | 151 | 151 | **100.0%** | 0 |
| SO   | 98.9% |  1 | 135 | 135 | **100.0%** | 1 |
| HBP  | 99.5% |  0 |  60 |  60 |  — | 64 |

**Reading:** every stat's "all units" exact% is dragged down almost entirely by the no-plays
column (coverage). Strip those and batting BB/SO are literally perfect (0–1 disagreements out
of 11,807); pitching SO is near-perfect (2). The signed skew is overwhelmingly **plays-under**
(plays missing PAs/events), not plays-over.

## Scoreboard — PITCH-LEVEL (separate axis; not outcome-derived)

| Measure | Value |
|---|---|
| Plays with `pitch_count > 0` (season-wide) | 33,621 / 35,198 = **95.5%** |
| Classified pitch events (`play_events.event_type='pitch'`) | 121,048 |
| **Dropped pitch events** (pitch text stranded as `event_type='other'` w/ `(PitchType)` suffix) | **5,841** |
| Plays carrying ≥1 dropped pitch event | 1,610 |
| Games affected by the drop | **29** |

The drop is **team-concentrated**: ~5,328 of the 5,841 are team 133 ("Empire Netting & Fence
Sr. Legion") alone, where 23 of 24 games are pitch-typed → FPS/P-PA collapse to physically
impossible values. Season-wide pitch_count looks healthy (95.5%) because most teams' scorekeepers
don't log pitch type; the bug is invisible until you scout a team that does.

---

## Coverage vs. accuracy split

- **No game is wholly un-charted** (0 boxscore games with zero plays). The coverage gap is at
  the *player/perspective* level, not the game level.
- The 95 no-plays **pitcher** units span 25 distinct (game, perspective). **88 of 95** sit in a
  (game, perspective) that has *zero* plays for that perspective — but the game DOES have plays
  under a *different* perspective. So this is largely **perspective misalignment**: boxscore
  loaded under perspective B, plays under perspective A. Re-running the pitcher reconciliation
  **ignoring perspective** drops no-plays from 95 → 66, i.e. ~29 units are pure perspective-join
  misses and ~66 are genuinely-absent plays for that player.
- **Implication for the scoreboard design:** decide perspective policy explicitly. Reports query
  plays perspective-scoped (scouted team), so the perspective-scoped grain is the honest one for
  *report* fidelity; a perspective-agnostic grain over-credits coverage. The scoreboard should
  report both the perspective-scoped exact% (what the report shows) and flag perspective-only
  misses as their own bucket.

---

## Ranked dominant causes

1. **Pitch-type-suffix parser drop (pitch_count / FPS% / P-PA).** `play_events.raw_template`
   like `"Strike 1 looking (Curveball)"` is classified `event_type='other'` instead of `'pitch'`
   (parser matches only the un-suffixed form), so `plays.pitch_count` / `is_first_pitch_strike`
   default to 0. **Does not touch outcome stats** — they reconcile ~99%. 5,841 events, 29 games,
   team-concentrated. *Highest-value fix:* recovers an entire stat family for affected teams.
   Requires parser fix + **reload** (whole-game plays idempotency keyed on
   `(game_id, perspective_team_id)` means a plain regen skips already-loaded games — plays +
   play_events must be cleared first; FK `play_events.play_id→plays.id`, no ON DELETE CASCADE).
   See companion finding `.claude/agent-memory/data-engineer/pitch_type_annotation_parser_gap.md`.

2. **Coverage / perspective misalignment (no-plays units).** 95 pitcher + 377 batter (AB) units
   where boxscore has the player but plays doesn't. ~30% perspective-join misses, ~70% genuinely
   absent. Biggest *count* contributor to non-exact across stats, but much is a join/perspective
   artifact rather than ingestion loss — quantify precisely before treating as "missing data."

3. **Self-games (`home_team_id = away_team_id`).** 23 games (3.9%) where the opponent identity
   collapsed onto the scouted team — an opponent-resolution failure at game-load. Breaks
   *team-level* attribution (the −45/−36 team-grain outliers) and produces *pitcher
   over-attribution* outliers (BF plays-over of +11, +23 — a starter absorbing the opponent's
   PAs). Player-level reconciliation mostly survives it, but it corrupts any team-rollup and the
   pitcher-workload view. Worth a targeted fix because it's a clean, enumerable set.

4. **Pitcher-attribution / multi-pitcher boundary drift.** Small ±1–6 BF deltas plus a couple of
   *normal*-game over-attributions (e.g. game `e283438c` persp 100: one pitcher credited 22 plays
   vs boxscore 11 — NOT duplication; 60 plays / 60 distinct orders — a within-game pitcher-boundary
   mis-assignment). Pitching BF fidelity drift = 44 units, mostly ±1 (15 under, 9 over).

5. **Abandoned-PA / outcome-template residual.** The irreducible tail: ±1 on AB/H from abandoned
   at-bats and rare outcome edges. Batting BB/SO are already 0–1 off. This is the
   "quick-scored games / scorekeeper noise" residual the north-star explicitly exempts from zero.

---

## Recommended success metric for E-245

The scoreboard above IS the metric. Concretely, track per-stat **fidelity exact%**
(perspective-scoped, excluding no-plays) and **abs-Δ**, plus the three axis-level counters
(dropped-pitch-events, no-plays units, self-games). The north-star "trend toward zero" binds the
abs-Δ and the axis counters. Suggested ingestion-change gate: **no stat's abs-Δ regresses and no
axis counter increases.** Highest-leverage first moves: (1) pitch-type-suffix fix + reload
(closes axis 1), (2) self-game/opponent-resolution fix (closes axis 3 + the attribution
outliers). Axis-2 (perspective) is partly a measurement-policy decision, not pure ingestion loss.

## Reproduction

Scoreboard query: `scratchpad/recon.sql` in this session (player-level, both sides, with and
without the no-plays exclusion). All figures are bare SQL over `plays` / `play_events` /
`player_game_batting` / `player_game_pitching`; no app code paths involved.

## Open coordination items

- **baseball-coach:** confirm stat priority weighting for the north-star metric (is BF/FPS the
  headline, or AB/H/BB/SO equally?) and whether the abandoned-PA residual (cause 5) is acceptable.
- **software-engineer:** owns parser cause analysis for axes 1, 4, 5 and the reload mechanism;
  api-scout confirms the live API delivers the suffixed pitch template and the abandoned-PA-with-
  charted-pitches shape.
- **data-engineer (me):** owns the perspective policy (axis 2) and the self-game/opponent-resolution
  data fix (axis 3) framing.
