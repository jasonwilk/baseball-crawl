# E-276-01: Shared Gate Primitive + Player-Line Grain

## Epic
[E-276: Reconcile-at-Load Health Gate — Capture the Prior Set Before the Run's Own Writes](epic.md)

## Status
`TODO`

## Description

After this story is complete, the reconcile-at-load health gate takes its prior id-set as a required input captured before the run's own writes, instead of reading it from the database after those writes. The shared authority check gains a vacuous-permit rule for an empty protected population. The player-line grain is the first consumer, and a full GameChanger `player_id` churn — the input that currently hard-deletes nine live batting lines — refuses instead **on the run it arrives**.

**⚠️ Those last four words are load-bearing and were absent** *(added at the R1 disposition, 2026-07-26)*. **A refusal still WRITES**: the fresh rows land and only the retire is refused, so a *sustained* churn grows the gate's own prior population until it permits at the floor and hard-deletes the prior generation — uncapped, this grain having no `MAX_*` beneath it. That is the corrected gate behaving as designed, not a defect in it, and **R1 ruled it an accepted, surfaced residual: no gate, no cap, no `extra_guard`.** What this story ships against it is a **diagnostic** (AC-15) and **regression tests pinning both regimes** (AC-14). Read AC-14's banner before writing any multi-run assertion — the intuitive "the originals must survive every run" property is **FALSE** under the shipping design.

## Context

The health gate is meant to ask "does the fresh payload still vouch for most of what we already had?" It cannot, because the prior set is read downstream of the upsert and therefore contains this run's own rows. Every row written this run lands on both sides of the floor ratio and relaxes it by half a row.

This story delivers the shared primitive **and** its first consumer together. The primitive alone would be a no-op whose tests could only pin arithmetic, and it would leave the tree half-migrated with one grain on the new gate population and two on the old — see the Stories sequencing note in the epic.

The player-line grain goes first because it is the grain the audit executed, the only grain with no absolute cap beneath the gate, and the one that demonstrated an uncapped mass delete.

## Acceptance Criteria

- [ ] **AC-1**: Given a payload whose player ids are all brand-new relative to the stored lines (9 stored, 9 fresh, zero overlap), when a re-scout runs through the real `ScoutingLoader.load_team`, then **zero** prior lines are hard-deleted, a refusal is recorded, and `LoadResult.errors == 0` — per Technical Notes TN-12 an absence assertion needs proof the mechanism completed cleanly.

- [ ] **AC-2 (which-mechanism-refused — binding, per TN-11)**: The refusal assertion MUST identify which mechanism refused, asserted on a **structural record carried by the result dataclass rather than on WARN prose** — a test that greps log text passes when someone rewords the message. Assert `refused_by == "gate"`, `gate_permitted is False`, and that **the gate's prior count equals the pre-run population (9), not the post-upsert population (18)**. That count is the numeric tell; a surviving-row count alone can pass post-fix for a wrong reason.

      **⚠️ ON THIS GRAIN THE RECORD IS NOT SCALAR, and a scalar assertion cannot satisfy this AC.** `retire_absent_player_lines` evaluates the gate inside a **double loop** — `for block in blocks:` × `for label, table in _PLAYER_LINE_TABLES:` — so there are **up to four independent gate evaluations per call** (2 blocks × 2 tables), each with its own prior count, comparable count and verdict. Per epic TN-11, **the gate-outcome record keys exactly as `.refusals` keys on that grain**, i.e. by `(table, team_id)` here. **A scalar `gate_prior_count` would capture only the last iteration**, and with both blocks present the "9, not 18" assertion would be unambiguous only by accident. **Assert against the keyed entry for the block and table under test.**

      **And `refused_by` does not carry the whole answer even here.** It is **UNIT-level** — "did this grain refuse as a unit, and why?" Per-id protections live in `.refusals`. **A test asserting "0 retired" must check BOTH.**

      This grain is the one where the 9-vs-9 shape genuinely discriminates, because it has no absolute cap beneath the gate. Do not carry that sizing to the roster grain — see TN-11 and story 03.

      **⛔ THE KEYED ASSERTION IS THE FAIL-OPEN GUARD, AND THIS IS OPERATOR-ORDERED** *(added at the R1 disposition, 2026-07-26; found by SE the hard way during the R1 evaluation)*. **A mis-keyed or missing snapshot makes this gate fail-OPEN, silently, with the full pre-fix blast radius.** SE's own harness hooked the wrong method name; the snapshot came back **empty**; AC-6's vacuous-permit rule then permitted **every** gate; and the run **hard-deleted all 9 originals** — the exact outcome this epic exists to prevent, produced by a wiring mistake rather than a design flaw, with nothing in the output saying so.

      **AC-7 does not cover this and cannot.** A required keyword parameter stops an **omitted** argument; it does nothing about a **present but wrongly-keyed** dict, which type-checks, passes AC-7's `TypeError` test, and arrives empty. **The two ACs guard different failures and neither substitutes for the other.**

      **So the `gate_prior_count` assertion of this AC MUST be made per keyed entry** — against the specific `(table, team_id)` entry for the block under test, asserting the **pre-run population**, never a scalar and never merely "some gate refused." An empty snapshot yields a prior count of **0**, which is exactly what the keyed assertion catches and what every coarser observable misses: rows still vanish, `LoadResult.errors` stays 0, and a refusal-shaped log line never appears because nothing refused.

      **The generalization worth carrying, because it is this epic's own subject pointed at its own fix**: the corrected gate's failure mode is **quieter than the bug it replaces.** The original defect at least left an implausible `18-of-18` in the log; a fail-open empty snapshot leaves a plausible `0-of-0` and permits. **A gate that fails open is worse than the defect it corrects, because it looks like a gate.**

      **The record is not reachable by default AND does not yet exist — read epic TN-17 before writing this test.** Two separate problems: the player-line wrapper returns only an int error increment and discards the result dataclass (reachability), **and no gate-outcome field exists on `PlayerLineRetireResult` at all** — its refusals are prose strings, the surface this AC forbids. **Adding the fields is a production change required under either sanctioned means**; the spy reaches the object but cannot conjure fields that are not on it.

      **⚠️ If a spy is the means, the test MUST assert positively that the spy captured a result object.** Row survival alone is satisfied by a spy that never fired, so that positive assertion is the observable check that the assertion target was genuinely reached — load-bearing, not decoration. **The patch site differs by grain, this grain's differs from the other two, and getting it wrong fails silently. Epic TN-17's per-grain table carries the target and the reason it is load-bearing; read it before choosing one.**

- [ ] **AC-3**: Given the zero-overlap boundary sweep encoded as parametrized cases (stale 9 / fresh 8, 9/9, 9/10), when each runs, then **every** case refuses. Pre-fix these produce refuse / delete-9 / delete-9 respectively, so the parametrization is the discriminating evidence.

- [ ] **AC-4**: Given overlap-bearing cases that discriminate the honest gate from the polluted one per TN-12 — prior 10 with 5 survivors + 6 new ids (honest verdict: permit) and prior 10 with 4 survivors + 6 new ids (honest verdict: refuse) — when each runs, then the outcomes match the honest verdicts.

      **The polluted arithmetic, corrected** [PM-VERIFIED 2026-07-25; an earlier version said "the polluted numerator is 10 in both", which is wrong]: the post-upsert prior is 16 (10 old + 6 new) so the floor is 8, and the polluted numerators are **11 and 10** respectively — survivors plus the six new ids. Both clear 8, so **the polluted gate permits both and the cases still discriminate exactly as intended**; only the stated number was wrong. Recorded rather than silently fixed because an implementer checking the arithmetic against a wrong stated numerator would reasonably conclude the fixture was mis-sized and change it.

- [ ] **AC-5**: Given a first-ever load of a game, when the reconcile runs, then **it retires nothing and emits no refusal, because every live prior id is present in `fresh`.**

      **⚠️ An earlier version of this AC said the pass "short-circuits without computing a gate (empty prior)". That was superseded residue and implementing it literally re-opens the TN-3 deadlock.** Under the settled design the candidate population is the **live** prior read, which on a first-ever load is **not** empty — those rows were written moments earlier. So the pass does not short-circuit, and a gate *is* computed (the corrected one, permitted vacuously). The empty-prior premise is true only of the **snapshot**. An implementer satisfying the old wording would gate the early return on the snapshot; on the roster grain that makes run 1 retire nothing, the 3 backfill-churn rows survive into run 2's snapshot, and the grain refuses permanently — exactly the deadlock TN-1(c) exists to prevent.

      **Pair the absence with positive evidence**, per the same rule AC-1 applies: assert the mechanism was entered and returned empty — an empty result object (reached per TN-17) plus `LoadResult.errors == 0`. A bare "nothing was retired" is satisfied identically by the reconcile never running.

- [ ] **AC-6**: The shared authority check implements the vacuous-permit rule of Technical Notes TN-1(c) — an empty protected population yields the fetch-ok value rather than a refusal — and **this grain's gate is the corrected gate ALONE**, computing the floor ratio over the **pre-upsert snapshot** population, per TN-1(b). The legacy live-population gate is **replaced, not conjoined**. Both the vacuous-permit rule and the corrected gate are covered by direct tests at the primitive level.

      **⚠️ The CONJUNCTION is superseded and must not be implemented in any form** — not as a shape, not as the basis of a neutrality proof, and not as a value reaching `classify_absences`. An earlier version of this AC required it. There is **one gate per grain**.

      **⚠️ Vacuous-permit MUST still be OPT-IN. An unconditional change to the shared check FAILS this AC**, because `crawl_is_authoritative` is shared with the roster grain's fetch-ok use and with the existing pinned assertion in `tests/test_reconcile_at_load.py`, which inverts by design (AC-12). Expose it as a keyword or a separate corrected-gate wrapper — the choice is the implementer's under TN-17's pattern. **"Inverts by design" is shorthand: the call as it stands today, with no opt-in argument, must STILL refuse. See AC-12's reconciliation paragraph — the pinned test is repurposed to the opted-in configuration and a sibling test holds the default-off position, which is the position that protects the roster grain's shared fetch-ok use.**

      **Calibration, so this is not over-read** (per TN-13): applying it unconditionally would not widen the gate *in production*, because all three helpers early-return on an empty live prior, so the gate is never reached with `prior_count == 0`. **The unit test still fails**, which is why the mechanism is specified. **The earlier form justified the conditionality by keeping a legacy conjunct at today's semantics; there is no legacy conjunct, and the calibration now stands on the early-return alone.**

- [ ] **AC-7**: The prior-set input is a **required keyword parameter** with no default, per TN-1(a) and the evidence-parameter rule in `.claude/rules/python-style.md`. **A TEST demonstrates that the parameter cannot be omitted** — calling the helper without it raises `TypeError`, in the manner of the existing `test_floor_is_not_overridable_by_callers`, which pins the same class of contract with `pytest.raises(TypeError, match=...)`.

      **"or a review note" is REMOVED from this AC.** A review note is not an observable verification target: it certifies that someone looked, not that the property holds, and it evaporates the moment the signature changes. **The property this AC protects is precisely the one a future edit restores by accident** — a default here silently reinstates the defect the whole epic exists to fix, which is why it needs a check that fails rather than a note that was true once.

- [ ] **AC-8 (deletion-neutrality — player-line grain, STRUCTURAL given a named premise)**: **The fix never permits a DELETION that today's code refuses, on this grain.** This holds **by construction from the premise `W ⊆ fresh`** (epic TN-5's two-line proof: every row the run adds contributes 1 to the legacy numerator and 1 to its denominator, and `1 ≥ 0.5·1`) — **not** from a conjunction and **not** from a sweep. The result is scale-free. Assert the algebra at the primitive level; the ported sweeps are corroboration only.

      **⛔ The blanket "on any grain and any input" form is STALE and must not be reinstated — it is FALSE on roster**, where `W ⊄ fresh` because the jersey backfill writes rows the fresh crawl never listed. That is a prediction of the same premise, not an exception to it.

      **⚠️ SCOPE THE ASSERTION TO DELETIONS, NEVER TO PERMITS.** The two gates genuinely disagree in one region — at `P_pre = ∅` **and** `W = ∅`, the corrected gate permits vacuously while the legacy gate refuses on its `fresh_count > 0` check (**32 executed cases**). All 32 have an empty candidate set, so nothing is deleted either way. **A test phrased as "permits whenever today permits" would fail against a design that is correct.**

