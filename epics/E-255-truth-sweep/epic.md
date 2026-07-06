# E-255: Truth Sweep — Context Layer, API Docs, Runbooks — DRAFT STUB (audit CE-5)

## Status
`DRAFT`
<!-- Capture stub from the 2026-07-03 platform audit (PLATFORM-AUDIT.md, repo root, UNCOMMITTED).
     Carries the audit's CE-5 scope, absorbed findings (by owner docket), size, owners, sequence.
     NOT refined: no stories/ACs. Refine to READY before dispatch. Do NOT dispatch a DRAFT. -->

## Overview
The meta-layer describes a partly-deleted product. Agent charters, agent memories, rules files, API endpoint docs, and operator runbooks still teach the dashboard, member sync, ghost schema entities, a "can't programmatically refresh tokens" falsehood, phantom migration numbers, and runbooks that are not executable end-to-end on a fresh machine. E-250 fixes a vetted slice of the cross-season prose; this epic corrects the substantially larger remainder.

## Audit Provenance
- **CE #**: CE-5 · **Size**: L · **Owners**: claude-architect, api-scout, docs-writer, product-manager (+ each agent's own memory) · **Sequence**: position 7 — **after E-250 lands**, so the sweep corrects the post-descope remainder rather than racing it.
- **§4 scope row (verbatim)**: "Everything in B1/B2/B3/B5 not owned by E-250: rules staleness, agent charters + memories, game_stream.id corrections, runbook executability (bb install, health URLs, phantom migrations, dashboard verification), delete agent-browsability doc, PM hygiene (stale READY triage, ideas repair, E-211 flip)."
- **Absorbs**: ~10 medium + ~30 low.

## Absorbed Findings (by owner docket, copied from audit §7)
**claude-architect** — testing.md worked example (wrong nested `team_season.season.year` shape + "spec wins"); key-metrics Longitudinal bullet + GS member-path + `pitches_7d` inverted NULL/0 semantics; gc-uuid-bridge Storage Rule vs the deliberate E-211 self-heal overwrite; data-model L18-20 (deleted machinery as live) + L32 ("awaits E-104"); CLAUDE.md ambient dashboard refs (L51/60/172) + L131 race caveat + L137 admin-ui pointer; stale migration-number citations (009/012/015, "currently 005"); arch-subsystems renamed-helper name + "cached boxscore JSON" framing; api-docs.md structure counts/flows (89 vs 120, missing flow docs); ux-designer repurpose-or-retire (**user decision**); PM `Task-tool`/`D1 migrations` wording; coach USSSA persona line; docs-writer dashboard charter; DE Core Entities pointer-replacement (IDEA-092); **delete `agent-browsability-workflow.md`**; `.claude/hooks/README.md` stale "fail open" prose (E-251/CE-1 Codex finding ③, explicitly DEFERRED→CE-5 as pre-existing/out-of-scope for that epic — the hook behavior changed in E-251-04 but the README description was not reconciled); document the SOUND_BUT_UNDERDOCUMENTED §3 items (context-growth counterweight, memory-lifecycle policy, roster-review record). (SE status-steps contradiction already fixed in CE-1/E-251-03 — do NOT redo.)

**api-scout** — game-summaries `game_stream.id` corrections (5 sites) + opponent-scouting Authenticated Fallback; the "`/games` returns only completed games" claim (superseded — morning-run depends on the opposite); boxscore IP self-contradiction (integer outs vs float); post-search punctuation/curly-apostrophe quirks; public-games perspective-specific-id caveat; README count/duplicate row (121→120); re-verify + fix the public-team-profile `team_season` shape backing testing.md's example. (The 15-file endpoint-doc **PII scrub** is scoped in CE-4; coordinate so one pass covers both.)

**docs-writer** — production runbook host-env/`bb` install + cron/`backup_db.py` command forms; operations.md false "plays pipeline removed in E-239" claim + nonexistent `bb creds login` + phantom migrations 006/009/012/014/015 + `cloudflared :latest` tag; post-reset health-check URL (`localhost:8000/health` fails every way); getting-started out-of-devcontainer path (never installs the project); dashboard-verification rewrites (production-deployment + cloudflare-access-setup — coach-login vs share-link model); rebuild-procedure "seeds placeholder data" (empty since E-228).

