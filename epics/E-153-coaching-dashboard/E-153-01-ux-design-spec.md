# E-153-01: UX Design Spec for Coaching Dashboard

## Epic
[E-153: Team-Centric Coaching Dashboard](epic.md)

## Status
`TODO`

## Description
After this story is complete, a text-based design spec exists that defines the layout, component structure, and interaction patterns for the coaching dashboard redesign. This spec covers: the schedule landing page, the 3-tab navigation, the opponent detail page (pitching-first), and all empty states. Subsequent implementation stories (E-153-03, E-153-04) build from this spec.

## Context
The coaching dashboard is being redesigned from a stats-first layout to a schedule-first layout. Four domain experts (coach, UXD, SE, DE) contributed requirements during discovery. This story synthesizes those requirements into implementable wireframes and component specs before SE begins coding. The existing templates in `src/api/templates/dashboard/` and `src/api/templates/base.html` provide the current-state baseline.

## Acceptance Criteria
- [ ] **AC-1**: A design spec document exists at `/.project/research/E-153-ux-design-spec.md` containing all sections listed below.
- [ ] **AC-2**: The spec includes a text-based wireframe for the schedule landing page showing: upcoming games section (with days-until, opponent name, home/away, scouted indicator) and completed games section (with date, opponent, score, W/L, home/away). The next upcoming game has visual emphasis per Technical Notes TN-5.
- [ ] **AC-3**: The spec includes a text-based wireframe for the 3-tab bottom navigation (Schedule | Batting | Pitching) with active/inactive state styling, replacing the current 4-tab nav per Technical Notes TN-4.
- [ ] **AC-4**: The spec includes a text-based wireframe for the opponent detail page with pitching-first section order per Technical Notes TN-6, including game count alongside all rate stats per TN-7.
- [ ] **AC-5**: The spec includes wireframes for three opponent empty states: (a) unlinked opponent with admin shortcut, (b) linked but unscouted opponent, (c) opponent with full stats -- per Technical Notes TN-6.
- [ ] **AC-6**: The spec includes a component inventory listing every new or modified template file and Jinja2 partial, with a brief description of each component's purpose.
- [ ] **AC-7**: The spec addresses mobile layout at 375px width -- touch targets >= 44px, no horizontal scroll on schedule rows, and responsive handling for score/badge columns.
- [ ] **AC-8**: The spec references existing Tailwind CSS patterns from `base.html` and current dashboard templates (color scheme, typography, spacing conventions) to maintain visual consistency.

## Technical Approach
Read all existing dashboard templates (`src/api/templates/dashboard/*.html`, `src/api/templates/base.html`) to document the current design system (colors, spacing, typography). Apply the expert consultation findings (coach priorities, UXD navigation recommendations, SE route structure) to produce wireframes. Use text-based ASCII/markdown wireframes -- not image files. The spec should be detailed enough that SE can implement each page without design ambiguity.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-153-03 (schedule landing + nav), E-153-04 (opponent detail redesign)

## Files to Create or Modify
- `/.project/research/E-153-ux-design-spec.md` (create)

## Agent Hint
ux-designer

## Handoff Context
- **Produces for E-153-03**: Schedule page wireframe, navigation wireframe, component inventory, mobile layout spec. SE should load `/.project/research/E-153-ux-design-spec.md` as deferred context.
- **Produces for E-153-04**: Opponent detail wireframe (all three states), pitching card layout, empty state designs. SE should load `/.project/research/E-153-ux-design-spec.md` as deferred context.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Design spec is complete with no TBD placeholders
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Text-based wireframes preferred over image files (easier for SE to reference during implementation)
- The design spec is a research artifact, not a permanent doc -- it lives in `/.project/research/`
- Existing Tailwind CDN usage means no build step; all styling is utility classes
