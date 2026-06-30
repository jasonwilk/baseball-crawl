# E-248-01: Pin per-status characterization tests for the 4 live verbs

## Epic
[E-248: GC API Client Error-Ladder Refactor](epic.md)

## Status
`DONE`

## Description
After this story is complete, each of the 4 LIVE GC API client verbs (`get`, `get_public`, `get_paginated`, `post_json`) will have characterization tests pinning its actual per-status contract, and those tests will pass against the current un-refactored client. This is the prerequisite that lets the E-248-02 refactor prove it preserves behavior with no assertion changes.

## Context
The H5 finding gates the client error-ladder refactor behind per-status test coverage because every crawl flows through this client. Under the resolved Option-A scope (see epic Background), the dead verbs `post()`/`delete()` are deleted by E-246-07 (which dispatches first), so this story covers ONLY the 4 live verbs. There is **no behavior change** in E-248 — the only 5xx gap was in the now-deleted `post()` — so these tests pin the existing behavior and must keep passing unchanged after the refactor.

The verbs' contracts differ, so the tests are NOT a single uniform set (per epic Technical Notes "Per-verb status matrix"):
- `get` / `get_paginated` / `post_json`: full ladder — 401-refresh-and-retry / 403 / 429 retry-after / 5xx backoff / unexpected-status raise.
- `get_public`: NO auth path — 200 / 429 / 5xx backoff / unexpected only.

Anchor the tests on these PUBLIC verbs' contracts, NOT on the private `_get_with_retries()` helper (Codex P2: `_get_with_retries` is a private seam called only by `get()` and the refactor will reshape it — pinning tests to it by name pins the wrong thing).

## Acceptance Criteria
- [ ] **AC-1**: Given each of the 4 live public verbs, when it receives each status in its own contract (mocked) — `get`/`get_paginated`/`post_json`: 401-refresh-retry, 403, 429 retry-after, 5xx backoff, unexpected-raise; `get_public`: 200, 429, 5xx backoff, unexpected-raise (no 401 path) — then a test asserts that verb's handling for each applicable status.
- [ ] **AC-2**: Given the tests, when they run against the current un-refactored client, then all the new characterization tests pass (they characterize existing behavior accurately).
- [ ] **AC-3**: Given the tests are anchored on the public verbs (`get`, `get_public`, `get_paginated`, `post_json`), when the suite is written, then no test asserts behavior by calling the private `_get_with_retries()` by name — the contract is pinned at the public surface that survives the refactor.
- [ ] **AC-4**: Given the tests use mocked HTTP responses, when they run, then they make no real network calls and do not require credentials.
- [ ] **AC-5**: Given E-246-07 deletes `post()`/`delete()` first, when this story is written, then it does NOT add or retain coverage for `post()`/`delete()` (those and their old tests are removed by E-246-07).

## Technical Approach
Verified locations (re-confirm before acting): live verbs at `src/gamechanger/client.py:233` (`get_paginated`), `:389` (`get`), `:426` (`get_public`), `:611` (`post_json`). Read each verb's current status handling and write characterization tests covering its real matrix (see Context). Mock the transport so no real requests are made. Follow the existing patterns in `tests/test_client.py` and the HTTP-discipline rule (do not assert on or alter headers/session behavior beyond what the error ladder needs). This story depends on E-246-07 having removed `post()`/`delete()` — coordinate so this suite covers only survivors.

## Dependencies
- **Blocked by**: None within E-248. (Cross-epic: assumes E-246-07's dead-verb deletion has landed — E-246 dispatches before E-248; see epic Technical Notes "Cross-epic ordering".)
- **Blocks**: E-248-02

## Files to Create or Modify
- `tests/test_client.py` (extend — add the per-verb characterization tests for the 4 live verbs; file exists today)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-248-02**: The per-verb characterization suite that the refactor must keep green with NO assertion changes (any required assertion change means the refactor altered behavior and is not shippable).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] New characterization tests pass against the current un-refactored client
- [ ] Tests anchor on the 4 public live verbs, not `_get_with_retries`
- [ ] Tests make no real network calls
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Test-only story (the prerequisite gate). It must complete and the tests must pass before E-248-02 begins. Covers only the 4 live verbs — `post()`/`delete()` are removed by E-246-07.
