# E-239 (D2) Deletion & Decoupling Inventory

> SE reconnaissance artifact for E-239 "Decouple imports, then remove unused surfaces" (`docs/ROADMAP.md` slice D2). Verified against the repo on 2026-06-16. All line numbers are point-in-time; re-verify before editing.
>
> **Conventions:** ⚠️ = DO-NOT-DELETE (shared with protected reports core). 🗑️ = delete-safe. ✂️ = adjust/trim (mixed-concern file). ❓ = PM scope decision.

---

## 1. Decoupling shape recommendation

**Recommendation: (a) extraction-then-delete — extract the *surviving* admin surface into a focused module, then delete the doomed `admin.py` wholesale.** Prefer this over (b) trim-in-place / lazy-import.

### Why (a) is the lowest-risk FIRST story and the cleanest end-state

1. **The decouple story becomes purely additive + re-registration.** Create `src/api/routes/reports_admin.py` containing the surviving routes (reports list/generate/delete + their helpers `_get_all_reports`, `_delete_report`) and the route guard (`_require_admin` / `_forbidden_response`, or import the canonical `user_is_admin` from `src.api.auth`). Re-point `src/api/main.py` to import the new router. No behavior change, easy to review, easy to test (app still boots, `/admin/reports` still serves).
2. **Extraction severs ALL four problem imports at once.** The module-level imports that couple admin.py to the deletion set — `from src.pipeline import trigger` (line 84), `from src.gamechanger.bridge import …` (66-69), `from src.gamechanger.team_resolver import …` (71-75), `from src.db.merge import …` (76-82) — all stay behind with the doomed `admin.py`. The new module imports none of them. After extraction, `import src.api.main` no longer transitively imports `trigger → crawl/load`, so the pipeline modules become deletable.
3. **Lowest churn across the epic.** Trim-in-place means every removal story re-edits the same 3400-line file and re-cleans imports, with merge-conflict risk if stories touch adjacent routes. Extraction lets the removal story `git rm` whole files.
4. **No lingering dead imports.** Trim-in-place tends to leave orphaned imports/helpers that later trip linters or confuse reviewers.

### Decision rule for the surviving keep-set (❓ PM owns)

The surviving admin surface = **reports routes (definite)** + possibly **user-management** + **programs** routes.
- The roadmap quarantines dashboard / member-sync / opponent-discovery. **User-management and programs are NOT in that list** — user admin is auth (E-023) infrastructure, not a quarantined surface. So unless PM explicitly scopes them out, they should be treated as KEEP and extracted alongside reports.
- If PM keeps users+programs+reports: extract all three into the new module (or `admin.py` stays but is heavily trimmed — at that ratio either is fine; extraction still preferred for the import-severing benefit).
- If PM deletes user-mgmt-beyond-login + programs too: the new module is reports-only and `admin.py` is deleted entirely — the cleanest possible outcome.

Either way the mechanism is identical: **extract what survives, delete the doomed file + its imports as a unit.**

### Note: `src/cli/data.py` needs the same treatment (second coupling chain, not in roadmap text)

`src/cli/data.py:22-24` imports `from src.pipeline import bootstrap/crawl/load` at module level. These are used only by the `sync`/`crawl`/`load` commands. Because Typer command modules are imported wholesale at CLI startup, deleting the pipeline modules breaks the **entire `bb` CLI** — including the KEEP commands. See §3.

---

## 2. Import-graph inventory

### 2a. Coupling chains that break startup if pipeline modules are deleted without decoupling

| Entry point | Path to deletion-set | Effect if not decoupled |
|---|---|---|
| `src/api/main.py:35` → `src/api/routes/admin.py:84` `from src.pipeline import trigger` → `trigger.py:34-35` imports `crawl`/`load` | app import | **App fails to start** |
| `src/cli/data.py:22-24` `from src.pipeline import bootstrap/crawl/load` | `bb` CLI import | **Entire `bb` CLI fails** (incl. KEEP commands) |
| `scripts/crawl.py`, `scripts/load.py`, `scripts/bootstrap.py` | self-only | scripts break (deleted anyway) |
| tests (see §4) | collection | test collection errors |

