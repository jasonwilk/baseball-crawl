# IDEA-178: `ngb=american_legion` shadows NRBL — E-272's new league does not fire for real NRBL teams

## Status
`CANDIDATE` — **live defect in shipped code (E-272, 2026-07-25). The gating baseball-coach ruling is now IN (below), so this is PROMOTABLE — the design is settled and only prioritisation remains.**

## PM TRIAGE 2026-07-25 — build the detection as DISPLAY-ONLY; the precedence change becomes CONTINGENT

**Accepted, with the contingency preserved rather than dropped.** ux-designer's Revision 2026-07-25b (`/workspaces/baseball-crawl/.project/research/2026-07-25-uxd-competition-level-disclosure-design.md`) recommends reusing this idea's reserve-age detection as a **display-only overlay** that never touches resolution, rendering two lines when they diverge:

```
Rest rules: American Legion
Level: NRBL (Summer Reserve)
```

`rules_label` names the table that computed the numbers; `level_label` names the scouting tier, computed independently of which table won.

**Verified premise, first-hand:** `LEGION` (`src/reports/starter_prediction.py:188-197`) and `NRBL` (`:208-217`) are byte-identical — `max_pitches=105` and the same five tiers (1-30/0, 31-45/1, 46-60/2, 61-80/3, 81-105/4). So the precedence change buys **zero difference in any pitch count or rest day** for the affected teams. They already get the correct numbers.

**Why this is the right call now.** A display computation structurally cannot regress which rules get applied; a precedence change to a rest-rule resolution chain can. Same detection logic, materially smaller blast radius, and it delivers the whole of this idea's stated "Why It Matters" (the mislabel), which was never about the numbers.

**What the triage does NOT do — and this is the load-bearing half.** It does **not** retire the precedence change. This idea's original argument was that the distinct-`NRBL`-constant design exists so a future divergence cannot silently corrupt NRBL teams, and that protection is **dead on arrival** while `ngb` always wins. Going display-only leaves that DOA state in place *permanently*.

**The contingency is not a hedge added by this triage — it is the codebase's stated design intent, and it is a recurring convention rather than a one-off.** `.claude/rules/pitch-rules.md` records the identical rationale for **two different pairs**:

- **`:134`** — `NRBL` is distinct from `LEGION` *on purpose*, "even though the two curves are identical today: NRBL and American Legion are separately governed bodies that merely agree right now, so a future Legion-only change must not silently move NRBL, nor an NRBL-only change move Legion."
- **`:180`** — `PITCH_SMART_15_18` is likewise "a *distinct* constant from Legion on purpose, even though the tiers match today, so a future Legion-only change cannot silently move the estimate."

So the file already states the principle this triage applies: **same numbers today, keep them separately addressable.** That is precisely "display-only now, precedence contingent on divergence." A reader should treat the contingent half as the design's own requirement, not as PM caution layered on top.

So:

- **Build now:** the display overlay. baseball-coach's detection ladder below is preserved **intact and unmodified** — what changes is only where its output is consumed (a label, not a table selection).
- **Contingent on divergence:** the precedence refinement in the ruling below activates **as written** the moment `LEGION` and `NRBL` stop being identical. Do not delete it.
- **The mechanism the contingency depends on — build this WITH the overlay, not later.** "Activates if they diverge" is **not self-executing**, and nothing today would tell anyone the divergence happened: nobody monitors nrbl.net against ALB, and the display-only build removes the last incentive to. If the curves diverge unnoticed, the affected teams silently take the wrong table with nothing in the suite to catch it — the exact failure this idea was filed for, and the risk `pitch-rules.md:134` names in its own words. **A test asserting `LEGION == NRBL` — a few lines — fails loudly on divergence and converts an unmonitored external dependency into a build-time signal. Treat it as part of the story, not an optional extra:** without it the contingency has no trigger and this idea quietly becomes unreachable a second time.

**Boundary note.** This is a scoping/risk call (PM), not a re-ruling of rest safety (baseball-coach). The operator's "just classify NRBL as legion for the case of pitching rules" makes the resolution-layer half unnecessary *while the tables are provably identical*; it should **not** be read as retiring the distinct constant, which `pitch-rules.md:134` keeps for exactly this reason.

