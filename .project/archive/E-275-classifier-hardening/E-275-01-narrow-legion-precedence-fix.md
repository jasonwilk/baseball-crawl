# E-275-01: Narrow Legion precedence fix and docstring correction

## Epic
[E-275: Classifier Hardening](epic.md)

## Status
`TODO`

## Description

After this story is complete, a team name carrying an explicit `legion`/`american legion` or `post N` token beside the generic word "Varsity" will resolve to the `legion` rule table in every season branch, instead of falling to `nsaa_varsity` whenever the season token is anything other than `summer`. The `_league_from_level_word` docstring will state what is actually true after the change.

> **⚠️ SCOPE CHANGED 2026-07-27 (trim pass). Read this before working from any earlier summary of this story.** Two things left:
>
> - **The ambiguous-name observability flag is CUT** — operator ruling. Its full specification, both trigger designs, SE's five-condition predicate and the logging decision now live in `/tmp/.worktrees/baseball-crawl-E-275/.project/ideas/IDEA-213-ambiguous-name-observability-flags.md`. **It was relocated, not abandoned.** The old AC-8, AC-9 and AC-10 are there.
> - **The bracket and season GUARD rows moved into the fixture pack** (E-275-02), where bracket-bin coverage belongs. The old AC-3, AC-6 and AC-7 are there.
>
> **Surviving ACs are deliberately NOT renumbered — AC-1, AC-2, AC-4, AC-5, AC-11, AC-12, AC-13, with gaps.** Renumbering would break cross-references in the epic, in E-275-02 and in two idea files, and this session's one renumber needed a positive-control sweep to be safe. **The gaps are intentional; do not close them.**

## Context

`_LEVEL_WORD_PATTERNS` is scanned in order and the first match wins. `\bvarsity\b` currently precedes every Legion-family pattern, so "Varsity" shadows an explicit governing-body token. This is a masked defect: when `season="summer"` the varsity branch maps to `legion` anyway, so the ordering weakness is invisible in the common case and only surfaces when the season signal is absent or drifts.

**Two patterns move, not four.** `seniors` and `juniors` stay where they are. The reasoning is signal reliability, not safety -- read TN-3 before touching them, and note that this narrowing is a same-day amendment to RULING 4, so the original ruling text says four.

**This story's reorder changes zero of 563 real team names** (TN-4 / Background). That is expected, and it is **not** a reason to treat the change as cosmetic. The load-bearing figure is the **rule-of-three 95% upper bound of ~13.6%** on the co-naming rate among Legion-named teams (TN-4): `0 of 563` does not mean *this does not happen*, it means the true rate could be anything up to roughly **one in seven Legion-named teams**, and this corpus — one operator's network, two days — cannot distinguish those. The consequence when it does occur is an arm called available that should not be.

## Acceptance Criteria

### The reorder -- CHANGE rows (these DISCRIMINATE: each fails against current code, passes after)

- [ ] **AC-1**: Given a name carrying an `american legion`/`legion` token beside `varsity` and no age bracket and no `ngb` (e.g. `"Wexlom Legion Varsity"`), when the season is `"spring"`, `""`, an unrecognized token, or absent, then `detect_league_level` returns `legion`. **Discriminates**: today every one of these returns `nsaa_varsity`. Per TN-15, all four season values are required -- season-absent is one member of the class, not the whole class.
- [ ] **AC-2**: Given a name carrying a `post N` token beside `varsity` (e.g. `"Quorrin Post 41 Varsity"`), under the same four season values, then `detect_league_level` returns `legion`. **Discriminates**: today all four return `nsaa_varsity`.

### The reorder -- GUARD rows (these must NOT move; each catches a specific wrong implementation)

> **AC-3 RELOCATED to E-275-02** (the summer-branch guard against a season-conditional patch). Number retired, not reused.

- [ ] **AC-4**: Given a name carrying `seniors` or `juniors` beside `varsity` (e.g. `"Trandive Seniors Varsity"`, `"Vaskeld Juniors Varsity"`), under all four non-summer season values, then the result is `nsaa_varsity` -- unchanged. **Catches**: promoting `seniors`/`juniors`, which TN-3 deliberately excludes. **These two rows changed role** from CHANGE to GUARD when the ruling narrowed; do not inherit a fail-first expectation for them from any earlier list.
- [ ] **AC-5**: Given a name carrying a Legion token beside a sub-varsity word (e.g. `"Zibbet Legion JV"`), under all four non-summer season values, then the result is `nsaa_subvarsity` -- unchanged. **Catches**: moving the Legion patterns to the FRONT of the list rather than immediately ahead of `varsity`. This is the single most likely wrong implementation of this story (TN-2).
> **AC-6 and AC-7 RELOCATED to E-275-02**, where bracket-bin coverage belongs. AC-6 was the Legion+`reserves?` guard (the one collision shape occurring in the real corpus, 5 names, TN-6); AC-7 was the four-row bracket-floor table with its 17U-cannot-fail analysis and its 14U EVIDENCE clause. **Both carry into the pack as rows under E-275-02 AC-9's per-row CRITERION/EVIDENCE marking**, which is a stronger encoding than AC-7's prose clause and cannot go stale as rows are appended. Numbers retired, not reused.

