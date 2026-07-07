# E-255: Truth Sweep — Context Layer, API Docs, Runbooks — READY (audit CE-5)

## Status
`READY`
<!-- READY 2026-07-07: all 6 domain docket-confirmations folded; internal review (CR spec audit +
     6 holistic) + Codex spec review (3 iterations) complete, all findings folded; quality checklist
     passed. Dispatch is a SEPARATE authorization (this was a "plan with review" trigger, not
     plan-and-dispatch) — do NOT dispatch without explicit user go-ahead. See History scorecard. -->
<!-- DISPATCH NOTE: Pre-Dispatch Step 0 (R-01 fact spike + the two runbook git mv, both committed to
     main) runs BEFORE worktree creation; dispatched set = 01–09. Not part of the planning commit. -->

## Roadmap
Not a `docs/ROADMAP.md` §5 slice — this is CE-5 of the 2026-07-03 platform-audit program (CE-1..CE-6 → E-251..E-256), so no §0 Roadmap-Tracking planning-commit is owed (that convention is roadmap-slice-only).

## Overview
The meta-layer describes a partly-deleted product. Agent charters, agent memories, rules files, API endpoint docs, and operator runbooks still teach the dashboard, member sync, ghost schema entities, a "can't programmatically refresh tokens" falsehood, phantom migration numbers, and runbooks that are not executable end-to-end on a fresh machine. E-250 fixed a vetted slice of the cross-season prose; this epic corrects the substantially larger remainder so the context layer, docs, and runbooks describe the CURRENT reports-first reality.

## Background & Context
This is CE-5 from the 2026-07-03 platform audit (`PLATFORM-AUDIT.md`, repo root, UNCOMMITTED). The audit found ~131 confirmed findings; the doc/context-accuracy remainder (B1/B2/B3/B5 not owned by E-250) is collected here: ~10 medium + ~30 low findings across the context layer, `docs/api/`, `docs/admin/`, and each agent's own memory.

**Critical timing context — FIVE epics have landed since the 2026-07-03 audit** (E-250, E-251, E-252, E-253, E-254). Several docket items were incidentally fixed or changed by intervening work:
- E-250 dropped `gc_athlete_profile_id`/`team_opponents`/`season_type` (migration 008), scrubbed `PlayerTeamSeason` from DE + baseball-coach memory + CA agent-blueprints, and archived E-104 ABANDONED.
- E-251 fixed the SE status-steps contradiction (E-251-03) and changed hook behavior (E-251-04) without reconciling `.claude/hooks/README.md`.
- E-252 introduced the operating-tz seam and `is_production()` (codified into CLAUDE.md).
- E-253 shipped migrations 009 + 010 and corrected several `data-model.md` facts (~16% coverage, `derive_local_date`).
- E-254 corrected the CLAUDE.md prod-detection prose and scrubbed PII from 24 `docs/api/` files (the CE-4 PII scrub the original docket asked CE-5 to coordinate with — **now DONE**, so the api-scout endpoint-doc corrections here operate on already-scrubbed files, pure accuracy work).

**Therefore every story MUST re-verify the audit's specific line citations against the CURRENT file state before applying — the audit's line numbers and migration-number citations (009/012/015, "currently 005") are stale relative to `migrations/` next=011 and the post-E-250..254 files.** The docket describes the class of error to hunt; it is not a blind apply list.

**Discovery findings (2026-07-07, verified against current files):**
- **DISCHARGED — descope from this epic:** VISION.md rewrite + vision-signals clearing (curation 2026-07-05, confirmed in `docs/vision-signals.md` header); E-211 archive Status flip (2026-07-04); IDEA-056/060 README repair (2026-07-04); `PlayerTeamSeason` cleanup across DE/coach/CA memory (E-250); SE status-steps contradiction (E-251-03); the CE-4 `docs/api/` PII scrub (E-254-07).
- **STILL OPEN — in scope:** `docs/ROADMAP.md` consistency (still `Status: DRAFT`; §4/§5 still describe D1/D2 removal as *future* while §0 shows E-238/E-239 COMPLETED — curation does NOT touch ROADMAP); the §3 curation-decision **codification** (context-growth counterweight, memory-lifecycle policy — decisions made 2026-07-05, captured in `.claude/agent-memory/product-manager/project_ce5_curation_handoff.md`, physical writes owed by CA); `docs/agent-browsability-workflow.md` deletion (confirmed EXISTS); `docs/E-221-HANDOFF.md` disposition (confirmed EXISTS); E-193 archive-or-replan (still READY on a deleted-dashboard premise); stale-READY triage of E-072/E-073/E-174/E-175; all rules-file/CLAUDE.md/arch-subsystems/endpoint-doc/runbook/own-memory truth corrections.

