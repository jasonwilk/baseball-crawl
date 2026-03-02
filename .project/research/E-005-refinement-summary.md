# E-005 Refinement Summary

**Date**: 2026-03-02
**Reviewers**: codebase-auditor, story-reviewer, tech-validator (agent team)

---

## Blocking Issues (must fix before dispatch)

### 1. Chrome 131 is 15 major versions behind -- update to Chrome 146

E-005-01 hardcodes Chrome 131 in User-Agent and sec-ch-ua. Chrome 146 is the current stable.
All ACs referencing version strings (E-005-01 AC-2, AC-3) and the epic's Technical Notes must
be updated. The sec-ch-ua GREASE brand string changes per major version -- the implementing
agent should capture fresh headers from a real Chrome 146 session on macOS.

**Action**: Update epic Technical Notes, E-005-01 ACs, to reference Chrome 146. Add a note
that the implementing agent must capture real headers rather than guessing the GREASE string.

### 2. Python package structure missing -- no story creates it

All stories use `from src.http.headers import BROWSER_HEADERS` but no story creates
`src/__init__.py` or a `pyproject.toml`. Zero application code exists in the repo -- no `src/`,
no `tests/`, no dependency manifest. The first story must establish project scaffolding.

**Action**: Add scaffolding scope to E-005-01: create `src/__init__.py`, `src/http/__init__.py`,
`tests/`, and a minimal `pyproject.toml` with httpx + pytest dependencies.

### 3. E-005-02 AC-3 timing assertion contradicts Notes

AC-3 says "between 1000ms and 1500ms" but `time.sleep()` overshoots on any OS. Notes say
1.6s upper bound. These contradict.

**Action**: Update AC-3 to "at least 1000ms" with a note that tests should use a generous
upper bound (e.g., 2000ms) to account for OS scheduling jitter.

### 4. E-005-03 premise is invalid -- nothing to retrofit

E-001-02 (`src/gamechanger/client.py`) is `TODO`, never started. There is no client to
retrofit. The epic's own Technical Notes anticipated this scenario and suggest E-005-03
becomes a no-op if E-001-02 is written against `create_session()`.

**Action**: Mark E-005-03 as DEFERRED. When E-001-02 is implemented, it should use
`create_session()` directly, making E-005-03 unnecessary. If E-001-02 is written without
it, E-005-03 can be revived.

---

## Important Issues (should fix for quality)

### 5. E-005-02 / E-005-04 test overlap is ~50%

Both stories test `create_session()` with mocked HTTP at the same abstraction level. The
only genuine integration test in E-005-04 (AC-6, testing GameChangerClient) is conditional
on E-005-03.

**Action**: Merge E-005-04 into E-005-02 (add the discipline integration ACs to E-005-02's
test file) OR redefine E-005-04 as solely the GameChangerClient integration test (blocked
by E-005-03). Given E-005-03 is being deferred, recommend merging E-005-04 into E-005-02.

### 6. No AC enforces Accept-Encoding includes zstd

Notes call it out but no AC checks it. An implementer could omit `zstd` and pass all ACs.

**Action**: Add an AC to E-005-01 checking that `Accept-Encoding` contains `zstd`.

### 7. Log safety check narrower than epic's rule

E-005-02 AC-5 checks only `Authorization`/`Bearer`/`Cookie` but the epic's Logging Safety
Rule says "any header value" must not be logged.

**Action**: Broaden AC-5 to state that no log record at any level contains any header value
from BROWSER_HEADERS or any injected credential string.

### 8. Epic status should be READY, not ACTIVE

Epic is `ACTIVE` but all stories are `TODO`. `ACTIVE` implies work is underway. After this
refinement, the correct status is `READY` (refined, dispatchable).

**Action**: Change epic status to `READY` after applying refinement changes.

---

## Minor Issues (nice to have)

- E-005-01 AC-6 (docstring content) is subjective -- consider moving to DoD
- E-005-02: no AC covers `min_delay_ms=0` behavior (should it be allowed?)
- No story creates `tests/conftest.py` for shared fixtures
- E-005-05 "under 300 lines" guidance is not an AC
- Python version not specified anywhere in the project
- Open questions in epic not formally closed
- Async caveat should be noted in epic (sync is correct, but flag future scenario)

---

## Recommended Story Changes

| Story | Recommendation |
|-------|---------------|
| E-005-01 | Add scaffolding scope (src/__init__.py, pyproject.toml, tests/). Update Chrome 131 → 146. Add Accept-Encoding zstd AC. |
| E-005-02 | Fix AC-3 timing bounds. Broaden AC-5 log safety. Absorb E-005-04's non-conditional ACs. |
| E-005-03 | Mark DEFERRED -- no client exists to retrofit. Revive only if E-001-02 ships without create_session(). |
| E-005-04 | Mark ABANDONED -- merge into E-005-02. The conditional AC-6 moves to a future story when E-005-03 is relevant. |
| E-005-05 | No changes needed. Viable as written. |

## Verdict

**After applying the changes above, E-005 is ready for dispatch.** Stories E-005-01, E-005-02,
and E-005-05 form a clean, independent chain. E-005-01 has no blockers. E-005-02 depends on
E-005-01. E-005-05 depends on E-005-02. The cross-epic dependency on E-001-02 is isolated to
E-005-03 (deferred) and does not block the core work.