**Scope discipline to preserve (ux-designer held this deliberately).** Do **not** extend the two-field `rules_label`/`level_label` split to [[IDEA-177]]'s HS Freshman/Reserve case in the same pass. Different mechanism: GameChanger's `age_group` enum genuinely has no Reserve value, so there is **no discarded structured signal to recover** there — only a name signal, and recovering it would mean overriding a higher-precedence `age_group` read with a lower-precedence name keyword, a real precedence question **E-274 TN-2/TN-4 already settled the other way** (`age_group` wins, no Reserve carve-out, on 0-of-17 observed disagreement). The pattern fits; the ruling does not. Bundling them would blur two separate decisions — the same warning this idea's own notes give about not folding into E-274.

**Sizing — UNRECONCILED (2026-07-25 audit): cite the mechanism, not a count.** The "40 of 752" figure did not survive independent verification: no saved script or output reproduces it, and an audit full-corpus recompute produced different figures (54 nrbl-resolvers, 26+6 rung split) under a possibly-different predicate/scoping. What IS verified, by 5,049-combination brute force: zero inputs tagged `american_legion` reach `nrbl` — the mechanism is exact. The affected-team count must be re-measured (with the predicate written down) in whatever story fixes or displays this; until then cite "dozens of the 752-team probe corpus, count unverified."

## RULING (baseball-coach, 2026-07-25) — refine `american_legion`, and ONLY `american_legion`

> **Status after the 2026-07-25 PM triage above: the DETECTION ladder below is preserved and is what gets built (as a display input). The PRECEDENCE half is CONTINGENT — it activates as written if `LEGION` and `NRBL` ever diverge. Nothing in this ruling is retracted.**


**Refine; do not leave fully dispositive.** TN-2's protective purpose is "do not apply the wrong rule SYSTEM," and that is real and **must stay intact for `usssa` / `perfect_game`** — those genuinely are different systems (innings/outs) and remain **fully dispositive, no refinement**. Legion and NRBL are not different systems today, so `american_legion` winning outright over a strong NRBL signal produces a **mislabel, not a wrong number** — which is exactly why it went unnoticed. The distinct-`NRBL`-constant design exists so a future divergence cannot silently corrupt NRBL teams, and that protection is **dead on arrival** while `ngb` always wins first.

**Refinement precedence** (extends the existing bracket-over-name-word pattern rather than inventing one):
1. Parseable **15U–16U bracket → refine to `nrbl`**. 17U+ confirms `legion`, no change. *(Fixes `Example Clinic Reserve`, the 16U-bracket team.)*
2. **No parseable bracket** (including the free-text range form, which is not a `\d+U` bracket at all) → a **summer sub-varsity name word** (Reserve/Reserves/JV/Junior Varsity/Freshman/Frosh/Sophomore) refines to `nrbl`. *(Fixes `Example Athletics Reserve`, the range-form team — the piece a bracket-only fix would miss.)*
3. Neither present → `american_legion` stays dispositive at `legion` (safe default absent contrary evidence).

**Range form — override IDEA-126's default, but narrowly.** IDEA-126's youth-estimate treatment stays the default for a bare range-form team with no other signal; that reasoning about genuine age uncertainty still holds generally. But when `ngb=american_legion` **AND** a summer sub-varsity name word are **both** present, the name is more specific evidence about *this* team than the org's generic range text, and overrides the range-form default to resolve **binding `nrbl`**. **WARN-log that override** — it is an inference stacked on two signals, not a direct parse.

**Stakes correction attached to the ruling (applies to this whole gate).** This governs **opponent-scouting predictions**, not LSB athlete safety or NSAA/ALB compliance — LSB's own compliance routes through the separate `teams.classification` DB field, which has a genuine `reserve` value and is untouched by this ambiguity. A wrong tier here yields a **worse prediction**, not an overworked athlete. Real, but scouting-accuracy risk, several notches below athlete-safety risk. **Do not over-weight this against an actual compliance gate** — and equally, do not let the correction be used to argue the defect is not worth fixing, since baseball-coach issued it *alongside* the ruling to fix it.

baseball-coach has recorded both this and the E-274 veto reversal in its own memory (`league-pitch-rules.md` — a correction note under the Season × Level model plus a cross-reference patch at the older "`ngb` still wins outright" restatement in Implementation Status, so a future read cannot miss it).

