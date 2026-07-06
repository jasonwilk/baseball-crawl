# E-256: Post-Descope Simplification & Foundations — DRAFT STUB (audit CE-6)

## Status
`DRAFT`
<!-- Capture stub from the 2026-07-03 platform audit (PLATFORM-AUDIT.md, repo root, UNCOMMITTED).
     Carries the audit's CE-6 scope, absorbed findings, size, owners, sequence. NOT refined: no stories/ACs.
     Refine to READY before dispatch. Do NOT dispatch a DRAFT. -->

## Overview
Retire the machinery the reframe made vestigial and lay the missing foundations. This includes the one architecture decision the audit says should be reopened — the stored `player_season_*` tables lost their last external reader and non-boxscore writer in E-239, and the roadmap's own revisit trigger fired and was never acted on — plus the production-dead disk twin flow, a 2,792-line multi-responsibility module, and the absent CI / dependency-refresh / backup / .dockerignore foundations that make disaster recovery untested and dead-on-arrival.

## Audit Provenance
- **CE #**: CE-6 · **Size**: L · **Owners**: data-engineer, software-engineer, product-manager · **Sequence**: position 8 — **last**, because the aggregate cutover depends on E-250's landed schema and the CI/foundations work benefits from a stabilized tree.
- **§4 scope row (verbatim)**: "Query-time season aggregates (upheld REVISIT), dead-code deletion (disk twin flow, bridge.py, discover_opponents, ghost dirs, backfill retirement), generator.py split, dead-table sweep, CI workflow, dep refresh + vulnerable pins, .dockerignore, data/seeds gitignore fix, backup scheduling, ruff."
- **Absorbs**: the upheld REVISIT decision + 6 medium + ~12 low.

