# E-181: Auto-Sync and Experience Polish

## Status
`COMPLETED`

## Overview
Make the system proactive: automatically trigger stat updates after team add and merge instead of requiring manual clicks, show coaches what data they're looking at (game coverage, not sync timestamps), and polish dashboard empty states so every page has a clear next step. Follow-up to E-178's terminology and UX overhaul.

## Background & Context

IDEA-055 captured six items deferred from E-178 per UXD recommendation (ship terminology polish first, features second). E-178 established the consistent language ("Update Stats", "Updating...", "Linked") that this epic's flash messages and labels build on.

**Expert consultations completed:**
- **ux-designer**: Designed solutions for all 6 items. Key design decisions: freshness timestamps use absolute date format on opponent detail and print pages (NOT schedule). "Link" micro-CTA on schedule cards uses `event.stopPropagation()` since card is itself a link. Welcome state shows empty teams list with CTA.
- **baseball-coach**: Validated all improvements. Critical refinement on freshness: "Updated Mar 27" tells when the *system* ran; "Through game Mar 25 (5 games)" tells what's *in the data*. Coaches think in games, not sync dates. Strongly prefers game-date approach for scouting context.
- **data-engineer**: `teams.last_synced` exists but coach wants game-coverage data. Requires a lightweight query against the games table.

**Design decision -- freshness indicator:**
Coach's game-coverage approach wins over UXD's sync-timestamp design. "Through Mar 25 (5 games)" is more actionable for coaches than "Updated Mar 27" -- it tells them what data they're making decisions on, not when the system last ran. Implementation requires querying the games table for MAX(game_date) and COUNT, which is a simple aggregate.

**Promoted from:** [IDEA-055](/.project/ideas/IDEA-055-auto-sync-and-experience-polish.md)

## Goals
- Team add and merge automatically trigger stat updates (no manual "Update Stats" click needed)
- Dashboard pages show game coverage ("Through [date] ([N] games)") so coaches know what data backs their decisions
- Schedule cards link unresolved opponents to the admin resolution workflow (admin users only)
- Opponent detail page has useful empty states with clear next steps
- New users see a welcome state with a clear path to adding their first team

## Non-Goals
- Changing the sync/crawl pipeline logic itself (triggers only)
- Real-time or WebSocket-based update notifications
- Per-game freshness (this is per-team aggregate)
- Freshness indicators on the schedule page (games have their own dates)
- Any terminology changes (E-178 handles all of that)

## Success Criteria
- Adding a team automatically starts a background stat update; no "Update Stats" click required
- Merging teams automatically starts a background stat update on the kept team
- Opponent detail and print pages show game coverage indicators
- Admin users see a "Link" action on schedule cards for unscouted opponents
- Opponent detail pages with no data show actionable empty states
- An empty teams list shows a welcome state with a CTA to add a team
- All existing tests pass with no regressions

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-181-01 | Auto-sync on team add and after merge | DONE | None | - |
| E-181-02 | Game coverage indicators on dashboard pages | DONE | None | - |
| E-181-03 | Dashboard empty states, schedule links, and welcome state | DONE | E-181-01, E-181-02 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Auto-Sync Trigger Pattern

**Epic-level prerequisite:** E-178 must be complete before this epic is dispatched. E-178 establishes the terminology that flash messages in this epic build on, and modifies the same route handlers and templates.

Both auto-sync triggers follow the same pattern: after the successful database operation (insert or merge), enqueue a background pipeline run using the existing `run_member_sync` or `run_scouting_sync` from `src/pipeline/trigger.py`. The confirm_team and merge POST handlers may not currently accept a `BackgroundTasks` parameter -- if not, one must be added to the function signature.

**Team add (admin.py confirm_team POST handler):**
Currently the handler inserts the team and flashes "Use the **Update Stats** button in the table to load stats for this team." (E-178 text). After this epic, it should instead enqueue a background sync and flash something like "Stats updating in the background." The flash message must use E-178's established terminology.

**Merge (admin.py merge POST handler):**
Currently the handler merges teams and flashes "Click Update Stats to load fresh data." (E-178 text). After this epic, it should enqueue a background sync on the kept team and flash something like "Teams merged. Stats updating in the background."

**Guard:** Both triggers must check `crawl_jobs` for an already-running job on the target team before enqueuing. If a job is already running, skip the auto-trigger (the existing job will complete). The existing sync endpoint already has this guard pattern (admin.py: "Update already in progress for {team_name}.").

**Membership routing:** Use `run_member_sync` for member teams, `run_scouting_sync` for tracked teams. The `membership_type` column determines which pipeline to invoke.

### TN-2: Game Coverage Query

The freshness indicator shows game coverage, not sync timestamps. The query derives two values from the `games` table:

- **Most recent game date**: `MAX(game_date)` for the team
- **Game count**: `COUNT(*)` for the team

**Query shape:** The `games` table uses `home_team_id` / `away_team_id` (not a single `team_id`). The query must match on either column: `WHERE (home_team_id = ? OR away_team_id = ?) AND status = 'final'`. Only completed games (status = 'final') should be counted -- scheduled or in-progress games are not "data the coach is looking at."

