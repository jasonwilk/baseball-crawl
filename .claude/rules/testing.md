---
paths:
  - "tests/**"
  - "src/**"  # Test Scope Discovery must fire when agents edit source files
---

# Testing Rules

- Use pytest as the test runner
- IMPORTANT: Never make real HTTP requests in tests -- use mocks or fixtures
- Use pytest fixtures for test data setup
- Test data parsing and transformation logic thoroughly
- Use parametrize for testing multiple input variations
- Name test files as `test_<module>.py`
- Name test functions as `test_<behavior_being_tested>`
- Prefer specific assertions (`assert result == expected`) over generic (`assert result`)
- Include edge cases: empty data, malformed input, missing fields
- **Subprocess smoke tests for console script entry points**: Entry points like `bb` must have at least one test that invokes the command via `subprocess.run()` (e.g., `subprocess.run(["bb", "--help"], ...)`). In-process test runners (`typer.testing.CliRunner`, pytest) add the project root to `sys.path`, which masks packaging and import errors that only surface when the entry point runs as an installed console script. Subprocess tests catch these real-world failures.

## Trustworthy pytest results (execution gotchas)

Two project-specific traps that have caused real "tests pass" misreports:

- **Never trust a piped pytest exit code.** `python -m pytest ... | tail` (or any pipe) reports the PIPE's exit code (≈always 0), NOT pytest's — a failing or hung run looks like "exit 0". In E-236 a `pytest | tail` run reported "passed, exit 0" when the real RC was 124 (a timeout/hang). Capture pytest's OWN return code with no pipe: `python -m pytest ... > /tmp/out.txt 2>&1; echo "RC=$?" >> /tmp/out.txt`, then read the file for the RC and the `N passed`/`N failed` line. The harness "background command completed (exit code 0)" reflects the whole compound command's last stage, not pytest — don't rely on it either. This is the pytest-surface form of `.claude/rules/tool-output-integrity.md`.
- **The disk-backed `db` fixture deadlocks on self-`backup()`.** The `db` fixture backing differs per report test file. `tests/test_report_generator.py`'s `db` is disk-backed at `tmp_path/test.db` (via `load_real_schema`); calling `db.backup(file_conn)` where `file_conn` opens that SAME path DEADLOCKS SQLite (the run hangs). Fresh connections already see committed rows directly — no backup needed there. Only use `db.backup()` when the source `db` is `:memory:` and a function under test opens its own connections (e.g. `tests/test_report_plays.py`). Full detail: `.claude/agent-memory/software-engineer/testing-gotchas.md`.
- **Stale `__pycache__` silently INVERTS mutation results.** Python invalidates a `.pyc` on `(mtime, size)`, so a size-CHANGING edit self-invalidates but a size-PRESERVING one may not — and reorder/move mutations are size-preserving, which makes **ordering invariants the class whose mutation evidence is least trustworthy by default**. In E-267 the interpreter executed the MUTANT while `grep`, `inspect.getsource`, and the file on disk all read correct: every source-of-truth an agent would reach for agreed, and all of them were wrong about what was executing. It cuts both ways — a mutation can appear NOT caught (fabricating a coverage gap) or a correct fix can appear broken (fabricating a defect), so every "N of M fail pre-fix" claim produced without cache hygiene is suspect. If you are actually running a mutation, the protocol is below.

### Mutation protocol — only when you are mutating source to prove a test discriminates

This fires on the deliberate act of mutating source to check that a test fails; ordinary test or source edits do not owe it. When you do run one:

- Run a **no-mutation control first**, clear `__pycache__` before each mutation AND each restore, and **assert the mutation actually applied** (a mutation whose target string no longer matches silently measures clean code and reports as an uncaught mutation).
- Re-run mutations after any refactor — a mutation can stop discriminating when the code beneath it changes.
- **A mutant must be the PLAUSIBLE FUTURE EDIT, not merely an edit that breaks the property** — a mutant nobody would write proves the test catches vandalism, not regression.
- **Report per-test outcomes, never an aggregate count**: in E-270 a `get_connection` mutant failed both tests, but a plain writable-connection mutant (the edit someone would actually make) PASSED test 1 and failed only test 2 — an aggregate "2 caught" would have hidden which test was load-bearing.

A verification method needs its own verification.

## An absence claim needs proof the mechanism COMPLETED CLEANLY

