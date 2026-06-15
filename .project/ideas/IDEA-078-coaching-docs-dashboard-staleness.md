# IDEA-078: Coaching Docs Still Sell a Dashboard-First / Longitudinal Product

## Status
`CANDIDATE` — surfaced by the reports-first drift scour (2026-06-15, Codex pass). Doc-only; bounded cleanup, not an epic.

## Summary
`docs/coaching/` still describes the pre-reframe product. `docs/coaching/README.md` promises "Player development tracking" across seasons/levels and directs coaches to the live dashboard; `docs/coaching/scouting-reports.md` is framed as a "Coaching Dashboard" guide and states "The dashboard is the main tool." Under the reports-first reframe (`docs/ROADMAP.md`), the dashboard surface and longitudinal/cross-season tracking are explicit NON-GOALS (§7), and the actual product is generate-and-share a standalone scouting report. The coaching docs should be rewritten to match — reports-first, no dashboard, no longitudinal framing.

## Why It Matters
- **Misleads the actual reader.** A coach handed these docs is pointed at a surface that is quarantine-bound and headed for removal; the docs describe capabilities the product no longer offers.
- **Drift the reframe didn't catch.** ROADMAP §7's footnote parks `docs/VISION.md` for the next "curate the vision" session, but `docs/coaching/*` was never called out — the same feature-vs-machinery gap that let `season_fallback` survive (IDEA-077), one layer over in the docs.
- **Cheap to fix, low risk.** Doc-only; no code or schema impact.

## Rough Timing
- Not urgent. Doc cleanup.
- Natural pairing: alongside D1 (dashboard quarantine + nav retarget) so the coaching docs and the redirect/nav changes land together, or as a standalone `docs-writer` pass whenever convenient.
- Trigger to promote/act: D1 planning, or a coach actually being handed the stale docs.

## Dependencies & Blockers
- None hard. Best sequenced with or after D1's dashboard quarantine so the docs describe the post-quarantine reality (no dashboard nav).

## Open Questions
- Rewrite in place now (reports-first) vs. wait for D1 so the docs match the post-quarantine nav? (Lean: bounded rewrite is safe anytime; the only D1-dependency is not referencing dashboard navigation that may move.)
- Do coaching staff currently use these docs at all, or are they effectively unread? (Affects priority.)

## Notes
**Scope (lightweight — docs only):**
- `docs/coaching/README.md` — drop "Player development tracking" / longitudinal framing; remove dashboard-as-primary-tool guidance; reframe around generate-and-share reports.
- `docs/coaching/scouting-reports.md` — retitle/reframe from "Coaching Dashboard" to the standalone report; drop "The dashboard is the main tool."

**Cross-references:**
- `docs/ROADMAP.md` §7 (dashboard + longitudinal non-goals); §4 (dashboard QUARANTINE → REMOVE); D1 (nav retarget away from `/dashboard`).
- Reports-first drift scour findings: `.project/research/reports-first-drift-scour/findings-claude.md` (Codex-pass INERT finding, 2026-06-15).
- IDEA-077 (season_fallback) — sibling "non-goal declared at feature level, not traced down" finding.
- `docs/VISION.md` is handled separately via the "curate the vision" trigger (§7 footnote); this IDEA covers `docs/coaching/` specifically, which that note does not.

---
Created: 2026-06-15
Last reviewed: 2026-06-15 (captured by reports-first drift scour)
Review by: 2026-09-13 (90 days from created)
