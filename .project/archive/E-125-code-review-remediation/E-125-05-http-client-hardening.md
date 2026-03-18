# E-125-05: HTTP Client Hardening (Rate Limit Crash, Pagination Validation, XSS)

## Epic
[E-125: Full-Project Code Review Remediation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the HTTP client layer will handle non-integer `Retry-After` headers without crashing, pagination will only follow URLs on the same host as the base URL, and the WebAuthn `|safe` filter will be replaced with a safe JSON embedding pattern. These are three independent but small fixes grouped into one story because each is a single-line to few-line change.

## Context
**Rate limit crash** (Review 01 I-7): `int(response.headers.get("Retry-After", "60"))` will crash with `ValueError` if the server sends an HTTP-date string (valid per RFC 7231). This appears in three locations in `client.py` (lines ~296, ~434, ~533). Additionally, the code sleeps for the retry-after duration and then raises an exception (the caller must catch and retry -- the sleep is wasted). The sleep-then-raise design is a secondary concern; the `int()` crash is the bug.

**Pagination URL validation** (Review 01 I-2): `get_paginated` follows `x-next-page` URLs without validating the host. A malicious server response could redirect auth tokens to an attacker-controlled host. Per Technical Notes TN-6.

**XSS via |safe** (Review 03 #2): `passkey_register.html` uses `{{ options_json | safe }}` which disables Jinja2 autoescaping. If `user_display_name` (sourced from user email) contains `</script>`, it would break out of the script tag. Per Technical Notes TN-7.

## Acceptance Criteria
- [ ] **AC-1**: `Retry-After` header parsing handles non-integer values gracefully (try/except with a sensible default, not a crash)
- [ ] **AC-2**: All three `Retry-After` parsing locations in `client.py` are fixed consistently
- [ ] **AC-3**: `get_paginated` validates that the `x-next-page` URL's host matches `self._base_url`'s host before following; logs a warning and stops pagination if the host differs
- [ ] **AC-4**: The `|safe` filter in `passkey_register.html` is replaced with a Jinja2-safe JSON embedding pattern that does not disable autoescaping
- [ ] **AC-5**: Tests verify that a non-integer `Retry-After` value does not crash the client
- [ ] **AC-6**: Tests verify that a pagination URL with a different host is rejected
- [ ] **AC-7**: All existing tests pass

## Technical Approach
**Rate limit**: Wrap the `int()` call in a try/except that falls back to a sensible default (e.g., 60 seconds). The sleep-then-raise pattern is a design issue but not a crash -- fixing the `int()` crash is the priority. If the implementing agent wants to also address the sleep-then-raise, that's acceptable but not required.

**Pagination**: Parse the `x-next-page` URL and compare its hostname to `self._base_url`'s hostname. Reject if different.

**XSS**: Replace `{{ options_json | safe }}` with `{{ options_json | tojson }}` (Jinja2 built-in, produces JSON-safe output with proper escaping) or use a `<script type="application/json">` tag with auto-escaped content that JS parses.

## Dependencies
- **Blocked by**: E-125-01 (CSRF changes affect `tests/test_auth_routes.py` fixtures -- see TN-8)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/client.py` (Retry-After parsing x3, pagination URL validation)
- `src/api/templates/auth/passkey_register.html` (replace |safe filter)
- `tests/test_client.py` (Retry-After and pagination tests)
- `tests/test_auth_routes.py` (passkey template test if applicable)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `Retry-After` header can legally be either an integer (seconds) or an HTTP-date string per RFC 7231 section 7.1.3. The HTTP-date format is e.g., `Fri, 31 Dec 1999 23:59:59 GMT`. Parsing it fully is overkill -- a try/except with a default is sufficient.
- The pagination URL validation is defense-in-depth for an undocumented API. Low probability of exploit but trivial to fix.
