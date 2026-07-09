# E-256-16: Eliminate the credential-parser test PII hit (12a-ii)

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`TODO`

## Description
After this story is complete, the `api_key_assignment` pattern hit at `tests/test_credential_parser.py:81` no longer fires, achieved by **changing the fake value** to one that is obviously fake and parses identically — not by adding a suppression marker.

## Context
This is flow-review item **12a-ii**. It is SE's story (not CA's) because it edits a test file, and Routing Precedence would otherwise pull the whole of item 12a into claude-architect. The choice of fix is deliberate and follows the choice hierarchy story 13 documents (Technical Notes §6, "change the data" is preferred): `tests/test_credential_parser.py` is the credential-parser test file — the single file in the repo **most likely to receive a real token** when a dev pastes a curl command to reproduce a bug — so a file-level suppressor is the worst possible instrument here. There is also a mechanical hazard: the offending line ends in a `\` continuation, so a trailing `# pii-ok` would corrupt the fixture. Change the value.

## Acceptance Criteria
- [ ] **AC-1**: Given `tests/test_credential_parser.py:81`, when this story is complete, then the `api_key_assignment` scanner hit is eliminated by replacing the fake value with an obviously-fake one that fires no pattern (e.g. a short/`deadbeef`-style device id) and that parses identically, so the test still asserts the same parsing behavior.
- [ ] **AC-2**: Given the fix, when this story is complete, then **no** suppression marker (`# pii-ok` or `synthetic-test-data`) was added to the file — the fix is a value change, not a suppression (per the choice hierarchy in story 13 / Technical Notes §6).
- [ ] **AC-3**: Given the PII pattern scanner run over `tests/`, when this story is complete, then it reports **zero** violations (the one `api_key_assignment` hit is gone).
- [ ] **AC-4**: Given the credential-parser test, when this story is complete, then it still passes and still exercises the same parsing path (the value change is behavior-preserving for the test's assertion).

## Technical Approach
Prefer a device-id-shaped value under the 16-char threshold, or an obviously-synthetic token that the `api_key_assignment` regex does not match (its value side requires `[=:]` + a 16+ non-space value). Confirm the parser treats the new value identically to the old for the test's assertion. Do NOT add a marker; do NOT touch `src/safety/` (that would be the IDEA-112 narrowing, out of scope). Run the pattern scanner over `tests/` to confirm zero hits.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `tests/test_credential_parser.py` (line ~81 — the fake value)

## Agent Hint
software-engineer

## Handoff Context
None.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No suppression marker added (AC-2); no `src/safety/` change
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The broader question — should the suppressors be narrowed so they *cannot* silence credential patterns — is IDEA-112 (measurement-first), explicitly out of this epic. This story only removes the one existing hit the correct way.