## Audit Provenance
- **CE #**: CE-5 · **Size**: L · **Owners**: claude-architect, api-scout, docs-writer, product-manager (+ each agent's own memory) · **Sequence**: position 7 — after E-250..E-254 land, so the sweep corrects the post-descope remainder.
- **§4 scope row (verbatim)**: "Everything in B1/B2/B3/B5 not owned by E-250: rules staleness, agent charters + memories, game_stream.id corrections, runbook executability (bb install, health URLs, phantom migrations, dashboard verification), delete agent-browsability doc, PM hygiene (stale READY triage, ideas repair, E-211 flip)."
- **Absorbs**: ~10 medium + ~30 low.

## Absorbed Findings (by owner docket, copied from audit §7)
> **NOTE (docket vs. resolved ACs):** This is the ORIGINAL audit §7 docket (historical source text). Where a resolved planning decision diverges from this prose, **the story ACs are authoritative** — do not implement from this section. Key reconciliations already settled: the `team_season` shape doc is `get-public-teams-public_id.md`, NOT the `public-team-profile` bridge doc (R-01 AC-2 / story 04 AC-6); the dead-table retention set is `crawl_jobs` + `coaching_assignments` only (`user_team_access` is LIVE, `team_opponents` already dropped — story 06 AC-4); the CLAUDE.md "L131 race caveat" is DISCHARGED, not a fix (story 01 AC-5, do NOT edit the L134 invariant); `data-model.md` "L32 awaits E-104" is already-fixed (E-250-07, excluded); the count is "120 files (119 endpoints + 1 web-routes reference)"; migrations 006/009 are REAL (operations.md fabricated their CONTENT — story 05 AC-1). Inline rows below are lightly annotated where they diverge.

**claude-architect** — testing.md worked example (wrong nested `team_season.season.year` shape + "spec wins"); key-metrics Longitudinal bullet + GS member-path + `pitches_7d` inverted NULL/0 semantics; gc-uuid-bridge Storage Rule vs the deliberate E-211 self-heal overwrite; data-model L18-20 (deleted machinery as live) + L32 ("awaits E-104" — **already-fixed E-250-07, excluded**); CLAUDE.md ambient dashboard refs (L51/60/172) + L131 race caveat (**DISCHARGED — now current concurrency invariants; story 01 AC-5, do NOT edit L134**) + L137 admin-ui pointer; stale migration-number citations (009/012/015, "currently 005"); arch-subsystems renamed-helper name + "cached boxscore JSON" framing; api-docs.md structure counts/flows (89 vs 120, missing flow docs); ux-designer repurpose-or-retire (**RESOLVED 2026-07-07 by Jason: REPURPOSE — refocus the charter, do not retire; matches VISION D4**); PM `Task-tool`/`D1 migrations` wording; coach USSSA persona line; docs-writer dashboard charter; DE Core Entities pointer-replacement (IDEA-092 is the broader table refresh, kept OUT); **delete `agent-browsability-workflow.md`**; `.claude/hooks/README.md` stale "fail open" prose (E-251/CE-1 Codex finding ③, explicitly DEFERRED→CE-5 as pre-existing — the hook behavior changed in E-251-04 but the README description was not reconciled); document the SOUND_BUT_UNDERDOCUMENTED §3 items (context-growth counterweight, memory-lifecycle policy, roster-review record — source text in the PM curation handoff). (SE status-steps contradiction already fixed in CE-1/E-251-03 — do NOT redo.)

**api-scout** — game-summaries `game_stream.id` corrections (5 sites) + opponent-scouting Authenticated Fallback; the "`/games` returns only completed games" claim (superseded — morning-run depends on the opposite); boxscore IP self-contradiction (integer outs vs float); post-search punctuation/curly-apostrophe quirks; public-games perspective-specific-id caveat; README count/duplicate row (**resolved: "120 files (119 endpoints + 1 web-routes reference)"**); re-verify + fix the `team_season` shape backing testing.md's example (**resolved: the shape lives in `get-public-teams-public_id.md` — the `GET /public/teams/{public_id}` doc — NOT the `public-team-profile` bridge doc**). (The 15-file endpoint-doc **PII scrub** was scoped in CE-4 and is DONE in E-254-07 — no coordination needed; operate on the already-scrubbed files.)

