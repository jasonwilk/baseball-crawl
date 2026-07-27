# E-277-03: Pin the chunking path with a non-vacuous test; correct its docstring

## Epic
[E-277: Reclamation Follow-Up Repairs](epic.md)

## Status
`DONE`

## Description
After this story is complete, the reclamation sweep's chunked-delete path is covered by a test that FAILS if chunking is removed, and the `_RECLAIM_CHUNK` docstring no longer cites a build-specific variable limit as though it were universal. Today no test exercises the path at all, and the obvious test would pass with chunking deleted.

## Description of the trap
Read epic Technical Notes TN-8 before writing anything. The obvious version of this test — seed enough orphans to cross two chunk boundaries, assert they all get deleted — **passes identically with chunking removed**, because this build's SQLite variable limit is 250,000 rather than the 999 the module's docstrings cite (more than one site cites it — see AC-7a). A test that goes green against the mutant it exists to catch is worse than no test, because it also reports that the path is covered.

## Context
Data-engineer verified with a positive control that neither `_RECLAIM_CHUNK` nor `_delete_where_in` appears in any test file, while `reclaim_orphan_reference_data` resolves in three — so the absence is real, not a search artifact.

This is not an edge case. The constant's docstring cites a live backlog of 681 teams and 14,326 players, so for players the chunked path is the ordinary path. The failure mode is quiet: a boundary off-by-one under-deletes rather than erroring, then surfaces at the pass's fixed-point self-assert as a `RuntimeError` rolling back the whole sweep — a confusing failure far from its cause.

