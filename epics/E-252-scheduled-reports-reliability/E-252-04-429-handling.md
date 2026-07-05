# E-252-04: Cap Retry-After on 429 + isolate RateLimitError in the scouting crawl

## Epic
[E-252: Scheduled-Reports Reliability (Cron-Grade Morning-Run)](../E-252-scheduled-reports-reliability/epic.md)

## Status
`TODO`

## Description
After this story is complete, a `Retry-After: 3600` on an HTTP 429 can no longer stall the cron for a server-controlled hour and then abort: the client caps the wait, retries once within the cap or raises immediately over the cap, and a 429 on a single opponent's boxscore fetch is isolated so it does not abort the whole team's crawl.

## Context
Two coupled defects (Technical Notes TN-6), both designed against **UNOBSERVED** GameChanger 429 behavior (`docs/api/error-handling.md:68` records no 429 ever captured — the story must document this and flag a revisit if a real 429 is captured):

1. **Client-level 429 mishandling** (`src/gamechanger/client.py` `_send_with_retry`, L499-512): `retry_after` is taken straight from the header with no ceiling, then the code sleeps the FULL duration and raises `RateLimitError` unconditionally — the worst of both worlds (stalls AND fails, no retry after the wait). This lives in the SHARED client, so the fix changes behavior for EVERY GameChanger caller, not just morning-run — a deliberate global change the story must call out.

2. **RateLimitError escapes the scouting crawler's per-game isolation** (`src/gamechanger/crawlers/scouting.py`): `RateLimitError` is a standalone `Exception` (a sibling, NOT a subclass, of `CredentialExpiredError`/`ForbiddenError`/`GameChangerAPIError`). Two catch SHAPES omit it: `_fetch_schedule` (:217) and `_fetch_roster` (:238) use a 3-tuple `except (ForbiddenError, CredentialExpiredError, GameChangerAPIError)`; the `_fetch_boxscores_in_memory` per-game loop (:268-281, verified) uses THREE SEPARATE `except` clauses — `except ForbiddenError` (continue), `except CredentialExpiredError` (**re-raises** — a 401 mid-boxscore INTENTIONALLY aborts the team crawl), `except GameChangerAPIError` (continue). In both shapes a 429 escapes and aborts the entire team crawl. (The plays crawl loop at `generator.py:929-931` already catches `except Exception` — a 429 is already isolated there; NO change.)

The 02↔04 boundary (TN-6): this story isolates the PER-GAME boxscore 429 at the crawler. Team-level 429s (schedule/roster) must still surface to morning-run's per-team seam (E-252-02) so the systemic-429 escalation (TN-9) can see recurring 429s — this story must not swallow team-level 429s in a way that blinds that escalation.