### 2b. Modules reachable ONLY from quarantined entry points → 🗑️ delete-safe

Quarantined entry points = dashboard routes, `run_member_sync`/`run_scouting_sync` (trigger.py), member crawl/load orchestration, remove-candidate `bb data` commands, member scripts.

| Module | Sole importer(s) (all deletion-set) |
|---|---|
| 🗑️ `src/pipeline/crawl.py` | trigger, data.py(crawl), scripts/crawl, tests |
| 🗑️ `src/pipeline/load.py` | trigger, data.py(load), scripts/load, tests |
| 🗑️ `src/pipeline/bootstrap.py` | data.py(sync), scripts/bootstrap, tests |
| 🗑️ `src/pipeline/trigger.py` | admin.py (deleted routes), data.py, tests — holds BOTH `run_member_sync` and `run_scouting_sync`; reports call `generator.generate_report` directly, so trigger is fully dead |
| 🗑️ `src/gamechanger/crawlers/roster.py` | `pipeline/crawl.py` only |
| 🗑️ `src/gamechanger/crawlers/schedule.py` | `pipeline/crawl.py` only |
| 🗑️ `src/gamechanger/crawlers/opponent.py` | `pipeline/crawl.py` only |
| 🗑️ `src/gamechanger/crawlers/player_stats.py` | `pipeline/crawl.py` only |
| 🗑️ `src/gamechanger/crawlers/game_stats.py` | `pipeline/crawl.py` only |
| 🗑️ `src/gamechanger/crawlers/plays.py` | `pipeline/crawl.py` only (member plays crawler; reports get plays via ScoutingCrawler) |
| 🗑️ `src/gamechanger/crawlers/spray_chart.py` | `pipeline/crawl.py` only (reports use `scouting_spray`) |
| 🗑️ `src/gamechanger/crawlers/opponent_resolver.py` | data.py(scout/resolve-opponents), `opponent_seeder.py`, trigger — all deletion-set |
| 🗑️ `src/gamechanger/loaders/roster.py` | `pipeline/load.py` only |
| 🗑️ `src/gamechanger/loaders/schedule_loader.py` | `pipeline/load.py` only (reports get schedule via ScoutingLoader) |
| 🗑️ `src/gamechanger/loaders/season_stats_loader.py` | `pipeline/load.py` only (season-stats endpoint is Forbidden for non-owned teams; reports compute aggregates from boxscores) |
| 🗑️ `src/gamechanger/loaders/spray_chart_loader.py` | `pipeline/load.py` only (reports use `scouting_spray_loader`) |
| 🗑️ `src/gamechanger/loaders/opponent_seeder.py` | trigger only |
| 🗑️ `src/api/routes/dashboard.py` | `main.py:38`/`:147` registration + tests; *consumes* shared providers but provides nothing to reports |

### 2c. Modules SHARED with the protected reports core → ⚠️ MUST SURVIVE

| Module | Reports-core importer (the reason it survives) |
|---|---|
| ⚠️ `src/gamechanger/loaders/game_loader.py` | `loaders/scouting_loader.py:39` imports `GameLoader, GameSummaryEntry` at module level → transitively required by `generator.py` |
| ⚠️ `src/gamechanger/loaders/plays_loader.py` | `generator.py:46` imports `PlaysLoader` |
| ⚠️ `src/gamechanger/loaders/backfill.py` | `bb data backfill-appearance-order` (KEEP) + `scripts/backfill_appearance_order.py` |
| ⚠️ `src/gamechanger/crawlers/scouting.py` | `generator.py:40` |
| ⚠️ `src/gamechanger/crawlers/scouting_spray.py` | `generator.py:41` |
| ⚠️ `src/gamechanger/loaders/scouting_loader.py` | `generator.py:47` |
| ⚠️ `src/gamechanger/loaders/scouting_spray_loader.py` | `generator.py:48` |
| ⚠️ `src/gamechanger/loaders/__init__.py` (`derive_season_id_for_team_with_fallback`, `ensure_season_row`) | `generator.py:42-45` |
| ⚠️ `src/api/helpers.py` | report Jinja filters (`format_avg`, `format_date`, `ip_display`); dashboard also consumed it but is a *consumer* |
| ⚠️ `src/charts/spray.py` | reports + dashboard; provider survives |
| ⚠️ `src/reconciliation/engine.py` | `generator.py:52` (`reconcile_game`) + `bb data reconcile` |
| ⚠️ `src/db/player_dedup.py` | `bb data dedup-players` + post-spray dedup |
| ⚠️ `src/reports/generator.py` (incl. `cascade_delete_team`, `is_team_eligible_for_cleanup`, `cleanup_orphan_teams`) | core; admin's `_delete_team_cascade` (952) & `_delete_report` (3265) delegate here |

