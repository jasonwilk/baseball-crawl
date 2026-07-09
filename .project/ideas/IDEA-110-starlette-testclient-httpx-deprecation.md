# IDEA-110: Resolve the httpx/starlette.testclient deprecation warning from the upgraded stack

## Status
`CANDIDATE`

## Summary
The coordinated fastapi/starlette upgrade in E-256 (fastapi 0.139.0 + starlette 1.3.1) introduces a `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated`. The tests still pass (SE verified `3849 passed, RC=0` on the upgraded stack), but the deprecation signals a future-breaking change in how the test client is constructed. Resolve it before a later starlette bump turns the warning into a hard failure.

## Why It Matters
Deprecation warnings are early notice of a contract that will break. The project's test suite depends on the starlette/httpx TestClient; leaving the warning unaddressed means a future routine dependency refresh could turn red with no warning budget spent. Cheap to fix now, potentially disruptive to diagnose later under a red suite.

## Rough Timing
Promote at the next dependency-refresh cycle, or sooner if a starlette bump is planned. No urgency while the warning is non-fatal.

## Dependencies & Blockers
- [ ] E-256 story 07 (the dependency refresh that surfaces the warning) should land first.

## Open Questions
- Is the fix a TestClient construction change, an httpx-version pin, or a starlette test-utility migration?
- Does it touch conftest/fixtures broadly or only the report/API test files?

## Notes
Surfaced by software-engineer during E-256 planning (2026-07-09) while validating the upgraded stack. Captured out of E-256 scope (E-256 remediates the CVE pins; this is a non-fatal warning). Domain: software-engineer.

---
Created: 2026-07-09
Last reviewed: 2026-07-09
Review by: 2026-10-07
