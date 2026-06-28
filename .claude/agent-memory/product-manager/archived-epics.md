# Archived Epics -- Key Milestones

Canonical source for the full archive: `ls /.project/archive/`

This file preserves only key milestones and architectural decision points from the project's history.

## Foundation (E-001 — E-030)
- **E-001**: GameChanger API Foundation — credential parser, API client, endpoint docs
- **E-002**: Data Ingestion Pipeline — 13 stories, 615 tests. Crawlers + loaders for all core data
- **E-003**: Data Model and Storage Schema — core schema, coaching_assignments, seed data
- **E-006**: PII Safety System — pre-commit hook + Claude Code hook for credential scanning
- **E-013**: Agent Buildout — data-engineer and software-engineer from stubs to full operational manuals

## Infrastructure (E-042 — E-100)
- **E-042**: Admin Interface and Team Management — URL-based onboarding, admin CRUD, opponent discovery
- **E-077**: Programmatic Auth Module — gc-signature HMAC, token refresh, client integration
- **E-088**: bb CLI Unification — Typer-based CLI replacing standalone scripts
- **E-096**: Production Deployment — Docker Compose on home Linux server with Cloudflare Tunnel
- **E-097**: Opponent Scouting Data Pipeline — bb data scout, scouting crawler and loader
- **E-100**: Team Model Overhaul — fresh-start schema rewrite. Programs, INTEGER PK, membership_type, TeamRef

## Process Evolution (E-112 — E-149)
- **E-112**: Context Layer Optimization — CLAUDE.md 508→152 lines, 4 new scoped rules, zero info loss
- **E-136/E-137**: Atomic Epic Commits + Worktree Isolation — single commit per epic, git worktree dispatch
- **E-140**: Planning Skill — formalized plan→spec review→triage→refine→READY workflow
- **E-149**: Review Methodology Retro — 6 new CR bug pattern checklist items from E-147/E-148 gaps

## Data Enrichment (E-155 — E-212)
- **E-155**: Combine Duplicate Teams — atomic merge across 16 FK cols in 13 tables
- **E-158**: Spray Chart Pipeline — full pipeline + dashboard integration, matplotlib rendering
- **E-173**: Fix Opponent Scouting E2E — resolution write-through, auto-scout, unified resolve page
- **E-195**: Plays Data Ingestion — FPS% and QAB from play-by-play, 2-table schema, parser/loader split
- **E-196**: Pitching Availability — migration 014, game ordering convention, shared workload query
- **E-197**: Derive season_id from Team Context — canonical utility, decoupled filesystem vs DB
- **E-198**: Reconciliation Engine — plays-vs-boxscore detection + BF-boundary correction
- **E-199**: Plays-Derived Stats in Reports — FPS%, QAB%, P/BF, P/PA on both scouting surfaces
- **E-204**: Starter vs. Relief Tracking — appearance_order, GS/GR display, backfill CLI
- **E-212**: Predicted Starter — first LLM integration, two-tier enrichment pattern, both surfaces
- **E-214**: Fix Predicted Starter Rest Day Anchoring — `reference_date` threading, `FEATURE_PREDICTED_STARTER` flag
- **E-215**: Fix Player-Level Duplicates — `ensure_player_row()` canonical upsert, prefix-matching detection, atomic merge, two-hook post-load dedup sweep in scouting pipeline
- **E-216**: Cross-Perspective Game Dedup — pre-load dedup via natural key (`game_date` + unordered team pair) with doubleheader tiebreakers, post-load validation (game duplicate check + roster count). Prevention-over-cleanup pattern.
- **E-217**: NSAA Pitch Count Availability Rules — replaced ad-hoc exclusion heuristics with NSAA-compliant frozen dataclass rule engine (tiered rest, consecutive-days, doubleheader aggregation, null pitch count handling). Bullpen shows available/unavailable with reasons. LLM rest table injection. Context-layer `pitch-rules.md` codifies NSAA/Legion/USSSA/PG rules.

