<!-- synthetic-test-data -->
# Safe Data Handling Guide

## The One Rule

If a file was produced by a real API call or contains real credentials, it goes
in `/ephemeral/`, never in a commit.

## Where Sensitive Data Lives

All raw API responses and real data files belong in the `/ephemeral/` directory
at the repository root. This directory is gitignored -- nothing placed there can
be accidentally committed.

Create a subdirectory for your current epic:

```
ephemeral/E-005/response.json
ephemeral/E-012/roster-data.csv
ephemeral/scratch/one-off-test.json
```

See `/ephemeral/README.md` for the full convention.

## What Can Be Committed

| Content | Committable? | Where it goes |
|---------|-------------|---------------|
| Source code (no secrets) | Yes | `src/` |
| Test fixtures with synthetic data | Yes | `tests/` (with `synthetic-test-data` marker) |
| Documentation | Yes | `docs/` |
| SQL migrations | Yes | `migrations/` |
| Raw API responses | **No** | `/ephemeral/` |
| Files containing real names, emails, phones | **No** | `/ephemeral/` |
| Files containing credentials or tokens | **No** | `/ephemeral/` |

## What Gets Scanned

The pre-commit scanner checks staged files for these pattern categories:

- **Email addresses** -- e.g., `user@example.com`
- **US phone numbers** -- e.g., `(555) 867-5309`, `555-867-5309`
- **Bearer tokens** -- e.g., `Authorization: Bearer eyJ...`
- **API key assignments** -- e.g., `api_key = "sk-..."`, `secret_key: abc123...`

For the authoritative pattern list with exact regexes, see
`src/safety/pii_patterns.py`.

Full names and GameChanger user IDs are also PII but cannot be reliably detected
by regex. They are protected by the `/ephemeral/` directory convention instead.

### What Gets Skipped

Certain paths are excluded from scanning entirely. Files whose paths start with
any of the following prefixes are never read by the scanner:

| Path prefix | Reason |
|-------------|--------|
| `.git/` | Git internals |
| `.claude/` | Agent context files |
| `node_modules/`, `__pycache__/` | Generated artifacts |
| `requirements.txt`, `requirements-dev.txt` | pip-compiled lockfiles (SHA256 hashes trigger phone pattern) |
| `epics/` | Active epic and story files (planning artifacts) |
| `.project/` | Archive, ideas, templates, and research (planning artifacts) |

Planning artifacts (`epics/` and `.project/`) frequently reference PII-like
patterns as documentation examples. They are excluded because real data from
the API should never appear there in the first place -- if it does, the
`/ephemeral/` convention was already violated earlier.

`docs/` is intentionally **not** excluded -- documentation could contain real
PII if someone pastes it carelessly. Use inline suppression (see below) for
any legitimate PII-like pattern in documentation files.

`tests/` is intentionally **not** excluded -- the `synthetic-test-data` marker
handles test fixtures; inline suppression covers edge cases.

## RFC 2606 Domain Allowlist

RFC 2606 reserves certain domains for documentation and testing. Email
addresses using these domains are never real, so the scanner allows them
automatically without requiring a `synthetic-test-data` marker or `# pii-ok`
comment.

**Reserved second-level domains** (the domain itself and any subdomain):

| Domain | Example |
|--------|---------|
| `example.com` | `user@example.com`, `user@sub.example.com` |
| `example.org` | `coach@example.org` |
| `example.net` | `player@example.net` |

**Reserved top-level domains** (any domain ending in these TLDs):

| TLD | Example |
|-----|---------|
| `.test` | `user@myapp.test` |
| `.example` | `user@foo.example` |
| `.invalid` | `user@fake.invalid` |
| `.localhost` | `user@app.localhost` |

`localhost` (without a TLD) is also treated as safe.

The allowlist applies **only to the email pattern**. Phone numbers, bearer
tokens, and API key assignments are unaffected -- use `# pii-ok` or the
`synthetic-test-data` marker for those.