- [ ] **AC-9a (precondition (c))**: Exactly one gate **value** reaches `classify_absences` — **the corrected gate's verdict**. Pin it with a test, not by inspection: this was the only one of SE's five attacks on the neutrality formulation that landed, so it is an implementation risk rather than a logic one. *(The object of this AC changed with the design — it previously named the conjunction. The requirement is unchanged: one value, not two, and no second gate composed at the call site.)*

- [ ] **AC-9b (precondition (d) — the slip no other AC can catch)**: `classify_absences` receives the **live** prior set as its `prior_ids`. **This story's deliverable is the PRIMITIVE-LEVEL CONTRACT TEST, on the grain this story wires** — not a cross-grain assertion and not the executed two-run construction, which story 03 AC-8 owns (see epic TN-16, "Precondition-(d) OWNERSHIP"). An earlier version said "on all three grains", which claimed a deliverable this story's file list does not reach. The snapshot computes the corrected gate value ONLY and is **never** passed as the classification universe.

      **Mechanism, stated because this is uncatchable downstream**: the classifier returns a classification covering exactly the ids it is handed, so that argument IS the candidate universe. The natural slip — *"the corrected gate uses the snapshot, so pass the snapshot to the classifier"* — reads as obviously correct while writing it, and makes the candidate set `snapshot − fresh`. Executed: run 1 then retires nothing where the correct form retires the 3 churn rows; run 2 those rows are pre-existing, trip the departure cap, and become **permanently** unretirable — the epic TN-3 deadlock re-entered through the classifier instead of the gate.

      **Why AC-8 cannot catch it**: the slip only SHRINKS the candidate set, so it permits strictly fewer deletions and the neutrality absolute stays TRUE while the thing it guards breaks. Pin this with its own test, not by inspection.

      **⚠️ Division of labour with story 03 AC-8, stated so the test is written ONCE.** Both stories previously claimed the precondition-(d) test outright. The split: **this story pins the CONTRACT at the primitive and player-line level** — that `classify_absences` is handed the live set, on the grain this story wires. **Story 03 ports the EXECUTED slip construction**, because the roster grain is the only one where the slip's consequence is demonstrable (run 1 retires nothing, run 2 the rows are pre-existing and trip the cap, permanently). Neither is redundant, but they are different tests and must not be written twice under two names.

      **Why the one-grain scope holds — the premise, added 2026-07-25 because this rationale was challenged and survives** (full derivation in epic TN-16, "Precondition-(d) OWNERSHIP"). The slip swaps the snapshot for the live prior as the classification universe, and since `live_prior = snapshot ∪ W` the two candidate sets differ by exactly **`W − fresh`**. **`W ⊆ fresh` holds on this grain and on game** — the epic's own discriminator, guarded at runtime by story 02 AC-8 — so `W − fresh = ∅` and **the slip is a strict no-op here**. On roster `W ⊄ fresh` (the jersey backfill writes rows the fresh crawl never listed), and those rows are the whole divergence. **So the scope is a prediction of the epic's discriminator, not an artifact of where a fixture was built** — which is why this story's deliverable is the contract test and not the construction. **It is not undone by the game grain having its own cap**: a cap makes a divergence permanent, and on game there is no divergence to make permanent.

