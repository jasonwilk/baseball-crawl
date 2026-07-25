---
name: probable-starter-model
description: Domain model for predicting probable starting pitcher in opponent scouting reports — signals, rest thresholds, role classification, committee handling, output shape, and backtesting scoring
metadata:
  type: project
---

# Probable Starter Prediction Model

Consulted 2026-06-27 for scouting report redesign. The LLM was producing hedge-heavy "committee situation" outputs and ignoring physical constraints. The fix: deterministic heuristic computes the candidate list and ranks arms; LLM narrates the computed result only.

## Core Principle
LLM writes words. It does not rank arms. All eligibility, role, and rotation logic is deterministic.

## Two Bad-Example Root Cause
Both failures came from missing two hard gates:
1. **Applicable league/level/phase rest gate** — must disqualify ineligible arms before prediction (gate is keyed by league × competition level × season phase; see [[league-pitch-rules]] — not Pitch-Smart-specific)
2. **Preferred-rest discount** — arms that clear the minimum but are still inside the preferred rest window get demoted below fully-available arms (HARD tiebreaker), not softly downweighted

## Ranked Prediction Signals

### Tier 1 — Hard gates (disqualify before prediction)
- Rest/eligibility by pitch count per applicable league/level/phase table (NSAA or Legion — see [[league-pitch-rules]] and threshold section below)
- Established starting role (GS share, appearance_order history)

### Tier 2 — Primary soft signals
- Rotation slot / least-recently-started among eligible starters (dominant predictor)
- Ace identification (top arm by GS share, quality stats) → elevated for high-stakes games

### Tier 3 — Secondary signals
- Game stakes (playoff/conference → pull ace forward)
- Home/away (modest effect, not primary)
- Doubleheader context (separate prediction context entirely)
- Season phase (early season: more experimentation; post-midpoint: rotation locks in)

## Rest Thresholds — Gate Is Keyed by League x Level x Phase

**NSAA and Legion use different breakpoints. Do not conflate them.**
Full authoritative tables (including NRBL), daily max caps, hard/guideline flags, the season x level classification model that picks the league family (E-272), universal NSAA rules (doubleheaders, midnight rule, ambidextrous pitchers), and the corrected structural conclusion are in [[league-pitch-rules]].

### NSAA Varsity (breakpoints 30/50/70/90/110)
Two phases. Pre-April 1 daily max is 90 (no 91-110 tier). April 1-State daily max is 110.

| Pitches | Required rest |
|---------|---------------|
| 1–30    | 0 days        |
| 31–50   | 1 day         |
| 51–70   | 2 days        |
| 71–90   | 3 days        |
| 91–110  | 4 days (April 1–State only) |

### NSAA Sub-Varsity — JV, Reserve, Freshman (daily max 90, all season)
Stricter than Varsity by exactly one rest day at every tier.

| Pitches | Required rest |
|---------|---------------|
| 1–30    | 1 day         |
| 31–50   | 2 days        |
| 51–70   | 3 days        |
| 71–90   | 4 days        |

### Legion Senior (18U) = Junior (17U) (daily max 105, all season)
This is the Pitch Smart 15-18 curve. Different breakpoints from NSAA.

| Pitches | Required rest |
|---------|---------------|
| 1–30    | 0 days        |
| 31–45   | 1 day         |
| 46–60   | 2 days        |
| 61–80   | 3 days        |
| 81–105  | 4 days        |

### Days-of-rest computation (all leagues)
`days_rest = (game_date - last_appearance_date).days`
Eligible: `days_rest >= required_rest_days`
(Day 0 = appearance date. Game day is not a rest day.)

### Two-tier availability model
- **UNAVAILABLE**: days_rest < applicable league/level/phase minimum. Hard gate. Never override.
- **AVAILABLE BUT DISCOUNTED**: days_rest >= minimum but < preferred rest window. **HARD tiebreaker**: all fully-available arms rank above all discounted arms in the candidate list (stable partition — relative order within each group preserved). Soft/graduated weight penalties were validated as ineffective in backtesting (17 opponent seasons) — they made no measurable difference on top-1 accuracy.

### Preferred rest thresholds (for starter role)
- 0-30 pitches: 2 days preferred
- 31-60 pitches: 4 days preferred
- 61+ pitches (full start): 5 days preferred

**Fallback when pitch count unavailable:** Use IP proxy: ≤2 IP → 0-30 bucket, 3-4 IP → 31-60 bucket, 5+ IP → 61+ bucket. Flag as estimate. **M1 ruling: null pitch count is always DISCOUNTED, never fully-available.** Treating null as available would invert the conservative-when-uncertain principle — and the null path fires precisely for youth/travel opponents where pitch tracking is least reliable. Confirmed against as-built implementation: `_rest_state()` routes null pitch count through the IP proxy; any non-zero preferred-rest result → DISCOUNTED (minimum preferred-rest is 2 days, so null is always DISCOUNTED).