When a test asserts something did NOT happen — rows survived, nothing was retired, no file was written — pair it with positive evidence that the mechanism **completed cleanly**, not merely that it was ENTERED. "Ran" is ambiguous between the two, and a `side_effect` spy records the call BEFORE invoking the wrapped function, so it certifies only ENTERED. E-270 proved this empirically rather than by argument: patching the reconcile to RAISE still produced `spy.call_count: 1`, the expected `game_ids`, and `A lines survive: True` — every positive assertion satisfied by a mechanism that blew up, with the ERROR invisible to a WARNING-level log check.

On this codebase the right evidence is usually the returned **result object** (`LoadResult.errors == 0`), not the spy. This matters more here than the general form, because the swallow-and-count pattern is DELIBERATE and load-bearing: `game_loader.py` catches broadly, logs ERROR, and returns 1 into `result.errors` so a failed cleanup never loses a good load. **Anywhere that pattern exists, spy-based proof is systematically insufficient — and it exists on the destructive paths by design.**

## Annotating a fixture limitation is not covering it

When you close a known coverage gap with a COMMENT rather than a TEST — "unreachable in production", "the fixture convention prevents this shape", "derived names make this case impossible here" — you have marked where the next defect will be, not closed the gap. The failure is subtler than omission: **an accurate scope note SUBSTITUTES for covering the region, because accuracy about a gap reads as management of it.** E-267 produced three such annotations, and two independent reviewers later found two unrelated defects inside the region one of them described.

The mechanical alternative: **when a fixture cannot produce a shape the production caller can, drive the test through the real producer rather than documenting the divergence.** This is stated generally because this codebase's producers take injected dependencies (e.g. `ScoutingCrawler`'s constructor-injected client), keeping the real producer cheap and in-process. That condition is what makes the rule safe — where a producer would need real network or credentials, driving through it yields a heavier or skipped test and a documented fixture limitation is the better trade. If the injection convention erodes, revisit this rule rather than applying it anyway. When you do leave an annotation, state what would have to be true for the uncovered path to matter and then CHECK whether it holds: an annotation is a hypothesis, not a result.

Note the compounding case — **a fixture hardened against one hazard can be structurally UNABLE to detect its neighbour.** E-267's per-player unique-name helper was added so a fixture would stop accidentally measuring the dedup sweep; that hardening made it impossible for any test in the file to detect the reconcile being mis-ordered below the dedup sweep. When you harden a fixture, ask what the hardening now makes undetectable.

**When a change makes an input load-bearing, go re-read the tests asserting it is NOT.** "Would this survive plausible edits?" does not cover this case, because the edit is not to the tested code — it is to what a parameter MEANS. E-267: a test pinned `previously_rostered_ids` as feeding only the log level, was ratified as sufficient, and was falsified when a later change made that input meaningful; the old test kept passing by fixture coincidence (it sat at the cap boundary either way). A test asserting an input is inert becomes a liability the moment the input is not, and it fails silently rather than loudly. The searchable tell is the test NAME asserting a negative property — `..._cannot_influence_...`, `..._never_affects_...`, `..._is_a_noop_...`. Those go wrong when SEMANTICS WIDEN rather than when code breaks, so they never fail; they quietly stop meaning anything. When a parameter's role changes, grep test names for negative-property assertions. Binds whoever makes the change — implementer and reviewer alike.

## Test Scope Discovery

When you modify a function in an existing source module, you MUST discover and run all test files that import from that module -- not just the tests named in the story's "Files to Create or Modify."

### Why

Story-scoped test lists are written during planning, before the implementation details are known. They cover the obvious test files but can miss cross-file dependencies. During E-085, a change to `check_single_profile()` in `src/gamechanger/credentials.py` broke `tests/test_check_credentials.py`, but the implementer only ran `tests/test_credentials.py` and `tests/test_cli_creds.py` (the story-scoped tests). The broken test was in a different file that also imports from the same module.

### The Discovery Pattern

For each source module you modified, find all test files that import from it:

1. Determine the importable module path. For `src/gamechanger/credentials.py`, this is `gamechanger.credentials`.
2. Search for test files that import from that module:
   ```
   grep -rl "gamechanger.credentials" tests/
   ```
   This catches `from gamechanger.credentials import ...`, `import gamechanger.credentials`, and variant forms. False positives are harmless (extra tests run); false negatives are the real risk, and grep avoids them.
3. Run the discovered test files in addition to any story-scoped tests:
   ```
   pytest tests/test_credentials.py tests/test_cli_creds.py tests/test_check_credentials.py
   ```

### Scope