## Summary
NRBL follows American Legion regulations, so coaches tag NRBL teams `ngb = ["american_legion"]` in GameChanger. That is **accurate about the governing body, not a data-entry error.** E-272 made a recognized `ngb` authoritative at Priority 2, above bracket, name, and season — so `american_legion` wins and `nrbl` is never reached.

Observed on real teams the operator identified by tier:

| team | season | `age_group` | `ngb` | resolves | should be |
|---|---|---|---|---|---|
| Example Clinic Reserve | summer | `16U` | `["american_legion"]` | **legion** | nrbl |
| Example Athletics Reserve | summer | `Between 13 - 18` | `["american_legion"]` | **legion** | nrbl |
| Springfield Reserve Eagles | spring | `high_freshman` | `[]` | nsaa_subvarsity | correct |

*Team names above are fictional sentinels (per the redaction scheme in `epics/E-274-age-group-level-signal/epic.md` → Background & Context); the same sentinel always means the same real team. Unlike E-274's measurements these three were **operator-labelled ground truth**, not probe output, so the real identities are **not** recoverable from any file in the repo — re-verifying needs the operator to re-supply them. Every input the classifier reads (`season`, `age_group`, `ngb`) is preserved verbatim, and the only name property the ruling turns on — a summer sub-varsity word — survives as the `Reserve` token.*

**Mechanism verified in code** (`src/reports/starter_prediction.py:445-463`): the Priority-2 block returns `"legion"` on `_NGB_MAP["american_legion"]` and returns *immediately*. The bracket ladder at `:476` sits in the ngb-EMPTY region below it and never runs.

## Why It Matters
**The precedence defeats E-272's own bracket floor.** Example Clinic Reserve carries `age_group=16U`, and TN-2's ladder maps 15U–16U → `nrbl`. That rule is correct and would have produced the right answer. E-272 built a bracket floor specifically for these teams and then placed a rule above it that overrides it.

**TN-2's justification for ngb-wins does not transfer to `american_legion`.** It reasoned that a genuine `ngb=usssa` team is a different rule **SYSTEM**, and overriding it into `nrbl` would apply the wrong system. Sound for USSSA and Perfect Game, whose rules are innings- and outs-based. **Legion and NRBL are the same system** — byte-identical curves. The premise that made the precedence safe is precisely the premise that fails here.

## Severity: real, not urgent — and the reason it is benign is load-bearing
**No coach is getting a wrong rest number today.** `LEGION` and `NRBL` are byte-identical (105 max, same tiers), which is exactly why nothing looked broken and why E-272's closure smoke passed.

1. **The NRBL feature is inert for these teams** — a shipped constant, league id, `get_rules_for_league` arm and test suite that the affected population never reaches.
2. **It becomes a live wrong-table bug the moment the two curves diverge** — the exact scenario the distinct-constant design was built for. The distinctness protects against a divergence the classifier can never act on.
3. baseball-coach's "within-summer Legion-vs-NRBL mis-assignment is safe because the curves are identical" reasoning held — but **nobody realised it was the only thing keeping this benign.**

## Two corrections to how this was first reported
**1. "NRBL never fires" is not measured.** n=2 observed, and the mechanism explains both. The precise claim: *any NRBL team whose coach tags the governing body accurately resolves `legion` instead of `nrbl`.* Whether that is all NRBL teams is unmeasured — api-scout could size it by checking `ngb` across summer Reserve-named opponents. Stating it as "never fires" is the same population-overreach that produced three other errors in the same session.

**2. Fixing the ngb precedence alone would NOT fix `Example Athletics Reserve`.** Its `age_group` is the free-text range `Between 13 - 18`, and the ngb-empty path checks the range form at `:477` **before** the team name, returning `youth_travel` — a labeled *estimate*, not binding NRBL. So team 1 (bracket `16U`) would resolve `nrbl` after an ngb fix; team 2 needs the summer + "Reserve" level-word path, which the range form short-circuits. **A fix scoped only to ngb precedence would look successful on one team and silently miss the other** — and the miss lands on the estimate path, which is quieter than a wrong table.

## Sizing — count UNRECONCILED (relayed "40 of 752" failed independent verification 2026-07-25)

