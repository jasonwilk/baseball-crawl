# IDEA-032: Multi-Credential per Program

## Status
`CANDIDATE`

## Summary
Support different GameChanger credentials for different programs (e.g., one GC account for HS teams, another for USSSA teams). Currently the system uses a single set of credentials for all API access.

## Why It Matters
The operator manages teams across multiple GC accounts (HS, USSSA, Legion). Some authenticated API calls may only work with the credential that owns/follows the target team. Multi-credential support would allow the system to use the right credential for each program's API calls.

## Rough Timing
Low urgency. The current single-credential approach works if the operator's primary GC account follows all teams. Promote when:
- The operator hits an API access error because the active credential doesn't have access to a team in a different program
- A second GC account is actually needed for a specific program

## Dependencies & Blockers
- [ ] Confirm the problem is real: does a single GC account have access to teams across all programs?
- [ ] Auth module (E-077 from IDEA-015) may need to support credential sets

## Open Questions
- Does a single GC account follow teams across HS, USSSA, and Legion? If yes, this idea may never be needed.
- How would credentials be associated with programs? Per-program env vars? A credentials table?
- Would this require changes to the HTTP session layer (`src/http/session.py`)?

## Notes
- E-100 Non-Goal: "Multi-credential per program: Different GC accounts for HS vs USSSA programs. Deferred."
- May never be needed if a single account has sufficient access.

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
