# E-178: Teams Page UX Overhaul

## Status
`COMPLETED`

## Overview
Fix the teams page experience: replace all remaining pipeline jargon with plain English, improve the merge page language, add auto-refresh while jobs are running, and surface error context on failed syncs. Everything that makes the current system feel right without adding new backend features.

## Background & Context

E-173's Goal #4 promised all pipeline jargon would be replaced with plain English. Story E-173-05 delivered this for most opponent templates but missed team management pages, residual jargon on the opponents page, route handler flash messages, and dashboard empty states. A comprehensive UXD front-to-back audit plus journey walk-through identified the complete scope.

**Category A -- Terminology cleanup (28 items across 10 files):**
A UXD string audit identified 25 remaining jargon instances in admin templates and route handlers, plus 2 in dashboard templates, plus 1 error page title tag. Additionally, 5 tests in `test_admin_opponents.py` are currently failing due to E-173's incomplete test updates.

**Category B -- UX experience improvements (template + light query):**
A UXD journey audit walked all major user flows and identified friction points that can be fixed without new backend logic:
1. Auto-refresh while jobs are running (meta refresh tag + yellow banner)
2. Failed sync badge shows error message as tooltip + retry action
3. Merge page uses "canonical" (database jargon) -- should use "keep"/"remove"
4. Minor confusing text: "(concurrent insert)" in an error message

**Expert consultations completed:**
- **baseball-coach**: Validated all improvements. Key feedback on auto-refresh: "Don't assume the coach is staring at the page. The row badges when they come back are what matters." Confirmed "keep"/"remove" for merge page is instant clarity.
- **ux-designer**: Designed concrete solutions for all items. Refined badge labels to be consequence-oriented: "Connected" (coach gets full stats) and "Limited access" (coach gets partial data). Recommended "Not linked" text become a clickable link. Confirmed 28-item string audit is complete.
- **data-engineer**: No concerns with display label changes. `crawl_jobs.error_message` column already exists.
- **software-engineer**: Confirmed test assertions in 3 test files require updates.

**Badge label evolution:**
- gc_uuid "Discovered" badge: Coach proposed "Linked", UXD initially proposed "Found", UXD refined to **"Connected"** -- tells the coach what they'll GET (full stats access), not what the system found. Overrides prior PM decision on "Found".
- gc_uuid "Not available (403)" badge: User decided to drop HTTP code. UXD refined to **"Limited access"** -- tells the coach what to expect (partial data), not the technical reason.

