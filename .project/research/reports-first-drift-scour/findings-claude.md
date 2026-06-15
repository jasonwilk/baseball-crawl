# Reports-First Drift Scour — Synthesis (CLAUDE-side)

**Date**: 2026-06-15
**Method**: 6 finder lenses (Claude Workflow, 42 agents, 35 candidates) → adversarial verify (LIVE-vs-INERT + already-tracked) → synthesis of 32 verified findings.
**Status**: CLAUDE-side set — reconcile against an independent Codex 5.5-xhigh pass (`codex-prompt.md`).

This set feeds ROADMAP §4/§7 + IDEA files + Epic D2 scope. **Default disposition is "fold into existing tracked work," not "open a new epic."** Only 2–3 findings are genuinely new; all fold into the already-sequenced D1 parity-rule shrink. No new epic.

## Executive Summary

| Verdict | Count |
|---|---|
| ALREADY_TRACKED (confirms coverage, no new action) | 26 |
| NOT_A_REMNANT (refuted / protected-core) | 3 |
| NEW REMNANT — LIVE | 2 |
| NEW REMNANT — INERT | 1 (likely collapses to already-tracked — see I1) |

**Takeaway:** the 2026-06-12 reframe + ROADMAP §4/§7 already captured essentially all vestigial machinery. The only genuinely new remnants are two doc/rule *parity-instruction* leftovers that still point PM toward the quarantined dashboard during reports planning.

---

## NEW REMNANT — LIVE

### L1 (medium) — `.claude/rules/scouting-data-flows.md:17-24,35` — "Feature parity principle" steers reports-epic planning toward the quarantined dashboard
- Loads on `src/reports/**`; CLAUDE.md:127 references it. Body line 35 directs the PM to "evaluate both surfaces during epic formation" — an active forward obligation toward `/dashboard/*` (QUARANTINE→REMOVE, §4:199). ROADMAP §4:187/211-212 reverses this policy and D1 owns execution, but D1 is NOT STARTED and no roadmap line names this specific rule file.
- **Highest-value LIVE remnant** — the only one that can mis-steer *future epic scope*.
- **Disposition:** fold into D1 — when D1 quarantines the dashboard, mark the "Opponent Flow (dashboard)" column QUARANTINED, reframe the line-35 parity principle to reports-only, fix CLAUDE.md:127's pointer. No new ROADMAP row/IDEA.

### L2 (low) — `.claude/rules/key-metrics.md:26` — forward "(parity requirement)" toward the dashboard
- `get_pitching_workload()` genuinely serves both surfaces today (generator.py:1825 + dashboard.py:1581,1814), but the "(parity requirement)" parenthetical asserts an ongoing keep-in-sync obligation §4:211-212 says to drop. The function is protected-core and stays; only the framing is the remnant.
- **Disposition:** drop/rephrase the parenthetical to reports-only; fold into the same D1 parity-rule shrink. No new row.

---

## NEW REMNANT — INERT

### I1 (low) — `crawl_jobs` table (migrations/001:590-602) — member-sync/scouting status substrate
- Producers/consumers all on quarantine-bound surfaces; reports never INSERT. One runtime name-reference on the live path: `generator.py:2201 DELETE FROM crawl_jobs` inside `_delete_team_scoped_data` (empty-set in practice).
- **CAVEAT / reconciliation needed:** the standalone finding treated it as a new untraced sibling, but three sibling-table findings quote §4:208 as already listing `crawl_jobs` verbatim. **If §4:208 lists `crawl_jobs`, this collapses to ALREADY_TRACKED → zero new INERT remnants.** Top Codex-reconciliation item.
- **Disposition:** fold into §4:208; remove the generator.py:2201 DELETE in the same removal-epic change. Cheap to leave.

---

## ALREADY_TRACKED — coverage confirmed (deduped to 7 clusters)

