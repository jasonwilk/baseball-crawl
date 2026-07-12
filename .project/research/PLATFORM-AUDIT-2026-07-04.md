# baseball-crawl — Full Platform Audit: Final Report

**Date:** 2026-07-03 · **Scope:** code, meta-layer (context/agents/skills/docs), and decision audit · **Inputs:** 131 adversarially-verified findings (after de-duplication: ~120 distinct), 3 uncertain items, 26 audited decisions

---

## 1. Executive Summary

**The product core is in better shape than its support layers.** The report-generation pipeline — the only surface anyone uses — has no confirmed high-severity defect in its happy path. The serious problems cluster in exactly the places no failure has yet exercised: the unattended cron path (E-240), deletion/cleanup paths, disaster recovery, and the meta-layer's description of a product that changed underneath it. Eight things matter most:

1. **Two silent data destroyers sit on routine operations.** Deleting a report for opponent X permanently destroys the plays data behind opponent Y's pitching stats when they share a game, and the plays hole can never self-heal (F-H1). Separately, re-running the morning cron on the same day wipes the audit row's report link and triggers a wasteful full duplicate regeneration on the run after that (F-H2). Both are triggered by documented normal workflows; the E-250 plan currently *blesses* the insufficient deletion guards.

2. **The designated safety controls don't do what the project believes they do.** The PII scanner — the sole enforcement behind "credentials MUST NEVER appear in commit history" — is case-sensitive and misses the project's own UPPERCASE credential format end-to-end (F-H3), and in `--staged` mode it scans the working tree, not the blobs that actually commit. There is no CI backstop for anything, despite a 79-second, zero-secret, fully-mockable test suite.

3. **The dispatch machinery itself has two defects that touch every future epic.** The routing table sends the three highest-volume story domains to `general-purpose` spawns that never load the SE/DE/api-scout definitions, checklists, model/effort specs, or memory (F-H4). And the implement skill's closure failure paths are broken as written: the red-suite recovery loop deadlocks for any epic that adds a file (F-H5), and both reset sequences silently destroy uncommitted ancillary edits. These should be fixed *before* E-250 is dispatched.

4. **Timezone naivety is systemic, not incidental.** Three independent date derivations (stored `game_date`, the report's rest-day reference date, morning-run's default target date) all use UTC while the product reasons in venue-local dates. The project already solved this once (`derive_local_date`) and never propagated the fix.

5. **The morning-run feature is not yet cron-grade.** Per-team failure isolation covers only 403s; one transient 5xx/429/connect error aborts the whole run *and* suppresses the summary email that is the system's only missed-run signal. Nothing validates that the alerting channel can actually deliver. The unattended path is the future of the product and currently its most fragile component.

6. **The meta-layer describes a deleted product.** Agent charters, agent memories, rules files, and operator runbooks still teach the dashboard, member sync, ghost schema entities (`PlayerTeamSeason`, `Lineup`), a "can't programmatically refresh tokens" falsehood, and phantom migration numbers. E-250 fixes a vetted slice of this; the audit found a substantially larger remainder, including runbooks that are not executable end-to-end on a fresh machine.

7. **One architecture decision should be reopened.** The stored `player_season_*` tables lost their last external reader and their last non-boxscore writer in E-239; the roadmap's own recorded revisit trigger ("if D2 lands first, revisit and simplify") fired and was never acted on. Query-time derivation would retire the entire parity/footgun apparatus. Every other audited decision held up — several (perspective provenance, dual review, E-250's keep-season_id call) are exemplary.

8. **Disaster recovery is untested and would fail.** A fresh `git clone` cannot build the Docker image (`data/seeds/` was never actually committed — the .gitignore negation is dead), backups are never scheduled by anything in the repo and land on the same disk as the live DB, and known-vulnerable dependency pins have no refresh mechanism.

---

## 2. Confirmed Findings

Findings carry the verifier's adjusted severity. Merged duplicates are noted. Owners use the finding's owning agent (see §7 for the response dockets).

### HIGH (5)

| ID | Finding | Location | Failure | Fix direction | Owner |
|----|---------|----------|---------|---------------|-------|
| **F-H1** | Report deletion cascade destroys shared-game plays another live report depends on; whole-game plays idempotency makes the hole permanent | `src/reports/generator.py:2694` | Delete report for X; X and Y played each other → Y's pitcher FPS%/P-BF plays rows deleted and never re-fetched; silently wrong or blank forever. E-250-02/TN-5 codifies the insufficient guard set. | Add a shared-game/reports-based eligibility guard or scope anchor-pass DELETEs to exclude perspectives with live reports; amend E-250-02 TN-5 | software-engineer |
| **F-H2** | Morning-run idempotency skip wipes `report_id`/`report_slug` from the audit row, causing duplicate regeneration on the next run | `src/reports/morning_run.py:300` | Same-day re-run (documented workflow after `map-opponent`) → skip branch upserts NULLs → run 3 does a full duplicate crawl+generate. Empirically reproduced. | Carry prior slug/id onto the skip slot, or `COALESCE` in the upsert | software-engineer |
| **F-H3** | PII scanner credential patterns are case-sensitive; the project's own UPPERCASE env-var credential format passes clean end-to-end | `src/safety/pii_patterns.py:67` | Pasted `GC_ACCESS_TOKEN=eyJ…` commits with "[pii-scan] … 0 violations" | Compile with `re.IGNORECASE`; add project-specific token key names; regression tests with uppercase forms | software-engineer |
| **F-H4** | agent-routing.md routes SE/DE/api-scout stories to `general-purpose`, so definitions, checklists, model/effort frontmatter, and memory never load during dispatch | `.claude/rules/agent-routing.md:12` | Highest-volume implementation stories run without the Pre-Submission Checklist written to catch recurring bug classes, at default model/effort | Route to the named agents, consistent with the rest of the table | claude-architect |
| **F-H5** | Implement skill's red-gate remediation loop is unexecutable for epics that add files: reset leaves patch-created files untracked, re-apply then fails | `.claude/skills/implement/SKILL.md:558` | Red suite at closure → documented reset → `git apply --check --3way` errors "does not exist in index"; loop deadlocks, inviting ad-hoc git surgery on main. Empirically reproduced; same defect dirties the abort path. | Use `git apply -R --3way` as the symmetric undo (verified working) | claude-architect |