## Role Classification

From appearance_order and innings data:

| Metric                              | STARTER     | SWING         | RELIEVER  |
|-------------------------------------|-------------|---------------|-----------|
| GS share (starts / total apps)      | ≥ 0.60      | 0.25-0.59     | ≤ 0.25    |
| Avg IP when entering as appearance_order=1 | ≥ 4.0 IP | — | — |

CLOSER/LATE RELIEVER: avg appearance_order ≥ 2.5

**Rule:** RELIEVER and CLOSER roles are disqualified from the probable starter list unless the team has fewer than 2 STARTER-classified arms.

**Sample size caveat:** Requires ≥ 5 appearances for reliable classification. Fewer → ROLE UNCLEAR, include with soft discount.

## Algorithm (deterministic steps)

1. For each pitcher: compute rest status (UNAVAILABLE / AVAILABLE BUT DISCOUNTED / FULLY AVAILABLE)
2. Classify role (STARTER / SWING / RELIEVER / CLOSER / ROLE UNCLEAR)
3. Eliminate UNAVAILABLE and RELIEVER/CLOSER arms from candidate pool
4. Among eligible starters: rank by least-recently-started (longest days since last start = highest priority)
5. Apply preferred-rest HARD tiebreaker: re-rank so all fully-available arms sort before all discounted ones (stable — preserves relative order within each group)
6. Apply quality boost to ace arm for high-stakes games
7. Score and rank; assign confidence level
8. Pass ranked list + unavailability list to LLM for narration

## Confidence Levels
- **HIGH**: Single clear arm, others unavailable or discounted, OR clear ace with 6+ days rest
- **MEDIUM**: 2 arms both eligible and close in rotation position
- **LOW**: 3+ arms genuinely equal — rare, but still produce a top-2 ranked list

## Committee Teams: Never Refuse to Predict

Even true committee teams are narrowed by:
1. Rest elimination (often removes 1-2 arms per game day)
2. Role filter (committees are still STARTER/SWING arms, not relievers)
3. Rotation sequence inference (least-recently-started)
4. Stakes weighting (best available quality arm for important games)

Minimum output: "X arms are unavailable by rest. Of Y eligible arms, [Name] has the longer rest gap and better K/BB [N IP]. Confidence: MEDIUM."

## Live-Run Refinements — 2026-07-18 (least-recently-started mis-ranked in BOTH runs)

The two 2026-07-18 Legion scouting runs (Norfolk, Columbus) each exposed a case where pure "least-recently-started" (Algorithm step 4) picked the wrong arm. Two distinct refinements:

### (a) Layoff ambiguity — "hasn't STARTED in N days" ≠ "hasn't APPEARED in N days"
The ranking signal must distinguish days-since-last-**start** from days-since-last-**appearance**. They diverge for swing arms and for rested aces:
- **Norfolk failure:** demoted swing arms (only 2 starts all season, last start weeks ago) floated to #1 on the naive least-recently-started metric — their long start-gap looked like "next in the rotation" when they simply aren't starters anymore.
- **Columbus failure:** an 11-day team schedule gap made the WHOLE rotation look equally stale, so days-since-start couldn't separate anyone. The naive metric would pick the longest-idle arm (23 days) over the actual answer — the *held ace* who was deliberately rested through an opener/bulk game the day before.
- **Domain rule:** an arm that has been idle (NO appearance) for a long stretch is a **WILDCARD, not "due."** A long no-appearance gap is weak evidence of an imminent start (could be injury, could be buried on the depth chart, could be a held ace) — it should NOT auto-elevate to #1. Weight recent-appearance-but-not-recent-start (a held/managed ace) at least as highly as a total-layoff arm. Consider capping or discounting the least-recently-started boost once the idle gap exceeds normal rotation spacing.

### (b) Opener/bulk usage — appearance_order=1 mislabels the "opener"
Columbus opened one game with a 28-pitch, 0-out "opener" followed by a bulk arm. `appearance_order=1` tags the OPENER as "the starter," but the hitters mostly faced the bulk guy.
- **Domain rule:** GS-by-`appearance_order=1` mislabels openers as starters. Detect the opener pattern — `appearance_order=1` with very low pitch count AND ~0 outs recorded (e.g., ≤ ~35 pitches / < 1 IP) followed immediately by a higher-workload arm — and treat the BULK arm as the effective starter for both role classification (GS share) and the scouting narrative. The coach cares who they'll actually face for the bulk of the game, not the ceremonial first-batter opener. Flag as a distinct usage pattern ("opener + bulk") in the report rather than silently naming the opener.

