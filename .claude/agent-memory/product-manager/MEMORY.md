# Product Manager -- Agent Memory

## Numbering State
- Next available epic number: E-202
- Epics created: E-001 through E-201 (E-001, E-003, E-005, E-006, E-007, E-008, E-010, E-011, E-012, E-013, E-014, E-015, E-016, E-017, E-018, E-019, E-020, E-021, E-022, E-024, E-025, E-026, E-027, E-028, E-029, E-030, E-031, E-032, E-033, E-034, E-035, E-036, E-037, E-038, E-042, E-044, E-046, E-048, E-049, E-050, E-052, E-053, E-054, E-056, E-057, E-058, E-055, E-059, E-060, E-061, E-075, E-081, E-084, E-087, E-088, E-089, E-090, E-091, E-092 archived; E-093, E-094, E-095 archived; E-096 archived; E-097 archived; E-098 archived; E-099 archived; E-100 archived; E-101 archived; E-102 archived; E-103 archived; E-104 ready; E-105 archived; E-106 draft; E-107 archived; E-108 archived; E-109 archived; E-110 ready; E-111 archived; E-112 archived; E-114 archived; E-115 archived; E-116 archived; E-113 completed; E-117 completed; E-118 archived; E-119 ready; E-120 archived; E-121 archived; E-122 archived; E-123 archived; E-124 completed; E-125 archived; E-126 completed; E-127 archived; E-128 archived; E-129 archived; E-130 archived; E-131 archived; E-132 ready; E-133 archived; E-134 ready; E-135 abandoned; E-136 ready; E-137 ready; E-138 archived; E-139 archived; E-140 archived; E-142 archived; E-143 archived; E-144 archived; E-145 archived; E-146 archived; E-147 archived; E-148 archived; E-149 archived; E-150 archived; E-151 archived; E-152 archived; E-153 archived; E-155 archived; E-156 archived; E-157 archived; E-158 completed; E-159 archived; E-160 archived; E-161 completed; E-162 ready; E-163 archived; E-165 ready; E-166 completed; E-167 archived; E-168 archived; E-169 draft; E-170 ready; E-171 abandoned; E-172 draft; E-173 archived; E-178 completed; E-179 completed; E-180 draft; E-181 completed; E-182 archived; E-177 archived; E-183 archived; E-184 archived; E-185 archived; E-186 archived; E-187 archived; E-188 archived; E-189 archived; E-190 archived; E-191 archived; E-192 archived; E-193 draft; E-194 archived; E-195 archived; E-196 draft; E-197 archived; E-198 archived; E-200 ready; E-201 ready)
- Next available idea number: IDEA-064
- Ideas created: IDEA-001 through IDEA-063

## Project Context
- Project: baseball-crawl -- GameChanger API -> database -> coaching dashboard
- Tech stack: Python end-to-end. FastAPI+Jinja2 serving layer. Docker Compose + Cloudflare Tunnel. SQLite.
- Architecture: src/ for source (gamechanger/, api/, http/, safety/, cli/), tests/ for tests, data/ for local dev outputs, migrations/ for SQL
- Operator CLI: `bb` command (Typer) -- unified entry point for all operator scripts. src/cli/ package. Entry point in pyproject.toml. Devcontainer-only (not in production image).
- Credentials: short-lived, profile-scoped (_WEB/_MOBILE env keys). Primary web path: `bb creds setup web` (email+password → full login bootstrap, auto-generates device ID). Fallbacks: mitmproxy extractor (auto-detects web/ios), `bb creds import` (curl paste). Mobile: mitmproxy only (iOS client key unknown). Auth-module rule at `.claude/rules/auth-module.md`.
- See CLAUDE.md for full project conventions

## Active Epics (Summary)

