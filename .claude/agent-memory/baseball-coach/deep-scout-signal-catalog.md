---
name: deep-scout-signal-catalog
description: Ranked scouting signal -> on-field exploit catalog for the Deep Scout effort (2026-07-13 consultation) -- value tiers, sample floors, ethics split per signal
metadata:
  type: project
---

Domain-content deliverable for the Deep Scout "Scouting Signal Catalog" consultation (team-lead request, 2026-07-13). Companion to [[probable-starter-model]] and [[league-pitch-rules]]; background in `.project/research/deep-scout-design-2026-07-12.md`.

**Why:** claude-architect designs WHERE the catalog lives and HOW it's stored; this file is the coaching WHY -- which signals earn a roster spot on a Friday-night one-pager, and which are noise.

**How to apply:** When PM or claude-architect scopes a Deep Scout epic, this is the domain input for prioritizing sections and their sample-floor/ethics gates. Full per-signal detail (exploit action, tier, floor, ethics) was delivered to team-lead via SendMessage on 2026-07-13; this file holds the durable summary so a future session doesn't have to re-derive it.

## Tier summary (the 15 given signals)

**MUST** (changes a lineup card, positioning, or in-game call): probable starter (deterministic eligibility + rank), per-arm innings-weighted control (BB/7, SO/7, strike%, two-branch approach), loss-forensics blueprint conditioned on the probable starter, first-pitch-strike% (ambush/patience call per hitter), steal light, battery-control/backpick card (dual-use: defend our runners AND bait first-and-third), defensive alignment directive (GB%+side -> shade/in/deep), error-map -> bunt/pressure targets.

**SHOULD** (real, situational, or a refinement of a MUST): times-through-order fade, running-game concentration (top-2 SB share -- key-on-2 vs team-wide hold), leg-hit/speed-inflation ledger (pairs with alignment), slasher overlay (compound of steal+leg-hit+alignment), lineup-slot reach-base shape, GDP-prone hitters, TOOTBLAN/aggression-cost (frequently a NULL result -- valuable specifically for ruling OUT a press play, e.g. "154 SB at 95%, only 11 outs = don't bother, they're too good, control the free 90s instead").

**SKIP for v1**: none of the 15 were SKIP-tier; all cleared the "changes a decision" bar. TOOTBLAN is the one to explicitly document as often-NULL so the memo doesn't force a finding where none exists.

## New signals recommended (not in the 15)

- **First-inning wobble per starter** (MUST) -- sets the locker-room script's opening line and top-of-order approach; needs 4-5+ starts before calling it a pattern.
- **Bunt-defense report card** (SHOULD, a bunt-specific slice of the error-map MUST) -- single-digit season sample typically, raw counts only, never a rate.
- **Rally-starter / leadoff-slot OBP** (SHOULD) -- narrower sibling of lineup-shape; weight recent games per the lineup-drift lesson (§8 of the design doc).
- **Two-strike chase rate (their hitters)** (SHOULD) -- pitch-calling intel for our arm; charted-subset, badge the denominator.
- **Opposing-coach substitution pattern** (SHOULD) -- entirely about the OTHER coach's decisions, not a player, so ethics gate is moot; needs 5+ games of that specific opposing coach.
- **Backup-catcher exploit window** (SHOULD, situational) -- near-certain no_data on the backup's own numbers; the actionable instruction is "watch for the sub, then default aggressive," not a computed rate.

## Cross-cutting doctrine confirmed in this pass

