# E-005 Refinement: Story Quality Review

**Reviewer**: story-reviewer (refinement team)
**Date**: 2026-03-01
**Scope**: All 5 E-005 stories + epic file, reviewed against CLAUDE.md and project rules

---

## Per-Story Issues

### E-005-01: Build canonical browser header configuration

**AC Testability**: All ACs are testable. AC-1 through AC-5 are simple assertions against a dict. AC-6 (docstring content) is verifiable by inspection or a string-match test. AC-7 delegates to a test file.

**Issues**:

1. **[Minor] AC-6 is a documentation criterion, not a code behavior** -- Verifying "a module-level docstring explains X, Y, Z" is subjective. An implementing agent could write a docstring that mentions all four topics but is unclear. Consider either dropping this AC (docstrings are a DoD item, not a testable AC) or making it a DoD bullet instead.

2. **[Important] No AC covers the `Accept-Encoding` value including `zstd`** -- The Notes section calls out that `zstd` must not be dropped, but no AC explicitly checks `Accept-Encoding` contains `gzip, deflate, br, zstd`. AC-1 only checks key presence, not specific values for non-UA headers. An implementing agent could write `Accept-Encoding: gzip, deflate, br` and pass all ACs.

3. **[Minor] Import path `from src.http.headers import BROWSER_HEADERS` assumes a specific Python path setup** -- No story mentions creating a top-level `src/__init__.py` or configuring `sys.path` / `pyproject.toml` with a package install. The import will fail without one of these. The Technical Approach says to create `src/http/__init__.py` but not `src/__init__.py`. This is technically a cross-story gap (see below).

4. **[Minor] No `pyproject.toml` or `requirements.txt` exists in the repo** -- E-005-01 has no external dependencies (pure stdlib), but the test file needs `pytest`. No story addresses project setup.

**Completeness**: Good. Technical approach is clear enough for an implementing agent.

---

### E-005-02: Build HTTP session factory with rate limiting and jitter

**AC Testability**: ACs 1-5 and 7 are testable with mocked HTTP. AC-6 is a signature/type check.

**Issues**:

5. **[Blocking] AC-3 timing assertion is too tight for CI** -- AC-3 says "the elapsed time between them is between 1000ms and 1500ms." In practice, `time.sleep()` on any OS can overshoot, and test execution overhead adds time. The Notes section mentions a buffer ("Assert `1.0 <= elapsed <= 1.6`") but the AC itself says 1000-1500ms. The AC and the Notes contradict each other. **Fix**: Update AC-3 to state the range with a reasonable upper buffer (e.g., "at least 1000ms and no more than 2000ms") or defer to the Notes' 1.6s upper bound.

6. **[Important] AC-2 and AC-3 overlap and create confusion** -- AC-2 says "no sooner than 1000ms" (lower bound only). AC-3 says "between 1000ms and 1500ms" (lower AND upper bound, implying jitter is bounded). These test overlapping behavior. Suggestion: merge into one AC that states the full contract: "delay is at least `min_delay_ms` and at most `min_delay_ms + jitter_ms` (plus reasonable execution overhead for testing)."

7. **[Important] AC-5 log safety check is incomplete** -- AC-5 checks for `"Authorization"`, `"Bearer"`, and `"Cookie"` substrings. But what about `"Set-Cookie"` in response logging? Or arbitrary header names? The epic's Logging Safety Rule says "Any header value" must not be logged, not just specific ones. The AC narrows the contract more than the epic intends. Consider adding: "no log record contains any key from BROWSER_HEADERS as a substring" or "no log record contains any HTTP header name-value pair."

8. **[Minor] The response hook fires AFTER every response, including errors** -- The technical approach puts the rate-limit sleep in a response hook. This means a 429 or 5xx response also triggers the sleep before the caller gets the response. This is probably fine (and even desirable), but it is not stated. An implementing agent might wonder whether to skip the delay on errors.

