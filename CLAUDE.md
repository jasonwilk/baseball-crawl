# baseball-crawl

**Simple first. Complexity as needed.** Build the smallest working thing, then iterate. Don't
design for scale, generality, or futures that have not arrived. One file beats a framework, a
script beats a pipeline, a dict beats a class - until it doesn't. When in doubt, leave it out:
adding is easy, removing is hard.

## What this product is

Reports-first: generate a scouting report for a GameChanger team by its `public_id`, share the
link. That is the product as actually used.

**Any team, by `public_id`** - high school, Legion, USSSA/travel youth. A 9U or 14U team in the
database is a real user's team; never reason "this is a high-school program, so a youth team is
junk", which nearly discarded 84 real teams (2026-07-25). Lincoln Standing Bear HS is the
operator's own program and proving ground, not the limit.

**One season, one report at a time.** Non-goals, deleted in E-239 and not to be rebuilt:
cross-team player identity, multi-season rollups, longitudinal tracking. Breadth (any team) does
not license depth (any season).

**We automate what a coach could do by hand.** Everything gathered is already visible to any
GameChanger user through the normal UI - we scale the manual work, we do not access hidden data.
Prefer the API; screen-scrape only for data already visible in the UI.

**North star: always get closer to byte-identical play ingestion.** Every ingestion change moves
plays-derived stats toward GameChanger's official box scores, never away. Run
`bb report reconcile-scoreboard` before and after such a change; it is a diagnostic, not a gate.

**Two destructive seams - name them before running either.**

- `bb report generate` is NOT read-only: it hard-deletes `games` and their whole child surface
  (reconcile-at-load) and unreachable `teams` / `players` / `team_rosters` (orphan reclamation).
  Report deletion and `bb report cleanup` run reclamation too.
  A THIRD condition landed 2026-08-15: an opponent-identity divergence collapse merges the
  stub-headed row away, deleting it.
- `bb db purge-scouting` wipes 20 of 27 tables, keeping only identity/auth/bootstrap: logins
  survive, team-access grants do not. `--force` (override the production refusal) and `--yes`
  (skip the prompt) are SEPARATE flags.

More: `docs/VISION.md`, `docs/ROADMAP.md`.

## How work gets done here

**Chunk lifecycle - walk every step, and state your current step whenever you report.**
One-sentence diff? Ask, then skip to step 4 with "small change: no spec".

1. **SPEC** - Enter plan mode yourself if the operator hasn't, interview, and write
   `.project/specs/<date>-<slug>.md`: one page - goal, files, out-of-scope, verification commands,
   progress log, no person's name. Verify every LOAD-BEARING claim you cite: an inherited claim is
   unverified, and unverified premises are where stubs come from.
2. **SPEC-REVIEW** - Plan mode cannot write files, so the flow is: ExitPlanMode presents an
   OUTLINE, and the operator's approval there authorizes exactly one thing - WRITING THE SPEC
   FILE. Never implementation. Then, in order: write the spec, run
   `./scripts/codex-spec-review.sh <path>` (mandatory when big or destructive; read its
   `RESULT_FILE`, not the preview), fold the findings in, and only then present the spec for
   commit approval. Implementation starts only from a COMMITTED spec, in a fresh session.
3. **EXECUTE** - In a FRESH session, from the spec. A spec is a CLAIM: audit it against the repo
   first. The spec, not the chat, carries state. Leave at a boundary - context bar yellow, or two
   failed corrections - by updating the progress log and going to step 9.
4. **VERIFY** - Run the spec's named commands. A chunk touching `src/`, `tests/`, or `migrations/`
   needs the FULL suite green. No green, no done.
5. **REVIEW** - Run `/code-review`; add `/security-review` on auth, serving, PII, or deletes.
   Both are OPERATOR-TYPED - a session cannot invoke them, so stop and ask. Codex review is
   REQUIRED when the chunk touches `src/`, a second opinion on request otherwise. `/simplify`
   is optional and runs BEFORE `/code-review` (its fixes need reviewing too). Docs-only chunk:
   PII gates alone. A review covers EVERY change since the chunk's base, committed or not -
   name that range to the reviewer and verify it is what the review received.
