# IDEA-056: Fix _search_fallback_team Return Type Bug

## Status
`CANDIDATE`

## Summary
`_search_fallback_team` in the opponent resolver returns bare `0` instead of tuple `(0, 0)` when no unlinked rows remain, causing an unpacking error in `resolve()` that silently inflates error counts by 1 on every resolution cycle.

## Why It Matters
Every opponent resolution run accumulates a phantom +1 error from this bug. While it does not block resolution (the real work completes), it makes error counts unreliable for monitoring and debugging. Discovered during E-179 test alignment -- tests were updated to expect the inflated counts, but the production bug remains.

## Rough Timing
- Low urgency but easy fix -- single return statement correction
- Promote when doing any work in the opponent resolver or when error monitoring becomes important

## Dependencies & Blockers
- [ ] None -- fix is straightforward

## Open Questions
- Is the bare `0` return the only code path with this issue, or are there others in the resolver?

## Notes
- Discovered by SE during E-179-08 (test_opponent_resolver.py assertion fixes)
- E-179 was test-only (TN-3), so the production fix was deferred
- Tests in `tests/test_crawlers/test_opponent_resolver.py` now assert the inflated error counts -- the test fix will need to be reverted when the production bug is fixed

---
Created: 2026-03-29
Last reviewed: 2026-03-29
Review by: 2026-06-27