### MEDIUM (49)

**Ingestion & data integrity**

- **All defensive spray rows silently discarded** — `scouting_spray_loader.py:526` + `migrations/001:417` — offense/defense share event ids; UNIQUE omits `chart_type`, so 100% of defensive rows hit INSERT OR IGNORE and are miscounted as idempotent skips; data-model.md's ~16% defensive-coverage claim is false at the DB layer. Fix: widen UNIQUE via migration, stop counting collisions as skips, correct the rule. *(data-engineer)*
- **Systemic UTC-date derivation** *(merges A1a game_date, A1b reference-date, A7 target-date)* — `game_loader.py:594`, `generator.py:2166`, `morning_run.py:447` — evening games file under the next day (skewing rest math, the 7-day window, cross-perspective dedup at UTC midnight); evening report generation and evening manual morning-runs use tomorrow's date. Fix: one operating-timezone convention (env-configured `ZoneInfo`, mirroring `derive_local_date`) applied at all three sites. *(software-engineer)*
- **429 handling: unbounded server-controlled sleep then raise anyway; `RateLimitError` escapes every per-game isolation** *(merges A1a + A7)* — `client.py:499/508`, `exceptions.py:41` — one `Retry-After: 3600` stalls the cron an hour, then aborts the remaining boxscores/run. Fix: cap Retry-After, retry-or-raise-immediately, add RateLimitError to crawl-loop catches. *(software-engineer)*
- **Tier-2 LLM enrichment runs on suppressed starter predictions; template renders the hallucinated narrative under "Not enough games yet"** — `generator.py:2214`, `scouting_report.html:607` — the system prompt *forces* the model to name a pitcher the deterministic engine refused to project. Fix: skip enrichment on `confidence == 'suppress'`; move the template block inside the non-suppress branch. *(software-engineer)*
- **Missing stat-key drift canary** — `game_loader.py:932` — a GC field rename silently zeroes a stat for every player on both teams; verify-aggregates passes (both sides share the corrupted source). Fix: ERROR + `LoadResult.errors` when a core key is absent from ALL rows of a non-empty group; failing-input tests. Belongs with the E-245 scoreboard. *(software-engineer)*
- **Migration runner is not transactional** — `migrations/apply_migrations.py:131` — `executescript()` autocommits per statement; a mid-file failure in a multi-ALTER migration (003, 007, and planned 008 have the shape) wedges the DB into a permanent duplicate-column crash-loop. Empirically reproduced. Fix: wrap file + `_migrations` INSERT in one transaction; correct the false docstring. *(data-engineer)*
- **Scouting crawler keeps a private `_ensure_season_row` bypassing the canonical seam** — `scouting.py:351` — first-writer-wins under DO NOTHING already produced E-241's drift bug; arch-subsystems.md falsely claims consolidation is complete. Fix: delegate to `ensure_season_row`; cheapest folded into E-250-02, which already edits both INSERT sites. *(software-engineer)*

**Concurrency & operations (morning-run reliability cluster)**

- **Per-team failure isolation covers only 403** — `morning_run.py:483` — a transient 5xx/429/connect error on team 1 aborts teams 2-4, records nothing, and suppresses the "always-sent" summary — silencing the very signal that means "investigate." Contradicts operations.md's isolation claim. Fix: broaden the per-team catch; try/finally around `run_morning` so a crash still emails; broaden preflight's catch. *(software-engineer)*
- **Nothing guarantees the summary email** — `cli/report.py:507`, `email.py:52/148` — send result discarded (exit 0 on failure); unset `ADMIN_EMAIL` silently disarms the heartbeat forever; unset `MAILGUN_API_KEY` logs the body and returns True ("sent"). Fix: validate alerting config in non-dry-run preflight; check/retry the send; tri-state the dev fallback. *(software-engineer)*
- **`_upsert_slot` outside per-slot isolation; no `busy_timeout` on any connection; ad-hoc connection setup** *(merges A3 + A5 + A7)* — `morning_run.py:540`, `src/api/db.py:52` — one slot-recording DB error (e.g. "database is locked" from the documented third-writer topology) aborts all remaining teams; zero contention tests exist. Fix: shared connection factory (WAL+FK+busy_timeout ~30s), move the audit write inside isolation, add one contention test. *(software-engineer)*
- **Morning-run holds an open write transaction across network I/O; no-slot runs roll the own-team INSERTs back on close** — `morning_run.py:477` — fresh-DB/pre-season window: WAL write lock held across a multi-team crawl; rolled-back rows re-INSERT every morning. Fix: commit after `ensure_team_row`; never hold a write txn across an HTTP fetch. *(software-engineer)*
- **Process death mid-generation leaves reports stuck at 'generating' forever** — `generator.py:241` — no reaper; admin page meta-refreshes indefinitely; delete button hidden for generating rows, so recovery requires raw SQL; orphan HTML possible. Fix: stale-run reaper in lifespan and/or `cleanup_expired_reports`. *(software-engineer)*

