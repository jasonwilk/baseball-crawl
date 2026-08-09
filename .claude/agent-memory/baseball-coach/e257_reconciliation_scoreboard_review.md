---
name: e257-reconciliation-scoreboard-review
description: E-257 planning consultation (2026-07-08) -- headline-metric weighting, abandoned-PA residual exemption, and report-time plausibility gate ranges for the plays-vs-boxscore reconciliation scoreboard
metadata:
  type: project
---

E-257 productizes the plays-to-boxscore reconciliation scoreboard (CLAUDE.md's byte-identical
play-ingestion north star). PM/main session asked me to resolve three open items from the
E-245 baseline (`.project/research/E-245-plays-boxscore-reconciliation-baseline.md`).

**Dated correction, 2026-07-26.** The scoreboard's one-way ratchet GATE was retired by
operator decision; `bb report reconcile-scoreboard` is now a pure diagnostic that an operator
reads before and after an ingestion change. Where this file below describes when "the gate
fires" against an accepted abs-Δ floor, read that as history -- no gate fires now. **This
applies ONLY to the gate mechanics.** Everything else here still stands, in particular the
display position in section 2: the residual is always SHOWN and LABELLED, never silently
excluded. `self_games == 0` also still holds as a hard invariant.

## 1. Headline-metric weighting: BF/FPS vs. equal-weighted AB/H/BB/SO

**Recommendation: equal-weight AB/H/BB/SO as the headline outcome-fidelity bucket. Do NOT
make BF or FPS the headline stat.**

Reasoning from what a coach actually reads:
- AB/H/BB/SO are the direct inputs to the stats I already rank highest ([[coaching-decisions]]
  and MEMORY.md Stat Priorities: OBP, K%, BB%, SLG on the batting side; K/9, BB/9, K/BB on the
  pitching side). These are read every game, every report.
- BF is mostly a denominator/workload number. It matters for ERA/FIP context and safety
  compliance (pitch counts, not BF itself, drive innings-limit flags), but it is not something
  a coach reads as a standalone decision stat the way K% or BB% is.
- FPS is a real coaching stat (command indicator) but it lives on a DIFFERENT axis than the
  outcome-derived scoreboard -- the baseline already separates it out as its own "PITCH-LEVEL
  (separate axis; not outcome-derived)" measure, covered by axis-counter #1 (dropped-pitch-events).
  That is the correct home for it. Blending FPS into a single weighted per-stat score would dilute
  a catastrophic, team-concentrated failure mode (18x-off FPS) into an average that could look fine
  while one team's report is unusable. Keep it a dedicated tripwire, not a blended average.
- The data itself supports this: pitching BF fidelity (98.4% exact, 120 abs-Δ) is worse than SO/BB
  (99.9%/98.9%) mostly because BF is the denominator that absorbs perspective-misalignment noise
  most acutely -- a coverage/join artifact, not something a coach would notice as wrong. Weighting
  the headline metric toward BF would make the scoreboard look worse for reasons unrelated to
  report trustworthiness.
- HBP: track it, but don't weight it equally with AB/H/BB/SO -- smallest sample, least
  decision-driving of the outcome stats.

**Net: track BF/HBP as secondary/context stats (report them, don't gate on them alone); keep
FPS/pitch-level entirely on its existing axis-1 counter; equal-weight AB/H/BB/SO (both batting
and pitching sides) as what drives the regression gate.**

## 2. Abandoned-PA residual (cause 5): exempt from the gate?

**Yes -- exempt from the pass/fail regression gate, but never hide the number.**

This is the same "quick-scored games, abandoned at-bats, scorekeeper noise" residual CLAUDE.md's
Operating Principle already names as the exempted floor ("a perfect zero is not the bar"). A ±1
AB/H discrepancy on a single quick-scored game is invisible to a coach reading a season OBP
(.347 vs .346 changes nothing about a lineup decision) -- it is genuinely below the threshold
that matters for coaching action.

**How to exempt without suppressing** (this is my standing display-philosophy position, see
`.claude/rules/display-philosophy.md` and MEMORY.md "Never suppress, always contextualize"):
- Establish the CURRENT baseline abs-Δ for each stat as the accepted floor (the numbers already
  in the E-245 baseline table, e.g. AB abs-Δ 34/12,555 units, HBP abs-Δ 64-65/whatever units).
- The gate fires only if a change pushes abs-Δ ABOVE that established floor -- holding steady at
  the residual is a pass, not a violation.
- The scoreboard DISPLAY must always show the residual number and label it, e.g. "AB abs-Δ: 34
  units (known residual, ~0.3% of units -- quick-scored/abandoned-PA noise)" rather than excluding
  it from the report silently. Same discipline I apply to small-sample stats on the bench card:
  show it with context, never hide it.

## 3. Report-time plausibility gate ranges (FPS 40-75%, P/PA 3.0-4.5)

**P/PA 3.0-4.5: sensible as-is, no change recommended.** Matches expected HS/Legion range
(roughly tracks pro-ball P/PA norms of ~3.8-4.0, with room either side for more aggressive or
less disciplined HS at-bats). Good plausibility band for a "catch the impossible value" gate.

**FPS 40-75%: recommend widening the floor to 30% (i.e., 30-75%), not 40%.** A genuinely wild
HS/Legion pitcher can have a real, full-season FPS in the low-to-mid 30s -- that is a true
performance signal a coach needs to see (e.g., "this kid can't find the zone"), not noise to
flag as implausible. A 40% floor risks false-flagging a real struggling pitcher as a parser
error. The ceiling of 75% is fine -- very hard to sustain higher even for elite-control arms
over a full season. This is consistent with my "never suppress" doctrine: even a legitimately
bad FPS (e.g., 32%) is useful coaching information ("this kid got shelled" is the pitching
equivalent), not noise to gate away.

**Framing for both ranges: these are plausibility flags for operator review, not silent
discard/clamp gates.** The original catastrophic failure (FPS 3.4% instead of ~60%) was caught
by a human eyeballing the number -- the gate should reproduce that catch mechanically
("FPS came back at 3.4%, outside expected 30-75% range -- likely a parsing error, review before
sharing") and surface it to the operator, not silently suppress or auto-correct the value. The
system observes and flags; the human (here, the operator, not the coach) decides. Same
bubble-up-not-push posture I use for performance flags on the coaching side, applied to data
trust on the operator side.

## Related

- [[coaching-decisions]] -- stat priorities and rate-stat rationale this weighting call is built on
- Baseline doc: `.project/research/E-245-plays-boxscore-reconciliation-baseline.md`
- Epic stub: `.project/archive/E-257-reconciliation-scoreboard/epic.md`
