# E-276 — Drafted replacement text for the conjunction removal (SE, for PM3)

> # ⛔ SUPERSEDED — EXECUTED WORK ORDER. NOT SPEC, AND NEVER WAS.
>
> **Marked 2026-07-25 at the fifth-pass edge-walk.** This file is **drafted replacement text plus instructions to a specific PM** (*"[PM3: relocate … here unchanged]"*). **Its edits were applied; the epic carries the result.** Read it only to audit how the conjunction removal was performed — never as a statement of current design.
>
> **The specific trap**: it quotes both the text being REMOVED and the text REPLACING it, side by side and often unlabelled as to which is which. **A reader arriving mid-file cannot tell a superseded quotation from a live one**, and its counts (*"`epic.md` 42, story 01 seven, story 02 six, story 03 zero"*) are a snapshot of a tree that no longer exists.
>
> **Found the same way as the triage handoff's marker**: an independent edge-walk found **five** `E-276-*` research files where the epic accounts for **two**. Both unaccounted files now carry a header; neither had one, and **`.project/research/` is outside story 05's sweep scope**, so nothing in this epic's own process would have reached them.

**Status**: draft for PM3 to write into `epic.md` and the stories. **SE does not edit epic or story files.**
**Scope**: TN-1(b), TN-5, TN-11's record, TN-10/TN-13 pass, the TN-19 collision, and the consequential ACs in stories 01 and 02.
**Method**: every claim verified against the files or by execution, not against the relay. Corrections to what I was handed are in §6.

> **⚠️ REVISION 2.** Revision 1 wrote game/player-line neutrality as a **SWEPT** result, on team-lead's brief. **That brief was wrong and team-lead has withdrawn it.** CR-2 refuted it before review, supplied the algebra, then attacked its own algebra and corrected an unnecessary assumption. I have since **executed** the corrected form. Neutrality on those grains is **structural**, conditional on a named premise. **If any of revision 1's "swept" tier reached the epic, it must come back out.**

---

## 0. What is actually stale, verified

The banner *"GATE SEMANTICS — RESOLVED PER GRAIN"* is **already correct** and carries the per-grain table. Story **03 is already V1-aligned**. Live conjunction references, per CR-2's count: **`epic.md` 42, story 01 seven, story 02 six, story 03 zero.**

| Site | Stale text | Fix |
|---|---|---|
| TN-1(b) | *"The gate is a CONJUNCTION… [SETTLED]"* | §1 |
| TN-5 blanket sentence (`epic.md:735`) | *"`legacy AND corrected`… never permits a deletion today's code refuses, on any grain and any input"* | §2 |
| TN-5 subsections | *"Why the conjunction earns its place"*, *"The conjunction still delivers the fix in full"* | demote to history — §2 |
| TN-11 record | `legacy_* / corrected_* / permitted = conjunction` | §3 |
| TN-10 / TN-13 | legacy half as a live conjunct | §4 |
| Story 01 | AC-8, AC-9a, AC-13 | §5 |
| Story 02 | AC-7, AC-10 | §5 |

---

## 1. TN-1(b) — replacement

> **(b) ONE GATE PER GRAIN. The candidate population is unchanged.**
>
> - **Candidate population = live prior, uniformly on all three grains.** Unchanged from today. **No intersection with the snapshot on any grain.**
> - **Game and player-line**: the gate is the **corrected gate alone** — the floor ratio over the **pre-upsert snapshot** population. The legacy live-population gate is **replaced, not conjoined**.
> - **Roster**: **no floor gate at all.** Its refusers are (i) an empty fresh payload and (ii) `MAX_ROSTER_DEPARTURES`.
>
> **The shape is no longer uniform, and that is the design.** Uniformity was never the goal — it was a property the superseded shape happened to have, and citing it as a virtue is how the conjunction survived three reopenings.

**Move to the superseded-shapes list**, verbatim:

> - the gate as `legacy AND corrected` on any grain — **the conjunction**, in every form: as a shape, as the basis of a neutrality proof, and as a value reaching `classify_absences`;
> - "the gate is one uniform shape across three grains";
> - any AC phrased as *"the legacy gate permitted and the corrected gate refused"*.

