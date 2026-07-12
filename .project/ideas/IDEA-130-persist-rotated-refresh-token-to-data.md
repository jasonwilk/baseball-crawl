# IDEA-130: Persist Rotated GC Refresh Token Beyond Container-Local .env

## Status
`CANDIDATE`

## Summary
When the GameChanger auth module rotates a refresh token, it persists the new token only to the container-local `.env`. Also persist it to the host-mounted `./data` directory so a container rebuild does not lose a live rotated token.

## Why It Matters
The refresh token is the long-lived credential that lets the system re-mint access tokens without an interactive login. If it rotates (GC issues a new refresh token on refresh) and that new value lands only in the container-local `.env`, a `docker compose up --build` / container rebuild wipes it — forcing a fresh interactive `bb creds setup web`. Persisting the rotated value to `./data` (already host-mounted, already the durable-state location for `app.db`) is cheap insurance against that avoidable re-auth.

## Rough Timing
Low urgency — a lost refresh token is recoverable via interactive re-auth, so this is convenience/resilience, not correctness. Promote if container rebuilds start costing real re-auth friction, or alongside any broader credential-durability work.

## Dependencies & Blockers
- [ ] Confirm where the auth module writes rotated tokens today and whether a second durable sink is clean to add.
- [ ] PII/secret posture: `./data` is host-mounted and gitignored; the token must never leave that boundary (no logging, no commit) — same discipline as `.env`.

## Open Questions
- Should `./data` become the authoritative source on startup (read-through), or just a backup that seeds `.env` when `.env` lacks a token?
- Interaction with the profile-scoped credential model (`_WEB` / `_MOBILE`) — one durable file per profile?
- Does this overlap IDEA-023 (env + db backup automation)? Reconcile rather than duplicate if promoted.

## Notes
Source: PLATFORM-AUDIT residual #11 (WATCH). Related: IDEA-023 (automated `.env` + `app.db` backup) covers a broader backup surface; this is the narrow "don't lose a live rotated token on rebuild" slice.

---
Created: 2026-07-12
Last reviewed: 2026-07-12
Review by: 2026-10-10
