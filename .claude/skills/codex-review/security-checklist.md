<!-- Single source for the SECURITY CHECKLIST block of the Codex review prompt.
     Read whole-file (no delimiters) by scripts/codex-review.sh and by this skill's
     prompt-generation path. Edit the content freely; keep the file non-empty. -->

### Priority 4: Security Review

Every review MUST evaluate the changed files against this security checklist. Findings are MUST FIX unless explicitly noted otherwise. **Cloudflare, WAF, or network-layer controls are NOT compensating controls for application-layer security defects (CSRF, XSS, SQLi, etc.). Do not downgrade these findings based on infrastructure.**

**Sensitive-path security trigger**: When the diff touches an authentication, credential, session, or PII-handling path, escalate scrutiny beyond the checklist below and specifically evaluate: **replay** (can a captured token, magic link, or request be reused?), **TOCTOU** (is there a check-then-use gap an attacker can wedge between?), **fail-open vs. fail-closed** (when the check errors or a dependency is unavailable, does the code deny by default or silently allow?), and **PII across ALL artifact types** -- not just source and logs, but also test fixtures, cached API responses, generated reports, error messages, and committed docs. These classes have historically been caught only by external review; this trigger makes them a standing review obligation.

#### 4a. Injection (SQLi, Command Injection)

- **SQL injection**: Flag any SQL query constructed via f-string, `.format()`, or string concatenation with external input. Only parameterized queries (`?` placeholders with parameter tuples) are acceptable. This includes dynamic column names, ORDER BY clauses, and table names -- if any part of the SQL string is interpolated from user input, request parameters, or API response data, it is SQLi.
- **Command injection**: Flag any use of `subprocess.call/run/Popen` with `shell=True` when arguments include external input. Flag any `os.system()` usage.

#### 4b. Cross-Site Scripting (XSS)

- **`|safe` filter audit**: Every use of `|safe` in Jinja2 templates MUST be justified. If the value could originate from user input, API responses, or database fields populated from external data, it is XSS. Autoescaping must be enabled (Jinja2 default in FastAPI). Flag any `autoescape=False` configuration.
- **JavaScript context**: Data injected into `<script>` blocks, `onclick` handlers, or `data-*` attributes used in JS requires JSON serialization with `|tojson`, not bare interpolation.
- **Template inheritance**: Verify child templates do not disable autoescaping that parent templates enable.

#### 4c. Cross-Site Request Forgery (CSRF)

- **POST/PUT/DELETE forms**: Every HTML form that performs a state-changing operation MUST include CSRF protection (token in a hidden field, validated server-side). Forms without CSRF tokens are MUST FIX.
- **AJAX state changes**: State-changing fetch/XHR calls must include a CSRF token header or use a same-site cookie defense.
- **GET side effects**: Flag any GET route handler that modifies database state (violates HTTP semantics and bypasses CSRF defenses).

#### 4d. Server-Side Request Forgery (SSRF)

- **URL following**: When code follows URLs from API responses, paginated `next` links, or redirect headers, verify the destination host is validated against an allowlist before sending authentication headers. Sending `gc-token` or other credentials to an unvalidated URL is SSRF.
- **User-supplied URLs**: Any URL taken from user input (form fields, query parameters) that the server fetches must be validated (scheme allowlist, host allowlist, no private IP ranges).

#### 4e. Authentication and Session Security

- **Token/secret storage**: All tokens, secrets, and magic link values stored in the database MUST be hashed (e.g., SHA-256). Plaintext storage of any authentication material is MUST FIX. Compare against how existing session tokens are stored -- inconsistent hashing across token types is a defect.
- **Token leakage**: Auth tokens must not appear in logs, error messages, URL query parameters, or HTTP Referer headers. Check `logging.*()` calls, `print()` calls, and exception messages in changed code.
- **Token scope**: Verify credentials are not sent to endpoints or hosts that should not receive them (overlaps with SSRF above).

#### 4f. Input Validation and Parsing Safety

- **Header parsing**: HTTP headers (`Retry-After`, `Content-Type`, `Location`, etc.) contain untrusted data. Parsing must handle malformed values gracefully -- no unhandled `ValueError`, `TypeError`, or `IndexError` from `int()`, `float()`, `.split()`, or date parsing on header values.
- **API response parsing**: Data from GameChanger API responses is external input. Key lookups should use `.get()` with defaults or explicit `KeyError` handling, not bare `[]` access on unvalidated structures.
- **Path traversal**: File paths derived from external input (API data, user input) must be validated to prevent directory traversal (`../`).
- **Type coercion**: When external strings are cast to `int`, `float`, or `datetime`, wrap in try/except or validate format first.

#### 4g. Credential Hygiene

- Credentials or tokens in code, logs, comments, or test fixtures. Violation of the **Security.** item under `## Facts` in CLAUDE.md. All are MUST FIX.
- Hardcoded secrets, API keys, or tokens anywhere in `src/`, `tests/`, `scripts/`, or templates.
- `.env` values logged or displayed in error output.
- Test fixtures using real credentials instead of synthetic data.

#### 4h. Infrastructure Security

- **Docker**: `Dockerfile` changes must not run the application as root. Check for `USER` directive. Flag `--privileged`, unnecessary `CAP_ADD`, or exposed ports beyond what the app requires.
- **Dependencies**: New dependencies added to `requirements*.in` files should not be obviously unmaintained or known-vulnerable. Flag vendored copies of libraries that have known CVEs if you recognize them.
- **File permissions**: Sensitive files (`.env`, credential stores, database files) should not be world-readable in Docker volumes or created with overly permissive modes.

#### Security Checklist Summary

For quick reference while reading each changed file, mentally tick through:

1. Any SQL not using parameterized queries?
2. Any `|safe` on data that could be user-influenced?
3. Any POST form missing CSRF protection?
4. Any URL followed/fetched without host validation?
5. Any token/secret stored as plaintext?
6. Any header/input parsed without error handling?
7. Any credential appearing in logs or error messages?
8. Any Docker container running as root?
