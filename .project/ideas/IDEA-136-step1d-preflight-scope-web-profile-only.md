# IDEA-136: Step 1d closure-smoke preflight should scope the credential check to the `web` profile only

## Status
`CANDIDATE`

## Summary
The Step 1d closure-smoke preflight (implement skill Phase 5, and the operator smoke procedure) gates on `bb creds check`, which audits BOTH the `web` and `mobile` GC profiles. The `mobile` profile is permanently dead by design, so a healthy closure can be held on a spurious env-FAIL read off the dead mobile block. The preflight credential check should assert on the `web` profile only (or ignore the mobile block) so a permanently-dead mobile profile cannot produce a false closure hold.

## Why It Matters
During E-261 closure (2026-07-13) the Step 1d preflight read the dead `mobile` credential block as a credential failure and HELD the closure, even though the `web` profile — the only one the reports/scouting path uses — was live and auto-refreshing. The mobile profile has no programmatic refresh (its client key isn't extractable from the iOS binary, E-075) and nothing in the reports product consumes it, so its "failure" is a permanent false signal at a gate that should reflect only the surfaces the epic's smoke actually exercises. A closure gate that fails on a by-design-dead profile erodes trust in the gate and wastes a re-run cycle. api-scout confirmed the reports path is web-exclusive.

## Rough Timing
Someday / low urgency — capture-and-park. Promote if the false env-FAIL recurs on another closure, or fold opportunistically into any epic already touching the implement-skill Step 1d text or `bb creds`.

## Dependencies & Blockers
- [ ] None hard. The `web`-exclusivity of the reports path is already confirmed (api-scout, E-261 closure).

## Open Questions
- Skill-text fix only (assert on the `web` profile / ignore the mobile block in the Step 1d preflight prose), or also add a `bb creds check --profile web` affordance to the command so the preflight can invoke a scoped check directly? The command affordance is SE domain; the skill text is claude-architect domain.
- Does the operator smoke procedure in `docs/admin/` carry the same both-profiles assumption and need the same scoping? (docs-writer touch if so.)
- Relationship to IDEA-122 (`bb creds check` exits 0 even on dead creds → Step 1d preflight mis-attribution) — that idea is about the exit-code being falsely GREEN; this one is about it being falsely RED on a by-design-dead profile. Sibling framing; may be co-addressed.

## Notes
Source: E-261 closure, 2026-07-13; api-scout diagnosis of the false env-FAIL that held the closure smoke. Context-layer/skill refinement — claude-architect owns the skill text; a `bb creds check --profile web` affordance would be SE. Related: IDEA-122 (Step 1d preflight false-GREEN on dead creds), IDEA-123 (Step 1d generate-before-reconcile baseline ordering).

---
Created: 2026-07-13
Last reviewed: 2026-07-13
Review by: 2026-10-11
