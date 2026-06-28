---
paths:
  - "src/reports/**"
  - "src/api/templates/**"
  - "src/charts/**"
---

# Display Philosophy and Season-Length Calibration

## Core Principle

**Never suppress. Always contextualize.**

Every stat displays at full visual weight -- same font size, same color intensity, same layout position -- regardless of sample size. The system is the presenter; the coach is the analyst. The coach decides what matters, not the code.

## What "Contextualize" Means

Data-depth context accompanies every rate stat:
- **PA badges** on batting lines (e.g., "5 PA", "47 PA")
- **IP badges** on pitching lines (e.g., "0.1 IP", "23.0 IP")
- **Game counts** on aggregate views

These badges replace dimming, asterisks, footnotes, and "small sample" warnings. The badge IS the context.

## Prohibited Patterns

- Dimming, graying out, or reducing opacity of rate stats based on sample size
- Asterisks or daggers on player names or stat values to flag small samples
- Footnotes like "fewer than 20 PA" or "small sample -- interpret with caution"
- Hiding or collapsing rows for players below a sample threshold
- Conditional CSS classes like `small-sample` that alter visual weight

## Season-Length Calibration

Thresholds are designed for **25-35 game high school and youth seasons**, not 162-game professional seasons.

Reference numbers per season:
- Batters: ~80-100 PA per season; splits may have 20-40 PA per bucket
- Pitchers: ~40-60 IP per season
- A 20 PA threshold blanks out most players for the first third of the season -- unacceptable at this level

**Anti-pattern**: Importing MLB-scale thresholds (e.g., 50 PA, 30 IP) that render the system useless until mid-season.

## Current Threshold Reference Values

These are the active thresholds as of E-187:

| Context | Threshold | Purpose |
|---------|-----------|---------|
| Batting qualification | 5 PA | Player included in heat-map ranking |
| Pitching qualification | 6 IP (18 outs) | Player included in heat-map ranking |
| Spray chart (per-player) | 3 BIP | Minimum to render a player spray chart |
| Spray chart (team aggregate) | 20 BIP | Minimum to render a team spray chart |

## Graduated Heat Intensity Tiers

Heat-map color richness scales with team data depth. The percentile ranking algorithm is unchanged -- these tiers clamp the maximum heat level based on how many players qualify. Players below the per-player threshold always get heat-0.

**Batting** (threshold: 5+ PA):

| Qualified Batters | Max Heat | Season Phase |
|-------------------|----------|--------------|
| 0-2 | 0 (no heat) | Game 1 |
| 3-4 | 1 (lightest) | Game 2 |
| 5-6 | 2 | Games 3-4 |
| 7-8 | 3 | Games 4-6 |
| 9+ | 4 (full) | Games 5+ |

**Pitching** (threshold: 6+ IP):

| Qualified Pitchers | Max Heat | Season Phase |
|--------------------|----------|--------------|
| 0-1 | 0 (no heat) | Games 1-2 |
| 2 | 1 (lightest) | Games 3-4 |
| 3 | 2 | Games 5-7 |
| 4-5 | 3 | Games 8-12 |
| 6+ | 4 (full) | Games 15+ |

Implementation reference (top-down first-match):
```
Batting:  [(9,4), (7,3), (5,2), (3,1)]  -- 0-2 qualified = max 0
Pitching: [(6,4), (4,3), (3,2), (2,1)]  -- 0-1 qualified = max 0
```

## Coach-Facing Copy: Internal Diagnostics Stay Internal

Engine dataclasses may carry internal/diagnostic fields that must NEVER be rendered raw to the coach. The Most Likely Arms card (`StarterPrediction` in `src/reports/starter_prediction.py`, rendered in `scouting_report.html`) is the live example (E-243):

- **`data_note` is internal-only.** It is a diagnostic string for operators/debugging, not coach copy. The renderer maps the `suppress_reason` discriminator (`"insufficient_data"` / `"unsupported_level"` / `None`) to softened, jargon-free copy and NEVER echoes `data_note`. Any future card with an engine diagnostic field follows the same split: discriminator -> coach copy; raw note stays out of the template.
- **Discounted is not unavailable.** A still-tired arm that PASSES the hard rest gate is *discounted* -- kept in the ranked pool, re-ranked below fully-rested arms, shown with a "Short rest"/"(prefers N)" annotation. Only hard-gate failures land in the "Unavailable today" sub-block. Do not collapse the two: a discounted arm can still start; an unavailable one cannot.

This is the card-copy counterpart of the operator-vs-coach honesty split in `.claude/rules/architecture-subsystems.md` (Reports Package). It does not override "Never suppress" above: that principle governs *stat rows* (present data always renders at full weight), whereas the starter card's suppress state is honest *absence* of a projection, not the hiding of present data.
