# E-243-05: Correct the baseball-coach probable-starter model doc

## Epic
[E-243: Make the Probable-Starter Analysis Useful on Game Morning](epic.md)

## Status
`DONE`

## Description
After this story, the baseball-coach domain memory for the probable-starter model records the corrected output shape (a ranked top-2/3 list of likely arms) and the corrected rest-discount mechanism (a HARD tiebreaker), replacing the prior "always name ONE starter at top" guidance that the backtest showed is 85% wrong when the engine does name one.

## Context
`.claude/agent-memory/baseball-coach/probable-starter-model.md` currently prescribes "One name at top, always. Never open with 'this is unclear.'" and a "Report Output Shape" with a single PROBABLE STARTER at top. The backtest validated against 17 real opponent seasons showed (a) naming a single starter is 85% wrong on the rare occasions the engine does it, and the honest output is a ranked top-2/3; and (b) the rest discount must be a HARD tiebreaker (demote discounted below available), not the soft "downweight" the doc currently describes — soft penalties did nothing in the backtest. baseball-coach maintains its own memory file, so this is a coach story (per the team-lead's direction and the agent-own-memory convention), not a claude-architect story.

## Acceptance Criteria
- [ ] **AC-1**: The "Report Output Shape" section is **fully replaced** — both the design rule ("One name at top, always") AND the sample output block (which shows a single "PROBABLE STARTER" at top with a "Confidence: HIGH" line — the one-name output shape) — with a ranked top-2/3 "most likely arms" output as the correct shape. The "85% wrong when it names one" finding is recorded as the reason. (Note: the sample block uses "NSAA rest rule", not "Pitch Smart" — the Pitch-Smart wording fix is in AC-5's Bad-Example section, a different part of the doc.)
- [ ] **AC-2**: The doc records the preferred-rest discount as a HARD tiebreaker (fully-available starters rank above still-tired/discounted ones), and notes that soft/graduated penalties were validated as ineffective.
- [ ] **AC-3**: The doc notes the backtest evidence basis (17 opponent seasons / 357 games; engine top-1 ~20% / top-2 ~40%; "committee" is structurally true at this level due to pitch-count caps) so future readers understand why the output is ranked rather than single-named.
- [ ] **AC-4**: The preferred-rest thresholds (≤30 → 2 days, 31-60 → 4, 61+ → 5) and the two-tier availability model remain consistent with what E-243-01 implemented; any now-incorrect cross-references are corrected.
- [ ] **AC-5**: In the "Two Bad-Example Root Cause" section, "Pitch Smart eligibility gate" is corrected to "applicable league/level/phase rest gate" (the gate is league/level/phase-keyed, not Pitch-Smart-specific — consistent with `league-pitch-rules.md`).
- [ ] **AC-6**: The doc's null-pitch-count IP-proxy (L87) is **kept as-is** (it is correct per the baseball-coach M1 ruling), and confirmed to MATCH what E-243-01 implements (≤2 IP → 0-30, 3-4 IP → 31-60, 5+ IP → 61+; proxied bucket → preferred-rest → DISCOUNTED if non-zero). The reconciliation is a confirmation of agreement, not a divergence fix. Record the coach reasoning: null→available would invert the conservative-when-uncertain principle, and the null path goes live exactly for youth/travel where pitch tracking is least reliable.
- [ ] **AC-7**: The doc's frontmatter `description` and any `[[links]]` remain valid; no other agent-memory file is contradicted (e.g., `league-pitch-rules.md` stays consistent).

## Technical Approach
Edit `.claude/agent-memory/baseball-coach/probable-starter-model.md` to reflect the validated model: ranked top-2/3 output and the HARD discount tiebreaker. baseball-coach owns the domain framing and wording. Cross-check `league-pitch-rules.md` for consistency. This is a memory/doc edit only — no code.

## Dependencies
- **Blocked by**: E-243-01 (so the doc records the IP-proxy/threshold contract as actually implemented — AC-4/AC-6 verify the doc matches E-243-01's as-built behavior)
- **Blocks**: None

## Files to Create or Modify
- `.claude/agent-memory/baseball-coach/probable-starter-model.md`

## Agent Hint
baseball-coach

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing tests (N/A — doc-only)
- [ ] Cross-references to other baseball-coach memory files remain valid

## Notes
**Routing (codified — resolves CR-F4 / Codex routing findings):** Routing per `.claude/rules/agent-routing.md` Routing Precedence own-memory exception — baseball-coach edits its OWN `.claude/agent-memory/baseball-coach/` directory (its domain content), so the edit stays with baseball-coach and does not route to claude-architect. The own-memory exception was generalized from PM-only to all agents in `agent-routing.md` on 2026-06-28 (claude-architect, with user authorization), resolving this recurring routing finding at the rule level — it is now a codified rule, not ad-hoc prose. `Agent Hint` = `baseball-coach`.

**M1 (RESOLVED — null pitch count).** baseball-coach ruled to keep the IP proxy (L87 stays correct); E-243-01 AC-4 was changed to apply the IP proxy on null. AC-6 is now a confirmation that doc and code agree — do NOT drop L87.
