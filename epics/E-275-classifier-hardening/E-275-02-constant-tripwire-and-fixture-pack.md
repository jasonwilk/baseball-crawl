# E-275-02: Constant divergence tripwire and the ground-truth fixture pack

## Epic
[E-275: Classifier Hardening](epic.md)

## Status
`TODO`

## Description

After this story is complete, a change to any one of the three byte-identical pitch-count constants will fail a test independently of the other two, and that failure will name its downstream consequence rather than merely reporting inequality. The repository will also carry a ground-truth fixture pack: operator-labeled input shapes, each paired with the league label a human says is correct, executed as a test and structured to be appended to across future classifier changes.

## Context

**Why the pack is the point of this epic.** Both classifier defects found in the last month -- the `ngb=american_legion` shadow of NRBL, and the `varsity` shadow of the Legion patterns -- were found ONLY by comparing behavior against ground truth. A green suite and two closure reviews caught neither. The pack institutionalizes the one instrument with a track record here.

**This story is "close two MEASURED gaps," not "add a tripwire."** The distinction is not cosmetic: the tripwire as originally proposed would have been **vacuous on the day it shipped**. `tests/test_league_detection.py` already contains `TestNrblRules::test_nrbl_is_distinct_constant_from_legion` and `TestGetRulesForLeague::test_pitch_smart_is_distinct_constant_from_legion`, and the first already asserts everything the proposal described **and one thing more** (`NRBL.rest_tiers is not LEGION.rest_tiers`, a structure-sharing check the proposal never mentioned). Writing it would have produced a passing test that could never fail against current code.

SE proved the shipped test *does* fire, by rewriting the source and importing mutants with a verbatim positive control and a per-mutant applied-check: **four of four mutants caught, by four different assertions.** It then measured two gaps that escape everything:

> **Gap A -- the relative-only test cannot see a tandem edit.** All four assertions in `test_nrbl_is_distinct_constant_from_legion` compare NRBL *to LEGION*. A change that edits both constants together preserves every relation and passes the test completely -- and a tandem edit is precisely the scenario the source comment warns about. Executed: mutant M6 edited the same tier in both constants and the entire NRBL test passed; it was caught only by LEGION's literal pin. **A relative assertion certifies that two things agree, never that either is right.**

> **Gap B -- a declared-cap divergence is caught by nothing and is behaviourally silent.** `test_pitch_smart_is_distinct_constant_from_legion` omits the `max_pitches` assertion its NRBL sibling carries. Executed: mutant M7 changed `PITCH_SMART_15_18.max_pitches` from 105 to 95 and **every existing assertion still passed**. No behavioural test could have caught it either, because `_is_excluded` never reads `rules.max_pitches` -- the required-rest curve was unchanged at all 130 counts.

**M7 is this story's named fail-first discriminator**: a `PITCH_SMART_15_18.max_pitches` divergence passes every test in the repo today and fails the proposed pin.

**Pin coverage across all six `PitchCountRules` constants** (SE, measured): `LEGION` pinned (`test_starter_prediction.py:1471-1481`); `NSAA_SUBVARSITY` pinned twice; **`NRBL` and `PITCH_SMART_15_18` unpinned** -- the two members of the byte-identical trio this story must close. `NSAA_PRE_APRIL` and `NSAA_POST_APRIL` are also unpinned but sit outside the divergence-tripwire rationale (nothing is supposed to track them); **recorded, deliberately not scoped in.**

`LEGION`, `NRBL` and `PITCH_SMART_15_18` are three separate constants that are byte-identical today by coincidence of their sources, and each carries a comment saying the identity is not to be relied on.

**WHY THE LITERAL PINS EARN THEIR PLACE — and it is not "constants drifting apart" (SE, executed 2026-07-27; added during the trim pass, absent from every earlier draft of this story).**

A tier-boundary typo does not produce a crash or a wrong-but-plausible number. It produces **zero required rest, silently.** `_is_excluded`'s `for/else` fall-through guards only `total_pitches > max_tier.max_pitches` — the **TOP** tier — so a count landing in a **mid-table gap** matches no tier, skips the fall-through, and `required_rest` keeps its initialiser of `0`. Executed on a deliberately gapped table (LEGION's third tier narrowed to 46-55):