### The observability flag -- CUT (relocated to IDEA-213)

> **AC-8, AC-9 and AC-10 CUT by operator ruling 2026-07-27 and RELOCATED IN FULL to `.project/ideas/IDEA-213-ambiguous-name-observability-flags.md`.** Numbers retired, not reused.
>
> **What went with them, so nobody rebuilds it from scratch**: the derived-rule trigger framing and coach's `frosh` ruling; the two-22s block with its defining sets; the *"absence-of-feature makes an emission assertion discriminate and an absence assertion vacuous"* analysis that keeps an impossible fail-first demand out of a DoD; SE's five-condition predicate for the second, **disjoint** flag; and the logging decision, whose default on any future promotion is a **shape summary**, not the raw team name.
>
> **The cut is not a judgment that observability is worthless here.** The operator's rule is that *a confirmed live defect gets a fix or an explicitly-homed follow-up, never just a log line watching for its shape* — see [[IDEA-205]], which is that home.

### Prose and safety property

- [ ] **AC-11**: `_league_from_level_word`'s docstring no longer asserts that Legion-specific words are season-independent without qualification. The corrected text must convey that the claim holds per matched pattern and not per name, and that sub-varsity words still precede the Legion patterns. **Read TN-13's grep trap before concluding the current sentence is absent** -- it wraps across a line break and a literal-phrase grep returns zero matches.
- [ ] **AC-12**: **No name's post-fix league requires strictly less rest than its pre-fix league, at any pitch count.** Verifiable against the names in **AC-1, AC-2, AC-4 and AC-5** -- this story's own outcomes. *(This read "AC-1 through AC-7" before the trim relocated AC-3, AC-6 and AC-7 into the pack; the range form would now silently include rows this story no longer owns.)* Assert against SE's measured curves, citing the execution, never against the comment block preceding `_SUMMER_SEASON` (TN-8). **Scope RESOLVED 2026-07-27** -- SE enumerated every exclusion axis and the universal stands unhedged; see TN-7. The correct phrasing is *never under-rests*, **not** *over-rests*.

  > **Scoped to NAMES, not fixture rows -- an earlier draft said "fixture row" and that was unverifiable here.** The fixture pack is built in **E-275-02**, which is blocked by this story, so at this story's Definition of Done there are **zero fixture rows** and the fixture-row form is vacuously satisfiable in the story that owns it. The fixture-row form of the same property lives in **E-275-02 AC-10**, and TN-7 names all three locations.

  > **Do NOT compress the divergence to "three bands."** An earlier draft of this AC read *"strictly stricter at only three bands and exactly equal everywhere else."* The divergence is **four items**: 46-50, 61-70 and 81-90 post-April, **plus every count from 81 upward without an upper bound pre-April**. The three-band form is the comment block's, which TN-8 forbids citing -- so a draft that agrees with the forbidden source and disagrees with the measured one is the exact provenance smell TN-8 exists to catch. Use TN-7's verbatim.

- [ ] **AC-13** *(non-vacuity companion to AC-12 -- neither is sufficient alone)*: **At least one name's post-fix league requires strictly MORE rest than its pre-fix league at some pitch count.** Witness: a 46-pitch outing on one day's rest -- NSAA requires 1 day, LEGION requires 2.

  > **Why this exists.** AC-12 alone is **vacuously satisfiable**: an identity mapping, or a fix that changed nothing at all, passes "never strictly less" trivially. A no-op implementation would satisfy it. AC-13 is what forces the pair to discriminate, and the two must be read as one assertion. Found by SE when asked to check the AC rather than to confirm it.

## Technical Approach

**The change is confined to the ordering of entries within `_LEVEL_WORD_PATTERNS`.** It is a two-entry move. Nothing structural in `detect_league_level` changes, and no new code path is added — the observability flag that once sat here is cut (see IDEA-213).

Three constraints that are not style preferences:

- **THERE ARE TWO DIFFERENT WRONG IMPLEMENTATIONS AND THEY HAVE DIFFERENT GUARDS. Do not merge them.** They sound like the same change, which is why they have been merged once already during planning.
  - **WRONG A -- a front-of-list move** within `_LEVEL_WORD_PATTERNS`. **It cannot punch the bracket floor at all**, because the bracket ladder runs *before* `_league_from_level_word` is ever called. **Caught by AC-5 in this story**, and by the relocated Legion+`reserves?` row in the pack: SE executed it and `Zibbet Legion JV`, `Morvath Legion Reserves` and `Post 41 Reserve` all flip `nsaa_subvarsity → legion`, in both season branches.
  - **WRONG B -- a hoist ahead of the bracket ladder**, a structural change to `detect_league_level`. This is what punches the floor.
  - **Two wrong implementations, two guards, no overlap and no gap -- verified by building both, not assumed.** The catch is *"before the bracket ladder"*, and that wording is load-bearing: rewriting it as "front of the list" would attach the guard to an implementation it cannot detect.

  > **⚠️ CONSEQUENCE OF THE TRIM, STATED RATHER THAN LEFT TO BE DISCOVERED. WRONG B's executable guard now lives in E-275-02**, because the bracket rows moved into the pack. The stories are serial and E-275-02 is blocked by this one, so the guard runs *after* this story is reviewed — a **delay, not a gap**, but it means this story's review cannot lean on a test to catch a hoist. **Verify by inspection that what landed is a list reorder and not a structural change to `detect_league_level`.** If a hoist is what an implementer reaches for, say so and stop; do not wait for the pack to find it.