### 2d. Deletion-risk flags (would be wrongly removed by a naive sweep)

- ⚠️❗ **`src/gamechanger/resolvers/gc_uuid_resolver.py`** — the `progenitor_team_id` Tier-2 bridging logic **Epic E reuses**. Currently imported ONLY by deletion-set callers (`data.py` scout command + `trigger.py`). **After D2 removes those, it has ZERO importers** — a "no importers → delete" heuristic would remove it. **D2 must explicitly PRESERVE it** (and ideally keep/relocate its test `tests/test_gc_uuid_resolver.py`).
- ⚠️❓ **`src/gamechanger/team_resolver.py`** — imported by admin.py (deleted teams/opponents routes), `opponent_resolver.py` (deleted), trigger (deleted), data.py (deleted commands). After D2 it may also be importerless. Preserve if Epic E needs team resolution; otherwise PM may scope it out.
- ⚠️❓ **`src/gamechanger/config.py`** (`load_config`, `load_config_from_db`, `CrawlConfig`) — used ONLY by crawl/load/trigger/bootstrap + member-crawler `__main__` blocks. Reports/scouting do **not** import it. Looks shared but is deletion-set-only → likely fully removable, but FLAG for explicit verification (and `teams.yaml` goes with it).

---

## 3. CLI module split (`src/cli/data.py`)

| Command | Verdict | Notes |
|---|---|---|
| `sync` | 🗑️ | `bootstrap_module.run` (line 79) |
| `crawl` | 🗑️ | `crawl_module.run` (line 114) |
| `load` | 🗑️ | `load_module.run` (line 151) |
| `scout` | 🗑️ | opponent scouting pipeline (ScoutingCrawler/Loader, gc_uuid_resolver, opponent_resolver) — quarantined opponent flow |
| `resolve-opponents` | 🗑️ | OpponentResolver |
| `dedup` | 🗑️ | tracked-team dedup (`src/db/merge`) |
| `repair-opponents` | 🗑️ | back-fills `opponent_links`→`team_opponents` |
| `reconcile` | ⚠️ KEEP | lazy-imports `src/reconciliation/engine.py` inside the function |
| `dedup-players` | ⚠️ KEEP | lazy-imports `src/db/player_dedup.py` |
| `backfill-appearance-order` | ⚠️ KEEP | lazy-imports `src/gamechanger/loaders/backfill.py` |

**Clean removal approach:**
1. Delete the remove-candidate command functions and the module-level imports `bootstrap as bootstrap_module` / `crawl as crawl_module` / `load as load_module` (lines 22-24) **together** — they have no other use.
2. The KEEP commands (`reconcile`, `dedup-players`, `backfill-appearance-order`) already use **lazy in-function imports** for their dependencies, so they have NO module-level coupling to the deletion set. They survive untouched.
3. **Shared helpers to audit before deleting:** the deleted commands use private helpers (`_scout_dry_run`, `_scout_live`, `_run_scout_pipeline`, `_resolve_missing_gc_uuids`, `_load_scouted_team*`, `_select_canonical`, `_format_team`, `_heal_season_year_*`, `_echo_dry_run_config`, `_post_spray_dedup`). Verify none are called by a KEEP command before deleting. From inspection these are scout/dedup-scoped; `_resolve_db_path` and the `_data_group` callback are shared and must stay. `_post_spray_dedup` calls `dedup_team_players` (player_dedup) but is invoked from the scout flow — delete with scout.
4. **Note:** `dedup-players` and `dedup` are different (`dedup-players` = same-team duplicate player entries via `src/db/player_dedup.py`; `dedup` = duplicate tracked *teams* via `src/db/merge.py`). Keep the former, delete the latter — easy to conflate.

