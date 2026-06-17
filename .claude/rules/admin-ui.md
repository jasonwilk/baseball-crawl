---
paths:
  - "src/api/routes/reports_admin.py"
  - "src/api/templates/admin/**"
---

# Admin UI

The admin UI (`/admin/`) is the operator interface for the reports product. It is served by `src/api/routes/reports_admin.py` (route prefix `/admin`) and covers two areas: **reports management** (the live product surface) and **user management** (auth / E-023 infrastructure). All admin routes are gated by `_require_admin` (delegates to the canonical admin predicate in `src/api/auth.py` -- see CLAUDE.md Architecture).

- **Reports list**: `/admin/reports` -- table of all generated reports with status badges, share links, and delete actions. Generation is triggered from here (`POST /admin/reports/generate`, runs in a background task) and from the `bb report generate` CLI; both take any GC `public_id` directly (no `team_opponents` link required).
- **Report delete**: `POST /admin/reports/{id}/delete` removes the report row and its HTML file, and cascade-deletes the report's team data when the team is eligible for cleanup (see the canonical `cascade_delete_team` helper and the Post-Cascade Probe note below).
- **User management**: `/admin/users` lists users; create, edit (`/admin/users/{id}/edit`), and delete (`POST /admin/users/{id}/delete`, cascade) flows manage magic-link/passkey auth artifacts. Admins cannot delete their own account (self-delete prevention).
- **Shared admin subnav**: Admin templates use a `{% include "admin/_subnav.html" %}` partial with `{% with active_tab='...' %}` for consistent sub-navigation across pages.

## Post-Cascade Probe for Retention UI

When an admin route invokes a cascade helper whose contract permits conditional row retention (e.g., `cascade_delete_team` retains the `teams` row when surviving cross-perspective `games` rows still FK-reference it), the route MUST probe the post-cascade database state and emit an accurate flash message reflecting the actual outcome. NEVER assume the cascade performed a full deletion when the helper's contract permits retention.

**Why**: A flash that claims a full deletion after a retention-path cascade is a lie -- the operator reads the flash, refreshes, and sees the row still present. This is an honesty failure even if the underlying cleanup is correct.

**How to apply (report-delete flow)**: `src/api/routes/reports_admin.py::_delete_report` calls `cascade_delete_team(conn, team_id)` for the report's team when it is eligible for cleanup. If a flash distinguishes "team data removed; team row retained because cross-perspective games still reference it" from a full deletion, derive it from a post-cascade `SELECT` on the `teams` row -- the database is ground truth, not a cached flag from the helper. Prefer post-cascade probes (admin-layer concern) over threading retention state through the data helper's return type (data-helper-layer concern): the admin UI is free to change flash wording without touching the canonical helper or its other callers.