**product-manager** — ROADMAP consistency pass (DRAFT header on executed roadmap, §0 missing E-241/E-250 rows, §5 D2 prose vs what E-239 shipped, L207 already-done follow-up); **E-193 archive-or-replan** (READY on a false premise: agent-browser not installed, motivating dashboard deleted); **stale-READY triage of E-072/E-073/E-174/E-175** (3-4 months, drifted premises) + consider a stale-READY re-confirmation rule (~60-day); ideas README moot-CANDIDATE sweep + one unnumbered/unindexed idea file; `docs/E-221-HANDOFF.md` disposition (dead session-handoff targeting deleted code); VISION/vision-signals via the overdue curation session; dead-table retention idea capture (`crawl_jobs`, `coaching_assignments`, `user_team_access`); PM sign-off on the §3 decision-doc items (aggregate-cutover epic = CE-6, raw-archive idea). **NOTE: two PM-docket quick wins are ALREADY DONE (2026-07-04) — the E-211 archive Status flip to COMPLETED and the corrupted IDEA-056/060 README rows repair — do NOT redo them.**

**baseball-coach (own memory)** — MEMORY.md cross-team/multi-season "from day one" section → one-line non-goal note + dashboard reference; coaching-decisions.md season-over-season framing + ghost entities (**PARTIAL: the `PlayerTeamSeason` ghost-entity mention in coaching-decisions.md was already scrubbed in E-250, 2026-07-05 — do NOT redo; the season-over-season framing + other ghost entities remain in scope**); scouting-pipeline.md SUPERSEDED banner on the 403 season-stats recipes.

**data-engineer (own memory)** — etl-patterns.md token-refresh-impossible rewrite; MEMORY.md Core Entity Model (ghost tables, cross-team identity, nonexistent Litestream); ~~endpoint-schema-notes `PlayerTeamSeason` mapping~~ (**DONE in E-250, 2026-07-05 — the `PlayerTeamSeason` mentions in endpoint-schema-notes.md AND MEMORY.md were scrubbed; do NOT redo. The rest of the Core Entity Model rewrite — remaining ghost tables, nonexistent Litestream — is still in scope**); season_aggregate_writers deleted-caller list.

**ux-designer (own memory)** — MEMORY.md pattern library + Key File Paths rewrite around surviving surfaces (pending the CA charter decision on the agent's future).

## Non-Goals (boundary vs. adjacent epics)
- The 15-file endpoint-doc PII **scrub** is CE-4 (security); CE-5 owns the doc-accuracy corrections. Coordinate the two so a file is touched once.
- Query-time aggregates / dead-code deletion / CI / deps → CE-6 (E-256).

## Refinement Notes (for the future planning session)
- Big multi-owner sweep — likely split into per-owner story clusters (CA rules/charters, api-scout endpoint docs, docs-writer runbooks, PM hygiene). Own-memory edits route to each agent under the own-memory carve-out (`.claude/rules/agent-routing.md`).
- The overdue **curate-the-vision session** (recommended in the audit's sequence at position 2, before CE-2) can absorb the ROADMAP/VISION/roster-review/memory-lifecycle PM items — run it first if possible so CE-5 inherits a reconciled VISION.
- Two PM hygiene items are already discharged (E-211 flip, ideas README repair) — scope CE-5 to exclude them.

## History
- 2026-07-04: Created as a DRAFT capture stub from the platform audit (CE-5). Not refined; not dispatchable until taken to READY.
- 2026-07-05 (E-250 dispatch, cross-epic coordination): The agent-memory `PlayerTeamSeason` cleanup listed in the DE + baseball-coach own-memory dockets was PULLED FORWARD into E-250 (per user direction) and is DONE — `PlayerTeamSeason` scrubbed from `data-engineer/{MEMORY.md, endpoint-schema-notes.md}`, `baseball-coach/coaching-decisions.md`, and `claude-architect/agent-blueprints.md` (verified clean in the E-250 closure commit via a staged-tree grep). CE-5 must NOT re-plan the `PlayerTeamSeason`-specific cleanup. The BROADER own-memory sweeps remain in scope (DE: etl-patterns token-refresh, MEMORY.md ghost tables + nonexistent Litestream, season_aggregate_writers; baseball-coach: MEMORY.md cross-team/multi-season section, season-over-season framing, scouting-pipeline banner) — only the `PlayerTeamSeason` token was removed early, not the full Core Entity Model / framing rewrites.