## Absorbed Findings (one-liners copied from the audit)
- **REVISIT — upheld: stored `player_season_batting/pitching` vs query-time derivation** *(data-engineer)* — post-E-239 zero `src/api/db.py` readers remain (only readers are inside `generate_report()`, moments after the same process computed the rows); zero `full`/`supplemented` writers survive, so the provenance guard now freezes legacy rows over fresh recomputes; the SUM projection is already shared SQL over ≤35 games × ~15 players. Retiring the tables retires verify-aggregates, aggregate_parity.py, six footguns, and the E-247 wipe-hazard class. **Roadmap's own revisit trigger ("if D2 lands first, revisit and simplify") fired 2026-06-17 and was never acted on. Recommend: cut over to query-time derivation, gated by the parity script built for exactly this cutover. NEEDS PM/user sign-off before planning.**
- **Entire disk-based twin load flow is production-dead but actively maintained** (`scouting_loader.py:101` + 3 loaders, ~150 pinning tests) — nothing writes `data/raw` anymore; the E-247 near-miss (a stat-wiping regression on the LIVE path introduced purely to preserve parity with this dead path) proves the carrying cost. Fix: delete the Path branches, `load_all`/`load_dir` surfaces, and their tests.
- **`generator.py` is a 2,792-line multi-responsibility module the admin delete path depends on** — deletion cascade, all report SQL, lifecycle, run records, and a cross-module `_utcnow_iso` all live with the generation stack (admin delete imports httpx/jinja2 transitively). Fix: extract lifecycle/deletion into a client-free module; move `_query_*` toward the db.py seam; publicize the time helper.
- **Migration/dead-code residue** — dead `bridge.py` module (implements the endpoint the rules ban for opponents); `discover_opponents` test-only dead code (`team_resolver.py:149`); three ghost package dirs (`src/pipeline/` etc., stale bytecode + a present-tense docstring reference); `backfill-appearance-order` reads a disk cache nothing writes (CLAUDE.md documents it as live — silent no-op on any fresh machine); two divergent `_utcnow_iso` implementations (one imported cross-module by underscore name). Delete/consolidate.
- **`data/seeds/` is not in git despite .gitignore claiming it is; Dockerfile COPY breaks any fresh clone** — the `!data/seeds/` negation is dead under the `data/` exclusion; `seed_dev.sql` exists on one machine; documented production deploy is dead on arrival. Fix: `data/` → `data/*`, commit the dir (or delete the orphaned COPY). *(software-engineer)*
- **No CI** — full-suite gate and PII scan are process/per-machine only; suite is 79s, zero secrets, fully mockable. Fix: one workflow (pytest + PII sweep + lockfile-drift check). *(software-engineer)*
- **Known-vulnerable pins with no refresh mechanism** — jinja2 3.1.5 (CVE-2025-27516), starlette 0.41.3 (CVE-2025-54121, unauthenticated multipart DoS reachable via POST /login). Fix: coordinated fastapi/starlette bump + `pip-compile --upgrade`; quarterly refresh or pip-audit in CI. *(software-engineer)*
- **requirements-dev.txt is 3 runtime deps stale; devcontainer backfills unpinned** — tests run matplotlib 3.11.0 while prod pins 3.10.8. Fix: recompile; add `--no-deps` to the devcontainer editable install. *(software-engineer)*
- **Backups never scheduled by anything in the repo, and written to the same disk as the live DB** — the sound `backup.py` is invoked by nothing; disk loss destroys DB and all backups together. Fix: required runbook step + off-disk copy; optionally invoke from morning-run. *(product-manager)*
- **No `.dockerignore`** — `.env`, live DB, and `.git` ship to the daemon as build context; one careless `COPY . .` from baking secrets into layers. Fix: add `.dockerignore`.
- **No lint tooling** — adopt ruff (12 current F-class violations found); explicitly skip mypy for now. Plus: docker-compose comment points dev ports at a git-ignored file; operations.md mis-states the cloudflared image as `:latest`.
- **Dead-table sweep** (§3 SOUND_BUT_UNDERDOCUMENTED) — retained write-orphaned `crawl_jobs`, `coaching_assignments`, `user_team_access`: idea capture + data-model.md note so the retention is a decision, not an accident. Also the ~100-column season split/advanced columns permanently unpopulatable in E-239 (one data-model.md dead-by-descope sentence).
- **Rest-day reference date — the third (orphaned) UTC site of the merged timezone finding** *(software-engineer)* — the audit's systemic-UTC finding had three sites; E-252 (CE-2) fixed morning-run's target date and E-253 (CE-3) fixed stored `game_date`, but the report's rest-day reference date fell between the two epics and was never fixed. `src/reports/generator.py` stamps `generated_at` via `_utcnow_iso()` and derives `reference_date` from that UTC timestamp, so evening report generations still compute pitcher rest days against tomorrow's date. Fix: derive the reference date through the operating-timezone seam E-252 already introduced (`src/util/timezone.py`), the same way the other two sites were corrected. Small fix, and it pairs naturally with this epic's `generator.py` split (both touch the report generation stack + the `_utcnow_iso` helper this epic already publicizes).

## Non-Goals (boundary vs. adjacent epics)
- Data-integrity/deletion-safety correctness fixes → CE-3 (E-253). This epic is simplification + foundations, not bug-fixing the live path (except the aggregate cutover, which is a structural simplification gated by the parity script).
- Backup scheduling also appears in CE-5's PM docket; it is scoped HERE (foundations) — CE-5 should defer it to CE-6.

## Refinement Notes (for the future planning session)
- **The query-time-aggregate cutover needs explicit PM/user sign-off before it is planned** (audit §7 PM docket + §3 REVISIT). Treat it as its own decision gate; it is the highest-value simplification but also the most invasive.
- data-engineer owns the aggregate cutover + dead-table sweep; software-engineer owns dead-code deletion, generator.py split, CI, deps, .dockerignore, ruff; product-manager owns backup-scheduling requirement + the retention idea capture.
- Consider whether the aggregate cutover should be its own epic separate from the foundations work (different owner, different risk profile) at refinement.

## History
- 2026-07-04: Created as a DRAFT capture stub from the platform audit (CE-6). Not refined; not dispatchable until taken to READY.
