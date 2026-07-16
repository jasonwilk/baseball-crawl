---
name: e265-krate-and-highlight-ruling
description: E-265 (Pitcher Outings Breakdown) -- IDEA-141 K-rate stat set resolved (K/BF over K/G), per-outing raw-count confirmation, and green-only highlight thresholds under the operator's locked highlighting scheme
metadata:
  type: project
---

Consultation (2026-07-15) during E-265 refinement, resolving IDEA-141 (the K-rate decision E-264 deliberately deferred -- see [[e264-era-basis-scope-consultation]]) and the concrete green-highlight thresholds under the operator-locked green-only scheme (overriding my original two-signal red-exploit/neutral-respect recommendation in [[pitcher-outings-scouting-consultation]] -- do not re-litigate; green-only is settled).

## Per-outing row: raw counts confirmed, not rates

K and BB stay as raw counts on the per-outing row (Date|Opp|IP|BF|H|HR|BB|K|R|FPS%|ERA(game)), not per-outing rate stats. A single outing is too small a sample to normalize (2 K in 0.2 IP as a "rate" is nonsense), and it mirrors how GameChanger's own boxscore shows a single game -- counts, not rates.

## Season-summary line K-rate set: K/BF | BB/INN | K/BB (NOT K/G)

Resolves IDEA-141. Ruled against the "replace K/9 with K/G" option PM-2 offered -- chose **K/BF** instead:
- No legacy number to protect on this brand-new surface, so the "coaches expect traditional K/9" argument from E-264 (which was specifically about NOT disrupting an already-displayed number) doesn't transfer here -- free to pick the best-fit stat.
- K/BF sidesteps the entire innings-per-game basis-disclosure apparatus E-264 built for ERA (asterisk/footnote machinery) -- a real scope win, not just a stat-purity preference. K/G would have required re-running that machinery on a brand-new surface for a non-ERA stat.
- K/BF is more tactically honest for opponent-scouting purpose: isolates swing-and-miss rate independent of choppy HS bullpen IP totals.
- BB/INN is GC's real field (not invented BB/9), consistent with WHIP's existing per-inning framing elsewhere on the report.
- K/BB retained per original SHOULD HAVE ranking (best single quality number at HS level); shares its K/BF numerator with the strikeout-rate column, so the two reinforce rather than duplicate different bases.

Do not show K/9 or K/G on this line -- three focused numbers only.

**Sample caveats**: flag when built on <15 IP or <~40 BF (firm threshold). K/BB additionally needs its own BB-count caveat below ~3-5 BB (the ratio is numerically unstable at very low walk counts) -- badge the BB count next to K/BB specifically, not just IP/BF. Never suppress regardless of sample.

## Green-only highlight thresholds (respect/strong direction, operator-locked scheme)

Any ONE of these four qualifies an outing for the green highlight (OR, not AND):
1. **Command**: BB = 0 across IP >= 3.
2. **Aggression**: FPS% >= 65% across BF >= 10.
3. **Dominance**: K >= 2/3 of BF (per-outing K/BF >= .667) across BF >= 10 -- deliberately the same .667 cut as the season-line K/BF stat for internal consistency.
4. **Shutdown**: R = 0 (not ER) across IP >= 4 -- uses R because it's the column actually visible in the row; flagging off a hidden ER number would leave a coach unable to see why a row is green from the visible columns alone.

**Sample floor**: no highlight when BF < 10 AND IP < 2 (same floor as the original exploit-direction thresholds). A 0.1-IP mop-up appearance never gets colored but still shows its raw counts plainly.

Thresholds are illustrative-but-ready-for-ACs; flagged to PM-2 that SE/DE should gut-check against real outing distributions before finalizing, same caveat as the original exploit thresholds.

## Status
Delivered to PM-2 during E-265 refinement (2026-07-15). IDEA-141 resolved by this ruling.
