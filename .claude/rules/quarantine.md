---
paths:
  - "src/api/routes/dashboard.py"
  - "src/api/templates/dashboard/**"
  - "src/pipeline/crawl.py"
  - "src/pipeline/load.py"
  - "src/pipeline/bootstrap.py"
  - "src/pipeline/trigger.py"
  - "src/gamechanger/loaders/opponent_seeder.py"
  - "src/gamechanger/crawlers/opponent_resolver.py"
---

# Quarantined Surfaces

This is the single source of truth for what "quarantine" means in the reports-first product. The reports flow (generate a scouting report for a GameChanger `public_id` and share the link) is the live product; the surfaces scoped by this rule are unused and slated for removal. See `docs/ROADMAP.md` for the reframe and the D1/D2 sequence.

## Quarantine semantics (the four meanings)

A quarantined surface is:

1. **Deprecated** -- it is on the path to removal, not a supported product surface.
2. **Unmaintained** -- no upkeep beyond keeping the app booting. Do not invest in fixes, refactors, or polish here.
3. **Parity-excluded** -- it is exempt from new-feature parity requirements. A new data capability does NOT need to be reflected in a quarantined surface.
4. **Closed to new feature work** -- a story that would route new work into a quarantined surface escalates to PM (see below).

**Quarantine != delete.** Deletion plus import decoupling is D2, a separate, deliberate step. No banner, comment, or rule edit may read as a delete-license. D1 marks; D2 removes.

## Quarantined surfaces

- **Dashboard**: `src/api/routes/dashboard.py` and the dashboard Jinja templates (`src/api/templates/dashboard/**`).
- **Member-team sync**: `src/pipeline/crawl.py`, `src/pipeline/load.py`, `src/pipeline/bootstrap.py`, and `run_member_sync` in `src/pipeline/trigger.py`.
- **Opponent discovery**: `src/gamechanger/loaders/opponent_seeder.py`, `src/gamechanger/crawlers/opponent_resolver.py`, and `run_scouting_sync` in `src/pipeline/trigger.py` (a function-level boundary, alongside `run_member_sync`).

## Highest-priority ban: `resolve_unlinked()` follow -> bridge -> unfollow

The single highest-priority quarantine ban is the `resolve_unlinked()` follow -> bridge -> unfollow path in `src/gamechanger/crawlers/opponent_resolver.py`. New code MUST NOT call into or extend this path. For the full BANNED-PATH detail (why it is banned, what to use instead), see `.claude/rules/gc-uuid-bridge.md`.

## Escalation

If a story would route new feature work into any quarantined surface, escalate to PM rather than implementing it. Quarantined surfaces are closed to new work; PM decides whether the work belongs elsewhere (the reports flow) or should be deferred.

## Scope notes

- **Protected-core seams are NOT quarantined.** Several modules look dashboard-owned by name but serve the reports flow: `src/api/helpers.py` (report Jinja filters), `src/charts/spray.py` (both surfaces), `get_pitching_workload` / `get_pitching_history` / `build_pitcher_profiles` in `src/api/db.py`, and the year-only/current-season derivation in `derive_season_id_for_team()`. These are out of scope for quarantine -- do not mark or treat them as quarantined.
- **Member-ONLY loaders' file-level markers are DEFERRED to D2.** The member-only `loaders/` (schedule/roster/season-stats) share protected-core loader code (`GameLoader` / `PlaysLoader` / `ScoutingLoader`), so file-level inventory and markers for them are intentionally deferred to D2 rather than applied in D1.
