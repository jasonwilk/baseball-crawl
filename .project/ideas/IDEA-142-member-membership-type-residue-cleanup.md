# IDEA-142: Remove the dead `'member'` membership_type residue (E-239 leftover)

## Status
`CANDIDATE`

## Summary
E-239 removed the member-team creation path, but the `'member'` `membership_type` value still has dead code: a never-taken branch in the report generator plus several relic READ paths that check for `'member'`. All 235 live teams are `'tracked'` and nothing can create a `'member'` team anymore, so these are safe-to-remove residue.

## Why It Matters
Dead branches invite wrong reasoning: during E-264 planning, an agent justified a design decision on hypothetical "member team" behavior that cannot occur (SE caught it against the live DB). Removing the residue makes the single-membership reality legible in the code and stops future agents from building logic around a state that no longer exists. This is the same "rip out the de-scoped bones at the root" hygiene the cross-season de-scope needed — leaf code still referencing a removed concept.

## Rough Timing
Low urgency / nice-to-have. A good candidate to fold into a future housekeeping epic (E-262-class) rather than standalone.

## Dependencies & Blockers
- [ ] None hard. Verify once more at promotion time that no INSERT/UPDATE anywhere writes `'member'` (E-239 removed it; confirm still true).

## Open Questions
- Is `membership_type` worth keeping as a column at all if only one value is ever written, or should the whole column go? (Schema-simplification call for data-engineer — a migration if the column is dropped.)
- Removing the `if membership_type == 'member'` resolution branch changes `_resolve_gc_uuid_stage` control flow slightly — confirm the `tracked` path covers every real team (it does today).

## Notes
Surfaced by software-engineer during E-264 formation (2026-07-15), verified against `data/app.db` (`teams` GROUP BY membership_type → tracked|235, member|0). "Member" = ANY operator-managed team (not LSB-specific — includes managed USSSA/Legion teams); confirmed no writer produces `'member'` even for a managed team, because member-team SYNC is fully gone post-E-239 (remaining `/me/teams` calls at `src/http/session.py:36` etc. are non-writing token-health/dev-tooling reads). Report generation stamps every team `'tracked'`. Cited residue locations (verify at promotion — line numbers drift): dead branch `src/reports/generator.py:1988` (`if membership_type == "member"`); relic READ checks in `src/db/teams.py` (~181/193/207 cascade), `src/db/game_merge.py:~692`, `src/api/auth.py:~129`, `src/api/routes/reports_admin.py:~164`. Sole team INSERT (`ensure_team_row_with_provenance`, `src/db/teams.py:224`) hardcodes `'tracked'` and has no membership_type param. Related: E-239 (reports-first descope). Domain: DE/SE.

---
Created: 2026-07-15
Last reviewed: 2026-07-15
Review by: 2026-10-13