**User decisions:**
- "Resolve" link (teams.html) → **"Merge"** (user overrode UXD's KEEP recommendation)
- Badge labels → **"Connected"** / **"Limited access"** (accepted UXD's refined designs)
- Auto-sync features deferred to follow-up epic (UXD recommendation: ship polish first)

## Goals
- All 28 remaining pipeline jargon instances replaced with plain English
- Merge page uses "keep"/"remove" instead of "canonical"
- Teams page auto-refreshes while jobs are running
- Failed sync badges show error context and offer retry
- "Not linked" text is a clickable link to the resolution workflow
- Minor confusing text cleaned up

## Non-Goals
- Auto-sync on team add or after merge (deferred to follow-up epic)
- Data freshness timestamps on dashboard pages (deferred)
- Richer empty states on opponent detail (deferred)
- Welcome state for new users (deferred)
- Renaming URL routes or Python function/variable names
- Changing the `last_synced` database column
- Any changes to the sync/crawl pipeline logic itself
- Changing test class/function names that use "sync"/"resolved"
- WebSocket or JS-based live updates

## Success Criteria
- No instances of "Sync", "Synced", "Syncing", "Discovered", "Resolve", "Resolved", or "Forbidden" (in pipeline/HTTP jargon context) appear as user-visible text in any admin, dashboard, or error template, or in route handler strings that render as user-visible flash/error messages. Case-insensitive search of rendered text, excluding URL paths, non-visible HTML attributes (`class`, `id`, `href`, `data-*`), Python identifiers, and test class/function names. User-visible HTML attributes (`title`) are in scope.
- No user-visible text on the merge page contains "canonical"
- The teams page auto-refreshes while any team has a running job
- Failed sync badges show the error message as a tooltip and offer a retry action
- The "Update Stats" verb is used consistently across all pages
- All existing tests pass (updated where they assert on old labels or changed behavior)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-178-01 | Replace all remaining pipeline jargon across templates and route handlers | DONE | None | - |
| E-178-02 | Auto-refresh while jobs running + failed badge error display | DONE | E-178-01 | - |
| E-178-03 | Merge page "keep" language + minor text fixes | DONE | E-178-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Complete Terminology Mapping (28 items)

**Teams page (teams.html) -- 7 items:**

| # | Current Term | Location | Replacement |
|---|-------------|----------|-------------|
| 1 | "Sync" (row action button) | line ~137 | "Update Stats" |
| 2 | "Sync Now" (post-merge flash button) | line ~27 | "Update Stats Now" |
| 3 | "Use the **Sync** button in the table to load stats for this team." (flash text) | line ~18 | "Use the **Update Stats** button in the table to load stats for this team." |
| 4 | "Last Synced" (column header) | line ~68 | "Last Updated" |
| 5 | "Running&hellip;" (job status label) | line ~129 | "Updating&hellip;" |
| 6 | "Resolve" (duplicate detection banner link) | line ~50 | "Merge" |
| 7 | "Unresolved &mdash; map first" (static inline helper text) | line ~142 | "Not linked &mdash; find on GameChanger first" AND convert from `<span>` to `<a>` linking to the opponents page (unresolved filter) |

**Edit team page (edit_team.html) -- 1 item:**

| # | Current Term | Location | Replacement |
|---|-------------|----------|-------------|
| 8 | "Last Synced" (label) | line ~42 | "Last Updated" |

**Confirm team page (confirm_team.html) -- 2 items:**

| # | Current Term | Location | Replacement |
|---|-------------|----------|-------------|
| 9 | "Discovered" (gc_uuid badge) | line ~39 | "Connected" |
| 10 | "Not available (403)" (gc_uuid badge) | line ~43 | "Limited access" |

**Merge teams page (merge_teams.html) -- 1 item:**

| # | Current Term | Location | Replacement |
|---|-------------|----------|-------------|
| 11 | "Last synced" (row label) | line ~105 | "Last updated" |

**Opponents page (opponents.html) -- 2 items:**

| # | Current Term | Location | Replacement |
|---|-------------|----------|-------------|
| 12 | "Syncing..." (pipeline status badge) | line ~107 | "Updating..." |
| 13 | "Sync failed" (pipeline status badge) | line ~111 | "Update failed" |

**Dashboard opponent list (dashboard/opponent_list.html) -- 2 items:**

| # | Current Term | Location | Replacement |
|---|-------------|----------|-------------|
| 14 | title="Syncing" (tooltip attribute) | line ~68 | title="Updating" |
| 15 | "Syncing" (text label) | line ~69 | "Updating" |

**Dashboard opponent detail + print (2 items):**

| # | Current Term | Location | Replacement |
|---|-------------|----------|-------------|
| 16 | "Stats not loaded yet." (empty state heading) | opponent_detail.html line ~50 | "Stats aren't ready yet." |
| 17 | "Stats not loaded yet." (empty state text) | opponent_print.html line ~240 | "Stats aren't ready yet." |

**Error page (errors/forbidden.html) -- 1 item:**

| # | Current Term | Location | Replacement |
|---|-------------|----------|-------------|
| 28 | "403 Forbidden — LSB Baseball" (`<title>` tag) | `<title>` element | "Access Denied — LSB Baseball" |

**Route handler flash/error messages (admin.py) -- 10 items:**

| # | Current Term | Location | Replacement |
|---|-------------|----------|-------------|
| 18 | `"Stats will update on next sync."` (merge flash) | line ~1988 | `"Click Update Stats to load fresh data."` |
| 19 | `"Cannot sync an inactive team."` | line ~2288 | `"Cannot update stats for an inactive team."` |
| 20 | `"Cannot sync unresolved team. Map a public ID first."` | line ~2295 | `"Cannot update stats — find this team on GameChanger first."` |
| 21 | `"Sync already in progress for {team_name}."` | line ~2304 | `"Update already in progress for {team_name}."` |
| 22 | `'Sync started for {team_name}.'` | line ~2324 | `'Updating stats for {team_name}.'` |
| 23 | `" Stats syncing in the background."` | line ~2446 | `" Stats updating in the background."` |
| 24 | `"This opponent is already resolved and cannot be manually linked. Disconnect the existing link first."` | line ~2459 | `"This opponent is already linked and cannot be manually connected. Disconnect the existing link first."` |
| 25 | `"Cannot disconnect an auto-resolved link. Only manual links can be disconnected."` | line ~2571 | `"Cannot disconnect an automatically matched link. Only manual links can be disconnected."` |
| 26 | `f"Resolved {link['opponent_name']} via search. Stats syncing in the background."` | line ~2831 | `f"Linked {link['opponent_name']} via search. Stats updating in the background."` |
| 27 | `f"Resolved {link['opponent_name']} via search."` | line ~2840 | `f"Linked {link['opponent_name']} via search."` |

### TN-2: Test Assertions Requiring Updates

The implementer should grep test files for old terms to find all occurrences. Known locations (line numbers approximate):

**tests/test_admin_teams.py:**
- `~282-290` -- docstring "Sync button hint" + asserts `"Sync" in response.text` (flash message)
- `~572-587` -- docstring "Discovered badge" + asserts `"Discovered" in response.text` (now "Connected")
- `~592-606` -- docstring "Not available badge" + asserts `"403" in response.text or "Not available" in response.text` (now "Limited access")
- `~1674-1675` -- `TestSyncRoute` class docstring (class/function names out of scope, but docstrings referencing old terms should be updated)
- `~1747` -- asserts `"Sync+started" in response.headers["location"]` (redirect URL query param -- changes because the route handler string changes)
- `~1785` -- same `"Sync+started"` assertion in tracked-team test
- `~1831-1835` -- `TestTeamsSyncDisplay` class, docstring references "Last Synced column"
- `~1900` -- tests unresolved tracked team indicator text ("Unresolved" / "map first")
- `~1912` -- docstring references "Sync button"

**tests/test_admin_merge.py:**
- `~164` -- asserts `"Resolve" in resp.text` (duplicate banner link text)
- `~614` -- hardcodes flash message `"Stats will update on next sync."` (now changes)
- `~623` -- asserts `"Sync Now" in resp.text`

**tests/test_admin_opponents.py (pre-existing E-173 failures + docstring):**
- `~975` -- docstring "auto-resolved link" (docstring only, no text assertion on response body)
- `~1068-1081` -- `TestSummaryStatLine`: asserts `"2 resolved"` and `"1 unresolved"` in summary line (template now says "X with stats" and "X needs linking"). **Currently failing.**
- `~1083-1092` -- `TestSummaryStatLine`: asserts `"Run Discovery"` in page (removed by E-173). **Currently failing.**
- `~1097-1108` -- `TestResolutionBadges`: docstring "Resolved/Unresolved badges" + asserts `"Unresolved"` in badge text (template now says "Needs linking"). **Currently failing.**
- `~1110-1119` -- `TestResolutionBadges`: docstring + asserts `"Resolved"` in badge text (template now says "Stats loaded" or "Linked"). **Currently failing.**
- `~1135-1145` -- `TestResolutionBadges`: asserts `"bg-green-100"` for "Resolved" badge (E-173 changed "Linked" badge to blue `bg-blue-50`; "Stats loaded" is green). **Currently failing.**

**Note**: Tests for admin.py lines 2459 and 2571 (`test_admin.py:~1126`, `test_admin_opponents.py:~974`) only assert on HTTP status codes (400), not response body text. These tests do not require assertion updates, but the response text they receive will change.

### TN-3: UX Improvement Designs

**Auto-refresh while jobs running (E-178-02):**
When any team in the list has `latest_job_status == 'running'`, the teams page should include a `<meta http-equiv="refresh" content="8">` tag in the `<head>` and display a yellow banner (e.g., "Stats are updating. This page refreshes automatically."). When no jobs are running, neither the meta tag nor the banner should be present. Coach feedback: "Don't assume the coach is staring at the page. The row badges when they come back are what matters."

**Failed badge error display (E-178-02):**
The `crawl_jobs.error_message` column already exists in the schema. The teams list query (`_list_teams_for_admin`) should select it alongside `latest_job_status`. When `latest_job_status == 'failed'`, the badge should: (a) show the error message as a `title=""` tooltip, and (b) include a "Retry" link that hits the existing sync endpoint.

**Merge page "keep" language (E-178-03):**
All user-visible instances of "canonical" on the merge page should be replaced: "Canonical" badge → "Keeping", "Select Canonical Team" → "Which team do you want to keep?", radio label "Keep (canonical team)" → "Keep this team", "Rows to reassign to canonical" → "Rows to reassign to kept team", confirmation text "to the canonical team" → "to the kept team". Hidden input `name="canonical_id"` stays.

**Minor text fix (E-178-03):**
`admin.py:~1800`: `"Team already exists (concurrent insert)."` → `"Team already exists."` (drop parenthetical).

## Open Questions
None.

## History
- 2026-03-28: Created as gap-fill for E-173's incomplete terminology cleanup.
- 2026-03-28: Expert consultations completed (coach, UXD, SE, DE).
- 2026-03-28: Internal review iteration 1. 11 findings; 4 accepted, 7 dismissed.
- 2026-03-28: Codex spec review iteration 1. 3 findings, all accepted.
- 2026-03-28: UXD comprehensive front-to-back audit. Scope expanded from ~8 to 25 items.
- 2026-03-28: UXD journey audit confirmed scope. 6 UX improvements identified.
- 2026-03-28: Codex spec review iteration 2. 4 findings, all accepted.
- 2026-03-28: Epic rescoped to full UX overhaul (4 stories: terminology + auto-sync + auto-refresh + merge language).
- 2026-03-29: UXD holistic design completed. Scope revised per UXD recommendation: auto-sync deferred to follow-up epic. Badge labels refined: "Found"→"Connected", "Not available"→"Limited access" (consequence-oriented). "Not linked" text becomes clickable link. "Stats not loaded yet" added to scope (2 dashboard templates). Epic now 3 stories: terminology cleanup, auto-refresh + failed badge, merge language + minor text. Follow-up items captured as IDEA-054.
- 2026-03-29: UXD deep audit (Flows 7-18) completed. 1 new item: 403 error page title tag. Added as TN-1 #28. Reports page noted as reference implementation for E-178-02.
- 2026-03-29: Epic set to READY.
- 2026-03-31: Epic set to ACTIVE. Dispatch started.
- 2026-03-31: All stories DONE. E-178-01: 2 MUST FIX (test assertions in test_dashboard_opponent_detail.py), both fixed. E-178-02: 1 SHOULD FIX (missing any_running in error path), fixed. E-178-03: clean.
- 2026-03-31: CR integration review: APPROVED, no findings.
- 2026-03-31: Codex code review: 2 findings, both dismissed (meta refresh placement is a base.html constraint, not a defect).
- 2026-03-31: Documentation assessment: No documentation impact. Changes are UI label/text replacements with no new features, architecture changes, or deployment changes.
- 2026-03-31: Context-layer assessment: Trigger 1 (new convention): No. Trigger 2 (architectural decision): No. Trigger 3 (footgun discovered): No. Trigger 4 (agent behavior change): No. Trigger 5 (domain knowledge): No. Trigger 6 (new CLI/workflow): No. No context-layer impact.
- 2026-03-31: Epic COMPLETED.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- Holistic team | 11 | 4 | 7 |
| Codex iteration 1 | 3 | 3 | 0 |
| Codex iteration 2 | 4 | 4 | 0 |
| UXD string audit | 24 items identified | N/A | N/A |
| UXD journey audit (Flows 1-6) | 6 UX improvements | N/A | N/A |
| UXD deep audit (Flows 7-18) | 1 new item (403 title) | N/A | N/A |
| **Total spec findings** | **18** | **11** | **7** |
| Per-story CR -- E-178-01 | 2 | 2 | 0 |
| Per-story CR -- E-178-02 | 2 | 1 | 1 |
| Per-story CR -- E-178-03 | 0 | 0 | 0 |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 2 | 0 | 2 |
| **Total** | **6** | **3** | **3** |