## Installing the Pre-Commit Hook

After cloning the repository, run:

```bash
./scripts/install-hooks.sh
```

This configures Git to use the `.githooks/` directory for hooks. You only need
to run this once per clone. The Claude Code PreToolUse hook requires no
installation -- it fires automatically from `.claude/settings.json`.

To verify the hook is active:

```bash
git commit --allow-empty -m "test: verify hook"
```

You should see scanner output (either "No PII detected" or a list of blocked
patterns). The commit should succeed if no PII is found.

## When the Hook Fires

### Understanding the Output

When the scanner detects sensitive data, you will see output like this:

```
[PII BLOCKED] path/to/file.json:42: matched 'email' pattern
[PII BLOCKED] path/to/file.json:87: matched 'bearer_token' pattern

2 violation(s) found in 1 file(s).

[pii-hook] Commit blocked. Fix the violations above, then try again.
```

Each line names the file, line number, and which pattern matched.

### Fixing a Violation

1. **Move the file to `/ephemeral/`** if it contains real data from an API call.
   Unstage it with `git reset HEAD <file>`, then move it.

2. **Remove the sensitive data** if the file is source code that accidentally
   contains a hardcoded token or credential. Replace with an environment variable
   reference or a placeholder.

3. **Add the synthetic marker** if the file is a test fixture containing fake
   data that happens to look like PII. Add `synthetic-test-data` to the first
   5 lines of the file (e.g., in a comment). See "Working with Test Fixtures"
   below.

4. **Add a `# pii-ok` comment** if the match is a genuine false positive on a
   single line -- for example, a regex pattern in source code that contains an
   email-like structure, or a documented example in a Markdown file. Add the
   comment at the end of the offending line. See "Inline Suppression" below.

### Inline Suppression: `# pii-ok`

A `# pii-ok` comment at the end of a line suppresses all scanner findings on
that line. This is analogous to `# noqa` in flake8 or `# type: ignore` in
mypy -- a surgical opt-out for a single line when the match is a known false
positive.

**Python and most text files:**

```python
EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'  # pii-ok
```

**YAML and shell:**

```yaml
example_contact: admin@fake-domain.example  # pii-ok
```

**HTML and XML** (`#` is not a comment character -- use an HTML comment):

```html
<p>Contact us at admin@internal.localhost</p> <!-- pii-ok -->
```

**When `# pii-ok` is appropriate:**
- A regex string in source code that resembles an email or phone number
- A documented example in a Markdown file that uses a pattern not covered by
  the RFC 2606 allowlist
- A configuration value that is structurally PII-like but is not real data
  (e.g., a placeholder in a template)

**When `# pii-ok` is NOT appropriate:**
- Real data that ended up in a source file -- move to `/ephemeral/` and fix
  the code that put it there
- Bulk suppression of many lines -- use `synthetic-test-data` for test
  fixtures instead
- Suppressing a real credential or token -- remove or rotate it

### Legitimate Bypass

```bash
git commit --no-verify -m "your commit message"
```

The `--no-verify` flag skips all Git hooks, including the PII scanner.

**When bypassing is appropriate:**
- You have verified the match is a false positive (e.g., a regex string in
  source code that resembles an email)
- An emergency hotfix must go in immediately and the false positive cannot
  be quickly resolved

**When bypassing is NOT appropriate:**
- "I'm sure the file is clean" -- let the scanner confirm it
- "The hook is slow" -- fix the hook, do not bypass it
- "I'm committing test data" -- use the `synthetic-test-data` marker instead

**Warning:** `--no-verify` skips ALL Git hooks, not just the PII scanner. After
using it, manually review the committed files.

The Claude Code PreToolUse hook **cannot be bypassed by an agent**. Only a human
can disable it by modifying `.claude/settings.json`. This is intentional --
agents are the primary committers in this project and should never skip PII
checks.

## Working with Test Fixtures

