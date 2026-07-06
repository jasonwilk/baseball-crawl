# IDEA-095: Constant-time login across all three post_login paths (repeated-probe residual)

## Status
`CANDIDATE`

## Summary
E-254-03 closes the single-probe login-timing enumeration vector by equalizing the FRESH-known and UNKNOWN `post_login` paths (BackgroundTask send + symmetric dummy work, asserted via call-parity). A second-order residual remains: the THIRD path — the rate-limit-suppression branch (a registered email with an unexpired recent token) — does LESS work than both equalized paths, so REPEATED probes of a REGISTERED email show a timing DROP on the 2nd probe while an UNREGISTERED email stays flat. A determined attacker probing the same email twice could distinguish registered from unregistered from that differential.

## Why It Matters
It is the same class of exposure the epic set out to close (login enumeration), just via a repeated-probe rather than single-probe signal. Closing it fully makes the enumeration protection complete rather than single-probe-only.

## Rough Timing
Low urgency — a LOW-severity finding on a single-operator HS app. Promote if the app opens to more users, or if a security review flags login enumeration as material. E-254-03 accepted-and-noted this residual (same disposition class as IDEA-093's token-in-logs residual).

## Dependencies & Blockers
- [ ] E-254-03 (login-timing equalization) shipped — this builds on that.

## Open Questions
- Cheapest fix: run the same dummy equalizing work (hash + dummy user-scoped SELECT) inside the rate-limit-suppression branch too, so all three paths do comparable work. Does that fully flatten the repeated-probe differential, or does the absence of the DELETE+INSERT still leak?
- Is a repeated-probe differential even worth closing for a single-operator app, or is this a permanent WONTFIX?

## Notes
Surfaced by software-engineer during the E-254 Codex spec-review triage (P2-03). Accepted-and-noted in E-254-03 Notes; SE + team-lead agreed not to expand E-254 scope for it. Related: IDEA-093 (magic-link token-in-logs residual, same accept-and-note pattern).

---
Created: 2026-07-06
Last reviewed: 2026-07-06
Review by: 2026-10-04