6. **SCAN** - Run `python3 src/safety/pii_scanner.py --staged` and compare scanned-count to
   staged-count: `SKIP_PATHS` blinds it to whole trees (`.claude/` among them). Give each skipped
   staged file a manual pass with a positive control.
7. **APPROVE** - Flip the spec's Status first (values in step 9) so it rides this commit.
   Stage by explicit PATH, never `add -A`; re-diff after staging; present that diff to the
   operator and wait for approval. Approval DIES WITH ITS COMMIT: a finding arriving after
   an approved commit produces a fix brought to the operator, never another commit.
8. **COMMIT** - Commit, then confirm `[pii-hook] PII scan passed.` printed. Its ABSENCE is the
   alarm: if it is missing, stop and investigate; don't assume it ran. It is a receipt, not a
   first check.
9. **HANDOFF** - Name every discovered thing and WHERE IT WENT - stub, `IDEAS.md` line, vision
   signal, or board residual; a residual parked in a spec moving to `done/` must ALSO land on
   the board; "nothing discovered" is a claim to defend. The Status from step 7 reads
   `COMPLETE (this commit)`, `READY`, `PARKED + why`, `STUB`, or `OPEN + what decision is owed`;
   a COMPLETE also names `acceptance: run` or `acceptance: owed at <chunk>`, and moves to
   `.project/specs/done/` in this commit - no hash needed, `git log --follow` supplies it.
   Only post-commit steps (a backfill, a migration run) earn a second small results commit, and
   THAT one cites hashes. Then report what landed, what's carried and where, the exact
   next-session prompt, and the literal last line
   `Type /clear now, then paste the prompt above.`
10. **CLEAR** - The operator types `/clear`, on a clean tree or a written progress note. A fork is
    never a substitute.

**Principles**

- **A.** Get operator approval for every commit.
- **B.** Treat a fork as the SAME BRAIN, not a second worker: never fork to parallelize, keep
  tangents read-only, close them after. A finished session answers no new questions - new
  question, new session. Exit discovered work, never work it here: broken or owed becomes a spec
  stub, someday becomes one line in `.project/specs/IDEAS.md`, direction goes to
  `docs/vision-signals.md`.
- **C.** Shape questions to the operator, who has NOT been following the session: give each
  decision, in order, what you were doing, what you found, what the decision is, the options with
  their consequences, your recommendation. Use no term or option they haven't been shown; define
  subagent language on relay.
- **D.** Use subagents narrowly: `Explore` for search, `api-scout` for API archaeology,
  `baseball-coach` for coaching semantics, `/code-review`'s fork for review. Don't delegate what a
  handful of tool calls finishes.
- **E.** Send lessons to memory; promote one to a rule only after it bites twice, at the
  per-3-chunk audit, never mid-flight. Keep the destructive seams in this file.
- **F.** At that audit, also do housekeeping: every spec in `.project/specs/` must read COMPLETE
  or PARKED, or belong to a live chunk; a STUB or OPEN one gets a decision; curate `IDEAS.md`.
  Close any session older than the last audit.
- **G.** Count a clean result only with a POSITIVE CONTROL: prove the instrument can fail before
  you trust its pass. A scan, probe, or gate you cannot show failing proves nothing.
- **H.** Use a worktree for ISOLATION, never ceremony - only when this session cannot safely write
  the shared checkout (backgrounded, or a sibling is writing). Enter, commit, land on main, remove
  worktree and branch, all in one session; never park work in one. Branches are worktree PLUMBING
  (a worktree needs its own HEAD), never workflow: this repo is trunk-based, `main` is the only
  long-lived branch, no feature branches, no PRs. Police your own Bash writes (`cp`, `mv`,
  redirects, `sed -i`); the guards cannot see them.