- **Ethics tier default**: coach-facing = full names/full data everywhere. Player-facing = team-tendency/number-only, NEVER a named opposing kid next to a weakness -- confirmed as the sharpest risk on the steal light (named catcher arm) and the leg-hit ledger (named hitter's inflated AVG). The ONE explicit exception: positioning/alignment cards may reference a hitter by number for alignment only (design doc §5's existing ethics rule) -- not a new carve-out, just re-confirmed as it applies across the 15.
- **Sample floors reused, not reinvented**: 20 PA batting / 15 IP pitching (season rate stats), 15 BIP (directional/alignment), 5 attempts (steal light), and the design doc's new "raw counts only, never a rate" rule for genuinely sparse events (backpicks, bunt-defense chances) -- extend this last rule to any event with a single-digit season count rather than inventing a new floor per signal.
- **Join, don't average**: the recurring correction across MUST-tier signals is conditioning on the SPECIFIC arm/hitter facing us tonight rather than a team/staff aggregate (design doc §8's live-validation lesson) -- applies to per-arm control (#2), loss-forensics (#3), and first-inning wobble equally.

## E-263 v2 methodology corrections (2026-07-18, two adversarial design reviews)

Graded a live report against a finished game: predicted the opponent's #2 starter correctly (top-2 hit), but he pitched WILD that night rather than the "hittable" our season-keyed point-lean implied; we won on walks. Codex (gpt-5.6-sol) + a Fable model converged on three stat-methodology fixes + one rendering fix. All computable from data already in the DB (plays' per-pitch strike/first-pitch flags from E-245, the season game log's W/L + walks/steals/errors/first-run). No new crawling.

### (1) Two-branch plan needs a LIVE in-game identification cue, not a season-keyed lean (SIG-004)
Season stats set the PRIOR (which outcome is more LIKELY); they CANNOT tell a coach which world they're in TONIGHT -- command varies by outing, so a season-keyed "if wild / if locating" branch is nearly unfalsifiable day-of. **The report must print a concrete cue the coach eyeballs in the first ~5 hitters (roughly first 1-2 innings):** count first-pitch strikes and deep (3-ball) counts.
- **WILD tonight** = throws strike one to ≤2 of the first 5 hitters, OR runs 2+ three-ball counts in the first two innings → *"Take until he proves the strike."* Take strike one, don't chase out of the zone, cash the free 90s (walks); don't expand.
- **LOCATING tonight** = strike one to ≥4 of the first 5 AND stays out of three-ball counts → *"He's around the plate -- get a good pitch early and put it in play; don't dig a hole taking. Once on, run."*
- Middle (3 of 5) = default to patience early, then adjust.
- Anchor: league-average first-pitch-strike is ~58-60%; "wild for him" also references his own season FPS so the coach knows the baseline. First-pitch strikes and 3-ball counts are the two things a dugout coach naturally already tracks -- that is why they're the cue, not a live-computed rate.

### (2) Loss "blueprint" = LIFT over base rate, NOT "majority of losses" (SIG-005)
"Present in a majority of losses" is misleading -- "scored first" correlates with winning generically, and walks/steals are exposure-sensitive. A lever only matters if the thread happens MATERIALLY MORE in their losses than in their wins.
- For each candidate thread (opponent issued 4+ walks, allowed 2+ steals, gave up the first run, committed 2+ errors, held scoreless through 2, etc.): compute `loss_rate` = share of LOSSES with the thread and `win_rate` = share of WINS with it; surface the LIFT = loss_rate − win_rate.
- **Loss-count floor:** <5 losses → NO blueprint; everything is a "historical thread (small sample)." A ~29-game summer season yields only ~8-12 losses, so this floor bites often.
- **"Blueprint" label** (build the game plan on it) requires present in ≥60% of losses AND loss_rate − win_rate ≥ +25 pts (~twice as common in losses). Otherwise **"historical thread"** (note it, don't build on it).
- Coach-legible rendering = raw fractions, which ARE the lift: *"happens in 6 of their 9 losses but only 2 of their 14 wins."* The lift math naturally kills generic threads (e.g., "they scored first") because those are ~equally present in wins.

### (3) "Volatility" = across-START dispersion, NOT moderate-strike%+high-BB (RETRACTION)
**I earlier floated a "both tails for volatile arms" rule keyed on moderate strike% + high walk rate -- that is WRONG and is retracted.** That describes a LEVEL (a mediocre-command arm), not volatility, and would slap "both tails" on nearly every HS arm. Volatility is across-OUTING dispersion:
- Take the arm's last N starts (up to ~6). Compute per-start strike% (strikes/pitches; FPS% if available). Volatility = the SPREAD (range = max−min, or IQR with enough starts); report median ± range.
- **Start-count floor:** <4 starts → *"Consistency: unknown -- only N starts."* Do NOT guess. Realistic because committee arms make only 2-4 starts a summer.
- **Steady** = per-start strike% range ≤ ~10 pts → you get the same guy every time; trust the season line. **Volatile** = range ≥ ~15 pts → command is a coin-flip by night; DON'T trust the season average -- the live cue from (1) is decisive for this arm. Middle = "moderately consistent."
- Volatility feeds (1): volatile arm → the in-game cue governs; steady arm → the season line is reliable.

### (4) Game-Plan rendering shape (E-263-07 / TN-5) -- RECOMMENDED
Replace "one bullet per committee arm" with a robust/fork/cue/fallback shape, rendered as ≤3 bullets (fits the ≤600-word / 60-sec budget). Rationale: top-2 prediction is only ~40% accurate (see [[probable-starter-model]] backtest), so one-bullet-per-arm forces the coach to guess the starter first and ~60% of the time key on the wrong bullet. Front-load what's true regardless of who takes the ball. Fold the identification cue INTO the fork bullet (the cue is how you resolve the fork) rather than making it a 4th bullet. When it's NOT a committee (HIGH-confidence single ace), collapse to 2 bullets (the arm's read + the live cue) -- don't force a fork that doesn't exist.