---

## 4. Test deletion discrimination

**Discrimination rule:** A test is **🗑️ delete** if every module it imports/exercises is in the deletion set. It is **✂️ adjust** if it imports BOTH deleted and surviving modules. It is **KEEP** if it only touches surviving/protected code. Verify by reading the test's imports + the routes/functions it calls — not just the filename.

### 🗑️ Delete (exercise ONLY deleted surfaces)

| Test | Deleted surface it covers |
|---|---|
| `tests/test_bootstrap.py` | `pipeline/bootstrap.py` |
| `tests/test_trigger.py` | `pipeline/trigger.py` |
| `tests/test_scripts/test_crawl_orchestrator.py` | `pipeline/crawl.py` + scripts/crawl |
| `tests/test_scripts/test_load_orchestrator.py` | `pipeline/load.py` + scripts/load |
| `tests/test_crawlers/test_roster_crawler.py` | member roster crawler |
| `tests/test_crawlers/test_schedule_crawler.py` | member schedule crawler |
| `tests/test_crawlers/test_opponent_crawler.py` | member opponent crawler |
| `tests/test_crawlers/test_player_stats_crawler.py` | member player_stats crawler |
| `tests/test_crawlers/test_game_stats_crawler.py` | member game_stats crawler |
| `tests/test_crawlers/test_plays_crawler.py` | member plays crawler |
| `tests/test_crawlers/test_spray_chart_crawler.py` | member spray_chart crawler |
| `tests/test_crawlers/test_opponent_resolver.py` | opponent_resolver crawler |
| `tests/test_loaders/test_roster_loader.py` | member roster loader |
| `tests/test_loaders/test_schedule_loader.py` | member schedule loader |
| `tests/test_loaders/test_season_stats_loader.py` | member season_stats loader |
| `tests/test_loaders/test_spray_chart_loader.py` | member spray loader + `pipeline/load` |
| `tests/test_opponent_seeder.py` | opponent_seeder |
| `tests/test_config.py` | `gamechanger/config.py` (delete only if config.py is confirmed deleted — see §2d) |
| `tests/test_dashboard.py`, `test_dashboard_auth.py`, `test_dashboard_opponent_detail.py`, `test_dashboard_prediction.py`, `test_dashboard_routes.py`, `test_dashboard_schedule.py`, `test_dashboard_workload.py`, `test_dashboard_year.py` | dashboard routes |
| `tests/test_strike_pct.py` | imports `_compute_*_pitching_rates` from `routes.dashboard`. **These are dashboard-LOCAL duplicates** — reports has its OWN `_compute_pitching_rates` (`generator.py:484`, independent strike_pct calc at 493-503). So this test covers only doomed code → delete. ⚠️ Confirm report-side strike_pct stays covered by `test_report_workload.py` / `test_report_generator.py` so coverage isn't silently lost. |
| `tests/test_admin_teams.py`, `test_admin_opponents.py`, `test_admin_connect.py`, `test_admin_resolve.py`, `test_admin_merge.py`, `test_admin_programs.py`(❓ if programs kept), `test_admin_gc_uuid_edit.py`, `test_admin_delete_cascade.py`(❓ — see ✂️ note) | admin teams/opponents/merge/programs routes |

### ✂️ Adjust (mixed — touch shared/protected code; trim the deleted parts)

