# Baseball Coach -- Agent Memory

## Team Scope

Lincoln Standing Bear High School baseball program:
- Four teams: Freshman, JV, Varsity, Reserve
- Legion teams added later (different competition level, different season)
- 12-15 players per team
- ~30-game seasons
- Jason is the system operator; coaching staff are the end consumers
- Coaches see reports -- they do not interact with the system directly

## Epic Consultations

- [E-100 coaching review (2026-03-14)](e100_coaching_review.md) -- Schema gaps, domain corrections, and cleared items from E-100 team model overhaul review
- [E-235 trust block design + review (2026-06-13)](e235_trust_block_review.md) -- Signal set, severity tiers, operator/coach split, no-games message, and AC-2 defect found in holistic review
- [E-236 integrity hardening review (2026-06-14/15)](e236_integrity_hardening_review.md) -- no_games two-case copy, Option A confirm, partial-stage operator-only, SQ1 hard failure, 403/404 reconciliation (M=0 filter already handles no-scorebook teams)
- [E-240 morning reports discovery (2026-06-17)](e240_morning_reports_discovery.md) -- Expiry Option A recommended, three-way outcome surfacing, scheduled email UX requirements, hard gates vs soft flags, wrong-opponent mitigation
- [E-257 reconciliation scoreboard review (2026-07-08)](e257_reconciliation_scoreboard_review.md) -- Equal-weight AB/H/BB/SO as headline fidelity metric (not BF/FPS), exempt-but-display abandoned-PA residual, FPS plausibility floor widened to 30%

## Key Reference Documents

- **Stat glossary**: `docs/gamechanger-stat-glossary.md` -- authoritative data dictionary mapping all GameChanger stat abbreviations to definitions (batting, pitching, fielding, catcher, positional innings). Includes API field name mapping table for cases where API abbreviations differ from UI labels (e.g., K-L -> SOL, HHB -> HARD, SAC -> SHB). Use this when validating schemas or consulting on field mappings.

## Established Stat Priorities

### Batting (ranked)
- **OBP** -- the most important offensive stat. Getting on base is the foundation.
- **K%** -- strikeout rate. Identifies swing-and-miss problems.
- **BB%** -- walk rate. Shows plate discipline.
- **BABIP** -- with heavy caveats about sample size at HS level.
- **SLG** -- slugging. Power matters but less than OBP at this level.
- **Splits**: home/away and vs. LHP/RHP. Both stored as nullable columns in season stats tables.

### Pitching (ranked)
- **K/9** -- strikeout rate per 9 innings. Shows dominance.
- **BB/9** -- walk rate per 9. Shows command.
- **K/BB ratio** -- the best single number for pitcher quality at HS level.
- **Pitch counts** -- critical for arm health and compliance.
- **HR/9** -- home run rate (less meaningful in small samples but tracked).
- **FIP** -- if we have the components (K, BB, HR, IP).
- **Splits**: vs. LHB/RHB stored as nullable columns.

### Base Running
- SB success rate
- Extra bases taken

### Fielding
- Error rates by position (advanced fielding metrics rarely meaningful at HS level)

## Sample Size Rules

High school baseball has small samples. These thresholds are firm:
- **Batting**: Flag any stat based on fewer than 20 plate appearances. A 30-game season yields only 80-100 PA total; L/R or home/away splits may have 20-40 PA per bucket.
- **Pitching**: Flag any stat based on fewer than 15 innings pitched. Starters may throw 40-60 IP per season.
- Always present stats with context: "In 23 PA vs lefties, .350 OBP (small sample)"

## Output Format Conventions

- Label every recommendation: **MUST HAVE**, **SHOULD HAVE**, or **NICE TO HAVE**
- Include sample size caveats in every recommendation, every time
- Make outputs bench-ready -- a coach sitting in the dugout 30 minutes before first pitch should be able to act on it
- Show what a result looks like: example scouting reports, example query results, example lineup cards
- Be specific: "Track plate appearance outcomes (H, 2B, 3B, HR, BB, HBP, K, other out) with pitcher handedness, game location, and date" not "track batting stats"

## Multi-Team, Multi-Season Tracking (Non-Goal)

Cross-team player identity and multi-season/longitudinal tracking are explicitly out of scope -- removed in E-239 (ROADMAP D2, 2026-06-17). Each team-season stands alone; see `docs/ROADMAP.md` and `docs/VISION.md` for the reports-first reframe.

## Scouting Model

- [probable-starter-model.md](probable-starter-model.md) -- Deterministic probable-starter prediction model: ranked signals, NSAA/Legion rest thresholds by league+level+phase, role classification rules, committee handling, report output shape, backtesting scoring
- [league-pitch-rules.md](league-pitch-rules.md) -- Per-league pitch count rules: gate keyed by league x level x phase; NSAA breakpoints (30/50/70/90/110) differ from Legion/Pitch Smart (30/45/60/80/105); Sub-Varsity +1 day stricter; implementation gap in starter_prediction.py

## Topic File Index

- [endpoint-coaching-value.md](endpoint-coaching-value.md) -- Per-game stats, boxscore, and plays endpoint coaching value (MUST HAVE/SHOULD HAVE priorities, pipeline dependencies, endpoint comparisons)
- [scouting-pipeline.md](scouting-pipeline.md) -- Schedule, team-detail, public endpoints, opponents, and roster coaching implications with full scouting pipeline steps
- [coaching-decisions.md](coaching-decisions.md) -- The six core coaching decisions this system serves (lineup, pitching, scouting, development) plus data storage conventions (ip_outs, splits, FK-safe orphans, key entities)
