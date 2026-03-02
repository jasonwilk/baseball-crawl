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

## Quick Reference

| Scenario | What to do |
|----------|------------|
| **Store an API response** | Save to `/ephemeral/<epic>/`. Never stage it. |
| **Commit a script** | Ensure no hardcoded tokens or credentials. The hook will catch common patterns. |
| **Add a test fixture** | Use fake data. Add `synthetic-test-data` in the first 5 lines. Commit normally. |
| **Share data with a teammate** | Describe the API call that produced it. Do not share the file -- it contains real data. |

## Related Documents

- `/ephemeral/README.md` -- Directory convention and what belongs there
- `src/safety/pii_patterns.py` -- Authoritative pattern list with regexes and
  explanations of each PII/credential category
- `.claude/rules/pii-safety.md` -- Rules for agents modifying the scanner
- `.claude/hooks/README.md` -- Documentation for the Claude Code PII hook
