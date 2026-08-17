<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# Cap concurrent report generation on the admin generate path

**Date**: 2026-08-10 (stubbed) · spec pass 2026-08-16 · executed 2026-08-16/17 ·
**Status**: `COMPLETE (this commit)` — `acceptance: run`. **This Status RIDES the commit that
lands it** (lifecycle step 7 flips Status before staging), so it is true from that commit forward,
not before it.

Acceptance is RUN, not owed: the suite moved `4536 → 4551` (+15) at `RC=0` with zero skips at both
ends, and all **13** mutants matched expectations stated before each run. Reviewed across four
gates — `codex-spec-review` **4 rounds** (3 on the spec, 1 scoped to the amendment), 12 findings,
11 folded and 1 disputed as an unfoldable lifecycle artifact; `codex-review.sh` on the code,
3 findings, all fixed; `/code-review`, 6 findings, all verified first-hand and all fixed;
`/security-review`, **no HIGH or MEDIUM findings** (path traversal via the reaper's `slug`-built
unlink, reflected XSS via the new refusal banners, and the authz boundary were each traced and
ruled out).

⚠ **Read the AMENDMENT section before citing the "N = 2" ruling below** — it did not survive
execution. The admin page is ONE-AT-A-TIME.
**Source**: `.project/specs/README.md` — the chunk's own entry is in **NEXT**
("Generate-concurrency cap — the NEXT CHUNK in the ruled sequence"); **NOW** names the sequence it
sits in (same-listing detection → **generate-concurrency cap** → runs-as-scoreboard instrument →
full regenerate) without pointing at this file. Measured from a read-only log audit of the
2026-08-10 13:25–13:52Z operator run.
The stub's REPAIR half died with the "Regeneration hazard — RULED 2026-08-12" residual; this spec
covers the CAP only.

## Goal

After this chunk, `POST /admin/reports/generate` refuses a submission when 2 generations started
from that route are already in flight, and says so in the red banner on `/admin/reports`. Today
the route enqueues without any admission check at all, and the only ceiling in the system is the
anyio worker-thread pool. `busy_timeout` is NOT touched — waiting longer only moves the cliff.

## The defect, and which numbers are measured vs. re-derived

**MEASURED 2026-08-10, NOT re-derived in the spec session.** 51 `POST /admin/reports/generate` in
27 minutes reached **14 simultaneous generations** against one SQLite file; the 30s `busy_timeout`
was exhausted at the peaks, producing **243 `database is locked` tracebacks** — 121
`merge_player_pair` failures, 121 `dedup_team_players` collapse failures, 1 orphan-reclamation
failure — and leaving 13 teams with roster bloat. Log capture and extracted merge-pair CSV were in
a trainer session's scratchpad; re-derive from logs if you need them. **Nothing in this design
depends on their exact values** — the design depends only on "unbounded", which is verified below.

Carried from the stub so it is not re-discovered: this is **NOT** covered by archived IDEA-099,
which is scoped to non-triad `bb data` writers. This failure is inside the triad that already has
the timeout.

**VERIFIED at spec time (2026-08-16), re-verify at execution:**

- **F1 — the route has no admission check.** `src/api/routes/reports_admin.py:724`:
  `background_tasks.add_task(generate_report, gc_url)`. No lock, semaphore, queue, or in-flight
  counter exists anywhere in `src/` on this path.
- **F2 — every submission gets its own thread.** `generate_report` is a plain sync `def`
  (`src/reports/generator.py:1585`). Starlette 1.3.1 `BackgroundTask.__call__` sends a sync
  callable to `run_in_threadpool`, whose body is `await anyio.to_thread.run_sync(func)` (read from
  installed source). With no limiter passed, that uses the default limiter: measured in this
  container, `anyio 4.14.1`, `current_default_thread_limiter().total_tokens` → **40**.
- **F3 — the CHECKED-IN TOPOLOGY starts one process. That is narrower than "one process", and
  the difference is the cap's whole exposure.** What the repo proves is that the tracked launch
  files omit `--workers` and omit an `app`-service `command:` override — it does NOT prove nothing
  replicates the container at runtime (a second `docker compose` project, a scaled service, a
  hand-run `uvicorn`, a future orchestrator). Any of those multiplies the cap to `2 × processes`
  and trips no guard, because no guard can see them. Evidence for the narrow claim: `Dockerfile:48`
  is
  `uvicorn src.api.main:app --host 0.0.0.0 --port 8000` — no `--workers`; no gunicorn in
  `pyproject.toml` / `requirements*.in` / Dockerfile; `src/api/main.py:97` is a module-level
  `app`, not a factory. **Precisely on compose**: `command:` keys DO exist in the repo —
  `docker-compose.yml:32` (traefik) and `:55` (cloudflared), and traefik again in
  `docker-compose.override.yml.example` — but **none on the `app` service**, and no
  `deploy.replicas` anywhere. ⚠ This is the design's LOAD-BEARING PREMISE and it is one flag away
  from false. Partially guarded by a test (work item 4) — see F3b for the half no test can reach.
- **F3b — the OPERATIONAL INVARIANT the test cannot enforce, and it must be written down.**
  *While this cap stands, the app is deployed as exactly ONE process serving HTTP: one container,
  one uvicorn worker, not replicated.* The work-item-4 test enforces the half that lives in
  tracked files; **the runtime-replication half is enforced by nothing but this sentence**, which
  is why it goes in `docs/admin/operations.md` (work item 5) and not only here. State it as a
  deployment constraint, not as a fact about the world: a reader who scales the app and keeps the
  cap gets `2 × processes` concurrent generations and no warning of any kind.
- **F3a — the guard's own reach, stated honestly.** `docker-compose.override.yml` is **gitignored
  and untracked** (`.gitignore:35`), so it does not exist in CI and a guard cannot depend on it.
  The guard therefore covers the two TRACKED inputs that decide production: `Dockerfile` and the
  `app` service in `docker-compose.yml`. A local untracked override adding `--workers` to `app`
  would defeat the cap **in dev only** — production explicitly does not use that file (its own
  header says so) — and dev is one operator. The guard reads the override only if it happens to be
  present, and never fails on its absence.
- **F4 — a DB-count admission check would be materially weaker here.** The
  `reports.status='generating'` row is not written until the background task has parsed the URL
  and made a public-API fetch (`_ReportGeneration.run` steps 1 → 1b → 2+3,
  `src/reports/generator.py:1686-1707`), i.e. seconds after the click. Several fast clicks all
  pass such a count. It would also need reap-then-gate, since a crashed generation's row would
  block the door for up to `STALE_GENERATING_SECONDS` = 3600 (`src/reports/lifecycle.py:41`).
- **F5 — the house refusal shape is a 303 flash, not a status code.** Admin registers no
  custom-exception handler; `src/api/main.py` has handlers for 404 and 500 only, and no admin
  route returns 409. The three existing validation refusals redirect 303 to
  `/admin/reports?error=…` (`reports_admin.py:701-720`), rendered as the red banner at
  `src/api/templates/admin/reports.html:36-40`.

## Operator rulings that bind this spec (2026-08-16)

1. **Scope: the admin web page only.** The cap counts only generations started from
   `POST /admin/reports/generate`.
