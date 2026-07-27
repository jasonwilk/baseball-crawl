# E-277-05: Collapse the per-absence WARN storm to one WARN per cause

## Epic
[E-277: Reclamation Follow-Up Repairs](epic.md)

## Status
`DONE`

## Description
After this story is complete, a single refused schedule in `retire_absent_games` emits one WARN per CAUSE with a count, rather than one WARN per absent game. Today a single refusal from one cause produces one WARN for every prior game — 30 observed, and 47 in a seeded run — burying the operator's signal in noise.

## Context
**The handoff states this defect backwards, and the reversed version points an implementer at the wrong file.** The handoff says the docstring is "per-absence, not per-cause," implying the docstring should be corrected. Software-engineer re-derived it from source: the literal docstring text is `Refusal cases, each logged as exactly one WARN:` followed by a bulleted list of four **causes**. So **the docstring already promises one WARN per cause, and the CODE is what violates it.**

Executed evidence, holding causes at exactly one (empty payload, `fetch_ok=True`) and varying only the prior-game count: 1 prior game gave 1 WARN, 5 gave 5, 30 gave 30, 47 gave 47. The count tracks absences and is blind to how many causes fired. Same at 30 for `fetch_ok=False`; the cap branch gave 10 for 10.

So the fix belongs in the code, and the docstring changes only enough that "each" cannot be misread again.

Note epic Technical Notes TN-7: this story's file, `src/db/reconcile_at_load.py`, is one of the nine under `src/` that HAVE moved since the audit baseline — touched by both E-270 and E-276. Any line-number citation into it from the handoff is suspect. Cite by symbol and docstring text.

## Acceptance Criteria
- [x] **AC-1**: Given a refusal arising from exactly one cause with N prior games (test at least N=1, N=30, and N=47), when `retire_absent_games` runs, then exactly ONE WARN is emitted for that cause regardless of N, and it carries the affected-game count.
- [x] **AC-2**: Given a run in which a whole-set cause AND a per-id cause both apply, then the collapsed whole-set WARN and the **`not_final`** per-id WARN BOTH appear, and neither absorbs the other. This is reachable: the `not_final` WARN fires for PRESENT games and the whole-set WARN for absent ones, in the same loop over the prior-game ids.
  - **⚰ CROSS-PERSPECTIVE STRUCK FROM THIS AC 2026-07-27 — it names an UNCONSTRUCTIBLE pairing.** The parenthetical read *"(`not_final`, cross-perspective)"*. **`classify_absences` computes `absence_class` as a SINGLE SCALAR per pass** (`src/db/reconcile_at_load.py:571-579`, verified by PM4 rather than taken from the report) **and every prior id resolves to `PRESENT` or that one class — so absent games are ALL `TRANSIENT_ABSENT` or ALL `REMOVED`, never mixed.** Cross-perspective fires only on the `REMOVED` path; the whole-set WARN only for `TRANSIENT_ABSENT`. **Mutually exclusive.** `not_final` fires on `PRESENT` games, which coexist with either class, **so the `not_final` pairing IS constructible and the AC's body and test were always sound.** Found by `cr5`.
  - **⚠ THIS IS THE SECOND UNCONSTRUCTIBLE PAIRING IN THIS ONE AC, AND THE ROOT CAUSE IS THE SAME BOTH TIMES.** The first was *"two whole-set causes co-firing"*, tombstoned above. **Both were written assuming causes COMPOSE FREELY, when a scalar upstream makes them MUTUALLY EXCLUSIVE.** **Both times a reviewer had to CONSTRUCT the scenario to discover it could not be constructed** — which is the reachable-red question asked of a *scenario* rather than of a criterion, and it is the form that catches an AC describing a situation the code cannot produce. **Any future AC on this grain that names two causes co-firing must first check `absence_class` — one scalar decides the whole pass.**
  - **Not "more than one whole-set cause."** An earlier draft required two whole-set causes to co-fire; that is unconstructible. `refused_by` is a single scalar chosen by a mutually exclusive `if / elif / else` chain, so exactly one whole-set value exists per call — verified by execution with two underlying conditions simultaneously true (`fetch_ok=False` with `boxscores_complete=False` yields `fetch_not_ok` alone; a gate failure with `boxscores_complete=False` yields `gate` alone). Satisfying the old wording would require making `refused_by` a set, which this story's Technical Approach expressly forbids.
  - **⚠ PROVENANCE: this unconstructibility claim is INHERITED, not re-derived.** `cr3` read the reasoning during its audit and **explicitly declined to execute it**, flagging it rather than passing it silently. So it rests on the original round's execution alone. **It is the only load-bearing claim in this story that a second party has not checked** — everything else in AC-7, AC-8 and the Technical Approach was regenerated from the module by `cr3`. Treat it accordingly: if it turns out constructible, AC-2 is the AC that changes.