```
counts 56-60, GAPPED table      -> [0, 0, 0, 0, 0] days required   SILENT ZERO
counts 56-60, well-formed table -> [2, 2, 2, 2, 2] days required
```

**A malformed tier table under-rests silently rather than erroring** — green suite, no exception, a zero-rest recommendation on a real arm. That is the one direction this codebase treats as unacceptable. **On `NRBL` and `PITCH_SMART_15_18` — the two constants this story pins — nothing else stands between a typo and that outcome.**

> **LATENT, not live, and that is MEASURED rather than assumed.** SE verified all six shipped tables are contiguous (first tier starts at 1; every tier's `max_pitches + 1` equals the next tier's `min_pitches`). The hazard is purely "someone edits badly." Benign contrast: `p=0` and negative counts also match no tier and correctly yield 0, because the fall-through's `> 0` guard makes those safe — **only mid-table gaps are the defect.**
>
> **⚠️ These pins do NOT close the underlying hazard, and this story must not be read as closing it.** They detect a *changed value* on two constants; they do not defend the **gate**, which will keep accepting a malformed table from any source — including tables that do not exist yet. The structural fix (a contiguity invariant at table-definition time, or a gate that refuses an unmatched count) is different in kind and outlives this epic. Filed as **[[IDEA-212]]**; deliberately not scoped in here.

## Acceptance Criteria

### The tripwire

