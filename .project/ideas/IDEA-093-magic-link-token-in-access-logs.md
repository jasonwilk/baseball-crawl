# IDEA-093: Remove the raw magic-link token from GET-verify access logs

## Status
`CANDIDATE`

## Summary
E-254-02 splits magic-link verification into a side-effect-free GET (interstitial) + a CSRF-protected POST consume, which closes the mail-scanner-prefetch threat. But the raw single-use token still travels in the GET `/auth/verify?token=…` URL and therefore still lands in web-server/access logs. A party who can read access logs could craft a POST replay and consume the token before the legitimate user clicks. Fully removing the token from logs requires delivering it out of the query string — e.g. via a URL fragment (`#token=…`) read by client JS and submitted to the POST, or an equivalent JS/one-time-exchange scheme.

## Why It Matters
Access logs are a lower-privilege surface than the auth DB, and a live 15-minute admin credential sitting in them is an unnecessary exposure. Closing it fully hardens the magic-link flow to defense-in-depth against a log-reading adversary, not just an email link scanner.

## Rough Timing
After E-254 ships the GET/POST split. Promote if a security review flags log retention of the token as material, or if magic links become the primary auth path for more users than the single operator.

## Dependencies & Blockers
- [ ] E-254-02 (GET/POST verify split) complete — this idea builds on that flow.
- [ ] Decide the delivery mechanism (fragment + JS vs. one-time-code exchange) and confirm it degrades acceptably when JS is unavailable.

## Open Questions
- Fragment-based delivery needs JS; what is the no-JS fallback (the current query-string path, accepting the residual)?
- Does the interstitial UX survive moving the token out of the query string?

## Notes
Surfaced by software-engineer during E-254 consultation as the explicit residual of the GET-verify fix (E-254 TN-3). Related to the E-254 magic-link hardening theme.

---
Created: 2026-07-06
Last reviewed: 2026-07-06
Review by: 2026-10-04