The default is **targeted discovery**: find and run test files that import from modules you changed. If targeted discovery reveals 10+ test files, run `pytest` (full suite) instead of listing them individually.

### Subprocess Edge Case

Subprocess-based tests (e.g., `test_script_entry_points.py` invokes scripts via `subprocess.run()` that internally import from modified modules) are not discovered by grep because the import happens in a child process. These tests check invocation and help-text, not internal logic -- they will still pass when you change a function's behavior. Subprocess-based tests are discovered by convention, not grep.

## Error-Path Testing

When code calls a function that can fail -- returns an error, raises an exception, or returns a status object indicating failure -- write at least one test where that function fails. Verify the caller handles the failure correctly: propagates the error, sets an appropriate status, returns a non-zero exit code, or surfaces the failure to the operator. The caller must NOT print a misleading success message or exit 0 when a dependency failed.

### Primary Scope: Orchestration Code

This requirement is most critical for orchestration code -- CLI commands, pipeline runners, and any function that chains multiple steps together where a failure in one step must be visible to the operator. These are the paths where silent failure causes the most damage: the operator believes the pipeline succeeded when it did not.

### Example Pattern

```python
def test_scout_command_surfaces_loader_failure(tmp_path, monkeypatch):
    """When the loader fails, the CLI must exit non-zero and report the error."""
    monkeypatch.setattr(
        "gamechanger.loaders.scouting_loader.load_team",
        Mock(side_effect=Exception("DB write failed")),
    )
    result = runner.invoke(app, ["data", "scout", "--team", "test-team"])
    assert result.exit_code != 0
    assert "DB write failed" in result.output
```

Mock the fallible dependency to raise or return a failure indicator. Assert the caller's exit code and output reflect the failure.

## Test-Validates-Spec

When writing tests that mock external data (API responses, database query results, file contents), verify the mock data matches the **authoritative spec** -- not the implementation under test. Sources of truth:

- `docs/api/endpoints/` for API response shapes and field names
- `migrations/*.sql` for database schemas (column names, types, constraints)
- Function docstrings for return value contracts

A test whose mock data mirrors a buggy implementation passes vacuously and provides false confidence. The test confirms the code does what it does, not that it does what it should.

### Example: E-147 Finding #2 (API field path divergence)

The GameChanger authenticated team endpoint (`docs/api/endpoints/get-teams-team_id.md`) returns `season_year` as a top-level integer field. The public team endpoint (`docs/api/endpoints/get-public-teams-public_id.md`) carries the year at `team_season.year` -- a FLAT integer sibling of `team_season.season`, where `season` is a bare string (e.g. `"summer"`), NOT an object with a `.year`. **Neither endpoint nests the year at `team_season.season.year`** -- that path is a fabrication. Code that reads either endpoint but accesses `data["team_season"]["season"]["year"]` is wrong -- yet a test that mocks the response with `{"team_season": {"season": {"year": 2026}}}` will pass, because the mock mirrors the buggy (nonexistent) field path instead of either endpoint's actual schema.

**Wrong** -- mock mirrors the implementation's fabricated field path:

```python
mock_response = {"team_season": {"season": {"year": 2026}}}  # matches buggy code; NO endpoint returns this nesting
```

**Right** -- mock mirrors the API endpoint doc's actual response shape:

```python
# Per docs/api/endpoints/get-teams-team_id.md, season_year is top-level (authenticated endpoint):
mock_response = {"season_year": 2026}
# Per docs/api/endpoints/get-public-teams-public_id.md, the public endpoint is FLAT
# (season = bare string, year = flat int sibling, record = {win,loss,tie}):
mock_response = {"team_season": {"season": "summer", "year": 2026, "record": {"win": 12, "loss": 8, "tie": 0}}}
```

Before writing a mock, open the authoritative spec and copy the field structure from there. If the spec and the implementation disagree, the test should fail -- that disagreement is the bug.

### Inverse direction: when you change a production contract, stale tests are MUST-FIX

The same principle runs the other way. When you deliberately **change a production contract** -- add or rename a query column, change a template variable, alter a figure's dimensions, change a function's return shape -- every fixture, mock, or assertion that still encodes the *old* shape is now a stale test, and updating it is a **MUST-FIX** part of the same change, not optional cleanup. A test that asserts the old contract will either fail (caught) or, worse, pass vacuously against an outdated fixture and give false confidence that nothing broke. When you change a contract, grep `tests/` for every fixture and assertion that encodes the old shape and bring them to the new contract in the same change. Leaving the suite red (or green-but-stale) is a regression, not a follow-up.
