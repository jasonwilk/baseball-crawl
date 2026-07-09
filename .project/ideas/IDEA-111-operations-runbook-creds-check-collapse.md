# IDEA-111: Collapse the operations.md:884 credential-recovery step now that bb creds check is an end-to-end probe

## Status
`CANDIDATE`

## Summary
The credential-expiry recovery recipe at `docs/admin/operations.md:884` predates the current `bb creds check`, which is itself a real end-to-end authenticated probe (`/me/user`). The recipe may now carry redundant or superseded steps (e.g. a separate `smoke_test.py` run whose liveness signal `bb creds check` already provides). Review the recipe and collapse it to the minimal, current set of steps.

## Why It Matters
An incident-time runbook is only useful if every step earns its place; redundant or stale steps slow recovery and invite the operator to run tooling that probes the wrong surface (see IDEA-109). This is a runbook-hygiene question, not a code change.

## Rough Timing
Promote as a docs-writer runbook pass, ideally alongside any `smoke_test.py` retarget (IDEA-109) so the recovery recipe and the tool it invokes are reconciled together.

## Dependencies & Blockers
- [ ] Interacts with IDEA-109 (smoke_test.py retarget) — resolving both together avoids two passes over the same recipe.

## Open Questions
- Which steps in the `operations.md:884` recipe are now covered by `bb creds check` alone?
- Should the recipe reference `bb creds check` as the primary liveness probe and demote or drop `smoke_test.py`?

## Notes
Surfaced by claude-architect during E-256 planning (2026-07-09). A docs-writer runbook question, out of E-256 scope. Domain: docs-writer. Anchor: `docs/admin/operations.md:884`, `src/gamechanger/credentials.py:175`.

---
Created: 2026-07-09
Last reviewed: 2026-07-09
Review by: 2026-10-07