**Security**

- **Magic-link URLs (live 15-min admin credentials) written to logs when Mailgun is unconfigured, with no production guard and a fake success page** — `email.py:52`. Fix: gate the stdout fallback on `APP_ENV != 'production'`; error without the body. *(software-engineer)*
- **Magic-link verification consumes the token and issues a 7-day session on a bare GET** — `auth.py:324` — mail-provider link scanners burn the token (user lockout) and can receive a live session; raw token lands in access logs. Fix: no-side-effect GET interstitial + CSRF-protected POST consume. *(software-engineer)*
- **`pii_scanner --staged` scans working-tree content, not the staged blobs that commit; staged-but-deleted files silently skipped** — `pii_scanner.py:141`. Fix: read `git show :<path>`. *(software-engineer)*

**CLI correctness**

- **`bb data dedup-players --dry-run --execute` silently executes merges** — `cli/data.py:105` — the explicit dry-run flag is accepted and never read. Fix: mutual-exclusion error. *(software-engineer)*
- **`backfill-appearance-order` / `reload-annotated-pitches` exit 0 with `games_with_errors > 0`** — `cli/data.py:567/618` — contradicts the same file's own AC-5 convention; scripted chains proceed over partially-repaired data. Fix: non-zero exit on errors. *(software-engineer)*

**Structure**

- **Entire disk-based twin load flow is production-dead but actively maintained** — `scouting_loader.py:101` + 3 loaders, ~150 pinning tests — nothing writes `data/raw` anymore; the E-247 near-miss (a stat-wiping regression on the LIVE path introduced purely to preserve parity with this dead path) proves the carrying cost is real. Fix: delete the Path branches, `load_all`/`load_dir` surfaces, and their tests. *(software-engineer)*
- **`generator.py` is a 2,792-line multi-responsibility module the admin delete path depends on** — deletion cascade, all report SQL, lifecycle, run records, and a private `_utcnow_iso` imported cross-module all live with the generation stack (admin delete imports httpx/jinja2 transitively). Fix: extract lifecycle/deletion into a client-free module; move `_query_*` toward the db.py seam; publicize the time helper. *(software-engineer)*

**Context layer & agents**

- **testing.md's worked example teaches a wrong API shape (nested `team_season.season.year`) and instructs "spec wins"** — `.claude/rules/testing.md:94` — the cited endpoint doc is wrong the same way; live API/code/fixtures are flat. Following the rule literally silently breaks season-year capture. Fix: api-scout corrects the endpoint doc; CA rewrites the example. *(claude-architect + api-scout)*
- **key-metrics.md lists "Longitudinal" as a tracked metric and cites the deleted member season-stats GS path** — `key-metrics.md:25/16` — half of this is in no E-250 story. Fix: delete/re-fence the Longitudinal bullet; rewrite GS to the appearance_order derivation. *(claude-architect)*
- **ux-designer charter is entirely the deleted dashboard; mandatory pre-read files don't exist** — `.claude/agents/ux-designer.md:85`. Fix: repurpose around report HTML + admin templates, or retire (user decision). *(claude-architect)*
- **software-engineer.md contradicts itself on story-status ownership** — L80-81 says update statuses; L157 and the ecosystem rule say never. Fix: delete steps 5-6. *(claude-architect)*
- **Implement skill closure resets destroy Step 7a ancillary edits (`git checkout -- .` after `git reset HEAD`)** — `implement/SKILL.md:578` — staged-but-uncommitted vision-signals/ideas edits are irreversibly deleted; the "back to pre-Step-8 state" claim is false. Fix: scope the revert to the patch's files; correct the prose. *(claude-architect)*

**Agent memories (all mislead future sessions; all survive E-250 as planned)**

- **baseball-coach MEMORY.md mandates cross-team/multi-season tracking "from day one"** — permanent non-goals presented as day-one MUSTs to a standing planning consultant. *(baseball-coach / claude-architect)*
- **coach coaching-decisions.md lists 4 ghost entities and season-over-season trends as system-served** — same hallucination-anchor class E-250-04 itself names. *(baseball-coach / claude-architect)*
- **ux-designer MEMORY.md pattern library + Key File Paths anchored to deleted dashboard surface** — 4-tab bottom nav, opponent badges, 4 dead file paths. *(ux-designer / claude-architect)*
- **DE etl-patterns.md asserts programmatic token refresh is impossible and prescribes the 403'ing season-stats opponent pipeline** — refuted 3 days after it was written; contradicts working `bb creds` flow. *(data-engineer / claude-architect)*
- **DE MEMORY.md "Core Entity Model" describes ghost tables, cross-team identity as the design, and a Litestream backup that doesn't exist.** *(data-engineer / claude-architect)*

**API docs & runbooks**

