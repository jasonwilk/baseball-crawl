# Ideas Backlog

This directory holds pre-epic ideas: directions, problems, and future plans that are worth remembering but are not yet ready to be structured as epics.

An idea becomes an epic when:
1. A dependency clears (e.g., a blocking epic completes)
2. The pain becomes real (we hit the problem the idea was meant to solve)
3. A strategic decision makes it a priority

Ideas do NOT have stories, acceptance criteria, or assignees. They are low-friction captures.

## Review Cadence
Review this list every 90 days, or when completing an epic. Ask:
- Is any CANDIDATE now unblocked?
- Should any CANDIDATE be promoted or discarded?
- Are there ideas we've already solved implicitly?

## Index

| ID | Title | Status | Review By |
|----|-------|--------|-----------|
| [IDEA-001](IDEA-001-local-cloudflare-dev-container.md) | Local Cloudflare Dev Container | DISCARDED | 2026-02-28 -- superseded by E-009 |
| [IDEA-002](IDEA-002-web-scraping-fallback.md) | Web Scraping Fallback Strategy | CANDIDATE | 2026-05-29 |
| [IDEA-003](IDEA-003-github-epics.md) | Work Management as Agent Interface | CANDIDATE | 2026-05-29 |
| [IDEA-004](IDEA-004-pii-protection.md) | Hard Data Boundaries and PII Protection | PROMOTED | 2026-03-02 -- promoted to E-019 |
| [IDEA-005](IDEA-005-intent-nodes.md) | Directory-Scoped Intent Nodes at src/ Module Boundaries | CANDIDATE | 2026-06-01 |
| [IDEA-006](IDEA-006-epic-lanes-convention.md) | Epic Lanes Convention for Multi-Workstream Epics | CANDIDATE | 2026-06-01 |
| [IDEA-007](IDEA-007-dispatch-coordinator-guardrail.md) | Dispatch Coordinator Guardrail -- Prevent Team-Lead-as-PM Bypass | DISCARDED | 2026-03-07 -- resolved by E-065 |
| [IDEA-008](IDEA-008-plays-and-line-scores.md) | Pitch-by-Pitch Plays and Inning Line Scores Crawling | CANDIDATE | 2026-06-02 |
| [IDEA-009](IDEA-009-per-player-game-stats-spray-charts.md) | Per-Player Per-Game Stats and Spray Charts | CANDIDATE | 2026-06-02 |
| [IDEA-010](IDEA-010-docs-port-map-consistency.md) | Docs Port Map Consistency for Devcontainer + Compose | CANDIDATE | 2026-06-03 |
| [IDEA-011](IDEA-011-investigate-500-endpoints.md) | Investigate HTTP 500 Endpoint Failures | CANDIDATE | 2026-06-04 |
| [IDEA-012](IDEA-012-crawl-orchestration-system.md) | Crawl Orchestration and Scheduling System | DISCARDED | 2026-07-08 -- member-sync pipeline removed (E-239); forward scheduling delivered by E-240 (`bb report morning-run` cron-CLI); ROADMAP §7 bars a standing orchestration system |
| [IDEA-013](IDEA-013-cmux-evaluation.md) | cmux Evaluation for Agent Teams | CANDIDATE | 2026-06-07 |
| [IDEA-014](IDEA-014-mobile-web-api-doc-split.md) | Mobile vs. Web API Documentation Split | CANDIDATE | 2026-06-05 |
| [IDEA-015](IDEA-015-programmatic-auth-module.md) | Programmatic Auth Module | PROMOTED | 2026-03-08 -- promoted to E-077 |
| [IDEA-016](IDEA-016-codex-hardening-and-validation.md) | Codex Hardening and Validation Trail Map | CANDIDATE | 2026-06-07 |
| [IDEA-017](IDEA-017-api-relationship-documentation.md) | API Relationship and Chain Documentation | CANDIDATE | 2026-06-07 |
| [IDEA-018](IDEA-018-fuzzy-llm-opponent-resolution.md) | Fuzzy LLM Opponent Resolution | CANDIDATE | 2026-06-07 |
| [IDEA-019](IDEA-019-retroactive-opponent-stat-crawling.md) | Retroactive Opponent Stat Crawling | PROMOTED | 2026-03-12 -- promoted to E-097 |
| [IDEA-020](IDEA-020-public-endpoint-opponent-ingestion.md) | Public Endpoint Opponent Data Ingestion | PROMOTED | 2026-03-12 -- promoted to E-097 |
| [IDEA-021](IDEA-021-database-migration-process.md) | Database Migration Process Definition | CANDIDATE | 2026-06-07 |
| [IDEA-022](IDEA-022-scouting-flow-doc-schema-mismatch.md) | Scouting Flow Doc / Schema Stat Mismatch | CANDIDATE | 2026-06-12 |
| [IDEA-023](IDEA-023-env-and-db-backup-automation.md) | Automated .env and app.db Backup | CANDIDATE | 2026-06-13 |
| [IDEA-024](IDEA-024-postcreatecommand-refactor.md) | Refactor postCreateCommand into Bootstrap Script | CANDIDATE | 2026-06-13 |
| [IDEA-025](IDEA-025-test-fixture-migration-driven.md) | Migration-Driven Test Fixtures | CANDIDATE | 2026-06-14 |
| [IDEA-026](IDEA-026-context-layer-placement-audit.md) | Context Layer Placement Audit -- Phase 2 | CANDIDATE | 2026-06-15 |
| [IDEA-027](IDEA-027-unified-team-lifecycle.md) | Unified Team Lifecycle -- Consult → Refine → Dispatch in One Team | PROMOTED | 2026-03-19 -- promoted to E-140 |
| [IDEA-028](IDEA-028-loader-stat-population.md) | Loader Stat Population (Per-Game + Season) | PROMOTED | 2026-03-16 -- promoted to E-117 |
| [IDEA-029](IDEA-029-lr-split-population.md) | L/R Split Data Population | CANDIDATE | 2026-06-14 |
| [IDEA-030](IDEA-030-fielding-catcher-pitch-type-tables.md) | Fielding, Catcher, and Pitch Type Tables | CANDIDATE | 2026-06-14 |
| [IDEA-031](IDEA-031-stat-blending-logic.md) | Stat Blending Logic | CANDIDATE | 2026-06-14 |
| [IDEA-032](IDEA-032-multi-credential-per-program.md) | Multi-Credential per Program | CANDIDATE | 2026-06-14 |
| [IDEA-033](IDEA-033-bulk-team-import.md) | Bulk Team Import from /me/teams | DISCARDED | 2026-06-16 -- member-team sync quarantined + member-team season-management product de-scoped (reports-first reframe) |
| [IDEA-034](IDEA-034-program-crud-admin.md) | Program CRUD Admin Page | DISCARDED | 2026-07-08 -- admin trimmed to reports-only (E-239); no program-management product in the reports-first reframe; single seeded `lsb-hs` suffices, `programs` inert/FK-only (IDEA-091) |
| [IDEA-035](IDEA-035-opponent-page-redesign.md) | Opponent Page Redesign | DISCARDED | 2026-06-16 -- opponent discovery quarantined + tracked-opponent registry de-scoped (reports-first reframe) |
| [IDEA-036](IDEA-036-dashboard-program-awareness.md) | Dashboard Program Awareness | DISCARDED | 2026-06-16 -- dashboard quarantined + multi-program de-scoped (reports-first reframe) |
| [IDEA-037](IDEA-037-scouting-report-redesign.md) | Scouting Report Redesign | CANDIDATE | 2026-06-14 |
| [IDEA-038](IDEA-038-query-time-splits-and-streaks.md) | Query-Time Splits and Streaks | CANDIDATE | 2026-06-14 |
| [IDEA-039](IDEA-039-game-metadata-enrichment.md) | Game Metadata Enrichment | CANDIDATE | 2026-06-14 |
| [IDEA-040](IDEA-040-optimistic-pitching-column-audit.md) | Optimistic Pitching Column API Audit | CANDIDATE | 2026-06-14 |
| [IDEA-041](IDEA-041-play-by-play-stat-compilation.md) | Play-by-Play Stat Compilation Pipeline | CANDIDATE | 2026-06-14 |
| [IDEA-042](IDEA-042-bulk-create-opponents-missing-links.md) | bulk_create_opponents Should Create team_opponents Links | DISCARDED | 2026-06-16 -- opponent discovery + dashboard quarantined; reports need no team_opponents link |
| [IDEA-043](IDEA-043-fuzzy-duplicate-detection.md) | Fuzzy Duplicate Team Detection | CANDIDATE | 2026-06-23 |
| [IDEA-044](IDEA-044-prevent-duplicate-team-creation.md) | Prevent Duplicate Team Creation | PROMOTED | 2026-03-27 -- promoted to E-167 |
| [IDEA-045](IDEA-045-worktree-divergence-detection.md) | Detect Main-Branch Divergence Before Epic Closure Patch | CANDIDATE | 2026-06-24 |
| [IDEA-046](IDEA-046-resolver-duplicate-gc-uuid.md) | OpponentResolver Creates Duplicate gc_uuid Team Instead of Merging | PROMOTED | 2026-03-26 -- promoted to E-162 |
| [IDEA-047](IDEA-047-worktree-diff-phantom-deletions.md) | Epic Worktree `git diff main` Shows Phantom File Deletions | CANDIDATE | 2026-06-24 |
| [IDEA-048](IDEA-048-spray-chart-fielder-zones.md) | Fielder Position Labels/Zones on Spray Charts | CANDIDATE | 2026-06-25 |
| [IDEA-049](IDEA-049-spray-chart-pull-center-oppo.md) | Pull/Center/Oppo Tendency Summary on Spray Charts | CANDIDATE | 2026-06-25 |
| [IDEA-050](IDEA-050-spray-chart-hot-cold-zones.md) | Count Overlay / Hot-Cold Zones on Spray Charts | CANDIDATE | 2026-06-25 |
| [IDEA-051](IDEA-051-spray-chart-title-stats.md) | Title with Stats on Spray Charts | CANDIDATE | 2026-06-25 |
| [IDEA-052](IDEA-052-familiar-faces-indicator.md) | Familiar Faces Indicator on Opponent Rosters | DISCARDED | 2026-06-16 -- depends on cross-team player identity + longitudinal tracking (permanent §7 non-goals) |
| [IDEA-053](IDEA-053-opponent-workflow-fix.md) | Fix Opponent Scouting Workflow End-to-End | PROMOTED | 2026-03-28 -- delivered by E-173 |
| [IDEA-054](IDEA-054-worktree-guard-cross-contamination.md) | Worktree Guard Should Prevent Cross-Epic Contamination | CANDIDATE | 2026-06-26 |
| [IDEA-055](IDEA-055-auto-sync-and-experience-polish.md) | Auto-Sync and Experience Polish | PROMOTED | 2026-06-27 |
| [IDEA-056](IDEA-056-search-fallback-team-return-bug.md) | Fix _search_fallback_team Return Type Bug | CANDIDATE | 2026-06-27 |
| [IDEA-057](IDEA-057-report-flow-orphan-team-stubs.md) | Report Flow Orphan Team Stubs | PROMOTED | 2026-03-29 -- promoted to E-188 |
| [IDEA-058](IDEA-058-pyproject-dependency-management.md) | Proper Python Dependency Management via pyproject.toml | PROMOTED | 2026-03-29 -- promoted to E-190 |
| [IDEA-059](IDEA-059-opponent-flow-spray-gaps.md) | Opponent Flow Spray Chart and Display Gaps | PROMOTED | 2026-03-29 -- promoted to E-189 |
| [IDEA-060](IDEA-060-flow-testing-and-validation.md) | Comprehensive Flow Testing and Validation | CANDIDATE | 2026-06-27 |
| [IDEA-061](IDEA-061-season-id-from-team-context.md) | Derive season_id from Team Context, Not Filesystem Path | PROMOTED | 2026-06-30 | → E-197 |
| [IDEA-062](IDEA-062-plays-boxscore-reconciliation.md) | Plays-vs-Boxscore Reconciliation Engine | PROMOTED | 2026-04-01 |
| [IDEA-063](IDEA-063-dump-game-skill.md) | /dump-game Diagnostic Skill | CANDIDATE | 2026-04-02 |
| [IDEA-064](IDEA-064-dashboard-report-parity.md) | Dashboard-Report Feature Parity | DISCARDED | 2026-06-16 -- dashboard quarantined; reports are the sole forward scouting surface |
| [IDEA-065](IDEA-065-llm-eval-harness.md) | LLM Starter Prediction Evaluation Harness | CANDIDATE | 2026-07-03 |
| [IDEA-066](IDEA-066-league-level-detection.md) | League/Level Detection for Pitch Rules | PROMOTED | 2026-07-06 | -> E-218 |
| [IDEA-067](IDEA-067-catcher-pitcher-restriction.md) | Catcher-Pitcher Restriction (NSAA) | CANDIDATE | 2026-07-06 |
| [IDEA-068](IDEA-068-evaluate-main-session-dispatch-behaviors.md) | Evaluate Main-Session Dispatch Behaviors for Codification | CANDIDATE | 2026-07-12 |
| [IDEA-069](IDEA-069-consolidate-cascade-delete-logic.md) | Consolidate Cascade Delete Logic (admin + reports) | PROMOTED | 2026-04-13 -- absorbed into E-221-05 |
| [IDEA-070](IDEA-070-admin-ui-delete-path-reports-gap.md) | Admin-UI Delete-Team Path Does Not Clean `reports.team_id` | CANDIDATE | 2026-07-13 |
| [IDEA-071](IDEA-071-e220-adopter-audit-fix-pre-provenance-code.md) | E-220 Adopter Audit — Fix Pre-Provenance Code Paths | PROMOTED | 2026-04-13 -- promoted to E-223 |
| [IDEA-072](IDEA-072-rtk-compression-retrospective-audit.md) | RTK Compression Retrospective Audit | CANDIDATE | 2026-08-28 |
| [IDEA-073](IDEA-073-full-suite-ci-gate.md) | Full-Suite CI Gate (GitHub Actions or Equivalent) | CANDIDATE | 2026-08-29 |
| [IDEA-074](IDEA-074-starlette-deprecation-migration.md) | Migrate Starlette Deprecations Before a Framework Upgrade Breaks Them | PROMOTED | 2026-06-07 -- promoted to E-232 |
| [IDEA-075](IDEA-075-harness-output-reliability.md) | Harness Output-Reliability Fix (stop the garble/drop/silent-edit thrash) → E-231 | PROMOTED | 2026-08-29 |
| [IDEA-076](IDEA-076-spray-value-regression-guard.md) | Spray-Value Regression Guard (E-234-05 left spray shape-only) | CANDIDATE | 2026-09-11 |
| [IDEA-077](IDEA-077-reevaluate-season-fallback-trust-flag.md) | Re-evaluate season_fallback Trust Flag — Option A coach-visible line DELIVERED by E-236-06; machinery removal residual → ROADMAP D2 | PROMOTED | 2026-06-15 -- Option A delivered by E-236-06 |
| [IDEA-078](IDEA-078-coaching-docs-dashboard-staleness.md) | Coaching docs still sell a dashboard-first / longitudinal product — reports-first rewrite (bounded docs cleanup; surfaced by drift scour) | CANDIDATE | 2026-09-13 |
| [IDEA-079](IDEA-079-rich-starter-narrative.md) | Reliably Rich Predicted-Starter & Bullpen Narrative — pin-vs-stabilize the HEAD-vs-prod richness gap (diff prompt across tag range first) | CANDIDATE | 2026-09-14 |
| [IDEA-080](IDEA-080-coach-facing-scheduled-report-delivery.md) | Coach-Facing Scheduled Report Delivery — email links to coaches the morning of the game (deferred from E-240; carries coach email-content MUST-HAVEs + the stable-URL/extended-expiry option) | CANDIDATE | 2026-09-15 |
| [IDEA-081](IDEA-081-post-e241-dead-code-stale-example-sweep.md) | Post-E-241 dead-code + stale-example sweep (scout_all-orphaned freshness-gating cluster + dead format_season_display + stale compound-slug example comments; deferred-whole from E-241) | CANDIDATE | 2026-09-19 |
| [IDEA-082](IDEA-082-twin-athlete-uuid-resolution.md) | GameChanger active/removed athlete-UUID "twin" resolution (one human split across two UUIDs fragments opponent stats; deterministic status-gated merge, re-base detection off team_rosters; blockers: re-validate blast-radius on clean DB + DE ratifies X-vs-Y) | CANDIDATE | 2026-09-25 |
| [IDEA-083](IDEA-083-per-arm-estimate-marker.md) | Per-arm estimate marker for IP-proxied arms in non-estimate probable-starter sections (deferred from E-243 by UXD "section-level estimate suffices, Simple first"; promote if proxied-arm-in-varsity proves common or a coach is misled) | CANDIDATE | 2026-09-25 |
| [IDEA-084](IDEA-084-scouting-coverage-fill.md) | Scouting-coverage fill to lift probable-starter accuracy (lever A: report-time opponent completed-schedule fill via existing no-auth public pipeline; ~40%→50-55% top-2, bounded by committee entropy; memo `.project/research/scout-coverage-lever.md`; open: report-time vs scheduled backfill + fetch budget; lever C cross-season is project non-goal) | CANDIDATE | 2026-09-26 |
| [IDEA-085](IDEA-085-richer-llm-data-block-field-translations.md) | Richer LLM data-block field-translations to match Variant A SOT exactly (E-243-04 conscious-accepts: null-pitch IP-proxy `pitch_display` numeric form + structured UNAVAILABLE rows; both AC-compliant + jargon-free today, refinement needs richer engine output) | CANDIDATE | 2026-09-26 |
| [IDEA-086](IDEA-086-leverage-pitch-selection-velocity.md) | Leverage pitch selection + velocity in scouting (E-245 stores per-pitch `pitch_type` + `pitch_speed_mph`; future pitch-mix/sequencing/velocity in reports; scorekeeper-coverage dependent; overlaps IDEA-030) | CANDIDATE | 2026-09-27 |
| [IDEA-087](IDEA-087-multi-pitcher-boundary-attribution-drift.md) | Multi-pitcher-boundary attribution drift (cause-4; +23 BF outlier `e283438c`, NOT a self-game; within-game pitcher-boundary mis-assignment; scoped OUT of E-245; likely a recon-engine BF-corrector gap) | CANDIDATE | 2026-09-27 |
| [IDEA-088](IDEA-088-per-game-sentinel-no-name-opponents.md) | Per-game sentinel for genuinely no-name unresolvable opponents (E-245-04 shared "Unknown Opponent" stub + `_find_duplicate_game` natural-key dedup could conflate two no-name opponents on same team+date; reviewer awareness-only, NOT a within-AC defect; reuse the loader's game-suffixed sentinel technique; real 23 self-games resolve by name so unreached today) | CANDIDATE | 2026-09-27 |
| [IDEA-089](IDEA-089-terminal-cooccurrence-fork-disambiguation.md) | Terminal co-occurrence fork disambiguation — Tier 2 of E-249: use same-game co-occurrence between component terminals to auto-collapse genuine same-human forks (Jo/John/Jon) while still refusing true two-human forks (O/Oliver/Owen). E-249 conservatively refuses ALL forks; this recovers same-human residuals + may add durable operator surfacing. Blocked by E-249 + live team_id=196 validation | CANDIDATE | 2026-09-28 |
| [IDEA-090](IDEA-090-codex-review-script-modernization.md) | Codex review/spec-review script modernization (v0.142.4) — 4 independent cleanups from the CA+SE tooling A/B (KEEP-custom decision already made): refresh stale v0.107.0 headers→v0.142.4; re-verify the now-maybe-obsolete CODEX_SANDBOX_OFF branch; adopt `-o/--output-last-message` to harden the read-receipt gate; fix `codex-review.sh` uncommitted-mode under-feeding untracked file CONTENTS (not just names). CA owns skill-side impl when promoted | CANDIDATE | 2026-09-28 |
| [IDEA-091](IDEA-091-e250-descope-leftovers.md) | E-250 de-scope leftovers — carved OUT of E-250: (a) never-read `programs` org-hierarchy machinery + `detect_league_level` unused `program_type`/`classification` params; (b) `_derive_season_id` `min(years)` rule (no driving problem on single-season data, may be DISCARD-worthy). Third E-250 out-of-scope item (season-agnostic overlap-confidence) already handled inside E-250-01 as a comment tweak. Related IDEA-066, IDEA-081 | CANDIDATE | 2026-10-01 |
| [IDEA-092](IDEA-092-de-agent-def-core-entities-stale.md) | `.claude/agents/data-engineer.md` Core Entities table is broadly stale vs the live schema (names non-existent tables like `PlayerTeamSeason`, mis-describes `Lineup`/`PlateAppearance`). E-250-04 removes ONLY the cross-season/`PlayerTeamSeason` cells; this captures the broader table refresh, kept OUT of E-250 to avoid a full agent-def rewrite. Surfaced by CA inventory (Flag B). CA-owned when promoted | CANDIDATE | 2026-10-01 |
| [IDEA-093](IDEA-093-magic-link-token-in-access-logs.md) | Remove the raw magic-link token from GET-verify access logs — E-254-02's GET/POST split closes the mail-scanner-prefetch threat but the token still rides the GET URL into access logs (log-reader could POST-replay); full fix needs fragment/JS delivery. Surfaced by SE during E-254 consult | CANDIDATE | 2026-10-04 |
| [IDEA-094](IDEA-094-admin-router-dependency-refactor.md) | Router-level admin `Depends` on the reports_admin router (defense-in-depth) — E-254-05 adds a sweep test; this prevents an unguarded admin route from existing by construction. Main design Q: FastAPI raise-HTTPException vs. the current return-Response `_require_admin` shape. Surfaced by SE during E-254 consult | CANDIDATE | 2026-10-04 |
| [IDEA-095](IDEA-095-login-timing-repeated-probe-residual.md) | Constant-time login across all three `post_login` paths — E-254-03 equalizes fresh-known vs unknown (single-probe vector); the rate-limit-suppression branch is lighter, leaving a repeated-probe registered-vs-unregistered timing differential. Accept-and-noted in E-254-03; cheapest fix = same dummy work in the rate-limited branch. Surfaced by SE during E-254 Codex triage | CANDIDATE | 2026-10-04 |
| [IDEA-096](IDEA-096-docs-api-systematic-pii-sweep.md) | Systematic `docs/api/` PII sweep — E-254-07 scrubs the 24 audited files; api-scout found a broader tail (~30 more docs with unredacted real UUIDs + additional real names incl. a likely minor). Blanket UUID→placeholder + a positive "example JSON uses taxonomy placeholders" rule, EXCLUDING GC app-identity client IDs (auth/headers/post-auth). Surfaced by api-scout during E-254 Codex triage | CANDIDATE | 2026-10-04 |
| [IDEA-097](IDEA-097-team-resolver-proxy-pacing-posture.md) | `team_resolver` public calls should adopt the proxy/pacing HTTP posture — `resolve_team`/`discover_opponents` pass `proxy_url=None`, `min_delay_ms=0`, bypassing the Bright Data + pacing posture `http-discipline.md` wants for GC requests. E-252-09 fixed only the ConnectError exception contract; this is the deferred posture half. api-scout domain | CANDIDATE | 2026-10-04 |
| [IDEA-098](IDEA-098-unify-prod-detection-is-production.md) | Unify prod-detection through `is_production()` — narrowly `csrf.py:135`'s inline `APP_ENV=="production"` idiom (E-252-03 scoped csrf.py/main.py OUT). CAVEATS: `auth.py:355` `.lower()` is DIFFERENT semantics (must NOT fold); `main.py` only logs; `reset.py` is a DB util that shouldn't import from api/helpers. SE domain | CANDIDATE | 2026-10-04 |
| [IDEA-099](IDEA-099-busy-timeout-non-triad-writers.md) | Broaden `busy_timeout` coverage to non-triad SQLite writers — `bb data` commands (`cli/data.py` ×5) + loaders/crawlers still hand-roll `sqlite3.connect` (some cwd-relative `./data/app.db`), no busy_timeout — same WAL file, outside E-252-06's scheduled-reports triad scope. DE/SE domain | CANDIDATE | 2026-10-04 |
| [IDEA-100](IDEA-100-stat-completeness-guard-inspect-and-narrow.md) | Inspect-and-narrow the three-state `stat_completeness` provenance guards — post-E-239 the member-write path is deleted so the guards never fire on the forward path, but member rows are API-authoritative/not re-derivable and retention was a deliberate E-239 decision (DE finding S3). Inspect live-DB provenance first, then narrow — do NOT delete blind. May be subsumed by E-256's aggregate cutover. Surfaced by the 2026-07-03 platform audit §3. DE domain | CANDIDATE | 2026-10-04 |
| [IDEA-101](IDEA-101-reset-db-guard-whitespace-bypass.md) | Close the `bb db reset` production-guard whitespace bypass — `reset.py:49` uses `.lower()`-only so `APP_ENV=" production "` bypasses the destructive-reset guard (runs without `--force`). Same fail-open class E-254-01 fixed; canonical `is_production()` now exists. Layering caveat: may fix inline `.strip().lower()` rather than import `api/helpers`. Out of E-254's app-security-gate scope. SE/DE domain | CANDIDATE | 2026-10-05 |
| [IDEA-102](IDEA-102-committed-artifact-pii-gap.md) | Close the committed-artifact PII gap — real PII in `epics/`/`.project/` idea/epic/note files is UNGATED: the pre-commit scanner has both dirs in SKIP_PATHS (+ can't detect names anyway), and the E-254-07 byte-gate only covers `docs/api/`. A near-miss real-name leak in a committed idea file (Codex Phase-4b, 2026-07-07) proves it. Extend the denylist sweep + a positive no-real-PII-in-artifacts rule. CA + SE/api-scout | CANDIDATE | 2026-10-05 |
| [IDEA-103](IDEA-103-dead-table-retention.md) | Dead-table retention — `crawl_jobs` + `coaching_assignments` are inert (cascade-DELETE only, never INSERT/SELECT); record retention rationale + drop-blocker (cascade rewrite + migration) for a future removal epic. Exclusions: `user_team_access` LIVE, `team_opponents` dropped mig 008, `programs` FK-load-bearing. DE+PM verified. (E-255-06 AC-4) | CANDIDATE | 2026-10-06 |
| [IDEA-104](IDEA-104-docs-api-denylist-completeness-gap.md) | `docs/api/` byte-gate denylist-completeness gap — real-looking identifiers (public_ids, UUIDs, team name "Kearney Mavericks 14U") sit in committed endpoint docs that `check_doc_pii.sh` passes GREEN on = not denylisted. Distinct from IDEA-102 (that = UNGATED paths; this = GATED docs/api, incomplete denylist). First determine real-vs-fake. Surfaced by api-scout in E-255-04. Related IDEA-096 | CANDIDATE | 2026-10-06 |
| [IDEA-105](IDEA-105-architecture-schema-changelog-rewrite.md) | Full rewrite of `docs/admin/architecture.md` "Schema Changes" historical changelog — still cites pre-E-220 migration numbers that no longer map to files. E-255-05 added a clarifying note + fixed the one false claim; full historical rewrite deferred (reference material, not an executable step). Low priority. Surfaced by docs-writer in E-255-05 | CANDIDATE | 2026-10-06 |
| [IDEA-106](IDEA-106-plays-pipeline-analytics.md) | Plays-pipeline analytics menu (renumbered from the unindexed `plays-pipeline-analytics.md` in E-255-06) — pipeline + FPS%/QAB now shipped (E-195/E-245); forward menu = situational hitting, baserunning, contact quality, count splits, two-strike approach. Scorekeeper-coverage dependent. Overlaps IDEA-086/030/038/041/062 | CANDIDATE | 2026-10-06 |
| [IDEA-107](IDEA-107-endpoint-doc-path-variable-naming.md) | Normalize `/game-stream-processing/` endpoint-doc path-variable naming (`game_stream_id` vs `event_id` filenames/placeholders; both take `event_id`). E-255-04 fixed all PROSE routing claims but left the coupled filename+frontmatter+see_also rename. The un-addressed residual when E-073 was archived. Cosmetic, low priority. api-scout owns docs/api | CANDIDATE | 2026-10-06 |
| [IDEA-108](IDEA-108-plausibility-signal-run-record-persistence.md) | Persist E-257-03's report-time plausibility signal as a queryable operator trust flag on `report_generation_runs` (surfaced in `/admin/reports`, E-236 honesty-split pattern) instead of the shipped WARNING-log-only form. Deferred out of E-257-03 (SE+lead recommended simple-first WARNING); promote if operators miss log-only warnings, esp. on unattended morning-run gens. Needs migration + `_RUN_RECORD_COLUMNS` allowlist + round-trip test → DE+SE | CANDIDATE | 2026-10-06 |

## Status Definitions

| Status | Meaning |
|--------|---------|
| `CANDIDATE` | Active idea, worth revisiting |
| `PROMOTED` | Became an epic -- see Notes in the idea file for the epic ID |
| `DEFERRED` | Set aside deliberately -- includes reason and re-review date |
| `DISCARDED` | Decided against -- includes reason |

## Adding a New Idea

1. Copy `/.project/templates/idea-template.md`
2. Name it `IDEA-NNN-short-slug.md` (next number in sequence)
3. Fill in all sections
4. Add a row to the index table above
