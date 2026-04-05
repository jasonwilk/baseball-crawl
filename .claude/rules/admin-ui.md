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