9. **[Minor] Cookie jar initialization is redundant** -- The technical approach says `cookies=httpx.Cookies()` but httpx.Client already creates an empty cookie jar by default. Not a bug, but could confuse an implementer into thinking it is required.

10. **[Important] No AC covers what happens when `min_delay_ms=0` and `jitter_ms=0`** -- Callers could pass zero values to disable rate limiting (useful in tests). The behavior should be specified: does it still work (zero sleep), or is it rejected? The Notes section uses `min_delay_ms=200` for tests but does not address the zero case.

---

### E-005-03: Retrofit GameChanger client to use session factory

**AC Testability**: ACs are testable. AC-1 is a grep check. AC-2 is a mocked request assertion. AC-3 delegates to E-001-02's test suite. AC-4 is a parameter mapping check. AC-5 is a code-level import assertion.

**Issues**:

11. **[Blocking] E-001-02 does not exist yet and is `TODO`** -- E-005-03 depends on E-001-02 being DONE, but E-001-02 is still `TODO` in E-001 (which is `ACTIVE`). The story acknowledges this ("should be executed AFTER E-001-02 is DONE") and has a contingency plan (abandon if E-001-02 is written against `create_session()` directly). However, dispatching E-005-03 before E-001-02 is complete would waste effort. **This dependency is correctly stated but the epic should note that E-005-03 cannot be dispatched until E-001 progress is assessed.**

12. **[Important] AC-4 changes the default delay from 500ms to 1000ms -- behavioral regression risk** -- The story says "If the existing E-001-02 tests hardcode the 500ms default, update them." This is fine, but AC-3 says "All existing E-001-02 acceptance criteria continue to pass" -- which includes E-001-02 AC-6 that specifies `request_delay_ms` default of 500. Changing the default to 1000ms technically violates E-001-02 AC-6. **Fix**: Either (a) update E-001-02 AC-6's default to 1000ms as part of this story's scope, or (b) explicitly state that AC-4 supersedes E-001-02 AC-6.

13. **[Important] AC-1 grep check is fragile** -- `grep "httpx.Client(" src/gamechanger/` will miss cases like `httpx.Client (` (with a space) or `httpx .Client(`. More importantly, E-005-02's `session.py` itself calls `httpx.Client(` internally -- the grep should be scoped to `src/gamechanger/` only, which it is, but the AC text should make the scope explicit. Currently it says "Given `src/gamechanger/client.py`, when grepped for `httpx.Client(`" which is adequately scoped.

14. **[Minor] No AC covers the case where `GameChangerClient` previously had manual `time.sleep()` calls** -- The Technical Approach says "remove any manual `time.sleep()` calls in `GameChangerClient.get()`" but no AC verifies this removal. An implementing agent could leave dead sleep calls alongside the event-hook sleeps, doubling the delay.

---

### E-005-04: Write header discipline tests

**AC Testability**: ACs 1-5 are testable. AC-6 is conditional ("if E-005-03 is done").

**Issues**:

15. **[Important] Heavy overlap with E-005-02 unit tests** -- AC-1 (headers present), AC-2 (no token in logs), AC-3 (rate limiting/jitter), and AC-4 (cookie jar) are all stated as E-005-02 ACs as well (E-005-02 AC-1, AC-5, AC-2/AC-3, AC-4 respectively). The story says "these are integration-level" but all the tests use `create_session()` directly with mocked HTTP -- which is exactly what E-005-02's tests do. **The boundary between "unit tests in E-005-02" and "integration tests in E-005-04" is not clear.** The only genuine integration test is AC-6 (GameChangerClient end-to-end), which is conditional.

    **Suggestion**: Either (a) remove the unit-level ACs from E-005-04 and make it purely about the GameChangerClient integration (AC-6 becomes required, not conditional, blocked by E-005-03), or (b) redefine E-005-04 as "regression suite" with the understanding that overlap is intentional for safety. Either way, the current framing is confusing.

