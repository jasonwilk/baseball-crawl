# E-256-13: Document the PII suppression mechanisms + choice hierarchy (12a-i)

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

## Description
After this story is complete, `.claude/rules/pii-safety.md` honestly documents the two PII-scanner suppression mechanisms, their true scope (both suppress ALL patterns including credentials, not just shape heuristics), and a **choice hierarchy** telling authors which instrument to reach for. It also records that the `tests/**` shape-exemption was rejected on evidence and that a real credential behind either marker is a MUST FIX.

## Context
This is flow-review item **12a-i**, and it is **zero code**. CA read `pii_scanner.py:143-155` and confirmed both suppressors sit OUTSIDE the `COMPILED_PATTERNS` loop, so per-line `# pii-ok` suppresses every pattern on its line (including `bearer_token`/`api_key_assignment`) and the file-level `synthetic-test-data` marker suppresses every pattern in the whole file. This is by design and load-bearing (a synthetic auth fixture legitimately contains `Authorization: Bearer test-token-…`), but it means the names mislead: an agent reading "pii-ok" would assume it silences only shape noise. Documenting the true scope + the choice hierarchy is the deliverable. See Technical Notes §6 for the full ruling, including why §4g is a review-time control and not a structural closure (the residual is IDEA-112, out of scope). The companion fixture fix is story 16 (12a-ii).

## Acceptance Criteria
- [ ] **AC-1**: Given `.claude/rules/pii-safety.md`, when this story is complete, then it documents both mechanisms — per-line `# pii-ok` (`pii_scanner.py:151-153`) and file-level `synthetic-test-data`/`SYNTHETIC_MARKER` (`pii_scanner.py:145-148`) — and states plainly that BOTH suppress **all** patterns including credential patterns (`bearer_token`, `api_key_assignment`, `email`, `us_phone`), not only shape heuristics.
- [ ] **AC-2**: Given the choice hierarchy, when this story is complete, then the rule records the preference order: (1) **change the data** so no pattern matches (always preferred; leaves no standing suppression); (2) **line-scoped `# pii-ok`** on the one offending line; (3) **file-level `synthetic-test-data`** only for an end-to-end synthetic fixture and **never on a file that handles, parses, or could receive real credentials**.
- [ ] **AC-3**: Given the rule, when this story is complete, then it states that a **real credential value behind either marker is a MUST FIX** (not a sanctioned suppression), and that the blanket `tests/**` exemption was **rejected on evidence** (shape heuristics fire zero times) and on the visibility-to-review axis (a marker is a reviewable token in the diff; a path exemption is invisible and silently unscans future fixtures for credentials).
- [ ] **AC-4**: Given the whole story, when it is complete, then **zero** code files are modified (no change to `src/safety/pii_scanner.py` or `pii_patterns.py`) — it is a documentation/rule change only.

## Technical Approach
Prose addition to `.claude/rules/pii-safety.md`. claude-architect owns this file. Do not change scanner behavior — the mechanisms already ship (E-254-06); the gap is that the rule under-describes their scope and offers no choice hierarchy. Do NOT overclaim §4g as closing the staged-blob hole (Technical Notes §6) — the reviewability point justifies marker-over-exemption, not a structural guarantee.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/pii-safety.md`

## Agent Hint
claude-architect

## Handoff Context
None.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Zero code files modified (AC-4)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Flow-review item 12 is three deliverables in this epic: **13 (12a-i)** = suppression-scope doc + choice hierarchy; **16 (12a-ii)** = the credential-parser fixture fix; **14 (12b)** = the planning-artifact byte-gate.
