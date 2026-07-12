# E-256-16: Eliminate the two pre-existing PII pattern hits (12a-ii + proxy false positive)

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

## Description
After this story is complete, the **two pre-existing `api_key_assignment` pattern hits** on the committed tree — the one at `tests/test_credential_parser.py:81` and the false positive at `proxy/addons/credential_extractor.py:42` — no longer fire, so the story-09 whole-tree CI PII step is GREEN. The two are fixed by **different tiers of the §6 choice hierarchy** because the sites differ: the test hit is fixed by **changing the fake value** (tier-1); the proxy hit is a false positive on real functional code whose value cannot change, so it is fixed by a **line-scoped `# pii-ok`** (tier-2). Neither uses a file-level suppressor.

**Scope note (WIDENED 2026-07-09, PM, dispatch):** this story originally targeted only the test hit (item 12a-ii). Story 09's correct whole-tree CI PII scan surfaced a **second** pre-existing hit — `proxy/addons/credential_extractor.py:42`, owned by no story — that keeps the build-failing CI PII step RED and so violates the epic Success Criterion "CI passes on push." Both hits are the same acceptance concern ("make the whole-tree PII scan green the correct way") and both are SE-owned (`.py` files, non-context-layer), so PM homed the proxy hit here rather than spawning a new micro-story (which would have been an epic-scope expansion). AC-5/6/7 below cover it.

## Context
This is flow-review item **12a-ii**. It is SE's story (not CA's) because it edits a test file, and Routing Precedence would otherwise pull the whole of item 12a into claude-architect. The choice of fix is deliberate and follows the choice hierarchy story 13 documents (Technical Notes §6, "change the data" is preferred): `tests/test_credential_parser.py` is the credential-parser test file — the single file in the repo **most likely to receive a real token** when a dev pastes a curl command to reproduce a bug — so a file-level suppressor is the worst possible instrument here. There is also a mechanical hazard: the offending line ends in a `\` continuation, so a trailing `# pii-ok` would corrupt the fixture. Change the value.

## Acceptance Criteria
- [ ] **AC-1**: Given `tests/test_credential_parser.py:81`, when this story is complete, then the `api_key_assignment` scanner hit is eliminated by replacing the fake value with an obviously-fake one that fires no pattern (e.g. a short/`deadbeef`-style device id) and that parses identically, so the test still asserts the same parsing behavior.
- [ ] **AC-2**: Given the fix, when this story is complete, then **no** suppression marker (`# pii-ok` or `synthetic-test-data`) was added to the file — the fix is a value change, not a suppression (per the choice hierarchy in story 13 / Technical Notes §6).
- [ ] **AC-3**: Given the PII pattern scanner run over `tests/`, when this story is complete, then it reports **zero** violations (the one `api_key_assignment` hit is gone).
- [ ] **AC-4**: Given the credential-parser test, when this story is complete, then it still passes and still exercises the same parsing path (the value change is behavior-preserving for the test's assertion).
- [ ] **AC-5** (proxy false positive — homes the second pre-existing hit): Given `proxy/addons/credential_extractor.py:42` (`"gc-device-id": "GAMECHANGER_DEVICE_ID",`), when this story is complete, then the `api_key_assignment` pattern no longer fires on that line. The hit is a **FALSE POSITIVE**: the regex keys on `device[_-]?id` in the `"gc-device-id"` header key and treats the mapped **value** `GAMECHANGER_DEVICE_ID` (a 21-char env-var NAME) as a long secret. It is not a secret — it is the literal name of the env var the header maps to, and it is real functional code that MUST stay verbatim. Per the §6 choice hierarchy tier-1 ("change the data") is therefore **unavailable** here, so the fix is **tier-2: a line-scoped `# pii-ok`** on line 42 with an adjacent comment stating it is a false positive (env-var name, not a credential value). Mechanically safe: the line ends in `,` (a valid Python inline-comment position), unlike the test fixture's `\` continuation that made a marker unsafe there.
- [ ] **AC-6**: Given the proxy fix, when this story is complete, then **no** file-level `synthetic-test-data` marker was added to `credential_extractor.py`. A file-level suppressor is forbidden by §6 on any file that handles, parses, or could receive real credentials — and this is the **credential-extractor** file, the worst possible place for one. The suppression is line-scoped only, and `src/safety/` is NOT touched (that would be the IDEA-112 narrowing, out of scope).
- [ ] **AC-7**: Given the PII pattern scanner run over the whole checked-out tree (`git ls-files -z | xargs -0 python -m src.safety.pii_scanner` — the exact story-09 CI invocation), when this story is complete, then it reports **zero** violations. Both pre-existing hits (`test_credential_parser.py:81` and `credential_extractor.py:42`) are resolved, so the story-09 CI PII step is GREEN and the epic Success Criterion "CI passes on push" holds for the PII gate.

## Technical Approach
Prefer a device-id-shaped value under the 16-char threshold, or an obviously-synthetic token that the `api_key_assignment` regex does not match (its value side requires `[=:]` + a 16+ non-space value). Confirm the parser treats the new value identically to the old for the test's assertion. Do NOT add a marker; do NOT touch `src/safety/` (that would be the IDEA-112 narrowing, out of scope). Run the pattern scanner over `tests/` to confirm zero hits.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `tests/test_credential_parser.py` (line ~81 — the fake value; tier-1 change-the-value)
- `proxy/addons/credential_extractor.py` (line ~42 — tier-2 line-scoped `# pii-ok` on the false positive; do NOT change the env-var name)

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