2. **N = 2.**
3. **The CLI path is uncapped BY DESIGN.** `bb report generate` and `bb report morning-run` write
   to the same WAL file and this cap cannot see them. This chunk guards the door the storm came
   through, not that one. **The full-regenerate chunk must state its own concurrency discipline —
   serial, or its own bound — in its own spec.**

A later reader arguing for N=1 must do it on cap grounds alone. The "re-generate SERIALLY" line in
the original stub belongs to the DE-SCOPED repair half and is not evidence about the cap.

## Files

- `src/api/routes/reports_admin.py` — edit: `threading` import, the cap constant, the module-level
  `BoundedSemaphore`, a non-blocking acquire in the route, a releasing background-task wrapper.
- `tests/test_admin_reports.py` — edit: the new behaviors, plus the single-worker premise guard.
- `.claude/rules/admin-ui.md` — edit: one line stating the generate route is capped and at what.
- `docs/admin/operations.md` — edit: "Generating a Report" (line ~555) gains the operator-visible
  refusal and its message.
- `.project/specs/README.md` — **already edited IN THE SPEC COMMIT, not at handoff**: the NEXT
  entry flips `STUB` → `READY` with the operator rulings and both residuals, and STANDING
  RESIDUALS' regeneration-hazard bullet gains consequence 3 (the regenerate owes its own
  concurrency discipline). Done here because the line of march requires NEXT to name every READY
  spec, and because a residual parked only in a spec that later moves to `done/` is a residual
  lost. At EXECUTION handoff (step 9) this entry moves out of NEXT as landed.

Not `CLAUDE.md`: this adds no destructive seam, and the byte cap is a tripwire not to be spent
here.

## The work

1. **Add the cap and its slots** to `src/api/routes/reports_admin.py`, near the existing
   module-level `_VALID_ROLES` (line 62):

   ```python
   MAX_CONCURRENT_ADMIN_GENERATIONS = 2
   _generation_slots = threading.BoundedSemaphore(MAX_CONCURRENT_ADMIN_GENERATIONS)
   ```

   `BoundedSemaphore`, not `Semaphore`, deliberately: a double-release bug raises `ValueError`
   loudly instead of silently inflating the cap. Carry the F2/F3 warrant in the constant's comment
   — the house style for a premise-bearing constant (cf. `_SAME_LISTING_MAX_DELTA_SECONDS`).

2. **Acquire LAST in the route** — after `_require_admin` and after all three URL validations,
   immediately before `add_task`. ⚠ **This ordering is the whole correctness of the change.**
   Acquiring earlier means every rejected empty/invalid/UUID URL returns without releasing and
   permanently burns a slot; two bad pastes would wedge the page. Pinned by a test, not a comment.

   ```python
   if not _generation_slots.acquire(blocking=False):
       return RedirectResponse(
           url="/admin/reports?error=" + quote_plus(
               f"{MAX_CONCURRENT_ADMIN_GENERATIONS} report generations are already "
               "running. Wait for one to finish, then try again."
           ),
           status_code=303,
       )
   background_tasks.add_task(_generate_report_releasing_slot, gc_url)
   ```

   Reject, not queue: a queued job the operator was told "started" that actually sits idle is a
   worse lie than an immediate refusal, and queuing would pin an anyio thread for the duration.

3. **Release in a `finally`** in a module-level wrapper:

   ```python
   def _generate_report_releasing_slot(gc_url: str) -> None:
       from src.reports.generator import generate_report
       try:
           generate_report(gc_url)
       finally:
           _generation_slots.release()
   ```

   The import stays INSIDE the function, as it is today at `reports_admin.py:723`. That is
   load-bearing for the existing tests: `tests/test_admin_reports.py:239` patches
   `src.reports.generator.generate_report` and asserts `assert_called_once_with(...)`, which only
   resolves through a call-time import.

4. **Guard the half of the premise that lives in tracked files (F3 / F3a).** A test that fails if
   a TRACKED launch file gains a way to start more than one worker, with a message naming this cap
   as what breaks. ⚠ Name it for what it checks, not for what we wish were true — it cannot see
   runtime replication (F3b), so a name like `test_the_served_process_count_is_one` would be a
   false claim in the test's own identifier. It reads **both** tracked inputs, not just the
   Dockerfile — that narrowness was a codex P2:
   - `Dockerfile` — the `uvicorn`/`gunicorn` line must carry no `--workers`, no `-w`, and no
     gunicorn worker-class flag.
   - `docker-compose.yml` — the `app` service must have no `command:` override and no
     `deploy.replicas`. (Parse the YAML; do not grep the whole file — `command:` legitimately
     appears on `traefik` and `cloudflared`, and a whole-file grep would fail today, vacuously.)
   - `docker-compose.override.yml` — checked the same way **only if present**; its absence is not
     a failure (F3a: untracked, absent in CI).

   Home it in `tests/test_admin_reports.py` beside the cap tests, so it dies with the cap if the
   cap is ever removed. (`tests/test_docker_build_context.py` also parses the Dockerfile and is the
   alternative home; it is scoped to `.dockerignore`/COPY, so putting an unrelated premise guard
   there would blur it.)

5. **Docs.** One line in `.claude/rules/admin-ui.md` on the reports-list bullet; and in
   `docs/admin/operations.md` under "Generating a Report", two things: the exact refusal message
   and why it exists, **and the F3b deployment invariant** — *while this cap stands, the app runs
   as exactly one process serving HTTP; replicating it multiplies the cap and nothing warns you.*
   That doc outranks any CLI docstring, so its wording is the contract, and F3b has no other
   enforcement anywhere.

## Tests

BDD shape per the 2026-08-15 authoring standard: class named for the situation, one behavior per
test, arrange/act/assert by blank line.

**The tests split into two kinds and the executor must not confuse them** (codex P1 caught this
spec asserting all seven would go RED, which is false).

**(A) RED-first — these CANNOT pass before the route change**, because today's route has no
admission check at all. Show each failing first.

1. `TestAdminGenerate_WhenTheCapIsReached::test_redirects_with_an_error_flash`
2. `TestAdminGenerate_WhenTheCapIsReached::test_does_not_enqueue_a_generation`
3. `TestAdminGenerate_WhenAGenerationFinishes::test_the_slot_is_returned`
4. `TestAdminGenerate_WhenTheGenerationRaises::test_the_slot_is_still_returned`
5. `TestAdminGenerate_WhenTwoRequestsRaceAtCapOne::test_exactly_one_wins` — `threading.Barrier(2)`
   on the acquire seam at N=1, modeled on the existing
   `tests/test_passkey.py:957::test_cap_hard_bound_under_concurrent_inserts`.

**(B) Guards that PASS TODAY BY CONSTRUCTION** — they pin a property the change must not break,
so RED-first does not apply and their only proof of worth is a mutation (step 4).

6. `TestAdminGenerate_WhenTheUrlIsInvalid::test_no_slot_is_consumed` — three bad POSTs (empty,
   malformed, UUID), then a valid one still enqueues. Green today because there are no slots at
   all; its worth is proven by mutant **M2** (acquire moved above the validations). This is the
   test for work item 2, and it is the one that catches the single worst way to get this change
   wrong.