Test fixtures that contain fake PII-like data (fake emails, fake phone numbers)
must include the string `synthetic-test-data` in the first 5 lines of the file.
This tells the scanner to skip the file entirely.

Example:

```python
# synthetic-test-data
# All data below is fake, used for testing the PII scanner.

TEST_CONTACTS = [
    {"email": "test@example.com", "phone": "(555) 867-5309"},
]
```

Rules for synthetic data:
- Use obviously fake values: `test@example.com`, `(555) 867-5309`,
  `Jane Fakename`
- Place the marker in a comment near the top of the file
- The marker is case-sensitive: `synthetic-test-data` (all lowercase, hyphens)

## Safe Fake Data Standards

When writing tests, documentation examples, or code comments that need
PII-like values, use these recommended patterns. They are either in the RFC
2606 allowlist (emails) or are universally recognized as fictional (phones,
tokens).

### Email Addresses

Use RFC 2606 reserved domains. The scanner allows these automatically -- no
marker or suppression comment required.

```
user@example.com
coach@example.org
player@example.net
admin@myapp.test
```

### US Phone Numbers

The `555-01xx` range (`555-0100` through `555-0199`) is reserved by the North
American Numbering Plan for fictional use. These numbers are universally
understood to be fake and will never be assigned to a real subscriber.

```
555-0100
555-0101
(555) 555-0199
+1-555-555-0100
```

Avoid `555-867-5309` and similar well-known pop-culture numbers -- while fake,
they are associated with real spam calls and are less clearly fictional in
technical contexts.

### Bearer Tokens

Use a clearly fictional placeholder that matches the bearer pattern structure:

```
Bearer FAKE_TOKEN_FOR_DOCS
Bearer TEST_CREDENTIAL_PLACEHOLDER
```

Files containing these will still trigger the scanner (bearer token pattern
fires on any `Bearer <value>`) -- use `# pii-ok` or `synthetic-test-data` as
appropriate.

### Summary Table

| PII type | Recommended fake value | Scanner behavior |
|----------|----------------------|-----------------|
| Email | `user@example.com` | Allowed automatically (RFC 2606) |
| Phone | `555-0100` to `555-0199` | Still flagged -- use `# pii-ok` or `synthetic-test-data` |
| Bearer token | `Bearer FAKE_TOKEN_FOR_DOCS` | Still flagged -- use `# pii-ok` or `synthetic-test-data` |
| API key | `api_key = "PLACEHOLDER_NOT_REAL"` | Still flagged -- use `# pii-ok` or `synthetic-test-data` |

## Quick Reference

| Scenario | What to do |
|----------|------------|
| **Store an API response** | Save to `/ephemeral/<epic>/`. Never stage it. |
| **Commit a script** | Ensure no hardcoded tokens or credentials. The hook will catch common patterns. |
| **Add a test fixture** | Use fake data. Add `synthetic-test-data` in the first 5 lines. Commit normally. |
| **Share data with a teammate** | Describe the API call that produced it. Do not share the file -- it contains real data. |
| **Use a fake email in code or docs** | Use `user@example.com` (RFC 2606). No marker needed. |
| **Use a fake phone in code or docs** | Use `555-0100`. Add `# pii-ok` or `synthetic-test-data`. |
| **Use a fake token in code or docs** | Use `Bearer FAKE_TOKEN_FOR_DOCS`. Add `# pii-ok` or `synthetic-test-data`. |
| **Single false positive line** | Add `# pii-ok` at end of line (HTML: `<!-- pii-ok -->`). |
| **False positives throughout a test file** | Add `synthetic-test-data` marker in first 5 lines. |

## Related Documents

- `/ephemeral/README.md` -- Directory convention and what belongs there
- `src/safety/pii_patterns.py` -- Authoritative pattern list with regexes and
  explanations of each PII/credential category
- `.claude/rules/pii-safety.md` -- Rules for agents modifying the scanner
- `.claude/hooks/README.md` -- Documentation for the Claude Code PII hook
