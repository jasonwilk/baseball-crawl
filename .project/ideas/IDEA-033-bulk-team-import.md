# IDEA-033: Bulk Team Import from /me/teams

## Status
`CANDIDATE`

## Summary
Batch-onboard all teams from the authenticated user's GC account via the `/me/teams` endpoint. Currently teams are added one at a time through the admin UI's add-team flow (paste URL → confirm).

## Why It Matters
The operator's GC account has 19 teams. Adding them one at a time is tedious. A bulk import would let the operator onboard all teams in one operation, then classify membership and programs afterward.

## Rough Timing
After E-100 cleanup and the add-team flow is stable. Promote when:
- The operator is ready for initial bulk onboarding
- Adding teams one-by-one becomes a pain point

## Dependencies & Blockers
- [x] E-100 (team model with membership_type) — DONE
- [ ] `/me/teams` endpoint must be documented (returns all teams the user follows/manages)
- [ ] Admin UI edit page must support batch program/membership assignment (or operator is OK doing it per-team)

## Open Questions
- Does `/me/teams` return all followed AND managed teams, or only managed?
- How to auto-classify membership? Default all to `tracked`, let operator mark `member` teams manually?
- Should this be a CLI command (`bb data import-teams`) or an admin UI feature?

## Notes
- E-100 Non-Goal: "Bulk import from /me/teams: Batch onboarding of all 19 teams. Deferred."
- The endpoint exists but hasn't been fully documented yet.

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