- [x] **AC-3**: `result.refusals[game_id]` remains populated per game, and the per-id `refused_by` protections are unchanged. Only LOGGING is collapsed.
- [x] **AC-4**: Per-id WARNs for the `not_final` and cross-perspective causes are preserved — those are per-game by design and are NOT collapsed.
  - **⚠ AC-4a (added 2026-07-27, `se` — THE DISCRIMINATOR, and the obvious test is WRONG in a way that violates this AC while appearing to satisfy AC-1).** The classification test is **the CAUSE's SCOPE — is membership a per-id property? — NEVER the message's variability.**
    - **Why the obvious test fails, measured:** an implementer reaching for *"does this WARN emit an identical message every time?"* **folds `not_final` too.** `not_final`'s reason is a **constant string built fresh each iteration from no per-game data**, so **both it and the whole-set cause emit a byte-identical message for every game they cover.** The obvious test cannot tell them apart — **and folding `not_final` violates this AC while looking like compliance with AC-1.**
    - **`cr3`'s ground for the whole-set classification is `transient_reason` being computed ONCE outside the loop.** That is true and it discriminates — **but it is a property of the CAUSE, not of the message**, and an implementer who generalises it to "same message means whole-set" inverts it.
    - **This is the attribution-versus-signal axis in a fourth instance: identical messages are the SIGNAL; what this AC needs is WHAT PRODUCED THEM.** Membership in a whole-set cause is decided for every absence at once; membership in a per-id cause is decided per game. **Two causes can emit the same bytes and still differ in the only respect that matters here.**
    - **`se` found this while designing against it and flagged it rather than quietly designing around it** — which is why it is in the story instead of only in the implementation.
- [x] **AC-5**: The docstring's "each logged as exactly one WARN" wording is tightened so it cannot be read as per-absence, and the four-cause list it heads is preserved.
- [x] **AC-6**: Existing test expectations are brought into line in two halves, because several existing assertions count exactly the WARNs AC-1 collapses:
  - **AC-6a (UPDATE, in scope)**: tests in `tests/test_game_grain_reconcile.py` asserting a PER-ABSENCE WARN count for a whole-set cause are updated to assert ONE WARN carrying the affected-game count. Several such assertions exist, including at least one in a shared helper called by more than one test. Where an existing assertion also pins WHICH cause fired, that discrimination is PRESERVED — do not weaken these to `len(warnings) >= 1`, which would lose the cause token and the count in one move. Regenerate the list of affected assertions by search rather than from this AC.
  - **AC-6b (MUST NOT change)**: no test asserting a game's DISPOSITION, `result.refusals` content, or the per-id `refused_by` values changes. If one does, the fix has crossed from logging into semantics and is wrong.
