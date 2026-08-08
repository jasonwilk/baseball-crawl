# IDEA-004: Hard Data Boundaries and PII Protection

## Status
`PROMOTED` -- see E-019 (Pre-Commit Safety Gates)

## Summary
Two-layer pre-commit defense (Git hook + Claude Code hook) backed by a stdlib-only Python PII scanner. Prevents accidental commit of real player names, contact info, and GameChanger user IDs. Includes ephemeral data directory structure, PII taxonomy, and developer guide. Full design already completed by claude-architect at `/.project/research/E-006-precommit-design.md`.

## Why It Matters
GameChanger API responses contain real PII (player names, parent contact info, coach phone numbers). Without guardrails, raw JSON exploration files could be committed to Git history, requiring destructive rewrites to remove. This protects against that risk.

## Rough Timing
After E-002 (Data Ingestion Pipeline) starts producing real data files that contain PII. Until real data is flowing, there is nothing to protect against.

## Dependencies & Blockers
- [ ] E-002 must be producing raw JSON files with real data
- [ ] E-001 API access must be working (credentials, authenticated requests)

## Open Questions
- Full name detection: regex is unreliable for names. Scanner starts with email/phone only; names added if PII taxonomy justifies a viable pattern.
- CI enforcement: should the scanner also run in GitHub Actions? Deferred for now.

## Notes
- Originally E-006 (ABANDONED 2026-03-01). All six stories and the architect's design doc preserved in `.project/archive/E-006-pii-protection/`.
- Promoted to E-019 (2026-03-02). Consolidated from 6 stories to 4. Added credential scanning scope.
- Design doc: `/.project/research/E-006-precommit-design.md`
- Scanner: stdlib-only Python at `src/safety/pii_scanner.py`
- Synthetic data marker: `synthetic-test-data` in first 5 lines exempts a file

---
Created: 2026-03-01
Last reviewed: 2026-03-01
Review by: 2026-05-29
