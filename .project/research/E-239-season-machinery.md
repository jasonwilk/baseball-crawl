# E-239 (D2) — Season-Machinery & Cascade-Table Inventory (data-engineer)

**Author**: data-engineer (consultation recon for E-239 / roadmap slice D2)
**Date**: 2026-06-16
**Status**: Advisory reconnaissance. Sibling to `E-239-deletion-inventory.md` (owned by `se`).
**Scope**: Answers PM's three refined DE asks. Concrete file/function/table refs.
All line numbers verified against `main` on 2026-06-16; treat as drift-prone — re-grep before editing.

---

## Q1 — Season-machinery inventory (file/function level)

### Framing correction (important for the D2 story author)

The roadmap (§5/§7) says "keep only the year-only/current-season derivation
`derive_season_id_for_team()`'s year-only path." **There is no separable
multi-season path *inside* `derive_season_id_for_team`.** That function — and its
sibling `derive_season_id_for_team_with_fallback` — always derives exactly ONE
`season_id` for ONE team. It is inherently single-season; there is nothing to
strip from it. The removable "multi-season machinery" is the **season-SELECTION**
layer and the **cross-season-CAREER** aggregation that sit ABOVE the derivation
primitive, and they are entirely in the (quarantined) dashboard surface.

### KEEP — reports path + all loaders depend on these (protected core)

| Symbol | Location | Why it stays |
|---|---|---|
| `derive_season_id_for_team()` | `src/gamechanger/loaders/__init__.py:61` | Single-season derivation. Called by every loader. |
| `derive_season_id_for_team_with_fallback()` | `__init__.py:81` | Same logic + `SeasonDerivation.fallback_used` telemetry. Reports call it at `generator.py:1682`. Year-only fallback rules at `:114` (`season_year IS None → current year`) and `:116-122` (program_type→suffix, else year-only). |
| `ensure_season_row()` | `__init__.py:125` | Idempotent `seasons` row writer; FK target for `season_id_used`. |
| `seasons` table | schema | FK target; per-report game filter. |
| Reports `_query_batting` / `_query_pitching` | `src/reports/generator.py:403` / `:445` | Read `player_season_*` with a SINGLE fixed `season_id` (`WHERE psb.team_id=? AND psb.season_id=?`, `:432`/`:484`). Reports NEVER enumerate seasons. |
| `season_year` reads in reports | `generator.py:365-371`, `:1436`, `:1539-1576`; `renderer.py:612` | Single-team, single-season display metadata + public-API backfill. NOT cross-season arithmetic. |
| `starter_prediction.py` "recency" weighting | `src/reports/starter_prediction.py:~742` | Within-report recency over the report's own game window — NOT cross-season. |

Callers of the derivation primitive (all KEEP — loaders): `game_loader.py:233`,
`schedule_loader.py:59`, `roster.py:124`, `season_stats_loader.py:131`,
`scouting_loader.py:108,183`, `spray_chart_loader.py:95`,
`scouting_spray_loader.py:186,335`. (Note: `season_stats_loader` itself is removed
with member-sync — see Q3 — but the derivation function it calls stays for the
surviving loaders.)

### REMOVE — the actual multi-season machinery (ALL dashboard-only)

