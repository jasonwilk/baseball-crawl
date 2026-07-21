# E-272-03: NRBL + season-axis in the baseball-coach model doc

## Epic
[E-272: Season × Level → League Classification (+ NRBL)](epic.md)

## Status
`TODO`

## Description
After this story is complete, the baseball-coach model doc (`.claude/agent-memory/baseball-coach/league-pitch-rules.md`) carries the Nebraska Reserve Baseball League (NRBL) as a recognized pitch-count league, documents the season × level → league classification model, and reconciles its existing "league SELECTION is inferred, not chosen" framing to the "Both, E-272 first" reality (E-272 improves inference now; the operator-pick layer comes later via E-263).

## Context
The coach model doc is the authoritative source for the per-league rest curves that `.claude/rules/pitch-rules.md` (E-272-04) references rather than duplicates. It currently frames the inference path purely as "the gap" to be replaced by an operator pick — which E-272 partially supersedes by improving inference as the standalone-now fix and the durable unset fallback. This story updates the doc so it is truthful about the shipped behavior. It is baseball-coach's OWN agent-memory directory, so per the agent-routing own-memory carve-out it is owned and edited by baseball-coach, NOT claude-architect. It runs before E-272-04 so the pitch-rules.md reference points at a doc that already carries NRBL.

## Acceptance Criteria
- [ ] **AC-1 (NRBL added)**: The model doc adds NRBL as a recognized pitch-count league: an Authoritative-Tables entry and a Summary-Metadata row, carrying the Legion-identical curve (30/45/60/80/105, 0/1/2/3/4 rest days, 105 daily max) with its source (nrbl.net) and the distinct-constant rationale (rule-identical to Legion today, separately governed, must not silently co-move). NRBL is noted as a SUMMER league.
- [ ] **AC-2 (season-axis model — the general hardened rule)**: The doc documents the season × level → league classification model per Technical Notes TN-2 §4c — "season picks the league family" as a GENERAL rule across ALL NSAA level words (not just Reserve), with the mapped-bracket ladder dispositive and season-independent. This must not contradict the doc's existing "(LEAGUE × COMPETITION LEVEL × SEASON-PHASE)" keying — it refines the classification signals, not the rest curves.
- [ ] **AC-3 (inference-framing reconciled)**: The doc's existing "league/level SELECTION is inferred, not chosen / operator-pick is the fix" narrative is reconciled to reflect that E-272 IMPROVES the inference (season × level mapping + NRBL) as the now-shipping fix, and the operator-pick override is a later layer (E-263) for which improved inference is the unset fallback — per Technical Notes TN-6's SELECTION-vs-MAPPING split. No stale claim that inference is only-a-gap-to-be-removed survives.
- [ ] **AC-4 (numbers stay authoritative and consistent)**: The NSAA Sub-Varsity curve in the doc (1/2/3/4, already correct) remains the authority E-272-01 reconciled the engine against; no rest-curve number is changed except the NRBL addition.
- [ ] **AC-5 (binding-assumption caveat)**: The doc records the documented assumption (per TN-2) that NRBL-binding (`is_estimate=False`) for an empty-`ngb` summer opponent rests on an in-state/Nebraska context — NRBL is Nebraska's dominant reserve-tier summer league — to be revisited if out-of-state summer opponents enter scope. (Note: the stale "LSB Reserve maps to sophomore-level Legion" line coach originally flagged lives in `.claude/agents/baseball-coach.md`, NOT this file — `league-pitch-rules.md` has nothing stale to correct on that point, so its NRBL work is purely additive. The agent-def correction is folded into E-272-04, per Codex-P2-a + coach's file-owner ruling.)

## Technical Approach
Edit `.claude/agent-memory/baseball-coach/league-pitch-rules.md`: add the NRBL table entry + summary-metadata row (mirroring the Legion entry), add or extend a section describing the season × level classification model per TN-2, and reconcile the inference-framing sections (the "Operator-Selected Gate" and "Implementation Status — Tables Present, Selection Is the Gap" sections) to the "Both, E-272 first" reality. Keep the existing rest curves intact; NRBL == the Legion curve. Do not duplicate engine code details — this is the domain reference.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-272-04 (pitch-rules.md references this doc for the NRBL curve rather than duplicating it)

## Files to Create or Modify
- `.claude/agent-memory/baseball-coach/league-pitch-rules.md` (modify)

## Agent Hint
baseball-coach

## Handoff Context
- **Produces for E-272-04**: the authoritative NRBL curve + season-axis model that `.claude/rules/pitch-rules.md` references (not duplicates).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The doc's frontmatter `description` still accurately summarizes its contents (update if NRBL/season-axis changes it)
- [ ] No rest-curve number changed except the NRBL addition
- [ ] Cross-links to related model docs remain valid

## Notes
This is a reference-doc update in the owning agent's memory directory — no code, no tests. It must land before or alongside E-272-04 so the rule doc's NRBL reference resolves.
