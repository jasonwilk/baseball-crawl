---
name: E-100 Coaching Domain Review (2026-03-14)
description: Findings from coaching review of E-100 team model overhaul — schema gaps, deferred items, and domain corrections
type: project
---

Coaching review of E-100 completed 2026-03-14 as part of e100-final-refinement team.

**Why:** Pre-dispatch validation that the foundation schema supports real coaching decisions before work begins.

## Confirmed Schema Gap (actioned in E-100-01)

`spray_charts` table needs `pitcher_id TEXT NULLABLE FK -> players(player_id)`.

The pitcher who threw the ball that was put in play is available from the plays endpoint. Without it, spray charts can only answer "where does this batter hit the ball?" — not "what does this pitcher make batters do?" The second use case (offensive scouting vs. a pitcher) is coaching-critical.

**How to apply:** Any future spray_charts schema work must include pitcher_id. All spray chart queries should support filtering by pitcher as well as batter.

## Domain Correction: Travel Ball Tier Values

If travel ball division/tier is added in a future epic, the values are:
**USSSA / AA / AAA / Majors** (NOT Gold/Platinum/Silver).

Gold/Platinum/Silver is NOT the correct USSSA tier nomenclature. Do not use those values in future recommendations.

**How to apply:** When recommending travel ball tier tracking or classification enhancements, use USSSA/AA/AAA/Majors as the value set.

## Deferred Items (no E-100 schema changes)

- **Travel ball tier**: Not now. Schema gap acknowledged, future epic scope.
- **Continuous batting order flag**: Not needed. `batting_order INTEGER` with no upper bound CHECK handles both 9-man and continuous batting orders. USSSA teams use both formats (full order for early tournament, tighten to 9 for deeper play).

## Opponent Stat Provenance (routed to SE/DE)

Opponent season stats have per-column completeness complexity:
1. Stats from opponent's own GC profile (definitive, where accessible)
2. Stats from our boxscore data (supplemental, for fields not in their profile)
3. Some columns may be NULL (never available from either source)

`membership_type = 'tracked'` implies limited data but doesn't capture which fields came from which source. SE/DE determining schema mechanism.

**How to apply:** When presenting opponent stats to coaches, always caveat with sample size AND data source. A tracked team's season line may be partial — surface coverage explicitly in the UI rather than relying on coaches to infer from membership type.

## Items Reviewed and Cleared (no concerns)

- `classification` CHECK constraint values — adequate for HS/USSSA/Legion levels
- `team_opponents` permanent (non-season-scoped) — correct; season scope via games table
- `programs` as organizational metadata, not navigation frame — matches coaching mental model
- Seasons as program-scoped temporal containers — correct; program-level season shared by all teams
- Fresh-start philosophy — handled by queries/UI, not schema
- Batting order column semantics — INTEGER without CHECK is correct for multi-format support
