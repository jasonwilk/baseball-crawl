# E-166-02: Modal Spray Chart Viewer

## Epic
[E-166: Enhanced Spray Charts](epic.md)

## Status
`DONE`

## Description
After this story is complete, all spray chart images on the opponent detail and player profile pages will be tappable to open in a full-screen modal overlay. The "View spray" text links in the opponent detail batting table will become buttons that open the modal instead of navigating to a new tab. The modal will be dismissible via outside click, Escape key, or a close button, and will work well on mobile devices.

## Context
Currently, "View spray" links in the opponent detail page open spray chart PNGs in a new browser tab (`target="_blank"`), which is a poor mobile experience. Embedded spray chart images (team spray in opponent detail, player spray in player profile) have no enlarge affordance at all. This story adds a shared modal component using vanilla JS and Tailwind CSS, with no external library dependencies.

## Acceptance Criteria
- [ ] **AC-1**: Given the opponent detail page with a player who has spray data, when the user clicks "View spray", then the spray chart PNG opens in a modal overlay instead of a new browser tab.
- [ ] **AC-2**: Given the opponent detail page with a team spray chart, when the user taps/clicks the embedded team spray chart image, then it opens in the modal overlay at larger size.
- [ ] **AC-3**: Given the player profile page with an embedded spray chart, when the user taps/clicks the spray chart image, then it opens in the modal overlay at larger size.
- [ ] **AC-4**: The modal is dismissible by: (a) clicking/tapping outside the chart area, (b) pressing the Escape key, (c) clicking/tapping the close (×) button. (d) Clicking/tapping the chart image itself inside the modal does NOT dismiss it (inner container uses `stopPropagation` per TN-6).
- [ ] **AC-5**: The modal uses the layout defined in Technical Notes TN-6: mobile top-aligned with status bar padding, desktop vertically centered.
- [ ] **AC-6**: Trigger elements use `<button type="button">` (not `<a>` anchors) per Technical Notes TN-6. Image-wrapped trigger buttons use `aria-label="Enlarge spray chart"`; text trigger buttons (e.g., "View spray") rely on visible text as the accessible name (no `aria-label`).
- [ ] **AC-7**: The modal markup and JS are placed per Technical Notes TN-7 — `base.html` provides a `{% block scripts %}` hook, and templates that need the modal override this block.
- [ ] **AC-8**: The `opponent_print.html` template is NOT modified (print layout, no interactive elements).
- [ ] **AC-9**: The modal has `role="dialog"`, `aria-modal="true"`, and the close button has `aria-label="Close"` per Technical Notes TN-6 accessibility requirements.
- [ ] **AC-10**: The close button (×) meets the 44px minimum touch target size for mobile usability per Technical Notes TN-6.
- [ ] **AC-11**: Background scrolling is locked (`overflow: hidden`) when the modal is open and restored when it closes, regardless of dismiss method (per TN-6 scroll lock requirement).
- [ ] **AC-12**: Each page uses a single modal instance (one `#chart-modal` element) reused for all spray chart triggers on that page, per TN-6.

## Technical Approach
Add a `{% block scripts %}{% endblock %}` to `base.html` just before `</body>`. Templates needing the modal override this block with the modal HTML and vanilla JS functions (`openChartModal`, `closeChartModal`, `handleModalEscape`). Replace the `<a target="_blank">` links in `opponent_detail.html` with button triggers per TN-8. Wrap embedded `<img>` elements in button triggers for the team spray chart and player profile spray chart.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/templates/base.html` — add `{% block scripts %}` before `</body>`
- `src/api/templates/dashboard/opponent_detail.html` — replace "View spray" anchors with button triggers, wrap team spray image in button trigger, add modal markup via `{% block scripts %}`
- `src/api/templates/dashboard/player_profile.html` — wrap player spray image in button trigger, add modal markup via `{% block scripts %}`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The modal JS is ~20 lines of vanilla JavaScript. No Alpine.js, HTMX, or other frameworks.
- The `cursor-zoom-in` Tailwind class provides a visual affordance that the image is enlargeable.
- `opponent_print.html` does not extend `base.html` and uses inline styles — it is explicitly out of scope.
- Testing scope is route-level: existing `tests/test_dashboard.py` tests confirm templates render without errors. Modal JS behavior (open/close/dismiss) is verified manually, not via automated tests.
