# IDEA-006: Epic Lanes Convention for Multi-Workstream Epics

## Status
`CANDIDATE`

## Summary
Formalize a "lanes" convention for organizing epic Technical Notes when an epic contains multiple independent workstreams. Lanes are labeled subsection headers (e.g., "Lane A: Code Review", "Lane B: Spec Review") that scope workstream-specific technical details to the stories they apply to. This helps implementing agents identify which Technical Notes content is relevant to their assigned story.

## Why It Matters
When an epic has 3+ independent workstreams, the Technical Notes section can contain details that apply to only a subset of stories. Without clear scoping, an implementing agent must read the entire Technical Notes section and determine which parts apply to its story -- increasing context consumption and risk of confusion.

E-034 (Codex Review Integration) demonstrated this naturally: code review and spec review had different CLI modes, different rubric evaluation criteria, and different runtime context rules. Lane headers made it immediately clear which details belonged to which story.

However, most epics in this project have 3-5 stories with straightforward dependency chains where Technical Notes apply uniformly. The value of lanes scales with epic complexity.

## Rough Timing
Promote when the project regularly produces epics with 6+ stories across 3+ independent workstreams AND implementing agents report confusion about which Technical Notes apply to their story. Neither trigger has fired yet.

Possible catalysts:
- E-002 (Data Ingestion, 8 stories) dispatch -- if agents are confused by crawl-vs-load Technical Notes
- E-004 (Coaching Dashboard) formation -- if the dashboard epic spans multiple feature areas with distinct technical details
- General growth in epic size as the project matures

## Dependencies & Blockers
- [ ] Evidence that implementing agents are confused by unscoped Technical Notes (the pain must be real, not hypothetical)
- [ ] At least 2-3 epics at the 6+ story scale to validate the pattern across cases

## Open Questions
- Should lanes be a formal template section (Optional "Lanes" subsection in Technical Notes), or guidance in the PM agent definition about when to use lane-style headers?
- Should lane labels appear in the Stories table (e.g., a "Lane" column) or only in Technical Notes?
- Does the dispatch-pattern need lane awareness, or do lanes remain purely an organizational aid for Technical Notes with no dispatch-rule impact?
- How do lanes interact with the existing "Parallel Execution Analysis" and "execution waves" patterns already used in Technical Notes?

## Notes
**Evaluation conducted 2026-03-03.** Reviewed E-034 (where lanes were used), E-009, E-023, E-028, and E-002 (where they were not). Findings:

**What lanes solve:** Scoping Technical Notes content to specific stories/workstreams. This is genuinely useful when an epic has workstream-specific technical details (different CLI modes, different evaluation criteria, different file sets).

**What lanes do NOT solve:** Dispatch ordering, file conflict detection, dependency management, or agent routing. The existing Stories table dependency column, Parallel Execution Analysis sections, execution waves, and context-layer routing check already handle these concerns.

**Existing patterns that overlap:**
- Stories table dependency column -- communicates sequencing
- Parallel Execution Analysis in Technical Notes -- communicates file conflicts and parallel safety
- Execution waves (used in E-028) -- communicates grouping + sequencing for dispatch
- Section headers in Technical Notes (used in E-009 as "Option A" / "Option B") -- ad-hoc workstream scoping

**Why DEFER, not ADOPT:** Most epics are small (3-5 stories). Formalizing lanes adds process overhead that violates the "simple first" principle for the typical case. The PM can already use lane-style headers informally when they fit (as in E-034) without a formal convention.

**Why DEFER, not DISCARD:** The pattern demonstrably worked in E-034. If the project grows to produce larger epics regularly, formalizing the convention would reduce cognitive overhead for implementing agents.

**Prior art in this project:**
- E-034 Technical Notes: explicit `### Lane A / B / C` headers
- E-009 Technical Notes: `### Option A / Option B` headers (same concept, different label)
- E-028 Technical Notes: "Execution waves" (sequencing variant)

---
Created: 2026-03-03
Last reviewed: 2026-03-03
Review by: 2026-06-01
