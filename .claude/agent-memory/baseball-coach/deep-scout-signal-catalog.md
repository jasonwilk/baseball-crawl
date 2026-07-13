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
