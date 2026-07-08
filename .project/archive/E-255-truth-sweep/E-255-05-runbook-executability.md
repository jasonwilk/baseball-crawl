# E-255-05: Operator runbook executability corrections (2 root runbooks pre-relocated in Step 0)

## Epic
[E-255: Truth Sweep — Context Layer, API Docs, Runbooks](epic.md)

## Status
`DONE`

## Description
After this story is complete, the operator runbooks live under `docs/admin/` (the two `docs/` root runbooks are relocated there) and are executable end-to-end on a fresh machine: no phantom migration numbers, no false "plays removed" claim, no nonexistent commands, a correct post-reset health-check URL, dashboard-verification steps rewritten to the reports model, and a correct rebuild-procedure description. Two command corrections (recovery command, host-exec form) apply the facts E-255-R-01 verified.

## Context
docs-writer owns `docs/admin/`. Scoped from docs-writer's own docket recon (relayed via main), split into seven mechanical (unblocked) ACs (AC-1..AC-7), two command corrections (AC-8/AC-9) that apply command facts verified in E-255-R-01 (the recovery command; the host-exec form, default `docker compose exec app …`) — resolved by main 2026-07-07 as facts, not design decisions (TN-8) — and a relocation (AC-10). Re-verify per TN-1 (migration numbers, commands changed across the 5 intervening epics).

**Root-doc ownership — RESOLVED by MOVE (Jason 2026-07-07, Codex P1b).** `docs/production-deployment.md` + `docs/cloudflare-access-setup.md` sit in the `docs/` ROOT, which `.claude/rules/documentation.md` says docs-writer MUST NOT modify. Rather than an epic-scoped exception, Jason chose the root-cause fix: **MOVE both into `docs/admin/`** (docs-writer's clean remit — they ARE operator runbooks). After the move there is NO ownership conflict and NO rule change; docs-writer owns them by directory (documentation.md's own structure). See AC-10 + TN-9.

## Acceptance Criteria (mechanical — unblocked)
- [ ] **AC-1**: Given `operations.md` documents phantom migrations 006/009/012/015 (and 014) with fabricated content while the real set is 001–010 (real 006 = `drop_season_fallback.sql`, real 009 = `spray_chart_type_unique.sql`), when corrected, then no phantom migration writeup remains — each documented migration matches an actual `migrations/*.sql` file.
- [ ] **AC-2**: Given `operations.md`'s FALSE "plays ingestion pipeline removed in E-239" claim (L190, L495) — the plays pipeline is alive (`plays_parser.py` + `plays_loader.py`, invoked every report generation; E-245 did in-place plays repair; only dashboard/member-sync was removed in E-239), when corrected, then the doc states the plays pipeline is live (consistent with CLAUDE.md's play-ingestion North Star).
- [ ] **AC-3**: Given the post-reset health-check URL (`curl http://localhost:8000/health` bare — hits Traefik with no Host header → 404s every time), when corrected, then it reads `http://localhost:8001/health` (matching the getting-started.md convention / CLAUDE.md in-container access).
- [ ] **AC-4**: Given `docs/admin/getting-started.md`'s "Install Python Dependencies" step runs only `pip install -r requirements.txt` and never `pip install -e .` (so `bb` never lands on PATH outside the devcontainer), when corrected, then the guide installs the project (the `bb` entry point resolves after following it).
- [ ] **AC-5**: Given the dashboard-verification sections (`docs/admin/production-deployment.md` §5.5 + `docs/admin/cloudflare-access-setup.md` §10/§7.1/§7.3, bypass path `/scouting/game-day` — the post-move paths per AC-10) that verify a deleted coach-login-to-dashboard model, when rewritten, then verification uses the current surfaces: (a) admin login reaches `/admin/reports`, (b) `/reports/{slug}` is reachable with no login, and the CF-Access bypass example references `/reports/*` (not `/scouting/game-day*`).
- [ ] **AC-6**: Given `docs/admin/operations.md`'s "Development Database Reset" section says "drop and recreate the database with **seed data**:" just before the `python scripts/reset_dev_db.py` block (reset produces an EMPTY db since E-228), when corrected, then that line reads "empty database" (matching getting-started.md).
- [ ] **AC-7**: Each corrected file's "Last updated" / "Source" staleness header reflects this pass.

## Acceptance Criteria (apply E-255-R-01 command facts)
- [ ] **AC-8**: Given `operations.md` L719's nonexistent `bb creds login`, when replaced with the E-255-R-01-verified recovery command — **`bb creds refresh`** (first-line) with **`bb creds import` / `bb creds setup web`** as the dead-refresh-token fallback — for a hard-FAILED all-boxscores-blocked run, then the doc names those commands (no `bb creds login`).
- [ ] **AC-9**: Given `docs/admin/production-deployment.md`'s bare host commands that fail on a Docker-only host (bare `bb creds setup web` at L144; bare `python scripts/backup_db.py` at L300/411/455 incl. the host cron at L428 — the post-move path per AC-10) — the package is pip-installed ONLY in the container (Dockerfile L30), no host install step exists — when corrected to the E-255-R-01-confirmed form **`docker compose exec [-T] app …`** (e.g. `docker compose exec -T app python scripts/backup_db.py`), then those sites document that form with runnable commands. (Non-blocking: the daily-backup cron's container-exec-vs-host-install is Jason's deployment-owner call — api-scout surfaces it at READY; the truth-sweep default is `docker compose exec`.)

