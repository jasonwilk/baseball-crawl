# E-277-02: Refuse a dirty borrowed connection at all three reclamation entry points

## Epic
[E-277: Reclamation Follow-Up Repairs](epic.md)

## Status
`DONE`

## Description
After this story is complete, all three public entry points that can reach the reclamation on a borrowed connection — `reclaim_orphan_reference_data`, `reap_stale_generating_reports`, and `cleanup_expired_reports` — refuse a connection that already has an open transaction, raising before any commit occurs. Today they silently commit the caller's uncommitted work and then delete it as orphan data, while the caller's subsequent rollback succeeds and recovers nothing. The pass's exception handler also stops replacing the real failure cause when SQLite has already auto-rolled back.

## Context
`reap_stale_generating_reports` commits unconditionally on a borrowed connection — the commit is the last statement in its connection scope, not gated on whether any rows were reaped. `reclaim_orphan_reference_data` calls it as step 1.

Data-engineer reproduced the consequence: a caller's uncommitted `INSERT INTO teams` becomes visible, is classified as an orphan by the same call, and is deleted; the caller's rollback then succeeds silently and recovers nothing. **Unrecoverable data loss with no error raised anywhere** — which is why it is in scope despite no live caller passing a dirty connection today.

Read epic Technical Notes TN-9 first, in its corrected form. Two things it establishes: `BEGIN IMMEDIATE` is NOT a second trigger (software-engineer refuted the handoff's claim by execution — it raises rather than implicit-committing); and the reap's unconditional commit is **a** trigger but **not the only one**. An earlier draft of TN-9 and of this paragraph said "SOLE trigger", which was true of the two passes then in scope and false one layer out: `cleanup_expired_reports` carries its own unconditional commit on the borrowed connection and reproduces the full harm with the reap neutralized entirely. That is why this story guards three entry points rather than two.

## Acceptance Criteria
- [x] **AC-1**: Given a connection with an open transaction holding uncommitted DML, when `reclaim_orphan_reference_data` is called with it, then it raises, and the caller's uncommitted work is neither committed nor deleted — a subsequent rollback still discards the DML as the caller intended.
- [x] **AC-2**: Given the same dirty connection, when `reap_stale_generating_reports` is called with it directly, then it raises before any commit occurs — **observed the way AC-1 observes it: the caller's subsequent rollback still discards the DML.** AC-1 states how "not committed" is seen; this AC previously stated only that it raises, leaving nothing to assert on.
- [x] **AC-2.1**: Given the same dirty connection, when `cleanup_expired_reports` is called with it, then it raises before ANY commit occurs and before the reap is invoked, and the caller's uncommitted work is neither committed nor deleted. The guard is placed at the function's entry and **deliberately NOT inside the `try` that swallows reaper failures** — a guard inside it is caught and the path proceeds. See Technical Approach: this is a third borrowed-connection surface, and it is reachable independently of the reap.
- [x] **AC-3**: The guard in `reclaim_orphan_reference_data` fires BEFORE the reap call. Per epic Technical Notes TN-9: below it, the reap has already committed and the guard can never observe the dirty state it exists to catch.
- [x] **AC-4**: The guard survives `python -O`, pinned by a COMMITTED test rather than a one-time demonstration — the test runs the AC-1 scenario in a `python -O` subprocess and asserts it still raises. Additionally, the test asserts the raised exception is NOT an `AssertionError`, which runs under both modes and fails immediately if a later change swaps the raise for a bare `assert`. A manual demonstration leaves no regression signal, which is verbatim the gap this AC's own rationale argues against.
- [x] **AC-5**: Given a clean connection, when any of the three entry points is called, then behavior is unchanged and **every test file importing `src.reports.lifecycle` passes** — `test_admin_reports.py`, `test_cleanup_eligibility.py`, `test_cli_report.py`, `test_orphan_reclamation.py`, `test_reclaim_orphan_script.py`, `test_report_generator.py`. **Enumerated because the earlier phrasing ("all existing orphan-reclamation tests") reads as one file, and the TWO that exercise the exact carve-outs this AC protects are the two it omitted** — `test_cli_report.py` (the `conn=None` CLI path) and `test_reclaim_orphan_script.py` (the one-shot's owned connection). Separately, given `conn=None` — a path that exists on `reap_stale_generating_reports` and on `cleanup_expired_reports`, but NOT on `reclaim_orphan_reference_data`, whose signature has no default and no `None` branch — the guard **SKIPS** rather than firing, and a test pins that it does. **An unconditional guard CRASHES `bb report cleanup` outright**: the CLI passes no connection and, unlike `generate_report`, does not wrap the call in a try/except, so it has no degradation path. This is the sharper half of the requirement — the `generate_report` caller would merely log at ERROR and continue, which is why an implementer testing only that path would not notice.
  - **⚠ A test asserting "the guard never evaluates on the `None` path" would pin something UNTRUE, and this AC's own wording invites writing one.** Measured by code-reviewer: on the `conn=None` CLI path, `reclaim_orphan_reference_data` still receives a **real** connection — it never sees `None`, because it is invoked inside the rebound `with _conn_scope(conn) as conn:` block. **So reclaim's guard is LIVE on every path, including the CLI one.** This AC's signature claim (reclaim has no `None` branch) is correct; the runtime consequence is stronger than the AC states. **Pin the SKIP only where a `None` actually reaches a guard — the reap and cleanup entry points — and do not generalize it to reclaim.**
- [x] **AC-5b (added 2026-07-27 — the instrumentation requirement three documents already claimed was here)**: **ENUMERATION and MEASUREMENT are two separate obligations and must be discharged in that order.**
  - **(i) DERIVE the hand-off matrix from the code first, and record it BEFORE reading the reference list in (ii).** Do not re-run an instrument you have already built: **a second run of a first instrument is not a second measurement — it reproduces the first one's blind spot exactly.** The suspect artifact is the SHAPE ENUMERATION, not the probe.
  - **(ii) THEN compare yours against the reference list below. Any point in one list and not the other is a FINDING to report, not a discrepancy to merge silently.** The reference list is a FLOOR against silent shrinkage, not a checklist to work — which is why (i) comes first and is recorded first. This is story 01's AC-9 discipline applied to a matrix instead of a sweep.
  - **(iii) MEASURE `in_transaction` at every point in the UNION of the two lists**, at each entry point, and report the observed value for each. **Any point observed `True` stops the story** — raise it rather than proceeding.
  - **The question to ask of every measurement, because a green reading can cover nothing:** not *"did I measure a reap?"* but **"which LIVE CALLER produces the connection state this measurement observed?"** If the answer is "none," the cell covers nothing however clean it reads.
  - **⚠ SCOPE — this AC measures the PRE-GUARD premise only.** It establishes whether any live caller was dirty *before* the guard existed, which is the evidence that justifies ADDING it. **Whether the DELIVERED guard raises on any live shape is a different question and is UNMEASURED.** Nothing in this story may assert the shipped guard is inert in production; that is the reviewer's post-guard run, not this AC's subject.
  - **The eight hand-off points, named so the list cannot quietly shrink to the four the Technical Approach preserves:** (1) `generate_report` → `cleanup_expired_reports`, dedicated fresh conn; (2) `bb report cleanup` → `cleanup_expired_reports`, `conn=None`; (3) admin report-delete → `reclaim_orphan_reference_data`, fresh conn; (4) **the one-shot script → `reclaim_orphan_reference_data`, owned conn AFTER `count_orphan_reference_data(conn)` has run SELECTs on it**; (5) app-startup lifespan → `reap_stale_generating_reports`, `conn=None`; (6) `cleanup_expired_reports` → reap, borrowed, first statement; (7) `cleanup_expired_reports` → `reclaim`, borrowed, after cleanup's own commit; (8) `reclaim` → reap, borrowed, Step 1, **not wrapped**.
  - **Row 4 is the one that must survive into your run.** It is covered by NEITHER preserved enumeration — one established only that the script *owns* its connection, the other covered fresh-conn and `None` shapes at two entry points. **Neither measured the connection after SELECTs had run on it**, and it is the only cell that could plausibly have been dirty.
  - **Two controls, or the result is worthless.** A **positive** control showing the run actually performed the DML whose commit you are measuring around (otherwise a post-commit borrowed reading is vacuous), and a **negative** control showing a deliberately dirtied connection reads `True` (otherwise the `False`s are a dead instrument, not observations).
  - **⛔ NOT satisfiable by citing anyone else's list or measurement** — the reviewer's, the Technical Approach's, or this AC's. **If your result disagrees with any of them, report the disagreement; do not reconcile it.** A disagreement here is this story's most valuable output and goes to the lead unsynthesized.
  - **⚠ This AC does NOT claim to produce two INDEPENDENT measurements, and must not be read as doing so.** The exchange has already spent part of that independence: the implementer's **pre-question measurement (six shapes) was independent**; its **re-derivation under this AC is PROMPTED**, because clarifying questions put to it encoded shapes from the reviewer's matrix — asking *"did you probe the internal hand-offs?"* tells you there are internal hand-offs worth probing. **So record WHICH enumeration was independent and which was prompted, per the provenance practice.** What this AC can require is derivation-before-reference, measurement at every union point, and no citation of another's list. **What it cannot require is that you reach the enumeration unaided — and an AC that pretended otherwise would be asserting an independence the record does not support**, which is this epic's defect in its own remedy for the third time.
  - **Why this AC exists, recorded so it is not trimmed later as redundant.** THREE documents already asserted that AC-5 required this — the Technical Approach twice and epic TN-9's closing sentence — and **AC-5 contained no such requirement.** All three were claims about a document nobody opened, inside the story whose TN-9 exists to warn about precisely that. It is load-bearing twice: the entire safety case for adding a `raise` to three production paths is "no live caller is dirty," and this is **the only structural counter to the implementer having authored the original measurement and then implementing against it.**
  - **⚠ KNOWN LIMITATION — THIS AC'S ORDER REQUIREMENT IS UNSATISFIABLE AS WRITTEN. Recorded, deliberately NOT re-authored (PM4 ruling 2026-07-27, `cr2` concurring).** Clause (i) requires deriving the matrix **before** reading the reference list — **and the reference list is inside this AC.** Reading the AC to learn the requirement *is* reading the list. **No implementer could have complied**, so the order clause is not grounds for failing anyone. `se` complied as far as possible, **reported the non-compliance rather than claiming the order met**, and labelled its re-derivation PROMPTED — which is exactly what the ⚠ provenance bullet above asks for. **The AC is MET IN SUBSTANCE**; only the order is defective.
    - **Not re-authored, for three reasons**: round 2 of 2 was spent, and moving AC text mid-review had already cost a review bracket once; the AC is discharged in substance, so a rewrite serves nobody; and **the real fix is structural and belongs to the next story of this shape, not to a text patch at the end of this one.**
    - **The structural fix, for whoever writes the next one: the reference list must live somewhere the implementer is RELEASED TO after recording their own** — a separate file, or held by PM and sent on request. Not in the AC that states the requirement.
    - **And the transmission failure is mine, which is worse than the drafting one.** I sent this AC text to `se` **twice**, each time stating that the derive-before-reference ORDER was the mechanism and that a paraphrase would collapse it — **while the text I was sending contained the list.** I handed over the reference list in the act of insisting it be read second. `pm3` drafted the defect; I transmitted it twice while naming it.
- [x] **AC-5a**: The precondition check is **defined once and shared by all three entry points**, not copied into each, **and the shared definition PERFORMS THE RAISE** — a `_require_clean_connection(conn)`-shaped helper, not a `_conn_is_dirty(conn) -> bool` predicate with three separate `if …: raise` statements at the call sites. **The distinction is not stylistic:** AC-4's `python -O` subprocess test runs the AC-1 scenario, which reaches `reclaim_orphan_reference_data` only, so a shared *predicate* with three separate raise sites satisfies AC-5a while leaving **two of the three raises unpinned** — and a later bare `assert` at either is exactly what AC-4 exists to catch. Single-sourcing the raise closes that at the source rather than by widening AC-4. Three hand-maintained copies of the same check is the "second path to something that already has one" shape `.claude/rules/canonical-seams.md` names as this codebase's recurring defect, and the copies drift. The shape of the shared definition is the implementer's call; that it is single-sourced is not.
- [x] **AC-6**: Given a failure inside the pass's transaction where SQLite has ALREADY auto-rolled back, when the exception handler runs, then the original exception is what propagates — the handler no longer raises "cannot rollback - no transaction is active" in its place. **Modelling this precondition is acceptable and is the expected route** (see Technical Approach); a genuine `SQLITE_FULL` is not required.
  - **AC-6a — the fix must not be broader than the defect.** *"The original exception propagates"* is also satisfied by wrapping the rollback in `except Exception: pass` — **which swallows a GENUINE rollback failure too** (`database is locked`), leaving an open transaction on a **borrowed** connection. **That is a worse state than the defect being repaired.** So: attempt the rollback only when a transaction is actually active (`if conn.in_transaction:`), or narrow the swallow to the no-active-transaction case and LOG any other rollback failure. A fix whose blast radius exceeds the bug's is not a fix.
  - **AC-6b — the same class, one site over, named so it is not correctly left out.** The deferred branch's own `conn.execute("ROLLBACK")` in the Step-2 gate is equally unguarded. AC-6 names only *"the exception handler"*, so an implementer could satisfy it and leave this untouched. **Include it under the same rule, or exempt it by name with a reason.**
- [x] **AC-7 (re-shaped 2026-07-27 — see AC-7a)**: For each of the THREE entry points, a reader of its docstring **ALONE, without reading the function body**, can answer both: **(a)** that passing a connection with an open transaction RAISES rather than proceeding, and **(b)** for the two that accept `conn=None`, that the `None` path does NOT raise. Separately, **`_conn_scope`'s docstring states AFFIRMATIVELY that the sweeps using it COMMIT on a borrowed connection, and that the only caller state it restores is `row_factory` — explicitly NOT transaction state. A reviewer must be able to QUOTE the sentence carrying this.** The existing *"keeps the borrow non-destructive"* claim is either scoped to `row_factory` or removed.
  - **AC-7b — why the trailing clause was replaced, and it is my own defect (PM, 2026-07-27).** It previously read *"a reader … cannot come away believing a borrowed connection is never committed"* — **a negative universal over readers, which no non-author can falsify**: there is no line to quote and no state to observe. **It failed AC-7a's own test, in the AC where I wrote that test**, one message after calling the property form "the whole point." The replacement names the artifact a verifier produces — a quotable sentence — which is what makes it property-shaped.
  - **And the live defect is WORSE than the clause assumed.** `_conn_scope`'s docstring does not merely OMIT the commit fact: it **affirmatively asserts something false** — the `row_factory` restore *"keeps the borrow non-destructive"*, which is true of `row_factory` and **false of transaction state**, since the sweeps using that helper commit on the borrowed connection. **This epic's signature one-sided claim, sitting inside the very helper AC-7 points at**, and the old AC could be satisfied without touching it. Found by code-reviewer.
  - **AC-7a (why this was re-shaped, and the general rule).** The original read *"the docstrings … state the clean-connection precondition"* — an **ACTION**, and an action is satisfiable by performing it badly: a docstring can state a precondition ambiguously, or in terms only its author can decode, and still have "stated" it. **The form above is a PROPERTY: it is checkable by a non-author against the file with no knowledge of what the implementer did.** That last clause is the test — **if verifying an AC requires knowing the author's process, it is action-shaped.** Per epic TN-15. Flagged by code-reviewer against story 01's AC-6b and AC-9, both of which were action-shaped and both of which passed while false.
  - **Note the quote that prompted this was STALE and the defect was real anyway.** The reviewer cited AC-7 as *"the docstrings of both public passes"*; the AC already said **THREE** entry points. The staleness affected the count, not the shape — recorded so the correction is not mistaken for a rejection of the finding.
- [x] **AC-8 (quantifier restricted 2026-07-27)**: The docstrings and any new comment state the guard's effect in BOTH directions: it raises at the entry point, AND **every call site AT WHICH THE GUARD CAN FIRE** catches that raise rather than letting it propagate. **NOT "demotes it to a log line" — that predicate was itself false and is corrected here (PM4, 2026-07-27):** at one site the consequence does NOT stop at the log, because `scripts/reclaim_orphan_reference_data.py` also returns a non-zero process exit. **"Catches" is true of every member; "demotes to a log line" was true of all but one** — the same one-sided-quantifier defect this AC exists to repair, sitting in the AC's own predicate after its quantifier had already been fixed once. **State each site's actual consequence, not the shared pattern.** **The list is CLOSED, with its exemptions named** — the same device story 04's AC-6 uses for the two frozen surfaces, so this is a house pattern rather than a new one:
  - **Demoting sites** (count REMOVED per story 01 AC-9b — the list IS the enumeration, and a tally beside it is one more thing to keep in step): `cleanup_expired_reports` → `reclaim` at WARNING; `cleanup_expired_reports` → reap at WARNING; the admin report-delete path in `src/api/routes/reports_admin.py` at WARNING; `generate_report` at ERROR. **The log LEVELS are verified correct by code-reviewer** — do not change them, state them. **Their ATTRIBUTION is not — see the ⚠ clause below.**
  - **One further demoting site the previous wording did not name — and it is a QUALIFIED member, not a clean one:** `scripts/reclaim_orphan_reference_data.py`. It passes a REAL connection — verified at `:124`, after `count_orphan_reference_data(conn)` has run SELECTs on it at `:121` — so the guard can fire there. **But "demoted to a log line" is FALSE of this site:** it catches, logs at `logger.error`, **and returns `EXIT_ERROR`**, so the consequence does not stop at the log — it escapes as a non-zero process exit. **State the exit code alongside the log level; do not round it into the pattern.**
    - **Ruled a QUALIFICATION on the demoting entry, not a third category (PM4, 2026-07-27 — this was raised as an open AC-text question and it is my call).** The site genuinely belongs in the demoting class: it CATCHES the raise, so the exception does not propagate, which is what "demoting" means here. A third category would imply it does not demote, which is false. **What is additional is that the demotion is not the end of the consequence.** So the class is right and the AC's headline predicate was the thing that was wrong — see the correction to it above.
    - **Found by `se` enumerating from the CALLERS rather than from this AC's list** — which is the ⚠ clause below working as intended on its first use. **Worth recording as evidence for that clause rather than as a one-off:** an implementer working from this list would have written "demotes to a log line" and been wrong; one working from the code found the exit code. **The list did not contain the defect — the list WAS the defect.**
  - **EXEMPT, by name, and each for a stated reason:** `bb report cleanup` in `src/cli/report.py` — **not** because it demotes, but because it passes `conn=None`, so the guard cannot fire there at all; **the `src/api/main.py` startup reaper, for the IDENTICAL reason** — verified at `src/api/main.py:80`, the call is a bare `reap_stale_generating_reports()` with no connection, and while it does catch and log at `logger.warning`, the guard can never fire there for it to demote; and `reclaim` → reap at Step 1, which is **not wrapped**, so a reap raise there propagates out of `reclaim` to its own caller rather than being demoted.
  - **⚰ RETIRED CLAIM, kept as a quoted tombstone rather than silently deleted (PM4, 2026-07-27).** This AC previously read: *"Two further demoting sites the previous wording did not name: `scripts/reclaim_orphan_reference_data.py` … and the `src/api/main.py` startup reaper (catches, `logger.warning`)."* **The `src/api/main.py` half was a misclassification.** The FACT it asserted is true — that site does catch and log at WARNING — **which is exactly how it survived: anyone checking the fact passes it, and only the classification is wrong.** It sat four lines above an exemption granted to `bb report cleanup` on identical facts: same test, same facts, opposite disposition, inside one AC. Left standing it would have required an implementer to write something false into a safety docstring. Found by PM4 reading `main.py`; `cr2` independently verified it and withdrew the matching clause of its own MUST FIX 3, recording that **its own pre-guard AND post-guard matrices had each already logged that shape as `conn=None`** — a falsifying fact sitting unread inside its own artifact, twice.
  - **⚠ THIS LIST IS GLOBAL; THE PROPERTY IS PER-ENTRY-POINT. Do NOT write one demotion paragraph into three docstrings.** Each entry point's raise has its own demotion picture, and a near-generic paragraph is wrong at every site in a different way — which is what shipped. Two demonstrations, both `cr2`, round 1: `cleanup_expired_reports` catches the REAP's raise at WARNING, so **`generate_report` can never observe a reap raise at all**, yet the reap's docstring cites it; and **`reports_admin.py` contains ZERO references to `cleanup_expired_reports`** (verified by count, not inference), yet cleanup's docstring credits it as demoting cleanup's raise. **Derive each docstring's demotion set from the CODE — the actual callers of THAT function — not from this list.** A hit in this list is a candidate, never a member.
  - **Why the quantifier had to move:** as written, *"every wired call site demotes that raise"* was **falsified by AC-5 inside this same story**, which states the CLI has no try/except and therefore no degradation path. Both could not be true. The universal survived only on an unstated restriction — that the guard cannot fire where `conn=None`. **Stating the restriction is the fix; the two ACs now agree.**
  - "Refuses loudly" describes a direct caller, not the deployed behavior; the guard's production value is that the destructive path stops, not that an operator is paged.

## Technical Approach
AC-4 exists because a bare `assert` is stripped under `python -O` / `PYTHONOPTIMIZE`. This guard prevents data loss rather than catching a development slip, so it must survive optimization. Software-engineer checked the deployed shape and reports the Dockerfile CMD is a plain `uvicorn` invocation today, so nothing strips asserts right now — **that is precisely the argument for the AC rather than against it: the protection is one environment variable away from silently vanishing, with no test failing to signal it.**

**A convention already exists and the AC should follow it rather than invent one.** Software-engineer confirmed that `reclaim_orphan_reference_data`'s own Step-7 fixed-point self-assert raises a bare `RuntimeError` with a formatted message and rolls back rather than committing a half-correct state — the same function, the same author, reaching for a raise over an `assert`. That is the module's established "refuse loudly on a violated invariant" shape.

Software-engineer instrumented `in_transaction` at the **two originally-scoped** entry points across every live caller shape — `cleanup_expired_reports` with a fresh connection, the same with an expired-report row so DML precedes the reclaim, `reclaim_orphan_reference_data` with a fresh connection, and `conn=None` — and found all `False`. That measurement is preserved as observed; it predates the third entry point and must not be read as covering it. **AC-5b — not AC-5 — is what requires your own instrumentation, and it names EIGHT hand-off points, not three.** (Until 2026-07-27 this sentence read *"AC-5 requires you to instrument all three"* and **AC-5 contained no instrumentation requirement at all** — one of three documents asserting a criterion nobody had opened. Corrected rather than deleted, because the miscitation is the reason AC-5b exists.) The guard is inert today, which is what you want. If your run disagrees, report it.

**There are THREE borrowed-connection surfaces, not two, and an earlier draft of this story was wrong about its own coverage.** That draft said: "Guarding only `reclaim_orphan_reference_data` would leave `cleanup_expired_reports` exposed, which is why this story guards the reap itself as well." Guarding the reap leaves it exposed too. Code-reviewer traced `cleanup_expired_reports(dirty_conn)` **with both of those guards installed**, and software-engineer executed the same trace:

1. it calls `reap_stale_generating_reports(conn)` inside `try: ... except Exception: logger.warning(..., exc_info=True)` — the reap's new raise is **swallowed** and execution continues;
2. it runs its expiry sweep and issues its OWN unconditional `conn.commit()` — the caller's uncommitted DML is now committed;
3. it calls `reclaim_orphan_reference_data(conn)`, whose new guard sees a connection no longer in a transaction, **passes**, and deletes the just-committed rows.

Same outcome as today's defect: committed, deleted, the caller's later rollback recovering nothing. **Software-engineer additionally re-ran it with the reap neutralized to a no-op entirely and got the identical outcome — so the reap is not load-bearing to the bypass at all; `cleanup_expired_reports`' own commit is sufficient on its own.** This is why AC-2.1 guards cleanup at its ENTRY rather than hardening the reap further, and why the guard must sit outside the swallowing `try`.

**AC-2's guard on the reap is RETAINED, not made redundant by AC-2.1.** With the cleanup entry guard in place the reap's guard becomes belt-and-braces on that particular path, but `reap_stale_generating_reports` is public and directly reachable, and a future caller passing it a borrowed connection would otherwise be unguarded. Do not drop it as duplicate work.

**Why an entry guard is safe to add — measured at `cleanup_expired_reports`' own entry, not inferred.** Software-engineer instrumented `in_transaction` at cleanup's first statement: `generate_report`'s run-start call is **False**, the same with an expired-report row present (so DML would precede) is **False**, and `bb report cleanup` has **no connection yet**. No shape is dirty.

**A wider caller enumeration exists and is accurate, but it is about other functions — do not read it as covering this guard.** Code-reviewer's list (admin delete opening a fresh connection for the reclaim, the one-shot script and app-startup reaper owning theirs) enumerates callers of `reclaim_orphan_reference_data` and `reap_stale_generating_reports`. This guard sits on `cleanup_expired_reports`, a different and much smaller call graph. Both are true; only the cleanup-specific measurement below bears on AC-2.1.

Two corrections to the caller picture came out of that measurement and are worth having before you start. **`cleanup_expired_reports` has exactly TWO live call sites** — `src/reports/generator.py` and `src/cli/report.py` — found by searching for calls rather than mentions. **There is no app-lifespan path into cleanup**: `src/api/main.py` calls `reap_stale_generating_reports()` directly, and the occurrences in `src/api/routes/reports.py` are prose inside comments. Do not write an AC or a test premised on a lifespan → cleanup path.

And **the reason `generate_report`'s call is clean is stronger than the in-code comment claims.** That comment argues safety from `_ensure_team_row` being a later `run()` step. The measurement shows something that does not depend on that argument being right: `generate_report` opens a **dedicated fresh connection** for the cleanup call and closes it immediately, so `run()`'s shared connection never reaches cleanup at all. Cite the dedicated connection, not the ordering argument — it is the more durable reason.

**Do not inherit any of this from this paragraph — AC-5b requires you to re-verify by instrumenting `in_transaction` at each of the eight hand-off points it names.** If any live shape is dirty at entry, stop and flag it: the guard would break production and the epic's Goal 3 needs narrowing instead.

**For AC-6, a construction is named because software-engineer already hit the dead end.** It could not force a real `SQLITE_FULL`: capping `max_page_count` at the current page count does not trip it, because the sweep's DELETEs free pages rather than allocating them. The workable route — and the one by which the defect was originally confirmed — is to MODEL the precondition: have an internal step issue a `ROLLBACK` and then raise, or patch the connection so `execute("ROLLBACK")` raises `sqlite3.OperationalError("cannot rollback - no transaction is active")` with an original exception in flight, then assert the original propagates. Modelling is acceptable here; do not spend a cycle chasing a genuine disk-full.

For AC-6, note also that the handoff overstates the harm and the epic does not inherit that. Software-engineer verified the swallow sites log with `exc_info=True`, so the original cause IS present in the emitted traceback under "During handling of the above exception" — it is demoted, not lost. What is actually wrong is the exception type and message a caller sees programmatically. Reachability is also narrower than implied: the obvious trigger, `BEGIN IMMEDIATE` losing a lock race, raises outside the `try` and propagates a clean `database is locked`. This only bites on an in-transaction `SQLITE_FULL`/`IOERR`.

Do not change the reap's commit semantics for the owned-connection case, and do not alter the reap-then-gate concurrency guard — epic Non-Goals bar redesigning the sweep. This is a precondition check, an exception-handler correction, and docstrings.

Constraints: synthetic DBs from `migrations/` only; never touch `data/app.db`; no `bb` commands.

## Dependencies
- **Blocked by**: E-277-01
- **Blocks**: E-277-03

## Files to Create or Modify
- `src/reports/lifecycle.py`
- `tests/test_orphan_reclamation.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-277-03**: Final state of `src/reports/lifecycle.py` and `tests/test_orphan_reclamation.py`. Story 03 adds tests to the same file.

## Definition of Done
- [x] All acceptance criteria pass
- [x] Tests written and passing
- [x] Code follows project style (see CLAUDE.md)
- [x] No regressions in existing tests

## PM AC Verdict — FINAL (2026-07-27, PM4)

**ALL THIRTEEN ACs PASS.** Verdicts ENUMERATE, never span: **AC-1, AC-2, AC-2.1, AC-3, AC-4, AC-5, AC-5a, AC-5b, AC-6, AC-6a, AC-6b, AC-7, AC-8.** Thirteen named; no range.

`cr2` reviewed independently across two rounds and reached the same thirteen. Where we agreed on the four round-1 FAILs, neither had seen the other's findings.

### What I verified AT THE PRIMARY, and what I took from others

**Read by me in the code or tests, and every verdict resting on it is mine:**
- **AC-6b** — `lifecycle.py:1421`. `"normally active"` occurs **nowhere** in the module. The comment opens `UNREACHABLE TODAY, and kept deliberately on a stated basis`, cites `_TEAM_STAT_EXISTS` by name, states why it cannot fire (**"NECESSARILY active here, not merely usually"**), and justifies guarding over exempting because the exemption's own argument leans on a `BEGIN IMMEDIATE` three statements away — *"exactly the 'safe because of what happened two statements ago' reasoning this epic keeps finding wrong."*
- **AC-8** — zero occurrences of either retired universal. `src/api/main.py` **EXEMPT** at `:213`; `reports_admin.py` *"does not call this function"* at `:332`. Notes line 321 rewritten: four levels including the script's **ERROR plus non-zero exit**, both `conn=None` exemptions named, and the dated correction record at line 323 correctly **preserved as evidence rather than edited**.
- **The MUST FIX, per the operator's explicit condition that I verify at the primary rather than accept a report.** `test_precondition_check_is_single_sourced`'s body calls **two** entry points (`:997-998`) with two assertions. The corrected docstring now claims exactly those two — *"either of these two"* — states **"This test covers TWO of the three entry points, not three,"** cites `cr2`'s ac5a mutation as measured rather than assumed, and **points at the sibling as the third entry point's only coverage.** The sibling's own reason-for-existing docstring is intact at `:1005`. **Discharged, and better than asked: it repairs the inversion rather than only the false sentence.**
- **AC-5a** — helper defined once (`:92`), performs the raise (`:131`), called at `:222` / `:348` / `:1379`.
- **AC-3** (`:1377-1379` precedes `:1383`), **AC-2.1** (`:339-348`, outside the swallowing `try`), **AC-7** (`_conn_scope`'s quotable sentence at `:69-79`).

**Taken from `cr2`, NOT re-derived by me:** the `308 passed` across the six enumerated files; the non-vacuity of AC-5a and AC-6 via two scoped mutations; the post-guard run; AC-2.1's confirmation by measurement; the `reports_admin.py` zero-reference count; and the executable proof behind the MUST FIX.

**Taken from `se`, NOT re-derived by me:** `4291 passed` / exit 0, ruff parity, and the AC-5b measurement values.

**I did NOT verify:** that the added tests account for the suite delta exactly.

### ⚠ The one claim that must not ship stronger than its evidence

**AC-5b's safety case is: seven points independently enumerated and twice measured; ONE point — row 4 — singly enumerated and twice measured.**

This is `cr2`'s formulation and it replaces mine, which said *"two independent measurements over a partly-shared enumeration"* — vague exactly where it needed to be specific. The eight points are `cr2`'s and reached `se` through the AC text, **so a hand-off `cr2` missed is missed identically by both runs.** `se`'s pre-question six-shape enumeration was genuinely independent and, reconciled for the unit mismatch, corroborates **7 of 8**. **Row 4 — the one-shot's connection after `count_orphan_reference_data`'s SELECTs — is enumerated by `cr2` alone, and it is the cell both prior enumerations missed.** Residual risk is localised there and nowhere else.

**Do NOT shorten this to "two independent measurements."** That phrasing was retired from AC-5b for this reason and would be reintroduced by paraphrase. **The mechanism, so this prohibition is self-sufficient rather than an appeal to authority: the MEASUREMENTS are two; the ENUMERATIONS are two for only seven of the eight points — and that gap is exactly where an unexamined hand-off could still hide.** `se`'s Notes state the same bound in the same words, independently sourced from `cr2`; **the two statements were compared after both landed and agree** (PM4 consistency sweep, recorded rather than left silent per story 01 AC-9b).

### Gate — all three propositions answered

1. **Correctly built?** Yes — thirteen ACs, two independent reviews.
2. **Should the guard exist?** **Yes, and this was the gating question.** `se`'s pre-guard measurement against the staged blob, verified pre-guard at load (`_require_clean_connection` occurrences **0**, keep-root **1**), both controls firing, **all eight points `False`/`None` including row 4.**
3. **Does the delivered guard raise on a live shape?** No — `cr2`'s post-guard run, clean. Bounded: it reproduced caller **shapes**, not callers.

---

### Historical record below — the INTERIM verdict, retained as evidence

**Everything from here to the end of this section was written at ~03:05 against a tree that has since moved.** It is preserved rather than rewritten because it is the dated record of what was observed and of four FAILs that were real when found — **all four now remediated and re-verified above.** Read it as evidence; the FINAL verdict above is the criterion.

> ## ⛔ SUPERSEDED TREE — READ THIS BEFORE APPLYING ANY VERDICT BELOW
>
> **Every verdict in this section was formed against the tree as it stood at roughly 03:05, and the tree has since MOVED TWICE.** Remediation went in flight at `src/reports/lifecycle.py` **03:22:58** and `tests/test_orphan_reclamation.py` **03:23:24**. **The verdicts below stand as ISSUED, for the state they were formed against; they must NOT be applied to the current tree.**
>
> **Relayed to PM by the dispatch lead and NOT verified by PM** (recorded as relay, per this epic's standing discipline): the production diff has grown from 162 to 186 insertions; the Step-2 gate `ROLLBACK` is now guarded; the reclaim docstring now discusses the one-shot script. **If those are accurate, at least AC-6b and part of AC-8 are already remediated and their FAILs below are historical.**
>
> **This section is now EVIDENCE — a dated record of what was observed — not a CRITERION.** Per `.claude/rules/tool-output-integrity.md`'s criterion-vs-evidence cut, it is preserved rather than rewritten. **The round-2 verdict will be a separate, later section against the settled tree.** `cr2`'s round-1 findings carry the identical bound, **including the `src/api/main.py` clause it withdrew to me: that withdrawal was correct when made, and whether it still describes the delivered docstrings is unverified.**
>
> **What does NOT go stale, and is the reason this section is still worth reading:** the AC-8 spec fix (a correction to the AC, not to the code — it stands regardless of what the tree does), and **AC-5b, which no code change can remediate** because it requires `se`'s own pre-guard measurement. See "The gate" at the end of this section.

**INTERIM RECORD, ISSUED BEFORE `cr2` REPORTED.** Written to disk because a verdict in a message is not a verdict in the epic.

### AC-6b — the reachability question I raised, ANSWERED (`cr2`, and it is stronger than I put it)

I invited the harsher answer — that I had reached a right call for a wrong reason. **The evidence does not support it; the call and the reason are both right.** `cr2` traced the structure rather than reasoning from the shape: **`conn.execute("BEGIN IMMEDIATE")` sits OUTSIDE the `try`**, so a failure there propagates immediately and the deferred branch is never reached; and **the gate's `SELECT` sits INSIDE it**, so a failure there diverts to the `except` handler rather than to the deferred branch. The deferred `ROLLBACK` is therefore reached only when `BEGIN IMMEDIATE` succeeded, the SELECT succeeded, and it returned nonzero. **So a transaction is not "normally" active at that line — it is NECESSARILY active.** My proposed exemption would have been correct on the merits; my FAIL verdict was correct because AC-6b requires *guarded or exempted-by-name* and the delivered code was neither.

**Carry into round 2 — a NEW SHOULD FIX arising from the remedy, not from the defect.** `se` took the *guard* branch rather than the *exempt* branch, which AC-6b permits, **so AC-6b is satisfied.** But its comment reportedly says a transaction is *"normally active here"* while also saying that relying on that is *"precisely the reasoning this epic keeps finding wrong"* — **two sentences pulling against each other with no statement of which is operative.** Given the analysis above the branch is **unreachable today**, so this ships a never-fires clause without saying it is dead: **MAJOR-2's exact shape, arriving inside the remedy for a different defect.** The house precedent sits in the same file — `_TEAM_STAT_EXISTS`, documented as *"VACUOUSLY TRUE on real data"*, deliberately kept, with the reason for keeping it stated. The comment should say plainly that the branch is unreachable today and that the guard is defensive against a future reordering (a statement inserted between `BEGIN IMMEDIATE` and the gate, or the `BEGIN` moved into a helper). **That basis survives a reader who checks; "normally active" does not.** Source `cr2`; PM has not re-read the delivered comment. AC boxes are deliberately NOT ticked: three ACs do not pass as delivered. Verdicts ENUMERATE — every AC in the story is listed below; none is covered by a range.

| AC | Verdict | Basis |
|---|---|---|
| AC-1 | PASS | PM read `test_reclaim_refuses_dirty_connection_and_preserves_caller_work`: raises, invisible to an independent connection, still present to the caller, rollback discards |
| **AC-2** | **FAIL** | **Regraded from PARTIAL, on the merits — see reconciliation R1.** The AC's named observable is not asserted |
| AC-2.1 | PASS | Guard at `lifecycle.py:339-348`, outside the swallowing `try`; test asserts the reap was never invoked |
| AC-3 | PASS | Guard at `:1377-1379` precedes the Step-1 reap at `:1383`; pinned by `test_reclaim_guard_fires_before_the_reap` |
| AC-4 | PASS | Verdict stands; **my stated basis for it was WRONG — see reconciliation R2.** It discriminates on ONE load-bearing assertion, not three |
| AC-5 | PASS | Clean-conn unchanged; `test_guard_skips_the_owned_connection_path` pins the SKIP at reap + cleanup ONLY and does **not** generalize it to reclaim — exactly what the ⚠ sub-bullet requires |
| **AC-5b** | **NOT DISCHARGED** | Six shapes reported against eight named hand-off points; no derivation-first record; no controls — see finding 1 |
| AC-5a | PASS | `_require_clean_connection` defined once (`:92`), PERFORMS the raise (`:131`), called at `:222` / `:348` / `:1379`; a helper, not a bool predicate. Pinned behaviourally at all three |
| AC-6 / AC-6a | PASS | `:1443-1452` uses the narrow `if conn.in_transaction:` form, NOT a blanket swallow; test asserts `excinfo.value is original` |
| **AC-6b** | **FAIL** | The Step-2 gate's own `conn.execute("ROLLBACK")` at `:1395` is neither guarded nor exempted by name — see finding 2 |
| AC-7 / AC-7a / AC-7b | PASS | All three docstrings carry a PRECONDITION paragraph answering (a) and (b) plus a `Raises:` entry; `_conn_scope`'s affirmative commit sentence is quotable at `:69-79` |
| **AC-8** | **FAIL** | Two of the three docstrings carry false quantifiers — see finding 4 |

### The three findings behind the non-passes

1. **AC-5b — not discharged.** `se`'s Notes report six caller shapes under a heading naming AC-5, against AC-5b's eight hand-off points. **Point (4) — the one-shot script's owned connection AFTER `count_orphan_reference_data(conn)` has run SELECTs — is not distinctly measured**; the Notes' row 3 merges `reports_admin / one-shot script … (fresh conn)`, a different shape. PM verified point (4) is a real live cell: `scripts/reclaim_orphan_reference_data.py:121` runs `count_orphan_reference_data(conn)` and `:124` then passes that same connection to the reclaim. Neither the positive nor the negative control AC-5b requires is reported, and AC-5b states that without both "the result is worthless." **Not closable by citing `cr2`'s run.**

2. **AC-6b — FAIL, and the AC predicted this exact failure by name.** The deferred branch's `conn.execute("ROLLBACK")` at `:1395` is bare. AC-6b required it be brought under AC-6a's rule **or exempted by name with a reason**; neither was done, and the story Notes' AC-6 section does not mention AC-6b at all. A defensible exemption exists — the pass opened its own `BEGIN IMMEDIATE` two steps earlier and the gate SELECT cannot have closed it, so "no transaction is active" is unreachable there — but AC-6b requires that reason be *stated*, not assumed. Remedy is one line either way.

3. **AC-2 — narrow miss on the named observation.** `test_reap_refuses_dirty_connection_before_committing` asserts the raise, invisibility to an independent connection, and `conn.in_transaction`. The revised AC-2 names a specific observation — *"the caller's subsequent rollback still discards the DML"* — and that is not performed. **The substituted assertion is not weaker in substance**; it is simply not the one the AC names, and AC-2 was revised precisely because its earlier form "left nothing to assert on." AC-1 and AC-2.1 both do the rollback; this test is the odd one of three. Remedy: two lines, making the three uniform.

4. **AC-8 — FAIL. Two false quantifiers in delivered safety docstrings.**
   - `reap_stale_generating_reports` (`:204-209`) reads **"Every wired call site demotes it to a log line"** — the exact universal AC-8 retired, and **false**: `reclaim` → reap at `:1383` is a wired call site that is *not wrapped*, so a raise there propagates. AC-8 names that site as an exemption. Names three demoting sites; names no exemption.
   - `reclaim_orphan_reference_data` (`:1356-1362`) reads **"Both wired call sites"** — a false count. There are three that pass a connection; it omits `scripts/reclaim_orphan_reference_data.py`, which demotes at `logger.error` + `EXIT_ERROR` (`:161-162`).
   - `cleanup_expired_reports` (`:309-314`) is **correct in shape** — restricted quantifier, and it names the CLI `conn=None` exemption explicitly.
   - The story Notes assert *"The restricted quantifier is now used in all four."* True of the four SPEC surfaces; **false of the delivered code, a fifth site nobody counted.** One of three docstrings uses the restricted form.

### Reconciliation with `cr2` round 1 (2026-07-27, after its report landed)

`cr2` reviewed independently — neither of us saw the other's findings, and my verdict above was written before its report existed. **Its per-AC verdicts match mine on every AC except AC-2.** It graded PASS on AC-1, 2.1, 3, 4, 5, 5a, 6, 6a, 7 and FAIL on AC-2, AC-5b, AC-6b, AC-8. **AC-6b and AC-8 are therefore two independent derivations each**, which is worth more than one plus a confirmation.

**R1 — AC-2 regraded PARTIAL → FAIL. `cr2` had it right and my grade was the weaker ruling.**
Tested against TN-15's "conceding is not automatically the rigorous move": I am not yielding because `cr2` disagreed. Two grounds that hold independently of it. **(a) `PARTIAL` is not a status this system has** — inventing one let the unmet half read as half-satisfied, when the specific thing the AC asks for is simply absent. **(b) AC-2 was REVISED precisely because its earlier form "left nothing to assert on"**, and the revision's entire content is the naming of one observable. A test that substitutes a different observable defeats the revision even when the substitute is sound. **Recorded in the AC's favour, because it bears on remediation size:** `assert conn.in_transaction` is not sloppy and is arguably stronger on one axis — it proves the transaction was never closed, where rollback-discards would also pass had it been closed and reopened. The remedy is two lines bringing this test into line with AC-1 and AC-2.1, not a redesign.

**R2 — AC-4's verdict stands; the BASIS I gave for it was false, and it was mine.**
I recorded that the `-O` subprocess probe "carries its own `assert c.in_transaction` positive control." **It cannot: the probe runs under `python -O`, which strips that assert.** A precondition guard that does not guard, inside the test whose subject is that `-O` strips asserts — and I cited it approvingly as the test's strength. Found by `cr2`. Compounding it, `cr2` also found `assert "RAISED" in proc.stdout` is satisfied by the FAILURE output, since the probe prints `NOT RAISED` and `"RAISED" in "NOT RAISED"` is `True`. **So the test discriminates on `assert proc.returncode == 0` ALONE** — which does discriminate, so AC-4 passes. Two of its three assertions are decorative. **This is the exact defect I had spent the round documenting in others** — a verdict's stated reason rotting independently of its verdict — authored by me, in the same message where I praised the artifact for the property it does not have. Retained rather than quietly rewritten. `cr2` files both as SHOULD FIX.

**R3 — AC-8 gains a third site I missed, and `cr2`'s unifying form supersedes my three-row table.**
I found two mis-enumerations (the reap's retired universal; reclaim's false "Both wired call sites"). `cr2` found a third I did not: **cleanup's docstring credits the admin report-delete path with demoting cleanup's raise, and `reports_admin.py` contains ZERO references to `cleanup_expired_reports`** — verified by count. It further observed that the reap's docstring cites `generate_report` at ERROR, when `cleanup_expired_reports` catches the reap's raise at WARNING, so `generate_report` can never observe a reap raise at all. **Its synthesis is better than my enumeration and I am adopting it: this is not three separate mis-citations but ONE near-generic demotion paragraph written into all three docstrings, accurate for none of them individually.** My table recorded cleanup's docstring as "correct in shape" — true of its quantifier and its CLI exemption, **false of its site attribution.** That row is corrected here rather than in place, so the original ruling stays visible.

**R4 — `cr2` withdrew one clause of its MUST FIX 3, and the withdrawal is recorded because the mechanism is the finding.**
It had asked that the reap's docstring name `src/api/main.py` as a demoting site. It verified my Finding A, agreed the guard cannot fire there, and withdrew. Its own account, which I am recording unsoftened at its framing: **its pre-guard AND post-guard matrices had EACH already logged that shape as `conn=None`** — the falsifying fact sat in its own output twice, and it used AC-8's classification as a criterion without re-deriving it against its own data. My Finding A is upstream of its finding: had AC-8 not been corrected first, `se` would have been asked to write a false statement into a safety docstring.

**R5 — what neither of us reached alone, which is the staffing argument.**
Each of us found in AC-8 what the other missed, reading the same files: I was checking **classification** (is this site on the right side of the quantifier), `cr2` was checking **membership** (is this site real at all). Neither gap was carelessness. Two independent reviewers found four defects in one criterion; either alone would have shipped some of them.

### PROVENANCE

- **PM read directly, and every verdict above rests on it**: `_conn_scope` and `_require_clean_connection` in full; all three entry-point docstrings and their guard call sites; the exception handler at `:1443-1452`; the Step-2 gate at `:1395`; the eight guard/rollback tests at `tests/test_orphan_reclamation.py:803-1014`; `src/api/main.py:74-87`; `scripts/reclaim_orphan_reference_data.py:121-162`.
- **Taken from `se` and NOT independently re-derived**: the suite result (`4290 passed`, exit 0), the ruff parity, and the mutation-check outcome (6 tests failing under the mutant).
- **Taken from `cr2`, added after its round-1 report and NOT independently re-derived by PM**: AC-5's PASS rests on **its** run of all six enumerated test files (`307 passed`) — I did not run them; the non-vacuity of AC-5a and AC-6 rests on **its** two scoped mutation probes; the post-guard result (no live caller shape raises against the delivered tree; negative controls fire at all three entry points; positive control fired) is **its** measurement; AC-2.1's confirmation *by measurement* — cleanup's entry then the raise with no reap invocation between — is **its** probe, distinct from my reading of the code. The `reports_admin.py` zero-reference count in R3 is **its** verification, not mine.
- **⚰ TOMBSTONE — a claim in this block that was TRUE WHEN WRITTEN and is now false.** It read: *"**Taken from NOBODY**: `cr2`'s review had not reported when this was written. No cell above cites it."* That was accurate at the time and is why the independent convergence in R1–R5 counts as convergence. **It is retired rather than deleted** because a reader arriving later would otherwise have no way to tell which cells were independent of `cr2` and which now lean on it — and the bullet above answers exactly that. The verdicts for AC-1, 2.1, 3, 4, 5a, 6/6a, 6b, 7 and 8 were all reached before `cr2` reported.
- **PM did NOT verify**: that the eleven added tests account for the suite delta exactly; that no live caller was dirty **before** the guard existed — that is AC-5b's open subject and **the single most important thing still unestablished in this story**. `cr2`'s post-guard run does not settle it, and `cr2` says so itself: the pre-guard safety case currently rests on its run **alone**, which is the single-source condition AC-5b exists to prevent.

### The gate, stated separately so an AC-by-AC pass cannot be mistaken for it

**Story 02 cannot reach DONE on an AC-by-AC pass alone.** Three propositions, kept apart because merging them is this dispatch's signature defect:

1. **Is the guard correctly built?** — my ACs plus `cr2`'s findings settle this. Currently: four FAILs outstanding.
2. **SHOULD the guard exist?** — **only AC-5b's PRE-GUARD measurement settles this, and it is currently single-source.** `se` wrote a `raise` into three production paths; the evidence it offered was post-guard. `4290 passed / exit 0` does not bear on this question at all — the suite proves the guard behaves as specified, not that it should be there. **If `se`'s pre-guard re-measurement finds any shape dirty, AC-5b stops the story, the guard is not what ships, and epic Goal 3 narrows instead.**
3. **Does the delivered guard raise on a live shape?** — `cr2`'s post-guard run, **CLEAN**. No production breakage. **Bounded, per `cr2`'s own grading of it: that run reproduced caller SHAPES, not callers.** `generate_report` and the admin route were never executed; their connection handling was reconstructed and the reconstructions measured. **ESTABLISHED that the reproduced shapes are clean; ASSERTED that the reproductions are faithful.** A caller doing something before its entry-point call that the model omits is invisible to it.

**⛔ A TRAP FOR ANY SUCCESSOR READING `cr2`'S CONCLUSIONS RATHER THAN ITS CAVEATS — recorded here because the two live in different places.** `cr2` reported **"7 of 7 agreement"** with `se`'s matrix. **That agreement is between two POST-guard runs and corroborates proposition 3 only.** `se` measured the post-guard tree; `cr2`'s comparison run was post-guard too. **It does NOT corroborate proposition 2, which remains sole-sourced to `cr2`'s single pre-guard run.** `cr2` flagged the tree-state ambiguity as an open question **in the same message as the 7-of-7 headline, and did not apply its own caveat to it** — its words: it *"raised the caveat and did not apply it to my own headline,"* and it rates this a sharper failure than the `main.py` clause it withdrew, because that one was inheriting someone else's criterion while this was **declining to apply its own.** **So: a reader who takes 7-of-7 as evidence the guard should exist has been misled by an accurate number.**

### Known spec defect in AC-8, being corrected separately by PM

AC-8's closed list classifies `src/api/main.py`'s startup reaper as a **demoting site**. Verified at `src/api/main.py:80`: the call is `reap_stale_generating_reports()` — bare, `conn=None`, so **the guard cannot fire there**. That is the identical test by which AC-8 exempts `bb report cleanup`. The `logger.warning` fact stated about it is true; the classification is wrong and it belongs in the EXEMPT list. **The delivered docstrings correctly do not name it, so this is not an implementation defect** — finding 4 stands independently of it.

## Notes

### AC-5b — PRE-GUARD measurement, with provenance stated first

**⚠ PROVENANCE — my derivation under this AC is PROMPTED, not independent, and the AC's own order was not achievable as delivered.** AC-5b requires deriving the matrix *before* reading the reference list in (ii). **The reference list is inside the AC text**, so reading the AC to learn the requirement was reading the list. I am recording that rather than claiming an order I did not follow.

What is genuinely independent, and what is not:

| artifact | provenance |
|---|---|
| my original six-shape enumeration (pre-question) | **INDEPENDENT** — made before any reference or clarifying question |
| my re-derivation under AC-5b | **PROMPTED** — the AC's eight points were in front of me, and `cr2`'s three clarifying questions had already encoded that internal hand-offs exist |
| the measurement below | mine, run against the pre-guard staged blob |

The AC anticipates this ("its re-derivation under this AC is PROMPTED… record WHICH enumeration was independent and which was prompted"), so this is compliance, not deviation. But the stronger statement belongs on the record: **derivation-before-reference is not achievable when the reference is in the AC that states the requirement.** If that order is to bind a future story, the list has to live somewhere the implementer can be released to *after* recording their own.

**Derivation (prompted).** Every call site of each entry point, from `grep` for invocations across `src/` and `scripts/`, excluding definitions: three for the reap, two for cleanup (the two `src/api/routes/reports.py` hits are comment prose, not calls), three for the reclaim. That yields the same eight hand-off points as the reference. **No disagreement to report** — which given the provenance above is weak evidence of agreement, not strong.

**Tree state: PRE-GUARD.** Measured against `git show :src/reports/lifecycle.py` — the staged story-01 blob — loaded as a module. Verified at load: `_require_clean_connection` occurrences **0**, keep-root occurrences **1** (confirming it is story-01 state, not something older). Stated as a field because the post-guard/pre-guard distinction is invisible in the output otherwise, which is exactly how my first measurement went wrong.

**Both controls fired.**

- **NEGATIVE** — a deliberately dirtied connection read **`True`**. Without this every `False` below is consistent with a dead probe. My earlier table had no such row.
- **POSITIVE** — on the expired-report shape, `report_path` went `'reports/s.html'` → `None`. So the sweep genuinely performed commit-bearing DML, and the surrounding `False` readings are measured around a real commit rather than around nothing happening.

**The eight points, observed:**

| # | hand-off point | observed |
|---|---|---|
| 1 | `generate_report` → `cleanup_expired_reports`, dedicated fresh conn | `False` |
| 2 | `bb report cleanup` → `cleanup_expired_reports`, `conn=None` | `None` |
| 3 | admin report-delete → `reclaim_orphan_reference_data`, fresh conn | `False` |
| 4 | **one-shot → `reclaim`, owned conn AFTER `count_orphan_reference_data` SELECTs** | **`False`** |
| 5 | app-startup lifespan → reap, `conn=None` | `None` |
| 6 | `cleanup` → reap, borrowed, first statement | `False` |
| 7 | `cleanup` → `reclaim`, borrowed, after cleanup's own commit | `False` |
| 8 | `reclaim` → reap, borrowed, Step 1, not wrapped | `False` |

**No point observed `True`. The story does not stop.** Row 4 — the cell neither preserved enumeration measured, and the one the AC calls the only plausibly-dirty one — reads `False`: the read-only SELECTs in `count_orphan_reference_data` leave no open transaction behind them.

**⚠ THE PRECISE INDEPENDENCE CLAIM — code-reviewer's wording, and it must not be strengthened.**

> **Seven points independently enumerated and twice measured; one point — row 4 — singly enumerated and twice measured.**

My pre-question six-shape enumeration independently corroborates seven of the eight. **Row 4 is code-reviewer's alone**, and it reached me through the AC text rather than from my own derivation. So the residual risk is localised to row 4's neighbourhood; everywhere else two independent enumerations agree. **Do NOT write "two independent measurements"** — the measurements are two, the enumerations are two only for seven of eight, and the difference is exactly where an unexamined shape could still hide.

**⚠ SCOPE, per the AC.** This measures the PRE-GUARD premise only — whether any live caller was dirty before the guard existed, which is the evidence justifying adding it. **It says nothing about whether the delivered guard raises on a live shape.** That is a separate proposition and not this story's to assert.

### AC-5 — the six enumerated files, and the ⚠-clause check

Both requirements were added to AC-5 after this story's completion report, so they are recorded here from a verification run rather than from the original delivery.

**The six enumerated files, run explicitly rather than inferred from the full suite:**

```
308 passed, 1 warning in 35.53s
```

`test_admin_reports.py`, `test_cleanup_eligibility.py`, `test_cli_report.py`, `test_orphan_reclamation.py`, `test_reclaim_orphan_script.py`, `test_report_generator.py`. The AC's reason for enumerating holds: the two that exercise the carve-outs this AC protects — `test_cli_report.py` for the CLI `conn=None` path and `test_reclaim_orphan_script.py` for the one-shot's owned connection — are exactly the two the earlier phrasing ("all existing orphan-reclamation tests") omitted.

**The ⚠ clause: no test here pins the untrue claim.** `test_guard_skips_the_owned_connection_path` asserts only on `reap_stale_generating_reports()` and `cleanup_expired_reports()` — the two entry points where a `None` actually reaches a guard. It asserts nothing about `reclaim_orphan_reference_data` on that path.

**And the AC-5b measurement independently shows the fact the clause protects.** Point 2 of the matrix reads:

```
bb report cleanup (conn=None) ->
  [('cleanup_expired_reports', None), ('reap_stale_generating_reports', None),
   ('reclaim_orphan_reference_data', False), ('reap_stale_generating_reports', False)]
```

The reclaim reads **`False`, not `None`** — it receives a real connection, because it is invoked inside the rebound `with _conn_scope(conn) as conn:` block. **So the reclaim's guard is LIVE on every path, including the CLI one.** Reached from two directions independently: code-reviewer from the call graph, this measurement from the probe.

### AC-5 — `in_transaction` REGENERATED at all THREE entry points

Not inherited: the prior measurement covered two entry points and predates the third, and the story says so explicitly. Re-instrumented every live caller shape, recording the value at each entry point's own first statement.

| caller shape | observed at entry |
|---|---|
| `generate_report` → `cleanup_expired_reports` (dedicated fresh conn) | cleanup `False`, reap `False`, reclaim `False` |
| same, with an expired-report row so cleanup's own DML precedes the reclaim | all `False` |
| `reports_admin` / one-shot script → `reclaim_orphan_reference_data` (fresh conn) | reclaim `False`, reap `False` |
| direct `reap_stale_generating_reports` (fresh borrowed conn) | `False` |
| app-startup reaper (`conn=None`) | `None` — owned path |
| `bb report cleanup` (`conn=None`) | cleanup `None`, reap `None`, then the OWNED conn forwarded internally to reclaim at `False` |

**No live shape is dirty at any entry point.** The guard is inert today, which is what a latent-defect fix should be. Nothing to flag; epic Goal 3 does not need narrowing.

Worth recording from the last row: on the `conn=None` path, cleanup opens its own connection and forwards it internally to the reclaim, which then sees a **borrowed-looking** connection that is clean. The guard is correct there for the right reason rather than by luck.

### Round-1 remediation (2026-07-27)

**AC-6b — the Step-2 gate ROLLBACK.** Guarded, and the comment now states the reachability honestly rather than hedging. `cr2`'s analysis is right and stronger than my first note: a transaction is **necessarily** active there, not merely usually — `BEGIN IMMEDIATE` sits outside the `try`, so a failure there never reaches the branch, and a failed gate `SELECT` diverts to the `except` handler. **So the guard is unreachable today, and it is now documented as such** on the `_TEAM_STAT_EXISTS` precedent in the same file: state that it cannot fire, on what grounds, and why it is kept anyway. My first version said "normally active" while also saying that reasoning is wrong, and did not say which was operative — a never-fires clause shipped without saying so, which is MAJOR-2 arriving inside a remedy for something else.

Pinned by `test_every_rollback_in_the_module_is_transaction_guarded`, which asserts **structurally** (via `ast`) that every `conn.execute("ROLLBACK")` sits inside `if conn.in_transaction:`. Chosen over a behavioural test because there is no naturally reachable failing state, so a behavioural test would have modelled one and then tested the model. Carries an anti-vacuity floor (`>= 2` sites) and catches a fourth unguarded ROLLBACK added later. Mutation-verified: removing the guard fails it with `unguarded conn.execute('ROLLBACK') at line(s) [1428]`.

**AC-8 — three docstrings, each derived from ITS OWN callers.** The near-generic demotion paragraph was accurate for none of them individually. Derived separately:

- **reap** — `cleanup_expired_reports` (wrapped, WARNING); `reclaim` Step 1 (**not wrapped**, propagates to the reclaim's callers); `src/api/main.py` (**EXEMPT** — bare call, `conn=None`, guard cannot fire). States explicitly that `generate_report` and the admin path do **not** call it.
- **cleanup** — `generate_report` (dedicated fresh conn, ERROR); `bb report cleanup` (`conn=None`, **no try/except at all**). States explicitly that `reports_admin.py` does not call it.
- **reclaim** — `cleanup_expired_reports` (WARNING); `reports_admin.py` (WARNING); the one-shot script, which **logs at ERROR AND returns a non-zero process exit code** — so "demoted to a log line" is false of that site, and the docstring says so rather than rounding it into the pattern.

`src/api/main.py` is recorded as EXEMPT rather than as a demoting site, matching `pm4`'s spec correction; `cr2` withdrew the matching clause of its own finding.

**AC-2** — the test now observes the outcome as AC-1 does: the caller's subsequent rollback still discards the DML. `in_transaction` being `True` is the mechanism; the discard is the property.

**SHOULD FIX ×3.** The `-O` probe's tokens were `RAISED` / `NOT RAISED`, and **`"RAISED" in "NOT RAISED"` is `True`** — so the substring assertion was satisfied by the failure output and discriminated only because the returncode assertion happened to precede it. Now disjoint tokens with negative assertions on both failure paths. The probe's own precondition was `assert c.in_transaction` running under `python -O`, **which strips it** — a precondition guard that does not guard, inside the one test whose subject is that `-O` strips guards; now an explicit `sys.exit(2)` with its own token. And `test_cleanup_also_routes_through_the_shared_check` carries a DO-NOT-REMOVE note recording that under the duplicate-check mutation the other AC-5a test passes and only this one fails.

### Mutation check — the guard tests discriminate

A guard test that passes without the guard proves nothing. `src/reports/lifecycle.py` was backed up to the scratchpad, `_require_clean_connection` mutated to an unconditional early `return`, the suite re-run, and the file restored from that copy — **md5 verified byte-identical to pre-mutation (`dd18c461af0190aa1afd712ab22dfc17`), and zero `MUTANT` markers remain.** No `git checkout --` was used at any point.

With the guard disabled, **6 tests fail**: `test_reclaim_refuses_dirty_connection_and_preserves_caller_work`, `test_reap_refuses_dirty_connection_before_committing`, `test_cleanup_refuses_dirty_connection_before_reap_and_before_commit`, `test_reclaim_guard_fires_before_the_reap`, `test_guard_is_not_an_assertion`, `test_guard_survives_python_dash_O`. The `-O` probe reports `stdout='NOT RAISED'`, exit 1 — so AC-4's subprocess test genuinely exercises the guard rather than passing on any raise.

The two AC-5a single-source tests and the AC-6 test correctly do **not** fail under this mutant: they patch the helper or exercise a different code path. Recorded so a reader does not read their survival as a coverage gap.

### AC-7 — checked as a non-author, from the docstrings alone

Each entry point's docstring carries a `PRECONDITION` paragraph answering both questions without reference to the body: **(a)** passing a connection with an open transaction RAISES `RuntimeError`, stated with the reason (the function commits on the connection it is given); **(b)** for the two that accept it, `conn=None` does NOT raise, named as the owned path. `reclaim_orphan_reference_data`'s says instead that the parameter is required and there is no `None` path, so every call reaches the guard. All three also carry a `Raises:` entry.

`_conn_scope`'s docstring previously described a borrowed connection as restored "non-destructively", which a reader could take as a transaction guarantee. It now states that **"non-destructive" refers to `row_factory` ONLY**, that nothing there prevents a borrowed connection from being committed, and enumerates the three callers that commit on whatever connection they are handed.

### AC-8 — both directions, and the call-site levels were verified not assumed

The docstrings state that the guard stops the destructive path but pages no one. **They do NOT claim a universal about how it is demoted, because no such universal is true** — each entry point has its own demotion picture, derived per docstring from that function's own callers. All four levels checked at source before being written down: `reports_admin.py` **WARNING**, `generate_report` **ERROR**, `cleanup_expired_reports`' internal swallows **WARNING**, and `scripts/reclaim_orphan_reference_data.py` **ERROR plus a non-zero process exit code** — the fourth site, and the one that shows "demoted to a log line" is false as a general claim: the raise is caught, but its consequence escapes the process. Two sites are exempt rather than demoting, because `conn=None` means the guard cannot fire there at all: `bb report cleanup` (which additionally has **no wrapper at all**, so AC-5's skip is load-bearing rather than tidy) and the app-lifespan reaper in `src/api/main.py`.

**Corrected 2026-07-27 — this paragraph carried the false universal and then refuted it two sentences later.** It said *"every wired call site demotes the raise"* and then noted the CLI has no wrapper at all. **A self-contradiction inside one paragraph, which nobody read as one because each half is true in isolation.** Fourth site carrying that universal; the others were AC-8, epic Goal 3 and epic TN-9. **The restricted quantifier is now used in all four**, and the CLI is exempt because `conn=None` means the guard cannot fire there — not because it demotes.

### AC-6b — confirmed at the file, not from the report

Verified by reading `src/reports/lifecycle.py` rather than trusting the round-1 report of it: **`"normally active"` appears nowhere in the module.** The current comment opens `UNREACHABLE TODAY, and kept deliberately on a stated basis -- the same treatment as the vacuous clause in _TEAM_STAT_EXISTS above`, then gives why it cannot fire (a transaction is **NECESSARILY** active — `BEGIN IMMEDIATE` sits outside the `try`, and a failed gate `SELECT` diverts to the `except` handler) and why it is kept regardless.

Recorded because a later review round asked me to check this and was reading the round-1 report, where the hedge still existed. **The report was stale; the file was not.** That is the file-wins rule applied to my own reporting — and it is the second time in this story that an item read as outstanding in the record while being closed in the work.

### AC-6 — modelled, per the story's own instruction

The precondition is modelled (an internal step ends the transaction, then raises) rather than chasing a genuine `SQLITE_FULL`. The fix is `if conn.in_transaction:` around the rollback. Pinned by `test_rollback_handler_propagates_the_original_failure`, which asserts the propagated exception **is the original object** (`excinfo.value is original`) rather than merely matching a message.

### TN-9's two caller enumerations are kept SEPARATE

The measurement above is **cleanup-specific** and is the only one bearing on AC-2.1. `cr`'s wider enumeration covers callers of `reclaim_orphan_reference_data` and `reap_stale_generating_reports` — a different call graph. Both are accurate; merging them into a mutually-corroborating claim is the shape TN-9 exists to prevent, and this report does not.

### Verification

```
cd /tmp/.worktrees/baseball-crawl-E-277 && PYTHONPATH=/tmp/.worktrees/baseball-crawl-E-277 \
  timeout 900 python3 -m pytest tests/ -q -p no:cacheprovider > <scratchpad>/s02.txt 2>&1
```
```
4290 passed, 1 warning in 93.77s (0:01:33)
```
Exit code `0`. Count is **4290**, up 11 from story 01's 4279 — the eleven tests added here account for the delta exactly.

`ruff check` on the two modified files: **2 findings, byte-identical to the staged story-01 baseline** (both pre-existing `F841`), verified by running ruff against `git show :<file>` for each. None introduced.

### Behavioral Changes

1. **All three entry points now RAISE `RuntimeError` on a borrowed connection with an open transaction**, where they previously committed it and exposed the caller's work to deletion. No live caller is affected — all measured clean above.
2. **`bb report cleanup` and the app-startup reaper are explicitly unaffected**: `conn=None` skips the guard by design.
3. **`reclaim_orphan_reference_data` no longer replaces a real failure with a rollback error** when SQLite has already auto-rolled back. Callers inspecting the exception type/message now see the true cause; the logged traceback already contained it.
4. **No change to reap commit semantics on the owned path, to the reap-then-gate concurrency guard, or to any deletion behaviour.** No schema, migration, CLI or API surface change.

---

Blocked by E-277-01 only to fix execution order on the shared module and test file — there is no logical dependency between the keep-root and this guard.
