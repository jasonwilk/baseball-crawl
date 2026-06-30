# E-246-07: Delete dead GameChangerClient verbs (post, delete)

## Epic
[E-246: Dead-Code Removal & Low-Risk Consolidation](epic.md)

## Status
`TODO`

## Description
After this story is complete, the two dead public verbs on the GameChanger API client — `GameChangerClient.post()` (`client.py:722`) and `GameChangerClient.delete()` (`client.py:794`) — and their tests will be removed. Both have zero production callers; their only historical caller was the follow/unfollow path removed in E-239 (now banned). This is a pure dead-code deletion that shrinks E-248's refactor surface from 6 verbs to 4 and dissolves its 5xx-gap behavior change.

## Context
This story was added during Codex spec-review triage, when api-scout (gc-uuid-bridge owner) verified by grep that `post()` and `delete()` are dead: zero call sites in `src/`/`scripts/`, exercised only by `tests/test_client.py`. Their sole historical caller was the follow→bridge→unfollow path removed in E-239 and now BANNED per `.claude/rules/gc-uuid-bridge.md`. The user delegated the scope fork to PM, who chose **Option A** (delete) over folding them into E-248's ladder refactor — simple-first, and the cleanup epic's domain is exactly dead-code removal.

Important disambiguation: this story deletes the two PUBLIC verb methods only. It does NOT touch:
- `post_json()` (`client.py:611`) — the LIVE POST verb (`/search` traffic), which stays.
- the FastAPI `@router.post(...)` route decorators in `src/api/routes/`.
- the raw `client.post(...)` calls in `token_manager.py`, `credentials.py`, `llm/openrouter.py`, `api/email.py` — those are separate httpx/requests clients, not `GameChangerClient`.
- the internal `self._session.post`/`self._session.delete` lines that live INSIDE `post_json`/`get` etc. (only the ones inside the deleted `post()`/`delete()` bodies go away with them).

## Acceptance Criteria
- [ ] **AC-1**: Given the verbs are claimed dead, when the implementer greps `src/` and `scripts/` for any invocation of `GameChangerClient.post(` / `.delete(` (the public verbs), then it confirms zero production callers — distinguishing them from `post_json`, the `@router.post` decorators, the raw `client.post` in other modules, and the internal `_session.post`/`_session.delete`. The grep result is recorded in the completion report.
- [ ] **AC-2**: Given zero production callers are confirmed, when the story completes, then `GameChangerClient.post()` (`client.py:722`) and `GameChangerClient.delete()` (`client.py:794`) are deleted in full, and `post_json`, `get`, `get_public`, `get_paginated`, `_get_with_retries` are left untouched.
- [ ] **AC-3**: Given the verbs had dedicated tests, when the story completes, then the `post()`/`delete()` tests in `tests/test_client.py` are deleted — including `test_delete_unexpected_status_raises_api_error` (`tests/test_client.py:1830-1838`) and any `post()`-verb tests — and no surviving test references the deleted verbs (grep-confirmed).
- [ ] **AC-4**: Given the deletions, when `tests/test_client.py` runs, then it passes (no test referenced the deleted verbs). The full-suite-green check across `tests/` is the epic-level closure gate, not a per-story AC.

## Technical Approach
Verified locations (re-confirm before acting via fresh grep — this is a deletion, so the E-246 deletion discipline applies): `src/gamechanger/client.py:722` (`post`, body uses `_session.post` at `:748`/`:757`), `:794` (`delete`, body uses `_session.delete` at `:821`/`:830`); stale test at `tests/test_client.py:1830-1838`. Delete the whole methods and their tests. Confirm zero `GameChangerClient.post(`/`.delete(` callers across `src/` and `scripts/` before deleting.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-248 (cross-epic — E-248 refactors the surviving 4 verbs in the same `client.py`; E-246 must dispatch before E-248 so the dead verbs are gone first; see E-248 Technical Notes "Cross-epic ordering")

## Files to Create or Modify
- `src/gamechanger/client.py` (delete `post()` and `delete()` methods)
- `tests/test_client.py` (delete the `post()`/`delete()` tests, incl. `:1830-1838`)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-248-01/02**: A client with only the 4 live verbs (`get`, `get_public`, `get_paginated`, `post_json`), so E-248's characterization tests and ladder extraction cover only survivors.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Fresh-grep zero-caller confirmation recorded in completion report
- [ ] `post_json` and the GET verbs untouched
- [ ] No surviving test references the deleted verbs (grep-confirmed)
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Pure dead-code deletion (zero stat surface — these verbs are never called in the collection path). api-scout's dead-verb finding is recorded in the E-248 epic Background. git history retains the deleted code if a future need arises.
