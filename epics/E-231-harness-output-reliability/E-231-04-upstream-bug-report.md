# E-231-04: Upstream Harness Bug-Report Artifact

## Epic
[E-231: Harness Output-Reliability -- Detect, Defend, and Report](../E-231-harness-output-reliability/epic.md)

## Status
`TODO`

## Description
After this story is complete, the repository will contain an artifact capturing a clean reproduction of the harness output-reliability failure, framed for filing with Anthropic / Claude Code. Because the transport bug is Anthropic-internal and not fixable from this repo, this report is the honest disposition for the part we cannot fix.

## Context
This epic's other four stories detect and defend against the failure; none of them repairs the channel. The root cause is harness/transport-layer bursty output drop and corruption (see epic Technical Notes). The right disposition for a non-fixable upstream bug is a clear, evidence-backed report. This very planning session reproduced the bug severely across PM, CA, and SE -- intermittent empty Reads, a stale-line-number Read (line counts 19→17→18 while `cat -n` showed clean 1-31 on the same file), and tail truncation, hitting even bare `echo`, recovering on retry, under concurrent multi-agent dispatch. That makes this session the primary evidence.

## Acceptance Criteria
- [ ] **AC-1**: The artifact exists at `.project/research/E-231-harness-repro/` (a file is created there). (Committing happens at epic closure -- not a story-DONE precondition.)
- [ ] **AC-2**: The artifact documents the failure taxonomy: bursty **empty** returns, **garbled** output (wrong line numbers -- include the observed 19→17→18-vs-clean-1-31 example), and **tail truncation**; notes it hits even zero-IO commands (bare `echo`); and notes it recovers on retry.
- [ ] **AC-3**: The artifact records the reproduction context with CONCRETE this-session examples (not hand-waving): concurrent multi-agent dispatch; the stale-line-number Read (19→17→18 vs. clean 1-31); empty returns on known-nonempty files recovering on retry; false-negative Globs ("no files found" while a clean Read of the same path succeeds); and the two truncated-read-composed-into-fabricated-findings relays during this very triage (a truncated review log relayed as a confident finding list -- the exact anti-pattern this epic exists to stop). Names PM/CA/SE as affected.
- [ ] **AC-4**: The artifact is framed as an upstream report for Anthropic / Claude Code (intended audience and purpose stated), not as an internal fix.
- [ ] **AC-5**: The artifact notes the non-fixable-from-here disposition and cross-references the detect-and-defend mitigations planned in sibling stories E-231-01, E-231-02, E-231-03, and E-231-05 (referenced as planned sibling work, not as "shipped" -- the five stories are independent and may run in any order, so E-231-04 must not assume its siblings have already landed).

## Technical Approach
This is a documentation/research artifact, not code. The implementer (claude-architect, per the Agent Hint) captures the failure taxonomy, reproduction context, and this-session evidence in a single artifact at `.project/research/E-231-harness-repro/` framed for upstream filing. The observed details for AC-2 and AC-3 are in this story's Context and the epic Technical Notes. No application code or tests are involved.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.project/research/E-231-harness-repro/` (new artifact directory; filename within it at implementer's discretion)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (N/A -- documentation/research artifact)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Honest disposition for the non-fixable part of the problem. Uses this very session as primary evidence -- the planning of E-231 reproduced the bug severely.
