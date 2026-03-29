# E-177: Reports Page View Link + Copy Icon

## Status
`COMPLETED`

## Overview
Replace the "Copy Link" button on the admin reports page with a "View" link that opens the report directly, plus a clipboard copy icon for sharing. The View link becomes the primary action; clipboard copy becomes a secondary icon action.

## Background & Context
The admin reports page (`/admin/reports`) currently offers only a "Copy Link" text button for each ready report. To view a report, the operator must copy the link, open a new tab, and paste -- three steps for the most common action. The user wants a direct "View" link as the primary interaction, with a small copy icon next to it for the sharing workflow.

This is a template-only change confined to `src/api/templates/admin/reports.html`. No backend routes, data model, or dependencies are affected.

No expert consultation required -- this is a self-contained UI change with clear user requirements.

## Goals
- Make viewing a report a single-click action (direct link)
- Preserve clipboard copy as a secondary action via an intuitive icon
- Use the "double paper" / document copy icon pattern the user requested

## Non-Goals
- Adding an icon library or external dependency
- Changing backend report routes or data model
- Redesigning the reports table layout beyond the Link column
- Propagating this icon pattern to other admin pages (future work if desired)

## Success Criteria
- The Link column shows "View" + copy icon for ready, non-expired reports
- Clicking "View" opens the report in a new tab
- Clicking the copy icon copies the report URL to clipboard with visual feedback
- The copy icon is recognizable as a "copy to clipboard" action (double-document SVG)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-177-01 | Replace Copy Link with View link + copy icon | DONE | None | SE |

## Dispatch Team
- software-engineer

## Technical Notes

### Icon Approach
The project has no icon library. Use an **inline SVG** for the copy icon -- a standard "two overlapping rectangles" pattern at 16x16 (or `w-4 h-4` in Tailwind). Inline SVG is zero-dependency, renders identically across browsers, and is consistent with Tailwind conventions. Do NOT add an icon library for this single icon.

### Layout Pattern
The Link column cell should use `flex items-center justify-center gap-1.5` to horizontally align the "View" text link and the copy icon button. The View link is the primary action (standard `<a>` tag with `rel="noopener noreferrer"` for `target="_blank"` security); the copy icon is a `<button>` element wrapping the SVG with adequate padding (`p-1` minimum) for touch accessibility.

### Copy Feedback
The current `copyLink()` function swaps button text and changes color classes. Since the new icon has no text to swap, adapt the feedback to change the SVG's color (e.g., stroke turns green for 1.5s) or briefly swap the copy SVG with a checkmark SVG. Either approach is acceptable -- the key requirement is visible confirmation that the copy succeeded.

### Accessibility
The icon button must include `aria-label="Copy report link"` and `title="Copy link"` for screen readers and hover tooltip.

### Existing JS
The `copyLink()` function in the `<script>` block will need adaptation since the caller is now an icon button rather than a text button. The `navigator.clipboard.writeText()` call and the 1.5s timeout pattern should be preserved.

## Open Questions
None -- all questions resolved during discovery.

## History
- 2026-03-28: Created
- 2026-03-28: Set to READY after internal review
- 2026-03-29: Set to ACTIVE, dispatch begun.
- 2026-03-29: COMPLETED. Single story delivered. Per-story CR: APPROVED (no findings). All ACs verified.
  - **Documentation assessment**: No documentation impact -- UI-only template change, no new features, routes, or workflows.
  - **Context-layer assessment**:
    - New agent capability or tool? **NO**
    - New convention or pattern? **NO**
    - New rule or constraint? **NO**
    - CLAUDE.md update needed? **NO**
    - Agent memory update needed? **NO**
    - Skill or hook change? **NO**

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 3 | 2 | 1 |
| Internal iteration 1 -- Holistic team | 3 | 1 | 2 |
| Per-story CR -- E-177-01 | 0 | 0 | 0 |
| **Total** | **6** | **3** | **3** |