- [x] **AC-7 (added 2026-07-27 — THE COLLAPSE TRAP. Read this before touching any `logger.warning` in that loop.)**: `retire_absent_games` has **FOUR** `logger.warning` calls inside `for game_id in sorted(prior_ids):`. **THREE are refusals. THE FOURTH IS NOT — it is the retire-SUCCESS log, and it is the ONLY per-game record of what this pass HARD-DELETED.** It fires immediately after `_delete_game_and_children` and carries the game id plus the per-table deleted row counts. **It is EXEMPT from collapse, by name, and the exemption is a required deliverable of this story — not a judgement call.**
  - **The four, classified. Derive this yourself from the loop and report any disagreement rather than reconciling to this list** (per the epic's standing discipline; the list is a FLOOR against silent shrinkage, not a checklist):
    1. `AbsenceClass.PRESENT` + `not_final` — REFUSAL, **per-id cause. Preserved per AC-4.**
    2. `AbsenceClass.TRANSIENT_ABSENT` — REFUSAL, **whole-set cause. THIS is what AC-1 collapses.**
    3. cross-perspective protected — REFUSAL, **per-id cause. Preserved per AC-4.**
    4. **the hard-delete success log** — **NOT a refusal. EXEMPT. Never collapsed, never made conditional, never folded into a summary.**
  - **✅ INDEPENDENTLY CONFIRMED IN FULL by `cr3` (C1), derived from the module rather than from this list — no disagreement to report.** Line anchors: 1135 · 1144 · 1223 · 1234, loop opening at 1125, function spanning 843–1273. **Two confirmations it added that are worth more than the agreement**, because they establish *why* the classification is right rather than merely that it is:
    - **`transient_reason` is computed ONCE at 1090–1109, OUTSIDE the loop.** That is what makes 1144 genuinely **whole-set** rather than merely repetitive — every absence in the pass shares one reason object, so collapsing it loses nothing.
    - **1223's reason varies per game across three branches.** That is what makes it genuinely **per-id**, and why AC-4 preserving it is not conservatism.
  - **✅ AC-7a's "AC-1 cannot catch this" — CONFIRMED STRUCTURALLY by `cr3` (C2), not merely argued.** Every refusal branch `continue`s (1140, 1149, 1228) **before** reaching the delete at 1230, so **no success log can fire in any AC-1 scenario.** AC-1 can pass with site 1234 destroyed. **AC-7a is load-bearing, not belt-and-braces** — do not trim it.
  - **Why the docstring does not protect it:** the promise this story enforces is *"Refusal cases, each logged as exactly one WARN"* — the success log is **not a refusal case**, so that sentence does not govern it and cannot be cited as authority for touching it.
  - **Why this is the most dangerous item in the epic.** Every other defect this epic repairs is a wrong DOCUMENT. This one would destroy **the audit trail of a destructive action** — the sole per-game record of a hard delete — and it would do so while looking exactly like the change the story asks for. A "collapse the WARN storm to one per cause" instruction applied to the loop rather than to the causes takes all four.
  - **AC-7a**: a test asserts the success log still fires **once per retired game** — N retired games produce N success WARNs, each carrying its own game id and its own deleted-row counts. **This must FAIL if the success log is collapsed, summarized, or made conditional.** Note AC-1's tests do not cover this: AC-1's scenarios are refusals, where nothing is retired and no success log fires, so **AC-1 can pass with the success log destroyed.**
- [x] **AC-8 (added 2026-07-27)**: Every prose site in `src/db/reconcile_at_load.py` stating the per-refusal WARN CARDINALITY is given a written verdict — corrected where this story falsifies it, or **explicitly recorded as needing no change**. Regenerate the list **by search against the module**, not from this AC.
  - **⚠ A sweep scoped to `retire_absent_games` MISSES MOST OF THEM. The true set is SIX, and FIVE sit OUTSIDE the function** (`cr3` S05-2, regenerated by search and each hit read literally): module docstring **60** · `AbsenceClass.TRANSIENT_ABSENT` enum docs **278** · `classify_absences` docstring **525** · section comment above `GameRetireResult` **600** · `GameRetireResult.refusals` attribute docs **618** · `retire_absent_games` docstring **869**. **The one this story most obviously falsifies is not the one inside the function.**
    - **⚰ This AC previously said FIVE, and named *"`classify_absences`' `TRANSIENT_ABSENT` documentation"* as one site. That phrasing CONFLATED TWO DISTINCT SITES and is where the missing member went.** 278 is the enum member's own bullet (*"the caller retires nothing and logs one WARN per refusal"*); 525 is the classifier function's docstring (*"The classifier only classifies; the caller emits the WARN per refusal"*). **Different regions, different wording, one phrase covering both.**
    - **Lineage, recorded because it is the argument for this AC's own design: `cr2` said two, I corrected to five, the true count is six. Three generations of one undercount.** Consistent with the repo's standing 8-for-8 record that authors never catch their own missing-member defects — **and each correction came from a non-author regenerating rather than checking the predecessor's list.** The instruction to regenerate by search is what surfaced this, **including against my own list.**
  - **⛔ THERE IS A FALSE POSITIVE THAT MUST NOT BE "FIXED", AND THE OBVIOUS SWEEP RETURNS EXACTLY IT.** The PLAYER-LINE grain's `PlayerLineRetireResult.refusals` at **1310** carries a byte-identical sentence — *"(bias to refuse). One WARN was emitted per entry."* — describing `retire_absent_player_lines`, **a grain this story does not touch, where the sentence REMAINS TRUE.**
    - **⚠ MEASURED CORRECTION TO THIS AC'S OWN INSTRUCTION (`cr3` S05-3). It previously read "A grep for the sentence hits both." IT DOES NOT.** At 1310 (must NOT fix) the sentence sits on **one line**; at **618–619** (MUST fix) it **WRAPS** between `emitted` and `per entry`. So `grep -n "One WARN was emitted per entry"` returns **1310 alone** — **the sweep returns the false positive and HIDES the true positive**, the exact inversion of this AC's intent. An implementer following the old instruction literally lands on the sentence they must not touch and never sees the one they must.
    - **⚰ RETIRED PRESCRIPTION, kept quoted because it was in this AC and in TN-15 and someone may be working from either.** It read: *"THEREFORE — discriminate BY SYMBOL, not by sentence: `GameRetireResult.refusals` → FIX. `PlayerLineRetireResult.refusals` → DO NOT TOUCH."* **That instrument CANNOT perform the discrimination it is prescribed for.** The attribute name is **identical on both classes**, the qualified forms **do not appear at the attribute-access sites**, and `se`'s words for the consequence are the ones to keep: ***"even a correct grep returns the right lines under the wrong label."*** **A second route to the wrong sentence, in the ostensible fix for the first.** A text sweep still must be whitespace-normalized if used at all — that part stands.
    - **THE REQUIREMENT (property form, falsifiable): every `.refusals` site touched by this story is MAPPED to its owning class, and the site → class mapping is RECORDED IN NOTES with one row per site.** An implementer's table can be checked by **counting its rows against the number of access sites** — which is what makes this an AC rather than an intention. **A site that cannot be resolved to an owning class is a FINDING to report, NOT a default to the more plausible label.** That last clause is the load-bearing one: **the failure mode is an unresolved site quietly getting the likelier owner.**
    - **The discriminating token is the CLASS NAME, and it is absent from the access sites — so this is a JOIN, not a grep**, which is why "discriminate by symbol" was never going to work. `se`'s method, recorded as known-working rather than mandated: enumerate where a `refusals` value is **born** (the class names differ, so that search discriminates), enumerate where one is **read** (that search does not, and must never be ruled on alone), then join by reading the function enclosing each read site and matching its receiver. **Any method that produces the mapping table satisfies the AC; this one is known to.**
    - **⚠ THE READ-SITE TOKEN MUST BE BARE `refusals`, NOT `.refusals` — measured by `se`, and the dotted form MISSES THE SITE THIS AC EXISTS TO FIX.** Dotted returns **9** sites; bare returns **20**; **`GameRetireResult`'s attribute docs — the MUST-FIX target — are in the 11 that dotted misses**, because a docstring names its own attribute **bare**: `refusals: {game_id: reason} ...`. There is no dot. **The prescribed search was invisible to its own target.** Expected mapping table is **20 rows, not 9**.
    - **The principle, and it is the reusable half: PREFER AN OVER-MATCHING ENUMERATION WITH A RESOLUTION STEP OVER AN UNDER-MATCHING ONE.** Under-match is **silent** — a missing site looks exactly like a site that does not exist. Over-match is **visible** — a non-member arrives and must be dispositioned. **Bare `refusals` over-matches into ordinary English** (`"rows its own refusals stranded"` in `retire_departed_roster_players`, whose `RosterRetireResult` has no `refusals` attribute at all), **and that is the SURVIVABLE direction**: the join discards it, and AC-8's unresolvable-site clause requires it be **reported rather than silently dropped.** **The clause is what makes over-matching safe** — without it, over-match degrades into quiet judgement calls.
    - **⛔ TIMING IS PART OF THE PROPERTY: BUILD THE TABLE LAST, AGAINST THE DELIVERED ARTIFACT — added 2026-07-27 after the row count FAILED for exactly this reason.** The AC said one row per site and said nothing about **when** the count is taken. `se` built a correct 20-row table at analysis time; **the story then authored four new `refusals` sites (631, 886, 1144, 1167) and the table went stale without anyone touching it.** **The row-count check is falsifiable ONLY against the file being reviewed** — measured before the edits, it certifies a file that no longer exists.
      - **`se`'s own statement of it, which is the general form:** ***"A sweep is a measurement of a MOMENT, and mine measured the moment before the story wrote anything. Run the enumeration LAST, against the delivered artifact — not first, against the one you set out to change."***
      - **This is story 01's AC-9a discipline, which AC-8 failed to inherit** — *"the sweep covers prose THIS STORY ITSELF writes; run it AFTER the story's own edits land, or it misses the sites the story created."* **Story 01 learned it, one story over it recurred with a different symptom, and the reason it recurred is that the clause lived in story 01's AC rather than anywhere a later AC-8 author would meet it.**
      - **Label the table's line-number column POST-EDIT** so a future reader can tell which moment it measured **without re-deriving it.**
    - **⚰ THIRD INSTRUMENT IN A CHAIN, each fix reproducing the defect it repaired.** (1) *"discriminate by symbol"* — returned the twin, hid the target. (2) the `.refusals` join — returns **neither** the target nor the twin's docstring. (3) bare-token join — over-matches, which is survivable. **Recorded because the pattern is the lesson: three consecutive corrections to one instrument, two of them worse than useless, and the AC's PROPERTY was unaffected by all three.** **Had the operation been the criterion, this AC would have been wrong three times.** That is the argument for property-in-the-AC and operation-in-the-prose, made by events rather than by reasoning.
    - This is the criterion-vs-evidence cut applied to a sweep's output: **a hit is a candidate, never a member** — and here, the only hit the naive pattern produces is the one member that must be left alone.
  - **Explicit NON-MEMBERS, each with a written verdict** (`cr3`, per story 01 AC-9b — recorded so the next sweep does not re-adjudicate them): **47** *"a WARN log line per retire"* — describes the SUCCESS log, **stays TRUE, no change** · **1178** mislabelled-WARN comment — not a cardinality claim · **1708** player-line matched-victim WARN — not a cardinality claim · **2331/2336** roster-grain *"warns exactly once"* — different subject (uncovered team ids) · **1310** — the twin, **MUST NOT change**.
  - **The module docstring's claim goes HALF stale and needs a TWO-SIDED repair, not a deletion**: it states the cardinality for the module's retire helpers generally, and after this story it is false for the game grain's whole-set causes and still true for the player-line grain. Scope it or state both halves; do not replace one one-sided claim with another.
  - **Counts: prefer REMOVE over restating**, per story 01 AC-9b. A sentence that does not need to assert a cardinality should stop asserting one.

## Technical Approach
The binding constraint comes from the code itself, and software-engineer flagged it explicitly: the comment above the `refused_by` assignment says per-id protections MUST NOT be folded together, and `result.refusals[game_id]` must stay per-game. **Collapse only the logging, and only for the two whole-set causes.** AC-3 and AC-4 exist to make that boundary testable rather than a matter of care.

**There is no whole-set WARN today — this story ADDS one.** ⚠ **CORRECTED 2026-07-27 (`cr3` S05-1): this paragraph previously read *"`retire_absent_games` has exactly TWO `logger.warning` sites, both inside the per-game loop (software-engineer)."* THAT IS FALSE. There are FOUR**, all inside `for game_id in sorted(prior_ids):` — derived independently by `cr3` from the module (function spans 843–1273, loop opens 1125, `logger.warning` at **1135, 1144, 1223, 1234**), and matching AC-7's enumeration exactly.

**The conclusion survives; its stated reason does not.** "This story ADDS one" is still correct — **but the ground is that NONE of the four is whole-set**, not that there are only two. So the change is not "modify an existing summary log"; it is to emit a new per-cause WARN carrying a count, and to stop the per-game emission for the whole-set cause only.

**Why this correction is not bookkeeping, and why it is the most dangerous single sentence in the story.** AC-7 is this story's self-declared most dangerous item and it exists to protect **site #4, the hard-delete success log**. **An implementer trusting this paragraph goes looking for two sites in a loop that has four** — and the one that falls outside a two-item mental model is precisely the one that does not look like the others, because the success log is the only non-refusal. **A reader reconciling "two" against what they see keeps the two most refusal-shaped calls and drops the success log.** The story's own Technical Approach pointed directly at the trap AC-7 was written to prevent. Expect AC-6a's existing assertions to go red as a direct consequence — that is the change landing, not a regression.

The distinction the fix turns on is between a cause that applies to the whole refused set (the empty-payload and fetch-failure cases, where every absence shares one reason) and a cause that is genuinely per-game (`not_final`, cross-perspective). The first should say what happened once and count the rows; the second is already correct.

Do not change refusal SEMANTICS. No game's disposition changes as a result of this story — a game refused today is refused after it, and the counts in `result` are identical. This is an observability fix, and if a test shows a disposition changing, something has gone wrong.

Constraints: synthetic DBs from `migrations/` only; never touch `data/app.db`; no `bb` commands.

## Dependencies
- **Blocked by**: E-277-01
- **Blocks**: None

## Files to Create or Modify
- `src/db/reconcile_at_load.py`
- `tests/test_game_grain_reconcile.py`

## Agent Hint
software-engineer

## Definition of Done
- [x] All acceptance criteria pass
- [x] Tests written and passing
- [x] Code follows project style (see CLAUDE.md)
- [x] No regressions in existing tests

## PM AC Verdict — FINAL (2026-07-27, PM4)

**ALL ACs PASS.** Enumerated individually, never spanned: **AC-1, AC-2, AC-3, AC-4, AC-4a, AC-5, AC-6, AC-6a, AC-6b, AC-7, AC-7a, AC-8.** Twelve named.

**`cr5` reviewed independently across two rounds and closed APPROVED. Its round 1 found TWO MUST FIX; both were in AC-8, which I had explicitly declared as NOT re-derived.** Neither of us saw the other's reasoning before ruling — the quarantine held across both rounds.

### Verified BY READING THE CODE AND TESTS

- **AC-1** — the whole-set WARN fires **once, after the loop** (`reconcile_at_load.py:1281-1287`), carrying `len(transient_refused)`. Ids collected in-loop at `:1179` **from the same iteration that populates `result.refusals`**, so the logged count cannot structurally drift from the recorded set.
- **AC-3** — `result.refusals[game_id]` still per-game at `:1165`, with the comment stating *"only the LOGGING collapses, never the record."*
- **AC-4** — `not_final` (`:1157`) and cross-perspective (`:1254`) still fire per game.
- **AC-4a** — landed at `:1170-1178`, **inside the branch where the wrong turn is taken**, naming the false discriminator and why it fails. A reader arriving to "simplify" meets the argument before making the mistake.
- **AC-5** — docstring `:881-886`: *"The WARN cardinality follows the CAUSE, not the number of absences."* Four-cause structure preserved as two whole-set + two per-id.
- **AC-7** — four sites; the success log at `:1265-1272` is **still inside the loop**, per retired game, carrying its own id and per-table counts.
- **AC-7a** — `test_success_log_still_fires_once_per_retired_game` asserts N retired → N successes **and that each line carries its OWN id and its OWN `Rows deleted: {`**. **Per-line attribution, not cardinality — a collapse preserving the count still fails it.**
- **AC-8's row count — RUN BY ME.** 24 occurrences of the bare token, **all on distinct lines**: 73, 74, 84, 97, 309, 341, 629, 634, 639, 640, 643, 649, 889, 1082, 1150, 1162, 1171, 1173, 1259, 1361, 1364, 1380, 1903, 2257. **24 = `se`'s regenerated table = `cr5`'s recount = mine. Three independent derivations.**
  - **⚠ A silent dependency of this property, flagged because nothing states it: line-count and occurrence-count COINCIDE in this file.** "One row per site" is unambiguous **only** because every one of the 24 sits on its own line. **It would not be if two ever shared one.**

### MF1's fix — all THREE halves checked SEPARATELY

**Not treated as one claim, because the fix's own lesson is that a two-sided form manufactures claims about unopened surfaces.**

1. **Game grain brought to whole-set shape** — `:1281-1287`. ✅
2. **Player-line unchanged, one WARN per refused `(table, team_id)` entry** — `:1903-1910`, inside the per-block loop, keyed by `key`, carrying that block's own absent ids. **"Per-id there" is correct because the id granularity on that grain IS the block key**, as `:84-86` explains. ✅
3. **Roster ALREADY whole-set** — `:2361-2367`, one WARN carrying `absent_count` and `absent_player_ids`, alongside a scalar `result.refused = True`. ✅ **The original claim that roster logs per-entry was false; `cr5` was right.**

### ⚠ Disclosure bearing on my own game-ids ruling

**I ruled to KEEP the ids on the collapsed line before I knew the roster grain already carries `absent_player_ids` on its own whole-set WARN** (`:2366`). I found that while checking half 3.

**Recorded because a verdict's stated reason rots independently of the verdict, and a correct conclusion immunises its premise.** The ruling was made on reasoning — *the storm's real content was WHICH games were held; a noise fix that also removes information has overshot* — **and the precedent was found afterwards.** **It is no longer a judgement call against house precedent: it matches the house.** The reasoning is still what makes it right; it is no longer the only support.

### Taken from `cr5`, NOT re-derived by me

Its **set-difference** of the 24 sites against the table's claimed lines — **symmetric difference empty in BOTH directions, which is stronger than matching counts and catches what an equal count hides.** Its **execution of both date formulas** (identical at i=0/7/20, first divergence at **i=21**) rather than reading the claim. Its confirmation that **all three grains call `classify_absences`** (`:1058`, `:1865`, `:2291`) and the roster path tests `TRANSIENT_ABSENT` at `:2317`, **so the roster claim belongs in the enum docstring on the code's evidence rather than on editorial judgement.** Its regeneration of the `refused_by` vocabulary establishing `boxscores_incomplete` as precisely and only the value with no bullet.

### Taken from `se`, NOT re-derived

`57 passed` / `331 passed`, both exit 0 and unchanged across a prose-only change — **the right shape, but not something I ran.**

### Two AC defects found during verification and fixed in the ACs, not the code

**AC-2's cross-perspective parenthetical was UNCONSTRUCTIBLE** — `absence_class` is a single scalar per pass (`:571-579`, verified by me), so cross-perspective and the whole-set WARN are mutually exclusive. **Second unconstructible pairing in that one AC, same root cause both times.**

**AC-8 carried no TIMING clause**, so a correct table built at analysis time went stale when the story authored four new sites. **Story 01's AC-9a discipline, which AC-8 failed to inherit** — recorded in TN-15 as *a rule in the wrong place is not a weaker rule, it is an absent one.*

## Notes
Production file is disjoint from every other story in this epic. **The coupling that justifies blocking behind E-277-01 is BEHAVIORAL, not a file conflict** — an earlier draft stated it as a shared-file conflict, which this story's own Files list rules out. `tests/test_report_generator.py` is NOT in this story's declared files and its Notes forbid touching it. What is true: this story changes `retire_absent_games`, and `tests/test_report_generator.py` OBSERVES that function at two sites (a recording-spy wrapper and a `patch.object`) while story 01 is separately modifying that same file. Two stories changing the observed behavior and the observing file concurrently is the risk; serial execution removes it at no cost, so the chain stays. `retire_absent_games` is exercised in `tests/test_game_grain_reconcile.py` (13 occurrences) and referenced in `tests/test_report_generator.py` (2). Write this story's tests in `tests/test_game_grain_reconcile.py`. If you find you must touch `tests/test_report_generator.py`, stop and flag it rather than editing a file story 01 owns.

Planning note worth carrying: `tests/test_reconcile_at_load.py` exists and is the name this story originally guessed, but it is NOT where `retire_absent_games` is tested. Four reconcile test files exist and are split by grain; do not assume the module name maps to the test file name.

---

## Implementation record (software-engineer, 2026-07-27)

Everything below was EXECUTED in this worktree unless a line says otherwise. Line numbers are given only where a reader is meant to SEE that something moved; every citation a reader is meant to FOLLOW is by symbol.

### Files Changed

| path | nature |
|---|---|
| `src/db/reconcile_at_load.py` | the collapse (3 edits in `retire_absent_games`) + 6 prose sites |
| `tests/test_game_grain_reconcile.py` | 5 assertions updated, 5 tests added |
| `epics/E-277-reclamation-followups/E-277-05-warn-per-cause-collapse.md` | this record |

**No other file.** `tests/test_report_generator.py` was NOT touched (story 01 owns it). No new files, nothing untracked.

### AC-8 mapping table — every `refusals` site, mapped to its owning class

**⚠ The method recorded in AC-8 as "known-working" is MINE and it is DEFECTIVE as written.** It says to enumerate read sites with `.refusals`. Measured: the dotted token returns **9** sites, the bare token **20**, and **the site this story must FIX is in the 11 that dotted misses** — `GameRetireResult`'s attribute docs write the attribute **bare** (`refusals:`), because that is how a docstring names its own attribute. There is no dot. **The target of the AC is invisible to the search prescribed for finding it** — the same defect as the retired "discriminate by symbol", reproduced inside its replacement. The corrected token is the bare `refusals`: it over-matches rather than under-matches, which is the survivable direction, and the join discards the non-members.

**⚠ REGENERATED against the DELIVERED file after review round 1. The first version of this table had 20 rows and was STALE ON DELIVERY** — it enumerated the pre-story state (`git show :src/db/reconcile_at_load.py` returns 20, matching it line-for-line), and the story then authored four new sites that were never added. **AC-8's own premise is that under-enumeration is silent, and it was silent here in the table built to satisfy it.** Found by `cr5`, reproduced by me. The four late sites are marked **NEW**; none was a misattribution and none touched the twin, so this was a completeness failure, not a correctness one.

**Line numbers below are POST-EDIT (the delivered file).** Labelled, because the first version's column was pre-edit and nothing said so.

| # | line | owning class | how resolved |
|---|---|---|---|
| 1 | 73 | `GameRetireResult` | line names the class literally |
| 2 | 74 | `PlayerLineRetireResult` | line names the class literally |
| 3 | 84 | `PlayerLineRetireResult` | sentence scopes itself: "by `(table, team_id)` on the player-line grain" |
| 4 | 97 | **BOTH** | "expect `.refusals` in two of them and `.refused` in the third" — Game + PlayerLine, contrasted with `RosterRetireResult` |
| 5 | 309 | **BOTH** | inside `GateOutcome`, grain-generic |
| 6 | 341 | **BOTH** | inside `GateOutcome.refused_by` docs, grain-generic |
| 7 | **629** | `GameRetireResult` | inside `class GameRetireResult` — **THE MUST-FIX SITE**; its sentence WRAPS to the next line |
| 8 | **634 — NEW** | `GameRetireResult` | authored by this story ("do not infer the WARN count from `len(refusals)`") |
| 9 | 639 | `GameRetireResult` | same class, `gate_outcome` docs |
| 10 | 640 | `GameRetireResult` | same |
| 11 | 643 | `GameRetireResult` | same |
| 12 | 649 | `GameRetireResult` | the field declaration |
| 13 | **889 — NEW** | `GameRetireResult` | authored by this story (the AC-5 docstring rewrite) |
| 14 | 1082 | `GameRetireResult` | inside `retire_absent_games` (`result = GameRetireResult()`) |
| 15 | **1150 — NEW** | `GameRetireResult` | authored by this story (the collector's comment) |
| 16 | 1162 | `GameRetireResult` | same function |
| 17 | 1171 | `GameRetireResult` | same |
| 18 | **1173 — NEW** | `GameRetireResult` | authored by this story (the TRANSIENT_ABSENT branch comment) |
| 19 | 1259 | `GameRetireResult` | same |
| 20 | **1361** | `PlayerLineRetireResult` | inside `class PlayerLineRetireResult` — **THE TWIN, NOT TOUCHED** |
| 21 | 1364 | `PlayerLineRetireResult` | same class, `gate_outcomes` docs |
| 22 | 1380 | `PlayerLineRetireResult` | the field declaration |
| 23 | 1903 | `PlayerLineRetireResult` | inside `retire_absent_player_lines` (`result = PlayerLineRetireResult()`) |
| 24 | 2257 | **NONE — not an attribute reference** | inside `retire_departed_roster_players`, whose result type is `RosterRetireResult` and has **no `refusals` attribute at all**; the text is the English plural noun ("rows its own refusals stranded") |

**Row 24 is REPORTED, not defaulted.** Per AC-8's load-bearing clause, a site that does not resolve to an owning class is a finding. This one resolves to *no* class, which is a real answer rather than a failure — but it is written down rather than dropped, because silently discarding it is indistinguishable from never having seen it.

Row count 24 against the bare-token site count 24 in the delivered file. Rows 7 and 20 are the pair the whole AC exists for.

**What the stale table teaches, beyond regenerating it: a sweep is a MEASUREMENT OF A MOMENT, and the moment it measured was before the story wrote anything.** The row-count check that makes AC-8 falsifiable only fires if the count is taken against the file being reviewed. **Run the enumeration LAST, against the delivered artifact — not first, against the one you set out to change.**

### The naive sweep's inversion — confirmed by execution, not relayed

`grep -n "One WARN was emitted per entry"` returns **`1310` alone** — the twin that must NOT be touched. The true positive wraps between `emitted` and `per entry`, so no single-line pattern can see it. My sweep (whitespace-normalized, markup-stripped, case-insensitive, wrap-spanning, seven patterns) returns both, as `618-619` and `1310`.

### AC-8 prose sites — six members, each with a written verdict

Regenerated by search against the module; agreement with the AC's list is a cross-check, not the source.

| site | verdict |
|---|---|
| module docstring | **CORRECTED, per-grain** — states the cause-follows-cardinality rule, then each grain separately. ⚠ **Round 1 shipped a FALSE half here; see "Review round 1" below.** |
| `AbsenceClass.TRANSIENT_ABSENT` | **CORRECTED** — cardinality attributed to the caller, game grain named as whole-set |
| `classify_absences` | **REMOVED, not restated** — the sentence's subject is the purity split; it never needed to assert a cardinality (AC-8's REMOVE preference) |
| section comment above `GameRetireResult` | **CORRECTED** |
| `GameRetireResult.refusals` | **CORRECTED** — plus an explicit "do not infer the WARN count from `len(refusals)`" |
| `retire_absent_games` docstring | **CORRECTED** (AC-5) — four-cause list preserved byte-for-byte, each bullet prefixed `WHOLE-SET --` / `PER-ID --` |

**NON-MEMBERS, no change, each verdicted:** the `WARN log line per retire` line (describes the SUCCESS log — stays true) · the mislabelled-WARN comment (not a cardinality claim) · **`PlayerLineRetireResult.refusals` — the twin, sentence remains true** · the player-line matched-victim WARN · the roster-grain `warns exactly once` (different subject: uncovered team ids).

### AC-7 — derived independently, no disagreement, plus one hazard no AC names

Four `logger.warning` in `retire_absent_games`, all inside `for game_id in sorted(prior_ids):`. Classification derived from the loop, matching AC-7's list: `not_final` PER-ID · `TRANSIENT_ABSENT` WHOLE-SET · cross-perspective PER-ID (three reason branches) · **hard-delete success log, EXEMPT**. AC-7a's structural claim independently confirmed: every refusal branch `continue`s before the delete.

**⚠ A hazard in no AC, and it selects the wrong set.** The obvious discriminator — *"does this WARN emit an identical message every time?"* — folds `not_final` too, violating AC-4. Its `reason` is a CONSTANT string built fresh each iteration from no per-game data, so both branches emit a byte-identical message for every game they cover. **The discriminator has to be the CAUSE's SCOPE (is membership decided per id?), never the message's variability.** Recorded in the code at the branch, where the wrong turn is taken.

**Supporting anchor already in the module**, found rather than added: the comment above `refused_by` states *"All of these are WHOLE-SET decisions, so the reason is settled once here rather than per game."* The module already knew; only the logging disagreed.

### Tests

**Updated (5 assertion sites, regenerated by search — 6 test failures, because one is a shared helper with two callers):** `_assert_nothing_retired` · `test_catastrophic_shrink_retires_nothing` · `test_truncated_array_padded_with_upcoming_games_retires_nothing` · `test_cap_refuses_a_mass_retire_that_passes_the_floor` · `test_newly_completed_games_no_longer_authorize_retiring_stale_ones`.

**Every cause token is PRESERVED, none weakened to `>= 1`** — `not authoritative`, `boxscores_complete=True`, `MAX_GAME_RETIREMENTS=`, `refused_by=gate`, `START of this run` all still asserted, now against the single line, and each gains a `REFUSED for N game(s)` count assertion.

**AC-6b holds mechanically: the pre-update run failed exactly those 6 and no others.** No disposition test, no `result.refusals` test, no `refused_by` test moved. That is the semantics/logging boundary measured rather than asserted.

**Added (5):** `test_whole_set_cause_logs_one_warn_regardless_of_absence_count` parameterized at **N=1, 30, 47** (AC-1, and it asserts `len(result.refusals) == prior_count` so AC-3's per-game record is pinned alongside) · `test_whole_set_and_per_id_warns_coexist_neither_absorbing_the_other` (AC-2) · `test_success_log_still_fires_once_per_retired_game` (AC-7a).

### Mutation record — AC-7a's rationale EXECUTED rather than argued

**MUTANT-S1**: the in-loop success log demoted from `logger.warning` to `logger.debug` — i.e. the audit line collapsed away. Applied to the source, run, restored, md5-verified byte-identical (`bebcb3c21b5f604f52f43c07f379d53e` before and after; zero `MUTANT` tokens in either file).

```
FAILED tests/test_game_grain_reconcile.py::test_success_log_still_fires_once_per_retired_game - AssertionError: []
1 failed, 56 passed in 1.00s
```

**One test out of 57 notices.** Every AC-1 case passes. So AC-7's claim — *"AC-1 can pass with site #4 destroyed"* — is now an observation rather than an argument: 56 tests, including all three AC-1 parametrizations, go green against a mutant that destroys the sole per-game record of a hard delete.

**Bytecode-cache hygiene: NO explicit step was taken** — no `__pycache__` clear, no `-p no:cacheprovider`, no `PYTHONDONTWRITEBYTECODE`. Why it could not have lied:
- **The mutant changed the file's SIZE**: 128,002 bytes pristine → 128,056 (`+54`). CPython's default invalidation is timestamp-mode and the `.pyc` header records source mtime AND source size; read from the live cache file `src/db/__pycache__/reconcile_at_load.cpython-313.pyc`, `flags=0` and `source_size=128002`, matching the source on disk. A non-zero size delta forces recompilation on its own; mtime changed too.
- **The failure DIRECTION is a control**: a stale `.pyc` would have run the pre-mutation source and produced a pass. It produced the predicted failure, in the predicted test.
- **The unmutated baseline, stated as what it actually was**: no control was *staged*. Two ordinary runs happened to be unmutated — the post-implementation run before the mutation (`57 passed`) and the post-restore scope run. "The suite was green beforehand" and "I ran a no-mutation control" are different claims and only the first is what happened.

### Verification

| command | result | exit |
|---|---|---|
| `python -m pytest tests/test_game_grain_reconcile.py -q` | `57 passed in 0.90s` | `0` |
| `python -m pytest tests/test_game_grain_reconcile.py tests/test_player_line_reconcile.py tests/test_reconcile_at_load.py tests/test_roster_grain_reconcile.py tests/test_report_generator.py -q` | `331 passed in 34.65s` | `0` |

The five-file scope was discovered by grepping `tests/` for importers of `reconcile_at_load`, not chosen.

### Review round 1 — four findings, all confirmed at the file before fixing

**⚠ MUST FIX 1 — the two-sided repair's second half was FALSE, and it is this epic's signature defect INSIDE the fix for it.** Round 1's module docstring and enum text said *"the player-line and roster grains are unchanged and still log one WARN per refused entry."* **The ROSTER grain does not.** `retire_departed_roster_players` emits its refusal WARN carrying `absent_count` / `absent_player_ids` **before** `for player_id in absent:`, immediately followed by `return result` — **already the exact shape this story introduces on the game grain.** The player-line half was correct.

**The lesson, which generalizes past this story: BEING TWO-SIDED IS NOT BEING TRUE ON BOTH SIDES.** The two-sided discipline exists to stop one-sided claims, and here it made me author a NEW claim about a grain I had never opened — **the discipline created the surface for the defect.** Each half of a two-sided claim is its own claim and needs its own verification.

**Three things already in reach should have caught it, and none was consulted:** the same module docstring says 25 lines below that *"the roster grain's refusal is a WHOLE-SET decision"*; **my own mapping table row recorded that `RosterRetireResult` has no `refusals` attribute**; and AC-8 said *"still true for the player-line grain"* and never mentioned roster — **the generalization to include it was the implementation's, not the AC's.** I had the refuting evidence in an artifact I wrote and did not read it against the sentence.

**MUST FIX 2 — the mapping table was stale on delivery.** See the regeneration note above.

**SHOULD FIX 3 — invalid dates.** `_seed_games` built `start_ts` as `f"2026-04-{10 + i:02d}"`, which emits `2026-04-31` … `2026-04-56` past `i = 20`. Every pre-existing caller passes at most 8; **the N=30/47 parametrization added by this story is the first to reach past April.** Harmless today — nothing on the exercised path parses `start_ts` — but a future date parse would fail a test whose subject is WARN cardinality. Replaced with real date arithmetic; **measured that the two formulas are identical for every `i <= 20` and first diverge at `i = 21`, so no pre-existing fixture moves.**

**SHOULD FIX 4 — a count label this story authored.** The new docstring said *"the two WHOLE-SET causes below"*, but `boxscores_incomplete` is a distinct `refused_by` member with no bullet in that list. The list gap is pre-existing; **the count label was new.** Counts REMOVED rather than restated (AC-8's preference, the same disposition applied to `classify_absences`), plus one sentence recording that the bullets are not exhaustive — **because removing the count without saying so leaves a reader to count the bullets and re-derive "two" themselves.**

### Verification (round 2, re-run after the fixes)

`ruff check src/db/reconcile_at_load.py` → clean. `ruff check tests/test_game_grain_reconcile.py` → **one pre-existing `F841`** (unused `stale` local in `test_newly_completed_games_no_longer_authorize_retiring_stale_ones`), confirmed NOT mine by running ruff against the pre-story-05 backup and getting the identical finding at the same site. Left alone; flagged rather than silently carried.