| Epic | Title | Status | Key Details |
|------|-------|--------|-------------|
| E-072 | Proxy Session Ingestion Skill | READY | Proxy session data ingestion |
| E-073 | API Documentation Validation Sweep | READY | API doc validation |
| E-104 | Athlete Profile Endpoint Probe | READY | athlete_profile_id probing for opponent access |
| E-106 | Evaluate Unauthorized E-100-01 Implementation | DRAFT | Evaluate DE's unauthorized E-100-01 work |
| E-110 | Iterative Review Rounds Convention | READY | Codify iterative review/refinement pattern |
| E-125 | Full-Project Code Review Remediation | READY | 6 stories: CSRF (01), SQL injection + magic link hashing (02), OBP formula + broken backlink (03), Docker non-root + executescript FK (04), HTTP client hardening (05), security hygiene (06). All parallel, SE only. Highest priority -- security + correctness. |
| E-134 | Strike % and # Pitches Columns | READY | 1 story. Add pitches + strike_pct to all 5 pitching display surfaces. Pure query+template, no schema changes. SE only. |
| E-169 | Fix Unknown Player Names in Scouting Data | READY | 2 stories: extract names from boxscore players array in GameLoader (01), fallback display for unresolved players (02). SE only. No schema changes. Conditional UPSERT upgrades stubs without overwriting real names. 32 review findings (26 accepted, 2 dismissed). |
| E-170 | Fix Opponent Connect public_id Collision | READY | 1 story. Fix 500 error when connecting opponent whose public_id already exists on another team row. Merge by repointing resolved_team_id + flash message + confirm page hardening. SE only. |
| E-172 | Standalone Scouting Report Generator | DRAFT | 4 stories: schema+renderer (01), generation pipeline+CLI (02), public serving route (03), admin reports page (04). Paste GC URL → crawl → self-contained HTML snapshot → shareable public link. 14-day expiry. SE only. |
| E-178 | Teams Page UX Overhaul | COMPLETED | 3 stories delivered: terminology cleanup (01), auto-refresh + failed badge (02), merge page language (03). SE only. Ready for archive. |
| E-180 | Codify E-178 Planning Knowledge | READY | 2 stories: UXD memory design principles + terminology refresh (01), PM memory audit-first lesson (02). CA only. |
| E-181 | Auto-Sync and Experience Polish | COMPLETED | 3 stories delivered: auto-sync on add/merge (01), game coverage indicators (02), empty states + schedule links + welcome state (03). Context-layer assessment: 3 YES triggers (convention, footgun, domain knowledge). Docs assessment: coaching docs update warranted. Ready for archive. |
| E-196 | Pitching Availability and Game Ordering | READY | 5 stories: start_time/timezone migration+loaders (01), game ordering fix (02), pitching workload query (03), dashboard availability columns (04), standalone report availability columns (05). SE only. Migration 010. All design decisions locked from consultation. |
| E-197 | Derive season_id from Team Context | ARCHIVED | Completed 2026-04-02. 4 stories delivered. Canonical `derive_season_id_for_team()` utility, all loaders updated, migration 011 fixed Rebels 14U. Context-layer codified (T1, T2, T3, T5). |
| E-198 | Plays-vs-Boxscore Reconciliation Engine | ARCHIVED | Completed 2026-04-02. 2 stories delivered. Detection engine (11 pitcher + 5 batter + 3 game-level signals), migration 012 (reconciliation_discrepancies), BF-boundary pitcher correction algorithm, `bb data reconcile` CLI. Context-layer codified (T1, T2, T5, T6). Docs update dispatched. |
| E-200 | Fix Stale season_id on Pre-Existing Games | READY | 2 stories: code fix (01, add season_id to _upsert_game ON CONFLICT), data migration 013 (02, correct stale season_ids for ~200+ teams without program_id). SE only. 02 blocked by 01. Bug from E-197 derivation change. |
| E-201 | Close Reconciliation Accuracy Gaps | READY | 1 story. 5 fixes in engine.py (~35 lines): boxscore #P/TS supplement (88.1%→99.2%), IBB in BB outcomes, games-table scores for game_runs (93.1%→100%), BF sum for game_pa_count. SE only. No schema changes. Blocks E-199. |

