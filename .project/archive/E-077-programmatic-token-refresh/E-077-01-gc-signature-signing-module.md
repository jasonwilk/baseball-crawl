# E-077-01: gc-signature Signing Module

## Epic
[E-077: Programmatic Token Refresh -- Fix Broken GameChangerClient](epic.md)

## Status
`DONE`

## Description
After this story is complete, the project will have a reusable Python module at `src/gamechanger/signing.py` that implements the gc-signature HMAC-SHA256 signing algorithm. This module provides pure functions for recursive body value extraction, HMAC payload signing, and complete gc-signature header generation -- everything needed to sign POST /auth requests programmatically.

## Context
The gc-signature algorithm was reverse-engineered from the web.gc.com JavaScript bundle on 2026-03-07 and confirmed working in manual Python testing. The algorithm is fully documented in `data/raw/gc-signature-algorithm.md` (JS pseudocode with detailed comments). This story creates a production-quality Python module implementing the algorithm. Story 02 (Token Manager) will use it to sign refresh requests.

## Acceptance Criteria
- [ ] **AC-1**: `src/gamechanger/signing.py` exists and exports three public functions: one for recursive body value extraction (equivalent to the JS `valuesForSigner`), one for HMAC payload signing, and one for assembling complete gc-signature headers (returns a dict with `gc-signature`, `gc-timestamp`, `gc-client-id` keys).
- [ ] **AC-2**: Body value extraction handles all JSON-equivalent cases: strings return as-is, numbers return as string representation, objects (dicts) have keys sorted alphabetically with values recursively extracted, arrays (lists) are flatmapped, None returns `["null"]`. Note: the JS algorithm has a branch for `undefined` that returns empty list -- this has no Python equivalent (Python JSON parsing never produces `undefined`; missing dict keys simply do not exist) and should be omitted from the Python implementation. Verified by unit tests covering each case.
- [ ] **AC-3**: HMAC signing correctly concatenates timestamp, nonce (as raw bytes), body values (pipe-delimited), and optional previous signature (as raw bytes) with pipe delimiters, then produces HMAC-SHA256 using the Base64-decoded client key. Verified by at least one test with a known input/output pair.
- [ ] **AC-4**: The header assembly function generates a random 32-byte nonce (Base64-encoded), produces the gc-signature in `{nonce}.{hmac}` format, and includes gc-timestamp as a string of Unix epoch seconds.
- [ ] **AC-5**: No credentials (client keys, tokens, signatures) are logged at any log level. The module uses `logging.getLogger(__name__)` but only logs non-sensitive operational information (e.g., "generating signature for POST /auth").
- [ ] **AC-6**: All new functions have type hints and docstrings.
- [ ] **AC-7**: `tests/test_signing.py` exists with tests covering AC-2 through AC-5. All tests pass. No real HTTP calls.

## Technical Approach
The signing algorithm is fully specified in `/workspaces/baseball-crawl/data/raw/gc-signature-algorithm.md` (JS pseudocode with detailed comments). The Python implementation should faithfully reproduce the JS behavior using standard library modules (`hmac`, `hashlib`, `base64`, `os` or `secrets` for random bytes). The epic Technical Notes section has a concise summary of the algorithm.

Key constraint: the nonce and previous signature must be decoded from Base64 to raw bytes before being fed into the HMAC -- the JS code does `Base64.parse()` on these values, not string concatenation.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-077-02

## Files to Create or Modify
- `src/gamechanger/signing.py` (create)
- `tests/test_signing.py` (create)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-077-02**: `src/gamechanger/signing.py` with the header assembly function that Token Manager will call to sign POST /auth refresh requests.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Reference implementation (JS): `/workspaces/baseball-crawl/data/raw/gc-signature-algorithm.md`
- Auth architecture context: `/workspaces/baseball-crawl/docs/api/auth.md`