Verified: every consumer of each symbol below is in `src/api/routes/dashboard.py`
(grep'd `src/` for callers — zero non-dashboard consumers).

| Symbol | Location | What it is | Consumers |
|---|---|---|---|
| `get_available_seasons(team_id)` | `src/api/db.py:2316` | Season ENUMERATION (`UNION DISTINCT season_id ... ORDER BY season_id DESC`) | `dashboard.py:397, 572, 757, 911, 1305, 1547, 1791` |
| `_pick_season_for_year()` | `src/api/routes/dashboard.py:157` | Season SELECTION-by-year | `dashboard.py:399, 575, 759, 913, 1307` + `?season_id=`/`?year=` query-param handling (`:395-405, 570-583, ...`) |
| `get_player_profile(player_id)` | `src/api/db.py:1103` | CROSS-SEASON career profile (`batting_seasons` + `pitching_seasons` lists across seasons, `ORDER BY psb.season_id DESC` `:1151`) | `dashboard.py:2235` (route `player_profile` `:2215`) + its template |
| `get_team_batting_stats` / `get_team_pitching_stats` | `src/api/db.py:~111` / `~204` | Single-season-scoped dashboard stat reads; each embeds a "most-recent season" selector (`SELECT season_id FROM seasons ORDER BY season_id DESC LIMIT 1`, `:162-168` / `:254-260`) | `dashboard.py:649, 766` |

**Direction for the D2 story**: state that the removal target is the dashboard's
season-selection + cross-season-career layer (the table above), NOT the derivation
primitive — so an implementer does not hunt for a nonexistent "multi-season path"
inside `derive_season_id_for_team`.

---

## Q2 — Cascade-table reconciliation (§4 vs the live DELETE set)

**Roadmap line refs (`generator.py:2197-2210`) are STALE.** The live helper is
`_delete_team_scoped_data()` at **`src/reports/generator.py:2477`** (DELETE block
`:2489-2511`). It is part of the PROTECTED report-delete cascade
(`cascade_delete_team` `:2514` → report-deletion cleanup; also `cleanup_orphan_teams`
`:2570`). Its DELETE set (9 tables + conditional `teams` + an `opponent_links`
nullify-UPDATE):

| # | Table | Line | §4 quarantined? | Verdict |
|---|---|---|---|---|
| 1 | `team_rosters` | :2489 | no | **PROTECTED-CORE** (reports read rosters) — stays |
| 2 | `player_season_batting` | :2490 | no | **PROTECTED-CORE** (reports read) — stays |
| 3 | `player_season_pitching` | :2491 | no | **PROTECTED-CORE** (reports read) — stays |
| 4 | `scouting_runs` | :2492 | YES | quarantined |
| 5 | `crawl_jobs` | :2493 | YES | quarantined |
| 6 | `coaching_assignments` | :2494 | YES | quarantined (was the scour-caught §4 gap; now closed) |
| 7 | `user_team_access` | :2495 | YES | quarantined — **auth-coupling caveat** |
| 8 | `team_opponents` | :2497 (our_team_id OR opponent_team_id) | YES | quarantined — **Epic-E caveat** |
| 9 | `opponent_links` | :2502 (DELETE our_team_id) + :2506 (UPDATE resolved_team_id→NULL) | YES | quarantined — **Epic-E caveat** |
| — | `teams` | :2511 (gated on `delete_team_rows`) | n/a | stays |

**Reconciliation result**: all 6 §4 quarantined tables
(`opponent_links, scouting_runs, crawl_jobs, user_team_access, team_opponents,
coaching_assignments`) are referenced by the PROTECTED cascade. ✓ No drift between
the §4 row and the live DELETE set. The cascade's other 3 are protected-core stat
tables — not drop candidates.

### CONFIRMED: NOT dropping tables this epic (§6 rule 2)

Audit + confirmation only. **Default = leave all 6 quarantined tables INERT.**
With the tables still present, the cascade's DELETE statements against them are
harmless empty no-ops ⇒ **D2 requires NO cascade rewrite.** A cascade rewrite is
forced only if/when the tables are DROPPED (else `no such table` at DELETE), which
belongs to a FUTURE removal epic.

> "Trivially droppable with zero cascade rewrite" = **none.** Because all 6 are
> referenced by the cascade, dropping ANY of them requires editing
> `_delete_team_scoped_data` to remove its DELETE line. There is no quarantined
> table that the cascade does not touch. So even the "easy" ones (`coaching_assignments`)
> need a one-line cascade edit when their drop epic comes.

### Eventual drop set (future removal epic — documented, NOT for D2)

| Table | Drop difficulty | Pre-drop requirement |
|---|---|---|
| `coaching_assignments` | Easiest — dead multi-user-permissions table (§7 non-goal) | Confirm zero readers; remove cascade line `:2494` |
| `scouting_runs` | Easy — written only by removed scouting pipeline | Inert after D2; remove cascade line `:2492` |
| `crawl_jobs` | Easy — written only by removed member/scouting pipelines | Inert after D2; remove cascade line `:2493` |
| `user_team_access` | **Caveat** | `_get_permitted_teams()` in `src/api/auth.py` reads it for non-admin dashboard access. After dashboard removal, confirm auth no longer reads it. Protected-core auth coupling — do NOT drop blind. |
| `team_opponents` | **Caveat** | Epic E reuses the resolver's `progenitor_team_id` bridging (§4 amendment). ALSO `finalize_opponent_resolution()` in `src/api/db.py` writes it. Retire/rewrite those readers first. |
| `opponent_links` | **Caveat** | Same Epic-E opponent-resolution-ladder reuse caveat as `team_opponents`. |

**Mirror-query reminder** (cleanup-detection mirror invariant, data-model.md): when
the cascade DELETE set is eventually edited, audit
`src/api/routes/admin.py::_get_delete_confirmation_data` (and any row-count/consent
gate) for mirrored references in the same change. (The mirror concerns the 5
cross-perspective STAT tables, not these 9 team-scoped tables — but the discipline
applies to any cascade-surface edit.)

---

## Q3 — `season_fallback` residual + any cross-season machinery beyond it

**`season_fallback` telemetry STAYS (IDEA-077 Option A, shipped E-236-06):**
- `SeasonDerivation.fallback_used` computed in
  `derive_season_id_for_team_with_fallback` (`__init__.py:119`).
- `report_generation_runs.season_fallback` column (operator-only; surfaced on
  `/admin/reports`).
- The coach-visible degraded line was already dropped (`generator.py:2218-2224`:
  `degraded_confidence` keeps ONLY `identity_match_method == 'name_only'`).
No D2 work needed here beyond leaving it intact.

**Is there cross-season machinery BEYOND that telemetry that becomes removable?**

Answer: **No NEW/hidden cross-season machinery beyond what Q1 already names.** I
audited the reports path, the shared `src/api/db.py` layer, dedup, and the
`seasons`-table reads. Findings:

- **Dedup season handling is a within-season correctness GUARD — KEEP.**
  `src/db/player_dedup.py:158` ("deduplicating across seasons") collapses a player
  who appears in multiple seasons to one result row; the merge logic is
  season-scoped (`merge.py:233,249` join on `season_id`). `src/cli/data.py:905,917`
  explicitly BLOCKS cross-season merges. These are dedup-correctness guards, not a
  multi-season feature. Removing them would be a regression, not a cleanup.
- **`season_year` reads in reports are single-season metadata — KEEP** (Q1 table).
- **`config.py:195`** (`SELECT season_id FROM seasons ORDER BY year DESC LIMIT 1`,
  inside `load_config_from_db()`) is a "most-recent season" picker, but it lives in
  the **member-pipeline `CrawlConfig` builder** (`membership_type = 'member'`). It
  is removed *with member-sync orchestration*, not as a separate cross-season
  concern. Flag it so the member-sync removal story includes it.

Net: once the Q1 dashboard season-selection layer and the member-sync orchestration
are removed, the only remaining season-related code is (a) the single-season
derivation primitive (keep), (b) the `season_fallback` telemetry (keep), and (c)
the within-season dedup guards (keep). No additional removable cross-season
machinery exists.

---

## Bonus: what D2 unlocks for Epic C (forward sequencing note)

Reports ARE direct readers of `player_season_*` (`generator.py:426`, `:465`), so
the tables MUST stay through D2 (this is exactly why Epic C deferred the
replace-with-views option). But D2 changes the calculus:

- **Reader set shrinks to single-season only.** Post-D2 readers of `player_season_*`
  = reports `_query_*` (single-season) + `aggregate_parity.py` (operator diagnostic)
  + `canonical_recompute` writer. All multi/cross-season readers leave with the
  dashboard. ⇒ A view replacing the tables would only need to satisfy a
  single-season, single-team report read — far more tractable.
- **Writer set collapses, simplifying provenance.** Surviving writer =
  `canonical_recompute` (`src/db/season_aggregates.py`) via `ScoutingLoader`
  (protected core — reports use it; NOT removed in D2 — only the opponent-flow
  ENTRY points `bb data scout` / `run_scouting_sync` go). The member
  `season_stats_loader.py` — the ONLY producer of `full`/`supplemented` provenance
  rows — is removed with member-sync. ⇒ Post-D2 all NEW season rows are
  `boxscore_only`; the mixed-provenance parity complexity (data-model.md
  "Season-Aggregate Parity") becomes moot for new data (only legacy `full` rows in
  an un-reset prod DB persist).

Recommendation: add a short "what this unlocks" note to the D2 spec so Epic C is
re-planned against the simpler post-D2 reader/writer graph.
