# E-178-01: Replace All Remaining Pipeline Jargon Across Templates and Route Handlers

## Epic
[E-178: Teams Page UX Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, all 28 user-visible instances of pipeline jargon across admin templates, dashboard templates, an error template, and route handler flash/error messages are replaced with plain English per TN-1. The UI uses consistent, coaching-friendly terminology across all pages, with "Update Stats" as the unified verb for the data refresh action, "Linked"/"linked" replacing "resolved" in opponent contexts, and consequence-oriented badge labels ("Connected"/"Limited access") on the confirm page.

## Context
E-173-05 cleaned most opponent-related templates but missed team management templates, residual jargon on the opponents page, dashboard empty states, an error page title tag, and route handler flash messages. A comprehensive UXD audit identified the full scope: 18 template occurrences across 9 files plus 10 route handler flash/error message strings in admin.py. This story applies the complete terminology mapping from TN-1 and updates test assertions that reference old labels (per TN-2).

## Acceptance Criteria

**Teams page (teams.html):**
- [ ] **AC-1**: The "Sync" row action button reads "Update Stats".
- [ ] **AC-2**: The "Sync Now" button in the post-merge flash message reads "Update Stats Now".
- [ ] **AC-3**: The flash message text after adding a team reads "Use the **Update Stats** button in the table to load stats for this team." (not "Sync").
- [ ] **AC-4**: The "Last Synced" column header reads "Last Updated".
- [ ] **AC-5**: The "Running..." job status label reads "Updating...".
- [ ] **AC-6**: The "Resolve" link in the duplicate detection banner reads "Merge".
- [ ] **AC-7**: The "Unresolved -- map first" text is replaced with "Not linked -- find on GameChanger first" AND converted from a static `<span>` to a clickable `<a>` link pointing to the opponents page (unresolved filter).

**Edit team page (edit_team.html):**
- [ ] **AC-8**: The "Last Synced" label reads "Last Updated".

**Confirm team page (confirm_team.html):**
- [ ] **AC-9**: The "Discovered" gc_uuid badge reads "Connected".
- [ ] **AC-10**: The "Not available (403)" gc_uuid badge reads "Limited access" (no HTTP status code).

**Merge teams page (merge_teams.html):**
- [ ] **AC-11**: The "Last synced" row label reads "Last updated".

**Opponents page (opponents.html):**
- [ ] **AC-12**: The "Syncing..." pipeline status badge reads "Updating...".
- [ ] **AC-13**: The "Sync failed" pipeline status badge reads "Update failed".

**Dashboard opponent list (dashboard/opponent_list.html):**
- [ ] **AC-14**: The "Syncing" text label and `title="Syncing"` tooltip both read "Updating".

**Dashboard empty states:**
- [ ] **AC-15**: The "Stats not loaded yet." heading on the opponent detail page reads "Stats aren't ready yet."
- [ ] **AC-16**: The "Stats not loaded yet." text on the opponent print page reads "Stats aren't ready yet."

**Route handler flash/error messages (admin.py):**
- [ ] **AC-17**: All 10 route handler flash/error message strings containing pipeline jargon in `admin.py` are updated per TN-1 items #18-#27.

**Sweep and tests:**
- [ ] **AC-18**: No user-visible text in any template (`src/api/templates/**/*.html`) or route handler flash/error message string in `admin.py` contains the words "Sync", "Synced", "Syncing", "Discovered", "Resolve", "Resolved", or "Forbidden" in pipeline/HTTP jargon context. Case-insensitive search of rendered text, excluding URL paths, non-visible HTML attributes (`class`, `id`, `href`, `data-*`), Python identifiers, and test class/function names. User-visible HTML attributes (`title`) are in scope.
- [ ] **AC-19**: All tests that assert on old label text are updated to match new labels per TN-2 -- including 5 pre-existing failing tests in `tests/test_admin_opponents.py` (TestSummaryStatLine and TestResolutionBadges). All existing tests pass with no regressions.

**Error page:**
- [ ] **AC-20**: The 403 error page `<title>` tag reads "Access Denied — LSB Baseball" (not "403 Forbidden").

## Technical Approach
Template string replacements across 9 template files plus 10 route handler flash/error message string changes in `admin.py`, with corresponding test assertion updates. Each change is a text substitution per TN-1, except item #7 which also converts a `<span>` to an `<a>` element. No database changes, no new queries, no functional changes. URL paths and Python identifiers remain unchanged. The implementer should grep test files for old terms to find all assertions requiring updates (approximate locations in TN-2).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-178-02, E-178-03 (both depend on terminology being clean first)

## Files to Create or Modify
- `src/api/templates/admin/teams.html` -- replace 7 jargon terms: "Sync" button labels, "Last Synced" header, "Running..." status, flash text, inline helper text (convert to link), "Resolve" link
- `src/api/templates/admin/edit_team.html` -- replace "Last Synced" label
- `src/api/templates/admin/confirm_team.html` -- replace "Discovered" → "Connected" and "Not available (403)" → "Limited access"
- `src/api/templates/admin/merge_teams.html` -- replace "Last synced" row label
- `src/api/templates/admin/opponents.html` -- replace "Syncing..." and "Sync failed" badges
- `src/api/templates/dashboard/opponent_list.html` -- replace "Syncing" label and tooltip
- `src/api/templates/dashboard/opponent_detail.html` -- replace "Stats not loaded yet." heading
- `src/api/templates/dashboard/opponent_print.html` -- replace "Stats not loaded yet." text
- `src/api/templates/errors/forbidden.html` -- replace `<title>` tag "403 Forbidden" with "Access Denied"
- `src/api/routes/admin.py` -- replace 10 user-visible flash/error message strings per TN-1
- `tests/test_admin_teams.py` -- update assertions referencing old label text
- `tests/test_admin_merge.py` -- update assertions referencing old label text
- `tests/test_admin_opponents.py` -- update 5 pre-existing failing assertions (E-173 stale tests) + docstring

## Agent Hint
software-engineer

## Definition of Done
- [ ] All 28 TN-1 terminology replacements applied
- [ ] AC-18 sweep confirms no remaining pipeline jargon in templates or route handler strings
- [ ] All TN-2 test assertions updated; full test suite passes with no regressions
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- URL paths and Python variable/function names are NOT user-visible and are out of scope. The 10 route handler changes are flash/error message *strings* (user-visible), not function names or URLs.
- Badge label "Connected" was chosen over "Found" and "Linked" -- it tells the coach what they'll get (full stats access), not what the system did. This is UXD's consequence-oriented design.
- Badge label "Limited access" was chosen over "Not available" -- it tells the coach what to expect (partial data), not the HTTP error.
- The inline helper text (item #7) is converted to a clickable link in addition to the text replacement. This is a minor template change (span → a tag with href) that reduces friction by one click.
- "Resolved" in route handler opponent context → "Linked" (consistent with E-173's opponent linking vocabulary).
- "auto-resolved" → "automatically matched" (plain English, preserves manual/auto distinction).
- Tests for admin.py lines 2459 and 2571 only assert on HTTP status codes (400), not response body text. No test assertion updates are needed for those, but the response text will change.