| Test | Action |
|---|---|
| `tests/test_cli_data.py` | Remove cases for sync/crawl/load/scout/resolve-opponents/dedup/repair-opponents and the pipeline imports; **keep** reconcile/dedup-players/backfill-appearance-order cases. |
| `tests/test_game_start_time.py` | Imports `GameLoader`(⚠️keep), `ScheduleLoader`(🗑️), `ScoutingLoader`(⚠️keep). Drop the ScheduleLoader assertions; keep game_loader/scouting_loader game-start-time coverage. |
| `tests/test_dedup_integration.py` | Imports `opponent_resolver`; if it also asserts protected dedup behavior, trim the resolver path; otherwise delete. Read before deciding. |
| `tests/test_admin.py`, `tests/test_admin_routes.py` | If they cover the full admin surface, retarget to the surviving reports (+users/programs) routes; drop teams/opponents/sync assertions. |

### KEEP (protected-core — verify they don't import deleted modules)

`test_admin_reports.py`, `test_report_*` (all), `test_scouting_*` (crawler/loader/spray — use scouting modules which survive), `test_plays_loader.py`, `test_reconciliation.py`, `test_player_dedup.py`, `test_backfill_appearance_order.py`, `test_helpers.py`, `test_charts/*`, `test_gc_uuid_resolver.py` (⚠️ keep to protect the Epic-E-reused resolver), `test_team_resolver.py` (❓ keep iff team_resolver survives).

### Test-scope hazards (shared fixtures / conftest)

- **`tests/conftest.py` is CLEAN** — no imports of any deletion-set module (verified). The shared DB/auth fixtures do not pull pipeline/dashboard/member modules, so deleting those modules will not break protected-core test collection via conftest.
- The only cross-cutting hazard is the `routes.dashboard` import in `test_strike_pct.py` (resolved above → delete) and the `ScheduleLoader` import in `test_game_start_time.py` (resolved above → adjust). No protected-core test imports a member crawler/loader.

---

## 5. Template / nav coupling (for the dashboard + admin-route removal stories)

- `src/api/templates/base.html:14` — "Admin" link points to `/admin/teams` (deleted). **Retarget to `/admin/reports`.**
- `src/api/templates/base.html:32-42` — bottom-nav dashboard links (`/dashboard`, `/dashboard/batting`, `/dashboard/pitching`). **Remove** (dashboard deleted). `reports.html` already passes `is_admin_page=True` to suppress this nav on the reports page, but base.html still needs cleanup for any other page.
- `src/api/templates/admin/_subnav.html` — links to `/admin/users`, `/admin/teams`, `/admin/programs`, `/admin/opponents`, `/admin/reports`, and calls the Jinja global `get_unresolved_opponent_count()`. **Rebuild** to only the surviving tabs and **drop the `templates.env.globals["get_unresolved_opponent_count"]` registration** (`admin.py:90`) + its import.
- Admin templates to delete: `confirm_delete.html`, `confirm_team.html`, `edit_team.html`, `merge_teams.html`, `opponent_resolve.html`, `opponents.html`, `teams.html` (+ `programs.html`, `users.html`, `edit_user.html` ❓ if those surfaces are scoped out). Keep `reports.html`, `_subnav.html` (rebuilt).
- Dashboard templates to delete: all 10 under `src/api/templates/dashboard/`.

## 6. Scripts

🗑️ delete `scripts/crawl.py`, `scripts/load.py`, `scripts/bootstrap.py`. KEEP the other 10 (`backup_db.py`, `check_credentials.py`, `refresh_credentials.py`, `regen_report_golden.py`, `reset_dev_db.py`, `smoke_test.py`, `validate_api_docs.py`, `validate_plays_stats.py`, `backfill_appearance_order.py`, `proxy-refresh-headers.py`). Note `tests/test_script_entry_points.py` may assert the deleted scripts exist — adjust it.

## 7. `teams.yaml`

🗑️ delete — referenced only by `pipeline/bootstrap.py`, `cli/data.py` (deleted commands), `scripts/crawl.py`/`load.py`, and `config.load_config`. All deletion-set. Goes with `config.py` (§2d) pending verification.
