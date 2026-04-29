# IDEA-083: CLI _scout_live Catches and Reports CredentialExpiredError from Spray

## Status
`CANDIDATE`

## Summary
Replace the existing `except CredentialExpiredError: raise` re-raise pattern at `src/cli/data.py:337-338` with the same "catch and report" pattern that the web path and the new E-229 plays helper already use. Today the CLI crashes mid-scout when spray's auth expires; the web path catches and continues. This idea brings CLI to parity with web and with this epic's plays helper contract.

## Why It Matters
After E-229, the CLI's behavior is internally inconsistent: spray auth-expiry crashes the CLI immediately (re-raises), but plays auth-expiry is caught and reported via typer.echo with an actionable operator message (`bb creds setup web` + idempotency reassurance). An operator running `bb data scout` and hitting auth expiry mid-spray sees a stack trace and loses any work that ran after spray's failure -- including the entire dedup + plays stages. With "catch and report" the CLI exits cleanly, the operator sees a typer.echo summary line naming the deferred work, and the remaining stages run.

## Rough Timing
Immediately actionable -- the change is well-scoped (single function, ~10 lines) and the pattern to follow is already in place from E-229. Promote when: an operator hits the spray auth-crash in practice, OR during the next cleanup epic touching `_scout_live`.

## Dependencies & Blockers
- [x] E-229 must be complete (this idea reuses the helper's "catch and report" pattern)
- [ ] None -- the change is mechanical

## Open Questions
- Should the spray failure produce a structured prefix in `crawl_jobs.error_message` (mirroring the web path), or is typer.echo sufficient for the CLI? (CLI does not write to `crawl_jobs`; uses `scouting_runs` instead.)
- Should the same treatment extend to other places in the CLI that re-raise `CredentialExpiredError`?

## Notes
Surfaced during E-229 planning. Documented in epic Tech Notes "Auth-error handling" section as a known inconsistency, explicitly out of scope for E-229 to keep the epic tight. Filed at E-229 closure per Closure Tasks section.

---
Created: 2026-04-29
Last reviewed: 2026-04-29
Review by: 2026-07-28
