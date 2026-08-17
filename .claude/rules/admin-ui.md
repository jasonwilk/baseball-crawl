---
paths:
  - "src/api/routes/reports_admin.py"
  - "src/api/templates/admin/**"
---

# Admin UI

The admin UI (`/admin/`) is the operator interface for the reports product. It is served by `src/api/routes/reports_admin.py` (route prefix `/admin`) and covers two areas: **reports management** (the live product surface) and **user management** (auth / E-023 infrastructure). All admin routes are gated by `_require_admin` (delegates to the canonical admin predicate in `src/api/auth.py` -- see CLAUDE.md Architecture).

- **Reports list**: `/admin/reports` -- table of all generated reports with status badges, share links, and delete actions. Generation is triggered from here (`POST /admin/reports/generate`, runs in a background task) and from the `bb report generate` CLI; both take any GC `public_id` directly (no opponent-registration step required).
- **Generate has TWO admission gates, and they cover different blind spots -- never collapse them into one.** `POST /admin/reports/generate` refuses (house 303-flash shape, never queued) via:
  1. **The cross-path gate** -- `_a_generation_is_in_flight()` reap-then-counts `reports.status='generating'`, reusing the canonical `reap_stale_generating_reports` (do NOT grow a second reap; same sequence as `reclaim_orphan_reference_data`). Runs BEFORE the semaphore acquire so a refusal cannot leak a slot. Sees OTHER PROCESSES (the `bb report` CLI); blind to the seconds between a click and its `generating` row being written. ⚠ Pass it OUR connection, never `None` -- `_conn_scope(None)` resolves `lifecycle.get_connection`, which fixtures do not patch, pointing it at the real `data/app.db`. ⚠ It calls a reaper that UPDATEs, unlinks files, and COMMITS unconditionally: this route is delete-adjacent, not a pure read.
  2. **The in-process semaphore** -- module-level `BoundedSemaphore(MAX_CONCURRENT_ADMIN_GENERATIONS)`, acquired non-blockingly LAST (after the admin guard and all three URL validations; acquiring earlier lets a rejected URL burn a slot permanently), released in the background-task wrapper's `finally`. Covers exactly the window gate 1 is blind to; cannot see other processes. Load-bearing on one uvicorn worker in one unreplicated container -- tracked-file half pinned by `TestTheCheckedInTopology`, runtime-replication half only by the deployment invariant in `docs/admin/operations.md`.
  Because `reports` has NO source column, gate 1 cannot distinguish a CLI run from this page's own in-flight generation, so **the admin page is effectively ONE-AT-A-TIME** (operator ruling 2026-08-16) and N=2 is reachable only inside that click-to-row window. The `bb report` CLI paths remain uncapped by design; gate 1 makes the admin door defer to them rather than capping them.
- **Report delete**: `POST /admin/reports/{id}/delete` removes the report row and its HTML file, and cascade-deletes the report's team data when the team is eligible for cleanup (see the canonical `cascade_delete_team` helper and the Post-Cascade Probe note below).
- **User management**: `/admin/users` lists users; create, edit (`/admin/users/{id}/edit`), and delete (`POST /admin/users/{id}/delete`, cascade) flows manage magic-link/passkey auth artifacts. Admins cannot delete their own account (self-delete prevention).
- **Shared admin subnav**: Admin templates use a `{% include "admin/_subnav.html" %}` partial with `{% with active_tab='...' %}` for consistent sub-navigation across pages.

## Post-Cascade Probe for Retention UI

When an admin route invokes a cascade helper whose contract permits conditional row retention (e.g., `cascade_delete_team` retains the `teams` row when surviving cross-perspective `games` rows still FK-reference it), the route MUST probe the post-cascade database state and emit an accurate flash message reflecting the actual outcome. NEVER assume the cascade performed a full deletion when the helper's contract permits retention.

**Why**: A flash that claims a full deletion after a retention-path cascade is a lie -- the operator reads the flash, refreshes, and sees the row still present. This is an honesty failure even if the underlying cleanup is correct.

**How to apply (report-delete flow)**: `src/api/routes/reports_admin.py::_delete_report` calls `cascade_delete_team(conn, team_id)` for the report's team when it is eligible for cleanup. If a flash distinguishes "team data removed; team row retained because cross-perspective games still reference it" from a full deletion, derive it from a post-cascade `SELECT` on the `teams` row -- the database is ground truth, not a cached flag from the helper. Prefer post-cascade probes (admin-layer concern) over threading retention state through the data helper's return type (data-helper-layer concern): the admin UI is free to change flash wording without touching the canonical helper or its other callers.