16. **[Important] AC-3 uses `min_delay_ms=200, jitter_ms=100` but the assertion approach differs from E-005-02** -- E-005-02 Notes say "Assert `1.0 <= elapsed <= 1.6`" (defaults). E-005-04 Notes say use 200/100 and "Assert `min(gaps) >= 0.200`". These are consistent in spirit but the dual specification of timing test methodology across two stories creates a risk of conflicting implementations. **Consider centralizing the timing test approach in one story only.**

17. **[Minor] AC-2 checks for `"Cookie"` substring in logs** -- If the session factory logs something like "Cookie jar initialized" (which is plausible logging), it would fail this check. The AC should be more precise: check for actual header values (the token string), not generic header names. Or the implementation should avoid using the word "Cookie" in any log message, which should be stated.

---

### E-005-05: Write HTTP integration guide

**AC Testability**: ACs 1-5 are verifiable by reading the document. AC-6 (syntactically correct Python) could be tested by extracting code blocks and running `py_compile`.

**Issues**:

18. **[Minor] AC-6 says "Python 3.11+" but no story or the epic specifies the project's Python version** -- The project has no `pyproject.toml`, no `.python-version`, no `Pipfile`. An implementing agent might not know what Python features are safe to use. This is a project-level gap, not specific to E-005-05.

19. **[Minor] "Under 300 lines" is stated in the Technical Approach but is not an AC** -- If this is a real constraint, it should be an AC. If it is guidance, leave it in the approach section (current state is fine, just noting).

20. **[Minor] Definition of Done includes "A second reader (or agent) can follow the guide to implement a new integration without asking clarifying questions"** -- This is not mechanically verifiable. It is aspirational. Consider removing or reframing as "the guide contains a complete code example that compiles and runs against a mocked endpoint."

---

## Cross-Story Issues

### 21. [Blocking] Python package structure not addressed by any story

All stories reference imports like `from src.http.headers import BROWSER_HEADERS` and `from src.http.session import create_session`. For these imports to work, one of the following must be true:
- `src/` has an `__init__.py` (making it a package) AND the project root is on `sys.path`
- A `pyproject.toml` exists with a package install (`pip install -e .`)
- `PYTHONPATH` is set to include the project root

E-005-01 creates `src/http/__init__.py` but not `src/__init__.py`. No story creates `pyproject.toml`. No story mentions `PYTHONPATH` configuration. **All imports will fail at runtime and in tests.**

**Fix**: Add an AC to E-005-01 (or a new story E-005-00) to establish the Python package structure: create `src/__init__.py` and either a `pyproject.toml` or a note about `PYTHONPATH`.

### 22. [Important] File path consistency -- tests directory

E-005-01 creates `tests/test_http_headers.py`. E-005-02 creates `tests/test_http_session.py`. E-005-04 creates `tests/test_http_discipline.py`. But `tests/` does not exist, and no story mentions creating `tests/__init__.py` or a `conftest.py`. The `tests/` directory needs to exist. Minor, but an implementing agent for E-005-01 (first story) should know to create it.

### 23. [Important] Import path consistency is correct across stories