---

## 2. TN-5 — replacement. One premise, one proof, one predicted failure.

**Delete the blanket sentence.** Replace with:

> ### TN-5 — Deletion-neutrality — STRUCTURAL, conditional on `W ⊆ fresh`
>
> **Neutrality is not a blanket property and it is not a swept result. It is a two-line consequence of one premise — and the same premise predicts the grain where it fails.**
>
> Let `P_pre` be the pre-upsert snapshot, `W` everything the run writes into the delete scope, `F` the fresh set, and **`k = |W \ P_pre|`** — the rows the run *adds*, however written. Where `W ⊆ F`:
>
> ```
> P_post        = P_pre ∪ W
> |P_post ∩ F|  = |P_pre ∩ F| + k        (W ⊆ F, so W\P_pre joins the numerator)
> |P_post|      = |P_pre|     + k
>
> corrected permits:  |P_pre ∩ F|      >= 0.5·|P_pre|
> legacy LHS       =  |P_pre ∩ F| + k  >= 0.5·|P_pre| + k
>                                       >= 0.5·(|P_pre| + k)  = legacy RHS     ∎
> ```
>
> **Every added row contributes 1 to the legacy numerator and 1 to its denominator, and `1 ≥ 0.5·1`.** So the legacy gate permits whenever the corrected gate permits, at any sizes, with slack `0.5·k`. **The result is scale-free** — it holds at 2 games and at 200.
>
> **State it in `k`, never in "new rows".** Insert-vs-update is never distinguished, which matters because TN-1 already rejected a design requiring exactly that discrimination (`changes()`/`rowcount` will not give it under `ON CONFLICT DO UPDATE`). A reader told "new rows" will think the proof needs a distinction it does not.
>
> **All three gate conditions transfer, not only the ratio** — `crawl_is_authoritative` is a three-way AND:
> - `fetch_ok` — the identical signal for both, unmodified;
> - `fresh_count > 0` — corrected permitting implies `|P_pre ∩ F| > 0`; legacy's count is that plus `k`;
> - the ratio — above.
>
> | Grain | Neutrality | **Evidence tier** |
> |---|---|---|
> | **game** | holds | **Structural, given the named premise `W ⊆ fresh`** |
> | **player-line** | holds | **Structural, given the same premise** |
> | **roster** | **FALSE — deliberately** | **RULED**; and a **prediction of the same rule**, not an exception |
>
> **The premise carries its own honest tier and must keep it.** `W ⊆ fresh` is a **NAMED PREMISE, not a structural guarantee** — on game it rests on one `INSERT INTO games` path whose ids come from `summary.event_id` (a fresh schedule id or a canonical redirect target, both in `fresh_ids`); on player-line the written ids *are* the block's fresh ids. It could not be falsified across 179 runtime invocations, **which is not proof.** Story 02's runtime assertion is its guard. The chain: **neutrality is proved from `W ⊆ fresh`; `W ⊆ fresh` is a named premise with a runtime guard; the sweeps are corroboration, not load-bearing.**
>
> #### Scope the claim to DELETIONS, not to permits
>
> State neutrality as *"never permits a **deletion** today's code refuses"* — never as *"permits whenever today permits."* The two gates **genuinely disagree** in one region: at `P_pre = ∅` **and** `W = ∅`, the corrected gate permits vacuously (TN-1(c)) while the legacy gate refuses on its `fresh_count > 0` check.
>
> **The region is protected TWICE, and the two protections fail differently — so record both:**
>
> 1. **Empty candidate set.** **Executed: 32 such cases, and in all 32 `P_post = ∅` — 0 of 32 have anything to delete.** [EXECUTED, SE]
> 2. **Unreachable in the implementation.** All three helpers early-return on an empty *live* prior before any gate is computed — `retire_absent_games` (`if not prior_ids: return result`), `retire_absent_player_lines` (`if not prior_ids: continue`), `retire_departed_roster_players` (same, post-exempt-filter). `P_post = ∅` never reaches `crawl_is_authoritative` at all. [CR-2]
>
> **Why both**: protection 1 survives a refactor that removes the early return; **protection 2 does not.** Recording only the unreachability would leave the claim resting on a guard someone may delete as redundant.
>
> **And the reachable sub-case is fine on its own terms**: at `P_pre = ∅` with `W ≠ ∅` — the first-ever load — legacy's population is `W`, `|W ∩ F| = |W| >= 0.5·|W|`, and **both gates permit**. The disagreement is confined to the doubly-protected corner.
>
> Recorded because a future reader checking *gates* rather than *deletions* will find a real disagreement and conclude something is broken.
>
> #### The roster grain — the premise is FALSE, and the failure follows from it
>
> On roster `W ⊄ F`: the jersey backfill writes rows the fresh roster crawl never listed, so churn rows land in the legacy **denominator only** and make the legacy gate *stricter* than the corrected one. Executed [DE's construction; CR-2 re-derived independently]:
>
> ```
> snapshot 10 · fresh 8 · churn 20  →  live prior 30
>   today (legacy floor):  8 >= 15   REFUSES  → deletes 0
>   V1  (no floor):                  PERMITS  → deletes 22, of which 2 are PRE-EXISTING
> ```
>
> **This is the fix working as ruled, not a regression.** The operator ruled prefer-delete on this grain: today's alternative is not safety but a **permanent strand** — the same construction re-run leaves the roster wrong forever, while V1 converges on the only evidence available. The 2 pre-existing rows are bounded by `MAX_ROSTER_DEPARTURES` as a **per-invocation rate, not a total** (TN-19).
>
> **This is why the statement is not a carve-out.** The property holds by construction everywhere it holds at all, and where it fails it fails for a stated structural reason: `W ⊄ F`. One premise produces the guarantee *and* its failure — which satisfies TN-5's original anti-carve-out requirement rather than breaking it.
>
> **Scale, with its limit stated.** An exhaustive roster sweep found **862 neutrality violations across 6560 reachable combinations** (four parameters over `0..8`, less the degenerate case) for the **corrected-gate-only** shape. **That is a LOWER BOUND for V1, not V1's count** — so `violations(V1) ⊇ violations(corrected-only) ⊇ 862` within the swept space, and V1's exact figure is **unmeasured**. Do not report 862 as V1's number.
>
> **State the MECHANISM, not "no floor is more permissive"** [CR-2's sharpening, adopted]. The relation holds because **V1 drops two conjuncts and adds none**:
>
> ```
> corrected-only = fetch_ok ∧ (|P_pre ∩ F| > 0) ∧ (|P_pre ∩ F| >= 0.5·|P_pre|) ∧ cap
> V1             = fetch_ok ∧ cap
> ```
>
> Same `fetch_ok` (`bool(fresh)`), same cap, two conjuncts removed — so V1 cannot refuse where corrected-only permits. **A future edit that dropped the floor while tightening `fetch_ok` would falsify the relation**, which is why the mechanism is stated rather than the slogan.
>
> **Tier: proved, contingent on three identities — and DO NOT try to execute it.** The relation reduces to `A ∧ B ⟹ A`, which cannot fail, so sweeping it over a grid would sample a tautology and return a zero that means nothing. (Same argument that demoted the 0-of-2197 sweep below the algebra, applied here.) Its real content is three identity checks, all verifiable by reading:
>
> 1. `fetch_ok` is the same signal in both designs — `bool(fresh)` on roster. ✓
> 2. The cap is the same — `roster_departure_guard(absent ∩ previously)`, untouched. ✓
> 3. **The candidate set is the same** — live prior under both, so `absent`, and hence the cap's input, are identical. ✓
>
> **Check 3 is the only one a future edit could falsify**, and it is named here for that reason: if V1 ever changed the candidate population, the cap would see a different set and the subset relation would not transfer.
>
> **Tier label, stated exactly** — mirroring TN-5's own form: **proved from three identity premises, of which only the candidate-set identity is falsifiable by a future edit.** **Do NOT label it "derived but not executed"** — that implies execution is a missing rung it could be promoted by, and it is not: the implication is a tautology and a run would return a meaningless zero. Not executing it is the correct disposition, not a gap.
>
> #### Verification tiers, stated separately so no sentence carries two
>
> | Evidence | What it covers | Tier |
> |---|---|---|
> | The algebra above | all sizes, both grains | **proof**, conditional on `W ⊆ F` |
> | Exhaustive set-structure execution — **0 violations in 55,728 combinations**: all `(P_pre, F, W)` with `W ⊆ F` over universes of 4, 5 and 6 elements [EXECUTED, SE] | set *structure*, not merely counts | **corroboration** |
> | The pre-existing parameter sweep — **0 violations / 2197 combinations**, three parameters over `0..12` | counts only, and **`0..12` does not reach a 20–30 game season** | **corroboration; cite with its range or not at all** |
> | The same execution with the premise **removed** (`W` unrestricted) — **296 violations at n=4, 2890 at n=5** [EXECUTED, SE] | the roster grain | **the failure is reproducible, not hypothetical** |
>
> #### Historical — the conjunction, and why it was dropped
>
> [PM3: relocate *"Why the conjunction earns its place"* and *"The conjunction still delivers the fix in full"* here unchanged, under this heading. Add one sentence:]
>
> **The conjunction's decisive argument was that DE's whole-set construction refuses under it, deleting 0. That is now precisely the behaviour the operator ruled AGAINST on roster.** The argument was sound and the objective changed underneath it — history, not error.

**Preconditions**: (a)–(d) survive in substance, but **(a) must be rescoped** — it says the legacy gate is untouched by vacuous-permit, and there is no legacy gate. Restate: *vacuous-permit applies to the corrected gate on game and player-line; roster has no gate for it to apply to.* **(e) is already recorded as MOOT under V1** and is correct as written.

---

## 3. TN-11 — the record, redesigned for one-gate-per-grain

Under one gate per grain there is no second conjunct, and **roster has no gate at all**, so a two-gate record cannot serve all three.

> | Field | Meaning |
> |---|---|
> | `gate_evaluated` | **`False` for roster always, since roster runs no floor gate** — and `False` for any grain that early-returns before evaluating one. **MUST NOT read as a permit.** |
> | `gate_permitted` | the gate's verdict, or `None` when `gate_evaluated is False` |
> | `gate_prior_count` | the denominator used — **the pre-upsert snapshot**. **The numeric tell**: pre-fix the WARN reads 18 where the true pre-run population is 9 |
> | `gate_comparable_count` | the numerator used |
> | `refused_by` | **UNIT-level refusal only** — `None` \| `"gate"` \| `"cap"` \| `"boxscores_incomplete"` \| `"empty_payload"` \| `"fetch_not_ok"` |
> | `permitted` | the value the code acted on; carried though derivable, so a test asserts the acted-on value rather than recomputing it |

> **⚠️ THE RECORD IS NOT SCALAR ON EVERY GRAIN — it keys exactly as `.refusals` keys** [CR-2 found this; SE verified in source]. Revision 3 said "a single record carried by all three grain dataclasses", which is **unit-level and wrong for player-line**. `retire_absent_player_lines` evaluates the gate inside a **double loop** — `for block in blocks:` × `for label, table in _PLAYER_LINE_TABLES:` — calling `crawl_is_authoritative` per `(block, table)`, i.e. **up to four independent gate evaluations per call**, each with its own `prior_count`, `comparable_count` and verdict. A scalar `gate_prior_count` would capture only the last iteration.
>
> **This breaks a live AC.** Story 01 AC-2 requires asserting *"the protected count equals the pre-run population (9), not the post-upsert population (18)"* — with both blocks present, a scalar field cannot make that assertion unambiguous, and that count **is** the numeric tell the AC exists to pin.
>
> **The rule that gets all three grains right in one sentence:**
>
> > **The gate-outcome record keys exactly as `.refusals` keys on that grain** — both derive from the same loop structure.
>
> | Grain | Gate evaluations per call | Record keying |
> |---|---|---|
> | game | one, whole-pass | scalar `gate_*`; per-id refusals in `.refusals[game_id]` |
> | **player-line** | **up to four** (2 blocks × 2 tables) | **`gate_*` keyed by `(table, team_id)`**, matching `result.refusals[(table, block.team_id)]` |
> | roster | none under V1 | scalar, `gate_evaluated = False` always |
>
> This also disposes of the `.refusals` / `.refused` plural asymmetry **without a special case**: roster carries `.refused` because its decision is whole-set, and its gate record is scalar for the same reason.
>
> **Note the symmetry, because it is this epic's shape once more**: SE corrected CR-2 for treating a per-id refuser as unit-level, and CR-2 corrected SE for treating a per-block gate as unit-level. **Both errors came from assuming one uniform record** over a module whose own docstring states the three grains model refusal differently and deliberately.
>
> **⚠️ `refused_by` is UNIT-level and MUST NOT absorb the per-id refusers** [CR-2 found the gap; SE verified in source and revised the repair]. Revision 2's enum was not exhaustive, and the reason is a category error rather than a missing member:
>
> - **Per-id refusers already have a home.** `_game_is_cross_perspective_protected` (`reconcile_at_load.py` :655, :779) and `not_final` (:707) refuse **individual ids**, and each already writes `result.refusals[game_id] = reason`. `GameRetireResult.refusals` and `PlayerLineRetireResult.refusals` exist for exactly this. **Folding them into a scalar `refused_by` would lose *which* ids were held back** — strictly worse than today.
> - **So the exhaustiveness requirement splits.** `refused_by` answers *"did this grain refuse as a unit, and why?"*; `.refusals` answers *"which ids were individually protected, and why?"* **A test asserting "0 retired" must check BOTH** — that is the wrong-reason trap's real closure on the game grain, and neither field alone provides it.
> - **`boxscores_incomplete` IS a genuine missing member** and must be added: it is a separate `retire_absent_games(..., boxscores_complete=...)` parameter, distinct from the cap, and the existing WARN already distinguishes them *because the remedies differ*. Reporting it as `"cap"` would be false.
> - **Note the grain asymmetry**: the module docstring records that two grains carry `.refusals` and roster carries `.refused` (singular). The record must not assume a uniform plural.
>
> **⚠️ AND TWO ROSTER PATHS PRODUCE NO RECORD AT ALL — this is the sharper half.** In `_reconcile_departed_roster`, **both** `if not fresh_player_ids: … return` and `if exempt_player_ids is None: … return` occur **before** `retire_departed_roster_players` is ever called [SE-verified in source]. So on the grain with no gate, two of the mechanisms that produce "0 retired" sit **upstream of the record meant to disambiguate them** — a fail-closed skip producing exactly the symptom the trap exists to catch, with the record structurally blind to it.
>
> **Required**: the wrapper **synthesizes a result** carrying `refused_by="empty_payload"` / `"skipped_no_exemption_plan"` for those two paths. If PM3 prefers not to mandate the synthesis, TN-11 must instead state explicitly that these paths produce no record and name what a test asserts instead. **Silence is not an option** — it is how the ambiguity re-enters through a different door.

> **`legacy_*` is GONE**, and `refused_by` replaces its discriminating power while generalizing it: the wrong-reason trap was never about legacy-vs-corrected, it is that **several mechanisms each produce "0 retired"**. Naming the mechanism beats inferring it from two booleans, and it is **the only formulation that works on roster**.
>
> **`gate_evaluated` is the fail-closed field**, replacing a `None` a reader may coerce. **Do not merely null the old `legacy_*`/`corrected_*` fields for roster** — a nulled field is indistinguishable from an unset one, which is this codebase's documented missing-safety-signal shape (`.claude/rules/python-style.md`).

**Fixture table**: `legacy | cap | corrected` → **`today | cap | gate`**. The roster row needs relabelling, not deleting: roster now has **no** gate, so the 2-stored/2-brand-new fixture no longer discriminates a gate — **it discriminates the reversal.**

---

## 4. TN-10 and TN-13

**TN-10** is about necessary-vs-sufficient conditions and is **not conjunction-dependent**. Strike only the phrase describing the legacy half as a live conjunct; the invariant sentence stories 01 and 05 bind verbatim must not change.

**TN-13's calibration** → replace:

> **Calibration, recorded honestly** [CR]: applying vacuous-permit unconditionally would not widen the gate *in production*, because all three helpers early-return on an empty live prior, so the gate is never reached with `prior_count == 0`. **The unit test still fails**, which is why the mechanism is specified. The earlier form justified the conditionality by keeping a *legacy conjunct* at today's semantics; there is no legacy conjunct, and the calibration stands on the early-return alone.

---

## 5. Consequential ACs

**Story 01 AC-8** →

> **AC-8 (deletion-neutrality — player-line grain, STRUCTURAL given a named premise)**: The fix never permits a **deletion** that today's code refuses **on this grain**. This holds **by construction from `W ⊆ fresh`** (TN-5's two-line proof), **not** from a conjunction and **not** from a sweep. Assert the algebra at the primitive level; the ported sweeps are corroboration. **The blanket "on any grain and any input" form is STALE and must not be reinstated — it is false on roster.**

**Story 01 AC-9a** → object changes: *Exactly one gate **value** reaches `classify_absences`* — ~~the conjunction~~ → **the corrected gate's verdict**. Pin with a test.

**Story 01 AC-13 / Story 02 AC-10** — requirement survives, rationale changes: discrimination is carried by `refused_by`, and the WARN is rendered from it. **Strike *"the discrimination the conjunction degrades"* from both titles**; the reason is several mechanisms producing "0 retired".

**Story 02 AC-7** → as AC-8, scoped to the game grain, **keeping its porting obligation** — the 0-of-2197 result still lives only in a scratchpad. Its status changes from *sole support* to *corroboration*, so the port is no longer load-bearing for the claim, but **it must carry its `0..12` range** wherever cited.

---

## 6. Corrections to what I was handed, and findings

1. **Team-lead's "swept, not structural" brief was wrong** — withdrawn by team-lead, refuted by CR-2. Drafted as given, it would have written a **weaker and under-covering** safety claim: the sweep's `0..12` range does not reach a 20–30 game season, so the evidence would have stopped short of the inputs it covers.

2. **CR-2's correction to its own proof is right and I adopted it** — the assumption `new ∩ old = ∅` is false (a re-scout UPSERTs) and unnecessary. Restating in `k = |W \ P_pre|` also keeps clear of the insert-vs-update trap TN-1 already rejected.

3. **CR-2's vacuous-permit attack reaches the right verdict by an incomplete argument — corrected here.** CR-2 argued no hole exists because *"legacy's population is `W`, and `|W ∩ F| = |W| >= 0.5·|W|`, so legacy permits too."* That covers `W` **non-empty**. **Executed, there are 32 cases where the corrected gate permits and the legacy gate refuses** — all at `P_pre = ∅` **and `W = ∅`**, where legacy fails the `fresh_count > 0` check that vacuous-permit bypasses on the corrected side. **The verdict still holds**: every one has `P_post = ∅`, so **0 of 32 have a non-empty candidate set** and no deletion is permitted either way. Hence the scoping requirement in §2 — state neutrality over *deletions*, not *permits*.

4. **The 862 sweep flips from historical to live.** `epic.md` says *"the 862 sweep (now historical, since the conjunction closed those cases)"*. The conjunction is gone; **those cases are open again**, and the sweep is now the measurement of how roster neutrality fails.

5. **862 is a LOWER BOUND for V1, not V1's count** (§2). Reporting it as V1's figure would be this epic's signature defect inside its own remediation. I derived the strictness relation (V1 ⊇ corrected-only in permits) rather than executing it — **flagged as the weakest link in this draft.**

6. **The TN-19 collision is already resolved in the epic**, which carries an explicit note on the renumbering. The stale reference was in **SE's** artifact and is corrected. The non-droppable rider — *"the cap is locked" carries zero adequacy content* — is present and intact.

7. **Sweep hazard**: `zero adequacy` greps to nothing; the epic hyphenates it as `zero-adequacy-content`. Same class as the emphasis hazard. Strip emphasis and expect hyphenation variants when verifying these files.
