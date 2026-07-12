# E-255-R-01: Live/code fact-verification pass (MAIN checkout, pre-dispatch)

## Epic
[E-255: Truth Sweep — Context Layer, API Docs, Runbooks](epic.md)

## Status
`TODO`
<!-- DISPATCH-SEQUENCING (not a normal worktree story): the main session runs R-01 in the MAIN
     checkout BEFORE it invokes the implement skill's worktree-creation step, commits the artifact
     to main, THEN creates the epic worktree from that commit. See Context + epic TN-6. -->

## Description
After this spike is complete, the six facts that the correction stories cannot safely read from the (suspect) doc prose are verified against ground truth and recorded in `.project/research/E-255-verified-facts.md`. This unblocks the fact-dependent corrections (E-255-01, -02, -04, -05) and removes guesswork from the load-bearing items.

## Context
This is a fact-gathering spike, not a doc-correction, and it is **NOT dispatched as a normal worktree story.** The standard implement-skill flow creates the epic worktree first and runs all story work inside it (`.claude/skills/implement/SKILL.md`) — but R-01 must run in the MAIN checkout (it needs `.env`/creds + proxy captures the worktree lacks, and its artifact must be committed to main so the worktree can branch from a commit that contains it). **Execution order the main session honors at dispatch time: (1) main session runs R-01 in the MAIN checkout (api-scout lead + DE), (2) commits `.project/research/E-255-verified-facts.md` to `main`, (3) THEN creates the epic worktree from that commit, (4) dispatches 01/02/04/05 as normal worktree stories that Read the committed artifact.** This is an epic-local sequencing note the main session orchestrates — not a general dispatch-skill/CLAUDE.md change (the pattern is specific to this epic's fact-gathering root). **Two-owner pass (no new SE): api-scout leads** (direct-routing exception for exploration; owns F, G, E-211, and the `bb creds` recovery-command determination) **and data-engineer supplies the `src/api/db.py` code read** (pitches_7d — DE's shared-query domain). Add SE later only if a genuine code-behavior JUDGMENT (not a read) surfaces — escalate to main if so. The artifact is the single source the correction stories cite; they do not re-derive these facts.