- E-005-02 imports from `src.http.headers` (consistent with E-005-01's output path)
- E-005-03 imports from `src.http.session` (consistent with E-005-02's output path)
- E-005-04 imports from both (consistent)
- **No issues here** -- paths are consistent, assuming the package structure issue (#21) is resolved.

### 24. [Important] Test overlap between E-005-02 and E-005-04 is significant

As detailed in issue #15, E-005-02 and E-005-04 test nearly identical behavior at the same level of abstraction (both use `create_session()` with mocked HTTP). The stories frame them as "unit" vs "integration" but the actual test implementations are indistinguishable. This will result in ~50% duplicate test code.

### 25. [Minor] No story creates a `conftest.py` with shared test fixtures

Multiple stories will need:
- A mocked HTTP transport or `respx` setup
- A `caplog` pattern for log safety checks
- Timing measurement utilities

These could be shared in `tests/conftest.py`. No story mentions this. An implementing agent will likely duplicate setup code across test files.

### 26. [Important] E-005-03 dependency on E-001-02 creates a cross-epic sequencing problem

E-005 is `ACTIVE` and E-001 is `ACTIVE`, but E-001-02 is `TODO`. E-005-01, E-005-02, E-005-04, and E-005-05 can all proceed without E-001-02. Only E-005-03 is blocked. This is correctly modeled in the dependency chain, but the epic's story table does not make it visually clear that E-005-03 has an EXTERNAL dependency. The epic table shows `E-001-02` in the dependencies column, which is correct, but the epic should note the risk: "E-005-03 is blocked by work outside this epic."

---

## Epic-Level Issues

### 27. [Important] Non-goals list may need updating given E-009

The epic lists "Async session support -- sync first; async can come later if E-002 needs it" as a non-goal. E-009 (Tech Stack Redesign) is `ACTIVE` and evaluating Docker Compose as a deployment model. If the stack moves to Docker + a standard web framework, async may become relevant sooner. The non-goal is still valid for E-005's scope, but the language could acknowledge the E-009 context: "Async session support -- sync first; E-009 stack decision may inform future async work."

Additionally, the non-goal "Playwright or Selenium browser automation" remains accurate -- E-005 is Python httpx only.

### 28. [Minor] Success criteria coverage

The epic's success criteria map well to stories:
- `create_session()` factory -- E-005-02
- `BROWSER_HEADERS` export -- E-005-01
- `pytest tests/test_http_session.py` passes -- E-005-02 + E-005-04
- `GameChangerClient` uses `create_session()` -- E-005-03
- `docs/http-integration-guide.md` exists -- E-005-05

All criteria are covered. No gaps.

### 29. [Minor] Open questions status

- Chrome version: answered (131) -- can be closed
- Origin/Referer headers: still open -- the epic says "to be confirmed." This is low-risk since headers can be added later, but it should be explicitly tracked or closed with a "not needed until observed" decision.
- Context manager support: answered implicitly by E-005-02 AC-7, but the open question is not marked resolved in the epic.

### 30. [Important] Epic status is `ACTIVE` but no stories are `IN_PROGRESS`

The epic is `ACTIVE` but all 5 stories are `TODO`. Typically `ACTIVE` means at least one story is in progress. This may be intentional (PM set it to ACTIVE for the refinement cycle), but it is worth confirming. If this refinement cycle is what transitions it from DRAFT to READY, the status should be `DRAFT` or `READY`, not `ACTIVE`.

---

## Summary

| Severity | Count | Key Items |
|----------|-------|-----------|
| **Blocking** | 3 | #5 (AC-3 timing too tight), #11 (E-001-02 dependency not ready), #21 (Python package structure missing) |
| **Important** | 10 | #2, #6, #7, #10, #12, #15, #16, #24, #26, #30 |
| **Minor** | 10 | #1, #3, #4, #8, #9, #13, #14, #17, #18, #19, #20 |

### Top 5 Recommendations (Prioritized)

1. **Resolve the Python package structure** (#21) -- Add `src/__init__.py` and either a `pyproject.toml` or documented `PYTHONPATH` setup to E-005-01's scope. Without this, nothing imports.

2. **Fix the timing AC in E-005-02** (#5) -- Change AC-3's upper bound from 1500ms to include execution overhead (e.g., 2000ms), or align with the Notes section's 1.6s buffer.

3. **Clarify the E-005-02 / E-005-04 test boundary** (#15, #24) -- Either make E-005-04 purely about GameChangerClient integration (requiring E-005-03), or explicitly state that the overlap is intentional. Current framing will confuse implementing agents.

4. **Add an AC for `Accept-Encoding` value in E-005-01** (#2) -- The `zstd` inclusion matters and is called out in Notes but not enforced by any AC.

5. **Address the E-001-02 delay default conflict** (#12) -- E-005-03 AC-4 changes the default from 500ms to 1000ms, which contradicts E-001-02 AC-6. State explicitly which takes precedence.
