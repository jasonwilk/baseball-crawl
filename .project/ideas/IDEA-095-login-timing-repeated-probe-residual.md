# IDEA-095: Constant-time login across all post_login paths (timing-residual family)

## Status
`CANDIDATE`

## Summary
E-254-03 closes the DOMINANT single-probe login-timing enumeration vector by equalizing the FRESH-known and UNKNOWN `post_login` paths — the awaited Mailgun NETWORK send (the large, exploitable signal) is moved to a BackgroundTask on both branches, and a symmetric `hash_token` dummy op is added to the unknown branch, asserted via mock call-parity. Two lower-order timing residuals remain, both accepted-and-noted as the SAME family (chasing full constant-time across all paths is over-scoping for a LOW finding on a single-operator app):

1. **Rate-limit-suppression branch (repeated-probe)**: the THIRD path — a registered email with an unexpired recent token — does LESS work than both equalized paths, so REPEATED probes of a REGISTERED email show a timing DROP on the 2nd probe while an UNREGISTERED email stays flat. An attacker probing the same email twice could distinguish registered from unregistered from that differential.
2. **Local-DB-write asymmetry (single-probe, sub-ms)**: on the FRESH-known path `post_login` does a rate-limit SELECT COUNT + a DELETE + an INSERT + commit that the unknown branch does not mirror (the unknown branch does only the users SELECT + the one dummy `hash_token`). These are sub-millisecond local-SQLite writes — a far weaker signal than the removed network send — but they are a residual single-probe asymmetry. CR (E-254-03 review) explicitly recommended recording this here rather than adding FAKE DB writes on the unknown branch (which the E-254-03 Notes call over-scoping for a LOW finding); AC-3's single-probe parity gates (byte-identical page + `hash_token` call-parity + BackgroundTask-not-awaited) all pass with this residual present.

## Why It Matters
It is the same class of exposure the epic set out to close (login enumeration), just via a repeated-probe rather than single-probe signal. Closing it fully makes the enumeration protection complete rather than single-probe-only.

## Rough Timing
Low urgency — a LOW-severity finding on a single-operator HS app. Promote if the app opens to more users, or if a security review flags login enumeration as material. E-254-03 accepted-and-noted this residual (same disposition class as IDEA-093's token-in-logs residual).

## Dependencies & Blockers
- [ ] E-254-03 (login-timing equalization) shipped — this builds on that.

## Open Questions
- Cheapest fix for BOTH residuals: run comparable dummy equalizing work (hash + a dummy user-scoped SELECT, and optionally throwaway writes) inside the rate-limit-suppression branch AND the unknown branch so all paths do comparable DB + hash work. Does that fully flatten the repeated-probe differential AND the local-write asymmetry, or does the absence of the real DELETE+INSERT still leak a residual signal?
- Are sub-millisecond local-SQLite write asymmetries even measurable over the network/middleware noise floor for a remote attacker — i.e. is residual #2 exploitable in practice, or effectively a permanent WONTFIX?
- Is a repeated-probe differential even worth closing for a single-operator app, or is this a permanent WONTFIX?

## Notes
Residual #1 (rate-limit repeated-probe) surfaced by software-engineer during the E-254 Codex spec-review triage (P2-03) and accepted-and-noted in E-254-03 Notes. Residual #2 (local-DB-write single-probe asymmetry) surfaced by code-reviewer during the E-254-03 dispatch review as a SHOULD FIX and folded HERE (2026-07-07) — CR explicitly recommended recording it as part of this accepted-residual family rather than adding fake DB writes on the unknown branch. SE + team-lead agreed not to expand E-254 scope for either. Related: IDEA-093 (magic-link token-in-logs residual, same accept-and-note pattern).

---
Created: 2026-07-06
Last reviewed: 2026-07-07
Review by: 2026-10-04
