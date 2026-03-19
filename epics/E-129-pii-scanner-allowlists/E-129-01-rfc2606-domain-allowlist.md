<!-- synthetic-test-data -->
# E-129-01: RFC 2606 Domain Allowlist

## Epic
[E-129: PII Scanner Allowlists](epic.md)

## Status
`IN_PROGRESS`

## Description
After this story is complete, the PII scanner's email pattern will skip matches where the domain is an RFC 2606 reserved domain. Emails like `user@example.com`, `test@foo.test`, and `admin@localhost` will no longer trigger findings. Real email addresses (any non-reserved domain) will continue to be caught.

## Context
The email regex (`[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`) matches all email-shaped strings indiscriminately. RFC 2606 reserves specific domains for documentation and testing -- these can never be real email addresses. Filtering them out eliminates the most common class of false positives.

## Acceptance Criteria
- [ ] **AC-1**: Given a file containing `user@example.com`, when the PII scanner runs, then no email finding is reported for that match
- [ ] **AC-2**: Given a file containing `test@subdomain.example.org`, when the PII scanner runs, then no email finding is reported for that match
- [ ] **AC-3**: Given a file containing `admin@foo.test`, when the PII scanner runs, then no email finding is reported for that match (`.test` TLD per TN-1)
- [ ] **AC-4**: Given a file containing `admin@localhost`, when the PII scanner runs, then no email finding is reported for that match
- [ ] **AC-5**: Given a file containing `jason@realdomain.com`, when the PII scanner runs, then an email finding IS reported
- [ ] **AC-6**: The allowlist is defined as a data structure in `pii_patterns.py` (not hardcoded in scanner logic), covering all domains listed in TN-1
- [ ] **AC-7**: Unit tests cover each reserved domain category (second-level, TLD, localhost) and confirm real domains are still caught

## Technical Approach
The reserved domain list lives in `pii_patterns.py` alongside the existing pattern definitions. The filtering logic lives in `pii_scanner.py` where email matches are evaluated -- after regex match, extract the domain and check against the allowlist before reporting. Per TN-1, the allowlist uses suffix matching: a domain is allowed if it equals or ends with a dot followed by any reserved domain entry (e.g., `subdomain.example.org` matches via `.example.org`). TLD entries (`.test`, `.example`, `.invalid`, `.localhost`) match any domain ending in that TLD.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-129-02 (shared files: `pii_scanner.py`, `test_pii_scanner.py`)

## Files to Create or Modify
- `src/safety/pii_patterns.py` -- add RFC 2606 domain allowlist data structure
- `src/safety/pii_scanner.py` -- add post-match filtering for email pattern
- `tests/test_pii_scanner.py` -- add tests for domain allowlist

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