- **Word position in the name is irrelevant** (TN-14). The matcher loops over pattern index. Do not build any assertion around a Legion token appearing first in the name; it would pass for the wrong reason.
- **The season class, not the season value, is what matters** (TN-15). `_is_summer_season` matches only an exact normalized `summer`; everything else takes the shadowed path.

Context files to load: this epic's Technical Notes (TN-1 through TN-3, TN-7, TN-8, TN-13 through TN-15 -- **TN-5 is removed from this list; it went to IDEA-213 with the flag**); `/tmp/.worktrees/baseball-crawl-E-275/.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md` (RULING 4 and, authoritative over it, the RULING 4 AMENDMENT); `/tmp/.worktrees/baseball-crawl-E-275/.project/ideas/IDEA-172-varsity-pattern-outranks-legion-patterns.md`.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-275-02 (the fixture pack asserts post-fix labels)

## Files to Create or Modify
- `src/reports/starter_prediction.py`
- `tests/test_league_detection.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-275-02**: the post-fix resolution behavior every Tier 1 CHANGE row in the fixture pack asserts. *(The observability record the pack was once told it "may sample" no longer exists — see IDEA-213.)*
- **Hands to E-275-02**: the three relocated guard rows (the old AC-3 summer guard, AC-6 Legion+`reserves?`, AC-7's four bracket rows), which the pack absorbs rather than duplicates — **and with them WRONG B's only executable guard**, per the Technical Approach warning above.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Every CHANGE row (**AC-1, AC-2**) demonstrated to FAIL against pre-change code -- a fail-first demonstration, not an assertion that it would fail
- [ ] Every GUARD row (**AC-4, AC-5**) demonstrated to pass both before and after
- [ ] **AC-11 verified by INSPECTION, explicitly not by fail-first demonstration**: read the corrected docstring against the defect TN-13 states. It is a prose correction with no executable, and a test asserting docstring content would be brittle against any rewording
- [ ] **AC-12 and AC-13 demonstrated as a PAIR** -- AC-12 alone is vacuously satisfiable by a no-op, so a demonstration that shows only AC-12 has shown nothing

  > **The CHANGE list has been narrowed TWICE and must not be restored to either earlier form.** It first read `AC-1, AC-2, AC-8, AC-9, AC-10, AC-11` — wrong because **AC-9 asserted an absence** (trivially true pre-change, since no record was emitted for any name), **AC-10 was vacuous pre-change** (its antecedent never satisfied), and **AC-11 has no executable**. It then read `AC-1, AC-2, AC-8`. It is now **`AC-1, AC-2`**, because AC-8 went to IDEA-213 with the flag.
  >
  > **The reasoning that retired AC-9 and AC-10 is preserved in IDEA-213, not here**, since it is about the flag's ACs. It is the sentence worth carrying: *absence-of-feature makes an emission assertion discriminate and an absence assertion vacuous* — one sentence, opposite consequences, and a DoD that demands fail-first for both either stalls or gets waved through.

- [ ] Tests written and passing
- [ ] No regressions in existing tests -- specifically `test_legion_words_ignore_season`, `test_seniors_14u_is_youth_travel` and `test_14u_juniors_is_youth_travel`
- [ ] Code follows project style (see CLAUDE.md)

## Notes

Every name in this story is a constructed sentinel per TN-17. Do not substitute a real or realistic team name. **Read TN-17 for what the doc-PII gate does and does not catch** -- `epics/**` IS gated at pre-commit, but only against identifiers already on the denylist, so a novel real name passes. Do not treat the gate as a backstop for this constraint.

The two existing guard tests coach asked to be checked against (`test_seniors_14u_is_youth_travel`, `test_14u_juniors_is_youth_travel`) exercise the bracket floor for `seniors`/`juniors` only. **The gap coach identified — coverage for the two patterns that actually move, across three bracket bins — is closed in E-275-02**, by the four bracket rows relocated there from this story's old AC-7.

> **✅ FILENAME RESOLVED 2026-07-27 — obligation discharged, not carried.** This file was named `E-275-01-legion-precedence-and-ambiguity-flag.md` until the flag was cut, at which point the path claimed a scope the story no longer had. Renamed to `E-275-01-narrow-legion-precedence-fix.md`, taken from the corrected in-file title so **path and title now agree**. *(Recorded rather than deleted: an inbound reference in a research artifact still cites the old name as a record of what was audited under it.)*