## Acceptance Criteria
- [x] **AC-1**: A test exercises the chunking path through the real `reclaim_orphan_reference_data` pass with an orphan-player set spanning more than two `_RECLAIM_CHUNK` chunks, and asserts every orphan is deleted with `ReclaimResult.players_deleted` equal to the seeded count.
- [x] **AC-2**: The test connection lowers its variable limit via `conn.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, ...)` before the pass is invoked. This is REQUIRED, not incidental — per epic Technical Notes TN-8, without it the test passes identically with chunking removed.
- [x] **AC-2.1 (strengthened 2026-07-27 — the earlier two-way coupling was insufficient)**: The lowered limit is not a bare literal disconnected from `_RECLAIM_CHUNK`, and **the test ASSERTS the three-way invariant. ⚠ The invariant is NECESSARY BUT NOT SUFFICIENT for discrimination — see AC-2.1c; this headline previously claimed it "is what actually makes it discriminate", which over-claims and was falsified by execution:**

      `_RECLAIM_CHUNK  <=  limit  <  seeded_count`

  with a failure message naming all three values. **Both inequalities are load-bearing and they fail in opposite directions**: the left one keeps the chunking-INTACT arm passing (every chunked statement must fit under the limit), the right one is the only thing that makes the chunking-REMOVED arm raise (a single statement must EXCEED the limit). Break either and the test stops discriminating **while still reporting success**.
  - **AC-2.1a — the limit is INCLUSIVE. The raise boundary is `limit + 1`, not `limit`.** 999 variables at limit 999 executes fine; 1000 raises `too many SQL variables`. **Provenance: measured by `cr2` and relayed; PM did NOT re-derive it and has no tool to.** Recorded so nobody re-derives it, and so the strict `<` in the invariant is not "corrected" to `<=`.
    - **PM4 verified 2026-07-27 that the INVARIANT AS WRITTEN correctly encodes this boundary — the arithmetic, which needs no tool:** with `_RECLAIM_CHUNK = 900` and `limit = 999`, the strict `limit < seeded_count` forces `seeded_count >= 1000`, which is exactly the first value that raises under the inclusive limit. **And it excludes the dead band by construction:** any seed in 901–999 fails `limit < seeded_count` and is rejected before it can produce a test that passes under both arms. So the invariant does not merely describe the boundary, it is unsatisfiable inside the band. **No change needed; recorded as an explicit "no change needed" verdict rather than left silent**, per story 01 AC-9b.
    - **CONFIRMED by `cr3` 2026-07-27, which challenged it on request — and its general form is stronger than the instance I derived, so I am stating its version.** I showed the exclusion at `limit=999`. **`cr3` showed it holds for ANY admissible limit: for any `C <= limit < seed`, the intact arm binds at most `C <= limit` and passes, while the removed arm binds `seed > limit` and raises.** So the invariant discriminates at **every** admissible limit, not only the current one. **That difference is load-bearing rather than cosmetic**: AC-2.1 exists precisely so that a future change to `_RECLAIM_CHUNK` cannot silently re-open the dead band, and a property demonstrated at one value would not have delivered that. A property that holds across the whole admissible range does. **I asked for this claim to be challenged specifically because it looked obvious — and "obvious" is where this epic has repeatedly shipped defects.**
    - **`cr3`'s proof is cleaner than mine and replaces it: the dead band is `C < seed <= limit`, the invariant demands `limit < seed`. They are DIRECTLY CONTRADICTORY, so the exclusion is limit-INDEPENDENT by construction** — no arithmetic at any particular limit is needed. **My verdict was right and my stated REASON was narrower than my own conclusion**: I demonstrated at 999 and concluded generally. That gap is the shape this epic keeps recording — a correct conclusion resting on a reason that does not carry it — **so it is corrected here even though nothing downstream changes**, because the next reader inherits the reason, not the verdict.
    - **⚠ And note what this axis does NOT cover.** The invariant is genuinely non-decorative *on the dead-band axis*. **It is decorative on two others** — evaluated at the wrong time (AC-2.1b) and expressed over the wrong quantity (AC-2.1c). **Three separate questions about one clause; passing one says nothing about the other two.**
    - **PROVENANCE — CURRENT STATE as of 2026-07-27, after `cr3`'s pre-implementation audit. Everything this AC rests on is now ESTABLISHED BY EXECUTION, by two parties independently.**
      - **The inclusive boundary**: default `SQLITE_LIMIT_VARIABLE_NUMBER` = 250,000, `setlimit(999)` applies, **998/999 execute and 1000/1001 raise.** Measured by `cr2`, **re-derived independently by `cr3`.** Two runs, two parties.
      - **The dead band — now MEASURED, previously reasoning.** Through the real pass at `C=900`, `limit=999`, removed-arm by monkeypatching `_RECLAIM_CHUNK` to `seed+1`: seeds **901, 950 and 999 all pass under BOTH arms; 1000 raises on the removed arm and discriminates.** Raw boundary on the same connection: **998 executes · 999 executes · 1000 raises · 1001 raises.** `cr3`. This was the half `cr2` explicitly graded as reasoning-from-the-boundary rather than observation.
        - **⚠ ESTABLISHED FOR ONE FIXTURE SHAPE ONLY, and the bound is mine to have missed.** `cr3` ran these against an **all-orphan fixture** — orphan set equals seeded count. **I first recorded them as ESTABLISHED with no condition attached, which over-generalises them**, and `cr3` supplied the bound when it delivered the numbers. **Under a MIXED fixture the band is entered at different seed values**, because what enters the band is the bound count, not the seeded count. **That is precisely the S03-6 condition** — so these numbers and AC-2.1c are the same fact seen from two sides, and quoting the seed values without the fixture shape would reintroduce S03-6 through the provenance mark.
      - **The four-cell matrix — NOW RUN, against the real pass, seed 1801, synthetic DB from `migrations/`.** default/INTACT pass · default/REMOVED **pass** · `setlimit(999)`/INTACT pass · `setlimit(999)`/REMOVED **raises `too many SQL variables`**. Reproduces TN-8 cell-for-cell. `cr3`.
      - **`cr3` also established SE's "nothing else in the pass binds >999 parameters"** — cell C ran the whole real pass at limit 999 intact; any other materialized `IN` would have raised. **Scoped honestly by `cr3`: its fixture seeded orphan players only, so this is established for the PLAYER-TIER path.**
    - **⚰ TOMBSTONE — the prior provenance state, retired 2026-07-27, kept because the promotion is the point of having had a split.** It read: *"**ASSERTED, NOT EXECUTED**: that a seed of 901–999 passes under BOTH arms … **AND THE FOUR-CELL MATRIX HAS NOT BEEN RUN AT ALL** — `cr2` states it cannot be, because it needs this story's test to exist first. **So no one has yet observed a chunking-removed arm raise.**"* **All three are now false, and that is the good outcome.** `cr2` could not run the matrix because it needs the test to exist; `cr3` ran it against the real pass instead. **The bottom-right cell — chunking removed, limit lowered, raises — had never been observed by anyone in this dispatch until now, and it is the single cell the entire story exists to protect.**
      - **Why annotate rather than overwrite, since `cr3` explicitly left this call to me.** The *current* state is a CRITERION: an implementer must know what it may rely on and what it must re-derive, so leaving a stale "not run" would make it under-trust a measured result. The *prior* state is EVIDENCE: it records that this story's central premise was inherited for most of the epic and was only measured at the last moment before dispatch. **Both readings were defensible; taking both costs four lines.**
    - **⚠ The 1000 figure is still `cr2`'s measurement, inherited and not executed by PM — but AC-3 is where it gets CHECKED MECHANICALLY, and that is why AC-3 is load-bearing rather than belt-and-braces.** AC-3 asserts a single unchunked `IN (...)` binding the full id set RAISES under the lowered limit. **If the inclusivity assumption were wrong in either direction, AC-3's assertion fails and the story stops.** So the implementer does not need to re-derive the boundary by hand: write AC-3 and the suite re-derives it. Do NOT drop AC-3 as redundant with AC-2.1 — it is the only executable check on a figure that reached this story by relay.
  - **The dead band this closes, stated because the AC it replaces looked correct.** At limit 999 with `_RECLAIM_CHUNK = 900`, **a seed of 901–999 passes under BOTH arms** — intact, every statement is ≤900; removed, the single statement is ≤999 and does not raise. `2C+1` at `C = 900` gives 1801 and is safe **today**, but the derivation only stays clear of the band while `C >= 500`: at `C = 499`, `2C+1 = 999`, inside it. **So a future lowering of `_RECLAIM_CHUNK` would make this test vacuous with no AC violated, no assertion failing, and the suite green.** PM verified this arithmetic; the 250,000 default and the inclusive boundary are `cr2`'s measurements.
  - **Why the invariant rather than a pinned number.** "Seed ≥ 1000" would be true of the value checked and false of the reachable range — the epic's signature shape, in an instrument that reports success either way. The invariant is a PROPERTY and converts silent vacuity into a legible failure at the moment a future constant change breaks it. Per epic TN-15, action-shaped vs property-shaped.
  - **AC-2.1b (added 2026-07-27, `cr3` S03-1 — BINDING, and this is the most important clause in the story): the invariant MUST be asserted against the SEED-TIME CAPTURED `_RECLAIM_CHUNK`, not against the live module global.** Capture the value once, at seed time, and assert on the captured value — or evaluate the invariant before any mutation occurs.
    - **Why, and it is this story's own defect re-entering through its own fix.** The Technical Approach records that AC-2.1 exists because TWO quantities couple to `_RECLAIM_CHUNK` and the original ACs protected only one. **AC-2.1 then introduced a THIRD — its own assertion — and did not inherit AC-5's protection.** AC-5 shields the seed derivation from re-evaluating under AC-4's mutation; until now nothing said when the invariant is evaluated, and the invariant *names* `_RECLAIM_CHUNK`, so the literal reading reads the global that AC-4 mutates to `seeded+1`.
    - **EXECUTED by `cr3`, both readings, against the real pass.** Invariant read LIVE → the mutated arm fails `AssertionError: _RECLAIM_CHUNK=1802, limit=999, seeded=1801`. Invariant read from the SEED-TIME captured value → the mutated arm fails `sqlite3.OperationalError: too many SQL variables`.
    - **The consequence is exactly what this story exists to prevent. AC-4 asks only that the test "FAIL" when chunking is removed — and the live reading DOES fail.** So every AC goes green, the mutation demonstration is dutifully recorded in Notes, **and the test discriminates nothing.** A vacuous chunking test, shipped through the ACs written to make a chunking test non-vacuous. **AC-4's S03-2 clause is the backstop that makes this self-detecting; both are required, neither alone is sufficient.**
  - **AC-2.1c (added 2026-07-27, `cr3` S03-6 — BINDING. The invariant must be expressed over the count the pass will ACTUALLY BIND, not over `seeded_count`.)** Assert the three-way invariant against **`len(orphan_player_ids)`** — the id set the pass materializes and binds — not against the number of rows seeded.
    - **Why: they are not the same quantity, and they coincide only by AC-1's separate grace.** AC-2.1 as written constrains `seeded_count`. What determines whether the chunking-REMOVED arm raises is the size of the set actually bound in one statement. Those are equal **only because AC-1 independently forces `players_deleted == the seeded count`** — a coupling AC-2.1 never states and a future editor could break from AC-1's side without ever opening AC-2.1.
    - **EXECUTED by `cr3` — same invariant, satisfied identically, two fixtures, real pass:**

      | fixture | invariant `900 <= 999 < 1801` | real orphan set | INTACT | REMOVED |
      |---|---|---|---|---|
      | 1801 orphans, 0 kept | **True** | 1801 | pass | **raises** |
      | 950 orphans + 851 kept | **True** | 950 | pass | **pass** |

      **Row two is the finding: invariant green, test vacuous.** The real bind count (950) sits inside the very dead band the invariant exists to exclude.
    - **METHOD, so row two cannot be dismissed as contrived** (`cr3`, supplied as it drained). Synthetic DB from `migrations/` via `tests.conftest.load_real_schema`. **The 851 "kept" players were anchored by `plays.batter_id` rows — one of the reachability edges `_orphan_player_ids` actually tests — so they are legitimately non-orphans, not a construction.** Both arms ran the real pass end to end. **This matters because the obvious rebuttal to row two is "that fixture is artificial," and it is not: it is a shape the production predicate genuinely produces.**
    - **⚠ PROVENANCE BOUND ON THIS MATRIX, volunteered by `cr3` about its own headline evidence.** Measured **~04:10Z** against the then-current worktree. **`src/reports/lifecycle.py` moved at `04:20:14` and `cr3` did NOT re-run this matrix afterwards** — it re-derived `_TEAM_BASE_PRED` post-movement and found the root set unchanged, but that is a different check. **Its own scoping of the residual risk: the mechanism depends on `_orphan_player_ids`' reachability edges and `_delete_where_in`'s chunking, neither of which is what moved.** Recorded because nobody would have known to ask for it, and it was offered while `cr3` believed it was making a closing argument.
      - **✅ RESOLVED by `se`, which owns the move `cr3` was bounding against — the matrix is NOT stale.** The `04:20:14` mtime is E-277-03's own edit, and `git diff -- src/reports/lifecycle.py` shows **three hunks, all docstring prose, ZERO executable lines changed**: `_RECLAIM_CHUNK = 900`'s assignment untouched (only its docstring grew), `_delete_where_in`'s `for start in range(0, len(ids), _RECLAIM_CHUNK)` **byte-identical**, `_orphan_team_ids`' SQL and predicate composition untouched, and **`_TEAM_BASE_PRED` not in the diff at all.** So nothing executable changed between `cr3`'s measurement and now, and **its own post-movement re-derivation finding the root set unchanged now has a MECHANISM rather than being a coincidence.**
      - **Why `cr3`'s caution is KEPT rather than deleted now that it is resolved.** The bound is a record of *what `cr3` did and did not re-run* — **evidence**, and the most creditable act of the night, volunteered at the moment of maximum incentive to omit it. What would have been wrong is leaving a reader to **infer staleness that did not occur**; that inference is the **criterion**, and it is the part `se`'s fact corrects. **Preserve the disclosure, remove the false implication** — the same cut this epic has applied to every tombstone.
    - **This is the SECOND, INDEPENDENT way this one AC goes decorative, and neither subsumes the other. AC-2.1b is the wrong TIME (evaluated under mutation); AC-2.1c is the wrong QUANTITY. Closing one leaves the other wide open.** Both sit inside the clause written to close the signature defect — *true of the fixture shape checked (every seeded player an orphan), false of the reachable fixture space.*
    - **Why the count and not a coupling note**, which `cr3` offered as the alternative and advised against: a note recording that AC-2.1 depends on AC-1's equality **leaves the coupling breakable from AC-1's side by someone who never reads this AC.** Binding the invariant to the quantity that physically matters removes the coupling instead of documenting it.
