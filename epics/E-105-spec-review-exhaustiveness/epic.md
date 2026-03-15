# E-105: Spec Review Exhaustiveness

## Status
`READY`

## Overview
Harden the spec review process so that multi-round review drift -- the pattern where each fix pass introduces new inconsistencies -- is structurally prevented rather than manually caught. E-072 required four refinement rounds because the rubric missed consistency/propagation checks, templates encouraged duplication, and the PM lacked a self-review gate.

## Background & Context
E-072 (Proxy Session Ingestion Skill) exposed a class of review failures during its refinement:

1. **Duplication trap**: ACs restated Technical Notes content verbatim, creating O(n^2) consistency surface. Every edit to Technical Notes required propagating to multiple ACs, and each propagation was a new opportunity for drift.
2. **No self-review step**: PM incorporated findings without a grep sweep or full re-read, so cascade edits introduced new inconsistencies (e.g., endpoint count changed in one place but not another, env var names standardized in epic but not stories).
3. **Rubric gaps**: The spec review rubric (`.project/codex-spec-review.md`) checks 9 surface-level properties but not internal consistency, propagation completeness, or specification surface area.
4. **Wrong methodology**: Reviewers pattern-matched individual items instead of building a complete model of the spec first and then checking each element against it.
5. **Re-review scope undefined**: Round 2+ reviews re-reviewed everything instead of scoping to changes only, producing false positives on already-fixed items.

Three independent analyses (PM, CR, CA) converged on the same root causes and deliverables. Claude-architect participated directly in the root cause analysis and co-produced the category definitions and methodology recommendations captured in Technical Notes. This satisfies the agent infrastructure consultation trigger (E-105-02 modifies `.claude/agents/product-manager.md`).

## Goals
- Spec review rubric catches consistency and propagation errors in a single pass
- Story template discourages AC-level duplication of Technical Notes content
- PM self-review gate prevents cascade drift from reaching reviewers
- Re-reviews are scoped to changes, reducing false positives and wasted rounds

## Non-Goals
- Rewriting E-072's ACs retroactively (it is already READY)
- Changing the code review rubric (`.project/codex-review.md`) -- this epic targets spec review only
- Changing the dispatch pattern or review loop mechanics
- Adding automated tooling (linters, scripts) -- these are template and rubric text changes

## Success Criteria
- The spec review rubric has categories that would catch the E-072 drift patterns (consistency, propagation, surface area)
- The story template includes guidance that would prevent the duplication trap
- The PM agent definition includes a self-review gate that would catch cascade edits before handback

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-105-01 | Spec review rubric hardening | TODO | None | - |
| E-105-02 | Template and PM self-review gate | TODO | None | - |

## Dispatch Team
- claude-architect

## Technical Notes

### Design Principle: Single Source of Truth

The core fix is structural: make it hard to create duplication in the first place, and easy to catch it when it happens. Technical Notes are the single source of truth for HOW; ACs verify WHAT outcomes hold. When an AC needs to reference a procedure defined in Technical Notes, it should say "per the procedure in Technical Notes section X" rather than restating the procedure inline.

### Deliverables Table

This table is the authoritative list of changes. Stories reference it by row rather than restating content.

| # | Change | File | Priority |
|---|--------|------|----------|
| 1 | Add rubric category 10: Internal Consistency | `.project/codex-spec-review.md` | HIGH |
| 2 | Add rubric category 11: Propagation Completeness | `.project/codex-spec-review.md` | HIGH |
| 3 | Add rubric category 12: Specification Surface Area | `.project/codex-spec-review.md` | HIGH |
| 4 | Add "complete model" methodology instruction | `.project/codex-spec-review.md` | HIGH |
| 5 | Add re-review scoping instruction | `.project/codex-spec-review.md` | MED |
| 10 | Add "Epic-Level Checks" structural separation before categories 10-12 | `.project/codex-spec-review.md` | HIGH |
| 6 | Add "reference not restate" guidance | `.project/templates/story-template.md` | HIGH |
| 7 | Add "single source of truth" note | `.project/templates/epic-template.md` | MED |
| 8 | Add PM self-review gate (post-incorporation grep sweep) | `.claude/agents/product-manager.md` | HIGH |
| 9 | AC complexity soft limit (3 sub-clauses guidance) | `.project/templates/story-template.md` | MED |

### Category Definitions (for Deliverables Table rows 1-3)

**Category 10 -- Internal Consistency**: Do values that appear in multiple locations (counts, env var names, field names, status codes) match across all occurrences in the epic and story files? Are there contradictions between ACs in different stories within the same epic?

**Category 11 -- Propagation Completeness**: When the epic's Technical Notes define a rule, procedure, or constraint, do all stories that implement that rule reflect the current version? Are there stale references to superseded decisions? After a finding is incorporated, has the fix propagated to all locations where the original value appeared?

**Category 12 -- Specification Surface Area**: Are ACs restating content from Technical Notes instead of referencing it? Could an AC sub-clause be replaced with "per Technical Notes section X"? Are there ACs with more than 3 sub-clauses that should be decomposed or converted to references?

### Structural Placement of Categories 10-12

Categories 1-9 are per-story checks ("does this story's ACs have clarity?", "does this story's routing match?"). The Evaluation Checklist intro ("For every story in the epic, check each item") is correct for them. Categories 10-12 are inherently cross-story -- they check consistency *across* files, propagation *across* stories, and surface area *across* ACs. They must be placed under a separate sub-heading (e.g., "Epic-Level Checks") with their own framing instruction that makes clear these checks operate on the epic as a whole, not per-story.

### Complete Model Methodology

The rubric should instruct reviewers to build a facts table before checking individual items: extract every named value (counts, env var names, field lists, status categories, file paths) from Technical Notes, then verify each value is consistent wherever it appears in story ACs. This front-loads the consistency check instead of hoping to notice drift during line-by-line review.

### Re-Review Scoping

Round 2+ reviews should: (1) read the change summary from PM, (2) verify each claimed fix was applied, (3) check that fixes did not introduce new inconsistencies in adjacent text, (4) NOT re-review unchanged sections. This prevents false positives on already-fixed items and reduces review fatigue.

## Open Questions
None.

## History
- 2026-03-13: Created. Motivated by E-072's four-round refinement experience. Root causes and deliverables produced by convergent analysis from PM, CR, and CA during E-072 troubleshooting session.