## Process + Reports-First Reframe (E-218 — E-243)
- **E-218**: League/Level Detection for Pitch Rules — cascading priority (DB fields → NGB+age_group → name keywords → unknown); Legion + NSAA-subvarsity rules; unsupported leagues suppress with warning.
- **E-221**: Test Fixture Schema Parity Audit + post-E-220 perspective residuals — canonical cascade consolidation via `generator.py::cascade_delete_team` (Option 2 refactor-delegate).
- **E-223**: E-220 Adopter Audit — fixed 4 IDEA-071 pre-provenance paths (admin delete counts, reconciliation dedup, spray game+perspective gate, backfill deprecated).
- **E-224**: Pytest Interaction Guardrails — SUPERSEDED by E-229 (all compensating machinery later removed); historical record only.
- **E-226**: Closure Commit Approval Gate Enforcement — Phase 5 Step 7 approval gate (named command `git diff --cached --stat main` + the four approval words).
- **E-227**: Closure Workflow Structural Remediation — Phase 5 → single atomic `feat(E-NNN)` commit; worktree cleanup first-class Step 9.
- **E-228**: Reset Dev Env — `bb db reset` → empty schema; admin-sees-all dashboard via `_get_permitted_teams` widening + canonical admin predicate `_user_is_admin`/`user_is_admin`.
- **E-229**: Remove RTK — removed the dev token-proxy + its compensating pytest-discipline rule/hooks; plain pytest output honest again. IDEA-072 (retrospective audit) open.
- **E-230**: Test Suite Fix — full suite green (0 product bugs; all test-maintenance). Established the **unconditional full-suite-green closure gate** + COMPLETED-flip deferral to Step 8 (set only on green).
- **E-231**: Harness Output Reliability — `tool-output-integrity.md` rule + `edit-verify.sh` PostToolUse hook (project's first) + relay-integrity rule + read-receipt triage gate.
- **E-232**: Starlette Deprecation Migration — request-first TemplateResponse + client-instance cookies + asyncio loop-scope; no version bump.
- **E-233**: LLM JSON Hardening — `src/llm/json_extract.py::extract_json_object` helper + `json_object` response_format baseline + single-source canonical default model slug.
- **E-234**: Report Regression Guards (ROADMAP A) — golden stat tables + `bb report verify-aggregates` parity (Epic C cutover gate); established the roadmap-tracking convention (§0 table + `## Roadmap` ref).
- **E-235**: Report Run Records (ROADMAP B) — `report_generation_runs` audit table; canonical-function additive-extension pattern (`ensure_team_row_with_provenance`, the sole surviving live example); in-memory per-run created-set concurrency pattern; data-bearing coverage (N=games-with-stat-rows); `no_games` shareable terminal state.
- **E-236**: Report Integrity Hardening (ROADMAP B2) — `src/reports/run_status.py::classify_stage_status` ERROR-driven (not coverage-driven) helper; migration 003 count cols; honest no-data copy. IDEA-077 Option A delivered.
- **E-237**: Payload-First Loaders (ROADMAP C) — `src/db/season_aggregates.py::canonical_recompute` single boxscore_only recompute; provenance-ownership model (full/supplemented member-authoritative, boxscore_only recompute-owned); parity column-set vs player-set drift are orthogonal.
- **E-238**: D1 Quarantine + Nav/Passkey (ROADMAP D1) — central `quarantine.md`; nav retarget /dashboard→/admin/reports; migration 004 `webauthn_challenges` table; **single-use-token consume (DELETE-is-the-arbiter)** footgun (gate on rowcount==1, never read-then-delete).
- **E-239**: Decouple and Remove (ROADMAP D2) — removed dashboard/member-sync/opponent-discovery (−59k lines/139 files); reports is the SOLE surface; admin = `reports_admin.py`; importer-gate deferral pattern. Migration NEXT=005.
- **E-240**: Morning Scheduled Reports (ROADMAP E) — cron `bb report morning-run`; migration 005 `scheduled_report_runs` (report_id ON DELETE SET NULL = audit outlives report); opponent resolution ladder + `opponent_links` revival (3 states keyed on resolution_method); sequential invariant; `bb report map-opponent`. Migration NEXT=006.
- **E-241**: Remove Season Machinery — removed cross-season derivation residue at the root; year-only season derivation from both producers; `season_fallback` gone end-to-end (migration 006); `programs.program_type` KEPT (pitch-rule selection). Zero stat-value change. Migration NEXT=007. IDEA-081 filed.
- **E-243**: Probable-Starter Usefulness — HARD rest-discount re-rank tiebreaker (fully-available > discounted, stable partition); youth/travel labeled-estimate fallback (`PITCH_SMART_15_18`, `is_estimate`); ranked "Most Likely Arms" card + `unavailable_arms` sub-block + `suppress_reason`-keyed softened copy (never leak raw `data_note`); Tier-2 Variant-A prompt + `google/gemini-2.5-flash-lite`@0.0 as tracked default; corrected baseball-coach `probable-starter-model.md`. NOT a ROADMAP slice. IDEA-085 deferral. Dispatch Scorecard 8/6/2.