- [x] **AC-3**: The test asserts its own precondition: that a single unchunked `IN (...)` binding the full id set raises `sqlite3.OperationalError` under the lowered limit — **run on the SAME connection the pass will use** (`cr3` S03-5; AC-2's "the test connection" implied it, now stated). This is what makes AC-2 self-verifying rather than silently load-bearing.
  - **Two things `cr3` measured here that pre-empt a plausible worry**: on the pass's own connection, both a `SELECT`-form and a `DELETE`-form probe binding all 1801 ids raise `OperationalError` and **both leave `in_transaction == False`**, and the pass afterwards still completes (1801 deleted). **`cr3` hypothesised a collision between this probe and story 02's dirty-connection guard and found there is none** — the probe does not leave the connection dirty, so the guard does not fire. Recorded so nobody re-derives it.
- [x] **AC-4**: The test FAILS when chunking is removed, demonstrated by the mutation protocol below. **The seeded count is captured BEFORE any mutation** and does not move with the constant. Record the observed failure in the story's Notes.
  - **Protocol (required — the naive version is unsatisfiable, see Technical Approach)**: materialize the orphan id set from the PRE-mutation value of `_RECLAIM_CHUNK`, then monkeypatch the module attribute `src.reports.lifecycle._RECLAIM_CHUNK` above the seeded count. `_delete_where_in` reads the module global at call time, so patching after seeding does take effect. An equivalent alternative is to patch `_delete_where_in` with a single-statement version that binds the whole id set at once; state in Notes which was used.
  - **AC-4a (added 2026-07-27, `cr3` S03-2 — the failure MODE is pinned, not just the fact of failure).** The recorded failure MUST be `sqlite3.OperationalError` matching **`too many SQL variables`**. A bare "the test fails" is not sufficient evidence that chunking was load-bearing.
    - **This is the backstop that makes AC-2.1b self-detecting.** With the mode pinned, S03-1's wrong-reason failure — an `AssertionError` about lost discrimination — **cannot satisfy AC-4 even if a future edit leaves the invariant reading the live global.** The two clauses are independent defences against one defect: AC-2.1b prevents it, AC-4a detects it. **Do not drop either as redundant with the other.**
    - **The literal form, supplied by `cr3` so the matcher cannot drift weaker:**

      ```python
      with pytest.raises(sqlite3.OperationalError, match="too many SQL variables"):
      ```

      **The `match=` is load-bearing, not decoration** — a bare `pytest.raises(sqlite3.OperationalError)` would also be satisfied by an unrelated `no such table`. `match=` is `re.search` over `str(exc)`, and the measured message contains **no regex metacharacters**, so the bare string is safe as written and needs no escaping. **The discrimination this buys, stated so nobody trims it:** S03-1's wrong-reason failure raises `AssertionError` and the pass's fixed-point failure raises `RuntimeError` — **neither can satisfy this matcher.**
  - **AC-4b (`cr3` C5 — mechanism note, one line).** `monkeypatch.setattr` defaults to `raising=True`, so it aborts loudly if the anchor attribute is absent — which satisfies the mutation-probe practice (*a mutation that never landed reports the same green as one that survived*) with no extra AC text. **But a bare `setattr(lifecycle, "_RECLAIM_CHUNK", N)` would NOT abort** — it would silently create a new attribute and the probe would report a meaningless green. **Use `monkeypatch.setattr`.**
- [x] **AC-5**: The seeded count is derived from `_RECLAIM_CHUNK` rather than hardcoded, is not an exact multiple of it, **and satisfies AC-2.1's invariant.** **This derivation is evaluated once, at seed time**; AC-4's mutation must not re-evaluate it, or the seed grows with the constant and chunking never disengages. **The derivation alone is NOT sufficient** — a formula can be correctly derived, correctly evaluated once, and still land inside the dead band AC-2.1 describes. **The arithmetic is the mechanism; the invariant is the requirement.** Where they disagree, the invariant governs and the formula changes.
  - **AC-5a (added 2026-07-27, `cr3` S03-4 — the JOINT region, because AC-1 and AC-2.1 constrain the seed together and no AC said so).** The seed must satisfy **both** ACs simultaneously:

        C <= limit    AND    seed > max(2C, limit)

    At `C=900, limit=999` that is **`seed >= 1801`** — and the story's own suggestion of 1801 sits **exactly on the boundary with zero margin.**
    - **The clause immediately above is what makes this reachable, so it is corrected rather than left standing.** *"Where they disagree, the invariant governs and the formula changes"* could land an implementer at `seed=1000, limit=999`. That **satisfies AC-2.1 and genuinely discriminates** — `cr3` measured it — **but yields two chunks (900+100) and violates AC-1's "more than two chunks."** The invariant governs over the *formula*, **never over AC-1.** A seed that discriminates but produces two chunks is a failed AC-1, not a permitted trade.
    - **Restated as the rule to apply: satisfy AC-1 and AC-2.1 together, then let the formula fall out** — not the reverse.
- [x] **AC-6**: After the pass completes, `count_orphan_reference_data` reports zero remaining orphans — the fixed-point self-assert is satisfied rather than bypassed.
- [x] **AC-7**: **Every** site in `src/reports/lifecycle.py` citing the variable limit as a fixed number is corrected — not only the `_RECLAIM_CHUNK` docstring. Each describes the limit as build-dependent and, where it explains the choice, says why 900 is safe across builds.
  - **AC-7a (binding)**: the list of such sites is regenerated **by search against the module** — searching for the figure itself — and NOT taken from this story, the epic, or any review finding. Record what was searched and what was found in Notes. An AC that checks a handed-down list inherits that list's fallibility and stops being a sweep.
  - **AC-7b**: the site a reader lands on when asking whether chunking is needed at all is corrected along with the rest. A surviving "999-safe"-style claim on the delete helper defeats the purpose of correcting the constant's own docstring.

## Technical Approach
Data-engineer's four-cell matrix (epic TN-8) is the evidence behind AC-2 and AC-3. On AC-3 specifically, they argued against dropping it as belt-and-braces, and the argument is worth repeating: without it, the test's validity rests silently on `setlimit` having taken effect. If someone deletes that line, or a future runtime makes it a no-op, the row-count assertion goes green again and the test is back to testing nothing — the exact failure being fixed, re-entered through the fix.

Data-engineer suggested 1,801 orphan players (two full 900-chunks plus one), which satisfies AC-5 at the current chunk size; AC-5 asks for that relationship expressed in terms of the constant so the test keeps testing what it claims.

**AC-4 and AC-5 were jointly unsatisfiable in an earlier draft, and AC-4's protocol exists to resolve it.** AC-5 requires the seed derive from `_RECLAIM_CHUNK` (say `2 * _RECLAIM_CHUNK + 1`); the old AC-4 required demonstrating failure by "raising `_RECLAIM_CHUNK` beyond the seeded set size." If the seed expression re-evaluates against the mutated constant, raising it to `C'` raises the seed to `2C' + 1` — which exceeds `C'` for every `C'`, so chunking always still engages, nothing raises, and the mutant the test exists to catch can never be demonstrated. Capturing the seed before mutating is what makes both ACs hold at once.

**Why lowering the limit is safe (software-engineer).** Nothing in the pass binds more than 999 parameters outside `_delete_where_in` — the orphan producers use correlated `NOT EXISTS` with zero bound parameters — so lowering the connection's limit exercises the chunker and nothing else. Worth a line in the test: if a later change materializes an `IN` list elsewhere in the pass, this test starts failing, and that should read as the test working rather than as a flaky fixture.

**AC-2.1 closes a coupling gap data-engineer found in review.** TWO quantities in this test couple to `_RECLAIM_CHUNK` — the seed count and the lowered variable limit — and the original ACs protected only the first. The lowered limit must EXCEED the chunk size (900 against 999 today, 99 of headroom). If a later change raises `_RECLAIM_CHUNK` past the hardcoded limit, the chunking-INTACT path starts raising `too many SQL variables`, and **the failure presents as a chunking bug rather than a test-configuration problem** — costing whoever hits it a debugging session on the wrong code. Expressing the relationship, or asserting it with a message that names it, is what makes the failure self-explaining.

For AC-7: **do not simply replace 999 with 250000.** That figure is build-specific, would rot on the next image rebuild, and worse, would imply chunking at 900 is unnecessary. The accurate statement is that the limit is build-dependent — 999 was SQLite's default before 3.32.0, 32,766 from 3.32.0, and 250,000 on this build — and that 900 is chosen to be safe under the most conservative of those.

**Why AC-7 is in this story rather than treated as a tidy-up.** The false premise is load-bearing for whether the code should exist at all: a reader who checks `getlimit()` on this build, sees 250,000 against a docstring citing 999, and concludes the chunking is dead code would be wrong, because the production container's SQLite is not necessarily this one. That is the same defect class as the MAJOR-2 comment in story 01 — a false rationale guarding a live guard. Data-engineer initially argued it should therefore be grouped with story 01 by defect class, and **conceded the placement on review** — agreeing that the implementer who has just measured the limit for AC-2 is the one holding the context needed to describe a build-dependent limit correctly. Their substantive requirement survives in full as AC-7; only the location was at issue, and it is settled. Recorded rather than dropped so the reasoning survives for whoever revisits this.

Seed through canonical entry points where practical — a fixture that cannot occur in production pins nothing. Watch runtime: if the test becomes slow enough to discourage running the suite, say so rather than trimming the count below the boundary, which would defeat AC-5 while appearing to pass.

Constraints: synthetic DBs from `migrations/` only; never touch `data/app.db`; no `bb` commands.

## Dependencies
- **Blocked by**: E-277-02
- **Blocks**: None

## Files to Create or Modify
- `src/reports/lifecycle.py`
- `tests/test_orphan_reclamation.py`

## Agent Hint
software-engineer

## Definition of Done
- [x] All acceptance criteria pass
- [x] Tests written and passing
- [x] Code follows project style (see CLAUDE.md)
- [x] No regressions in existing tests

## PM AC Verdict — FINAL (2026-07-27, PM4)

**ALL ACs PASS.** Enumerated individually, never spanned: **AC-1, AC-2, AC-2.1, AC-2.1a, AC-2.1b, AC-2.1c, AC-3, AC-4, AC-4a, AC-4b, AC-5, AC-5a, AC-6, AC-7, AC-7a, AC-7b.** Sixteen named.

**`cr4` reviewed independently across two rounds and closed APPROVED, final — zero MUST FIX at any point.** Its verdict is valid against the delivered state: both code files match its round-2 bracket exactly. **Neither of us saw the other's reasoning before ruling** — the lead quarantined my verdict until `cr4` reported, on the ground that two approvals anchored on each other are one approval.

### AC-5a — the deviation, adjudicated rather than inherited

`se` did not use the spec's `seed=1801`. It derived **`limit = 2C`, `seed = 2C + C//2`**. I checked the algebra, not the claim: `C <= 2C` holds; `max(2C, limit) = 2C`; `2C + C//2 > 2C` ⟺ `C >= 2`. At C=900 that is limit 1800, seed 2250, `ceil(2250/900) = 3` chunks, not an exact multiple.

**PERMITTED, and better than the spec.** AC-5a called its own suggestion *"exactly on the boundary with zero margin"* — 1801 clears `2C` by **one**. `se`'s clears it by **`C//2`**, 450 at the current constant, **and the margin SCALES with the constant.** That is the durability property AC-2.1 exists to deliver, and a margin of one does not deliver it. **There was no deviation to forgive; the spec's number was the weaker choice.**

### AC-2.1b and AC-2.1c — enforced structurally, not observed conventionally

**AC-2.1b**: `chunk` is captured in `_seed_chunking_fixture` and passed to `_assert_chunking_fixture` **as a parameter**. The assertion cannot re-read the mutated global — **the signature makes the wrong thing impossible**, which is a stronger result than an implementer following a convention.

**AC-2.1c**: the invariant's third term is `len(orphan_ids)` from `_orphan_player_ids`, never `seeded`; and `len(orphan_ids) == seeded` is asserted **separately**, so the all-orphan property is written down rather than assumed. **`cr3`'s 1801-seeded/950-orphan counter-example trips that separate assertion first.**

**The two are independent, as the clauses required**: 2.1b is enforced by the parameter, 2.1c by the choice of term. Neither closes the other.

### ⚠ AC-1 — a SPEC finding, found by `cr4`, with its bounds

**`ReclaimResult.players_deleted` is assigned `len(player_ids)` at `src/reports/lifecycle.py:1508` — the COMPUTED set size, not rows affected.** So AC-1's `players_deleted == seeded` **cannot fail on an under-delete**, which is the boundary off-by-one this story exists to pin. PM verified the assignment line directly.

**THREE BOUNDS, all binding, all `cr4`'s:**

1. **This is vacuity against UNDER-DELETE SPECIFICALLY — not general vacuity, and not a claim the assertion is worthless.** It pins the pass's accounting, which is a real thing to pin.
2. **⛔ `players_deleted` being a set size is PRE-EXISTING behaviour, untouched by this story. NOBODY MAY CITE THIS NOTE AS AUTHORITY FOR CHANGING IT TO A ROWCOUNT.** That is a behaviour change to a shipped return value, outside E-277-03, needing its own justification. **This note is exactly the kind of artifact that acquires authority its author never claimed, so the limit is stated rather than assumed.**
3. **The actionable half is narrow and is the sentence to keep:** `se`'s `SELECT COUNT(*) FROM players == 0` and AC-6's `count_orphan_reference_data(conn) == OrphanCounts(0,0,0)` are **STRONGER than the criterion they satisfy**, so neither is redundant and **neither may be tidied away as covered by AC-1.**

**Why the deletion is unattractive rather than merely forbidden — this enumeration and this framing are PM4's, NOT `cr4`'s, and the line is drawn because the paragraph above it is labelled "all `cr4`'s" and adjacency carries attribution.** `cr4`'s finding is bound 3 above: the two assertions are stronger than the criterion they satisfy. **The four-instrument enumeration below, and the choice to make the deletion unattractive rather than forbidden, are mine.** A do-not-delete label invites the question; a mechanism answers it. **Four instruments exist and only one is vacuous:** AC-1's equality; `se`'s external row count; AC-6's independent producer; and the pass's own Step-7 zero-delta self-assert, which raises regardless of what any test asserts. **Deleting the test's own two because "AC-1 covers it" leaves the test relying on the implementation to police itself** — it would still go green if Step 7 were ever weakened, and it would no longer be the thing that notices. **That argument survives a reader who knows about Step 7.**

**Provenance of the finding, because the remedy matters more than the credit.** `cr4` did not find this by reading AC-1 harder. It came to `reclaim_orphan_reference_data` **for an unrelated reason** — closing the "nothing else binds per-id" enumeration — and the assignment line was simply there. **In its words: *"Read it more carefully" is not a reproducible remedy. "Have a non-author read the code for a different reason" is.*** Three parties read AC-1 — `cr3` who authored it, PM who verified it at the primary by its anchors, and `cr4` who had no stake. **The third found it**, and PM's own miss was precise: **I confirmed the AC's assertions were present and correct, and never asked whether the quantity it names is CAPABLE of failing.**

### `ReclaimResult`'s docstring — declined for scope, captured with a trigger

`lifecycle.py:1196-1197` says those fields *"count the rows removed."* **They do not.** Declined for scope; **filed as an idea with an explicit fold-in trigger** (below).

**`feedback_no_preexisting_excuse` — *"if something is wrong, fix it; 'pre-existing' is not a valid reason to skip"* — was in play and is NAMED here rather than passed over.** Raised by `cr4`. **Why it does not govern:** the operator issued a **more specific and more recent ruling on this same file** — TN-6's pin enumerations, declined, with *"do not fix it opportunistically"* attached — and **a specific ruling on the actual file outranks a general preference.** **And the preference is discharged by CAPTURE, not only by FIX**, which is what makes an idea-with-a-trigger a discharge rather than a dodge. Recorded because **a decision that silently steps over an operator preference reads as an oversight when someone later finds the preference.**

**The decline's own justification, stated so it is not read as a consolation:** *a recorded finding whose cause is left live is misleading only if the record omits the cause.* The cause is named above, so nothing is left to mislead — which is why not fixing it is a complete answer rather than a deferral.

### PROVENANCE

- **PM read directly**: `_seed_chunking_fixture` and `_assert_chunking_fixture` in full; both chunking tests; `players_deleted` at `:1508`, `teams_deleted` at `:1500`, `roster_rows_deleted` at `:1485` **and its PRE-delete comment at `:1484`**; the AC-7 sites at `:936-939`, `:1258` and `_delete_where_in`'s docstring.
- **Taken from `cr4`, NOT re-derived**: its round-2 confirmation; **AC-7a's sweep, which it REBUILT rather than confirmed — 3 / 0 / 4 / 5 / 35, matching, including `se`'s self-corrected 35.** That discharges the gap PM named rather than duplicating PM's check. **Two parties confirming a list is not one party rebuilding it.**
- **Taken from `se`, NOT re-derived**: `310 passed`, ruff parity, the mutation record.
- **NOT VERIFIED BY ANYONE, and recorded as DEFERRED rather than as a hole**: the pytest results. `cr4` declined under its Test Execution Constraint and said so. **The full suite runs at closure in the main checkout where it is authoritative, and that gate is unconditional.**

### Idea captured — `ReclaimResult` docstring (number globbed at closure)

**Fix the PROSE, not the code** (`cr4`). **Trigger: the next story or epic touching `src/reports/lifecycle.py` docstrings takes it; it needs no epic of its own.** Files alongside IDEA-198 — **same file, same declined-for-scope shape, so the next person opening `lifecycle.py` finds both together.** A third landing there is an argument for a cleanup epic rather than a third idea.

**Two hazards the idea must carry, or it defeats itself:**

1. **⚠ THE PHRASE WRAPS.** `grep -n "count the rows removed"` returns **EMPTY, exit 1** — the text breaks between `count the` (1196) and `rows removed.` (1197); positive control `"rows removed"` hits 1197. **This epic's own S05-3 shape, live, on the exact site the idea sends someone to.** An implementer greps the quoted sentence, finds nothing, and closes the idea as stale. **DISCRIMINATE BY SYMBOL — `ReclaimResult`, line 1193 — never by the sentence.**
2. **⚠ THE THREE FIELDS ARE WRONG IN DIFFERENT WAYS, so a one-word fix is a NEW false claim.** `teams_deleted` and `players_deleted` are **computed set sizes**; **`roster_rows_deleted` is a real `COUNT(*)` — but taken PRE-delete** (`:1485`, under the comment at `:1484`; PM verified this directly). **So "these are set sizes" is FALSE about the third.** The accurate statement covering all three: **what the pass computed it WOULD remove, not what it did.**

## Notes
**Blocked by E-277-02. The ordering and the dependency direction are CORRECT — do not re-sequence.** ⚠ **The rationale previously given here was FALSE and is corrected (`cr3` S03-3, measured 2026-07-27).** It read: *"Blocked by E-277-02 only to fix execution order on the shared module and test file; **there is no logical dependency**."* **There is one.** Story 02's `_require_clean_connection` raises at the reclamation's entry on a connection carrying an open transaction, so **this story's seed must be COMMITTED before the pass is invoked** — measured: an uncommitted seed leaves `in_transaction == True` and the pass raises `RuntimeError`.

**Risk is LOW and `cr3` checked rather than assumed**: the house idiom already commits (`_add_player` commits per row, and every existing test commits before invoking). So this changes nothing an implementer following the file's conventions would do — **which is exactly why the false sentence was dangerous rather than harmless.** It is a one-sided claim, true of the file-conflict scope it was written about and false of the behavioral surface, **and its function in the file was to license a future reader to reorder or parallelize these two stories.** The sentence is fixed; the dependency stays.

**⚠ Read this as a CONSTRAINT TO PRESERVE, not a change to make** (`cr3`'s addition, so the correction is self-defending). The existing fixture idiom in `tests/test_orphan_reclamation.py` **already commits** — `_add_player` commits per row, and every existing test commits before invoking the pass. **So an implementer following the file's conventions needs to do nothing new here.** Stated explicitly because a correction this emphatic invites the opposite reading — that story 03 must now add something — when what it must do is *not remove* a commit that is already there. Build facts: Python **3.13.13**, SQLite **3.45.1**, default `SQLITE_LIMIT_VARIABLE_NUMBER` **250,000**, `conn.setlimit` available. **RE-MEASURED 2026-07-27 by `cr3` — previously these were "observed during discovery" and inherited from an earlier session, and I had flagged them as such. All three hold.**

**This matters beyond bookkeeping: TN-8's PREMISE is now executed rather than inherited, and so is its CONCLUSION.** TN-8's finding — that the naive test would pass against the mutant it exists to catch — previously rested on *inferring* from the 250,000 figure that a chunking-removed arm would not raise at the default limit. **`cr3`'s four-cell run observed that cell directly: default limit, chunking REMOVED, passes with 1801 deleted.** The vacuity TN-8 predicted has now been seen rather than derived.

---

## Implementation record (software-engineer, 2026-07-27)

Everything below was EXECUTED in this worktree unless a line says otherwise. Where a figure reached this story by relay, it is re-derived here first-hand and both readings are given.

### What was built

`tests/test_orphan_reclamation.py` — one new section, two helpers and two tests:

| symbol | role |
|---|---|
| `_seed_chunking_fixture` | seeds the all-orphan player set, captures `_RECLAIM_CHUNK` at seed time, commits, lowers the connection's variable limit |
| `_assert_chunking_fixture` | asserts the three-way invariant and returns the pass's real orphan id set |
| `test_chunked_player_delete_spans_more_than_two_chunks` | AC-1/2/2.1/3/5/6 — the pass itself |
| `test_chunking_is_load_bearing_removing_it_raises` | AC-4/4a/4b kept as a PERMANENT test, not a one-time write-up |

`src/reports/lifecycle.py` — the three AC-7 docstring sites.

### The parameterization, and why it is not 1801 (AC-5, AC-5a)

Captured once at seed time, all three derived from the same `C`:

    C      = lifecycle._RECLAIM_CHUNK      (900 today)
    limit  = 2 * C                         (1800)
    seeded = 2 * C + C // 2                (2250)

AC-5a's joint region is `C <= limit AND seed > max(2C, limit)`. The story's own suggestion — `limit=999, seed=1801` — satisfies it **with zero margin**, and AC-5a says so. This parameterization instead satisfies it for **every `C >= 2`**, algebraically: `C <= 2C` always; `seed > max(2C, 2C) = 2C` reduces to `C // 2 > 0`; "more than two chunks" is the same condition; and `seeded % C == C // 2 != 0`, so it is never an exact multiple.

**Not left as arithmetic — EXECUTED through the real pass at five chunk sizes**, both arms, synthetic DBs from `migrations/`:

| C | limit | seed | invariant | INTACT arm | REMOVED arm |
|---|---|---|---|---|---|
| 4 | 8 | 10 | True | pass (10 deleted) | **raises `too many SQL variables`** |
| 100 | 200 | 250 | True | pass (250 deleted) | **raises** |
| 499 | 998 | 1247 | True | pass (1247 deleted) | **raises** |
| 900 | 1800 | 2250 | True | pass (2250 deleted) | **raises** |
| 1500 | 3000 | 3750 | True | pass (3750 deleted) | **raises** |

**`C = 499` is in the table on purpose**: it is the value at which the story records that the `2C+1` derivation falls *inside* the dead band (`2C+1 = 999 = limit`). This parameterization is clear of the band there and discriminates. That is the AC-2.1 property — *a future lowering of `_RECLAIM_CHUNK` must not silently re-open the band* — measured rather than argued.

### AC-2.1b and AC-2.1c, as implemented

- **Time (2.1b).** `_seed_chunking_fixture` returns the chunk value it read; `_assert_chunking_fixture` takes it as a PARAMETER and never re-reads the module global. The docstring states why in the imperative ("MUST be the seed-time captured value").
- **Quantity (2.1c).** The invariant is asserted over `len(orphan_ids)` where `orphan_ids = _orphan_player_ids(c)` — the set the pass materializes. `seeded` is checked separately as an equality (`len(orphan_ids) == seeded`), so the all-orphan property is a stated assertion rather than an unwritten assumption. A mixed fixture in the S03-6 shape trips one of the two.

### AC-3 as implemented

`SELECT COUNT(*) ... WHERE player_id IN (<2250 placeholders>)` on the pass's own connection, inside `pytest.raises(sqlite3.OperationalError, match="too many SQL variables")`, followed by `assert not conn.in_transaction`. SELECT rather than DELETE because it is non-destructive and `cr3` measured both forms equivalent for this purpose; the `in_transaction` assertion is written rather than inherited, so story 02's guard cannot start firing here unnoticed.

### AC-4 / AC-4a / AC-4b — the mutation record

**Mechanism used: monkeypatch of the module attribute** (`monkeypatch.setattr(lifecycle, "_RECLAIM_CHUNK", len(orphan_ids) + 1)`), not the `_delete_where_in` replacement alternative.

Three mutants were run against the shipped tests. Each was applied to a scratchpad copy, run, and the file restored and md5-verified byte-identical (`c965edf1ab0bf7d0dedf2c745d5c1b5a` before and after; zero `MUTANT` tokens remain in the tree).

**M1 — chunking removed inside `test_chunked_player_delete_spans_more_than_two_chunks` itself.** This is AC-4's literal requirement: *the* test fails.

```
>           conn.execute(
                f"DELETE FROM {table} WHERE {column} IN ({placeholders})", chunk
            )
E           sqlite3.OperationalError: too many SQL variables

src/reports/lifecycle.py:1356: OperationalError
FAILED tests/test_orphan_reclamation.py::test_chunked_player_delete_spans_more_than_two_chunks - sqlite3.OperationalError: too many SQL variables
1 failed in 0.19s
```

**M2 — the invariant made to read the LIVE global instead of the seed-time capture.** AC-2.1b's failure mode, reproduced against this implementation rather than accepted on relay:

```
E       AssertionError: fixture no longer discriminates: _RECLAIM_CHUNK=2251 (captured at seed time), variable limit=1800, orphan set=2250. ...
E       assert 2251 <= 1800
1 failed in 0.17s
```

Both mutants FAIL, and **only M1 fails in the mode AC-4a pins.** So the two clauses are demonstrated to be independent defences here, not just described as such.

**M3 — the `setlimit` call deleted.** Both tests catch it, which is the failure the Technical Approach warns about (*"the exact failure being fixed, re-entered through the fix"*):

```
FAILED tests/test_orphan_reclamation.py::test_chunked_player_delete_spans_more_than_two_chunks - Failed: DID NOT RAISE <class 'sqlite3.OperationalError'>
FAILED tests/test_orphan_reclamation.py::test_chunking_is_load_bearing_removing_it_raises - Failed: DID NOT RAISE <class 'sqlite3.OperationalError'>
2 failed, 50 deselected in 0.24s
```

**M3's second line is an independent observation worth keeping.** That test's only `pytest.raises` wraps the pass with chunking REMOVED; with `setlimit` gone the connection is back at this build's default and it **did not raise**. That is TN-8's top-right cell — *default limit, chunking removed, passes* — reproduced in **this** fixture rather than in `cr3`'s. TN-8's premise now holds against the artifact that ships.

**Bytecode-cache hygiene, and the honest version is that I took NO explicit step** — no `__pycache__` clear, no `-p no:cacheprovider`, no `PYTHONDONTWRITEBYTECODE`. `.claude/rules/testing.md` requires this be stated, so it is stated rather than quietly satisfied. Why it could not have lied, measured rather than argued:

- **A stale `.pyc` cannot have been used, because every mutant changed the file's SIZE.** CPython's default invalidation is timestamp-mode, and the `.pyc` header records BOTH source mtime and source SIZE. Read from the live cache file (`tests/__pycache__/test_orphan_reclamation.cpython-313-pytest-9.0.3.pyc`): `flags=0`, `source_size=62505`, matching the source on disk. Byte deltas against the 62,505-byte pristine: **M1 `+187`, M2 `+355`, M3 `-26`** — all non-zero, so the size field alone forces recompilation; mtime changed too, since each `cp` rewrote the file.
- **The failure DIRECTIONS are themselves a control.** A stale cache would have executed the PRE-mutation source and produced a PASS. All three produced the predicted FAILURE in the predicted mode — M1 `OperationalError`, M2 `AssertionError`, M3 `Failed: DID NOT RAISE`.
- **The unmutated baseline, stated as what it actually was.** No control was *staged* for this battery. What exists is two ordinary runs that happened to be unmutated: the post-implementation verification run BEFORE any mutation (`2 passed, 50 deselected`) and the post-restore run after the last one (`52 passed`). Between them, each mutant ran red. **That does give a genuine both-directions observation — green → red under M3, then red → green after the restore, on the same file** — which is what a no-mutation control would have been for: a stale cache would have to be simultaneously stale enough to hide M3 and fresh enough to un-hide the restore. **But "the suite was green beforehand" and "I ran a no-mutation control" are different claims, and only the first is what happened.** There was also no green run BETWEEN the mutants — M2 was applied on top of M1, and M3 straight after a restore — so the pattern is green, red, red, red, green, not an alternation.
- **Restore verified by digest, not assertion**: `c965edf1ab0bf7d0dedf2c745d5c1b5a` before and after; `cr4` independently regenerated the same value.

**So: no explicit hygiene step, and the size-change mechanism plus the direction and alternation controls cover it. Recorded as "no step taken, here is why it did not matter" rather than re-run** — a re-run produces a fresh green that says nothing about what the original run executed.

### AC-7a — the sweep, regenerated against the module

Not taken from this story, the epic, or any review finding. Five independent passes over `src/reports/lifecycle.py`:

| pass | pattern | hits before | disposition |
|---|---|---|---|
| A | `999` (bare figure) | 3 | all three corrected |
| B | `250000\|250,000\|32766\|32,766\|SQLITE_LIMIT` | 0 | — |
| C | `variable` (case-insensitive) | 4 | 3 are pass A's; the 4th (a comment about a *Python* variable holding a team id) is not a limit citation |
| D | `limit` (case-insensitive) | 5 | 2 are pass A's; 3 are SQL `LIMIT 1` clauses |
| E | `sqlite\|bound-\|parameter` (case-insensitive) | 35 | type annotations and unrelated prose; no additional limit citation |

Counts are matching LINES, measured with `grep -icE` against the pre-edit file — not eyeballed from the listing. (I first wrote `40` for pass E from the visual listing and the re-measurement returned `35`; recorded because an unexpected count is a cross-check trigger, and here the cross-check was the thing that caught it.)

The three corrected sites: the `_RECLAIM_CHUNK` docstring, the `_orphan_team_ids` docstring, and the `_delete_where_in` docstring. The count agrees with the bound PM recorded in epic TN-15 — that agreement is a **cross-check, not the source**, per AC-7a.

**AC-7b** is the `_delete_where_in` docstring, whose entire body was `(999-safe)`. It now states the build-dependence and the decisive cue inline — *a generous `getlimit()` on the build in front of you is NOT evidence that this chunking is unnecessary* — rather than only pointing at `_RECLAIM_CHUNK`. Per TN-15's low-salience finding, a cue quieter than the misreading it must defeat does not defeat it.

**Single-sourced deliberately.** The full range of documented values (999 pre-3.32.0, 32,766 from 3.32.0, 250,000 on this build) is stated ONCE, on `_RECLAIM_CHUNK`; the other two sites reference it. Three copies of three figures is three places to rot, and story 01's measured finding was that REMOVE beats restate.

**The `900` claim is stated in both directions**, per the safety-comment rule: 900 holds on any build whose limit is at least 900, which covers every documented SQLite default — **and** a build configured below 900 would still raise and would need this constant lowered with it.

### Figures re-derived first-hand rather than relayed

- **The inclusive boundary.** Re-measured at *this test's* limit rather than at 999: `setlimit(..., 1800)`, then `n=1799` executes, `n=1800` executes, `n=1801` raises. So the limit is inclusive, the non-strict `chunk <= limit` is correct, and the strict `limit < orphans` is correct. Agrees with `cr2`/`cr3` at a different value.
- **Build facts**, measured in this worktree: Python `3.13.13`, SQLite `3.45.1`, default `SQLITE_LIMIT_VARIABLE_NUMBER` `250000`, `conn.setlimit` present.

### Surprises

1. **The seed is 2250, not 1801, and that is the only place I departed from a figure the story suggests.** AC-5a called 1801 zero-margin; rather than accept zero margin I changed the *formula* so the margin is structural at every `C`, then measured it at five values. AC-1 is satisfied by a wider margin as a result (3 chunks, 900+900+450), not a narrower one.
2. **Runtime is a non-issue** — both new tests together run in `0.23s` despite 4,500 seeded rows, because the fixture is one `executemany` and one commit rather than the per-row `_add_player` helper. The story flagged runtime as a watch item; it does not bite.
3. **Two pre-existing `ruff` `F841` findings in `tests/test_orphan_reclamation.py`** (unused `orphan` and `o2` locals) are NOT mine — confirmed by running `ruff` against the pre-story-03 backup and getting the identical two. I did not fix them: they sit in test bodies outside this story's diff and widening the diff is the code-reviewer's cost, not mine to spend unasked. **Flagging rather than silently leaving them** — say the word and they are two token deletions.

### Verification

Story-scoped: `python -m pytest tests/test_orphan_reclamation.py -k chunk -q` → `2 passed, 50 deselected in 0.23s`.

Full test scope for `src/reports/lifecycle.py`, discovered by grepping `tests/` for importers (`test_admin_reports.py`, `test_cleanup_eligibility.py`, `test_cli_report.py`, `test_orphan_reclamation.py`, `test_reclaim_orphan_script.py`, `test_report_generator.py`):

```
310 passed, 1 warning in 37.13s
```

exit code `0`. The one warning is a pre-existing Starlette/httpx deprecation from `fastapi.testclient`, unrelated.

---

**Coordination with story 01, stated so it is not discovered.** At least one of AC-7's targets sits in a docstring story 01 has already rewritten for a different reason — its root enumeration and its variable-limit claim are roughly one line apart in the same docstring. Serial execution (01 → 02 → 03) makes this safe, but you will be editing prose story 01 authored: correct the limit claim without disturbing the root enumeration it now carries. This is a within-file sequencing detail, not a missing interface.
