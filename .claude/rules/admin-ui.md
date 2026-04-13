---
paths:
  - "src/api/routes/admin.py"
  - "src/api/templates/admin/**"
---

# Admin UI

The admin UI (`/admin/`) is the **primary operational interface** for routine team management, crawl triggering, and program administration. The `bb` CLI remains available for automation and scripting but is no longer the sole path for day-to-day operations.

- **Team list**: Flat table of all teams at `/admin/teams/`. Columns: team name, program, division (classification), membership badge, active/inactive, opponent count, edit link.
- **Two-phase add-team flow**: Phase 1 = URL input (paste a GameChanger team URL). Phase 2 = confirm page showing resolved team info, gc_uuid status (from reverse bridge lookup), membership radio (`member`/`tracked`, default: `tracked`), optional program dropdown and division dropdown.
- **Edit page**: Program assignment, division, name override, active toggle. Membership type is editable (radio button) as a correction path for misclassification.
- **Crawl triggering**: Admin UI triggers background crawl/load pipelines per-team via `src/pipeline/trigger.py`. Job status tracked in `crawl_jobs` table. See Architecture section for pipeline caller conventions.
- **Opponent resolution**: `/admin/opponents/{link_id}/resolve` provides a GC-search-powered workflow for connecting unresolved opponents to real GC teams. Resolution is a write-through operation via `finalize_opponent_resolution()` (see Architecture). Includes duplicate detection at confirm time (warns if selected team's `public_id` already exists). "No match" dismissal sets `is_hidden=1` (reversible via "Unhide"). Auto-scout triggers in the background when `public_id` is non-null.
- **Dashboard opponent data states**: Opponent lists display three data states: `stats` (scouting stats loaded -- green), `syncing` (crawl job running -- yellow), `scoresheet` (only game data from own team's boxscores -- gray). Opponents are sorted by `next_game_date` ascending (NULLs last), then name.
- **Shared admin subnav**: Admin templates use a `{% include "admin/_subnav.html" %}` partial with `{% with active_tab='...' %}` for consistent sub-navigation across pages.

## Post-Cascade Probe for Retention UI

When an admin route invokes a cascade helper whose contract permits conditional row retention (e.g., `cascade_delete_team` retains the `teams` row when surviving cross-perspective `games` rows still FK-reference it), the route MUST probe the post-cascade database state and emit an accurate flash message reflecting the actual outcome. NEVER assume the cascade performed a full deletion when the helper's contract permits retention.

**Why**: A flash that says `Team "X" deleted.` after a retention-path cascade is a lie — the operator reads the flash, refreshes the teams list, and sees the team still present. This is an honesty failure even if the underlying cleanup is correct.

**Concrete example**: `src/api/routes/admin.py::delete_team` calls `_delete_team_cascade(id)`, then re-queries via `_get_team_by_integer_id(id)`. If the row is still present, the handler flashes `Team "X" data removed; team row retained because cross-perspective games still reference it.` Otherwise it flashes `Team "X" deleted.` The probe uses the same `SELECT` the rest of the admin surface uses — the database is the ground truth, not a cached flag from the helper.

**How to apply**: Prefer post-cascade probes (admin-layer concern) over contract changes that thread retention state through the data helper's return type (data-helper-layer concern). The admin UI is free to add or change flash wording without touching the canonical helper or its other callers.