Display format: `"Through [date] ([N] games)"` -- e.g., "Through Mar 25 (5 games)". When no games exist, show nothing (the empty state handles that case).

The query should be a reusable helper (e.g., in `src/db/` or inline in the dashboard route) since it's used on 2 pages: opponent detail and print report.

**Scope:** Opponent teams only (scouting context). Member team dashboard pages are out of scope for this epic.

### TN-3: Schedule Card Micro-CTA

On dashboard schedule cards, opponents with `resolution_status != 'resolved'` (or no scouting data) currently show "Not scouted" as static text. This epic adds a "Link >" micro-CTA next to (or replacing) that text.

- **Admin-only:** The CTA is visible only when the current user has admin role. Non-admin coaching staff see the existing static text. Note: the schedule route handler may not currently pass `is_admin` to the template context -- if not, this must be added to `dashboard.py`.
- **Link target:** `/admin/opponents?filter=unresolved&team_id={team_id}` (filtered to the relevant team's unresolved opponents).
- **Event handling:** The CTA must use `event.stopPropagation()` because the schedule card itself is a clickable link. Without this, clicking "Link" would navigate to the card's destination instead.

### TN-4: Empty States and Welcome State

**Opponent detail empty state (richer):**
When an opponent has no scouting data, the empty state depends on resolution status:
- **Linked opponents** (has `public_id`): Heading: "No scouting data yet." Subtext: "Stats will appear after the next update."
- **Unlinked opponents** (no `public_id`): Heading: "This opponent isn't linked to GameChanger yet." Subtext for admin users: a link to the resolution workflow. Subtext for non-admin users: "Ask your admin to link this team."

**Welcome state (new users):**
When the teams list is empty (no teams in the database), the teams page shows: Heading: "Welcome to LSB Baseball." Subtext: "Get started by adding your first team." with a CTA button linking to the add-team flow (`/admin/teams/add`). This replaces the current empty table.

## Open Questions
None.

## History
- 2026-03-29: Promoted from IDEA-055. Expert consultations completed (UXD, coach, DE).
- 2026-03-29: Created as DRAFT. Coach's game-coverage approach adopted over sync-timestamp design.
- 2026-03-29: Codex spec review. 6 findings, all accepted: phantom pages removed, query shape fixed, E-178 dep explicit, is_admin route gap noted, file conflict resolved, empty state text specified.
- 2026-03-29: Epic set to READY.
- 2026-03-31: Epic set to ACTIVE. Dispatch started.

- 2026-03-31: All stories DONE. E-181-01: 5 MUST FIX + 2 SHOULD FIX from CR round 1, all fixed in round 2. E-181-02: clean. E-181-03: 2 SHOULD FIX dismissed (nested anchors per AC/TN, #add-team adaptation).
- 2026-03-31: CR integration review: APPROVED, 1 SHOULD FIX dismissed (noqa annotation follows existing pattern).
- 2026-03-31: Codex code review: 2 findings. 1 fixed (Link CTA showed for resolved opponents), 1 dismissed (welcome CTA #add-team is correct adaptation).
- 2026-03-31: Documentation assessment: Trigger 5 fires (new feature ships -- auto-sync, game coverage indicators, empty states, welcome state, schedule link CTA). `docs/coaching/README.md` says "A coaching dashboard is coming soon" -- the dashboard is live and this epic adds user-facing features coaches will encounter. Docs-writer dispatch warranted for `docs/coaching/` updates. However, no docs-writer dispatch is possible from this closure context -- flagging for main session to dispatch if desired.
- 2026-03-31: Context-layer assessment:
  - Trigger 1 (new convention): YES -- _prepare_auto_sync/_enqueue_from_prep pattern for background task resilience (try/except around auto-sync, separating DB work from async add_task).
  - Trigger 2 (architectural decision): NO -- uses existing pipeline triggers, no new technology.
  - Trigger 3 (footgun discovered): YES -- status='completed' vs 'final' discrepancy in story spec vs codebase (AC-6 specified 'final' but codebase uses 'completed').
  - Trigger 4 (agent behavior change): NO.
  - Trigger 5 (domain knowledge): YES -- coaches think in games not sync dates; "Through [date] ([N] games)" is the coaching-friendly freshness format.
  - Trigger 6 (new CLI/workflow): NO.
  - Verdicts: 3 YES (triggers 1, 3, 5), 3 NO (triggers 2, 4, 6). Claude-architect dispatch warranted to codify findings.
- 2026-03-31: Ideas review: No CANDIDATE ideas have E-181 as an explicit blocker. IDEA-035 (Opponent Page Redesign) partially addressed by E-181's empty states and freshness indicators; remaining scope (proactive flags, PDF export) unchanged.
- 2026-03-31: Epic COMPLETED.

### Spec Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Codex iteration 1 | 6 | 6 | 0 |
| **Total** | **6** | **6** | **0** |

### Implementation Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-181-01 | 7 | 7 | 0 |
| Per-story CR -- E-181-02 | 0 | 0 | 0 |
| Per-story CR -- E-181-03 | 2 | 0 | 2 |
| CR integration review | 1 | 0 | 1 |
| Codex code review | 2 | 1 | 1 |
| **Total** | **12** | **8** | **4** |
