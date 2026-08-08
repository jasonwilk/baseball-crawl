# IDEA-109: Retarget scripts/smoke_test.py at the endpoints the reports product actually uses

## Status
`CANDIDATE`

## Summary
`scripts/smoke_test.py` proves credential liveness by probing three GameChanger endpoints — `/me/teams`, `/teams/{id}/game-summaries`, `/teams/{id}/players` — all of which are **member-team endpoints the reports product abandoned in E-239**. It verifies liveness against a surface nobody uses. Retarget it at the endpoints the reports flow actually depends on (public team/schedule/roster + the authenticated boxscore/plays it fetches per game), so a green smoke means "the reports pipeline's real dependencies are reachable," not "a retired member surface answers."

## Why It Matters
The operator relies on `smoke_test.py` (and `bb creds check`) to distinguish live credentials from expired ones during incident recovery (`docs/admin/operations.md:884`). If the probed endpoints are ones the product no longer touches, the smoke can pass while the reports flow's real dependency is broken, or fail on a surface whose failure is irrelevant. `bb creds check` already proves basic liveness via a real authenticated `/me/user` call, so `smoke_test.py`'s value is specifically end-to-end coverage of the reports dependency chain — which it does not currently provide.

## Rough Timing
Promote as a small operator-tooling follow-up. No urgency; E-256 keeps `smoke_test.py` as-is and records the keep-not-delete verdict, so nothing is broken — this is a fidelity improvement. Escalate if an incident is ever misdiagnosed because the smoke probed the wrong surface.

## Dependencies & Blockers
- [ ] None hard. E-256 (which decided to keep, not delete, the script) should land first so this builds on the retained file.

## Open Questions
- Which authenticated endpoints does the reports flow actually require (the per-game boxscore + plays), and do any need credentials that a smoke can exercise without a full report generation?
- Should the retargeted smoke overlap `bb creds check`'s `/me/user` probe or replace it?
- Does retargeting change its role in the `operations.md:884` recovery recipe (relates to IDEA-111)?

## Notes
Surfaced by software-engineer during E-256 planning (2026-07-09). The E-239 descope retired the member-sync surface; `smoke_test.py` was never updated. E-256 explicitly scoped this OUT (two epics, not three) and captured it here instead. Domain: software-engineer. Anchors: `scripts/smoke_test.py`, `src/gamechanger/credentials.py:175` (`bb creds check` → `/me/user`), `docs/admin/operations.md:884`.

---
Created: 2026-07-09
Last reviewed: 2026-07-09
Review by: 2026-10-07
