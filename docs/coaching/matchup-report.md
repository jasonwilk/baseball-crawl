# Game Plan Section -- Matchup Strategy Report

*Last updated: 2026-04-30 | Source: E-228*

---

## What Is the Game Plan Section?

The **Game Plan** section is a new part of the standalone scouting report that turns raw opponent data into a short, focused at-bat plan for your team. It tells you who to attack, who to pitch around, when the opponent likes to run, when they like to score, and how their losses tend to unfold. It also lists which of their pitchers (and yours) are rested enough to start.

You'll see the Game Plan section right after the executive summary and **before** the Predicted Starter card. It only appears when Jason generates the report with your team selected as the "us" side -- otherwise the report renders without it (the rest of the report is unchanged).

---

## When the Game Plan Section Appears

Three conditions must all be true for the section to show up:

1. **Jason picked your team as "us"** when generating the report (admin form checkbox or `--our-team` CLI flag).
2. **The matchup feature is turned on** in the system (`FEATURE_MATCHUP_ANALYSIS=1`).
3. **The opponent has enough data** to scout. If they have zero hitters with at-bats AND zero losses on file, the engine suppresses the entire section (no placeholder, no "insufficient data" message -- the section is simply not there).

If any of these conditions isn't met, the report renders without the Game Plan section -- exactly like a standard scouting report.

---

## How to Read Each Sub-Section

The Game Plan section opens with a one- or two-sentence intro that frames the matchup. Below that, you'll see six sub-sections:

### 1. Top Hitters

The opponent's three most dangerous hitters this season, ranked by OPS (with PA used as a tiebreaker). Each hitter card shows:

- **Name and jersey number**
- **PA badge** (e.g., `35 PA`) -- how many plate appearances back the ranking
- **A short coaching cue** -- a 1-2 sentence call on how to attack this hitter, with the supporting stat in parentheses inline (e.g., "Pitch around #14 Smith -- patient bat with power (.485 OBP, .633 SLG)").

Below the three hitter cards, you may see a list of **pull-tendency notes** -- full-roster hitters (not just the top three) who are pulling 55% or more of balls in play with at least 10 BIP on file. These say things like "Watch the pull from Brown #7 (62% pull on 24 BIP)." Position your defense accordingly.

If a hitter's PA total is low (under 20), an italic gray "Note: Early read only..." line appears at the bottom of the sub-section. Treat those hitters with appropriate skepticism -- a hot start can fade.

### 2. Eligible Opposing Pitchers

A short table of the opposing pitchers most likely to throw against you, with each pitcher's last outing date, days rest, last outing pitch count, and 7-day workload. This complements the **Predicted Starter** card below -- the predicted starter card tells you who is most likely to start; this list tells you who is *available* to pitch in any role.

### 3. Stolen-Base Profile

A quick read on how aggressive the opponent is on the bases: total attempts, success rate, and attempts per game. When the LLM is available, this is followed by a one- or two-sentence note about what that pattern means for your battery.

If the sample is very small (under 5 attempts), an italic gray "Note: Small SB sample..." line appears.

### 4. First-Inning Tendency

How often the opponent scores in the first inning, plus average runs scored in the first. Knowing this shapes your starter's first-inning approach -- if a team scores in 60% of first innings, your pitcher needs to be sharp from pitch one.

If the season is still young (under 5 games), an italic gray "Note: Thin first-inning sample..." line appears.

### 5. Loss Recipe

Of the opponent's losses this season, how many fit each of three patterns:

- **Starter shelled early** -- their starter gave up 4+ ER in fewer than 4 innings.
- **Bullpen couldn't hold** -- starter went 4+ innings but the bullpen gave up 3+ ER.
- **Close game lost late** -- the final margin was 2 runs or fewer.

Below the counts, when the LLM is available, you'll see a short note interpreting the pattern (e.g., "Most losses come when their starter gets shelled -- be ready to attack early"). If the loss sample is small (under 3), an italic gray note appears.

### 6. Eligible LSB Pitchers

Same shape as sub-section 2, but for *your* pitchers. Use this in tandem with the opposing pitcher list to plan rotation matchups.

---

## Reading the Italic Gray "Note: ..." Lines

These are **data thinness warnings**. The section's underlying engine is conservative -- when a sub-section has very limited data, the renderer adds an italic gray note line at the bottom of that specific sub-section. Examples:

- *Note: Early read only: Smith has 12 PA on the season.*
- *Note: Small SB sample: 3 attempt(s) on the season.*
- *Note: Thin first-inning sample: 2 game(s).*

Each note shows up only in the sub-section it pertains to. If a sub-section has no note, the data is robust enough by the engine's threshold.

---

## When the AI Analysis Is Off

If Jason's system isn't configured with an AI analysis key (or if the AI call fails for any reason), the Game Plan section still renders -- but the LLM-authored prose disappears. You'll see:

- The deterministic data: top-3 hitter names + PA badge + raw stats, all six sub-section headers, pull-tendency notes (always), eligible pitcher tables, SB counts, first-inning rates, loss-recipe bucket counts, and italic gray notes.
- **No** prose intro, **no** per-hitter coaching cues, **no** SB/first-inning/loss-recipe interpretation lines.

The section is still useful in this mode -- you just have to do the interpretation yourself instead of having the LLM phrase it for you.

---

## How to Generate a Report with the Game Plan Section

Ask Jason to generate the report with your team selected as the "us" side. He has both an admin form checkbox and a CLI flag for this. See the operator-facing companion document, [Matchup Report Generation](../admin/matchup-report-generation.md), for the operator workflow.

---

## Related Coaching Pages

- [Standalone Reports](standalone-reports.md) -- the parent page for everything you see in a standalone scouting report.
- [Understanding the Stats](understanding-stats.md) -- plain-language explanations of every stat in the report.