## Key Architectural Decisions
- Storage: SQLite (WAL mode). Host-mounted at ./data/app.db. Simple file backup via scripts/backup_db.py (no Litestream).
- Serving layer: FastAPI + Jinja2 (Python). Single monolithic app. No TypeScript.
- Deployment: Docker Compose (local + prod). Home Linux server (no VPS, no hosting cost). Cloudflare Tunnel (ingress). App-internal auth (magic links + passkeys). Production: https://bbstats.ai.
- Migrations: numbered SQL scripts (migrations/001_*.sql). No Alembic. apply_migrations.py at startup.
- HTTP layer: src/http/headers.py + src/http/session.py. Dual-header system: BROWSER_HEADERS (Chrome 145/macOS) + MOBILE_HEADERS (iOS Odyssey). create_session(profile="web"|"mobile"). Profile-aware proxy: PROXY_ENABLED + PROXY_URL_WEB/PROXY_URL_MOBILE env vars.
- Dependency management: pip-tools + pyproject.toml dual-source (E-190). Runtime deps in both `pyproject.toml` (`>=` ranges) and `requirements.in` (`~=` ranges). `.in` -> `.txt` via pip-compile. Rule: `.claude/rules/dependency-management.md`.
- ip_outs: innings pitched stored as integer outs (1 IP = 3 outs)
- Mobile credentials (E-075, 2026-03-08): Mobile client key CONFIRMED DIFFERENT from web. iOS app is purely native (no JS bundles). Programmatic mobile refresh blocked on unknown client key.
- FK-safe orphan handling: unknown player_ids get a stub row inserted before the stat row
- Data model (revised 2026-03-31, E-195): Fresh-start schema rewrite in single migration `001_initial_schema.sql` (old 001-008 archived). Key changes: programs table (hs/usssa/legion umbrella entity); teams use INTEGER PK AUTOINCREMENT with gc_uuid/public_id as UNIQUE external identifier columns; `membership_type` (member/tracked) replaces is_owned; `classification` replaces level (varsity/jv/freshman/reserve/8U-14U/legion); team_opponents junction table for opponent relationships; TeamRef dataclass pattern (id/gc_uuid/public_id) for pipeline code; enriched stat columns -- game_stream_id + all counting stats now populated by E-117 (game loader: 12 stats + game_stream_id; season stats: 47 batting + 47 pitching; scouting aggregates: 5 batting + 6 pitching cascade). E-158 added: migration 006 (spray_charts indexes + columns: event_gc_id, created_at_ms, season_id). spray_charts now populated by SprayChartCrawler + SprayChartLoader. E-167 added: migration 007 (idx_teams_name_season_year COLLATE NOCASE index); `src/db/teams.py` with `ensure_team_row()` -- canonical team creation function used by all 8 pipeline INSERT paths. E-195 added: migration 009 (plays + play_events tables with pre-computed is_first_pitch_strike and is_qab flags; partial index for FPS% queries). Plays pipeline: PlaysCrawler + PlaysParser + PlaysLoader. Still unpopulated: bats/throws, splits, batting_order. Auth tables simplified (users/sessions/magic_link_tokens/passkey_credentials/coaching_assignments). E-143 added: migration 002 (users.role column), migration 003 (crawl_jobs table). E-197 added: migration 011 (fix season_id for Rebels 14U -- data correction, USSSA program creation, team 126 assignment). `derive_season_id_for_team()` canonical utility in `src/gamechanger/loaders/__init__.py`. E-198 added: migration 012 (reconciliation_discrepancies table -- per-signal per-player per-team discrepancy records with 5-value status lifecycle). `src/reconciliation/engine.py` with `reconcile_game(conn, game_id, dry_run=True)` and `reconcile_all()`. BF-boundary pitcher attribution correction in execute mode. Next migration: 013.
- Routing model (2026-03-03): Orchestrator removed (E-030). PM is the direct entry point for all work.
- Auth model (revised 2026-03-26, E-157): ALL users = magic link email + optional passkey. No separate admin login path. Cloudflare Access present but passive (no enforcing policies). Dev bypass via DEV_USER_EMAIL. Role-based access: `users.role` column (admin/user, migration 003). `_require_admin()` accepts EITHER `ADMIN_EMAIL` env var match OR `role='admin'`. Auth tables in 001_initial_schema.sql (folded in during E-100 rewrite).