**Do not cite 40 of 752 as settled.** The figure was relayed and never PM-verified, and the 2026-07-25 independent audit could not reproduce it: no saved script computes it, and a full-corpus recompute got different numbers (54 teams resolving `nrbl`, all blank-`ngb`; rung split 26+6) under a possibly-different predicate. The MECHANISM is verified exactly — an exhaustive 5,049-combination sweep of `ngb=american_legion` inputs reached `nrbl` zero times (`legion` 5,049 times), so a counterexample is structurally impossible: `ngb` returns at Priority 2 before the bracket ladder is reachable. Re-measure the affected-team count with an explicit, saved predicate as part of the fixing/display story.

**An earlier figure of 14 is the same defect measured on a quarter of the data** — 198 teams (the 156-name resolution plus a 51-team profile sweep) — and split 7 via the 15U–16U bracket rung, 7 via the summer sub-varsity name rung. **It is not a competing measurement and there is no conflict to re-derive.** Recorded here only so a future reader who meets "14" in an older artifact can identify it rather than re-litigate it. Cite **40 of 752**, always with its denominator.

Two things NOT re-measured at 752, so do not scale them:
- **The per-rung split.** 7+7 was the 198-team breakdown. The 40 was reported as a total; how it divides between the bracket rung and the name rung is unknown. The 198 split is still the only evidence that the name rung carries a large share — which is the independent reason a bracket-only fix is insufficient (correction 2 below argues the same from mechanism, so the conclusion does not depend on the split).
- **"9 teams correctly reach `nrbl`, all with blank `ngb`; zero tagged `american_legion` ever reach it."** That was measured on the 198 and has not been re-run at 752.

That last line is still the sharpest statement of this defect: **the feature is inert wherever the tagging is accurate, and the population reaching `nrbl` correctly is doing so by accident of a missing tag rather than by design.** The 40-of-752 measurement does not disturb that mechanism — it only sizes the affected side.

## Rough Timing
Promote when baseball-coach rules the design question below. This is not blocked on engineering — the fix is small either way; it is blocked on a rest-safety decision nobody has made.

Do **not** fold into E-274. That epic reads `age_group` for **school-family** teams; this is a precedence defect on the **summer** path. They touch the same function and the same ladder, which is exactly why bundling them would blur two separate decisions.

## Dependencies & Blockers
- [ ] **baseball-coach ruling required** (below). Adjacent to the E-274 OQ-2 Reserve-veto ruling coach already owes, and worth deciding together since both concern when a structured signal should be overridden.

## Open Questions
- **The design question, and it belongs to coach:** should `american_legion` remain dispositive, or should a summer sub-varsity signal — a 15U–16U bracket, or a "Reserve" name word — **refine** it to `nrbl`? Refining means a recognized governing body no longer wins outright, which is a real weakening of TN-2's precedence and needs to be decided deliberately rather than patched.
- If refinement is chosen, does it apply **only** to `american_legion` (same rule system as NRBL) and explicitly **not** to `usssa`/`perfect_game` (genuinely different systems)? That carve-out is what preserves TN-2's original, sound justification.
- What should the range-form team resolve to? `youth_travel` (today, an estimate) or binding `nrbl`? Note the range form spans 13–18 and dips below the 15-18 curve, which is why IDEA-126 put it on the estimate in the first place — that reasoning may still hold even for a team we believe is NRBL.
- Is there an observability gap worth closing regardless? A recognized `ngb` that overrides a *mapped* bracket currently logs nothing — `_log_bracket_season_disagreement` only fires in the ngb-empty region.
- How many summer Reserve-named opponents carry `ngb=american_legion`? Sizes the population; api-scout can answer.

## Notes
Found by pointing the classifier at real teams the operator had labelled by tier — not by review, not by tests, not by the closure smoke. **E-272 shipped, passed both closure gates and a live runtime smoke, and the feature at its centre does not fire for the teams it was built for.** Nothing in the suite could have caught it: the smoke asserts the pipeline runs and the scoreboard reconciles, neither of which notices that a classification branch is unreachable.

That is the durable lesson and it is bigger than this defect: **a green suite and a passing smoke cannot detect an unreachable branch.** Only ground truth — teams whose correct answer a human already knew — could.

Related: E-272 TN-2 (the precedence this defeats), [[IDEA-168]] and [[IDEA-172]] (same function, same ladder, also parked), [[IDEA-171]] (promoted to E-274 — deliberately kept separate from this).

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
