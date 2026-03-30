# E-192-01: Fix Spray Chart Print Layout in Both Templates

## Epic
[E-192: Fix Spray Chart PDF Page Breaks](epic.md)

## Status
`DONE`

## Description
After this story is complete, printing either scouting report template to PDF via the browser print dialog will produce pages where spray charts do not split across page boundaries. Individual spray charts will render in a 4-column flexbox layout that fits 8+ charts per landscape page. The screen layout remains unchanged.

## Context
Chrome's print engine ignores `break-inside: avoid` on CSS Grid items, causing spray chart images to split mid-image across PDF pages. Both scouting report templates (`opponent_print.html` and `scouting_report.html`) use CSS Grid for spray chart layout and both exhibit this problem. The fix is a print-only CSS override that switches from Grid to flexbox, where Chrome respects fragmentation hints reliably. See TN-1 through TN-6 in the epic for the full specification.

## Acceptance Criteria
- [ ] **AC-1**: In `opponent_print.html`, the `@media print` block overrides `.tendencies-grid` to use `display: flex; flex-wrap: wrap` with `gap: 6px`, and `.tendency-card` to use `width: calc(25% - 5px)` with both `break-inside: avoid` and `page-break-inside: avoid`, per TN-2.
- [ ] **AC-2**: In `scouting_report.html`, the `@media print` block overrides `.spray-grid` to use `display: flex; flex-wrap: wrap` with `gap: 6px`, and `.spray-card` to use `width: calc(25% - 5px)` with both `break-inside: avoid` and `page-break-inside: avoid`, per TN-2.
- [ ] **AC-3**: No CSS rules outside `@media print` blocks are added, modified, or removed in either template.
- [ ] **AC-4**: In `scouting_report.html`, the `.spray-card-stats` element is hidden in the print context (`display: none`) per TN-4.
- [ ] **AC-5**: Card padding is `4px` in print context for both `.tendency-card` and `.spray-card` per TN-4.
- [ ] **AC-6**: No print overrides are added for `.spray-team-chart` or its children; the element retains its existing screen-context styling in print.
- [ ] **AC-7**: Player name text in `.tendency-card-name` and `.spray-card-name` uses `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` in print context, with no change to font size, per TN-4.
- [ ] **AC-8**: Existing `page-break-before: always` rules on `.tendencies-section` and `.spray-section` are preserved per TN-5.
- [ ] **AC-9**: Existing `break-inside: avoid` and `page-break-inside: avoid` on `.spray-card` in base CSS are not removed or overridden to weaker values.

## Technical Approach
Both templates need `@media print` CSS overrides that replace Grid with flexbox on the spray chart container and apply compact card styling. The screen-context CSS remains untouched. The changes are purely CSS -- no Python, no template structure changes, no renderer changes.

Key files to reference:
- Epic Technical Notes TN-1 through TN-6 at `/workspaces/baseball-crawl/epics/E-192-pdf-spray-chart-page-breaks/epic.md`

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/templates/dashboard/opponent_print.html` -- add `@media print` overrides for `.tendencies-grid`, `.tendency-card`, `.tendency-card-name`
- `src/api/templates/reports/scouting_report.html` -- add `@media print` overrides for `.spray-grid`, `.spray-card`, `.spray-card-name`, `.spray-card-stats`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
**Verification delegation**: AC-1 through AC-9 are implementer-verifiable via CSS code inspection during implementation and code review. The behavioral print outcomes (no page splits, 8+ charts per page) are verified by the user post-deploy via browser "Print to PDF". The design intent is 8+ individual spray charts per landscape page based on the TN-3 page geometry (3 rows x 4 columns = 12 possible, 8+ conservatively with spacing).

This is a CSS-only change. No new Python tests are required because the change is purely in template print styling. Existing tests are unaffected.
