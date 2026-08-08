# IDEA-112: Narrow the PII suppressors so they cannot silence credential patterns

## Status
`CANDIDATE`

## Summary
The two PII-scanner suppressors — the per-line `# pii-ok` pragma and the file-level `synthetic-test-data` marker — currently suppress **all** patterns, credential patterns included (`bearer_token`, `api_key_assignment`). Narrow them so credential patterns stay **active even under a marker**, while shape heuristics (email/phone) remain suppressible. This closes the staged-blob hole where a `GC_REFRESH_TOKEN=<real> # pii-ok` line is staged, scanned, and certified clean.

## Why It Matters
Per CA's E-256 ruling, CLAUDE.md §4g (the human review-time "test fixtures using real credentials = MUST FIX" gate) does **not** close this hole: it is a dispatch-time human control that does not fire on ad-hoc operator commits, unread files, or a marker added in one epic with a real token added to that file epics later. Treating §4g as a closure is "the same category error as accepting Cloudflare as CSRF mitigation." A suppressor that can silence a real credential is a structural gap, not author discipline — and this is the credential-heavy repo where that matters most.

## Rough Timing
Promote as a PII-hardening follow-up, sibling of E-254. Security-flavored, low urgency, but the fix may be nearly free (see the measurement below). **Do NOT plan the narrowing before the measurement runs** — the blast radius is unknown.

## Dependencies & Blockers
- [ ] None hard. Reuses the existing scanner. Best done after E-256 (which documents the current suppressor scope + choice hierarchy in `pii-safety.md`, story 13).

## Open Questions
- **FIRST STORY IS MEASUREMENT, NOT CODE (~10 min):** re-run the scanner over the ~30 `synthetic-test-data`-marked files with suppression DISABLED. SE's existing "1 violation across tests/" scan measured the tree **with markers active**, so those 30 marked files were never scanned — we do not yet know how many synthetic fixtures actually rely on *credential* suppression (vs. shape suppression). Near-zero → the narrowing is nearly free and closes the hole structurally. Large → it needs a per-file allowlist. Do not skip the measurement.
- Should credential patterns be un-suppressible entirely, or suppressible only via an explicit second marker that is itself a review trigger?
- Interaction with story 16's precedent (change-the-value over marker) — does narrowing make some existing markers redundant?

## Notes
Surfaced by claude-architect during E-256 planning (2026-07-09) when ruling that §4g does not close the staged-blob residual. Related: [[IDEA-102-committed-artifact-pii-gap]] (the planning-artifact half, promoted to E-256-14), [[IDEA-096-docs-api-systematic-pii-sweep]], [[IDEA-104-docs-api-denylist-completeness-gap]] — these may consolidate into one "PII hygiene across all committed files" slice. Domain: software-engineer (scanner) + claude-architect (rule). Anchors: `src/safety/pii_scanner.py:143-155` (both suppressors outside `COMPILED_PATTERNS`), `src/safety/pii_patterns.py`.

---
Created: 2026-07-09
Last reviewed: 2026-07-09
Review by: 2026-10-07
