# Defensive Positioning — Coaching Domain Reference

Coaching-facing knowledge for the defensive positioning subsystem produced by E-228 + E-229. The engineering / coord-convention side lives in `.claude/rules/positioning-vocabulary.md`; this file captures what the coach actually consumes and the reasoning behind the design choices the coach validated.

## The Three Coach Artifacts (4-Page Bundle)

A defensive positioning report is a single 4-page mixed-orientation PDF, generated per opponent. The coach prints once pre-game and uses it through 7 innings.

1. **Page 1 — In-game call sheet** (letter landscape). Jersey × position matrix. Coach reads this in the dugout to call a shift: jersey number on the left, zone letter for each fielder across. Alphabetical sort by last name (NOT by jersey, NOT by severity — coach lock during E-229-07).
2. **Page 2 — Pre-game prep page** (letter landscape). Full-field overlay showing all 6 positions and all outlier batters on one field. Used 30 minutes before first pitch for opponent review.
3. **Pages 3-4 — Per-position player pocket cards** (letter portrait, quarter-letter 4-up). Cut after printing into 6 cards (LF / CF / RF / 3B / SS / 2B) plus a coach-facing visual compass key and opponent-context card. Handed to fielders pre-game; survives a back pocket.

The bundle is regenerated, not edited in place. Coverage cue (`Through {Mon Day} ({N} games)`) is snapshotted at generation time — re-viewing the bundle does NOT see updated coverage; the next regeneration does.

## The 8-Zone Compass (How Coaches Read It)

Each per-position card shows ONE position's field diagram with:

- **The star** = where this opponent's whole-spray centroid says THIS fielder should shade by default. Per-opponent. Moves between opponents; the compass letters do not.
- **The faint open circle** = the textbook BASE_POSITION for context — where a fielder learns to stand in practice. Reference only.
- **A-H compass letters** at fixed angular positions around the star — populated zones at full opacity, empty zones at 30% opacity. Stable across opponents (fielder learns the compass once and reuses it all season).
- **Outlier batter pills** at their `(x, y)` deviation from the star — jersey + truncated last name on each pill.

Zone meaning (the compass key card on sheet 2 is the coach's reference):

| Zone | Coach calls it             |
|------|----------------------------|
| A    | "in and left"              |
| B    | "left"                     |
| C    | "deep and left"            |
| D    | "in" (centered)            |
| E    | "deep" (centered)          |
| F    | "in and right"             |
| G    | "right"                    |
| H    | "deep and right"           |
| NULL | "play the star" (no shift) |

"In / deep" is the locked axis vocabulary. NOT "shallow / deep" — coach lock during E-229 (E-228 used "shallow" and the coach corrected to "in" because that is what gets shouted in the dugout — "bring it in", "play them in").

## Coverage Tiers — What the Card Shows by Tier

The system never lies about its own coverage. Three tiers map to three card states:

- **Full (50+ BIPs against this opponent)**: Solid star with `(N BIP)` caption, outliers rendered, faint density background showing where this opponent's hits have been landing.
- **Thin (15-49 BIPs)**: Star with a dashed ring + `(~N BIP)` caption. Outliers still render. NO density background (the sample is too thin to draw a meaningful spray pattern).
- **Zero (0-14 BIPs)**: NO star. Card body shows "Not enough spray data — play your standard alignment." NO outliers. NO density background.

The system does NOT fall back to the textbook base position when coverage is zero — that would silently say "play this opponent as if they were generic" and re-introduce the E-228 reference-frame bug. Zero-coverage is an honest "we don't know yet" message.

15 BIPs ≈ 1 full HS game. 50 BIPs ≈ 3-4 games. Tier thresholds were coach-calibrated.

## What the LLM Adds (Tier 2 Rationale)

A small italic note can appear next to a flagged batter — only on coach surfaces (prep page sidebar second-line + call sheet NOTE column), NEVER on the fielder cards (the cards have to fit in a back pocket; legibility wins over rationale). The note explains WHY this batter sits in their zone in plain English — pulled, late hitter, weak against fastballs, etc.

The rationale is render-time only — it is regenerated when the bundle is regenerated. There is no audit log of what the LLM said last time. If the LLM is unavailable, rationale slots render empty without crashing the bundle.

## What the Coach Doesn't See (Retired in E-229)

The E-228 categorical vocabulary ("SHADE LEFT", "MIXED", "L Sh", "R Sh", per-position glyphs) is gone. If a coach asks about "the L-shade" or "the MIXED zone", they are remembering the E-228 design — the E-229 design replaces categorical text with the spatial compass + outlier pills.

The per-handedness card variants (one card for LHB, one for RHB) are NOT in v1 and are unlikely to ever ship — handedness is not in the GameChanger scouting data we can pull. The team-aggregate star averages across all batters; handedness-driven variance surfaces through individual outlier pills, not through separate cards.

## Calibration Rollout

After E-229 lands, the user (Jason) runs a first-real-opponent calibration pass: generate the bundle for a real opponent, eyeball the team-aggregate stars against the spray chart, and tweak the position-scaled projection constants and confidence-tier thresholds if needed. The compass letter ordering and zone vocabulary are NOT calibration-time decisions — they are coach-locked.