7. `TestTheCheckedInTopology::test_no_tracked_launch_file_starts_extra_workers` — work item 4.
   Green today because `Dockerfile:48` already starts one worker; its worth is proven by mutant
   **M4**. The name is deliberately about tracked FILES, not about the served process count, which
   it cannot observe (F3b).

**Test mechanics the executor must not get wrong.** The semaphore is constructed from the constant
at import, so monkeypatching `MAX_CONCURRENT_ADMIN_GENERATIONS` changes nothing — a test must
replace `_generation_slots` itself with a fresh `BoundedSemaphore(n)` and restore it. There is no
injection seam at a module global; `testing.md` prefers DI, and this is the stated exception, not
an oversight. Every test that acquires a slot must release it, or it poisons later tests in the
same process.

**Test-scope discovery**: `tests/test_admin_authz_sweep.py:107` also POSTs this route (with
`mock_generate`). It acquires and — because TestClient runs background tasks synchronously —
releases. Confirm it still passes rather than assuming it.

## Out of scope

- **`busy_timeout`.** Untouched at 30000ms (`src/api/db.py:84`). Raising it was explicitly rejected
  by the stub: waiting longer moves the cliff.
- **The CLI and cron paths** — operator ruling 3 above. Their discipline belongs to the
  full-regenerate chunk's spec.
- **Repairing the 13 bloated teams and the race-created duplicate game.** De-scoped by the
  2026-08-12 regeneration ruling; the full regenerate replaces it.
- **Client-side submit-button disabling** on `admin/reports.html`. It would reduce accidental
  double-clicks but is not a cap and cannot be relied on. One line in `IDEAS.md` if wanted.
- **Any DB table, migration, or job/lease record.** None needed.

## Verification

Never trust a piped pytest exit code — redirect and capture `$?` separately.

0. **Precondition gate (F3 / F3a) — checks the tracked files only; F3b is not checkable here.**
   Both tracked inputs, not just the Dockerfile:
   `grep -n uvicorn Dockerfile` — expected the single `--host 0.0.0.0 --port 8000` line with no
   `--workers`; and read the `app` service in `docker-compose.yml` — expected no `command:` and no
   `deploy.replicas` (note `command:` legitimately appears on `traefik` and `cloudflared`, so read
   the service, do not grep the file). **If either is false the mechanism is wrong and the chunk
   STOPS** and comes back to the operator.
1. **Baseline — from a full RUN, not from `--collect-only`.** ⚠ A collected count is NOT a passed
   count: this suite has real `skip`/`skipif` paths (`tests/test_validate_api_docs.py`,
   `tests/test_cli.py`, `tests/test_outings_browser.py`, `tests/test_script_entry_points.py`
   among them), so "passed ≥ collected" is arithmetic that a perfectly green run can fail. This
   was a codex round-2 P2 against an earlier draft of this spec — do not reintroduce it.
   `python3 -m pytest > /tmp/base.txt 2>&1; echo "RC=$?" >> /tmp/base.txt`
   Record the WHOLE terminal line — passed, skipped, xfailed — plus `RC`.
   Measured 2026-08-16 on a clean tree, pasted verbatim from the file:
   `4536 passed, 1 warning in 103.42s (0:01:43)` with `RC=0`.
   ⚠ **Read that honestly**: in THIS container nothing skipped, so passed (4536) and collected
   (4536) happen to coincide. That is a property of this environment, not of the suite — the
   skipif paths named above are real and fire elsewhere (a missing chromium, `SKIP_BROWSER_TESTS`,
   an absent entry point). The arithmetic fix stands on the general unsoundness; do not conclude
   from today's equality that collected-vs-passed is interchangeable. Re-measure at execution and
   compare against YOUR run, not against 4536.
2. **RED — group (A) ONLY.** Add all seven tests, then run the five group-(A) tests:
   `python3 -m pytest tests/test_admin_reports.py -k "WhenTheCapIsReached or WhenAGenerationFinishes or WhenTheGenerationRaises or WhenTwoRequestsRaceAtCapOne" > /tmp/red.txt 2>&1; echo "RC=$?" >> /tmp/red.txt`
   — expected non-zero RC with **all 5 failing**, each for the RIGHT reason (read the failures;
   an import error is not a RED).

   Then group (B), tests 6 and 7, as its own command with its own expectation:
   `python3 -m pytest tests/test_admin_reports.py -k "WhenTheUrlIsInvalid or TheCheckedInTopology" > /tmp/greenb.txt 2>&1; echo "RC=$?" >> /tmp/greenb.txt`
   — expected `RC=0`, **2 passed**, at this same pre-change commit. A group-(B) test failing here
   means the TEST is wrong, not that the code is. Confirm both counts; "no failures" is not the
   same observation as "2 passed" when a selector can silently match nothing.
