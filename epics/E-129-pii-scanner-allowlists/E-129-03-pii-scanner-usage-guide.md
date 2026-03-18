<!-- synthetic-test-data -->
# E-129-03: Update Safe Data Handling Guide

## Epic
[E-129: PII Scanner Allowlists](epic.md)

## Status
`TODO`

## Description
After this story is complete, `docs/safe-data-handling.md` will be updated to document the new allowlist mechanisms (RFC 2606 domain allowlist, inline `# pii-ok` suppression, expanded path exclusions) and include a "Safe Fake Data Standards" section with recommended patterns for tests and documentation.

## Context
`docs/safe-data-handling.md` already comprehensively documents the PII scanner — detection patterns, the `synthetic-test-data` marker, how to fix violations, and when `--no-verify` bypass is appropriate. This story adds the new allowlist mechanisms introduced by E-129-01 and E-129-02 to the existing guide rather than creating a separate document. The git pre-commit hook at `.githooks/pre-commit` already references this file in its error output.

## Acceptance Criteria
- [ ] **AC-1**: `docs/safe-data-handling.md` includes a new section documenting the RFC 2606 domain allowlist — which domains are automatically allowed and why (per TN-1)
- [ ] **AC-2**: `docs/safe-data-handling.md` includes a new section documenting the `# pii-ok` inline suppression marker — syntax, when to use it, and examples in both Python (`# pii-ok`) and HTML (`<!-- pii-ok -->`) per TN-3
- [ ] **AC-3**: The "Fixing a Violation" section is updated to include `# pii-ok` as an option alongside moving to `/ephemeral/`, removing data, and adding the synthetic marker
- [ ] **AC-4**: A "Safe Fake Data Standards" section lists recommended patterns: RFC 2606 domains for emails (`user@example.com`), `555-0100` through `555-0199` for US phone numbers (fictional number range), `Bearer FAKE_TOKEN_FOR_DOCS` for bearer tokens
- [ ] **AC-5**: The expanded `SKIP_PATHS` (adding `epics/`, `.project/`) is mentioned in the "What Gets Scanned" section or a related section so readers know planning artifacts are excluded

## Technical Approach
Update the existing `docs/safe-data-handling.md` file. Read the current content, the scanner code, and the epic's Technical Notes to document the new mechanisms. Preserve the existing structure and tone. Add new sections in logical positions within the existing document flow.

## Dependencies
- **Blocked by**: None (can be written in parallel with 01/02; document the intended behavior from Technical Notes rather than requiring code to be merged first)
- **Blocks**: None

## Files to Create or Modify
- `docs/safe-data-handling.md` -- update existing file

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Documentation is clear and complete
- [ ] No regressions in existing docs
