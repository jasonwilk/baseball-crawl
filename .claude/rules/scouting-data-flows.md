---
paths:
  - "src/reports/**"
  - "src/gamechanger/loaders/scouting*"
  - "src/api/routes/dashboard.py"
  - "src/api/routes/admin.py"
  - "src/api/routes/reports.py"
  - "src/api/templates/dashboard/**"
  - "src/api/templates/reports/**"
  - "src/pipeline/**"
---

# Scouting Data Flows

Two distinct flows produce scouting intelligence. Confusing them causes wrong auth, wrong data source, or wrong lifecycle assumptions.

| | Opponent Flow (dashboard) | Reports Flow (standalone) |
|-|--------------------------|--------------------------|
| **Entry** | `/dashboard/opponents` | `/admin/reports` or `bb report generate` |
| **Auth** | Session + permitted_teams | Web: admin auth. CLI: none. Serving: none (`/reports/{slug}` is public) |
| **Data** | Live DB queries per page load | Frozen HTML snapshot at generation time |
| **Lifecycle** | Persistent (exists while `team_opponents` link exists) | Ephemeral (14-day expiry, deletable) |
| **Data source** | `team_opponents` + scouting pipeline (tracked teams) | Ad-hoc crawl of any GC `public_id` (no `team_opponents` required) |

**Naming convention**: "scouting report" or "opponent scouting" = opponent flow. "Standalone report" or "generated report" = reports flow.

**Architectural conventions**:
- `/reports/{slug}` MUST NOT query stats tables or render Jinja2 templates at serve time -- only `reports` table lookup + file read from disk
- Reports have no `team_opponents` dependency; generation takes any GC `public_id`
- Reports are ephemeral: 14-day expiry, no versioning, no update-in-place
- `src/reports/` is self-contained (`generator.py`, `renderer.py`); neither module is imported by the opponent flow

**Routing note**: Stories modifying `src/reports/`, `src/api/routes/reports.py`, report handlers in `src/api/routes/admin.py`, or `src/api/templates/admin/reports.html` belong to the reports flow. Stories modifying opponent dashboard routes/templates or `src/gamechanger/loaders/scouting_loader.py` belong to the opponent flow.

**Feature parity principle**: When a new data feature (stat, callout, visualization) is added to either scouting surface, it should be considered for both. This is a planning-time consideration, not a dispatch-time gate -- the surfaces have different constraints (reports are frozen HTML with LLM access; dashboard is live with latency limits), so not every feature will appear on both. But scoping to one surface should be a deliberate decision, not an oversight. In practice: design queries and engines as shared-first (reusable modules in `src/api/db.py` or dedicated packages), then adapt presentation per surface. The PM should evaluate both surfaces during epic formation for any scouting-related feature.