## Acceptance Criteria
- [ ] **AC-1** (count-based bound — tests patch `sleep`, so the guard is call-count, not wall-clock): Given an HTTP 429 whose `Retry-After` is within the cap (`<= _MAX_RETRY_AFTER_SECONDS`, 60 per Technical Notes TN-6) that RECURS on the retry (429 on BOTH the initial attempt and the single retry), when the client handles it, then `sleep` is invoked AT MOST ONCE and every `sleep` argument is `<= _MAX_RETRY_AFTER_SECONDS`; the transport `send` is invoked AT MOST TWICE (initial + one retry); then `RateLimitError` is raised. (A within-cap 429 whose retry returns 200 returns that response.) This deterministically pins "no ~180s three-attempt stacking" — an implementation that stacks 3 capped sleeps fails the `sleep`-calls ≤ 1 bound. The retry MECHANISM is specified in Technical Approach, not here.
- [ ] **AC-2** (count-based): Given an HTTP 429 whose `Retry-After` EXCEEDS the cap, when the client handles it, then `sleep` is invoked ZERO times, `send` is invoked ONCE, and `RateLimitError` is raised immediately (no server-controlled stall), per Technical Notes TN-6.
- [ ] **AC-3**: Given an HTTP 429 with an absent or unparseable `Retry-After` header, when the client handles it, then it falls back to `_DEFAULT_RETRY_AFTER_SECONDS` (60) and then clamps to the cap (never sleeps longer than the cap).
- [ ] **AC-4**: `RateLimitError` remains a standalone `Exception` — it is NOT subclassed under `CredentialExpiredError` (a 429 must not be misrouted into auth-refresh / "check .env" handling), per Technical Notes TN-6.
- [ ] **AC-5** (behavioral): Given a team crawl where ONE game's boxscore fetch raises `RateLimitError`, when `_fetch_boxscores_in_memory` processes the games, then that single game is isolated (skipped/recorded) and the remaining games of the team are still crawled (the 429 no longer aborts the whole team crawl), AND the existing behavior for a mid-boxscore `CredentialExpiredError` (401) is preserved — it still aborts the team crawl (re-raises). The catch MECHANISM (a new clause vs a tuple edit) is specified in Technical Approach, not here.
- [ ] **AC-6**: Team-level 429s (a `RateLimitError` from `_fetch_schedule` / `_fetch_roster`, or a client raise-fast) are NOT silently swallowed at the crawler in a way that prevents them reaching morning-run's per-team seam — they propagate so E-252-02's systemic escalation (TN-9) can observe recurring 429s. (The exact catch placement for schedule/roster is the implementer's call under this constraint; verify the boundary against E-252-02.)
- [ ] **AC-7**: The client change is documented in-code as a deliberate GLOBAL change (all GC callers) designed against UNOBSERVED GC 429 behavior, with a revisit note if a real 429 is captured (Technical Notes TN-6 caveat).
- [ ] **AC-8**: Tests (per Technical Notes TN-8, HTTP mocked at the transport layer; patch `sleep` and assert on CALL COUNTS + args, not wall-clock): within-cap recurring 429 → `sleep` called ≤ 1 with arg ≤ cap, `send` called ≤ 2, then raise (AC-1); over-cap 429 → `sleep` called 0, `send` called 1, immediate raise (AC-2); absent/unparseable-header fallback+clamp (AC-3); a single-game boxscore 429 isolated so sibling games still crawl, with the `CredentialExpiredError` re-raise preserved (AC-5). A `Retry-After: 3600` case proves the cap prevents the hour-long stall (over-cap → no sleep).

## Technical Approach
In `_send_with_retry`, add `_MAX_RETRY_AFTER_SECONDS = 60`, clamp the parsed/`_DEFAULT_RETRY_AFTER_SECONDS` value, and replace the sleep-then-raise block with the decided policy: within-cap → sleep(clamped) + INLINE single retry (mirror the 401 branch at `:479`, not a loop `continue`) + return-on-200-else-raise; over-cap → raise immediately without sleeping. Keep `RateLimitError` standalone. In `src/gamechanger/crawlers/scouting.py`, add a NEW `except RateLimitError: continue` clause to `_fetch_boxscores_in_memory`'s three-clause per-game structure (preserving the `except CredentialExpiredError: raise`) so one game's 429 is isolated; for `_fetch_schedule`/`_fetch_roster`, do NOT add `RateLimitError` to their tuple — leave team-level 429s to propagate to E-252-02's per-team seam (TN-6). Do NOT touch `morning_run.py` (that is E-252-02's per-team seam) and do NOT touch the plays loop in `generator.py` (already isolated). Confirm the exception hierarchy against `src/gamechanger/exceptions.py`. Make the sleep patchable so AC-2/AC-8 do not actually sleep.

**Known consequence (api-scout, no behavior change):** `_DEFAULT_RETRY_AFTER_SECONDS` (60) equals the new `_MAX_RETRY_AFTER_SECONDS` (60), so a header-less 429 always takes the within-cap branch and sleeps the full 60s. This is acceptable and coherent; if cheaper header-less 429s are wanted later, set the default below the cap. Noted here to preempt a re-flag.

## Dependencies
- **Blocked by**: E-252-02 (co-design of the 429 isolation seam per Technical Notes TN-6 — the per-team escalation must exist to receive propagated team-level 429s)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/client.py` (`_send_with_retry` 429 block; `_MAX_RETRY_AFTER_SECONDS` constant)
- `src/gamechanger/crawlers/scouting.py` (`_fetch_boxscores_in_memory` per-game loop — new `except RateLimitError: continue` clause, preserving the `CredentialExpiredError` re-raise; schedule/roster :217/:238 left unchanged per AC-6)
- `tests/test_client.py` and/or `tests/test_scouting_crawler.py` (or the existing modules) — the AC-8 tests
- (No change expected) `src/gamechanger/exceptions.py` — `RateLimitError` stays standalone (AC-4)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Audit one-liner (MEDIUM): "429 handling: unbounded server-controlled sleep then raise anyway; `RateLimitError` escapes every per-game isolation — one `Retry-After: 3600` stalls the cron an hour, then aborts the remaining boxscores/run" — `client.py:499/508`, `exceptions.py:41`. api-scout confirmed the escape point is the SCOUTING crawler catch tuples (not the plays loop) and that GC 429 behavior is unobserved.
