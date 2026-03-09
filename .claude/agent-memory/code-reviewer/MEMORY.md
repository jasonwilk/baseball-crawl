# Code Reviewer Agent Memory

## Recurring Patterns Found in Reviews

### Test/Implementation Alignment on Behavior Changes
When an implementer changes behavior for correctness (e.g., making PII-safe fallbacks instead of email exposure),
existing tests written against the old behavior will break. Always run the full related test suite, not just
new test files. Pre-existing tests that document old behavior need to be updated when behavior intentionally changes.

### Function Length Violations (50-line rule)
The 50-line limit applies to ALL code written or modified in a story, including rewritten functions.
A function replacement counts as new code and is subject to the 50-line limit even if the original was longer.
Common overage areas: multi-step auth flows, CLI commands with error handling branches.

### Duplicate Helper Functions
When a story says "consider moving to a shared location (implementer discretion)" for a utility function,
and the implementer instead creates a near-identical copy in a different module, flag as SHOULD FIX.

### PII in Tests
Test files may contain fake PII (email addresses) as test data. The `# synthetic-test-data` comment at the
top of test files marks them as containing synthetic data. Real PII must never appear.

### git diff vs. tracked-but-unchanged files
When using `git diff HEAD`, files listed in the review assignment but not appearing in the diff were not
changed in this epic -- they existed before. The scope guardrail applies: only flag code WRITTEN OR MODIFIED
in the current story.

## Project-Specific Conventions
- `from __future__ import annotations` required at top of every module
- `Optional[str]` from typing is acceptable in Typer CLI commands (existing pattern)
- Bare `except Exception:` needs `# noqa: BLE001`
- Function length limit: 50 lines (strict -- applies to rewritten functions too)
- Test files use `# synthetic-test-data` comment for files with fake credentials/emails
- `dotenv_values()` from python-dotenv is the standard way to load .env in tests (monkeypatched)

## Important File Locations
- Python style rules: `.claude/rules/python-style.md`
- Testing rules: `.claude/rules/testing.md`
- Story files: `/epics/E-NNN-slug/` or `/.project/archive/E-NNN-slug/` after archival
