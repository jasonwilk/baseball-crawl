# E-180: Codify E-178 Planning Knowledge

## Status
`READY`

## Overview
Capture the design principles, terminology conventions, and process lessons generated during E-178's planning session into the appropriate context-layer locations (agent memory). This knowledge was produced by expert consultations but currently exists only in the E-178 epic file and conversation history.

## Background & Context

The E-178 (Teams Page UX Overhaul) planning session produced significant reusable knowledge beyond the implementation spec:

1. **UXD completed a comprehensive front-to-back audit** of every template, user flow, and interaction in the system. Key findings: auth flow, schedule page, batting/pitching stats, player profiles, spray charts, navigation, and error pages are all clean. The schedule page was identified as the best-designed page. The reports page implements auto-refresh and error tooltip patterns that serve as reference implementations.

2. **Design principles were articulated** that should inform all future UI work:
   - "Consequence-oriented labels" — tell the user what they GET, not what the system found
   - "Question-as-heading pattern" — headings frame the user's decision
   - "Update Stats" as the unified verb for all data refresh actions
   - Three coach modes: setup mode, game prep mode, check-in mode

3. **Terminology decisions were made** that supersede earlier conventions (E-088):
   - "Connected"/"Limited access" replacing "Discovered"/"Not available (403)"
   - "keep"/"remove" replacing "canonical" on merge pages
   - "Linked" replacing "Resolved" in flash messages
   - "Not linked — find on GameChanger first" replacing "Unresolved — map first"

4. **A pattern failure was identified**: E-173 scoped "fix everything" from a partial list, missing items. E-178 initially repeated the same mistake. The lesson: when the user says "front to back" or "comprehensive", audit the entire surface FIRST, then write the spec from the complete inventory.

**Expert consultations completed:**
- **claude-architect**: Assessed placement for each knowledge type. Terminology conventions and design principles belong in UXD agent memory (not rules, not CLAUDE.md). Process lesson belongs in PM agent memory. CLAUDE.md Admin UI section describes architecture concepts, not UI copy — no changes needed. No new rules warranted.
- **docs-writer**: Assessed documentation impact. `docs/admin/operations.md` and `docs/coaching/scouting-reports.md` need targeted label updates, but only AFTER E-178 implementation ships. Those updates belong to E-178's closure documentation assessment, not this epic.

No additional expert consultation required — CA and DW covered the relevant domains.

## Goals
- UXD agent memory captures the design principles (consequence-oriented labels, question-as-heading, unified verbs, coach modes) as a reusable reference for future UI design work
- UXD agent memory reflects post-E-178 terminology decisions, superseding stale E-088 conventions
- UXD agent memory includes a pointer to the reports page as a reference implementation for auto-refresh and error tooltips
- PM agent memory captures the "complete audit first" lesson for future epic scoping