Both refinements argue the same thing: raw `appearance_order=1` counting and raw least-recently-started are too naive for the real usage patterns Legion teams show. Keep the deterministic engine, but sharpen these two inputs.

## Report Output Shape

**Validated shape: ranked top 2–3 most likely arms** (not a single predicted starter).

**Why ranked, not single-named — backtest finding (17 opponent seasons / 357 games):** The engine commits to one name only rarely. When it does, that prediction is wrong ~85% of the time. Overall top-1 accuracy across all games is ~20%; top-2 is ~40%. "Committee" is structurally true at the high school level — pitch-count caps mean no arm owns the rotation the way an MLB ace does. The honest, actionable output is a ranked list, not a headline name.

```
MOST LIKELY ARMS
#22 Martinez — RIGHT
7 days rest | Last outed June 20 (58 pitches, 5.1 IP)
8 of 12 GS this season (67%) | K/BB 2.8 (37.2 IP)
Fully available

#33 Williams — LEFT
4 days rest | Last outed June 23 (38 pitches, 3.0 IP)
3 of 12 GS this season (25%) — swing role
Fully available

#7 Ramirez — RIGHT
2 days rest | Last outed June 25 (52 pitches, 4.1 IP)
5 of 12 GS this season (42%)
Discounted — prefers 4 days rest

UNAVAILABLE TODAY
#14 Johnson: 88 pitches 1 day ago — needs 3 days rest (NSAA Varsity)
#8 Torres: 67 pitches 1 day ago — needs 2 days rest (NSAA Varsity)
```

Design rules:
- **Ranked top 2–3 arms, always a list.** The old "One name at top, always" framing is retired — the backtest showed it is wrong ~85% of the time on the rare occasions the engine commits to one name.
- **Fully-available arms sort above discounted arms** (hard tiebreaker). Show rest eligibility inline: "Fully available" or "Discounted — prefers N days rest".
- Handedness mandatory (coach needs it for lineup construction immediately)
- Sample size badge on all rate stats: "K/BB 2.8 (37.2 IP)"
- Unavailability section always present
- No narrative hedging, no conditional prose, 10-second scan target

**Deep Scout Game-Plan rendering (E-263 v2, 2026-07-18):** The ~40% top-2 accuracy above is the reason the Deep Scout Game Plan does NOT render one bullet per committee arm (the coach would key on the wrong bullet ~60% of the time). Instead: robust-across-arms / the-one-fork+live-cue / unknown-arm-fallback, as ≤3 bullets. Full definition in [[deep-scout-signal-catalog]] §"E-263 v2 methodology corrections" (4).

## Backtesting Scoring

### Validated Findings (17 opponent seasons / 357 games — 2026 backtest)

- **Top-1 accuracy ~20%** across all games. The engine rarely names one clear starter; when it does, the prediction is wrong ~85% of the time.
- **Top-2 accuracy ~40%.** The ranked list (2–3 arms) is the correct output shape.
- **Committee is structurally true** at the high school level. Pitch-count caps mean no arm owns the rotation the way an MLB ace does; the engine cannot reliably isolate a single starter from boxscore data alone.
- **Soft/graduated rest penalties were ineffective.** Replacing the soft downweight with a HARD fully-available-first tiebreaker produced no regression on top-1 accuracy and a measurable improvement on unavailability recall. The hard partition is the validated mechanism.
- These findings are the basis for the "ranked top 2–3 arms" output shape (see Report Output Shape above).

**Primary:** Top-1 accuracy
- Hit = predicted #1 is actual appearance_order=1. Score 1.0.
- Near-miss = predicted #1 appeared but as appearance_order ≥ 2. Score 0.5.
- Miss = different arm started. Score 0.

Track separately: ace-rotation teams (one arm GS share ≥ 0.50) vs. committee teams (no arm above 0.40). Expected ace-rotation accuracy: 70-80%. Committee accuracy: lower, acceptable.

**Secondary:** Top-2 accuracy (primary metric for committee-team subset)
Hit if actual starter appears in #1 or #2 slot.

**Tertiary:** Unavailability recall
% of UNAVAILABLE predictions where pitcher did NOT start. Target >90%.

**Backtesting protocol:**
- Input state = all boxscore appearances with date strictly before target game (no lookahead)
- Label = actual appearance_order=1 pitcher in target game
- Minimum 8 labeled games per opponent season for a valid accuracy number

**Calibration check:**
- HIGH confidence hitting < 75% → tighten gap threshold for HIGH designation
- MEDIUM hitting > 70% consistently → threshold may be miscalibrated low

**Edge case:** appearance_order=1 pitcher removed after one pitch (injury/tactical) still counts as the game's "starter" for labeling purposes.