- [ ] **AC-10**: The pure classifier's contract is otherwise unchanged: it never receives the snapshot as its prior population (AC-9), and connection-in / no-commit / caller-owns-the-transaction still holds across the module. No `commit()` or `rollback()` is introduced.

- [ ] **AC-11**: The prose sites assigned to this story in Technical Notes TN-9 are corrected in this same change — including `crawl_is_authoritative`'s docstring, which is **already false today, pre-fix**: it documents the fresh count as "size of the fresh payload" while all three callers have passed the overlap since E-267. The module docstring's invariant carries **both** the temporal clause and the necessary-but-not-sufficient note per TN-10.

      **Plus one CITATION THAT RESOLVES TO NOTHING, found by DE during the R1 evaluation and in scope here because this AC already opens this module's prose** *(added at the R1 disposition, 2026-07-26; PM-VERIFIED by grep — the cited name appears in no file)*. In `src/db/reconcile_at_load.py`, the `ORDERING IS LOAD-BEARING` comment above `classify_absences`' `permit_removal` block ends: *"Pinned by `test_permissive_guard_cannot_widen`."* **No test of that name exists.** The real test is `tests/test_reconcile_at_load.py::test_permissive_guard_cannot_widen_a_refused_health_gate`. Correct the name in place.

      **This is not a typo class, it is the one `.claude/rules/tool-output-integrity.md` names**: a safety comment citing a test as its proof, where the proof cannot be looked up. The comment is otherwise **correct and load-bearing** — it forbids collapsing the gate-then-guard ordering — so **fix the citation, do not touch the invariant it states.**

