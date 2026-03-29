# E-177-01: Replace Copy Link with View Link + Copy Icon

## Epic
[E-177: Reports Page View Link + Copy Icon](epic.md)

## Status
`DONE`

## Description
After this story is complete, the admin reports page Link column will show a "View" text link that opens the report in a new tab, alongside a small clipboard copy icon (inline SVG, double-document pattern). Clicking the icon copies the report URL to clipboard with visual feedback. The old "Copy Link" text button is removed.

## Context
The current Link column has only a "Copy Link" button, requiring three steps to view a report. This story replaces it with a direct View link (primary action) and a copy icon (secondary action), improving the most common operator workflow. This is a template-only change -- the backend already serves reports at the URL in `report.url`.

## Acceptance Criteria
- [ ] **AC-1**: Given a report with `status == 'ready'` and `is_expired == false`, when the Link column renders, then it shows a "View" text link and a copy icon side by side (per Technical Notes: Layout Pattern).
- [ ] **AC-2**: Given the View link is visible, when the operator clicks it, then the report opens in a new browser tab (`target="_blank"` with `rel="noopener noreferrer"`).
- [ ] **AC-3**: Given the copy icon is visible, when the operator clicks it, then `report.url` is copied to the clipboard via `navigator.clipboard.writeText()`.
- [ ] **AC-4**: Given the copy icon is clicked, when the clipboard write succeeds, then visible feedback is displayed for ~1.5 seconds (per Technical Notes: Copy Feedback).
- [ ] **AC-5**: Given a report with `status != 'ready'` or `is_expired == true`, when the Link column renders, then it shows an em-dash -- same as current behavior.
- [ ] **AC-6**: The copy icon button includes `aria-label="Copy report link"` and `title="Copy link"` (per Technical Notes: Accessibility).
- [ ] **AC-7**: The copy icon is an inline SVG depicting two overlapping rectangles (standard copy/document icon) -- no icon library added (per Technical Notes: Icon Approach).
- [ ] **AC-8**: The old "Copy Link" text button and its associated dead code are removed.

## Technical Approach
The change is confined to `src/api/templates/admin/reports.html`. The Link column cell (inside the `{% for report in reports %}` loop) needs its content replaced: the `<button>` becomes a container with an `<a>` (View link) and a `<button>` (copy icon wrapping an inline SVG). The `copyLink()` JS function in the `<script>` block needs adaptation since the caller is now an icon button rather than a text button -- the feedback mechanism changes from text swap to a visual indicator on the SVG or button.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/templates/admin/reports.html` (modify -- Link column markup + copyLink JS function)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing functionality (delete, generate, status badges, auto-refresh)
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- `report.url` is already a full absolute URL -- used directly in the current `copyLink()` implementation.
- No tests exist for this template (server-rendered HTML). Manual verification is the test method.
- Use `| tojson` (not `| safe`) when embedding `report.url` in JavaScript contexts to prevent XSS.
