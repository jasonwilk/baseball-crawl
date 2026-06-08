# E-232-02: Silence pytest-asyncio Loop-Scope Deprecation via Config

## Epic
[E-232: Clear the Test-Suite Deprecation Warning Surface (Starlette + pytest-asyncio)](../E-232-starlette-deprecation-migration/epic.md)

## Status
`DONE`

## Description
After this story is complete, `pyproject.toml` declares an explicit `asyncio_default_fixture_loop_scope` under `[tool.pytest.ini_options]`, silencing the pytest-asyncio `PytestDeprecationWarning` about that option being unset. This is a config-only, single-line change with no behavior impact.

## Context
This is the third warning family found during E-232 discovery (beyond the idea's original two) and is NOT a Starlette warning — it comes from pytest-asyncio 0.25.0, which warns when `asyncio_default_fixture_loop_scope` is unset. No asyncio config exists in `pyproject.toml` today (the `[tool.pytest.ini_options]` table at line 31 contains only `timeout = 30`). Folding it into this epic matches the "clean the warning surface" goal and is trivial. This story is independent of E-232-01 — different file, different warning family, no overlap.

## Acceptance Criteria
- [ ] **AC-1 (authoritative)**: Given `pyproject.toml`, when this story is complete, then `[tool.pytest.ini_options]` declares `asyncio_default_fixture_loop_scope` set to the conventional default (per epic Technical Notes "pytest-asyncio config"), with the existing `timeout = 30` setting preserved. This is the authoritative, unconditional verification for this story.
- [ ] **AC-2**: Given this story's change, when a pytest run is performed with the config applied during dispatch, then it reports 0 failed (no regressions). Full-suite-green (`python -m pytest tests/` in the main checkout, 0 failed) is asserted at epic closure per the Full-Suite-Green Closure Gate, not as a per-story acceptance run.

## Technical Approach
Add the single `asyncio_default_fixture_loop_scope` key under the existing `[tool.pytest.ini_options]` table in `pyproject.toml`, using the conventional `"function"` scope described in the epic Technical Notes. This is config-only — no dependency change, no `src/` or `tests/` change. The authoritative verification is the config-key presence (AC-1). As a secondary, best-effort signal, the pytest-asyncio `asyncio_default_fixture_loop_scope`-unset `PytestDeprecationWarning` should no longer appear in a normal suite run after the change; this is not a gate, because the warning only fires under certain async-fixture conditions and its absence does not by itself prove the config is correct.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `pyproject.toml` (modify — add one key under `[tool.pytest.ini_options]`)

## Agent Hint
software-engineer

## Definition of Done
- [ ] `[tool.pytest.ini_options]` in `pyproject.toml` declares `asyncio_default_fixture_loop_scope` (conventional `"function"` scope), with `timeout = 30` preserved (AC-1)
- [ ] No new test code — this is a config-only change (see Notes); verified by config-key presence plus a no-regressions pytest run (AC-2)
- [ ] Config follows project style (see CLAUDE.md)

## Notes
No file overlap with E-232-01, so the two stories are independent and can execute in any order during dispatch. There is no new test code for this story — it is a config change verified by the absence of the warning in a suite run.
