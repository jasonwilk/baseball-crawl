# Code Reviewer Agent Memory

## Invariant Audit Patterns
- [Sibling writers can defeat a provenance guard](invariant_audit_sibling_writer.md) — when an epic guards ONE writer, sweep sibling DELETE+rederive paths that delete the protected row first (E-237 merge_player_pair).
- [Spec audit: distrust "sole/canonical producer" claims](spec_audit_sibling_producer.md) — grep src/ for literal output forms + sibling `_derive_*`/`_ensure_*` helpers before trusting an epic's enumerated producer set (E-241: crawler `_derive_season_id` falsified "no code path produces YYYY-suffix" + broke migration durability).

## Removal-Epic Review Patterns
- [Asset deletion: sweep ALL test reference mechanisms](route_deletion_test_sweep.md) — deleting a route/module/template breaks tests that import it, `client.get()` it (assert 200), OR read it by literal path in a parametrize list (FileNotFoundError); import sweeps miss forms 2+3. Never `| head` a completeness grep (E-239: Codex caught form 2 in 4b, Phase 5 gate caught form 3).
- [Spec audit: a column-DROP story asserting full-suite-green can't defer fixture cleanup](spec_audit_column_drop_fixture_atomicity.md) — a dropped column breaks all its INSERT fixtures atomically; if cleanup is assigned downstream while the drop story asserts pytest-green, that's a MUST-FIX scope/dependency finding. Grep `tests/` (incl. fixtures/*.sql) for the dropped element and count files (E-250: season_type in 29 files + 2 SQL fixtures).

## Refactor/Extraction Review Patterns
- [Extraction scope gap = a CALLER's existing characterization suite](refactor_extraction_caller_test_scope.md) — when a story relocates a seam, the unrun test is usually a caller's pre-existing transport-mocked suite that directly exercises the changed function; grep tests/ for the changed function + module, flag any importer not in the run list as MUST FIX (it's often the committed pre-vs-post pin the HARD gate rests on). E-247-03: test_report_generator.py's ~17 _resolve_gc_uuid tests.
- [Removing an early-return before a recompute/dedup tail: prove no-op on a POPULATED DB](recompute_tail_noop_populated_db.md) — a fresh-DB no-op test is necessary but NOT sufficient; canonical_recompute DELETE+re-INSERTs from ALL existing per-game rows and dedup can merge, so on a populated/out-of-sync DB (post-backfill stale aggregates, pre-existing dupes) the unconditional tail mutates data. Demand a populated-DB characterization test; under a stat HARD gate, restore the early-return. (E-247-01 F1, caught by Codex Phase 4b after I missed it.)

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

### Allowlist-gated DB writes need real-schema round-trip proof
See [allowlist-gated DB writes](feedback_allowlist_gated_db_writes.md) — when a write helper filters
columns through an allowlist (e.g. `_update_run_record` + `_RUN_RECORD_COLUMNS`), a new column is
silently dropped if not added to the allowlist. Require the allowlist add AND a real-schema round-trip
test (not a mock). E-236 used this pattern correctly across 4 count columns.

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

## Security Review Mandate (added after E-123 full-project code review)

The Priority 4 security review checklist was expanded significantly after a full-project code review
found critical issues (CSRF, SQLi, SSRF, XSS, plaintext tokens, root Docker) that should have been
caught during story-level reviews. The checklist is now in the agent definition under Priority 4 with
subsections 4a-4h. Key reminders:

- Cloudflare/WAF/network controls are NOT compensating controls for app-layer defects. Never downgrade.
- `|safe` in Jinja2 templates is a red flag -- must be justified for every use.
- POST forms without CSRF tokens are automatic MUST FIX.
- SQL via f-string/format/concat is automatic MUST FIX regardless of input source.
- URL following (pagination, redirects) must validate host before sending auth headers.
- All stored tokens/secrets must be hashed -- inconsistency between token types is a defect.
- Header parsing (Retry-After, etc.) must handle malformed values without crashing.
- Docker containers must not run as root.

## Important File Locations
- Python style rules: `.claude/rules/python-style.md`
- Testing rules: `.claude/rules/testing.md`
- Story files: `/epics/E-NNN-slug/` or `/.project/archive/E-NNN-slug/` after archival
