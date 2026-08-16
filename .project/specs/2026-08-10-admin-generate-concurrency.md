<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# Cap concurrent report generation on the admin generate path

**Date**: 2026-08-10 (stubbed) · spec pass 2026-08-16 · **Status**: `READY` — written and
codex-spec-reviewed over **3 rounds, 9 findings: 8 accepted and folded, 1 disputed with reason**
(see the progress log). **This Status RIDES the commit that lands it** (lifecycle step 7 flips Status before staging), so it is true from that commit forward,
not before it. Waiting only for a fresh execution session — do NOT implement from this spec in the
session that wrote it.
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
- `/security-review`: **offered, operator decides.** This is an admission control on an
  auth-gated serving route. It is not obviously in the auth/PII/delete set, and it is not obviously
  out.
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
- The admin form still has no submit-button disabling and the page still meta-refreshes every 15s
  while generating. Neither is a defect this chunk owns.

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

- **2026-08-16 — UNREVIEWED-EDITS NOTE, and why the rounds stop at 3.** The round-3 fold-ins above
  (the step-2 group-(B) command, the step-5 grep comparison) and these log lines themselves are
  **not covered by a further codex round**. That is deliberate. Logging round N always creates new
  text, so "re-round every fold" does not terminate; the protocol's own escape is an explicit
  unreviewed-edits note, and this is it. The two unreviewed folds are both *narrowings of
  verification steps into concrete commands* — they add no claim about the repo, name no new
  mechanism, and change nothing the executor implements. The round-3 tripwire also applies: the
  only P1 was a recurrence, not a fresh blocker, and it is unfoldable by construction. **A fourth
  round would re-report the same P1 against the same uncommittable artifact.**