**docs-writer** — production runbook host-env/`bb` install + cron/`backup_db.py` command forms; operations.md false "plays pipeline removed in E-239" claim + nonexistent `bb creds login` + phantom migrations 006/009/012/014/015 + `cloudflared :latest` tag; post-reset health-check URL (`localhost:8000/health` fails every way); getting-started out-of-devcontainer path (never installs the project); dashboard-verification rewrites (production-deployment + cloudflare-access-setup — coach-login vs share-link model); rebuild-procedure "seeds placeholder data" (empty since E-228).

**product-manager** — ROADMAP consistency pass (DRAFT header on executed roadmap, §0 rows, §4/§5 D2 prose vs what E-239 shipped, already-done follow-up lines); **E-193 archive-or-replan** (READY on a false premise: agent-browser not installed, motivating dashboard deleted); **stale-READY triage of E-072/E-073/E-174/E-175** (3-4 months, drifted premises) + consider a stale-READY re-confirmation rule (~60-day); ideas README moot-CANDIDATE sweep + one unnumbered/unindexed idea file; `docs/E-221-HANDOFF.md` disposition (dead session-handoff targeting deleted code); VISION/vision-signals via the overdue curation session (**DONE 2026-07-05 — descope**); dead-table retention idea capture (**resolved set: `crawl_jobs` + `coaching_assignments` only — `user_team_access` is LIVE (excluded), `team_opponents` already dropped in mig 008 (excluded), `programs` FK-load-bearing (excluded); story 06 AC-4**); PM sign-off on the §3 decision-doc items (aggregate-cutover epic = CE-6, raw-archive idea). **NOTE: two PM-docket quick wins are ALREADY DONE (2026-07-04) — the E-211 archive Status flip and the corrupted IDEA-056/060 README rows repair — do NOT redo them.**

