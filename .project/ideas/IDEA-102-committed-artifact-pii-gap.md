# IDEA-102: Close the committed-artifact PII gap (planning/idea/epic files are ungated)

## Status
`CANDIDATE`

## Summary
Real PII (names, UUIDs, public_ids) can be written into committed NON-`docs/api/` artifacts — idea files, epic/story files, PM/agent notes, decision logs — with NO automated gate to catch it. Two independent holes leave these files unprotected:
1. **The pre-commit PII scanner skips them**: `src/safety/pii_patterns.py::SKIP_PATHS` includes `epics/` and `.project/`, so `pii_scanner.py` never reads idea/epic/story/research files at all.
2. **Even if scanned, names are undetectable**: the scanner detects emails/phones/credentials by regex but deliberately does NOT detect person names (too high a false-positive rate — names are protected only by the gitignored `/ephemeral/` convention). A pasted real minor's name would pass regardless.

The E-254-07 byte-gate (`scripts/check_doc_pii.sh` + the real denylist) is scoped to `docs/api/` only, so it does not cover these paths either. Net: the ONLY thing standing between a real identifier and git history in a planning artifact is author discipline (E-254-07 Decision #2: "exact real identifiers are NOT written into committed artifacts").

## Why It Matters
This is not hypothetical: during the E-254-07 dispatch (2026-07-07), a real likely-minor's name was captured verbatim into a committed idea file while recording a PII-tail finding — the epic that was SCRUBBING that class of PII nearly REINTRODUCED it in an idea file. Codex caught it in the Phase-4b review and it was scrubbed before closure, but no automated control would have blocked the commit. For a project whose core discipline is "credentials/PII MUST NEVER enter git history," a whole class of committed files being ungated is a real gap.

## Rough Timing
Promote as a PII-hardening follow-up (natural sibling of [[IDEA-096-docs-api-systematic-pii-sweep]]). Low urgency but security-flavored; the near-miss makes it more than cosmetic. Escalate if it recurs.

## Dependencies & Blockers
- [ ] None hard. Reuses the E-254-07 harness/denylist pattern.

## Open Questions
- **Cheapest lever**: extend the byte-gate to also sweep `epics/` + `.project/` against the real denylist (catches KNOWN identifiers — the same ones scrubbed from docs). Does NOT catch NEW/unknown names (denylist is inherently a blocklist), but would have caught THIS incident (the name was already a known identifier in the tail).
- **Scanner angle**: should `epics/`/`.project/` come OUT of `SKIP_PATHS` so at least emails/phones/credentials in planning artifacts are caught? Weigh against the noise reason they were added (story/idea files reference PII-like patterns as examples — that is exactly why they were skipped, TN-2 of the scanner). Might need a `pii-ok`-marker discipline for legitimate example references.
- **Behavioral vs. mechanical**: is a durable check worth it, or is the fix a context-layer reminder (a rule that agents MUST NOT write real identifiers into committed artifacts, mirroring Decision #2 as a standing convention)? Likely BOTH — a positive rule + a denylist sweep of the wider tree.
- Relates to the E-254 Open-Questions "denylist as a re-runnable check" item and [[IDEA-096-docs-api-systematic-pii-sweep]]'s positive-placeholder-rule direction — these three may consolidate into one "PII hygiene across all committed files" slice.

## Notes
Surfaced by the Codex Phase-4b review of E-254 (2026-07-07), which flagged a real-name leak in a committed idea file authored during dispatch. Domain: claude-architect (context-layer rule) + software-engineer/api-scout (denylist/scanner mechanics). Anchors: `src/safety/pii_patterns.py::SKIP_PATHS`, `scripts/check_doc_pii.sh`, E-254-07 Decision #2.

---
Created: 2026-07-07
Last reviewed: 2026-07-07
Review by: 2026-10-05
