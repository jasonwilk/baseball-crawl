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

> **QUARANTINE (2026-06-12)**: The Opponent Flow (dashboard) surface described below is **quarantined and parity-excluded** -- see `.claude/rules/quarantine.md`. The reports flow is the sole forward scouting/delivery surface. The comparison table and conventions below are retained as a description of how the surviving code behaves; they are NOT a forward mandate to keep the dashboard in feature parity with reports.

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

**Feature parity principle (QUARANTINE -- reports is the SOLE forward surface)**: The dashboard/opponent-flow surface is quarantined (see `.claude/rules/quarantine.md`), so there is no longer a two-surface parity obligation. New scouting data features (stat, callout, visualization) target the **reports flow only** -- do NOT scope new work to the dashboard, and do NOT treat the dashboard as a parity target during epic formation. The shared-first design discipline still applies for the protected-core seams that survive in `src/api/db.py` (e.g. `get_pitching_workload`), but only because the reports flow consumes them -- not to keep two surfaces in step. The historical two-surface parity is frozen, not forward.