- [ ] **AC-1**: Each of `LEGION`, `NRBL` and `PITCH_SMART_15_18` is pinned to its literal **`PitchCountRules.max_pitches`** value and its literal `rest_tiers` values, such that changing **any one** of the three fails a test **without** depending on comparison to the other two.

  > **The field is named explicitly because "maximum" was ambiguous between two of them** -- `PitchCountRules.max_pitches` and `RestTier.max_pitches` both exist in this module. SE confirmed by execution which is which: **the exclusion gate reads `RestTier.max_pitches` only** (tier selection and the past-top-tier clamp); `PitchCountRules.max_pitches` is never read by `_is_excluded`, and its only reads anywhere in `src/` are display strings inside `format_nsaa_rest_table`. Setting the rules-level field to 60 leaves the required-rest curve identical at all 130 counts.

  > **PIN THE CONSTANT WHOLE, AND DO NOT CHARACTERISE THE FIELD.** Assert `max_pitches` and `rest_tiers` together as one literal object -- e.g. `test_nrbl_constant_literal_values` -- rather than field by field. **The test NAME is the adjacent prose, more than any comment is**: `test_nrbl_max_pitches` singles the field out and puts "max" in the reader's eye, inviting exactly the inference TN-8 exists to prevent. A whole-object pin highlights no field, says nothing about caps or enforcement, and is a stronger assertion besides.
  >
  > *(Two alternatives were considered and rejected. A comment stating the field is display-only: TN-8 drops the daily-cap claim **entirely**, "not demoted to constants-level color, because a reader can infer enforced behavior from adjacent prose" -- and a test comment is precisely that. SE, who supplied such comment text when the question was how PM should state the executed fact, agrees it does not belong here: the executed fact already lives in TN-8, and a reader who needs a test comment to tell them the field is not enforced is a reader the test's existence invited to wonder.)* **Discriminates**: today a change applied identically to all three passes the entire suite. The fail-first demonstration is to move all three together and observe that the existing pairwise tests still pass while the new pins do not.
- [ ] **AC-2**: The pairwise relationships are still asserted, so an edit to one constant alone is caught by both the pin and the pairwise check. **The two sibling tests must be SYMMETRIC**: `test_pitch_smart_is_distinct_constant_from_legion` must carry the `PITCH_SMART_15_18.max_pitches == LEGION.max_pitches` assertion that its NRBL sibling already carries. **Catches**: a remedy that replaces the existing tests instead of adding to them -- this AC fails if either sibling is deleted or weakened.

  > **Why symmetry, when the literal pin already detects it.** The added assertion is **redundant for detection** -- M7 (the `PITCH_SMART_15_18.max_pitches` mutant that escaped every existing test) is caught by AC-1's pin alone. Its value is structural: **the M7 gap existed precisely because the two siblings were asymmetric.** One carried a `max_pitches` equality and the other did not, and that single omission is the entire reason a cap divergence could ship unseen. Symmetry is the cheap guard against the same omission recurring when someone adds a fourth constant by copying whichever sibling they happen to open.

  > **⚠️ THE INVERSE RISK, and it is the one that will actually bite.** **The pairwise equalities are the divergence SIGNAL; the literal pins are the DETECTOR, and neither substitutes for the other.** Do not later drop a literal pin on the grounds that the pairwise assertions cover it -- **a tandem edit that changes both constants together passes every pairwise assertion** and is caught only by the pins (SE's mutant M6, executed: it edited the same tier in both constants and the entire NRBL test passed).
- [ ] **AC-3**: When a `LEGION`/`NRBL` divergence fails, the failure identifies the downstream consequence -- that `ngb=american_legion` resolves before the NRBL branch is reachable, so a deliberate divergence would serve NRBL-eligible teams the Legion curve regardless of which constant was edited. **Discriminates**: no existing artifact states this. It is the gap named in TN-10; a failure that reports only "these differ" leaves the engineer who deliberately diverged them to update the test and never learn what broke.

### The fixture pack -- Tier 1 (executes)

- [ ] **AC-4**: A ground-truth fixture pack exists as an executed test, in which each row pairs a set of `detect_league_level` inputs with the league label a human has certified as correct, and each row is labeled **CHANGE** (fails against pre-E-275-01 code, passes after) or **GUARD** (passes both; must not move). **Catches**: an unlabeled pack, in which a row that proves nothing is indistinguishable from one that proves the fix.
- [ ] **AC-5**: Tier 1 covers, at minimum, **the six Tier 1 shape families enumerated in TN-16** (added there 2026-07-27 -- this citation previously dangled, because TN-16's Tier 1 paragraph enumerated nothing and its only six-member list was the **Tier 2** member list, so a reader chasing it landed on a plausible-looking wrong list of the same length; TN-16 is authoritative if the two copies drift apart). They are: mapped travel brackets across their bins; the free-text age-range form; the recognized-`ngb` values including one genuinely unmapped `ngb` string proving the generic-unknown copy; the name-word conflict shapes from E-275-01 across all four non-summer season values plus summer; the bracket-versus-name-word conflict shapes; and the no-signal fallthrough. **Catches**: a pack that covers only the shapes this epic changed, which would not be a ground-truth instrument.
- [ ] **AC-6**: Every Tier 1 row's expected label is the human-certified label, not the current output. Where the two differ, the row belongs in Tier 2. **Catches**: a pack generated by recording current behavior, which would lock in defects instead of detecting them -- specifically the bare-`seniors`-on-a-school-team misfire, which must NOT appear in Tier 1 as correct.
- [ ] **AC-9**: Each Tier 1 row distinguishes whether its expected value is a **CRITERION** (a human has ruled this is the right answer) or **EVIDENCE** (this is what the classifier does today, recorded so a change is detected, with no claim that it is domain-correct). **Catches**: the pack being read as a coaching endorsement of behaviour nobody has ruled on.

  > **Why this is a whole-pack requirement and not a note.** The same conflation was caught by coach in a single AC in story 01 -- the 14U bracket row, whose `youth_travel` value records today's precedence behaviour while coach's own ruling says that band should suppress. **A fixture pack is that trap at scale**: every Tier 1 row asserts a currently-produced value, and a reader has no way to tell which rows encode a ruling and which merely encode the status quo. Without the distinction, "the pack is green" gets read as "a coach approved all of this." The rule is the one in `.claude/rules/tool-output-integrity.md`: **correct a criterion, preserve evidence** -- and you cannot apply it to a row whose kind is unmarked.

### The fixture pack -- Tier 2 (recorded, NOT asserted)

- [ ] **AC-7**: Shapes that coach has ruled but the code does not implement are carried in the same file as a data block that is **not executed as an assertion**, each with its ruled label and a citation to the ruling. Members are listed in TN-16. **Catches**: both failure modes -- asserting them (a red suite at closure) and omitting them (the rulings evaporate).
- [ ] **AC-8**: The pack documents its append-only contract: rows are added as classifier behavior is extended, and an existing row is changed only when the human-certified label itself changes, never to match new output. **Catches**: the pack being "fixed" to match a regression.

### The safety property -- scoped to the fixture rows this story builds

- [ ] **AC-10**: **No fixture row's post-fix league requires strictly less rest than its pre-fix league, at any pitch count** -- and **at least one row requires strictly MORE**, so the pair cannot be satisfied by a pack of rows that all resolve identically. Assert against SE's measured curves, citing the execution, never against the comment block preceding `_SUMMER_SEASON` (TN-8). The correct phrasing is *never under-rests*, **not** *over-rests*; the divergence is **four items**, not three (TN-7's verbatim -- 46-50, 61-70 and 81-90 post-April, plus every count from 81 upward unbounded pre-April). **Catches**: a pack that adds a row whose expected label quietly loosens the rest requirement for a shape the reorder touches.

  > **Why this AC exists here and not only in story 01.** This is the one property TN-7 exists to protect, and until 2026-07-27 **every one of its marked locations sat in the epic or story 01** -- TN-7 itself, story 01 AC-12, the epic Success Criteria, and story 01's DoD. **The story that actually builds the fixture rows carried none of them**, and did not even list TN-7 among its context files. Resolve the property in its marked locations and the pack -- the thing the property is *about* -- was left unconstrained, with nothing red to show for it. Story 01 AC-12 now carries the **name**-scoped form; this AC carries the **fixture-row** form; TN-7 names all three locations.

## Technical Approach

The tripwire and the pack both live in the existing league-detection test module unless there is a reason to separate them; the pack's structure should make it obvious where a new row goes, since its value depends on future contributors actually appending to it.

**The pack ABSORBS story 01's name-conflict tests; it does not duplicate them.** AC-5 requires Tier 1 to cover "the name-word conflict shapes from E-275-01 across all four non-summer season values plus summer" and "the bracket-versus-name-word conflict shapes". Left unstated, an implementer arriving second has to guess, and both guesses are defensible. **Absorption is the call**: TN-16 frames the pack as the durable append-only instrument, and two independent encodings of one behaviour drift apart, with the un-updated one being the one that runs.

> **⚠️ ABSORPTION IS PARTIAL, AND THE BOUNDARY IS NAMED HERE BECAUSE AN UNQUALIFIED "ABSORBS" HAS TWO DEFENSIBLE READINGS** — absorb all seven of story 01's original rows, or absorb none and duplicate. The trim pass (2026-07-27) settled it:
>
> | | where it lives | what this story does |
> |---|---|---|
> | **AC-1, AC-2** (the CHANGE rows) and **AC-4, AC-5** (the two realistic-wrong-implementation guards) | written as tests in **E-275-01** | **fold them into pack rows** — re-home, do not re-write, do not leave two encodings standing |
> | **the old AC-3, AC-6, AC-7** | **RELOCATED here**; they no longer exist in story 01 | **author them as pack rows** — this story is their only home |
>
> **The three relocated rows, so none is lost in transit:**
> 1. **the summer-branch guard** (old AC-3) — the AC-1/AC-2 names under `season="summer"` resolve `legion` both before and after. **Catches** a "fix" implemented as a season-conditional special case inside the varsity branch instead of as a list reorder — the shorter route to green than re-ordering a list, and one that will not survive the next season-vocabulary change.
> 2. **Legion + `reserves?`** (old AC-6) — e.g. `"Morvath Legion Reserves"` → `nrbl` under summer, `nsaa_subvarsity` under the four non-summer values, unchanged in every branch. **Catches** the front-of-list over-move, on the one collision shape that actually occurs in the real corpus (5 names, TN-6).
> 3. **the four bracket rows** (old AC-7) — `"Wexlom 14U Legion Varsity"` → `youth_travel`; `"Quorrin 14U Post 41 Varsity"` → `youth_travel`; `"Quorrin 16U Post 41 Varsity"` → `nrbl`; `"Quorrin 17U Post 41 Varsity"` → `legion`. The first three **discriminate** against an implementation that hoists Legion matching ahead of the age-bracket ladder; **the 17U row CANNOT FAIL and is bin coverage only** — any 17U-or-above row is inherently non-discriminating for this defect, for every Legion pattern, because the bracket resolves 17U+ to `legion`, the same value a wrong implementation returns. The `16U` row discriminates *while* covering a third bin, and 15U-16U is adjacent to `_BRACKET_LEGION_MIN = 17`, so an off-by-one there surfaces at that row and nowhere else. **Three bracket bins (14U, 16U, 17U) and both moved patterns are required.**
>
> **These three carry WRONG B's only executable guard** — the hoist-ahead-of-the-bracket-ladder implementation. Story 01 can no longer catch it by test and says so.
>
> **AC-9's per-row CRITERION/EVIDENCE marking applies to all of them, and it SUBSUMES an obligation that was owed against the old AC-7's prose.** In particular: **the `youth_travel` on both 14U rows is EVIDENCE, not a CRITERION.** It records what the classifier does today. It does **not** endorse `youth_travel` as domain-correct for that band — baseball-coach's URGENT CORRECTION rules 8U-14U should **suppress**, and that fix is out of scope and unfixed ([[IDEA-208]]). A reader taking those rows as coach's endorsed answer has it exactly backwards. **The prose clause this replaces had already gone stale once** (it said "the 14U row" after the table grew to two 14U rows, and omitted the 16U row entirely); a per-row marking cannot go stale as rows are appended, which is why it is the better encoding.

**The dependency is scoped, not whole-story.** `Blocked by: E-275-01` binds **AC-4 through AC-10** (the pack asserts post-fix labels). **AC-1, AC-2 and AC-3 -- the constant tripwire -- have no dependency on E-275-01 whatsoever** and may be implemented before it lands. They were bundled here for cohesion, not sequence, and nothing about the precedence fix gates them.

The exact form of the constant pins -- literal values per constant plus the retained pairwise assertions -- is being supplied by software-engineer and is recorded in the epic as OQ-2. **Do not begin AC-1 or AC-2 before that lands**; a relative-only assertion is the failure mode this story exists to close, and E-272-01 already paid for it once.

Context files to load: this epic's Technical Notes (TN-6, **TN-7**, TN-8, TN-9, TN-10, TN-11, TN-16, TN-17 -- TN-7 and TN-8 were absent from this list until 2026-07-27, which is how the safety property came to have no surface in the story that builds the rows it is about); `/tmp/.worktrees/baseball-crawl-E-275/.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md` for every Tier 2 label and its reasoning (RULING 1 for the `age_group` vocabulary, RULING 2 for `little_league`, RULING 3 for USSSA/Perfect Game, the RULING 4 AMENDMENT for the `seniors` misfire); `/tmp/.worktrees/baseball-crawl-E-275/.project/ideas/IDEA-178-ngb-american-legion-shadows-nrbl.md` for the shadow consequence in AC-3.

## Dependencies
- **Blocked by**: E-275-01, **scoped to AC-4 through AC-10 only** (Tier 1 CHANGE rows assert post-fix labels). **AC-1, AC-2 and AC-3 (the constant tripwire) are NOT blocked** and may be implemented first -- see Technical Approach.
- **Blocks**: None

## Files to Create or Modify
- `tests/test_league_detection.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] AC-1 demonstrated fail-first by moving all three constants together and showing the existing pairwise tests pass while the new pins fail -- a demonstration, not an assertion that it would fail
- [ ] Every Tier 1 CHANGE row demonstrated to fail against pre-E-275-01 code
- [ ] **AC-10 demonstrated as a PAIR** -- the "never strictly less" half alone is vacuously satisfiable by a pack whose rows all resolve identically, so a demonstration showing only that half has shown nothing
- [ ] **AC-9 verified per row**: every Tier 1 row carries a CRITERION/EVIDENCE marking. An unmarked row fails this line
- [ ] Tier 2 confirmed non-asserting: the suite is green with the block present and unimplemented
- [ ] Tests written and passing
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes

Every name in the pack is a constructed sentinel per TN-17 -- invented tokens only, and specifically NOT the `Anytown`/`Springfield`/`Example` taxonomy from `.claude/rules/api-docs.md`. **The reason is that invented tokens have no collision surface at all; it is NOT that the taxonomy is known-blocked.** The "doc-PII gate has already blocked that class once" claim traces to the spec seed, is unconfirmed, and nobody has reproduced it (IDEA-203).

**This constraint binds `tests/` even though `tests/` is outside the gated trees**, and `tests/test_league_detection.py` already carries real place names and a real-sponsor-shaped team name in its existing fixtures. Those are pre-existing. **They are not the standard and must not be extended** -- an implementer following surrounding style here does exactly the wrong thing. See TN-17.

A green pack is not evidence that this epic changed any real report. Per TN-9 the discriminating rows are necessarily synthetic, because the real corpus contains no instance of the targeted shape.