- **A — Dashboard surface** (multi-season player profile, `get_player_profile()` career aggregation, multi-season opponent detail) → §4:199 + §5 D2:348. `player_season_*` kept-until-D2 (§5:318-319).
- **B — Season-selection / multi-season scoping** (`get_available_seasons`/`_pick_season_for_year`, `_resolve_year_and_team`) → §4:206 + §4:199 (dashboard-only callers) + §3 + IDEA-077.
- **C — season_fallback / year-only derivation** (the named archetype, fully traced: `derive_season_id_for_team_with_fallback`/`fallback_used`, `_PROGRAM_TYPE_SUFFIX`, `degraded_confidence`, `_DEGRADED_CONFIDENCE_LINE`, `report_generation_runs.season_fallback`) → §4:207 (Option A DECIDED) + §4:206 + §3:150-160 + §7 + IDEA-077. **E-236 fixes the coach-visible layer; machinery removal is D2.**
- **D — Opponent discovery / tracked-opponent** (`finalize_opponent_resolution`+`first_seen_year`, `find_duplicate_teams` season partitioning + `bb data dedup`, cross-season merge guard, `scouting_runs`, `opponent_links`, `team_opponents`, `user_team_access`) → §4:202 + §4:208 + §4:203 + §7 + §3. **Corrections:** `scouting_runs`/`opponent_links`/`team_opponents` are LIVE write/delete couplings (not INERT — these are the "cascade-logic rewrites" §4:208 anticipates); `user_team_access` INERT-for-admin. Reader is `get_team_opponents` (db.py:797), not "get_all_opponents".
- **E — Import & cascade coupling into reports** (`admin.py:84→trigger.py` import; cascade DELETEs generator.py:2200-2216; `opponent_links` UPDATE generator.py:2213-2216) → §3:118-123 + §4:201/200 + §3:162-163 + §5 D2:344-348 (D2's FIRST story). When D2's cascade-rewrite story is written, enumerate generator.py:2209-2217 explicitly.
- **F — `gc_athlete_profile_id`** (migrations/001:95-102) → §4:205 (leave inert; close E-104) + §7:518-520 + data-model.md:32.
- **G — Doc/config drift** (architecture-subsystems.md dashboard refs; admin-ui.md opponent states; pitch-rules.md dashboard paths; VISION.md Layers 2-4) → clean up during D1/D2 (don't pre-edit); VISION.md → next "curate the vision" (§7:545-548).

---

## Refuted (protected-core / not remnants — do not re-raise)

1. **Season aggregation recompute** (scouting_loader.py:700-800) — reports DO recompute (generator.py:1505→load_team→scouting_loader.py:159); single-season-id aggregation is the §7-sanctioned within-report game filter. KEEP (§3 + Epic C).
2. **`detect_league_level()` program_type branch** (starter_prediction.py:211-278) — `program_type` is a league-type pitch-rule discriminator (hs/usssa/legion), not cross-season machinery; protected-core Tier-1 prediction. Dead branch falls away with dashboard removal.
3. **display-philosophy.md dashboard path entry** — surface-agnostic stat philosophy backing protected-core heat tiers; flagging the `paths:` load-trigger is the context-layer-guard "don't steer when you can define" anti-pattern.

---

## Citation corrections (for accurate D-slice targeting)
- "Cross-season merge blocked" guard is at **`src/cli/data.py:904-921`**, NOT `src/db/player_dedup.py:900-930` (that range is `recompute_season_pitching`).
- `scouting_runs` is **LIVE** (written via `ScoutingCrawler.scout_team` on every generation, generator.py:1453→scouting.py:185/224; never read).

## Codex reconciliation flags (top priority for the 5.5-xhigh cross-check)
1. **I1 `crawl_jobs`** — confirm whether §4:208 already lists it (if yes → zero new INERT).
2. **L1 parity principle** — confirm it's a genuine un-named remnant vs. already-subsumed by §4:212's general direction.
3. **Cluster D LIVE/INERT relabels** — validate the reports-path write/delete couplings.
4. **Citation error** — confirm the cross-season-merge guard location.
