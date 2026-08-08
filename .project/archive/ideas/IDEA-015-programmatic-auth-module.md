# IDEA-015: Programmatic Auth Module

## Status
`PROMOTED` -- promoted to E-077 (scoped to token refresh + client integration; full login flow and bb creds refresh migration deferred)

## Summary
Build a productionized Python module that implements the full GameChanger auth flow programmatically: gc-signature HMAC-SHA256 generation, token refresh (POST /auth with type:refresh), full login (4-step flow), auto-refresh in GameChangerClient (detect 401, refresh, retry), and migrate `bb creds refresh` from manual curl-paste to programmatic refresh.

## Why It Matters
The auth architecture is fully documented (three-token, gc-signature HMAC-SHA256, programmatic refresh confirmed working via manual testing), but no productionized Python module implements it. The current workflow requires manual curl-paste via `bb creds refresh`. This is acceptable for occasional operator use but becomes a hard blocker when crawl scheduling (IDEA-012) is promoted -- automated crawls cannot stop and wait for a human to paste a curl command.

Secondary benefit: improved error messages in client.py and credentials.py, which currently reference the manual workflow.

## Rough Timing
- **Hard trigger**: When IDEA-012 (crawl scheduling) is promoted, this becomes a blocking dependency -- automated crawls need automatic token refresh.
- **Soft trigger**: Quality-of-life improvement anytime the operator tires of the manual curl-paste workflow.
- **Sequencing**: E-075 (mobile credential capture and validation) should complete first to stabilize the credential model. Auth handling script refresh should also precede this work.

## Dependencies & Blockers
- [x] Auth architecture documented (three-token, gc-signature, refresh flow) -- done, see `docs/api/auth.md`
- [x] gc-signature algorithm reverse-engineered and confirmed working -- done (2026-03-07)
- [ ] E-075 (mobile credential capture and validation) -- should complete first to stabilize credential env var naming and validation
- [ ] Auth handling scripts refreshed -- user plans to do this before promoting this idea

## Open Questions
- Should the gc-signature module live in `src/gamechanger/` or `src/http/`? It is GC-specific but is an HTTP-layer concern.
- Should auto-refresh be opt-in (explicit flag on GameChangerClient) or always-on? Always-on is simpler but could mask credential problems.
- Does the full 4-step login flow need to be in the initial scope, or is token refresh (which only needs the refresh token + client credentials) sufficient for IDEA-012's needs?
- How should refresh token rotation be handled? Each refresh call returns a new refresh token -- the module needs to persist the updated token back to `.env` or a credential store.

## Notes
- The gc-signature algorithm is HMAC-SHA256 using the client_key as the signing secret. Full details in `docs/api/auth.md`.
- The refresh token is self-renewing (each refresh call returns a new refresh token with a fresh 14-day TTL).
- Related: IDEA-012 (crawl scheduling) is the primary downstream consumer of this capability.
- Scope pieces identified during investigation:
  1. gc-signature HMAC-SHA256 generation module
  2. Programmatic token refresh (POST /auth with type:refresh)
  3. Full programmatic login (4-step flow)
  4. Auto-refresh in GameChangerClient (detect 401, refresh, retry)
  5. `bb creds refresh` using programmatic refresh instead of curl paste
  6. Updated error messages in client.py and credentials.py

---
Created: 2026-03-08
Last reviewed: 2026-03-08
Review by: 2026-06-06
