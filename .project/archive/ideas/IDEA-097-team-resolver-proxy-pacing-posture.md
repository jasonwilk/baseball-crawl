# IDEA-097: team_resolver public calls should adopt the proxy/pacing HTTP posture

## Status
`CANDIDATE`

## Summary
`resolve_team` and `discover_opponents` in `src/gamechanger/team_resolver.py` call the public GameChanger endpoints with `proxy_url=None` and `min_delay_ms=0`, bypassing the Bright Data proxy + request-pacing posture that `.claude/rules/http-discipline.md` wants for all GC requests (presenting as a normal browser). E-252-09 hardened these calls' *exception contract* (catch the whole `httpx.RequestError` family) but deliberately left the proxy/pacing posture unchanged. This idea is the posture half.

## Why It Matters
Every GC request should present as a normal browser and respect pacing/backoff to avoid pattern-detection or rate-limiting (the same discipline the shared client enforces). These resolver calls fire during opponent display-profile resolution on the morning-run and `map-opponent` paths — an unpaced, un-proxied burst here is an HTTP-discipline gap that could, over time, get the IP flagged. Low severity today (few calls, unobserved GC 429s), but it is a real inconsistency with the project's stated HTTP posture.

## Rough Timing
Someday / low urgency. Promote if: GC ever returns a real 429 (the UNOBSERVED caveat clears and pacing becomes load-bearing), OR if a broader HTTP-discipline sweep is undertaken, OR if resolver call volume grows.

## Dependencies & Blockers
- [ ] api-scout should own the posture decision (proxy routing + pacing values) — this is HTTP-discipline domain, not a mechanical change.
- [ ] Confirm the public endpoints tolerate the Bright Data proxy (some public paths may behave differently than authenticated ones).

## Open Questions
- Should the public resolver calls route through the same shared client/session that already carries the proxy + pacing, rather than their own bare `session.get`?
- What pacing (`min_delay_ms`) is appropriate for these low-volume resolution calls without slowing the morning run materially?

## Notes
Deferred out of E-252-09's required scope (the story fixed only the ConnectError exception contract). Anchor: `src/gamechanger/team_resolver.py` (`resolve_team`, `discover_opponents`). Domain owner: api-scout. See `.claude/rules/http-discipline.md`. Surfaced during the E-252 dispatch (Phase 4b) as one of three closure follow-up candidates (with [[IDEA-098-unify-prod-detection-is-production]] and [[IDEA-099-busy-timeout-non-triad-writers]]).

---
Created: 2026-07-06
Last reviewed: 2026-07-06
Review by: 2026-10-04