- **game-summaries doc still instructs using `game_stream.id` for boxscore/plays** — the exact guidance a 2026-03-18 A/B test proved returns HTTP 500; the correction was applied to the boxscore doc but never here (5 locations). *(api-scout)*
- **opponent-scouting.md's Authenticated Fallback repeats the disproven `game_stream.id` claim and mislabels the public id as `game_stream_id` throughout.** *(api-scout)*
- **15 endpoint docs commit a real, identifiable 14U youth team** (full UUID, `public_id`, name/city, exact 61-29-2 record) — the api-docs rule was literally written *from this data* and the docs were never scrubbed. Fix: sweep all 15 files to the placeholder taxonomy (git history retains the old values; this stops propagation). *(api-scout)*
- **Production runbook never installs the `bb` CLI or any host Python env** *(merges the crontab-example finding)* — `production-deployment.md:138`, `operations.md:234` — Step 2.4 requires `bb` before the stack exists; the cron example and `python scripts/backup_db.py` assume a host env no step creates. Fix: explicit host-setup step or container-exec forms throughout; state the host-vs-container model. *(docs-writer)*
- **operations.md + architecture.md claim the plays pipeline was removed in E-239** — false; every report generation crawls and loads plays, and E-245 was built on that pipeline. *(docs-writer)*
- **`bb creds login` doesn't exist** — prescribed in the hard-fail recovery path, mid-incident. *(docs-writer)*
- **Post-reset guide's health check URL fails in every configuration** (`localhost:8000/health` — refused without override, 404 with it). *(docs-writer)*
- **operations.md/architecture.md document migrations 006/009/012/014/015 that don't exist; the numbers now collide with real, different migrations.** *(docs-writer)*
- **getting-started's out-of-devcontainer path never installs the project** — `bb`, `pytest`, and two of three documented access points all fail verbatim. *(docs-writer)*
- **Deployment-verification steps still expect the deleted dashboard** *(merges production-deployment + cloudflare-access-setup findings)* — trains the wrong sharing model (coach login vs. share links). *(docs-writer)*
- **agent-browsability-workflow.md instructs deleted CLI commands and the deleted /dashboard route** — every command in the doc fails. Fix: delete. *(claude-architect)*

**PM & foundations**

- **ROADMAP.md internally inconsistent** — DRAFT header on a fully-executed roadmap; §0 missing E-241/E-250 rows; §5 D2 prose contradicts what E-239 shipped; L207 follow-up already done by E-241; E-250-05 fixes only one line of this. *(product-manager)*
- **E-193 (browser automation) is READY on a false premise** — agent-browser not installed, motivating dashboard surface deleted. Archive or re-plan. *(product-manager)*
- **Four more READY epics (E-072/E-073/E-174/E-175) stale 3-4 months with drifted premises** — E-073 spec'd against 90 of 120 endpoint docs; E-174/E-175 spec'd against a GC bundle 3+ months unvalidated. Triage before any dispatch; consider a stale-READY re-confirmation rule. *(product-manager)*
- **`data/seeds/` is not in git despite .gitignore claiming it is; Dockerfile COPY breaks any fresh clone** — the `!data/seeds/` negation is dead under the `data/` exclusion; `seed_dev.sql` exists on exactly one machine; documented production deploy is dead on arrival. Fix: `data/` → `data/*`, commit the dir (or delete the orphaned COPY entirely). *(software-engineer)*
- **requirements-dev.txt is 3 runtime deps stale; devcontainer backfills unpinned** — tests run matplotlib 3.11.0 while prod pins 3.10.8. Fix: recompile; add `--no-deps` to the devcontainer editable install. *(software-engineer)*
- **No CI** — full-suite gate and PII scan are process/per-machine only; suite is 79s, zero secrets, fully mockable. Fix: one workflow (pytest + PII sweep + lockfile-drift check). *(software-engineer)*
- **Known-vulnerable pins with no refresh mechanism** — jinja2 3.1.5 (CVE-2025-27516), starlette 0.41.3 (CVE-2025-54121, unauthenticated multipart DoS reachable via POST /login). Fix: coordinated fastapi/starlette bump + `pip-compile --upgrade`; quarterly refresh or pip-audit in CI. *(software-engineer)*
- **Backups never scheduled by anything in the repo, and written to the same disk as the live DB** — the sound `backup.py` is invoked by nothing; disk loss destroys DB and all backups together. Fix: required runbook step + off-disk copy; optionally invoke from morning-run. *(product-manager)*

### LOW (60+, condensed)