## Non-Goals
- Updating CLAUDE.md (CA assessed: describes architecture, not UI copy — no changes needed)
- Creating new `.claude/rules/` files (CA assessed: design vocabulary is UXD-scoped, not an invariant for all agents)
- Updating `docs/admin/` or `docs/coaching/` (DW assessed: those updates belong to E-178's closure documentation assessment)
- Modifying any source code, templates, or tests

## Success Criteria
- UXD agent memory contains a topic file for design principles that names all four principles and is linked from MEMORY.md
- UXD agent memory's "Coach-Friendly Language" section reflects E-178 terminology (not E-088 terminology)
- UXD agent memory includes a reference implementation entry for the reports page
- PM agent memory contains a feedback-type memory file capturing the "complete audit first" lesson and is linked from MEMORY.md
- No stale E-088 terminology remains in UXD MEMORY.md that contradicts E-178 decisions

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-180-01 | UXD agent memory — design principles, terminology refresh, and reference implementations | TODO | None | - |
| E-180-02 | PM agent memory — "complete audit first" scoping lesson | TODO | None | - |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: UXD Memory Updates (Story 01)

Three categories of updates to `.claude/agent-memory/ux-designer/`:

**A. New topic file: design principles**
Create a topic file capturing these reusable principles:
1. **Consequence-oriented labels**: Tell the user what they GET, not what the system found. Example: "Connected" (you get full stats) instead of "Discovered" (system found a match).
2. **Question-as-heading pattern**: Frame headings as the user's decision. Example: "Which team do you want to keep?" instead of "Select Canonical Team."
3. **Unified verbs**: One verb per action across all pages. "Update Stats" for all data refresh.
4. **Three coach modes**: setup mode (initial configuration), game prep mode (before a game), check-in mode (routine monitoring). Design flows should consider which mode the coach is in.

**B. Update "Coach-Friendly Language (E-088 Design)" section**
The E-088 terminology in MEMORY.md is partially superseded by E-178 decisions. Full terminology mapping (E-088 → E-178):

| E-088 / Pre-E-178 Term | E-178 Replacement | Context |
|---|---|---|
| "Discovered" (gc_uuid badge) | "Connected" | Consequence-oriented: tells coach they get full stats |
| "Not available (403)" (gc_uuid badge) | "Limited access" | Consequence-oriented: tells coach data is partial |
| "Sync" / "Sync Now" (action button) | "Update Stats" | Unified verb for all data refresh actions |
| "Last Synced" (column/label) | "Last Updated" | Consistent with "Update Stats" verb |
| "Syncing..." / "Running..." (status) | "Updating..." | Consistent with "Update Stats" verb |
| "Sync failed" (status badge) | "Update failed" | Consistent with "Update Stats" verb |
| "Resolve" (duplicate banner link) | "Merge" | User decision: merge duplicates, not "resolve" them |
| "Canonical" (merge page labels) | "keep" / "remove" | Plain English for merge page decisions |
| "Resolved" (flash messages) | "Linked" | Opponent connection language |
| "Unresolved — map first" (inline text) | "Not linked — find on GameChanger first" | Action-oriented, explains what to do |
| "Stats not loaded yet" (empty state) | "Stats aren't ready yet" | Softer, less technical |

**Terms E-178 does NOT change** (retain as-is from E-088):
- "Scoresheet only" (yellow badge) — this is a dashboard data state label describing what data the coach gets, not pipeline jargon
- "Full stats" (green badge) — same: describes data availability
- "Connect to GameChanger" (opponent link action) — already plain English
- "Disconnect" (opponent unlink action) — already plain English

Update the section to reflect the current terminology, organized as "Current conventions (E-178)" with a note that these supersede E-088.

**C. Reference implementation pointer**
Add a memory entry noting that `src/api/templates/admin/reports.html` demonstrates the auto-refresh (meta tag) and error tooltip patterns. Future UX work requiring similar patterns should reference this page.

### TN-2: PM Memory Update (Story 02)

Create a feedback-type memory file in `.claude/agent-memory/product-manager/` capturing:
- **Rule**: When the user says "front to back", "comprehensive", or "fix everything", audit the entire surface FIRST, then write the spec from the complete inventory.
- **Why**: E-173 scoped a "fix everything" epic from a partial list and missed 25+ items. E-178 initially repeated the same mistake before UXD's comprehensive audit caught the gap.
- **How to apply**: Before writing stories for any "fix all X" or "comprehensive cleanup" epic, require a complete inventory/audit step. The audit output becomes the spec's source of truth.

### TN-3: Documentation Note

DW assessed that `docs/admin/operations.md` and `docs/coaching/scouting-reports.md` will need targeted label updates after E-178 implementation ships. These updates are NOT in scope for this epic — they belong to E-178's normal closure documentation assessment per `.claude/rules/documentation.md`. This note exists so the PM remembers to flag it during E-178 closure.

## Open Questions
None.

## History
- 2026-03-29: Created. CA and DW consultations completed. CA: all knowledge belongs in agent memory, no CLAUDE.md or rules changes needed. DW: doc updates belong to E-178 closure, not this epic.
- 2026-03-29: Codex spec review iteration 1. 3 findings, all accepted: (1) wrong template path for reports reference implementation, (2) "Scoresheet only" assessment not testable — settled as retained term, (3) TN-1B terminology mapping incomplete — expanded to full 11-item table plus 4 retained terms.
- 2026-03-29: Epic set to READY.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Codex iteration 1 | 3 | 3 | 0 |
| **Total** | **3** | **3** | **0** |
