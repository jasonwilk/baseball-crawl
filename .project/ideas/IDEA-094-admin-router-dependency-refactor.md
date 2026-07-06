# IDEA-094: Router-level admin dependency for the admin router (defense-in-depth)

## Status
`CANDIDATE`

## Summary
Admin authorization on `src/api/routes/reports_admin.py` is opt-in per route: every handler individually calls `_require_admin` and returns its `Response` on denial. E-254-05 adds a sweep test that fails closed if a future route ships without the gate — but the structural fix is to attach the admin check as a router-level dependency (FastAPI `dependencies=[Depends(require_admin)]` on the router / a sub-router) so a new admin route is gated by construction, not by remembering to add the call.

## Why It Matters
Per-route opt-in is a standing footgun: the sweep test catches an unguarded route in CI, but a router-level dependency prevents the unguarded route from existing at all. Defense-in-depth — the test and the structural guard reinforce each other.

## Rough Timing
After E-254-05 establishes the sweep test. Promote when the admin surface grows (more admin routes) or during a broader auth-hardening pass.

## Dependencies & Blockers
- [ ] E-254-05 (admin sweep test) complete — establishes the behavioral safety net this refactor would complement.
- [ ] Confirm the `_require_admin` return-shape (redirect for unauth, 403 for non-admin) maps cleanly onto a FastAPI dependency that raises `HTTPException` vs. returns a `Response`.

## Open Questions
- FastAPI dependencies signal denial by raising `HTTPException`; the current `_require_admin` returns a `Response` (302/403). Reconciling the two shapes (raise vs. return) is the main design question.
- Does the 302-redirect-to-login-for-unauth behavior survive a dependency-based approach, or does it become a 401/403?

## Notes
Surfaced by software-engineer during E-254 consultation as a defense-in-depth follow-up to the E-254-05 sweep test (E-254 TN-9). Deliberately kept OUT of E-254 scope.

---
Created: 2026-07-06
Last reviewed: 2026-07-06
Review by: 2026-10-04