## User Preferences
- Build it right, no rush
- Coaches see dashboards; user (operator) runs the system
- Multi-team (4 Lincoln levels), multi-season, player tracking across orgs
- CLAUDE.md and shipped code comments describe current implemented reality, NOT future planned state
- Epics/stories describe future work until that work is done
- Archived files are frozen historical records -- do not modify

## Ideas Backlog
| ID | Title | Status | Review By | Notes |
|----|-------|--------|-----------|-------|
| IDEA-001 | Local Cloudflare Dev Container | DISCARDED | 2026-02-28 | Superseded by E-009 |
| IDEA-002 | Web Scraping Fallback Strategy | CANDIDATE | 2026-05-29 | Promote when API data gap discovered |
| IDEA-003 | Work Management as Agent Interface | CANDIDATE | 2026-05-29 | Promote when file-based system causes friction |
| IDEA-004 | Hard Data Boundaries and PII Protection | PROMOTED | 2026-03-02 | Promoted to E-019 |
| IDEA-005 | Directory-Scoped Intent Nodes | CANDIDATE | 2026-06-01 | **Trigger met**: E-002+E-003 both complete |
| IDEA-006 | Epic Lanes Convention | CANDIDATE | 2026-06-01 | Promote when 6+ story epics common AND agents report TN scoping confusion |
| IDEA-007 | Dispatch Coordinator Guardrail | DISCARDED | 2026-06-02 | Resolved by E-065 |
| IDEA-008 | Plays and Line Scores Crawling | CANDIDATE | 2026-06-02 | Plays portion delivered by E-195. Line scores remain. |
| IDEA-009 | Per-Player Game Stats + Spray Charts | CANDIDATE | 2026-06-02 | **Trigger met**: E-002+E-004 complete |
| IDEA-010 | Docs Port Map Consistency | CANDIDATE | 2026-06-03 | Patch stale docs port references |
| IDEA-011 | Investigate HTTP 500 Failures | CANDIDATE | 2026-06-04 | Three endpoints return 500 with web headers |
| IDEA-012 | Crawl Orchestration and Scheduling | CANDIDATE | 2026-06-06 | All blockers resolved -- promotable |
| IDEA-013 | cmux Evaluation | CANDIDATE | 2026-06-07 | Blocked by E-066 + operator experience |
| IDEA-014 | Mobile vs. Web API Doc Split | CANDIDATE | 2026-06-05 | Trigger: 3+ endpoints with divergent per-profile behavior |
| IDEA-015 | Programmatic Auth Module | PROMOTED | 2026-03-08 | Promoted to E-077 |
| IDEA-016 | Codex Hardening Trail Map | CANDIDATE | 2026-06-07 | Preserve hardening path |
| IDEA-019 | Retroactive Opponent Stat Crawling | PROMOTED | 2026-03-12 | Promoted to E-097 |
| IDEA-020 | Public Endpoint Opponent Data | PROMOTED | 2026-03-12 | Promoted to E-097 |
| IDEA-022 | Scouting Flow Doc Mismatch | CANDIDATE | 2026-06-12 | Flow doc lists stats not in schema |
| IDEA-023 | Automated .env and app.db Backup | CANDIDATE | 2026-06-13 | Only precious state without automated backup |
| IDEA-024 | Refactor postCreateCommand | CANDIDATE | 2026-06-13 | Extract monolithic one-liner |
| IDEA-025 | Migration-Driven Test Fixtures | CANDIDATE | 2026-06-14 | |
| IDEA-026 | Context Layer Placement Audit -- Phase 2 | CANDIDATE | 2026-06-15 | Trigger: after E-112 ships |
| IDEA-027 | Unified Team Lifecycle | PROMOTED | 2026-03-19 | Promoted to E-140 |
| IDEA-028 | Loader Stat Population (Per-Game + Season) | PROMOTED | 2026-03-16 | Promoted to E-117 |
| IDEA-029 | L/R Split Data Population | CANDIDATE | 2026-06-14 | E-100 deferred. E-117 complete but handedness data source unknown -- not fully unblocked. |
| IDEA-030 | Fielding/Catcher/Pitch Type Tables | CANDIDATE | 2026-06-14 | E-100 deferred. Additive tables. |
| IDEA-031 | Stat Blending Logic | CANDIDATE | 2026-06-14 | E-100 deferred. API vs boxscore merge strategy. |
| IDEA-032 | Multi-Credential per Program | CANDIDATE | 2026-06-14 | E-100 deferred. May never be needed. |
| IDEA-033 | Bulk Team Import from /me/teams | CANDIDATE | 2026-06-14 | E-100 deferred. 19-team batch onboarding. |
| IDEA-034 | Program CRUD Admin Page | CANDIDATE | 2026-06-14 | E-100 deferred. Before non-HS teams onboard. |
| IDEA-035 | Opponent Page Redesign | CANDIDATE | 2026-06-14 | E-100 deferred. E-153 delivered pitching-first layout, empty states, team batting summary. Remaining scope: proactive flags, PDF export. |
| IDEA-036 | Dashboard Program Awareness | CANDIDATE | 2026-06-14 | E-100 deferred. After multiple programs exist. |
| IDEA-037 | Scouting Report Redesign | PROMOTED | 2026-03-29 | Promoted to E-185 (completed 2026-03-29). Remaining: proactive flags, PDF export. |
| IDEA-038 | Query-Time Splits and Streaks | CANDIDATE | 2026-06-14 | **Trigger met**: E-117 complete. Coach MUST HAVE: recent form, doubleheader, season phase. All query-time over per-game data. |
| IDEA-039 | Game Metadata Enrichment | CANDIDATE | 2026-06-14 | venue_name, is_doubleheader, game_num_in_week. Supports IDEA-038. |
| IDEA-040 | Optimistic Pitching Column API Audit | CANDIDATE | 2026-06-14 | **Trigger met**: E-117 complete. api-scout: which of 23 optimistic pitching cols does GC actually return? |
| IDEA-041 | Play-by-Play Stat Compilation Pipeline | CANDIDATE | 2026-06-14 | Foundational layer delivered by E-195 (plays ingestion + FPS%/QAB). Remaining: advanced analytics (situational hitting, baserunning, count splits), opponent pipeline integration, season aggregate compilation. |
| IDEA-043 | Fuzzy Duplicate Team Detection | CANDIDATE | 2026-06-23 | **Trigger met**: E-155 complete. Extend exact-name matching to fuzzy (NULL season_year gap, similar names). |
| IDEA-044 | Prevent Duplicate Team Creation | PROMOTED | 2026-06-23 | Promoted to E-167 (completed 2026-03-27). |
| IDEA-045 | Detect Main-Branch Divergence Before Closure Patch | CANDIDATE | 2026-06-24 | Context-layer: add `git log epic/E-NNN..main` check to implement skill Phase 5. |
| IDEA-046 | OpponentResolver Duplicate gc_uuid Bug | PROMOTED | 2026-03-26 | Promoted to E-162. |
| IDEA-047 | Worktree `git diff main` Phantom Deletions | CANDIDATE | 2026-06-24 | Misleading diff output during dispatch; closure merge unaffected. |
| IDEA-048 | Fielder Position Labels/Zones on Spray Charts | CANDIDATE | 2026-06-25 | Defensive position overlays on spray chart images. |
| IDEA-049 | Pull/Center/Oppo Tendency Summary on Spray Charts | CANDIDATE | 2026-06-25 | Text summary of directional tendencies on spray chart images. |
| IDEA-050 | Count Overlay / Hot-Cold Zones on Spray Charts | CANDIDATE | 2026-06-25 | Heat-map density visualization on spray charts. |
| IDEA-051 | Title with Stats on Spray Charts | CANDIDATE | 2026-06-25 | Enhanced titles with BA, BIP count, pull% on spray chart images. |
| IDEA-052 | Familiar Faces Indicator | CANDIDATE | 2026-06-26 | Show when opponent roster includes players coach has seen before (cross-team identity). |
| IDEA-053 | Opponent Workflow Fix E2E | PROMOTED | 2026-03-28 | Delivered by E-173. |
| IDEA-054 | Worktree Guard Cross-Epic Contamination | CANDIDATE | 2026-06-26 | Prevent writes into another epic's worktree. |
| IDEA-055 | Auto-Sync and Experience Polish | PROMOTED | 2026-06-27 | Promoted to E-181. |
| IDEA-056 | Fix _search_fallback_team Return Type Bug | PROMOTED | 2026-03-29 | Promoted to E-184. |
| IDEA-057 | Report Flow Orphan Team Stubs | PROMOTED | 2026-03-29 | Promoted to E-188. |
| IDEA-058 | Proper Python Dependency Management via pyproject.toml | PROMOTED | 2026-03-29 | Promoted to E-190. |
| IDEA-061 | Derive season_id from Team Context | PROMOTED | 2026-06-30 | Promoted to E-197. |
| IDEA-062 | Plays-vs-Boxscore Reconciliation Engine | PROMOTED | 2026-04-01 | Promoted to E-198. Phase 1: pitcher attribution detection+correction. Phase 2 deferred: batter validation, heuristic evolution. |
| IDEA-063 | /dump-game Diagnostic Skill | CANDIDATE | 2026-07-01 | Pull every API endpoint for a single game to enable gap exploration. After E-201. |