- **I.** A cap is a TRIPWIRE, not a wall: when one binds against load-bearing content, stop and
  bring the operator the trade. Never compress meaning to fit; never raise a cap yourself.

## Line of march

Read `.project/specs/README.md` before proposing scope: NOW / NEXT / PARKED DECISIONS / STANDING
RESIDUALS. Step 9 updates it. Individual chunk specs sit beside it as `<date>-<slug>.md`.

## Facts

**Stack.** Python end-to-end, version governed by `.python-version` (keep Dockerfile,
`devcontainer.json`, `pyproject.toml` in sync with it). FastAPI + Jinja2, server-rendered HTML;
SQLite (WAL) at `./data/app.db`; Docker Compose local and production; Cloudflare Tunnel ingress;
app-internal auth (magic links + passkeys); pip-tools (`*.in` to `*.txt`). Local:
`docker compose up`, then http://baseball.localhost:8001. Production: `https://bbstats.ai`.

**GameChanger API** - undocumented; our spec is `docs/api/README.md`. Five gotchas: `/teams/*` and
`/me/*` need `gc-token` + `gc-device-id` and must handle expiry, public endpoints need neither.
Public URL shapes are not uniform (the roster inverts to `GET /teams/public/{public_id}/players`),
so read the endpoint doc. Public game ids are perspective-specific, so diffing stored ids against
a fetch reports false removals unless you perspective-control first; authenticated
`game-summaries` returns a stable `event_id`. `root_team_id` is not `gc_uuid`, so never store one
in the other's column; a present `progenitor_team_id` means the coach linked via team lookup, a
reliable dedup signal. Resolve `public_id` to `gc_uuid` via `POST /search` filtered by `public_id`.

**Commands.** `bb` is the operator CLI and the primary interface; `bb --help` lists everything.
Groups: `bb status`, `bb creds`, `bb data`, `bb proxy`, `bb db`, `bb report`. Read
`docs/admin/operations.md` for per-command behavior, flags, and exit codes - it outranks any CLI
docstring.

**Security.** Keep credentials and tokens out of code, logs, commit history, and agent output;
secrets in `.env` (gitignored) locally, env vars in production; strip auth headers from any stored
API response. Treat GameChanger session tokens as sensitive at all times.

**Proxy boundary.** mitmproxy runs on the Mac host, NOT in this devcontainer - never start, stop,
or manage it; ask the operator to run proxy commands. You may read `proxy/data/`. Bright Data runs
inside the container as part of the normal HTTP session.

**Git.** Use conventional commits (`feat:`/`fix:`/`refactor:`/`test:`/`docs:`/`chore:`); explain
the why.

## Pointers

Rules in `.claude/rules/` load themselves on matching paths; `tool-discipline` always loads. What
each answers:

- `canonical-seams` - where the single entry point already is (DB paths, connections, upserts,
  deletes, team search, reconcile-at-load, orphan reclamation). Read it before adding a second
  path to anything; drifting copies are this repo's recurring defect.
- Reports and admin surfaces: `architecture-subsystems`, `admin-ui`, `display-philosophy`,
  `jinja-safety`, `browser-render-testing`.
- Schema and provenance: `data-model`, `migrations`, `perspective-provenance`.
- Stats and pitching eligibility: `key-metrics`, `pitch-rules`.
- Reaching GameChanger: `auth-module`, `http-discipline`, `gc-uuid-bridge`, `api-docs`,
  `proxy-boundary`.
- Writing code: `testing`, `python-style`. Safety: `pii-safety`. Stack: `app-troubleshooting`,
  `devcontainer`, `dependency-management`.
- Docs and vision: `documentation`, `vision-signals` - capture vision signals as you notice
  them; "curate the vision" is the operator's trigger to review them, and `docs/VISION.md` is
  edited only in that deliberate session.