**baseball-coach (own memory)** — MEMORY.md cross-team/multi-season "from day one" section (lines 65-72, CONFIRMED STALE: "from day one" + "Longitudinal tracking enables") → one-line non-goal note + dashboard reference; coaching-decisions.md (**REFINED via coach recon + PM verify: the season-over-season *framing* is CONFIRMED already clean — DROP that sub-item; but L19's "Key entities" list STILL names the ghost `Lineup`/`PlateAppearance`/`PitchingAppearance` (PM verified 2026-07-07) — that stays IN scope, see TN-7**); scouting-pipeline.md SUPERSEDED banner on the five dated 403 season-stats recipes (banner over inline-editing 5 dated research entries).

**data-engineer (own memory)** — etl-patterns.md token-refresh-impossible rewrite; MEMORY.md Core Entity Model (ghost tables, cross-team identity, nonexistent Litestream); ~~endpoint-schema-notes `PlayerTeamSeason` mapping~~ (**DONE in E-250 — the `PlayerTeamSeason` mentions in endpoint-schema-notes.md AND MEMORY.md were scrubbed; do NOT redo. The rest of the Core Entity Model rewrite — remaining ghost tables, nonexistent Litestream — is still in scope**); season_aggregate_writers deleted-caller list.

**ux-designer (own memory)** — MEMORY.md pattern library + Key File Paths rewrite around surviving surfaces (the CA charter decision on the agent's future is DECIDED: refocus, not retire — 2026-07-05 curation; so this rewrite reflects the refocused report-layout/trust-surface/tools-hub charter).

## Goals
- The context layer (CLAUDE.md, rules, agent charters), `docs/api/`, `docs/admin/` runbooks, and each agent's own memory describe the CURRENT reports-first system — no dashboard/member-sync/ghost-entity/false-token-refresh/phantom-migration claims survive except where explicitly framed as historical.
- `docs/ROADMAP.md` is internally consistent (status header, §0 tracking table, and §4/§5 prose all agree that D1/D2 shipped).
- Operator runbooks are executable end-to-end on a fresh machine (correct `bb` install, health-check URLs, migration numbers, command forms).
- PM backlog hygiene is resolved: stale-READY epics triaged, dead handoff/idea artifacts dispositioned, dead-table retention captured, `docs/agent-browsability-workflow.md` removed.
- The three §3 curation decisions (context-growth counterweight, memory-lifecycle policy, agent-roster refocus) are codified in the context layer.

## Non-Goals
- **PII scrub of `docs/api/`** — CE-4 territory, DONE in E-254-07. This epic owns doc-accuracy only; operate on the already-scrubbed files.
- **Query-time aggregates / dead-code deletion / CI / deps** — CE-6 (E-256).
- **The `PlayerTeamSeason`-specific memory/agent-def cleanup** — DONE in E-250; do not re-plan.
- **VISION.md / vision-signals rewrite** — DONE in the 2026-07-05 curation; do not re-plan.
- **The E-211 archive Status flip and IDEA-056/060 README repair** — DONE 2026-07-04.
- **IDEA-092 broader data-engineer.md Core Entities table refresh** — kept as an idea; only the narrow cross-season/ghost pointer-replacement is in scope here.
- **Re-litigating the three §3 curation decisions** — they are Jason-approved (2026-07-05); CA codifies the recorded rationale, does not re-decide.

## Success Criteria
- Every AC below passes; a grep for each retired stale token (e.g. dashboard-as-live, `team_opponents`, "cannot programmatically refresh", phantom migration numbers) returns zero live (non-historical) hits in the touched files.
- `docs/ROADMAP.md` header + §0 + §4/§5 are mutually consistent.
- A fresh-machine reader can follow the runbooks without hitting a nonexistent command, wrong URL, or phantom migration.
- `docs/agent-browsability-workflow.md` no longer exists; `docs/E-221-HANDOFF.md` is dispositioned (removed or explicitly marked superseded).
- Full test suite green at closure (unconditional closure gate).

## Pre-Dispatch (Step 0) — MAIN-checkout actions, NOT dispatched stories
Two things run in the MAIN checkout BEFORE the implement skill creates the epic worktree (Codex iter-2 P1a + iter-3 P1; Jason-approved 2026-07-07). Both are committed to `main` so the worktree branches from a commit that already contains them:

- **(A) E-255-R-01 fact-verification spike** (owners: api-scout lead + data-engineer) — needs `.env`/creds + proxy captures the worktree lacks; produces `.project/research/E-255-verified-facts.md`. See `E-255-R-01-fact-verification.md` + TN-6.
- **(B) Relocate the two root runbooks** (owner: api-scout — already in main for (A), has Bash) — `git mv docs/production-deployment.md docs/admin/production-deployment.md` and `git mv docs/cloudflare-access-setup.md docs/admin/cloudflare-access-setup.md`. Done pre-dispatch (not inside a dispatched story) because docs-writer has no Bash and an in-story cross-specialist `git mv` breaks the one-specialist-per-story model (Codex iter-3 P1). After this, story 05 (docs-writer) is pure content-editing of the already-relocated `docs/admin/` files + same-dir ref updates — self-contained, no Bash. See TN-9.

**Execution order the main session orchestrates:** (1) spawn api-scout (direct-routing) + DE → run R-01 (A) AND the two `git mv` (B) in the MAIN checkout, (2) commit BOTH the verified-facts artifact and the file relocations to `main`, (3) create the epic worktree from that commit, (4) invoke the implement skill on the dispatched set (**01–09**). The dispatched stories 01/02/04/05 depend on the committed artifact + the relocated `docs/admin/` paths existing.

## Stories (dispatched set = 01–09)
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-255-01 | CLAUDE.md + data-model.md + arch-subsystems.md + migrations.md truth corrections | TODO | R-01 artifact (team_season shape); + runbook-path coupling w/ 05 (TN-9) | claude-architect |
| E-255-02 | Rules-file truth corrections + delete agent-browsability doc + hooks README | TODO | R-01 artifact (shape, pitches_7d, E-211), E-255-04 (endpoint count) | claude-architect |
| E-255-03 | Agent charter corrections + §3 curation-decision codification | TODO | None (ux charter → REPURPOSE, decided) | claude-architect |
| E-255-04 | `docs/api/` endpoint-doc accuracy corrections | TODO | R-01 artifact (game_stream.id, team_season shape) | api-scout |
| E-255-05 | Operator runbook executability corrections (2 root runbooks pre-relocated to docs/admin/ in Step 0) | TODO | Step 0 (relocation) + R-01 artifact (recovery command + host-exec form for AC-8/AC-9) | docs-writer |
| E-255-06 | PM backlog hygiene: ROADMAP consistency + stale-READY triage + artifact disposition | TODO | None | product-manager |
| E-255-07 | baseball-coach own-memory truth sweep | TODO | None | baseball-coach |
| E-255-08 | data-engineer own-memory truth sweep | TODO | None | data-engineer |
| E-255-09 | ux-designer own-memory truth sweep (REPURPOSE branch) | TODO | E-255-03 (refocused charter) | ux-designer |

**Cross-story consistency couplings** (must agree — see TN-7 + TN-9): (a) the "Key entities" list appears in THREE files — baseball-coach `coaching-decisions.md` L19 (E-255-07), data-engineer `MEMORY.md` (E-255-08), and the data-engineer.md charter Core Entities pointer (E-255-03, narrow) — all three must name only real tables (`player_game_batting`/`player_game_pitching`/`plays`/`play_events`), never the ghost `Lineup`/`PlateAppearance`/`PitchingAppearance`; (b) the relocated runbook path `docs/admin/production-deployment.md` must be identical in the CLAUDE.md pointer (story 01) and the file move + inbound-ref updates (story 05) — TN-9.

## Dispatch Team
- claude-architect
- api-scout
- docs-writer
- product-manager
- baseball-coach
- data-engineer
- ux-designer

## Technical Notes

### TN-1: Re-verify before apply (binds every story)
The audit dockets were written against the 2026-07-03 repo state. E-250/251/252/253/254 have since landed. Before correcting any cited claim, each owner MUST read the current file and confirm the stale claim still exists in its cited (or drifted) location. If an intervening epic already fixed an item, mark it discharged in the story notes and move on — do not re-introduce a "correction" to already-correct prose. Migration numbers are authoritative from `ls migrations/` (next = 011), NOT from the audit's citations.

### TN-2: "Truth" means current implemented reality
CLAUDE.md convention: context/docs describe CURRENT implemented reality, not future plans. Corrections replace stale claims with what the code/schema/runbook actually does today. Where a historical mention is load-bearing (e.g., "removed in E-239"), keep it framed as history — do not delete the history, correct the tense/accuracy.

### TN-3: File ownership and conflict isolation
Stories are clustered so each file is touched by exactly one story (avoids same-file dispatch conflicts). Own-memory edits route to each owning agent under the own-memory carve-out (`.claude/rules/agent-routing.md` Routing Precedence). The lone cross-story coordination: the canonical GameChanger endpoint count is set authoritatively by api-scout in E-255-04 (they own `docs/api/`); CA's `.claude/rules/api-docs.md` structure counts in E-255-02 must match that number — hence E-255-02 depends on E-255-04.

### TN-4: §3 curation-decision source text
The three §3 decisions CA codifies in E-255-03 are recorded in `.claude/agent-memory/product-manager/project_ce5_curation_handoff.md` (Jason-approved 2026-07-05): (1) agent-roster refocus of ux-designer + docs-writer (retire neither); (2) context-growth counterweight as a closure-assessment review prompt / trigger-7 in `.claude/rules/context-layer-assessment.md` (NOT a hard line-count cap); (3) memory-lifecycle policy (promote-to-rule / strike-on-staleness / per-agent review cadence). CA uses that file as source; does not re-decide.

### TN-5: PM-hygiene dispositions (RESOLVED by Jason 2026-07-07)
E-255-06 executes the mechanical hygiene (ROADMAP consistency edits, ideas README moot sweep + index the unnumbered file, `docs/E-221-HANDOFF.md` disposition, dead-table retention idea capture) directly, PLUS the now-decided dispositions: (a) **E-193 → archive ABANDONED** (dashboard premise deleted, agent-browser never installed); (b) **E-073 → archive or shrink** (E-255-04 owns the endpoint-doc corrections; PM decides archive-vs-shrink at triage); (c) **E-072/E-174/E-175 → triaged once** (re-confirm/replan/archive per epic). **No ~60-day stale-READY rule** is created (Jason: skip). Dead-table idea capture uses the DE-confirmed table set.

### TN-6: Fact-verification spike (E-255-R-01) runs in the MAIN checkout, pre-dispatch
Three correction items need facts that cannot be read from the current doc prose (the prose IS the thing under suspicion), and two need a live GameChanger call that a worktree cannot make (no `.env`/creds). E-255-R-01 gathers all of them once, in the main checkout, before the worktree correction stories dispatch, and writes them to `.project/research/E-255-verified-facts.md`:
- **(F) `game_stream.id` vs `event_id` routing — settled PROXY-FIRST** — game-summaries L52 claims `game_stream.id` for BOTH boxscore and plays with "different UUIDs". Settle from proxy captures (`proxy/data/sessions/2026-03-09_062059/` + `2026-03-11_032625/`) + cached responses + working code (a fresh authenticated curl is a last resort — `.env` creds are ~4 months stale and would just fail; flag the user). Record the ACTUAL captured behavior, not a naive swap: the `/game-stream-processing/{id}/…` form takes the SAME id for boxscore AND plays (contradicting L52), and TWO plays URL forms exist. HIGHEST RISK item; the F-correction spans ~12 docs/api files (see E-255-04's cross-file sweep AC), not just the 5 game-summaries sites.
- **(G) `team_season` shape from `GET /public/teams/{public_id}`** (doc `get-public-teams-public_id.md`, NOT the bridge `get-*public-team-profile*.md`) — the doc (and testing.md's worked example) claim `team_season.season` is an object with `.year`; a cached sample shows `season` is a BARE STRING and `year` is FLAT at `team_season.year`. This is a PUBLIC endpoint — cheaply live-verifiable with a plain curl, no creds. It feeds BOTH the endpoint doc (E-255-04 AC-6) AND data-model.md L18 + testing.md (E-255-01/02).
- **(pitches_7d)** NULL vs 0 semantics of `pitches_7d` — read from `get_pitching_workload()` in `src/api/db.py` (code fact; **data-engineer's** domain — shared query functions). The audit says the `key-metrics.md` description is INVERTED.
- **(E-211 self-heal)** the `gc_uuid-bridge.md` Storage Rule "never overwrite existing gc_uuid" contradicts the deliberate E-211 self-heal overwrite — read the actual E-211 behavior from the code (api-scout) so the rule is reconciled to reality, not guessed.
- **(recovery command + host-exec form)** the two `docs/admin/` runbook items originally flagged as design choices are treated as FACTS resolved here (main 2026-07-07): the correct `bb creds` recovery command replacing `bb creds login`, and the host `bb`/scripts invocation form (DEFAULT `docker compose exec app …`, confirmed against `docker-compose.yml` + `Dockerfile` + the runbook). These feed E-255-05 AC-8/AC-9.
Owners: **api-scout (lead) + data-engineer** — no new software-engineer (add SE only if a genuine code-behavior JUDGMENT, not a read, surfaces; escalate to main). E-255-R-01's artifact is the single source these facts flow from; 01/02/04/05 cite it rather than re-deriving.

**Dispatch-sequencing (M1, deepened per Codex): R-01 is NOT a normal worktree story.** The implement skill creates the epic worktree first and runs all story work inside it — but R-01 must run in the MAIN checkout (needs `.env`/creds + proxy captures the worktree lacks; its artifact must be committed to main so the worktree branches from a commit that contains it). The main session honors this order at dispatch time: **(1) run R-01 in the MAIN checkout (api-scout + DE), (2) commit `.project/research/E-255-verified-facts.md` to `main`, (3) create the epic worktree from that commit, (4) dispatch 01/02/04/05 as normal worktree stories that Read the committed artifact.** `git worktree add` won't include an uncommitted main file and worktree-isolation forbids committing inside the worktree, so skipping steps 1–2 leaves the artifact unreadable by 01/02/04/05. This is an epic-local sequencing note the main session orchestrates — NOT a general dispatch-skill/CLAUDE.md change (see the triage note: PM's lean, matching main's, is that epic-local suffices; a durable "pre-dispatch main-checkout spike" pattern would be a separate claude-architect item if the project wants one).

### TN-7: "Key entities" list consistency across three files
The ghost entities `Lineup`/`PlateAppearance`/`PitchingAppearance` (which do NOT exist in the squashed schema — real tables are `player_game_batting`/`player_game_pitching`/`plays`/`play_events`) appear in THREE places that must end up consistent: baseball-coach `coaching-decisions.md` L19 (E-255-07 — verified still-present during discovery, so this file stays IN scope despite the coach's initial "already clean" read, which caught the season-over-season framing but not the entity list), data-engineer `MEMORY.md` Core Entity Model (E-255-08), and the data-engineer.md charter Core Entities pointer (E-255-03, narrow fix only; the broader charter-table refresh is IDEA-092, out of scope). All three describe the same conceptual entities; keep them naming only real tables. The broader-vs-narrow split means E-255-03 fixes only the ghost-table pointer, not the whole charter table — flag any residual divergence to PM at closure.

### TN-8: docs-writer runbook items — RESOLVED as facts (not design decisions)
The two E-255-05 items originally flagged as design choices were resolved by main (2026-07-07) as FACTS to verify in E-255-R-01, not user decisions:
- **Finding #3 recovery command (RESOLVED by api-scout)**: `bb creds login` does not exist; the recovery command is **`bb creds refresh`** (first-line) with **`bb creds import` / `bb creds setup web`** as the dead-refresh-token fallback. R-01 records it (AC-5). → E-255-05 AC-8.
- **Finding #5 host `bb`/scripts execution (RESOLVED by api-scout)**: **`docker compose exec [-T] app …`** — api-scout confirmed against `docker-compose.yml` + `Dockerfile` (L30, container-only `pip install`) + the production-deployment runbook that prod does NOT bootstrap `bb` on the bare host. R-01 records it (AC-6). Non-blocking FYI: the daily-backup cron's container-exec-vs-host-install is Jason's deployment-owner call (api-scout surfaces at READY); truth-sweep default is `docker compose exec`. → E-255-05 AC-9.
The other mechanical docs-writer findings (story 05 AC-1..AC-7: phantom migrations, "plays removed in E-239" falsehood, health-check URL, getting-started install, dashboard-verification rewrites, "seeds placeholder data", staleness headers) are unblocked.

### TN-9: Relocated-runbook path coupling (story 01 ↔ story 05)
Per Jason's P1b resolution (2026-07-07), the two `docs/` root runbooks are MOVED into `docs/admin/` (root-cause fix — dissolves the docs-writer ownership conflict; `docs/admin/` is docs-writer's clean remit): `docs/production-deployment.md` → `docs/admin/production-deployment.md` and `docs/cloudflare-access-setup.md` → `docs/admin/cloudflare-access-setup.md`. **The physical `git mv` (both files) happens in PRE-DISPATCH Step 0, run by api-scout in the MAIN checkout alongside R-01 and committed to `main` before the worktree is created (Codex iter-3 P1)** — NOT inside a dispatched story, because docs-writer has no Bash and an in-story cross-specialist `git mv` breaks the one-specialist-per-story model. After Step 0, the worktree already contains the files at `docs/admin/`, so: **story 05** (docs-writer) does the content corrections + the four `docs/admin/`-internal inbound-ref updates (all same-dir, no Bash); the ONE inbound ref outside docs-writer's ownership — **`CLAUDE.md:40`** (`See docs/production-deployment.md …`) — is CA's file and is updated in **story 01**. Both stories MUST land the identical new path `docs/admin/production-deployment.md` (the CLAUDE.md-table analogue coupling). Intentionally NOT updated (flagged in story 05): `.project/archive/**`, `reviews/e125-cr-infra.md`, and `PLATFORM-AUDIT.md` (uncommitted audit source Jason is working — prose reference, not a link).

## Open Questions

### Resolved by Jason (2026-07-07)
- **ux-designer repurpose-or-retire → REPURPOSE.** E-255-03 AC-1 refocuses the ux charter (report-layout/trust-surface/tools-hub; do NOT retire); E-255-09 takes the REPURPOSED branch (~6-AC memory rewrite). Both gates lifted. Matches VISION D4. (This also resolves the handoff-vs-recon discrepancy PM flagged — the 2026-07-05 refocus stands.)
- **E-193 → ARCHIVE as ABANDONED** (E-255-06): move to `.project/archive/` with ABANDONED status + reason (dashboard premise deleted in E-239, agent-browser never installed). No replan.
- **E-073 → E-255-04 owns the endpoint-doc corrections; shrink/archive E-073** (E-255-06 triage): archive it or shrink to only what 04 doesn't cover (PM's call at triage time; 04 is the owner).
- **Stale-READY ~60-day rule → SKIP (not adopted).** No standing context-layer rule; E-255-06 triages the current stale-READY epics (E-072/E-174/E-175) this once. No CA rule-creation sub-item.

### Resolved by main (2026-07-07)
- **SE on the dispatch team → NO new SE.** R-01 is a two-owner pass: api-scout (F, G, E-211, recovery command) + data-engineer (`pitches_7d` in `src/api/db.py`). Add SE later only if a genuine code-behavior JUDGMENT surfaces during R-01 (escalate to main).
- **docs-writer AC-8/AC-9 → FACTS in R-01, not design decisions.** AC-8 recovery command determined in R-01; AC-9 host-exec DEFAULTS to `docker compose exec app …`, confirmed in R-01 against compose/Dockerfile/runbook. See TN-8.

### Resolved by DE + PM verification (2026-07-07)
- **Dead-table set for E-255-06 AC-4 = `crawl_jobs` + `coaching_assignments` only.** DE's `src/` sweep + PM verification: `user_team_access` is LIVE (non-admin grant mechanism — do not capture); `team_opponents` was already DROPPED in migration 008 (gone, not retained — PM verified `DROP TABLE team_opponents` at migrations/008 L75); `programs` is unqueried-but-FK-load-bearing (exclude). Folded into story 06 AC-4.

**All planning Open Questions are resolved; all 6 domain docket-confirmations folded; internal review + Codex spec review (3 iterations) complete.** Epic is READY (see History scorecard). Dispatch authorization is separate.

## History
- 2026-07-04: Created as a DRAFT capture stub from the platform audit (CE-5). Not refined; not dispatchable.
- 2026-07-05 (E-250 dispatch): The agent-memory `PlayerTeamSeason` cleanup listed in the DE + baseball-coach own-memory dockets was PULLED FORWARD into E-250 (per user direction) and is DONE — `PlayerTeamSeason` scrubbed from `data-engineer/{MEMORY.md, endpoint-schema-notes.md}`, `baseball-coach/coaching-decisions.md`, and `claude-architect/agent-blueprints.md`. CE-5 must NOT re-plan the `PlayerTeamSeason`-specific cleanup; the BROADER own-memory sweeps remain in scope.
- 2026-07-05 (vision curation): VISION.md rewrite + vision-signals clearing DONE. The §3 curation *decisions* were made and recorded in the PM curation handoff; their context-layer *codification* remains CE-5/CA work (E-255-03).
- 2026-07-07: Refined from stub to full DRAFT — 9 per-owner stories + ACs written by PM in discover→plan mode. Discovery verified open-vs-discharged docket state against current files (5 intervening epics). User decisions surfaced as Open Questions.
- 2026-07-07: All 6 domain docket-confirmations (CA, api-scout, docs-writer, baseball-coach, data-engineer, ux-designer) folded. Corrections included the coach `coaching-decisions.md` L19 ghost-entity catch (PM clean re-read), the DE `team_opponents`-already-dropped correction (PM verified `migrations/008`), and the pitches_7d direction. R-01 fact-verification spike added (proxy-first, main-checkout pre-dispatch).

### Review Scorecard (READY 2026-07-07 — all findings folded)
| Pass | Findings | Outcome |
|------|----------|---------|
| Internal iter-1 — CR spec audit | 3 (1 MUST-FIX + 2 SHOULD-FIX) | all folded (R-01 commit-before-worktree; CLAUDE.md agent-table rows; L172 non-exhaustive enum) |
| Internal iter-1 — Holistic team review (6 domain lenses) | combined internal-round triage = **9 ACCEPT / 4 DISMISS** (13 findings de-duped across CR+holistic) | 9 folded; 4 dismissed as already-coherent/already-landed, each verified by clean re-read + literal quote (M4 05↔R-01 graph coherent; L2 regression-guard, L3 root-paths, Me2-core agent-rows — all already present) |
| Codex spec review — iter-1 | 4 | 4 ACCEPT / 0 DISMISS (dispatch-contract deepen; story-05 root-doc conflict; 2 propagation/testability) |
| Codex spec review — iter-2 | 6 (2 P1 + 3 P2 + 1 P3) | 6 ACCEPT; the 2 recurring P1s escalated to Jason → **P1a** reclassify R-01 as pre-dispatch Step-0 spike, **P1b** MOVE both root runbooks to `docs/admin/` (root-cause fix) |
| Codex spec review — iter-3 | 3 (2 P1 + 1 P2) | 3 ACCEPT (trigger-7 count propagation across 3 live sites; git-mv → Step 0 for single-specialist dispatch; lifecycle-policy target named). Prior 2 P1s NOT re-raised — converged. |

Domain experts consulted: baseball-coach, api-scout, claude-architect, data-engineer, ux-designer (+ docs-writer). A consistency sweep ran after every incorporation round.
- 2026-07-07: **Status → READY.** Quality checklist passed; all Open Questions resolved; all review findings across 1 internal + 3 Codex iterations folded and consistency-swept. Dispatch is a separate authorization (this was a "plan with review" trigger). Pre-Dispatch Step 0 (R-01 spike + runbook git mv) and the dispatched set 01–09 are dispatch-time actions, not part of the planning commit.