- [ ] **AC-12 (suite green — scoped to THIS STORY, which is what previously went unstated)**: `python -m pytest tests/` reports 0 failed. **As of this story's completion**, the **72 tests in the three grain files** keep every assertion unchanged, with mechanical keyword-argument churn at the 9 direct call sites listed in TN-13.

      **⚠️ THE SCOPE WORDS "as of this story" ARE LOAD-BEARING AND WERE MISSING** *(added 2026-07-25, second Codex spec pass)*. **Story 03 AC-11 later changes an assertion inside those same 72** — `tests/test_roster_grain_reconcile.py::test_catastrophic_roster_shrink_refuses_on_the_floor`, one of the roster file's 18 — so the unscoped claim was **epic-wide false** even though it is story-locally true. The epic-wide total is **TWO** expected assertion changes, tabulated in **Success Criterion 2**. **Do not read this AC as a standing guarantee about the 72**, and do not "fix" story 03 to preserve it.

      **Exactly one existing assertion inverts IN THIS STORY, by design** (the epic-wide total is two — see the scope note directly above): `tests/test_reconcile_at_load.py::test_empty_payload_refused_even_with_empty_prior` asserts `crawl_is_authoritative(fetch_ok=True, fresh_count=0, prior_count=0) is False` — the precise input AC-6's vacuous-permit rule inverts. Update it with its docstring and name, which currently say an empty payload is refused "independently of the (vacuous) ratio test." **An earlier version of this AC forbade any assertion change and was therefore unsatisfiable** — see TN-13 for how a count over three files came to stand for the whole reconcile suite.

      **⚠️ HOW THIS RECONCILES WITH AC-6's OPT-IN REQUIREMENT — read before touching the test, because the two ACs read as contradictory and are not** *(added at the R2–R5 red-team repairs, 2026-07-26)*. AC-6 and TN-1(c) require vacuous-permit to be **opt-in**, so the call **exactly as written today** — `crawl_is_authoritative(fetch_ok=True, fresh_count=0, prior_count=0)`, with no opt-in argument — **must still return `False` after the fix.** Taken literally, "this assertion inverts" and "vacuous-permit is opt-in" cannot both hold. The resolution is that **the assertion inverts only once the call opts in**:

      - **`test_empty_payload_refused_even_with_empty_prior` is REPURPOSED**, not merely flipped: it is updated to exercise the **opted-in** configuration (whatever keyword or corrected-gate wrapper the implementer chooses under TN-17's pattern) and asserts the permit there, with its name and docstring brought to that subject.
      - **A SIBLING test pins the default-off refusal** — the same three arguments with **no** opt-in still returning `False`. This is not new scope: AC-6 already requires the vacuous-permit rule to be "covered by direct tests at the primitive level", and a switch is only covered when **both** of its positions are pinned.

      **The sibling is the load-bearing half, and it is the one an implementer will skip** as redundant with the flipped test. It is the only executable guard on the property AC-6 exists to protect: `crawl_is_authoritative` is **shared**, and the roster grain calls it for its fetch-ok signal on a grain that under story 03 has **no floor beneath it**. An unconditional vacuous-permit would make an empty roster payload read as authoritative there — so if the default-off assertion is lost, the next edit that "simplifies" the opt-in away restores that silently and every test still passes. Same reasoning as AC-7: the property this protects is the one a future edit restores by accident, which is why it needs a check that fails rather than a note that was true once.

- [ ] **AC-13 (PRESERVE the operator-facing which-refuser discrimination)**: When this grain refuses, the WARN it emits MUST name the refusing mechanism and carry **that mechanism's own counts**, rendered from `refused_by` and the gate-outcome record.

      **This is a preservation requirement, not a new capability** [PM-VERIFIED, clean read of `retire_absent_player_lines`]. The refusal path already emits a `fresh_comparable_count` / `prior_count` / `floor_ratio` triple. **The reason it needs naming is not the conjunction** — that is superseded — **it is that several mechanisms each produce "0 retired" on this path**, and an unlabelled triple cannot say which one is reporting.

      Concretely: a refusal reading "not authoritative, comparable 18 of 18" tells an operator nothing about which population was measured, and **18-of-18 is exactly the shape the original defect produced while looking healthy** — the polluted prior counted this run's own writes on both sides. The corrected gate would have read 0-of-9 on the same input. A message carrying the refusing gate's own pair is the difference between a diagnosable log line and the one that hid this bug.

      **This is not a duplicate of AC-2, and the two do not conflict.** AC-2 governs what a *test* asserts on and forbids the WARN as an assertion target. This governs the *message itself*, which in production is the operator's only signal. The gate-outcome record (epic TN-11) is the source and the WARN renders from it, never the reverse — so a test for this AC may assert on the message text, because here the message **is** the deliverable rather than a proxy for behaviour.

- [ ] **AC-14 (MULTI-RUN — the class every planning probe missed, at production scale)**: A test drives **N ≥ 4 sequential `ScoutingLoader.load_team` invocations** and asserts the **exact surviving line count after each one**, not merely at the end. Per-invocation assertions are the deliverable; an endpoint-only assertion does not satisfy this AC.

      **Why this AC exists, and it is not a completeness gesture** [epic TN-16]: *every* probe and sweep run during this epic's planning was **single-run**, and the failure that reopened the design three times (F1, the roster lock) is **multi-run** — it needs a refusal to strand rows that a later run then counts. **A grain with no multi-run regression test is untested against that whole class.** TN-16 assigns this construction to each grain story; story 03 discharges it at the roster grain through AC-7's erosion sequence and **AC-8(c)**, and this AC is its player-line counterpart.

      **⛔ THIS AC PREVIOUSLY PINNED "THIS GRAIN MUST NOT RATCHET" AS A GLOBAL PROPERTY. THAT PROPERTY IS FALSE UNDER THE SHIPPING DESIGN, ON THE VERY FIXTURE THIS AC MANDATES — it was an unsatisfiable assertion, not a wording problem. It MUST NOT be reinstated in any form.** *(Rewritten at the R1 disposition, 2026-07-26, on evaluations SE-R1 and DE-R1 ran independently by construction.)* Three corrections, each of which the old text got backwards:

      1. **A refusal WRITES.** The old text said *"a refusal writes nothing, so run 2's snapshot should equal run 1's."* The retire is refused; the **upsert is not**. Every refused run adds its generation to the stored population.
      2. **The originals do NOT survive every invocation.** Because the population grows while the gate's floor is a ratio over it, a sustained churn reaches a run where the gate **permits** and hard-deletes the prior generation — uncapped, this grain having no `MAX_*` beneath it.
      3. **A recovery invocation DOES retire, and that is CORRECT.** The old text required it to "retire nothing." A recovery payload carrying the original ids makes the *churned* ids absent, so retiring them is the right answer. An AC demanding zero retirement there would forbid correct behaviour.

      **⚠️ `W ⊆ fresh` DOES NOT RESCUE THE OLD PREMISE, AND THIS IS THE CRUX** — reached independently by both agents. `W ⊆ fresh` constrains the **candidate** set (what may be deleted); it says nothing about the **gate population** (what the floor is computed over), **and it is the population that grows.** The old text leaned on `W ⊆ fresh` to claim this grain was clean where roster was not. The premise is true and the inference does not follow.

      **Pin TWO REGIMES. They differ in outcome, and collapsing them loses the finding.**

      **REGIME A — churn the dedup sweep CAN merge, on the scouted team's OWN block.** The originals survive every invocation. Executed (SE-R1, 9-line block): `rows per run [9, 9, 9, 9]`, `originals surviving [9, 9, 9, 9]`, gate reading `prior=9 comparable=0 permit=False` every run.

      **The required observable is the POST-SWEEP ID-IDENTITY ASSERTION**: after run 2, assert the surviving ids are the **original** generation **and** the row count equals the block size. Both halves — a run where the sweep silently did nothing fails it, finding either `2 × block` rows or the churned ids surviving.

      **⚠️ Three things about this observable, stated because the obvious stronger-looking options are worse** *[SE-R1, and the first is a correction to how this AC was previously worded]*:
      1. **SE ran NO dedicated mechanism assertion** — its evidence was the row-count-plus-id-identity pair above, from which the sweep is *inferred* (nothing else in the pipeline removes freshly-written rows there). This AC therefore requires that inference's observable, and does not credit SE with a direct one.
      2. **A SPY ON THE SWEEP IS NOT SUFFICIENT and must not be substituted.** Per [[IDEA-189]] a failing collapse is logged and swallowed **without incrementing `LoadResult.errors`**, so a spy certifies ENTERED, never COMPLETED — a sweep that entered and threw produces spy evidence identical to one that merged. This is the exact gap `.claude/rules/testing.md` names, and on this seam the usual fallback (`LoadResult.errors`) does not cover it either.
      3. **The genuinely stronger option exists but costs a patch**: `dedup_team_players(...) -> int` returns the count merged away, and **`ScoutingLoader._load_team_core` discards it** (bare call inside its `try`) — the same reachability problem TN-17 describes for the reconcile result. **Take it if you are willing to reach it; the id-identity assertion is the floor, not the ceiling.**

      **REGIME B — churn the sweep CANNOT merge. Pin the executed sequence as an ACCEPTED, DOCUMENTED RESIDUAL — do NOT assert its absence.** Two disjoint triggers, and the second is the one that gets forgotten:
      - **non-prefix name churn** (`Mike`→`Michael`), invisible to a detector that matches on name prefix;
      - **ANY churn on the OPPONENT block** — `dedup_team_players` is scoped to the **scouted** team, so the opponent block has **no closer in any shape**. Not "a weaker closer": none. *(Operator-ruled an accepted documented residual, 2026-07-26.)*

      **Assert the loss where it occurs rather than asserting it does not.** This AC's job in regime B is to make a later change that *worsens* it fail loudly.

      **The executed sequences to pin** *[SE-R1, §1 B2 and §2a]*. **The prior generation is hard-deleted on RUN 3, in full, uncapped**, in both sizes:

      ```
      9-line own block    rows per run        [9, 18, 9, 9]
                          originals surviving [9,  9, 0, 0]
                          run2 gate  prior=9   comparable=0  permit=False  absent=9   retired=0
                          run3 gate  prior=18  comparable=9  permit=True   absent=9   retired=9

      12-line own block   rows per run        [12, 24, 12, 12, 12]
                          originals surviving [12, 12,  0,  0,  0]
                          run2 gate  (12,  0, False, 12,  0)
                          run3 gate  (24, 12, True,  12, 12)
      ```

      **The opponent-block case is EXECUTED, not reasoned, and it is executed on the HARDEST shape** *[SE-R1, §1 B3]* — the **identical-name re-issue**, i.e. precisely the churn `dedup_team_players` is supposed to close. Same 9-line fixture with the payload under the opponent key yields the **same** numbers: `rows [9, 18, 9, 9]`, `originals [9, 9, 0, 0]`, run-3 gate `prior=18 comparable=9 permit=True retired=9`, keyed `('player_game_batting', 2)`.

      **State it at that strength — executed end-to-end AND structurally explained, not inferred from the own-block result.** The mechanism was confirmed by reading the call site: `_load_team_core` calls `dedup_team_players(..., team_id, ...)` with the **scouted** team id, while the opponent block's `player_game_*` rows are written under `opp_team_id`. **So the opponent block has no closer in ANY shape — including the one shape that does close on the own block.**

      **Production scale is required and is the point.** Drive a season at production scale — **20-30 completed games** (CLAUDE.md, "Scope"), with roster-sized blocks of **12-15 lines**, which is the grain's actual gate denominator. A one-game two-line fixture satisfies the letter of a multi-run test and exercises none of the accumulation the class is about. State both figures in the fixture, because the season size and the block size are different denominators and **only the second reaches the gate.**

      **The executed figure that makes this concrete — and ⛔ IT BELONGS HERE, NOT IN REGIME B.** *(Withdrawn from regime B on 2026-07-26 after SE-R1 specified what it measures. It was one label away from citing the wrong phenomenon as evidence for the run-3 window.)* Executed at **24 games × 13-line blocks with 3 ids churning per game**: **72 batting lines die**, `24 × 3 = 72` — **13 is the block size / gate denominator, not a multiplicand**, and total rows stay **312** (`24 × 13`) throughout, each churned line replaced one-for-one. Per-run `(total_rows, originals_alive)`: `[(312, 312), (312, 240), (312, 240), (312, 240), (312, 240)]`. All 72 are **own-block `player_game_batting` rows** — the fixture's pitching group is `stats: []`, so no `player_game_pitching` rows exist at all.

      **⚠️ The loss lands on RUN 2, and this is why it is not a regime-B figure.** 3 of 13 is **below the floor**, so the gate permits immediately — **this is TN-8's partial-churn residual at season scale ([[IDEA-185]]), not the R1 run-3 accumulate-then-delete window.** It earns its place here because it shows exactly what the production-scale requirement is for: **the block size gates, the season size multiplies.** Attaching it to regime B would cite one residual as evidence for another.

      **📌 THE SIZING BOUNDARY — preserved inline because the harness that produced it lives in a session scratchpad and WILL VANISH** (epic TN-16: *a construction that exists only in a transcript is not a regression test*). All figures confirmed by SE-R1 against its executed record, 2026-07-26.

      **The rule is `m ≥ P`, NOT "m ≥ 12"** — `m` is the **churn block size** (the fresh block's line count from run 2 on; in a total-churn fixture this is also the number of churned ids, and SE measured no case where the two differ), and `P` is the original block. The gate permits iff `m >= 0.5 · (P + m)` ⟺ **`m >= P`**. Write `m ≥ P` if you want the rule; write "12" **only** if the fixture is pinned at a 12-line block.

      - **Measured, not a safe margin**: at `P = 12`, **`m = 11` refuses and `m = 12` deletes — no gap.** At `m = P` the arithmetic is `12 >= 0.5 · 24`, an **exact equality**, so this is a knife edge rather than a comfortable threshold. Confirmed at a second value of `P` (`P = 9, m = 9` deletes on run 3). **Everything beyond those two points is algebra consistent with the measurements, not measurement** — SE's own scoping, kept.
      - **Below the boundary the outcome is DIFFERENT, not merely smaller.** At `m = 9/10/11` the gate refuses on **every** run, rows stabilise at **21/22/23**, and the originals all survive. **Do not call this "duplicates"** *[SE-R1's wording correction]*: below the boundary the churn block is *smaller* than the original, so it is **two co-resident generations**, not a doubling — exact doubling appears only at `m = P`. **A regime-B fixture built below the boundary pins permanent co-residence instead of the delete, and reads as passing.**

      **The DISCRIMINATING assertion remains the per-run prior count** — pre-fix it reads the post-upsert population (18) on the churn run, post-fix the pre-run one (9). Assert it **per invocation**, on the keyed record entry per AC-2, and the test fails pre-fix for the right reason.

      **📌 THE ACCUMULATE-THEN-DELETE PREDICATE — EXECUTED, 8/8, and it lives HERE because it is TEST-SIDE ONLY** *(SE-R1 `drv7_predicate.py`, research record §6b; added 2026-07-26)*. Express the regime-B detection as this predicate across invocations. **No tolerance, no arithmetic:**

      ```
      fires(prev, cur) == cur.gate_permitted is True
                          AND cur.gate_prior_count > prev.gate_prior_count
                          AND prev.gate_prior_count > 0
      ```

      `prev` is the record for the **SAME KEY** from the **PREVIOUS** invocation. **The key is `(game_id, table, team_id)` and `game_id` is REQUIRED** — omit it and a season's games overwrite each other's records, which is a silent wrong answer rather than an error.

      Executed across 8 scenarios: fires on regime B run 3 at **both** measured block sizes (P=12, P=9) **and on the opponent block**; silent on regime A, on the sub-boundary case, on a first-ever-load-then-clean-reload, on a clean no-churn re-scout, and on a new game joining the season.

      **⛔ THE `> 0` CLAUSE IS REQUIRED, NOT DEFENSIVE — proved by RUNNING WITHOUT IT, not by argument.** Dropped, three scenarios false-fire, and one of them is an **ordinary in-season shape**: a game added on invocation 2 records `prior=0, permitted=True` under the vacuous-permit rule, so invocation 3's perfectly clean load reads as growth-with-permit. **That case false-fires TWICE.** Without the clause the predicate misfires on **every new game of the season** — a diagnostic that cries wolf on normal operation is worse than none.

      **⚠️ TWO SCOPE LIMITS, both flagged by SE against its own result:**
      1. **The 8/8 was run against the harness's RECORD DICT, not against the real `ScoutingLoader`.** The predicate is validated **at the record level**; expressing it against the real loader is **this story's implementation work and does not yet exist**. Do not read "executed, 8/8" as meaning the test is written.
      2. **In regime A the silence comes from the `gate_permitted` conjunct, NOT the growth conjunct** — dedup merges the fresh generation away each run, so `comparable` is 0 and the gate refuses every invocation. **The predicate does not distinguish merged from unmerged and does not need to.** Do not write a comment claiming it detects a successful dedup; it keys on permit ∧ growth and nothing else.

      **⛔ AND IT CANNOT BE MOVED TO AC-15 OR TO PRODUCTION.** It needs the previous invocation's record for the same key, and **nothing in production retains one** — the record is built per call and returned in the result dataclass. Persisting it across runs would be **a snapshot table by another name, which epic TN-2 rejects outright.** AC-15's production diagnostic is deliberately single-run for exactly this reason. **These are two artifacts; a future editor consolidating them would reintroduce the storage TN-2 forbids.**

      **⛔ EVERY REFUSAL ASSERTION IN THIS AC NEEDS POSITIVE EVIDENCE THAT THE PATH COMPLETED CLEANLY. A CRASH PRODUCES EXACTLY THE OBSERVABLE OF A REFUSAL.** `_retire_absent_player_lines` sits inside a broad swallow-and-count `except`, so an exception anywhere in it yields *nothing retired, rows intact, no refusal WARN* — indistinguishable from a healthy refusal by row count, which is the obvious assertion and the wrong one.

      **⛔ AND THE TWO INSTANCES POINT IN OPPOSITE DIRECTIONS, WHICH IS A STRONGER AND WORSE FINDING THAN A REPEATED TRAP** *[SE-R1's correction to a "same trap twice" framing]*. It was hit **twice independently in one session, by two agents each writing code specifically to probe this seam, neither knowing the other had** — and each got the answer they were looking for:

      - **SE** was probing for a **refusal**. Its guard raised, was swallowed, and returned **exactly the observable of a refusal**.
      - **DE** was probing for a **closure**. Its `PlayerRef`-into-a-set-intersection `TypeError` was swallowed, the reconcile aborted, and its harness printed **"CLOSES the fork window."**

      **In both cases the surviving-row count cooperated with the hypothesis.** DE caught it on `LoadResult.errors`; nothing about the rows would ever have surfaced it.

      **A trap that fires twice the same way is a hazard you can name and dodge. This seam converts a crash into WHICHEVER OUTCOME THE OBSERVER WAS LOOKING FOR — which naming does not protect you from**, because the confirming evidence arrives exactly where you were already looking.

      **Therefore the requirement is not "count rows carefully." It is that on this grain THE ROW COUNT IS NOT AN ADMISSIBLE WITNESS FOR EITHER OUTCOME** — not for a refusal, not for a successful retire. Any assertion establishing **either** needs positive evidence the path completed:

      - **pair every "nothing was retired" with `LoadResult.errors == 0` per invocation** (`.claude/rules/testing.md`, "An absence claim needs proof the mechanism COMPLETED CLEANLY");
      - **require `gate_evaluated` to go false on exception**, so a crash cannot read as a permit;
      - and note the one place `LoadResult.errors` does **not** cover you — the dedup sweep's swallowed collapse ([[IDEA-189]]), which is why regime A's observable is id-identity rather than a spy.

      **A test that passes when the code crashes is worse than no test, and this epic has already produced two — pointing opposite ways.**

- [ ] **AC-15 (THE ADOPTED R1 OUTCOME — a DIAGNOSTIC on a PERMITTED retire. No gate, no cap, no `extra_guard`)** *(added at the R1 disposition, 2026-07-26)*: On a retire this grain **PERMITS**, when a victim id name-matches or jersey-matches a **surviving fresh** id, emit **one** WARN naming the count, the ids, and **`bb data dedup-players`** as the instrument. Additionally record the accumulation signature in the gate-outcome record.

      **⚠️ THIS IS NOT AC-13, AND IT MUST NOT BE FOLDED INTO IT.** SE's source text cited "see AC-13" for this diagnostic; **AC-13 is scoped to REFUSALS** — its first line is *"When this grain refuses, the WARN it emits MUST name the refusing mechanism."* **This fires on the opposite branch: a retire that was PERMITTED and deleted rows.** Folding it into AC-13 would invert that AC's subject and silently re-scope a preservation requirement. They are complementary halves of the same operator-facing surface: AC-13 explains a refusal, AC-15 explains a *deletion that looked routine*.

      **What R1 established, so this AC is not read as a consolation prize.** Three mechanisms that would have CLOSED this window — an `extra_guard`, a cap, and a churn-signature gate — were evaluated **by construction**, independently, and **none was adopted**. Not on cost: **every mechanism that closes the window closes it by refusing forever, and a permanent refusal on this grain doubles the coach-facing season aggregate** (measured against the shipped `get_season_batting`). A doubled season line reaching a coach is worse than the deletion. **So the operator ruled: surface it, do not gate it.** Deletion behaviour is unchanged by construction, which is why AC-8's deletion-neutrality is untouched.

      **⛔ THIS AC IS SINGLE-RUN AND MUST STAY SINGLE-RUN. NO CROSS-INVOCATION STATE, NO PREVIOUS-RUN RECORD, NO ACCUMULATION SIGNATURE.** *(Scoped 2026-07-26. Earlier routing bundled a cross-run signature into this AC; that instruction was **withdrawn** once SE-R1 built the predicate and found what only building it revealed.)*

      **The reason is structural, not stylistic.** A cross-run signature needs the previous invocation's record for the same key, and **nothing in production retains one** — the record is constructed per call and returned in the result dataclass. Retaining it across runs would be **a snapshot table by another name, which epic TN-2 rejects outright.** So the accumulate-then-delete predicate is **test-side only and lives in AC-14**, where the multi-run harness already provides the history it needs.

      **What this AC ships is the single-invocation signal**: on a **permitted** retire, victims that name- or jersey-match a **surviving fresh** id — computable from one call, no history required. **That is the whole diagnostic.** If implementing it makes you want the previous run's numbers, stop: that is AC-14's predicate and it cannot come here.

      **⛔ Do NOT pin `gate_prior_count ≈ 2 × gate_comparable_count` anywhere.** *(Withdrawn 2026-07-26. SE-R1 swept it against its own executed rows: `prior == 2 × comparable` is **exact when `m = P` and false otherwise** — 2.00 / 1.92 / 1.86 / 1.80 at `m = 12/13/14/15` — an artifact of the equality case, not a signature. **An approximation in an AC is a claim, and that one is false.**)*

      **`retired == prior − comparable` is likewise NOT an invariant** and must not be recorded as one. It held exactly in every executed run-3 row, **but it is false on run 2** — `retired` derives from the *live* prior and `prior − comparable` from the *snapshot*, and those coincide only once the run's own writes are already in the snapshot. **Pinning it would encode a run-3 coincidence as a law.**

      **📎 SOURCING CONSTRAINT for anyone adding executed figures here or in AC-14** *[SE-R1, self-reported against its own draft]*: `drv5`'s m-sweep printed **3-tuples** `(prior, comparable, permitted)` only. Any `absent`/`retired` value for m = 13/14/15 seen elsewhere was **inferred from row counts, not printed.** Only two rows are fully sourced with printed `absent`/`retired`: **m = 12** (from `drv2`) and **P = 9, m = 9** (from `drv1`). **Pin an `absent`/`retired` figure from those two rows only.**

      **Two implementation constraints that survive the verdict, both load-bearing:**

      1. **The diagnostic sits inside the same broad swallow-and-count `except` as everything else in `_retire_absent_player_lines`.** A diagnostic that raises is swallowed and produces the observable of a clean run — see AC-14's banner for the two independent reproductions. **`gate_evaluated` must go false on exception**, and this AC's own test must assert `LoadResult.errors == 0` so a silently-crashed diagnostic cannot pass as a working one. **A diagnostic whose failure is invisible is worse than none: it converts "no warning" from evidence into noise.**
      2. **If the match test calls `plan_player_dedup`, precompute it ONCE PER GAME LOAD and close over the result.** This grain's gate is evaluated **up to 4× per game** (2 blocks × 2 tables), so a planner call per evaluation is **4 self-joins per game** — on a 24-game season that is ~96 self-joins for a diagnostic. Cost, not correctness, but it is the difference between a diagnostic that ships and one that gets removed.

      **Scope discipline**: this AC adds **one WARN, one record field, and their tests.** It does not change what is deleted, does not add a refusal path, and does not alter any existing gate. If implementing it requires changing a retire decision, stop — that is outside the operator's ruling and belongs to [[IDEA-185]].

## Technical Approach

The fix shape, capture anchor, rejected alternatives, and contract impact are specified in the epic's Technical Notes — TN-1 (fix shape), TN-2 (capture anchors), TN-5 (deletion-neutrality), TN-6 (transaction verdict), TN-9 (prose sites), TN-10 (corrected invariant), TN-12 (test design), TN-13 (churn inventory), TN-14 (guardrails). Read those before starting; they carry rulings from three consultations and several rejected shapes that should not be re-derived.

Two things specific to this story:

The player-line capture anchor must sit after the canonical-id rebind and before any of this game's stat writes. The reason it cannot be hoisted to the start of the run is in TN-2: the canonical game id does not exist until mid-loop.

The prose corrections belong in this same change rather than deferred to the context-layer story, per the same-commit rule in `.claude/rules/tool-output-integrity.md`.

Reference material, read-only, both in ephemeral session scratchpads — reproduce what they demonstrate rather than depending on the paths surviving:
- `/tmp/claude-1000/-workspaces-baseball-crawl/4aca143d-2d11-40ae-ae02-d8924803b063/scratchpad/recon_audit/` — the original audit harness. `t_playerline.py` carries an `upsert_fresh` toggle that isolates exactly this ordering, plus the boundary sweep already parametrized.
- `/tmp/claude-1000/-workspaces-baseball-crawl/2728098f-4677-4ff3-a474-cda6aed92b4c/scratchpad/` — `divergence_plugin.py` and `divergence_game.py`, the read-only probes that recompute the gate both ways at every reconcile call and report divergences.

## Implementer's Notes on the Preconditions

Two attacks DE ran that SE had not, both verified, recorded here so they are not re-derived:

- **The `fetch_ok` sources are unchanged and that still matters.** All three — the roster's non-empty-fresh signal, the player-line block's populated flag, and the game grain's schedule-fetch flag — are **identical to today**. Under one-gate-per-grain this is no longer about a "legacy half"; it is why `fetch_ok` transfers unmodified in TN-5's proof, which covers all three of `crawl_is_authoritative`'s conjuncts and not only the ratio.
- **The exempt-filtered set is load-bearing at the roster grain, and the wrong choice LOOKS SAFE.** Today's roster prior set is already exempt-filtered. **It is now the candidate population rather than a gate input** — roster has no gate — so getting it wrong changes which rows are *retirable*, not merely which are counted. Precondition (e) is MOOT under the shipped design for exactly this reason, and carries its own wake-up triggers. Another true-looking construction; give it the same suspicion as the rest.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-276-02, E-276-03, E-276-04, E-276-05

## Files to Create or Modify
- `src/db/reconcile_at_load.py`
- `src/gamechanger/loaders/game_loader.py`
- `tests/test_reconcile_at_load.py` (the primitive's own test file — home for AC-6's vacuous-permit and corrected-gate tests; **holds the one assertion that inverts**, per AC-12)
- `tests/test_player_line_reconcile.py` (this grain's tests, plus its **1** direct helper call site — inside `test_perspective_predicate_on_the_diff_is_observable_in_the_proposal` — per TN-13. **Cited by test name, not by line: this story adds tests to this same file, so a line number rots before you reach it.**)

**NOT in this story's list, corrected 2026-07-25**: `tests/test_game_grain_reconcile.py` (6 sites) and `tests/test_roster_grain_reconcile.py` (2 sites) were previously listed here for "mechanical keyword-argument churn". TN-13's 9 sites is a **whole-epic** inventory, not this story's; the game and roster churn belongs to stories 02 and 03, in the same commit as the behaviour change it accompanies. Keeping them here overstated this story's already-largest footprint and put two files in two stories' lists with no ordering reason.

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-276-02 and E-276-03**: the shared prior-set parameter shape and the amended authority check including the vacuous-permit rule. Both consuming grains depend on that contract; a half-migrated gate is the state the sequencing exists to avoid.
- **Produces for E-276-02 and E-276-03**: the **gate-outcome record**, defined once and carried by all three grain result dataclasses. Its field set is specified in epic **TN-11** ("THE RECORD ITSELF"). **The type's name is this story's to choose; the field set and the keying rule are not.** Three traps, all load-bearing:
  1. **`gate_evaluated` is the fail-closed field.** A grain that never computed a gate — roster always, plus any early return — must be distinguishable from one that computed and permitted, and **must not read as a permit**. Do not represent it by nulling fields; a nulled field is indistinguishable from an unset one (`.claude/rules/python-style.md`).
  2. **`refused_by` is UNIT-level and must not absorb per-id refusers**, which already live in `.refusals`. Folding them in loses *which* ids were held back.
  3. **The record keys exactly as `.refusals` keys on that grain** — scalar on game and roster, **keyed by `(table, team_id)` on player-line**, which is this story's own grain. **A uniform shape is the defect, not the goal**: two reviewers each reached for one in a single pass, in opposite directions. This record is also what makes each grain's operator-facing refusal WARN nameable (AC-13 here, AC-10 in stories 02 and 03) — the WARN renders *from* the record, never the reverse.
- **Produces for E-276-05**: the corrected invariant wording, which the CLAUDE.md replacement paragraph must carry per TN-10.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing. **The DISCRIMINATING tests — those in AC-1, AC-2, AC-4 and AC-14 — demonstrably FAIL against pre-fix code and PASS after.** Scoped deliberately: several required tests here cannot fail pre-fix and it is not a defect that they cannot. AC-3's `9/8` case refuses under both regimes (it is a floor, and the parametrization is discriminating as a set, not case-by-case); AC-5 asserts behaviour identical to today; AC-6, AC-7, AC-8, AC-9a and AC-9b test code that does not exist pre-fix, so "fails before" is not even well-defined for them. **A blanket fail-before/pass-after line would make this story's own Definition of Done unsatisfiable**, and an implementer meeting it literally would have to manufacture discrimination where none is available — the failure this epic exists to stop.

      **⛔ AC-14's ENTRY HERE WAS WRONG AND IS REPLACED WITH A THREE-WAY SPLIT** *(R1 disposition, 2026-07-26; both SE-R1 and DE-R1 ruled the old line wrong, independently)*. It read: *"Its **no-ratchet and recovery** assertions hold under both regimes and are regression guards, not discrimination."* **Two errors.** The **no-ratchet** assertion does not hold post-fix at all — **it fails, and that failure IS the residual** this epic accepts and documents; keeping it as a "regression guard" would have required an implementer to make a false property pass. And **recovery** does hold, but not as the old AC stated it (a recovery invocation **does** retire the churned ids, correctly — see AC-14's banner). **A two-way discriminating/non-discriminating split cannot express an assertion that pins an accepted defect**, which is why the category is added rather than the entries reshuffled.

      **The three categories, and every AC-14 assertion belongs to exactly one:**

      1. **DISCRIMINATES** — fails pre-fix, passes post-fix. **The per-run prior count**, asserted per invocation (18 pre-fix, 9 post-fix on the churn run). This is the assertion that earns AC-14 its place in the discriminating list above.
      2. **REGRESSION GUARD** — holds under both regimes; catches a future change, not this one. **Regime-A survival** (originals persist when the dedup sweep can merge the churn) **and recovery** (a recovery payload retires the churned ids and leaves the originals).
      3. **RESIDUAL PIN — NEITHER, and this category is new.** **Regime-B sequence assertions.** They do not discriminate the fix and they do not guard a passing property: they **pin an accepted, operator-ruled residual at its measured size** so a later change cannot worsen it silently. **Reporting these as either of the other two is an overclaim in opposite directions** — as discrimination it would claim the fix closes a window it does not, and as a regression guard it would imply a healthy property is being protected. **A test asserting that a known defect still behaves exactly as measured is a legitimate third thing**, and the epic now has one.

      **Applies equally to AC-15**: its WARN-fires assertion is a regression guard; nothing in it discriminates the fix, because the diagnostic does not exist pre-fix.
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] `data/app.db` untouched; no network; synthetic DBs from `migrations/` only

## Notes

Two framings worth keeping in view while implementing, both from the consultations:

The candidate/absent set is **already correct** today — this is a gate-population fix, not a delete-targeting fix. Widening it would be a mistake.

The existing test suite cannot see this defect because every existing shrink test uses a fresh set that is a strict subset of prior. That is why the new tests must drive the real producer with genuinely new ids, and why a helper-level test would not have caught it.