**Code (software-engineer unless noted):**
- `team_resolver` catches only `TimeoutException` and bypasses the proxy/pacing posture — a `ConnectError` crashes the whole morning run (`team_resolver.py:93`).
- Missing game-summary scores coerced to 0-0, letting a scoreless doubleheader collapse into one game (`game_loader.py:500`).
- Load-path dedup deletes canonical `boxscore_only` season rows in scopes the end-of-load recompute never rebuilds (`player_dedup.py:850` — latent, multi-season only).
- Dedup detection uses ASCII-only NOCASE, missing accented-name duplicates; diverges from the planner's Unicode fold (`player_dedup.py:201`).
- Unescaped LIKE wildcards create spurious dedup edges that weld legit collapses into refused forks (`player_dedup.py:207`).
- Reconcile `--execute` commits plays mutations per team before discrepancy rows are written; crash window leaves corrections unrecorded (`engine.py:1124`).
- `get_summary_from_db` dedup partition omits `perspective_team_id`, collapsing distinct cross-perspective signals — matters for the E-245 scoreboard (`engine.py:1161`).
- `bb status` hardcodes `data/app.db`, bypassing `resolve_db_path()` *(merged A1d+A2)* (`status.py:22`).
- `build_pitcher_profiles` per-pitcher appearance_order gate undercounts starts on mixed-ao data (`api/db.py:344`).
- Passkey **registration** consume ignores the DELETE rowcount, violating the project's own single-use invariant (`auth.py:595`).
- Dead `bridge.py` module implements the endpoint the rules ban for opponents, with zero-delay clients — an E-239 deletion-set survivor *(merged A2+A6)*. Delete.
- Seven loader docstrings model the banned cwd-relative `sqlite3.connect("./data/app.db")` pattern.
- Cross-perspective game dedup is SELECT-then-INSERT with no DB UNIQUE backstop — narrow cross-process duplicate-game window *(data-engineer)* (`game_loader.py:1100`).
- Morning-run slot idempotency is read-then-act, recorded only after generation — overlap/SIGKILL double-generates (`morning_run.py:387`).
- Report serve can 500 instead of 404 when cleanup unlinks between `is_file()` and `read_text()` (`reports.py:82`).
- Login timing reveals whether an email is registered, defeating the route's stated enumeration protection (`auth.py:317`).
- Report HTML served `Cache-Control: public, max-age=3600`, undermining revocation by up to an hour (`reports.py:85`).
- Cookie Secure flags + dev-bypass guard all fail open on missing/mistyped `APP_ENV` (`auth.py:93`).
- Unauthenticated passkey-options endpoint allows unbounded challenge-row writes (`auth.py:685`).
- Admin denial is per-route opt-in with no sweep test; all POST mutation routes lack non-admin 403 coverage (`reports_admin.py:664`).
- Inline-schema guardrail degrades to whole-file opt-out — one pragma exempts every CREATE TABLE in the file (`test_no_inline_schemas.py:29`).
- Empty `tests/test_crawlers/` package misrepresents where crawler tests live.
- `backfill-appearance-order` reads a disk cache nothing writes anymore, yet CLAUDE.md documents it as live maintenance; silent no-op on any fresh machine.
- Three ghost package dirs (`src/pipeline/` etc.) contain only stale pre-E-239 bytecode; a live docstring references `src.pipeline.trigger` in present tense.
- `discover_opponents` is test-only dead code from the removed discovery surface (`team_resolver.py:149`).
- Two divergent `_utcnow_iso` implementations; one imported cross-module by underscore name; formats invert lexical ordering same-second (`generator.py:225` vs `scouting.py:459`).
- No .dockerignore — .env, live DB, and .git ship to the daemon as build context; one careless `COPY . .` away from baking secrets into layers.
- No lint tooling — adopt ruff (12 current F-class violations found in a read-only pass); explicitly skip mypy for now.
- docker-compose comment points dev ports at a git-ignored file; operations.md mis-states the cloudflared image as `:latest`.
- SE app-conventions.md memory falsely claims DEV_USER_EMAIL auto-creates an `is_admin=1` user (own-memory fix).

**Context layer (claude-architect):**
- Stale migration numbers 009/012/015 + "currently 005" across data-model.md, architecture-subsystems.md, migrations.md — E-250 TN-2 already had to warn implementers about these *(merged A1c+B1)*.
- key-metrics.md documents `pitches_7d` NULL/0 semantics exactly inverted from the (AC-pinned) implementation.
- gc-uuid-bridge.md Storage Rule ("never overwrite gc_uuid") contradicts the deliberate E-211 tracked-team self-heal overwrite the rule's own evidence section cites.
- data-model.md L18-20 describe deleted machinery (sync self-heal, admin division dropdown, seeder/resolver) as live; L32 still says gc_athlete_profile_id "awaits E-104."
- CLAUDE.md ambient sections still frame the dashboard as live (L51/60/172) and point to admin-ui.md for content that no longer exists (L137); L131 presents `_find_duplicate_game` as race-settled without the cross-process caveat.
- architecture-subsystems.md names the renamed deletion helper and the stale "cached boxscore JSON" reconciliation framing.
- api-docs.md structure map: 89 files (actual 120), flows/ listing omits 3 of 4 flow docs including the one CLAUDE.md points at.
- product-manager.md: "Task tool" consultation mechanism doesn't exist in PM's grant; "D1 migrations" is a Cloudflare-era leftover.
- baseball-coach.md still serves USSSA 9U-14U personas; docs-writer.md still directs writing dashboard docs; data-engineer.md Core Entities table names 4 never-existed tables (fix deferred to unscheduled IDEA-092 — cheaper to replace with a pointer to migrations/).
- Coach scouting-pipeline.md memory teaches the deleted-and-403 season-stats pipeline; DE endpoint-schema-notes maps rosters onto `PlayerTeamSeason`; DE season_aggregate_writers "current state" lists deleted callers.
- worktree-guard does no path normalization (double-slash bypass in both modes); commit-interception regexes miss `git -C` forms (epic-archive gate has no second layer); pii-check.sh reports every scanner infra failure as "PII detected"; codex-review Step 7 inverts Phase 4a/4b; filesystem-context teaches the obsolete PM-dispatches model; context-fundamentals cites a nonexistent CLAUDE.md "Workflow" section; plan skill Step 2a's trailing-slash glob never stages file-form research artifacts.