3. **GREEN, full suite.**
   `python3 -m pytest > /tmp/suite.txt 2>&1; echo "RC=$?" >> /tmp/suite.txt`
   ⚠ **The `+ 7` below is SUPERSEDED. The FINAL acceptance is `passed` ≥ baseline + 15, and the
   mutant set is M1–M13.** How it moved, so the number is auditable rather than asserted:
   `+ 7` as written → **+ 8** (operator ruling: pin the cap's literal value, M1 caught nothing)
   → **+ 12** (the cross-path amendment's four tests) → **+ 13** (codex P1: the import-outside-try
   slot leak) → **+ 14** (`/code-review`: `WEB_CONCURRENCY` in the process environment) →
   **+ 15** (`/code-review`: the unlink-failure lockout). Measured final:
   `4551 passed, 1 warning in 116.05s (0:01:56)`, `RC=0`, against the `4536` baseline — zero skips
   at both ends. (Codex round 4 P2: leaving this section at `+ 7` / M1–M4 meant a literal executor
   would never run the amendment's proof at all.)
   Acceptance is **`RC=0` AND `passed` ≥ step 1's PASSED baseline + 7** (the new tests), **AND
   `skipped` unchanged from step 1**. Compare passed-to-passed and skipped-to-skipped — never
   passed-against-collected. A rise in `skipped` is a finding to chase, not a pass: it means a
   test stopped running rather than started passing. Read the file for the numbers and the RC;
   never a pipe.
4. **Positive control (mutation).** State the expected catchers BEFORE running, and report
   per-test outcomes, never an aggregate. Clear `__pycache__` before each mutation AND each
   restore, and assert each mutation actually applied.
   - **M1** `MAX_CONCURRENT_ADMIN_GENERATIONS = 2` → `= 99`. Expected to fail tests 1 and 2;
     expected NOT to fail 5 (it replaces the semaphore), 6, or 7.
   - **M2** move the `acquire` above the URL validations. Expected to fail test **6** only —
     this is the sole proof that guard 6 is worth its lines.
   - **M3** delete the `finally:` release (leave the call). Expected to fail tests 3 and 4.
   - **M4** append ` --workers 4` to the `Dockerfile:48` uvicorn line; restore, then separately
     add a `command:` override on the `app` service in `docker-compose.yml`. Each is expected to
     fail test **7** and nothing else — this is the sole proof that the premise guard is not
     vacuous, and it must be run for BOTH inputs, since a Dockerfile-only mutation would leave the
     compose half of the guard unproven (the narrowness codex flagged as P2).
   A result differing from the expectation in EITHER direction is a finding to chase, not a pass.
   ⚠ M4 mutates tracked infrastructure files — restore them and confirm `git status` is clean
   before proceeding to step 5.
5. **Docs agreement — a comparison, not a judgement call.** Extract the refusal string the code
   actually emits and the string the doc claims, and diff them:
   ```sh
   grep -n "already" src/api/routes/reports_admin.py
   grep -n "already" docs/admin/operations.md
   ```
   **Pass condition**: the operator-visible sentence in `docs/admin/operations.md` is
   CHARACTER-IDENTICAL to the message the route builds (modulo the interpolated
   `MAX_CONCURRENT_ADMIN_GENERATIONS`, which the doc may write as the literal `2`). A paraphrase
   FAILS this step — prose about behavior is an unverified claim until resolved against the repo,
   and a near-miss quote is the form that survives review.
   Also confirm `docs/admin/operations.md` carries the **F3b deployment invariant** sentence; its
   absence fails this step, because F3b has no other enforcement anywhere in the repo.

## Reviews owed at EXECUTION (step 5) — all OPERATOR-TYPED

- Full suite green (touches `src/` and `tests/`).
- **Codex review: REQUIRED** — the chunk touches `src/`.
- `/code-review`, over every change since the chunk's base, committed or not; name the range and
  confirm the reviewer received it.
- `/security-review`: **REQUIRED — upgraded from "offered" by the amendment** (codex round 4 P2).
  It was a genuine judgement call while this chunk only added an in-memory semaphore. It is not
  one any more: the amendment's gate calls `reap_stale_generating_reports`, which UPDATEs rows,
  unlinks files, and commits unconditionally on every valid submission to an auth-gated serving
  route. That is squarely CLAUDE.md step 5's "auth, serving, PII, or deletes".
- `python3 src/safety/pii_scanner.py --staged`, reconciling scanned-count against staged-count.
  Note the standing rename gap: this spec moving to `done/` at handoff IS a rename and the scanner
  skips it — give it a manual pass with a positive control.

## Residuals this chunk creates or names

- **The CLI/cron paths stay uncapped by design, and the full-regenerate chunk owes its own
  concurrency discipline in its own spec.** Must land in `.project/specs/README.md` STANDING
  RESIDUALS **and** on the regenerate line in NOW — a residual parked only in a spec that moves to
  `done/` is a residual lost.
- **A future multi-worker uvicorn silently multiplies the cap** (`--workers N` → cap `2N`).
  Covered by the guard test in work item 4; recorded here so the next reader knows the test is
  load-bearing rather than incidental.
- **⚠ Runtime replication of the app container multiplies the cap and NOTHING detects it** (F3b).
  No test can reach it; its only enforcement is the deployment invariant written into
  `docs/admin/operations.md`. This is the cap's largest residual exposure and it is accepted
  deliberately — the alternative is a cross-process mechanism, which F4 shows is materially weaker
  at the door this chunk exists to guard. Anyone who scales the app owes this cap a re-think.
- **⚠ `WEB_CONCURRENCY` in the untracked `.env` silently multiplies the cap and NO TEST CAN SEE
  IT** (found at `/code-review`). uvicorn reads the variable directly; the `app` service loads
  `env_file: .env`, which is untracked and absent from CI. The widened guard covers the TRACKED
  routes and the dev container's own environment only. This now ranks alongside F3b as the cap's
  largest exposure, and unlike F3b it needs no infrastructure change — one line in a file nobody
  reviews.
- **The stale-generation reaper now runs on EVERY admin submission, refused ones included**
  (operator-ruled residual, 2026-08-16). Previously it fired only at generation start and app
  startup. Consequence if a generation ever legitimately exceeds `STALE_GENERATING_SECONDS` =
  3600: it is marked `failed` and its already-written HTML unlinked WHILE STILL ALIVE, then
  completes and flips itself to `ready` with a `report_path` pointing at a deleted file. Judged
  unlikely (the threshold is ~70x a real generation) and deliberately not chased. Anyone who
  raises generation times materially — many more games, a slower feed — owes this a re-look.
- **A dead `generating` row younger than one hour still has no operator escape.** Restarting the
  container resets the in-process semaphore for free and the startup reaper clears rows past the
  threshold, but nothing clears a younger one on demand. An explicit force-clear command was
  offered and **declined by the operator** (2026-08-16); an unconditional startup wipe was
  recommended against, because CLI generations survive an app-container restart and would be
  killed mid-run. Reopen only with a way to tell a live CLI run from a dead row — which is the same
  missing provenance that made this page one-at-a-time.
- The admin form still has no submit-button disabling and the page still meta-refreshes every 15s
  while generating. Neither is a defect this chunk owns.

## AMENDMENT (operator ruling 2026-08-16, during execution) — cross-path in-flight refusal

**The defect this closes, measured tonight, not re-derived.** At 21:54–21:59 a UI-initiated
generation raced the serial CLI restore run. It hard-deleted stat rows on games the CLI was
actively writing, forced the CLI to skip orphan reclamation for one team, and produced a report
now served as `ready` while carrying 155 uncorrected reconciliation discrepancies.

**VERIFIED at amendment time (2026-08-16), first-hand:**

- **A1 — the deferral fired.** `ephemeral/2026-08-16-report-restore/regenerate-20260816-204714.log`
  line **7974**: `INFO src.reports.lifecycle: Orphan reclamation deferred: 1 live 'generating'
  report(s) remain after reap.` It sits between `[22/71] START tNvpyrrSFSYb` and that team's crawl
  — i.e. mid-CLI-run, exactly as claimed.
- **A2 — the damaged run exists.** `report_generation_runs` id=160: `overall_status = completed`,
  `discrepancies_found = 155`, `discrepancies_corrected = 0`, `plays_status = completed`,
  `load_status = completed`. A report that reads as clean and is not.
- **A3 — the admin-path damage itself, VERIFIED from the correct source.** This cite initially
  failed to reproduce because it was looked for in the CLI regenerate log, which carries no clock
  timestamps and only ever showed the race's shadow (A1). The primary is the APP CONTAINER's log:
  the admin generation ran inside the uvicorn process, so its pipeline logging went to container
  stdout. `docker compose logs app --since 2026-08-16T21:54:00 --until 2026-08-16T22:00:00`
  carries, at a single `21:56:23` timestamp, **32 `hard-deleted` player-line retire WARNINGs and
  12 `retire REFUSED` WARNINGs** across many games — plus the `POST /admin/reports/generate
  303 See Other` and its `?msg=Report+generation+started+for+...` redirect that started the run.
  Many of the hard-deletes carry the loader's own re-issued-player_id warning, i.e. rows deleted
  that were not departures. Identifiers deliberately omitted here per this file's PII header.
  **This, not A1, is the direct record of the damage the amendment exists to prevent.**
- **A4 — per-path caps do not compose.** With the cap as landed, admin ≤ 2 AND CLI uncapped permits
  **three** concurrent destructive generates. The original spec's ruling 3 ("the CLI path is
  uncapped BY DESIGN") stands as a statement about what this chunk *caps*; it was never a claim
  that a CLI run is safe to race. This amendment does not cap the CLI — it makes the ADMIN door
  refuse while the CLI is working.
- **A5 — the mechanism ALREADY EXISTS canonically; do not re-inline it.**
  `reclaim_orphan_reference_data` (`src/reports/lifecycle.py:1460-1471`) already performs exactly
  reap-then-gate: `reap_stale_generating_reports(conn)` then
  `SELECT COUNT(*) FROM reports WHERE status = 'generating'`, deferring when non-zero. Per
  `.claude/rules/canonical-seams.md` the route MUST call `reap_stale_generating_reports`, not grow
  a second copy of the reap. Its signature is `(conn: sqlite3.Connection | None = None)`.
- **A5a — ⚠ CORRECTION to A5, found at implementation: the route MUST PASS ITS OWN CONNECTION, not
  `None`.** An earlier draft ruled `None`, reasoning that a self-owned connection cannot violate
  `_require_clean_connection`. That reasoning is sound and the conclusion is still wrong, for a
  reason `_conn_scope`'s own docstring (`src/reports/lifecycle.py:44-60`) exists to warn about:
  `_conn_scope(None)` resolves **`lifecycle.get_connection`** — a module global the admin test
  fixture does NOT patch (it patches `reports_admin.get_connection`, `src.api.db.get_connection`
  and `src.reports.generator.get_connection`). Passing `None` would therefore point every test of
  this gate at the REAL `data/app.db`. That is precisely the detachment E-256-04 introduced the
  injected-connection seam to prevent, and `generate_report` swallowing sweep exceptions is why it
  would not have announced itself. The route opens a connection with its OWN module-global
  `get_connection` (already imported) and PASSES IT IN, so the caller's sandbox travels with the
  connection. A freshly-opened connection has no open transaction, so the
  `_require_clean_connection` precondition is satisfied regardless.
- **A6 — F4 is NOT contradicted by this amendment, and the distinction is the whole design.** F4
  says a DB count is a materially weaker *cap* — true, and unchanged: the `generating` row is not
  written until seconds after the click, so several fast admin clicks all pass a DB count. That is
  why the semaphore stays. A DB count is nonetheless the ONLY thing that can see *another process*.
  The two are layered because they fail in different directions, not redundant.

### ⚠ The amendment CHANGES ruling 2 (N=2) in practice — operator ruled 2026-08-16

Codex round 4 P1, verified first-hand: **there is no source discriminator anywhere.** `reports`
carries only `(id, slug, team_id, title, status, generated_at, expires_at, report_path,
error_message)` — no column naming who started the run — and `report_generation_runs` has no
route-vs-CLI column either. So a `COUNT(*) WHERE status='generating' > 0` gate cannot tell a CLI
run from the admin page's OWN first generation, and will refuse the operator's second click once
that first run writes its row (seconds after the click).

**Operator ruling: ACCEPT — the admin page becomes ONE-AT-A-TIME.** N=2 was ruled before the
cross-path hazard was known, and refusing while anything is generating is what tonight's incident
warrants. The alternatives were declined: a provenance column means a migration and new plumbing
on an otherwise-finished chunk, and subtracting the page's own in-flight runs is a racy inference
rather than a recorded fact.

**The semaphore still earns its place, and this is the reason to keep it** — it is not made
vestigial. F4 is exactly the argument: the `generating` row is not written until the background
task has parsed the URL and made a public fetch, so in the seconds between click and row the DB
gate is BLIND and several fast clicks all pass it. The semaphore is the only thing covering that
window. Two layers, two different blind spots:

| | covers the click-to-row window | sees other processes |
|---|---|---|
| semaphore (in-process, N=2) | YES | no |
| DB gate (reap-then-count) | no | YES |

**Consequence for the docs**: `docs/admin/operations.md` and `.claude/rules/admin-ui.md` must now
say the page generates ONE report at a time, not two. The `2 report generations are already
running.` refusal string stays reachable (the click-to-row window) but is no longer the message an
operator normally sees — so the doc must carry BOTH refusal messages, and Verification step 5's
character-identical check now applies to both.

### Ruled design

1. **Placement: after `_require_admin` and all three URL validations, and BEFORE
   `_generation_slots.acquire()`.** Checking before acquiring means a cross-path refusal
   **cannot leak a slot by construction** — there is no slot held at the moment of refusal. The
   alternative (acquire, check, release-on-refusal) is also correct but relies on a release a
   reviewer must verify; this ordering removes the failure mode instead of guarding it. Pinned by
   a test either way, per the ruling.
2. **Reap FIRST, then count** (A5's order). A crashed generation's row must not block the admin
   page for `STALE_GENERATING_SECONDS` = 3600. Reversing these two is a real regression with no
   visible symptom for an hour, so it gets its own test and its own mutant.
3. **Refuse if the count is > 0**, in the house 303-flash shape (F5), with a message that names
   the cross-path cause — the operator must be able to tell "my own second click" from "the CLI is
   busy", because the remedies differ.
4. **Async discipline**: the check is sync SQLite on an `async def` route, so it goes through
   `await run_in_threadpool(...)`, matching this module's existing convention (18 call sites,
   e.g. `reports_admin.py:716`). Doing it inline would block the event loop.
5. **⚠ HONEST FRAMING — this is exposure-MINIMIZATION, not elimination, and must be written that
   way in `docs/admin/operations.md`.** A CLI run that starts in the seconds after the check still
   races, and nothing detects that. It is the delta-0 precedent in `.claude/rules/data-model.md`,
   not a fix. Do not write it as "prevents".
6. **⚠ THE GATE IS NOT A READ — corrected, codex round 4 P2.** An earlier draft of this section
   called it one. `reap_stale_generating_reports` **UPDATEs `reports`, unlinks orphan HTML files,
   and `commit()`s UNCONDITIONALLY — even when it reaps zero rows**
   (`src/reports/lifecycle.py:233`). So this amendment puts a committing, file-deleting side effect
   on an auth-gated serving route on every valid submission. Two consequences, both binding:
   **`/security-review` is REQUIRED, no longer merely offered** (CLAUDE.md step 5 names auth,
   serving, and deletes — this route is now all three); and the operator-facing doc must not
   describe the gate as a passive check.

### The work (amendment)

6. **Add the cross-path gate** to `src/api/routes/reports_admin.py`: a module-level sync helper
   that calls `reap_stale_generating_reports()` then counts `reports.status='generating'`, invoked
   via `run_in_threadpool` at the placement in (1).
7. **Docs**: `docs/admin/operations.md` gains the cross-path refusal, its message, and the
   minimization framing; `.claude/rules/admin-ui.md`'s cap bullet gains the second gate.

### Tests (amendment) — split by kind, NOT all RED-first

⚠ **Corrected by codex round 4 (P1).** The first draft called all four RED-first and simultaneously
expected M5 (delete the gate) to leave two of them green — a self-contradiction. If deleting the
gate leaves a test green, that test does not prove the gate exists. The same split the original
scope needed applies here.

**(A) RED-first — each asserts a REFUSAL, so none can pass before the gate exists.**

8. `TestAdminGenerate_WhenAGenerationIsInFlightAnywhere::test_redirects_with_an_error_flash`
9. `TestAdminGenerate_WhenAGenerationIsInFlightAnywhere::test_does_not_enqueue_a_generation`
10. `TestAdminGenerate_WhenAGenerationIsInFlightAnywhere::test_no_slot_is_consumed` — the ordering
    pin for (1). Asserts BOTH that the submission was refused AND that every semaphore slot is
    still free. Asserting only the slot state would pass vacuously against a route with no gate —
    the same vacuity that made tests 3 and 4 worthless in the original scope until they were made
    to probe DURING the generation.

**(B) Green today by construction — its worth is proven by mutation, not by RED.**

11. `TestAdminGenerate_WhenTheOnlyGeneratingRowIsStale::test_the_submission_proceeds` — the
    ordering pin for (2). A `generating` row older than `STALE_GENERATING_SECONDS` must be reaped
    and must NOT block the submission. Green today because today nothing blocks at all; its only
    proof of worth is **M7**.

Suite acceptance moves from baseline+8 to **baseline+12** (`4536 + 12 = 4548`).

### Mutants (amendment) — expected catchers stated before running

- **M5** delete the gate entirely. Expect **8, 9 and 10** to fail; 11 passes (nothing to clear).
- **M6** move the gate BELOW the acquire, without releasing on refusal. Expect **10 only**.
- **M7** swap reap and count (count first, then reap). Expect **11 only** — the sole proof that
  guard 11 is worth its lines.
- **M8** change the refusal threshold from `> 0` to `> 1`. Expect **8, 9 and 10** to fail.

## Progress log

- **2026-08-10** — Stubbed from the log audit. No writes, no merges, no regenerations run.
- **2026-08-16** — Spec pass. Repair half confirmed dead (2026-08-12 regeneration ruling); F1–F5
  verified against the repo; operator ruled scope = admin web page only, N = 2, CLI uncapped by
  design with the discipline owed by the regenerate chunk.
- **2026-08-16** — `codex-spec-review` round 1: **3 findings (1×P1, 1×P2, 1×P3), all ACCEPTED**,
  none disputed.
  * **P1** — the RED plan was unsatisfiable: two of the seven tests pass on today's code. Folded
    by splitting the list into group (A) RED-first (5 tests) and group (B) guards-green-today
    (2 tests), and rewriting Verification step 2 to run them separately with opposite expectations.
  * **P2** — the single-process premise was stated loosely and guarded too narrowly. Folded as
    F3 (precise: `command:` DOES appear at `docker-compose.yml:32`/`:55`, just not on `app`),
    a widened guard covering the `app` service in `docker-compose.yml`, and a new mutant **M4**
    so the guard is shown failing on BOTH inputs. **One correction ON TOP of the finding**: codex
    suggested guarding `docker-compose.override.yml`, but that file is gitignored and untracked
    (`.gitignore:35`) and is absent in CI — recorded as F3a, with the guard reading it only if
    present and never failing on its absence.
  * **P3** — the Source line pointed at README NOW; this spec's own entry is in NEXT. Corrected.
- **2026-08-16** — `codex-spec-review` round 2 (scoped re-round on the round-1 folds, prompted by
  a peer session applying the Re-Review Protocol: the P1 fold had restructured a whole verification
  section, and fold-introduced defects are a known class here). **3 findings (1×P1, 2×P2), all
  ACCEPTED**, none disputed. No finding was a regression introduced by a round-1 fold; all three
  pre-existed it.
  * **P1 (Status)** — the header claimed `READY … committed` while the rewrite was only STAGED, so
    the claim was false at read time and would have blocked execution (step 3 starts from a
    COMMITTED spec). Folded: the header now says the Status RIDES the commit that lands it, per
    lifecycle step 7. The finding's second half — README:81 still calling this spec a `STUB` — is
    fixed in the SAME commit by updating that NEXT entry to `READY`, which the line of march's own
    rule requires ("the march's NEXT should name every READY spec"). That widened this commit from
    one file to two; called out explicitly rather than folded in silently.
  * **P2 (Verification step 3 arithmetic)** — "passed ≥ collected baseline + new" is unsound
    because the suite has real skip/skipif paths, so a green run could fail the spec's own check.
    Folded: step 1 now baselines from a full RUN, step 3 compares passed-to-passed AND
    skipped-to-skipped, and a RISE in skips is named as a finding to chase. **Measured while
    folding**: this container runs `4536 passed, 1 warning`, `RC=0` — **zero skips**, so the two
    numbers coincide HERE. The finding is a latent unsoundness, not a live discrepancy, and the
    spec now says so rather than implying the check was catching something today.
  * **P2 (F3 overclaim)** — "one process, so an in-process cap is a real cap" claimed more than
    the repo proves: tracked launch files omitting `--workers` does not rule out runtime
    replication, which would multiply the cap and trip no guard. Folded: F3 narrowed to the
    CHECKED-IN TOPOLOGY; new **F3b** states the deployment invariant as an invariant (the half no
    test can reach) and routes it into `docs/admin/operations.md`; work item 4 renamed to what it
    checks; test 7 renamed from `test_the_served_process_count_is_one` — a false claim in the
    test's own identifier — to `test_no_tracked_launch_file_starts_extra_workers`; and the
    exposure is recorded as this chunk's largest accepted residual.
- **2026-08-16** — `codex-spec-review` round 3 (fold-verification on the round-2 folds, since the
  F3b fold reached beyond the sentences the finding named). **3 findings (1×P1, 1×P2, 1×P3): 2
  ACCEPTED and folded, 1 DISPUTED with reason.** Rounds STOP here — see the note below.
  * **P2 (ACCEPTED)** — Verification step 2 gave a command for group (A) and told the executor to
    run group (B) "separately" without a selector. Folded: group (B) now has its own command, its
    own `RC=0` / **2 passed** expectation, and a warning that a selector matching nothing is not
    the same observation as a pass.
  * **P3 (ACCEPTED)** — Verification step 5 was judgemental ("re-read the paragraph against the
    code"). Folded into a concrete two-`grep` comparison with a CHARACTER-IDENTICAL pass
    condition, plus an explicit check that the F3b invariant sentence is present.
  * **P1 (DISPUTED — a lifecycle artifact, not a spec defect).** The finding is that Status
    `READY` is false because the spec is not yet committed (`git log --follow` ends at the stub
    commit `d1f8fe9`; `git status --short` shows `MM`/`M` — both verified firsthand, the facts are
    correct). But CLAUDE.md step 7 REQUIRES flipping Status before staging so it rides the commit,
    so the Status is necessarily "false" in the window between the flip and the commit. **This
    finding will fire on every spec commit in this repo, forever, and no edit to the spec can
    satisfy it** — any Status I write is uncommitted at review time. It is already answered in the
    header ("this Status RIDES the commit that lands it"). Round 2 raised the same P1 and its
    foldable half (the README still calling this spec a `STUB`) was fixed then; what remains is
    the unfoldable half. Recorded, not folded.

- **2026-08-16 — EXECUTION session.** Precondition gate PASSED (Dockerfile:48 carries no
  `--workers`; the `app` service in `docker-compose.yml` has no `command:` and no
  `deploy.replicas`). F1–F5 all re-verified first-hand against the repo; anyio 4.14.1 default
  limiter measured at **40** tokens, starlette 1.3.1. Baseline `4536 passed, 1 warning in 103.37s
  (0:01:43)` with `RC=0`, zero skips.
  * **Group (B) diverged from the spec at step 2** — `1 failed, 1 passed`, RC=1, not the expected
    `2 passed`. Cause was the TEST, exactly as the spec predicts for that case: test 6 had been
    written through the slot-swapping helper, which needs a module global that does not exist at
    the pre-change commit. Rewritten to drive the real route with no swap; then `2 passed`, RC=0.
  * **RED was claimed once before it was earned, and the claim is corrected here.** The first
    group-(A) run failed all 5 on an identical `AttributeError` (missing module global) — the
    spec's own "an import error is not a RED" clause covers that shape. Recovered by staging the
    implementation: constant + semaphore + wrapper FIRST, re-run to get a behavioral RED (5 failed
    on flash/enqueue/slot assertions), and only then the route's acquire. The two-stage recovery
    was right; the first claim was not earned when stated.
  * **Tests 3 and 4 were vacuous as first written** — a fresh `BoundedSemaphore(1)` is free whether
    or not the route ever acquired it, so "free afterwards" passed against a route with no
    admission check. Both now probe DURING the generation (slot must be UNavailable) as well as
    after.
  * **M1 was caught by NOTHING**, against an expectation of tests 1 and 2. Root cause is structural,
    not a slip: the spec's own mandated mechanics require each test to install its own
    `BoundedSemaphore(n)`, which decouples every behavior test from the constant — and the refusal
    message interpolates the constant, so even the operator-visible text changed silently.
    Mutating `2` → `99` left the whole suite green. **Operator ruled: add a literal pin.** Test 8
    `TestTheCapValue::test_is_the_operator_ruled_two` added; M1 re-run and caught by test 8 ONLY.
    Acceptance moved from baseline+7 to baseline+8 by that ruling.
  * Positive control complete, per-test outcomes, expectations stated before each run: control
    `8 passed`; **M1** → test 8 only; **M2** (acquire above validations) → test 6 only; **M3**
    (delete the `finally:` release) → tests 3 and 4; **M4a** (Dockerfile `--workers 4`) → test 7
    only; **M4b** (`command:` on the `app` service) → test 7 only. Every result matched its stated
    expectation. Infrastructure files restored and `git status` confirmed clean of them.
  * Verification step 5 PASSED: `docs/admin/operations.md:569` is character-identical to the
    message the route builds, modulo the literal `2`; the F3b invariant sentence is present at
    `:575`.
  * Full suite after the original scope: `4544 passed, 1 warning in 114.58s (0:01:54)`, `RC=0` —
    baseline + 8, skips unchanged at zero.
- **2026-08-16 — AMENDMENT ruled by the operator mid-execution** (relayed via a peer session and
  confirmed directly by the operator): the admin route must ALSO refuse while any generation is
  in flight database-wide. Evidence audited first-hand before designing — A1 and A2 confirmed, A3
  recorded as NOT reproducible. See the AMENDMENT section above. The amendment is scoped for its
  own codex-spec-review round.
- **2026-08-16 — `codex-spec-review` round 4 (SCOPED to the amendment).** **4 findings (2×P1,
  2×P2), ALL ACCEPTED and folded**, none disputed. Codex explicitly cleared the placement ruling,
  the reap-then-count order, and the `_require_clean_connection` interaction.
  * **P1 (scope)** — no source discriminator exists, so the gate cannot separate a CLI run from
    the page's own in-flight generation and would silently reduce the shipped N=2 to 1. Verified
    first-hand (`reports` has 9 columns, none of them provenance; `report_generation_runs` has no
    route-vs-CLI column). **Operator ruled: ACCEPT the reduction — the page is one-at-a-time**;
    alternatives (a provenance migration; subtracting the page's own in-flight count) declined.
    Folded as its own section, including why the semaphore is still NOT vestigial.
  * **P1 (verification)** — the amendment claimed all four tests RED-first while expecting M5 to
    leave two green, a self-contradiction. Folded into an (A)/(B) split: 8/9/10 RED-first (each
    asserts a refusal), 11 green-today with M7 as its sole proof of worth.
  * **P2** — Verification steps 3 and 4 still said `+ 7` and M1–M4, so a literal executor would
    never run the amendment's proof. Folded: superseded-notice pointing at baseline+12 and M1–M8.
  * **P2** — "the check is a read" was false: the reaper UPDATEs, unlinks files, and commits
    unconditionally. Folded, and **`/security-review` upgraded from "offered" to REQUIRED**.
- **2026-08-16 — AMENDMENT executed.** One correction found by reading the seam rather than the
  finding list: **A5a** — the spec's own `conn=None` ruling would have pointed every test of this
  gate at the REAL `data/app.db`, because `_conn_scope(None)` resolves the unpatched
  `lifecycle.get_connection`. Route now passes its own connection.
  * RED (group A): 8, 9, 10 failed on flash/enqueue/slot assertions; 11 passed green-today, exactly
    as the corrected split predicts.
  * Full suite `4548 passed, 1 warning in 106.40s (0:01:46)`, `RC=0` — baseline + 12, zero skips.
  * Mutants, expectations stated before each run: **M5** (delete gate) → 8, 9, 10 ✓; **M7**
    (count before reap) → 11 only ✓; **M8** (`> 0` → `> 1`) → 8, 9, 10 ✓; **M6** (gate below
    acquire) → **DIVERGED**, catching 10 *and* 11 against a prediction of 10 only.
    **Chased, not accepted**: differential showed test 11 ALONE under M6 passes (`1 passed`), so
    the extra failure was a slot-exhaustion cascade — tests 8 and 9 drove the REAL module
    semaphore and, under a leak-mutant, drained it for test 11. Fixed the hygiene rather than the
    expectation: 8 and 9 now run inside `_slots(2)`. **M6 re-run → test 10 ONLY**, matching the
    prediction with a clean signal. All eight mutants now match their stated expectations.
  * Verification step 5 re-run against BOTH refusal strings: each is character-identical between
    the message the route builds and the doc (`operations.md:569` cross-path, `:573` cap); the F3b
    invariant sentence is still present.
  * Documentation assessment (`.claude/rules/documentation.md`): triggers 1 and 5 fire.
    `docs/admin/operations.md` and `.claude/rules/admin-ui.md` updated in this chunk — the page is
    now documented as one-at-a-time, carrying both refusal strings, both measured incidents, and
    the exposure-minimization caveat.
- **2026-08-16 — `codex-review.sh uncommitted` (REQUIRED, chunk touches `src/`).** Range = this
  chunk's five working files; the peer session's `cbd8975` stub commit is excluded by construction
  since it is committed and these changes are not. **3 findings (1×P1, 1×P2, 1×P5), ALL ACCEPTED
  and fixed before any commit.**
  * **P1 — a real permanent slot leak.** `_generate_report_releasing_slot` had the call-time import
    ABOVE the `try`, so an `ImportError` (circular-import regression, missing transitive dep) would
    skip the `finally` and leak the slot forever; two such failures wedge the page until restart.
    The spec required the import be call-time; it never said "outside the try", and I put it there.
    Fixed by moving the import INSIDE the `try`, which keeps call-time resolution (the patched
    tests still pass). New regression test
    `TestAdminGenerate_WhenTheGenerationImportFails::test_the_slot_is_still_returned`, proven to
    discriminate by **M9** (revert the fix) → that test **ONLY**, 54 others green.
  * **P2 — a test that could delete real files.** Test 11 drives the real reaper, which unlinks
    `_REPORTS_DIR/"{slug}.html"`; unpatched it could delete `data/reports/stale-gen.html` from a
    live checkout. Fixed by patching `src.reports.lifecycle._REPORTS_DIR` to a `tmp_path`, matching
    what the existing reaper tests already do.
  * **P5 — the doc still implied a passive check**, which the amendment had explicitly ruled
    against. `docs/admin/operations.md` now states plainly that a REFUSED submission still reaps,
    unlinks, and commits.
  * Full suite after the fixes: `4549 passed, 1 warning in 111.41s (0:01:51)`, `RC=0` —
    baseline + 13 (the twelve planned, plus the P1 regression pin), zero skips.
- **2026-08-16 — `/code-review` (operator-typed).** Range = this chunk's working files since
  `a607ad0`, excluding the peer session's committed `cbd8975` stubs. **6 findings (3 medium,
  3 low). ALL 6 verified against the repo first-hand, ALL accepted, ALL resolved pre-commit.**
  * **`WEB_CONCURRENCY` defeats the whole premise, and nothing in the chunk saw it.** Verified:
    `uvicorn/config.py:351-352` reads it straight from the environment when `workers is None`, and
    the `app` service takes `env_file: .env`, which is UNTRACKED. So one line in `.env` yields
    4 workers and an effective cap of 8 while `TestTheCheckedInTopology` stays GREEN — precisely
    the false assurance that class exists to prevent, and a hole F3/F3a never named. Guard widened
    to cover `entrypoint` (overrides CMD as effectively as `command`), an `environment:` entry, and
    the variable's absence from the live process env; the docs invariant now names it as the
    easiest accidental break. Proven by three new mutants: **M10** (`entrypoint` on `app`),
    **M11** (`WEB_CONCURRENCY` in `environment:`), **M12** (`WEB_CONCURRENCY` in the process env)
    — each caught by exactly its intended test and nothing else.
  * **A permanent product lockout, escalated from a stray file by THIS chunk. OPERATOR RULED: fix
    it.** In `reap_stale_generating_reports` the orphan `unlink()` ran BEFORE the
    `UPDATE ... SET status='failed'`, inside one per-row `try` that logs and `continue`s. A failing
    unlink (read-only mount, permissions, EBUSY) therefore skipped the UPDATE and left the row
    `generating` FOREVER. Harmless-ish before; now that the generate route refuses on ANY
    `generating` row it wedges the page permanently — and `admin/reports.html:170` gates the delete
    affordance on `status != 'generating'`, so there is NO UI escape. Fixed by flipping the row
    FIRST and unlinking after, which downgrades the failure to the stray-file condition this
    function already tolerates. Pinned by
    `TestReapStaleGenerating::test_the_row_is_freed_even_when_the_orphan_unlink_fails`, proven by
    **M13** (restore the old order) → that test ONLY, 279 others green. Touches
    `src/reports/lifecycle.py`, outside this spec's Files list — taken deliberately on the
    operator's ruling because this chunk is what makes the defect product-fatal. It is NOT the
    defect owned by the peer session's `2026-08-16-orphan-cleanup-fk-rollback.md` stub, which is
    about FK rollback in orphan cleanup; that stub is untouched.
  * **The reaper's own call-site enumeration was made wrong by this chunk.** Its docstring says
    "call sites are exactly three, enumerated from the code" and explicitly that the list excludes
    the admin paths. This chunk adds a FOURTH — borrowed-connection (so `_require_clean_connection`
    is LIVE) and on a SERVING request path. Updated to four, naming the fail-closed absorption and
    warning not to read the admin generate and admin delete paths as one. Classic
    `.claude/rules/tool-discipline.md` inbound-sweep miss: I added a caller and left prose
    asserting the caller set. ⚠ Note the count cross-check: grep found **three** such
    enumerations in that file (`reap_stale_generating_reports`, `cleanup_expired_reports`,
    `reclaim_orphan_reference_data`); only the first gains a caller here, and the other two were
    read and left alone rather than edited by pattern.
  * **A 500 where a 303 was designed.** The reaper's `SELECT` and final `commit()` sit OUTSIDE its
    per-row isolation, so `database is locked` — the very contention this gate exists for —
    escaped `_a_generation_is_in_flight` and would have returned a 500. Now caught and FAILS
    CLOSED (refuse, don't race an unknown writer), per `.claude/rules/python-style.md`. The gate
    also now logs `ReaperResult.errors`, which it had been discarding.
  * **My own comment justified the right order with wrong reasoning.** It claimed count-first would
    wedge the page "for the full STALE_GENERATING_SECONDS = 3600" — wrong in both directions, since
    the reaper only ever selects rows ALREADY past the threshold. Rewritten to state what the order
    actually buys (same-request recovery). Prose I authored, so it was my unverified claim.
  * **Reaper frequency (low).** It now fires on every submission, refused ones included, where it
    previously fired only at generation start and app startup. **OPERATOR RULED: document as a
    residual, do not chase** — the 1-hour threshold is ~70x a real generation.
- **2026-08-16 — restart-as-escape-hatch, asked and ruled.** Operator asked whether the cap should
  reset on container start. Answered from the code: the SEMAPHORE half already does, for free (it
  is in-process state, rebuilt at import), and `src/api/main.py`'s lifespan startup reaper already
  clears `generating` rows past the threshold. Making that startup reap UNCONDITIONAL was
  recommended AGAINST and **ruled out**: CLI generations run in a SEPARATE process that SURVIVES an
  app-container restart, so an unconditional wipe would mark a live `bb report morning-run` slot
  failed and unlink its HTML mid-run — manufacturing the "ready row, missing file" state. **Ruled:
  no further change**; the lockout fix above closed the real wedge.
- **2026-08-16 — UNREVIEWED-EDITS NOTE, and why the rounds stop at 3.** The round-3 fold-ins above
  (the step-2 group-(B) command, the step-5 grep comparison) and these log lines themselves are
  **not covered by a further codex round**. That is deliberate. Logging round N always creates new
  text, so "re-round every fold" does not terminate; the protocol's own escape is an explicit
  unreviewed-edits note, and this is it. The two unreviewed folds are both *narrowings of
  verification steps into concrete commands* — they add no claim about the repo, name no new
  mechanism, and change nothing the executor implements. The round-3 tripwire also applies: the
  only P1 was a recurrence, not a fresh blocker, and it is unfoldable by construction. **A fourth
  round would re-report the same P1 against the same uncommittable artifact.**