## Acceptance Criteria (inbound-ref reconciliation after the Step-0 relocation — P1b)
> **PRECONDITION (Pre-Dispatch Step 0, NOT this story):** the physical `git mv` of both runbooks into `docs/admin/` is done in main by api-scout before the worktree is created (Codex iter-3 P1 — keeps this story single-specialist/no-Bash). By the time story 05 runs, `docs/admin/production-deployment.md` + `docs/admin/cloudflare-access-setup.md` already exist and the old root paths are gone. See epic Step 0 + TN-9.
- [ ] **AC-10**: Given the two runbooks are already relocated to `docs/admin/` (Step 0), when docs-writer reconciles the inbound refs, then: (a) the FOUR `docs/admin/`-internal refs to `../cloudflare-access-setup.md` are updated to same-dir `cloudflare-access-setup.md` — `docs/admin/architecture.md:254`, `docs/admin/operations.md:40` & `:903`, `docs/admin/README.md:24`; (b) internal cross-refs INSIDE `production-deployment.md` to `cloudflare-access-setup.md` (L121/167/174/196/204) are verified valid (both files moved together → same-dir links stay correct; no edit expected); (c) the ONE ref outside docs-writer's ownership — `CLAUDE.md:40` — is updated in **story 01** (TN-9 coupling), NOT here; (d) intentionally NOT updated (out of scope, flagged): `.project/archive/**` (immutable epic history), `reviews/e125-cr-infra.md` (historical artifact), and `PLATFORM-AUDIT.md` (uncommitted audit source Jason is working — a prose reference at production-deployment.md:138, not a link).

## Technical Approach
Read each runbook in full; verify every command against `bb --help`, every migration number against `migrations/` (001–010), every URL against CLAUDE.md. Where a step verified a deleted surface, rewrite it to verify the surviving reports flow. AC-8/AC-9 apply the command facts E-255-R-01 records in `.project/research/E-255-verified-facts.md` — no design decision is made in this story. The two runbooks arrive already relocated to `docs/admin/` (Pre-Dispatch Step 0); this story only edits their CONTENT + reconciles the four same-dir inbound refs (AC-10) — no `git mv`, no Bash, single specialist.

## Dependencies
- **Blocked by**: Pre-Dispatch Step 0 (the two runbooks relocated to `docs/admin/` + the R-01 artifact committed to main — both preconditions for this story's worktree). E-255-R-01 artifact supplies the AC-8 recovery command + AC-9 host-exec form; AC-1..AC-7 + AC-10 need no fact input.
- **Blocks**: None
- **Couples with**: E-255-01 (CLAUDE.md:40 runbook-path update — TN-9; both must land `docs/admin/production-deployment.md`).

## Files to Create or Modify
- `docs/admin/production-deployment.md` (already relocated from `docs/` root in Step 0; content corrections AC-5/AC-9)
- `docs/admin/cloudflare-access-setup.md` (already relocated from `docs/` root in Step 0; content AC-5)
- `docs/admin/operations.md` (AC-1/AC-2/AC-6/AC-8 + AC-10 `../cloudflare-access-setup.md` → `cloudflare-access-setup.md` at :40 & :903)
- `docs/admin/getting-started.md` (AC-4)
- `docs/admin/post-reset-guide.md` (AC-3)
- `docs/admin/architecture.md` (AC-10 ref update at :254)
- `docs/admin/README.md` (AC-10 ref update at :24)
- (any other `docs/admin/` runbook carrying the phantom-migration / dashboard-verification / rebuild-procedure content found during re-verification)

## Agent Hint
docs-writer (single specialist — the `git mv` relocation is done pre-dispatch in Step 0, so this story needs no Bash).

## Definition of Done
- [ ] AC-1..AC-10 pass
- [ ] 4 same-dir refs updated; internal cross-refs verified valid; CLAUDE.md:40 handled in story 01 (TN-9). (The physical relocation is a Step-0 precondition, not verified by this story.)
- [ ] Every documented command/URL/migration verified to exist / be correct
- [ ] Dashboard-verification rewritten to the reports model (not deleted)
- [ ] Staleness headers updated

## Notes
docs-writer may READ but not modify agent-maintained docs (`docs/api/**`, CLAUDE.md, rules) — the CLAUDE.md:40 runbook-path ref is CA's, handled in story 01 (TN-9). After the Step-0 move, no ownership exception is needed: `docs/admin/` is docs-writer's clean remit per documentation.md. AC-8/AC-9 apply the E-255-R-01 command facts (`bb creds refresh`; `docker compose exec [-T] app …`). Settled by main 2026-07-07.