**API docs (api-scout):**
- opponent-scouting.md still claims `/games` returns only completed games (superseded 2026-06-12; the morning-run scheduler depends on the opposite).
- Boxscore doc contradicts itself on IP encoding (Key Observations says integer outs; schema + CORRECTION say float).
- post-search.md omits the punctuation/curly-apostrophe quirks the canonical helper exists to absorb.
- Public games doc omits the perspective-specific-id caution CLAUDE.md carries.
- README Completeness Check says 121 files; actual 120 (plus one duplicated index row).

**Docs/PM hygiene:**
- rebuild-procedure.md says reset "seeds placeholder data" (empty since E-228). *(docs-writer)*
- VISION.md ~45/105 lines describe deleted/de-scoped product, no in-file banner (deliberate deferral — see §3); vision-signals 43-signal backlog, ~60% pre-reframe. *(product-manager)*
- E-221-HANDOFF.md: dead session-handoff in docs/ root with live-looking "pending" section targeting deleted code. *(product-manager)*
- Ideas README index physically corrupted at IDEA-056/060 rows (a silent-partial-edit in the wild); ~15 of ~45 pre-reframe CANDIDATE ideas verified moot/delivered but still active; E-211 archived with Status ACTIVE; one unnumbered, unindexed idea file. *(product-manager)*

---

## 3. Decision Audit Results

