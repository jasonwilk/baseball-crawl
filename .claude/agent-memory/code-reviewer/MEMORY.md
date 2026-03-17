# Code Reviewer Agent Memory

## Mandatory Review Checks (added after E-097 post-dev failures)

### SQL Dimension Audit (Bugs, Priority 2)
For every SELECT/aggregate query in a loader, identify ALL dimensions in the calling function's signature.
Verify the WHERE clause filters on ALL of them. If a function receives `(team_id, season_id)` and queries
a table, the WHERE clause must use both. Missing dimensions = silent data scope bug. MUST FIX.
If the required dimension requires a JOIN (not a direct column on the queried table), that is additional
evidence the query is wrong — flag it even harder.

### Fallible Call Chain Audit (Bugs, Priority 2)
For every call to a fallible operation (DB write, loader call, HTTP call, file write) in the CLI path:
- Verify exceptions propagate to a point that affects exit code / user feedback
- Verify the caller does NOT print "success" before inspecting the result
- Common pattern: `loader.load_team()` call followed by unconditional `echo("Load complete")` is a bug

### Status Write Lifecycle Audit (Bugs, Priority 2)
When a function writes a terminal status (`completed`, `failed`) to a tracking table (e.g., `scouting_runs`):
- Trace forward: what downstream behavior does this status gate?
- Verify the status is written ONLY AFTER gated work succeeds
- Key failure mode: status written at end of crawl phase, loading phase happens separately -- if load fails,
  status is already "completed" and next run's freshness check skips the team permanently

### Multi-Dimension Test Coverage (Tests, Priority 3)
When a test covers an aggregate/sum computation that should filter by multiple dimensions, the test fixture
MUST include data spanning at least two values of each filtering dimension (two seasons, two teams, etc.).
Single-value fixtures make wrong-scope queries produce correct results -- the bug is invisible.

### Error-Path CLI Test Coverage (Tests, Priority 3)
For every new CLI command added in a story, require at least one test where a critical dependency
(loader, crawler, DB) raises an exception or returns a failure indicator. Verify exit code is non-zero
and output does not falsely claim success. Happy-path tests only are MUST FIX.

## Recurring Patterns Found in Reviews

### Test/Implementation Alignment on Behavior Changes
When an implementer changes behavior for correctness (e.g., making PII-safe fallbacks instead of email exposure),
existing tests written against the old behavior will break. Always run the full related test suite, not just
new test files. Pre-existing tests that document old behavior need to be updated when behavior intentionally changes.

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
- Test files use `# synthetic-test-data` comment for files with fake credentials/emails
- `dotenv_values()` from python-dotenv is the standard way to load .env in tests (monkeypatched)

## Important File Locations
- Python style rules: `.claude/rules/python-style.md`
- Testing rules: `.claude/rules/testing.md`
- Story files: `/epics/E-NNN-slug/` or `/.project/archive/E-NNN-slug/` after archival
