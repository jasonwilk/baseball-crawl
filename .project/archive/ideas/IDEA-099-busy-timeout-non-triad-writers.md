# IDEA-099: Broaden busy_timeout coverage to the non-triad SQLite writers

## Status
`CANDIDATE`

## Summary
E-252-06 routed the scheduled-reports writer triad (admin UI, interactive report CLI incl. `map-opponent`, morning-run cron) through the single `get_connection()` factory, which sets `busy_timeout=30000` + `synchronous=NORMAL`. But the `bb data` maintenance commands (`src/cli/data.py`, ~5 subcommands) and the loader/crawler modules still hand-roll `sqlite3.connect` (some with cwd-relative `./data/app.db`), carrying NO `busy_timeout`. This idea extends the factory (or an equivalent) to those non-triad writers so they also WAIT on a lock overlap rather than immediately raising `database is locked`.

## Why It Matters
Those `bb data` commands and loaders are also SQLite writers on the same WAL file. If an operator runs `bb data reconcile` / `dedup-players` / a loader while the admin UI or morning-run cron holds a write lock, they still hit an immediate `SQLITE_BUSY` instead of the graceful wait the triad now enjoys. E-252 made the scheduled-reports path cron-grade; this closes the same contention gap on the maintenance surface.

## Why It Was Out of Scope for E-252
E-252 is the scheduled-reports reliability epic — its contention fix (06+07) was deliberately scoped to the triad that composes the morning-run path. The `bb data` maintenance writers are a separate operational surface; broadening to them is a distinct, larger change (some use cwd-relative paths that should first route through `resolve_db_path()`) best done as its own slice. E-252-06's Description was corrected during Phase 4b to stop over-claiming "every SQLite writer".

## Rough Timing
Promote if: an operator actually hits a `database is locked` on a `bb data` command during a concurrent write, OR when a broader connection-hygiene sweep is undertaken.

## Dependencies & Blockers
- [ ] None hard. `get_connection(db_path=...)` already accepts an override (E-252-06).

## Open Questions
- Route each `bb data` command through `get_connection(db_path=resolve_db_path(override))` (mirrors the E-252-06 morning-run + E-252-03 map-opponent reroutes)?
- The cwd-relative `./data/app.db` sites should first adopt `resolve_db_path()` (canonical path resolution) — bundle that in.
- Do the loader/crawler modules open their own connections, or are they always passed one? Inventory before scoping.

## Notes
Surfaced by the Phase 4b Codex review of E-252 (P5) and CR's integration review; confirmed the bb-data writers are genuinely out of E-252's triad scope. Domain: data-engineer / software-engineer. Anchors: `src/cli/data.py`, `src/api/db.py::get_connection`, `src/db/paths.py::resolve_db_path`. One of three E-252 closure follow-up candidates (with [[IDEA-097-team-resolver-proxy-pacing-posture]] and [[IDEA-098-unify-prod-detection-is-production]]).

---
Created: 2026-07-06
Last reviewed: 2026-07-06
Review by: 2026-10-04
