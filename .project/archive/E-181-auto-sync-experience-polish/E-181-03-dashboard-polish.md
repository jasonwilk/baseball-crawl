# E-181-03: Dashboard Empty States, Schedule Links, and Welcome State

## Epic
[E-181: Auto-Sync and Experience Polish](epic.md)

## Status
`DONE`

## Description
After this story is complete, the dashboard has three polish improvements: schedule cards show a "Link" action for admin users when opponents aren't scouted, the opponent detail page shows actionable empty states that explain why there's no data and what to do next, and an empty teams list shows a welcome state with a clear path to adding the first team.

## Context
These three items are template and light route handler improvements that make every page feel complete. Currently, "Not scouted" on schedule cards is a dead end, opponent detail with no data shows a minimal message, and new users see an empty table with no guidance. Together these eliminate the most common "what do I do next?" moments.

## Acceptance Criteria

**Schedule card "Link" micro-CTA (admin-only):**
- [ ] **AC-1**: On schedule cards, when an opponent is not scouted, admin users see a "Link >" action next to (or replacing) the "Not scouted" text.
- [ ] **AC-2**: Non-admin users see the existing "Not scouted" text without a link.
- [ ] **AC-3**: The "Link" action links to `/admin/opponents?filter=unresolved&team_id={team_id}`.
- [ ] **AC-4**: The "Link" action uses `event.stopPropagation()` to prevent the card's own click handler from firing.

**Richer opponent detail empty states:**
- [ ] **AC-5**: When an opponent is linked (has `public_id`) but has no scouting data, the empty state heading reads "No scouting data yet." with subtext "Stats will appear after the next update."
- [ ] **AC-6**: When an opponent is not linked (no `public_id`), the empty state heading reads "This opponent isn't linked to GameChanger yet." Admin users see a link to the resolution workflow; non-admin users see "Ask your admin to link this team."
- [ ] **AC-7**: The empty states replace the current minimal message on the opponent detail page.

**Welcome state for new users:**
- [ ] **AC-8**: When the teams list is empty (no teams in the database), the teams page shows a welcome heading "Welcome to LSB Baseball." with subtext "Get started by adding your first team." instead of an empty table.
- [ ] **AC-9**: The welcome message includes a CTA button linking to the add-team flow (`/admin/teams/add`).

**Tests:**
- [ ] **AC-10**: Tests verify the "Link" CTA appears for admin users and is absent for non-admin users.
- [ ] **AC-11**: Tests verify the appropriate empty state message for linked vs. unlinked opponents.
- [ ] **AC-12**: Tests verify the welcome state appears when no teams exist.
- [ ] **AC-13**: No regressions in existing tests.

## Technical Approach
The schedule card CTA requires the user's admin role to be available in the template. The schedule route handler in `dashboard.py` may not currently pass `is_admin` to the template context -- if not, this must be added. The opponent detail empty states require the opponent's resolution status (already in template context). The welcome state requires checking the team count (already available -- the route handler passes the teams list to the template). Per TN-3, the schedule card link uses `event.stopPropagation()` because the card itself is clickable. Per TN-4, empty states use exact text specified in the ACs.

## Dependencies
- **Blocked by**: E-181-01 (shared file: `tests/test_admin_teams.py`), E-181-02 (shared file: `opponent_detail.html`)
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/dashboard.py` -- pass `is_admin` to schedule template context (if not already present)
- `src/api/templates/dashboard/schedule.html` -- add "Link >" micro-CTA for admin users on unscouted opponents
- `src/api/templates/dashboard/opponent_detail.html` -- replace minimal empty state with richer linked/unlinked variants
- `src/api/templates/admin/teams.html` -- add welcome state when teams list is empty
- `tests/test_dashboard.py` -- add tests for schedule CTA (admin vs non-admin), empty states (linked vs unlinked)
- `tests/test_admin_teams.py` -- add test for welcome state

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The "Link" micro-CTA is deliberately small and unobtrusive -- it's a convenience for admins, not a primary action. Coaches who aren't admins don't need to see it.
- Empty state text is specified exactly in the ACs per TN-4. The key principle (from E-178's design language): tell the coach what to expect, not what the system did.
- The welcome state should feel inviting, not like an error. "Get started by adding your first team" is better than "No teams found."