17 of 26 audited decisions were plain **SOUND** (including SQLite-with-bespoke-mitigations, DELETE+INSERT recompute shape, perspective provenance, frozen HTML reports, cron-over-scheduler, dual-layer review, uniform dispatch ceremony, the player-dedup component model, and E-250's keep-season_id call — several with exemplary recorded rationale).

### REVISIT — upheld after defense (1)

**Stored `player_season_batting/pitching` tables vs. query-time derivation** *(data-engineer)*
The defense failed on the facts. The roadmap's own recorded revisit trigger ("if D2 lands first, revisit and simplify") fired on 2026-06-17 and was never acted on. Post-E-239: zero `src/api/db.py` readers remain (the only readers are inside `generate_report()`, moments after the same process computed the rows); zero `full`/`supplemented` writers survive, so the provenance guard now protects — and increasingly *freezes* — legacy rows over fresh recomputes; the SUM projection is already factored as shared SQL, making the stored table a materialization of an existing query over ≤35 games × ~15 players. Retiring the tables retires verify-aggregates, aggregate_parity.py, six documented footguns, and the E-247 wipe-hazard class — squarely aligned with the user's repeated root-removal direction. **Recommend: a post-E-250 epic to cut over to query-time derivation, gated by the parity script that was built for exactly this cutover.**

### REVISIT — defense held (3)

- **In-memory crawl with no raw-payload persistence** *(software-engineer)* — Defense held: `play_events.raw_template` is a *designed*, delete-protected repair source (E-245's reload was a zero-fetch offline re-parse); boxscores are re-fetched on every generation and self-heal; the reconciliation scoreboard compares persisted derived views, not raw bytes. Residual actions only: fix the stale raw-first clause in CLAUDE.md; capture a "write-only raw archive" idea for if/when a second pain event lands.
- **Two-artifact vision system (VISION.md + signals parking lot)** *(product-manager)* — Defense held: the alleged rule "bypass" was a user-directed, transparently-recorded promotion; the interim VISION/ROADMAP contradiction is a documented sequencing decision with a one-sentence cost. The agreed remedy — actually run the long-overdue curation session — requires no design change. The execution lag is real; the architecture is not the defect.
- **Three-state `stat_completeness` provenance retained post-E-239** *(data-engineer)* — Defense held: member rows are API-authoritative and NOT re-derivable (the writer and re-fetch path are deleted); the guards never fire on the forward opponent-scouting path; retention was a deliberate, recorded E-239 decision (DE finding S3). Capture a targeted "inspect-and-narrow" cleanup idea; do not delete the guards blind.

### SOUND_BUT_UNDERDOCUMENTED (5) — needs a written rationale, not a change

1. **Nine-agent roster unchanged through the reframe** — record a one-paragraph roster review (retire/refocus ux-designer, docs-writer?) — fold into the curation session.
2. **One-directional context-layer growth** — record the counterweight: a standing size/density budget with an enforcement point (e.g., a "compress/retire?" trigger 7 in the closure assessment); the line-count budget is currently density-gameable.
3. **Persistent agent-memory system (~516KB, no lifecycle policy)** — record when memories get promoted to rules, struck, or evicted, and a per-agent ceiling.
4. **~100-column season tables whose split/advanced columns became permanently unpopulatable in E-239** — one data-model.md sentence marking them dead-by-descope.
5. **Retained write-orphaned tables (`crawl_jobs`, `coaching_assignments`, `user_team_access`)** — an idea capture + data-model.md note so the retention is a decision, not an accident.

---

## 4. Candidate Epics

| # | Epic | Scope | Size | Absorbs | Owners |
|---|------|-------|------|---------|--------|
| **CE-1** | **Dispatch-machinery repair** | Fix the two implement-skill closure defects (F-H5 + Step 7a destruction), agent routing (F-H4), SE status contradiction, worktree-guard normalization, hook regexes, codex-review label, plan-skill glob | **S** | F-H4, F-H5, skill/hook lows | claude-architect |
| **CE-2** | **Scheduled-reports reliability (cron-grade morning-run)** | Slot wipe (F-H2), per-team isolation, summary-email guarantees, `_upsert_slot` isolation + busy_timeout/connection factory, write-txn-across-network, 429 handling, target-date timezone, team_resolver hardening, stuck-'generating' reaper, slot reservation race | **M** | F-H2 + 8 medium + 4 low | software-engineer |
| **CE-3** | **Data-integrity & deletion safety** | Deletion-cascade shared-game guard (F-H1, incl. E-250-02 TN-5 amendment), spray chart_type UNIQUE migration, game_date timezone + backfill, migration-runner transactionality, stat-key drift canary (E-245 alignment), game-dedup DB backstop, 0-0 coercion, dedup fold/wildcard fixes, reconcile atomicity, Tier-2 suppress gate | **L** | F-H1 + 6 medium + 7 low | software-engineer, data-engineer |
| **CE-4** | **Security & PII hardening** | PII scanner case + staged-blob fixes (F-H3), magic-link log/GET-verify fixes, endpoint-doc PII scrub (15 files), APP_ENV fail-safe, rowcount gate, cache-control, timing, options rate-limit, admin sweep test | **M** | F-H3 + 4 medium + 7 low | software-engineer, api-scout |
| **CE-5** | **Truth sweep: context layer, API docs, runbooks** | Everything in B1/B2/B3/B5 not owned by E-250: rules staleness, agent charters + memories, game_stream.id corrections, runbook executability (bb install, health URLs, phantom migrations, dashboard verification), delete agent-browsability doc, PM hygiene (stale READY triage, ideas repair, E-211 flip) | **L** | ~10 medium + ~30 low | claude-architect, api-scout, docs-writer, product-manager (+ each agent's own memory) |
| **CE-6** | **Post-descope simplification & foundations** | Query-time season aggregates (upheld REVISIT), dead-code deletion (disk twin flow, bridge.py, discover_opponents, ghost dirs, backfill retirement), generator.py split, dead-table sweep, CI workflow, dep refresh + vulnerable pins, .dockerignore, data/seeds gitignore fix, backup scheduling, ruff | **L** | upheld REVISIT + 6 medium + ~12 low | data-engineer, software-engineer, product-manager |

**Recommended sequence:**

1. **CE-1 (dispatch repair) first, before anything is dispatched** — F-H4/F-H5 degrade or break every subsequent epic's execution, including E-250's own closure.
2. **Curate-the-vision session (already planned)** — resolves VISION/signals, absorbs the roster-review and memory-lifecycle SOUND_BUT_UNDERDOCUMENTED items, and lets PM triage the stale READY epics and moot ideas in the same sitting.
3. **Dispatch E-250 (already READY)** — with two cheap amendments: the TN-5 deletion-guard caveat from F-H1, and folding the crawler `_ensure_season_row` consolidation into E-250-02 since it already edits both INSERT sites.
4. **CE-2 (morning-run reliability)** — the forward feature is the product's future and its most fragile component; the slot-wipe HIGH is triggered by documented daily workflows.
5. **CE-3 (data integrity)** — sequenced with the E-245 reconciliation-scoreboard resumption so the stat-key canary and reconcile fixes land on the same foundation the scoreboard measures.
6. **CE-4 (security/PII)** — the scanner fix is a quick win that can be pulled forward; the rest is a coherent hardening pass.
7. **CE-5 (truth sweep)** — after E-250 lands, so the sweep corrects the post-descope remainder rather than racing it.
8. **CE-6 (simplification & foundations)** — last, because the aggregate cutover depends on E-250's landed schema and the CI/foundations work benefits from a stabilized tree.

---

## 5. Quick Wins

One sitting, near-zero risk:

- `git apply -R --3way` fix in the implement skill (F-H5) — verified working replacement.
- Route SE/DE/api-scout by name in agent-routing.md (F-H4) — three cell edits.
- `re.IGNORECASE` + uppercase test cases in the PII scanner (F-H3 core).
- Mutual-exclusion check for `--dry-run --execute`; non-zero exits for backfill/reload error counts.
- `bb status` → `resolve_db_path()`.
- COALESCE in `_upsert_slot` (F-H2 core fix is ~2 lines).
- Delete `bridge.py`, `discover_opponents`+tests, empty `tests/test_crawlers/`, ghost `__pycache__` dirs, `docs/E-221-HANDOFF.md`, `docs/agent-browsability-workflow.md`.
- One-line doc corrections: `bb creds login` → real commands; post-reset URL → `:8001`; "seeds placeholder data" → "empty"; key-metrics pitches_7d sentence; migration-number citations; README 120-count; "D1 migrations" → "SQL migrations"; delete SE Work-Authorization steps 5-6; codex-review line 151; plan-skill trailing slash.
- `.gitignore` `data/` → `data/*` + commit seeds (or delete the orphaned COPY).
- Add `.dockerignore`.
- Repair the two corrupted Ideas README rows; flip E-211 to COMPLETED.

---

## 6. Watch List

Uncertain items — worth monitoring, not yet actionable findings:

- **GS aggregate on partially-populated `appearance_order`** (`season_aggregates.py:122`) — NULL rows count as definite non-starts in mixed scopes; the semantics are *documented as intentional* and the pipeline self-heals at generation time, but if legacy NULL rows exist on the live DB, served GS can silently undercount. Check once during CE-3.
- **`FEATURE_PREDICTED_STARTER` stale "temporary" flag** — default-off gate on the flagship card, past its documented removal condition; promote-to-default-on is a deliberately deferred operator decision. Decide it (also note the `os.environ`-vs-`dotenv_values` read inconsistency).
- **Rotated GC refresh token persisted only to container-local `/app/.env`** — chain survives within a container lifetime and the login fallback covers recreation *if configured*; depends on unverified GC invalidation semantics. Cheap insurance: persist the token store into the mounted `./data` volume; escalate the warn-only persist failure.

---

## 7. Reconciliation Plan — Dockets by Owning Agent

*(One line per item; agents respond agree / rebut / accept. Memory-file items are routed to the memory's owner under the own-memory carve-out, with claude-architect as fallback coordinator.)*

### software-engineer (largest docket)
- F-H1 deletion cascade destroys shared-game plays; F-H2 slot wipe; F-H3 PII scanner case-sensitivity (+ staged-blob scan gap).
- Timezone family: game_date UTC, report reference date, morning-run target date.
- 429 sleep-then-raise + RateLimitError isolation gap; team_resolver narrow catch/proxy bypass; 0-0 score coercion.
- Tier-2 enrichment on suppressed predictions; stuck-'generating' reaper; write-txn-across-network; slot idempotency race; serve-route 500 race; `_upsert_slot` isolation + busy_timeout/connection factory; per-team isolation 403-only; summary-email guarantees.
- Auth: magic-link log fallback, GET verify, timing enumeration, APP_ENV fail-open, passkey registration rowcount, passkey-options flood, cache-control.
- CLI: dry-run/execute conflict, exit codes, bb status path.
- Dedup/reconcile: load-path recompute scope, NOCASE fold, LIKE wildcards, commit/audit atomicity, summary perspective partition; pitcher ao gate; stat-key canary.
- Structure: dead disk twin flow, generator.py split, bridge.py, discover_opponents, ghost dirs, dual `_utcnow_iso`, cwd docstrings, backfill retirement, crawler private season writer.
- Testing: admin sweep test, inline-schema pragma granularity, empty test_crawlers.
- Foundations: data/seeds gitignore, requirements-dev recompile + `--no-deps`, CI workflow, jinja2/starlette bumps, .dockerignore, ruff, compose-comment/cloudflared-tag.
- Own memory: app-conventions.md `is_admin` correction.

### data-engineer
- Spray-chart UNIQUE migration (chart_type) + coverage-claim correction; migration-runner transactionality; game-dedup natural-key DB backstop.
- Decision: **query-time season aggregates (upheld REVISIT)** — respond to the cutover case; stat_completeness targeted-cleanup idea; wide-table dead-columns doc sentence.
- Own memory: etl-patterns.md token-refresh rewrite; MEMORY.md Core Entity Model + Litestream; endpoint-schema-notes PlayerTeamSeason; season_aggregate_writers caller list.

### claude-architect
- F-H4 routing table; F-H5 + Step 7a closure resets; worktree-guard normalization; hook commit regexes; pii-check failure labeling; codex-review 4a/4b; filesystem-context dispatch model; context-fundamentals phantom citation; plan-skill glob.
- Rules: testing.md worked example; key-metrics Longitudinal/GS + pitches_7d; gc-uuid-bridge Storage Rule; data-model L18-20/L32; CLAUDE.md ambient dashboard refs + L131 caveat + L137 pointer; migration-number citations; arch-subsystems helper name + "cached JSON" framing; api-docs.md counts/flows.
- Agents: ux-designer repurpose-or-retire (user decision); SE status steps; PM Task-tool/D1 wording; coach USSSA line; docs-writer dashboard charter; DE Core Entities pointer-replacement.
- Delete agent-browsability-workflow.md.
- Decisions to document: context-growth counterweight; memory lifecycle policy; roster review record.

### api-scout
- game-summaries `game_stream.id` corrections (5 sites) + opponent-scouting fallback; completed-games-only claim; boxscore IP self-contradiction; post-search quirks; public-games perspective caveat; README count/duplicate row; **PII scrub of 15 endpoint docs**; re-verify + fix the public-team-profile `team_season` shape backing testing.md's example.

### docs-writer
- Production runbook host-env/bb install + cron/backup command forms; operations.md plays-pipeline claim + `bb creds login` + phantom migrations + cloudflared tag row; post-reset health URL; getting-started out-of-devcontainer path; dashboard-verification rewrites (production-deployment + cloudflare-access-setup); rebuild-procedure seeds sentence.

### product-manager
- ROADMAP consistency pass (header, §0 rows for E-241/E-250, D2 prose, L207); E-193 archive-or-replan; stale-READY triage (E-072/073/174/175) + consider a 60-day re-confirmation rule; ideas README repair + moot-CANDIDATE sweep + unnumbered file + E-211 status; E-221-HANDOFF disposition; VISION/signals via the overdue curation session; backup scheduling as a required deploy step; dead-table retention idea capture; decision-doc items from §3 that need PM sign-off (aggregate cutover epic, raw-archive idea).

### baseball-coach
- Own memory: MEMORY.md L65-72 cross-team/multi-season section → one-line non-goal note + L11 dashboard reference; coaching-decisions.md L11/L19 (season-over-season framing, ghost entities); scouting-pipeline.md SUPERSEDED banner on the 403 pipeline recipes.

### ux-designer
- Own memory: MEMORY.md pattern library + Key File Paths rewrite around surviving surfaces (pending the CE-5/CA charter decision on the agent's future).