## Acceptance Criteria
- [ ] **AC-1** (F — proxy-first, HIGHEST RISK; api-scout): Given the game-summaries doc (L52) claims `game_stream.id` for BOTH boxscore and plays with "different UUIDs", when F is settled PRIMARILY from the proxy captures (`proxy/data/sessions/2026-03-09_062059/` + `2026-03-11_032625/`, which contain successful boxscore + plays requests) + cached responses + working code — attempting a fresh authenticated curl ONLY if the captures are inconclusive, and flagging the user that `.env` creds are ~4 months past the 14-day refresh (a live curl would just fail) — then the ACTUAL captured behavior is recorded, NOT a naive `game_stream.id → event_id` swap. Specifically record: (a) the `/game-stream-processing/{id}/…` form takes the SAME id for boxscore AND plays (contradicting L52's "different UUIDs"); (b) TWO plays URL forms exist (`/game-stream-processing/{id}/plays` and `/teams/{team}/schedule/{event_id}/plays`); (c) map the captured id (e.g. `3cab6a64…`) back to its game-summaries record so the per-endpoint id mapping is unambiguous. (Consult-proxy-data-first per `feedback_consult_proxy_data`.)
- [ ] **AC-2** (G — public, no creds; api-scout): Given the `team_season` shape returned by **`GET /public/teams/{public_id}`** (doc `get-public-teams-public_id.md` — NOT the UUID→public_id bridge `get-*public-team-profile*.md`, which has no `team_season`) is documented as an object with `.year` but a cached sample shows `season` a bare string and `year` flat at `team_season.year`, when a plain public curl confirms the current shape, then the verified `team_season` structure is recorded (feeds E-255-04's endpoint doc AND E-255-01/02's data-model.md + testing.md worked example).
- [ ] **AC-3** (pitches_7d — code fact; data-engineer): Given the audit says `key-metrics.md`'s `pitches_7d` NULL vs 0 semantics are INVERTED, when `get_pitching_workload()` in `src/api/db.py` (L205-209) is read, then the verified direction is recorded as authoritative — **`0` = no outings in the 7-day window** (LEFT JOIN miss), **`NULL` = had outing(s) but ALL pitch counts unrecorded / unknown**, **`SUM` = normal** (DE pre-confirmed this; the record makes it the source CA's E-255-02 corrects `key-metrics.md` to).
- [ ] **AC-4** (E-211 self-heal — code fact; api-scout): Given the `gc-uuid-bridge.md` Storage Rule "never overwrite existing gc_uuid" contradicts the deliberate E-211 self-heal overwrite, when the actual E-211 self-heal behavior is read from the code, then the real overwrite condition is recorded so the rule can be reconciled to reality.
- [ ] **AC-5** (recovery command — command-surface fact; api-scout, PRE-RESOLVED): Given `operations.md` names the nonexistent `bb creds login` as the recovery step for a hard-FAILED all-boxscores-blocked run, when the real `bb creds` surface is confirmed (subcommands: import/refresh/check/extract-key/capture/setup — no `login`), then the recovery command is recorded as **`bb creds refresh`** (first-line — renews the access token from the refresh token, matching the idiom at operations.md:418 + getting-started.md:137), with **`bb creds import` / `bb creds setup web`** as the fallback if the refresh token is dead. Feeds E-255-05 AC-8.
- [ ] **AC-6** (host execution — config fact; api-scout, PRE-RESOLVED): Given the production runbook uses bare `bb creds setup web` (L144) + bare `python scripts/backup_db.py` (L300/411/455, incl. a host cron L428) while the package is pip-installed ONLY in the container (Dockerfile L30, no host install step), when confirmed against `docker-compose.yml` + `Dockerfile` + the runbook, then the invocation form is recorded as **`docker compose exec [-T] app …`** (e.g. `docker compose exec -T app python scripts/backup_db.py`) — api-scout confirmed prod does NOT bootstrap on the bare host. Feeds E-255-05 AC-9. (Non-blocking: whether the daily-backup cron ultimately uses container-exec vs a documented host install is <OPERATOR-REDACTED>'s deployment-owner call — api-scout surfaces it as an FYI at the READY summary; the truth-sweep default is `docker compose exec`.)
- [ ] **AC-7**: Given all six facts, when recorded, then `.project/research/E-255-verified-facts.md` exists with one section per fact (F/G/pitches_7d/E-211/recovery-command/host-exec), each stating the verified truth + its source (endpoint call evidence, file:line, or config file), consumable by E-255-01/02/04/05 as deferred context.

## Technical Approach
Run in the main checkout. AC-1 (F) is settled proxy-first (captures + cached responses + working code; a fresh authenticated curl is a last resort and will likely fail on the ~4-month-stale creds — flag the user rather than block). AC-2 is a plain curl (public endpoint, no creds). AC-3/AC-4 are code reads (`src/api/db.py`, the E-211 self-heal path). AC-5/AC-6 are command-surface/config reads (`bb creds --help`, `docker-compose.yml`, `Dockerfile`, the runbook). Record verified facts + evidence; do not edit any doc in this spike (that is the correction stories' job).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-255-01 (team_season shape), E-255-02 (team_season shape, pitches_7d, E-211 self-heal), E-255-04 (game_stream.id, team_season shape), E-255-05 (recovery command, host-exec form)

## Files to Create or Modify
- `.project/research/E-255-verified-facts.md` (new artifact)

## Agent Hint
api-scout

## Handoff Context
- **Produces for E-255-01**: verified `team_season` shape for data-model.md.
- **Produces for E-255-02**: verified `team_season` shape (testing.md), `pitches_7d` NULL/0 semantics (key-metrics.md), E-211 self-heal behavior (gc-uuid-bridge.md).
- **Produces for E-255-04**: verified per-endpoint ID params (game_stream.id vs event_id, 5 sites + fallback), `team_season` shape.
- **Produces for E-255-05**: the correct `bb creds` recovery command (AC-8) and the confirmed host-execution form (AC-9, default `docker compose exec app …`).

## Definition of Done
- [ ] All six facts recorded with evidence in the artifact
- [ ] No doc edited in this spike
- [ ] **`.project/research/E-255-verified-facts.md` is committed to `main` BEFORE the epic worktree is created** — otherwise `git worktree add` won't contain the file and the worktree correction stories (01/02/04/05) can't Read it (worktree-isolation forbids committing inside the worktree). This is the hand-off gate from R-01 (main) to the dispatched stories (worktree).
- [ ] Artifact path communicated to CA, api-scout, and docs-writer for the correction stories

## Notes
This spike exists because (a) the doc prose under correction is exactly the thing in doubt, so it can't be the source of truth, and (b) worktrees can't make authenticated GC calls (TN-6). Owners settled by main (2026-07-07): api-scout + DE, no new SE; the two docs-writer runbook items (recovery command, host-exec form) are FACTS resolved here, not user design decisions. **F-evidence starting points (api-scout, day one): proxy captures `proxy/data/sessions/2026-03-09_062059/` + `2026-03-11_032625/` (successful boxscore + plays), and the `3cab6a64…`→game-summaries cross-ref.**
