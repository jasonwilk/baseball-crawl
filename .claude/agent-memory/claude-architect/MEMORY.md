# Claude Architect -- Agent Memory

## Core Principle: Simple First, Complexity as Needed
IMPORTANT -- This is the governing design principle for the entire project.
- Build the smallest working thing, then iterate
- Do NOT pre-create agents, infrastructure, or abstractions before they are needed
- One file > framework, script > pipeline, dict > class (until it isn't)
- When in doubt, leave it out
- CRITICAL LESSON: The principle guides FUTURE decisions. It does NOT justify deleting existing working context, architectural details, or agent configs. Existing documentation has value.

## Project: baseball-crawl
- Project root: repository root (workspace-relative paths used throughout)
- Purpose: Coaching analytics for Lincoln Standing Bear HS baseball (GameChanger data)
- Teams: Freshman, JV, Varsity, Reserve (Legion later)
- Users: Jason (operator), coaching staff (consumers)
- MVP (achieved): queryable database for scouting/game prep. Product is REPORTS-FIRST -- generate a report for a GC `public_id` and share the link. The dashboard, member-sync, and tracked-opponent surfaces were REMOVED in E-239 (ROADMAP D2 slice), NOT quarantined. Forward feature: morning-of-game scheduled reports.
- State: Active development -- src/http/ module exists (headers, session factory), multiple epics completed

## Key Architectural Decisions
- PII safety system: two-layer defense (Git pre-commit hook + Claude Code PreToolUse hook)
  - Design doc: `/.project/research/E-006-precommit-design.md`
  - Git hook: `.githooks/pre-commit` with `core.hooksPath` (not pre-commit framework)
  - Claude Code hook: `.claude/hooks/pii-check.sh` (PreToolUse, Bash matcher)
  - Scanner: `src/safety/pii_scanner.py` (stdlib only, shared by both hooks)
  - No agent/skill created for scanning (deterministic check, not reasoning)
- Product-manager has full template content inline (comprehensive operational manual)
- Tech stack: Python end-to-end. FastAPI+Jinja2 serving layer. Docker Compose + Cloudflare Tunnel. SQLite (WAL mode). Home Linux server. Simple file backup via scripts/backup_db.py. Decision finalized in E-009.
- Docker Compose stack (3 services): app (FastAPI, localhost:8001 direct / localhost:8000 via Traefik), traefik (reverse proxy, dashboard at :8180), cloudflared (tunnel). E-027 established devcontainer-to-compose networking.
- App troubleshooting section in CLAUDE.md covers: stack management, health check, logs, rebuild after changes, unreachable diagnosis. Agents should rebuild + health-check after modifying src/, migrations/, Dockerfile, docker-compose.yml, or requirements.txt.
- Proxy boundary: mitmproxy runs on Mac host, NOT in the devcontainer. Agents must not attempt proxy lifecycle commands (start/stop/status/logs). Agents CAN read proxy data from `proxy/data/` and credentials from `.env`. Documented in CLAUDE.md "Proxy Boundary" section + Commands subsection separation + `.claude/rules/proxy-boundary.md` (glob-triggered on `proxy/**`). See `docs/admin/mitmproxy-guide.md` for full details.
- CLAUDE.md has Core Principle section at top, followed by full project context
- Ideas workflow in `/.project/ideas/` for pre-epic tracking (IDEA-NNN numbering)
- Ideas rule: if acceptance criteria cannot be written, it is not an epic -- capture as idea
- Ideas are reviewed on every epic completion (mandatory) and every 90 days
- Ideas workflow encoded in five places:
  - `CLAUDE.md` (Ideas Workflow subsection under Project Management)
  - `.claude/rules/ideas-workflow.md` (scoped rule, paths: .project/ideas/**)
  - `.claude/agents/product-manager.md` (Ideas Workflow section + System of Work flow)
  - `.claude/agent-memory/product-manager/MEMORY.md` (idea numbering state)
- PM handles "capture for later" / "someday" / "idea" intent directly
- Any agent identifying future work should flag to PM, not create speculative epics
- Per-epic codification records (E-077 auth, E-228 team-access, E-235/236/237 reports telemetry+integrity+aggregates, E-239 surface removal + removal-epic process footguns, E-241 season year-only collapse, E-246 resolve_db_path + false-parity footgun, E-247/E-249/E-252 consolidation+dedup+scheduled-reports seams, E-254 security/PII hardening — strict `is_production()` + `validate_app_env()`, scanner staged-blob/fail-closed, doc-PII byte-gate, atomic count-cap, E-257 reconciliation-scoreboard — `bb report reconcile-scoreboard`, code-canonical stat-def constants in `recon_scoreboard.py` (its one-way ratchet gate was RETIRED 2026-07-26 by operator decision; the Operating Principle binds as direction, not mechanically), E-261 cross-perspective game-dedup — canonical `merge_duplicate_game`/`src/db/game_merge.py` twin-merge seam + `bb data merge-duplicate-games` operator repair pass, pre-classification fail-closed refusal, E-262 post-program housekeeping — defect-cited context-layer truth/staleness fixes + Step 1d preflight/gate corrections (freeze holds), IDEA-113 rename `season_aggregates.py`→`season_projection.py`, E-264 league-aware ERA basis — nullable `teams.innings_per_game` (migration 012) documented in `data-model.md` as load-bearing NULL provenance (no DEFAULT/NOT NULL/blind backfill), self-heals like `season_year`; `era_basis_innings()` stays below the CLAUDE.md canonical-seam bar, E-267 reconcile-at-load — canonical retire-absent seam `src/db/reconcile_at_load.py` (pure `classify_absences` + connection-in/no-commit grain helpers, hard-delete uniform, health-gate on the FRESH payload with no snapshot table) + **report generation is now DESTRUCTIVE** + `bb db purge-scouting` + four defect-cited behavioral footguns placed where they BIND: missing-safety-signal-defaults-to-REFUSE → `python-style.md`, `git checkout --` in a staged dispatch worktree → `worktree-isolation.md`, stale-`__pycache__`-inverts-mutation-results + annotating-is-not-covering → `testing.md` (+ reviewer side in `code-reviewer.md`), coherent-garble Read → `tool-output-integrity.md` as a concrete case): see `epic-codifications.md`. Key live invariants surfaced from there: canonical helpers `resolve_db_path()`, `ensure_team_row()`, `ensure_season_row()`; scored-but-empty games are the MODAL scouting case (coverage signals MUST be data-bearing EXISTS, never bare COUNT). E-273 orphan-reference reclamation — canonical `reclaim_orphan_reference_data`/`src/reports/lifecycle.py` reachability sweep (single-source `_orphan_team_ids`/`_orphan_player_ids` feed both DELETE and `count_orphan_reference_data`; pass OWNS its `BEGIN IMMEDIATE` transaction as a NAMED EXCEPTION; deferred-on-live-generating) + reworked the E-267 destructive bullet into **report deletion AND generation are DESTRUCTIVE** (both axes) + T8 promotion of "exhaustive-class claims: verify by independent enumeration, not spec/code/test agreement" into `code-reviewer.md`. E-270 harden reconcile-at-load + purge — the **WAL-pragma boundary placed AT the canonical `get_connection()` bullet** (a "read-only" preview via the factory persistently rewrote a non-WAL target's journal mode; framed as a SCOPE BOUNDARY since the canonical rule already says "every SQLite **writer**", NOT an exception — and the predicate is "must not MODIFY the target", never "is a reader", since many legitimate readers use the factory for `busy_timeout`), guard-surface==delete-surface via the shared `_PERSPECTIVE_CHILD_TABLES` constant, the **`ON DELETE CASCADE` silent-success footgun** (a KEEP→PURGE FK raises only for a DEFAULT-ACTION FK; CASCADE COMMITS while destroying the preserved identity row — so the action-agnostic plan-time test is PRIMARY and the runtime abort a BACKSTOP), api-scout's twin-phantom/truncation envelope placed as a CORRECTION to the "absent ⇒ removal" trap sentence, and T8: absence-claims-need-COMPLETED-CLEANLY-not-ENTERED → `testing.md`, prose-you-AUTHOR-is-a-claim (+ stable-anchor fold) → `tool-output-integrity.md`. E-272 season×level→league classification + NRBL — season is a first-class classification AXIS in `.claude/rules/pitch-rules.md` (new "Season as a Classification Axis" section) and the precedence predicate is bracket **PRESENCE**, not mapped-ness (an UNMAPPED 14U outranks every level word too; the title I first shipped named the wrong predicate); NRBL is a distinct constant == LEGION per the `PITCH_SMART_15_18` precedent and is **inference-resolved with NO `program_type`**; TN-6's SELECTION-vs-MAPPING split binds the undispatched E-263-02c (operator pick authoritative WHEN SET, unset DELEGATES to `detect_league_level` — morning-run has no operator, so forcing Pitch Smart would re-introduce the bug); season vocabulary is **observed, not specified** (n=18: summer×17 spring×1, OPEN not a closed enum); NSAA Varsity UNDER-rests vs Legion at 46-50/61-70/81-90p +110-vs-105 post-April, so "default to NSAA" is *spring-is-likelier*, NEVER *spring-is-safer*; T8 split ACROSS two rules because it is two failures — relayed-claims/borrowed-authority → `tool-output-integrity.md`, retired-claim degraded-form taxonomy → `doc-sweep.md` (a derived RATING has no sentence to check, so a prose-authoring rule structurally cannot catch it). E-276 reconcile-at-load health gate — **the same-population invariant I pinned at E-267 was SATISFIED BY THE BROKEN CODE** (both sides drawn from the polluted post-upsert set), so it is now stated as NECESSARY-BUT-NOT-SUFFICIENT with the temporal clause as the load-bearing half, in CLAUDE.md and in the E-267 entry; the seam bullet separates the CANDIDATE population (live read, `old ∪ fresh`, uniform, correct) from the per-grain HEALTH-GATE population, and **the three grains did NOT converge — roster ships with NO floor at all, LESS gating than it started with, on an operator ruling** (never write "all three grains now read their prior correctly"); my E-267 "benign, dedup would have merged the rows anyway" ruling is corrected as REFUTED BY EXECUTION, with the standing check extended — **A MITIGATION IS A CONCLUSION TOO** (for any "X would have caught this anyway", establish that X runs AFTER the harm; a dismissal is the claim nobody re-opens); T8 opened under a ~100-line operator cap that was LIFTED mid-pass (*"you can let it grow; we're about to refine the context layer anyway"*), so the two items declined for SIZE were reinstated and my eight files closed at **73 net** (four-subtree ratchet measure 231; baseline still NOT re-snapshotted, inherited debt stays visible): `tool-output-integrity.md` gains "A check that RAN is not a check that WORKED" — **the PRODUCIBILITY check** (a figure is checked for whether it SUPPORTS the conclusion, never whether it could have been PRODUCED) **and, adjacent and explicitly distinguished, the CRITERION-vs-EVIDENCE cut** (*a figure is a CRITERION when a reader must MEET it and EVIDENCE when a reader must SEE what was observed — correct the first, preserve the second*); **⛔ I shipped the first under the second's NAME, because that label had no written definition anywhere — three uses, all naming an application, never stating a rule. A term that cannot be promoted without being defined is TESTED BY THE ACT OF PROMOTION**, so codification is a detector for undefined shared vocabulary, not just a consumer of it — plus the 8-of-8 author-never-catches-their-own record, the instrument-lies BOUND, severity-ordering-is-a-claim + the grep-narrowing class (markup/wrap/hyphenation/case, and **an unexpected COUNT is a cross-check trigger in EITHER direction**) + asymmetric framing folded into the safety-comment sub-class, `python-style.md` gains the identifier sweep's stopping rule + `docs/`-inclusive tree scope, `code-reviewer.md` gains the cost-argument disposition rule + untracked-files-are-invisible-to-`git diff`, `context-layer-assessment.md` gains retired-CLAIM sweeping + SE's re-homed never-write-a-live-number-into-memory, `doc-sweep.md` gains the REVERSE shape (the refutation shares no token with the claim) + a prose sweep cannot see code that still PARSES. **Re-homing beat duplicating, measurably: SE then deleted its longer local copy, so that promotion's net cost was NEGATIVE.** (E-259 retired `canonical_recompute` and the mixed-provenance season-aggregate apparatus — the stored season tables were dropped and season totals are now query-time; the surviving invariant is the query-time perspective filter, `get_season_batting`/`get_season_pitching`.)
- Dispatch pattern: PM is a standing team coordinator (not fire-and-forget)
  - PM joins every dispatch team, stays active throughout, manages all state
  - Implementers do NOT update story statuses or epic tables -- PM owns that
  - PM verifies acceptance criteria before marking DONE, cascades to unblocked stories
  - Encoded in: `dispatch-pattern.md` (rule), `product-manager.md` (Dispatch Mode), `CLAUDE.md` (Workflow Contract #5)

## User Preferences (Jason)
- "Simple first" is a guiding principle for FUTURE decisions, not a deletion tool
- Actively edits project files -- respect his changes, do not revert
- Values detailed context in agent prompts (full operational manuals)
- Wants all architectural details preserved (stack decisions, metrics, collaboration patterns)

## Topic File Index
- `epic-codifications.md` -- Per-epic record of what was codified where (E-077, E-228, E-235..E-241, E-246..E-262, E-264, E-267, E-270, E-272, E-273)
- `claude-practices.md` -- CLAUDE.md design, context management
- `agent-design.md` -- Subagent architecture, ecosystem patterns
- `skills-and-hooks.md` -- Skills system, hooks patterns
- `semantic-layer.md` -- Intent routing, layering strategy
- `agent-blueprints.md` -- Historical blueprints for agents (data-engineer, software-engineer built via E-013; baseball-coach, api-scout for reference)
- `boundaries.md` -- Operational boundary catalog (host vs container, auth vs public, PII, hallucinated identifiers)
- `ingest-workflow-log.md` -- Per-endpoint integration history from ingest-endpoint skill executions (19 endpoints, 2026-03-04)
- `codex-config.md` -- Codex CLI configuration, model, reasoning effort, available models
- `model-behavior-reference.md` -- Four-tier placement architecture, verification taxonomy, per-model adapters (4.8/Opus 5/Sonnet 5/Fable 5), dated alias-to-model register. Consult BEFORE any placement or agent-definition call.

## Claude Code Platform Facts
- CLAUDE.md loaded every session; keep concise
- First 200 lines of MEMORY.md auto-loaded into system prompt
- Hooks: deterministic; CLAUDE.md: advisory
- Agent Teams enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) -- only the main session (lead) spawns subagents via the `Agent` tool; subagents cannot spawn their own (no nesting)
- Flag gates the team-coordination surface: without `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, the team-coordination tools (`SendMessage` + the shared `Task*` task list) are unavailable and spawned agents are one-shot
- `TeamCreate`/`TeamDelete` were removed in Claude Code v2.1.178 (recorded 2026-06-29) -- team formation is now implicit and teardown automatic; no explicit create/delete calls exist
- `Agent` (Task tool): main session only; spawns a named subagent. Subagents are long-lived and resumable -- re-engage via `SendMessage` with context intact. Use for epic/story dispatch.
- Context window is the #1 resource to manage
- Statusline: configured via `statusLine` key in settings.json (type: "command", command: path to script)
- Statusline receives JSON on stdin with model, workspace, cost, context_window, etc.
- For devcontainer portability: use relative paths in statusLine.command (e.g., `.claude/hooks/statusline.sh`)
- Statusline runs after each assistant message, debounced at 300ms
- Custom hooks live in `.claude/hooks/` directory

## Epic History (Agent Ecosystem)
- E-013 (COMPLETED 2026-03-02): Agent Buildout -- completed data-engineer and software-engineer from stubs to full operational manuals, seeded memory directories for api-scout, baseball-coach, software-engineer, and data-engineer, wired skill references into all agent definitions. Absorbed E-012 and E-014.

## Skills Index
Four skills in `.claude/skills/`:
- **context-fundamentals** -- Context window mechanics, budget management, load/defer decisions
- **filesystem-context** -- File-based context delivery, progressive disclosure, ambient vs. deferred
- **multi-agent-patterns** -- Telephone game problem, verbatim relay, dispatch checklist
- **ingest-endpoint** -- Workflow automation: two-phase GameChanger API endpoint ingestion (api-scout -> claude-architect). Created 2026-03-04. Referenced from: CLAUDE.md (Workflows section). Replaces manual workflow used for season-stats and game-summaries endpoints.

## Domain Reference Documents
- `docs/api/` -- API spec directory (owned by api-scout). Index at `docs/api/README.md`, per-endpoint files in `docs/api/endpoints/`, global reference files in `docs/api/*.md`.
- `docs/gamechanger-stat-glossary.md` -- stat abbreviation data dictionary (owned by api-scout, created 2026-03-04). Referenced from: CLAUDE.md (Key Metrics), api-scout agent def + memory, data-engineer agent def + memory, software-engineer agent def + memory, baseball-coach agent def + memory. Integration audit completed 2026-03-04.

## Ingest-Endpoint Workflow Executions
20 integrations (19 endpoints 2026-03-04, plus POST /search re-ingestion 2026-03-29). Full per-endpoint integration log: `ingest-workflow-log.md`

## Codex Configuration
Details in topic file: `codex-config.md`

## Known Hallucination Traps
- **A read disagreeing with disk has TWO causes and the alarming one is over-diagnosed.** "The transport garbled it" and "the file moved under a live writer" produce IDENTICAL evidence (second read disagrees; grep for the remembered text finds nothing) — the discriminators are the harness "modified on disk" note, `stat` mtime vs. read time, and the other writer's `~/.claude/projects/<slug>/<session>/subagents/*.jsonl` payloads. `.claude/rules/tool-output-integrity.md` carried only the garble etiology until 2026-07-25, when a re-adjudication of its own E-267 anchor anecdote showed that case was a concurrent writer (mutation-testing mutant on disk), not a garble. Garble is real and kept; the anchor for it is `.project/research/E-231-harness-repro/harness-output-reliability-report.md`. Full record: `epic-codifications.md` E-267 T3 re-adjudication. The same 2026-07-25 pass added ONE paragraph ("A handoff artifact is a claim with a timestamp") for the agent-actionable half of the root cause and DELIBERATELY declined a new session-lifecycle rule: only the operator opens a second session or seeds a successor, so a rule addressed to agents cannot bind it. If it recurs, extend `dispatch-pattern.md` (which already carries the advisory concurrency note) rather than creating a surface.
- **`pitch-rules.md`'s NRBL/LEGION separate-constant rationale is DELIBERATE and stated at line 134** ("a future Legion-only change must not silently move NRBL, nor an NRBL-only change move Legion"), mirroring the `PITCH_SMART_15_18` note at line 180; line 136's nrbl.net cite is a THIRD, separate point. Do not collapse the two constants in a sweep, and do not accept a summary of this passage — on 2026-07-25 it was misstated three times in one afternoon (a true claim retracted, then the retraction "corrected" into a second false claim), with the underlying verdict staying right at every step, so no verdict-level check caught it. That shape is codified in `.claude/rules/tool-output-integrity.md` under "A claim you RELAY is a claim you AUTHOR".
- `ghcr.io/devcontainers/features/apt:1` DOES NOT EXIST. The official devcontainers/features registry has no apt installer feature. Real apt features are from rocker-org and devcontainers-extra. See `.claude/rules/devcontainer.md` for correct identifiers.
- General rule: always verify devcontainer feature identifiers against https://containers.dev/features before referencing them in rules or configs.