## Key Workflow Contract
- Routing model: planning (user -> PM), dispatch (user/main session -> implementers directly). PM plans and closes; main session dispatches.
- PM modes: discover, plan, clarify, triage, close, curate
- Epic lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED)
- READY gate: must be READY/ACTIVE before dispatch. PM sets READY explicitly.
- Dispatch: Main session creates team, spawns implementers + code-reviewer + PM, assigns stories, routes to PM for AC verification and status updates, manages merge-back and cascade.
- Direct-routing exceptions (no PM needed): api-scout, baseball-coach, claude-architect
- Implementing agents needing work auth: software-engineer, data-engineer, docs-writer
- Agent ecosystem: 9 agents (claude-architect, product-manager, baseball-coach, api-scout, data-engineer, software-engineer, docs-writer, ux-designer, code-reviewer)
- Before assigning epic numbers: ALWAYS ls /epics/ to avoid numbering collisions

## Topic File Index
- [archived-epics.md](archived-epics.md) -- Complete list of archived epics with summary descriptions (E-001 through E-198)
- [lessons-learned.md](lessons-learned.md) -- Epic authoring patterns, dependency patterns, process patterns, platform constraints
- [mcp-research.md](mcp-research.md) -- MCP server evaluation findings (E-009-R-05, R-06)
- [feedback_fix_all_real_findings.md](feedback_fix_all_real_findings.md) -- Fix all real review findings, dismiss only false positives
- [feedback_domain_expert_designs.md](feedback_domain_expert_designs.md) -- For context-layer epics, CA designs stories; PM frames ACs
