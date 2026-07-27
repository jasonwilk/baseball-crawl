# E-277-04: Correct the cascade citation and the reclamation-seam root enumeration in the rules layer

## Epic
[E-277: Reclamation Follow-Up Repairs](epic.md)

## Status
`DONE`

## Description
After this story is complete, `.claude/rules/data-model.md` cites the file `_delete_team_scoped_data` actually lives in, and records that the reclamation sweep is a third team deleter whose deletion decision is made differently from the other two. A reader following the rule no longer lands on a path where the symbol does not exist, and no longer has to re-derive the false contradiction the 2026-07-25 audit derived. Separately, `.claude/rules/canonical-seams.md`'s reclamation bullet enumerates the predicate's roots, and story 01 adds a fourth — this story updates that enumeration so the seam rule does not ship a false root count.

**The two rule files get DIFFERENT claims and neither covers the other** (claude-architect, and stated here because merging them is the obvious move and it is wrong). `data-model.md` gets a table-semantics fact — a row of *this table* roots its own team — in the bullet block where that table's row-level semantics already live. `canonical-seams.md` gets a seam-level enumeration — the predicate keeps *four* roots. AC-6's sweep is symbol-only on the cascade symbols and structurally cannot reach the reclamation bullet, which is exactly why AC-7 carries its own instrument. ⚠ **This previously read "the two cascade symbols." There are THREE (`cr3` S04-1)** — `_delete_team_anchor_and_orphan_data` is a third stale citation, named as `src/reports/generator.py` at `data-model.md:43` and **defined at `src/reports/lifecycle.py:550`.**

## Context
`_delete_team_scoped_data` is defined in `src/reports/lifecycle.py` and appears nowhere in `src/reports/generator.py`. The `scheduled_report_runs` bullet in `.claude/rules/data-model.md` still cites the old `generator.py` path.

The citation fix alone would be a one-word change. This story has three parts, not one — the citation (AC-1), the third-deleter record (AC-2/AC-3), and the reclamation-seam root enumeration (AC-7). The reason the story is worth dispatching is the second: migration 005 documents two team-deletion cleanups, both correct, and is silent on the sweep E-273 added. That silence is what led the audit to conclude the code contradicted the migration when it does not — a wrong conclusion reached by a careful reader from an accurate document. Recording the third deleter is what stops the next reader repeating it.

Read epic Technical Notes TN-1 and TN-5 before starting. TN-5 in particular explains why two other surfaces carrying the same stale citation are deliberately NOT changed.

## Acceptance Criteria
- [x] **AC-1**: `.claude/rules/data-model.md`'s team-deletion cascade reference for `scheduled_report_runs` names `src/reports/lifecycle.py` as the file containing `_delete_team_scoped_data`.
- [x] **AC-2**: The same file records that a third team deleter exists — the reclamation sweep — and that it INFERS unreachability where **`cascade_delete_team` and `cleanup_orphan_teams`** act on a decision already made. **NAME THOSE TWO BY SYMBOL; do not write "the other two."**
  - **⚰ AMBIGUITY RESOLVED 2026-07-27, `ca-2` reading B adopted.** *"The other two"* had two readings and the AC did not say which. **(A)** migration 005's two cleanups — **rejected: report deletion is not a TEAM deleter, so "third team deleter" does not compose.** **(B)** `cascade_delete_team` + `cleanup_orphan_teams` — **adopted: it composes, and the epic's own Background already says exactly this** (*"`cascade_delete_team` and `cleanup_orphan_teams` delete a team someone decided to delete. The sweep infers unreachability"*). **The AC was ambiguous where the epic was not** — which is why naming the symbols is the whole fix.
  - **The property that makes reading B CHECKABLE rather than merely intended (`ca-2`, and it is better than the prose test): it is visible at the SIGNATURE.** `cascade_delete_team` and `cleanup_orphan_teams` **RECEIVE** their target (`team_id`, `orphan_ids`); **`reclaim_orphan_reference_data(conn)` COMPUTES** its set from `_team_orphan_pred`. **Receives-versus-computes is the decided-versus-inferred distinction, readable off the signatures without interpreting anyone's prose.** It states that a `scheduled_report_runs` row is a reachability root for its own team, **so a team carrying such a row is excluded from the orphan set and is never deleted by the sweep.** The prose ALSO states the non-reach explicitly: the row roots its OWN team and confers nothing on the opponent, which the table identifies by an opaque GameChanger token carrying no `teams(id)` FK. Without that second half, a sentence sitting near the `opponent_root_team_id` bullet reads as protecting both teams it names, and it does not.
- [x] **AC-3**: The existing statement that team deletion removes audit rows while report deletion only NULLs `report_id` is preserved and not weakened. Both remain true; AC-2 adds a case, it does not replace one. **AC-2's and AC-3's statements are ADJACENT and linked in the prose, not separated** — together they are the two-sided form a reader needs: the root blocks the sweep's INFERRED deletion, and does NOT block a DELIBERATE deletion, which still removes the audit rows per migration 005. Split apart, AC-2 alone reads as "a team with a scheduled run cannot be deleted," which is false.
- [x] **AC-4**: `migrations/005_scheduled_report_runs.sql` is unmodified, and `docs/ROADMAP.md` is unmodified. Per epic Technical Notes TN-5.
  - **⚠ NOT verified by the pre-implementation audit — `cr3` flagged this rather than passing it silently (C8).** It did not open either file to confirm they are unmodified, judging it an implementation-time check; neither appears in this epic's `git status`. **So AC-4 is the one AC in this story with no second-party check behind it, and it is the implementer's to discharge at the point of work.**
- [x] **AC-5**: Every symbol and path newly cited in the prose written by this story resolves in the repository. Verify each by opening it, not by recalling it.
- [x] **AC-6**: No rule file, doc, or agent definition **outside the two surfaces AC-4 freezes** is left contradicting the corrected text. The two exempt surfaces are `migrations/005_scheduled_report_runs.sql` and the `docs/ROADMAP.md` QUARANTINE row, both of which retain the old path deliberately per epic Technical Notes TN-5; **the exemption is this closed list and is not a judgment to extend.** Establish the rest with a symbol-only search per epic Technical Notes TN-13, and record what was searched and what was found in the story Notes — including surfaces deliberately left alone and why, and any surface that MENTIONS the stale citation without asserting it.
  - **THREE symbols are in scope, not two (`cr3` S04-1, added 2026-07-27): `_delete_team_scoped_data`, `_delete_team_anchor_and_orphan_data`, and `_query_freshness`.** The second is the one this AC previously omitted — cited as `generator.py` at `data-model.md:43`, **defined at `lifecycle.py:550`.**
    - **This is an UNRECORDED CLEAN, not a live defect, and the distinction is why the fix is cheap.** `cr3` ran the repo-wide `.md` sweep with a positive control (`_delete_team_scoped_data`, 26 files) and found **the only rule file, doc or agent definition carrying the stale third citation is `data-model.md:43` — which AC-6a already covers.** **⚰ CORRECTED 2026-07-27 — the clause that stood here was a ONE-SIDED CLAIM and it was mine.** It read: *"Every other hit sits in `.project/archive/**` or `.project/research/**`: records of what was observed, correctly outside AC-6's scope."* **That is true of the THIRD SYMBOL's sweep only, and reads as a statement about the sweep generally.** `ca-2` measured the other two: **`_query_freshness` hits `IDEA-057` and a data-engineer memory file; `_delete_team_scoped_data` hits `architecture-subsystems.md`, `docs/ROADMAP.md`, two data-engineer memory files, PM `archived-epics.md`, `IDEA-198` and `IDEA-103`.** **Rule files, docs and agent-memory among them — none of which is archive or research.** So: **the archive/research characterisation holds for `_delete_team_anchor_and_orphan_data` and for nothing else.** The epic's signature defect, in the AC written to bound a sweep, **correct-as-scoped and general-as-read** — the same shape as the adjacency finding, one layer down.
    - **Named here so the sweep's completeness is RECORDED rather than incidental.** As written, a reader of these ACs could not tell the third symbol's repo-wide cleanliness had ever been checked — and the next reader would re-derive what `cr3` has already run. **A clean result that nobody can see was obtained is indistinguishable from one nobody sought.**
  - **⛔ `.project/ideas/**` IS OUT OF SCOPE FOR THIS STORY — an explicit exemption, not a judgement call, added 2026-07-27 after the AC-stress pass surfaced a live site nobody anticipated.** `ca-2` found **`.project/ideas/IDEA-103-dead-table-retention.md`** carrying the stale path *"`_delete_team_scoped_data` in `src/reports/generator.py`"* and repeating the symbol in its checklist. **Its read is correct: that is a CRITERION, not evidence** — a reader is meant to go there and act, and they would land on a path where the symbol does not exist. **It is a real defect.**
    - **It is nonetheless NOT this story's to fix, and the reason is DOMAIN, not scope-protection.** `.project/ideas/` is **PM-owned**; `.claude/rules/**` routes to `claude-architect` under `agent-routing.md`, and idea files do not. **An implementer editing another agent's domain is a routing violation even when the edit is correct.**
    - **Recorded as a PM ACTION to be discharged at closure, not left silent** — which is what stops the exemption becoming a hiding place. **The point of naming it here is that an implementer meeting it now has an explicit boundary instead of a silent judgement**, which is the failure mode this AC's whole design fights.
  - **⚠ AC-6b (ruled 2026-07-27, PM4): SWEEP `.py` AND `.sql` FOR THE THREE SYMBOLS — REPORT ONLY, EDIT NOTHING.** Record every hit in Notes with its verdict. **You may NOT edit any file outside this story's two declared rule files on the strength of it**; a hit becomes an idea or a follow-on story, **routed by domain** — a stale citation in `src/**` is software-engineer's, not `claude-architect`'s, exactly as `.project/ideas/**` is PM's.
    - **Why this is added rather than deferred, and it is a narrow asymmetry rather than a general licence.** `ca-2` raised it as a gap in the AC and correctly refused to widen on its own authority. **The `.md` boundary is not defensible on the merits: this epic's own MAJOR-2 was a false comment in a `.py` file**, so "prose lives in `.md`" is the wrong cut for a sweep hunting false prose.
    - **What makes it addable HERE when the `ReclaimResult` docstring was NOT: story 04 has no approval yet.** The `ReclaimResult` fold was refused partly because `cr4` had already approved story 03 against its ACs and widening would have voided that. **No reviewer has approved story 04, so there is nothing to invalidate** — and the AC-stress pass has not started implementing. **That asymmetry is the whole reason, and it expires the moment story 04 is approved.**
    - **And this adds an OBSERVATION, not an EDIT.** The sweep already exists; only its glob changes, and the clause **forbids acting on the delta**. **A report cannot cause a routing violation.** Cost is one search; the return is that **the `.py`/`.sql` surface stops being unknown** — per this story's own principle, *a clean result nobody can see was obtained is indistinguishable from one nobody sought*, and right now nobody knows which this is.
  - **⚠ COVERAGE BOUND on AC-6 proper, stated because `ca-2` named it and did not widen on its own authority: AC-6's EDIT scope remains `.md` and the two declared files.** **A reader must not take AC-6's clean result as repo-wide across file types** — AC-6b reports the rest, it does not repair it. `ca-2` also flagged, without acting, that **`cascade_delete_team` carries stale `generator.py` citations in `IDEA-069`, `IDEA-070` and PM `archived-epics.md`** — outside this story's three-symbol scope, **named so nobody widens silently and so the next sweep starts from a known floor.**
- [x] **AC-6a**: **Every** citation of `src/reports/generator.py` inside `.claude/rules/data-model.md` is enumerated and each is either corrected or verified accurate. AC-1 is scoped to the `scheduled_report_runs` bullet and does not reach the others; at least one further citation in that same file names a symbol that is defined in `src/reports/lifecycle.py`, and at least one is accurate and needs no change. Regenerate the list **by searching the file for the bare path**, and NOT from this story, the epic, or any review finding. Record each citation with its verdict in Notes.
  - **Search the BARE path `src/reports/generator.py`, not the `::` prefix.** An earlier draft of this AC prescribed the `path::symbol` prefix — the path-precedes-symbol shape that epic Technical Notes TN-13 and this story's own Technical Approach both warn misses `data-model.md`, because that file writes some citations symbol-first with the path in parentheses. The bare path is a strict superset and catches both forms. **The three-source prohibition matters here specifically because a review finding named one of these sites**: an implementer holding a reviewer's named symbol plus a two-site floor can satisfy a weaker text without sweeping.
  - **The honest limit, so the bare-path search is not oversold**: it still misses a symbol cited with NO path, and a differently-spelled path. Both forms are live in `data-model.md`, which carries bare `lifecycle.py` / `reports_admin.py` / `game_loader.py` citations. claude-architect checked and found no bare `generator.py` in that file today, so no further sweep is required — but do not record the bare-path search as exhaustive.

- [x] **AC-7**: `.claude/rules/canonical-seams.md`'s "Canonical orphan-reference reclamation" bullet states that the orphan-team predicate keeps **four** operator/security roots and enumerates all four, the fourth being `scheduled_report_runs.own_team_id`. Today it states three and enumerates three, which story 01 makes false.
  - **AC-7a (the instrument, binding — REWRITTEN 2026-07-27 after the AC-stress pass found it unrunnable)**: the root COUNT and the enumeration are verified against **`_TEAM_BASE_PRED`** in `src/reports/lifecycle.py` — **NOT against story 01's story text, NOT against this AC, and NOT against the epic.** Record in Notes what you read. This AC exists because a root enumeration went stale; regenerating it from another document would reproduce the defect one file over.
    - **⚰ TWO DEFECTS, both BLOCKING, both found by `ca-2` attempting to satisfy this AC — the pass story 04 had never had.**
      1. **It named `_team_orphan_pred`'s COMPOSED predicate in the body and `_TEAM_BASE_PRED` in its sub-bullet. Different objects.** Composed = base **AND NOT `_TEAM_STAT_EXISTS`**, which adds six game-child clauses that are not roots. **`_TEAM_BASE_PRED` is the correct authority and the body is corrected to it** — counting roots against the composed predicate would require silently excluding the stat clauses, which is the same unstated class judgement defect (2) describes.
      2. **The instrument could not return four.** `_TEAM_BASE_PRED`'s SQL yields **SIX** `NOT EXISTS` clauses — `reports.team_id`, `games.home_team_id OR away_team_id`, `opponent_links.resolved_team_id`, `opponent_links.our_team_id`, `user_team_access.team_id`, `scheduled_report_runs.own_team_id`. **Reducing six to four requires the class "operator/security root", which appears NOWHERE in the SQL — only in the comment above it. And that comment labels the `reports` clause "The root", so the term is overloaded inside the very object this AC names as its authority.**
    - **⛔ THE CLASS BOUNDARY, STATED SYNTACTICALLY SO IT IS NOT RESOLVED SILENTLY (`ca-2`'s fix, adopted): the roots are the `NOT EXISTS` clauses over tables OTHER THAN `reports` and `games`.** That rule is checkable against the SQL literal **without reading the comment**, and it returns **four roots across three tables** (`opponent_links` twice). **State the rule you applied in Notes.**
    - **Why syntactic rather than by the word "root": the comment overloads the term**, so an instrument that keys on it inherits the ambiguity it was written to remove. **`reports`/`games` are the in-use test; the other four are the operator/security pins.** An implementer left to draw that line themselves draws it silently — **which is the exact defect AC-7a exists to prevent, sitting inside AC-7a.**
    - **⛔ AGREEMENT AMONG DOCUMENTS IS NOT VERIFICATION — this is the sharpest available statement of AC-7a and it is `cr2`'s, carried in its words because a paraphrase softens it.** This is an **exhaustive-class claim**: *"the predicate keeps FOUR roots, and here they are."* So **regenerate the root set from `_TEAM_BASE_PRED` yourself and DIFF it against the rule file's list.** ***"Do not verify by confirming spec, code and test agree — they can all descend from one under-enumerated source."*** That is precisely how this epic's own four-root defect survived planning, a Codex pass and an implementation round: every document agreed, and they agreed because they were copies. **A diff against the predicate can fail; a consistency check among documents cannot.**
    - **Story 04 has NOT been reviewed by anyone.** `cr2` flagged this AC and then drained without starting the story. **Nothing here has been checked against the tree by a second party** — treat every claim in this story, including this one, as unverified.
  - **AC-7b (scope bound)**: nothing else in that bullet changes. The six game-child tables, the exclude-not-clear qualifier, the owns-its-transaction exception and the deferral behavior are all still accurate and are not rewritten. If the exclude-not-clear parenthetical does not read correctly once a fourth root is inside it, re-scope the parenthetical rather than restating the bullet. Epic Non-Goals bar re-documenting the reclamation design, which E-273 already covered.
    - **✅ ANSWERED IN ADVANCE (`cr3` C2): NO re-scoping is needed. *"Exclude-not-clear, never destroyed or NULLed"* is TRUE of all four roots, and the parenthetical stands.** Also confirmed: the six game-child tables match the predicate's own comment with no drift (C5).
    - **⚠ BUT IT IS TRUE AS AN OUTCOME CLAIM, NOT A MECHANISM CLAIM — and this is the trap in the repair.** `scheduled_report_runs` **IS** in `_TEAM_PIN_TABLES`, and the pin loop hard-deletes from it. (⚰ **This cited "line 1136" until 2026-07-27. The entry is at 1158; 1136 falls inside the comment block above the tuple — the claim was true, the pointer was not.** Found by `cr5`. **REMOVED rather than corrected to 1158**: a line number in a story whose subject is stale citations is a figure that rots again on the next edit to that file, and `_TEAM_PIN_TABLES` is unique in the module. TN-7 and story 01 AC-9b both govern — cite stable anchors, and prefer REMOVE over restating a figure that is not load-bearing.) It is **UNREACHABLE while the keep-root stands** — a team carrying such a row is excluded from `team_ids`, so that DELETE matches nothing. **`opponent_links` and `user_team_access` are genuinely absent from the pin list; `scheduled_report_runs` is present and deliberately retained.** So: **do NOT let the corrected parenthetical imply the fourth root's table is absent from `_TEAM_PIN_TABLES`.** It is there on purpose (epic TN-10), and IDEA-198 is open on exactly that asymmetry.
    - **How `cr3` reached this is the part worth copying: it EXPECTED re-scoping to be needed, and opened the tuple rather than ruling from two code comments that both asserted the answer.** The code refuted its expectation. **Two agreeing comments were available and would have produced the wrong verdict** — the same "documents agreeing is not verification" shape AC-7a exists to enforce, arriving unprompted in the clause next door.

## Technical Approach
This is context-layer prose. The whole change is a claim about how the code behaves, so it is unverifiable by the test suite and must be resolved against the repository directly — `.claude/rules/tool-output-integrity.md`, "Prose you AUTHOR is a claim too."

Cite stable anchors — symbol names, section headings — not line numbers. Line numbers in this area have already rotted once, which is what produced the stale citation being fixed.

AC-6's search is where this story is most likely to go wrong. A pattern that assumes the path precedes the symbol misses this very file, because it writes the symbol first and the path second in parentheses. Use a symbol-only pattern, and treat an unexpected match count in either direction as a trigger to cross-check rather than a result. `.claude/rules/architecture-subsystems.md` already cites the correct path and needs no change; claude-architect confirmed this by opening the file — it cites `src/reports/lifecycle.py` for both `_delete_game_scoped_data_for_perspectives()` and `_delete_team_scoped_data()`. Confirm rather than assuming, but expect it to be clean.

**AC-6's sweep WILL produce at least one false positive, named here so you do not "fix" it.** `.claude/agent-memory/data-engineer/migration-immutability-basis.md` quotes `generator.py::_delete_team_scoped_data` — but quotes it AS AN EXAMPLE OF THE DEFECT, closing with "a citation naming a file that does not hold the thing." It AGREES with the correction; it does not contradict it, and editing it would destroy the record of what was observed. `.claude/agent-memory/product-manager/archived-epics.md` mentions the symbol with no path at all — likewise not contradictory. Both are agent-memory files: under `.claude/rules/agent-routing.md`'s own-memory carve-out they belong to their owning agent, so even a genuine defect in one is not yours to edit. This is the criterion-vs-evidence cut applied to the sweep's OUTPUT: a hit is not automatically a correction target.

**AC-7's file is a second surface with a different failure and a different instrument.** The `data-model.md` work is stale-CITATION repair — a path that no longer holds a symbol. The `canonical-seams.md` work is a stale ENUMERATION that story 01's change CREATES. That distinction is why this defect was invisible to every sweep the epic originally specified: epic Technical Notes TN-5 framed all context-layer work as citation repair, so a symbol-only search for the two cascade symbols never reaches a bullet that names neither. Do not try to satisfy AC-7 through AC-6's search.

On scope discipline: the sweep's status as a third deleter is worth one or two sentences where the cascade is described. It does not need a new section, and epic Non-Goals bar re-documenting the reclamation design, which E-273 already covered.

## Dependencies
- **Blocked by**: E-277-01
- **Blocks**: None

**Why, since the files are disjoint**: AC-2 requires `.claude/rules/data-model.md` to assert that a `scheduled_report_runs` row is a reachability root, and AC-7 requires `.claude/rules/canonical-seams.md` to state a FOUR-root count verified against **`_TEAM_BASE_PRED`** (⚰ **this said `_team_orphan_pred` until 2026-07-27 — RESIDUE from AC-7a's correction, surviving in the rationale after being fixed in the AC. Different objects: composed = base AND NOT `_TEAM_STAT_EXISTS`. Found by `ca-2`'s stress pass**). Both describe behavior story 01 adds, and neither is true until it lands — AC-7 doubly so, since verifying a count against a predicate that still composes three roots would produce the wrong answer with the right instrument. With no blocker, nothing prevented this story running first and committing a rule file describing code that is not there, which is the defect class this epic was formed to repair. The dependency is on CONTENT, not on file conflict.

## Files to Create or Modify
- `.claude/rules/data-model.md`
- `.claude/rules/canonical-seams.md`
- `epics/E-277-reclamation-followups/E-277-04-correct-cascade-citation.md` — **this story's own Notes.** AC-6, AC-6a, AC-6b and AC-7a all MANDATE recording searches and per-site verdicts here, so the file is a required output and was missing from this list. **`ca-2` wrote the Notes because the ACs require it and FLAGGED the gap rather than silently reconciling it** (`cr5` SHOULD FIX, 2026-07-27). **Any story whose ACs require a written record must list its own file here** — otherwise the mandated output has no declared home and a file-list check reads it as an unauthorised write.

## Agent Hint
claude-architect

## Definition of Done
- [x] All acceptance criteria pass
- [x] Code follows project style (see CLAUDE.md)
- [x] No regressions in existing tests

## PM AC Verdict — FINAL (2026-07-27, PM4)

**ALL ACs PASS.** Enumerated: **AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-6a, AC-6b, AC-7, AC-7a, AC-7b.** Eleven named. **`cr5` APPROVED round 1, no MUST FIX.**

**This story had NO EXECUTABLE GATE anywhere** — every AC is prose about code, and no test can fail if one is wrong. **So the verification below is the only instrument that could have failed**, and I read the delivered rule files rather than the story's account of them.

### Verified BY READING THE TWO RULE FILES

- **AC-7 / AC-7a** — `canonical-seams.md:52` states the predicate *"KEEPS **four** operator/security roots **across three tables**"* and enumerates all four, the fourth attributed to E-277-01. **I derived the same four independently from `_TEAM_BASE_PRED` by AC-7a's syntactic rule** (`NOT EXISTS` clauses over tables other than `reports`/`games`): `opponent_links.resolved_team_id`, `opponent_links.our_team_id`, `user_team_access.team_id`, `scheduled_report_runs.own_team_id`. **Exact match.** With `cr5`'s pre-registration and `ca-2`'s regeneration that is **three independent derivations of a number the rule file had as three.**
- **AC-7b** — the six game-child tables, the exclude-not-clear qualifier, the owns-its-transaction exception and the deferral behaviour are all present and unchanged. **And the H2 hazard is closed EXPLICITLY rather than by omission**: *"unlike the other two tables, `scheduled_report_runs` IS still a retained `_TEAM_PIN_TABLES` entry, deliberately kept though unreachable while that root stands, so being a root does NOT imply absence from the pin list."*
- **AC-1** — `data-model.md:72` cites `_delete_team_scoped_data` at **`src/reports/lifecycle.py`**. Correct.
- **AC-2** — `:73` records the third deleter, names **`cascade_delete_team` and `cleanup_orphan_teams` BY SYMBOL** (reading B, per my ruling — no *"the other two"*), carries `ca-2`'s **receives-versus-computes** signature test, and states the non-reach half explicitly: *"It roots its OWN team only and confers nothing on the opponent."*
- **AC-3** — the *"team deletion REMOVES the audit rows / report deletion only NULLs `report_id`"* statement is preserved at `:72`, and **`:73` is immediately adjacent to it**, which is what AC-3 required. A reader meets both halves together.
- **AC-5** — every symbol newly cited resolves. Note `:73`'s use of `_team_orphan_pred` is **CORRECT** — it describes what the code computes, which is the true-usage class my residue sweep preserved.

### Taken from others, NOT re-derived

**From `cr5`**: AC-4's frozen files unmodified at verdict time; the AC-7b word-diff; the grep establishing no line numbers authored into either rule file; AC-6b re-run on content rather than filename, finding exactly one stale-path assertion at `migrations/005_scheduled_report_runs.sql:58`, the known frozen surface. **From `ca-2`**: the AC-6/6a sweep verdicts in Notes.

### ⚠ PROVENANCE OF THE CLEAN RESULT — corrected, and the correction matters

`cr5` pre-registered two hazards (H1: the sweep returns three `generator.py` citations, **one of which is accurate and must not be "fixed"**; H2: the pin-list implication). **The dispatch lead relayed both to `ca-2` believing implementation was in flight.**

**It was not. `ca-2` had already completed and handled both INDEPENDENTLY, before either reached it.** So **the evidence a warning would have destroyed is intact: this clean result IS evidence about the ACs**, not about a warned implementer. The earlier draft of this note said the opposite and was wrong.

**⚠ THE ORDERING IS TESTIMONY, NOT MEASUREMENT — recorded at the strength it was actually established, at `cr5`'s request and by its own standard.** `cr5` verified the three file mtimes and stops there: **it did not and could not timestamp the relay.** That `ca-2`'s writes completed *before* the relay reached it rests on **`ca-2`'s attestation and the dispatch lead's account**, which nobody independently clocked. **Attributed, not asserted** — the same standard `cr5` applied to the story-file movement, applied here to a fact that happens to favour our conclusion. The clean-result reading above is only as good as that attestation.

**But `ca-2` then answered the real question against its own work, which is worth more than the evidence:**

> **AC-6a permits the right outcome but does not forbid the wrong one — there is no ⛔ of the kind story 05's twin trap got. It held because the IMPLEMENTER checked where each symbol was defined, not because the AC blocked the edit.**

**So AC-6a is a REPORTING criterion, not a PROTECTIVE one** — and note it still passes the reachable-red test, because *"record each citation with its verdict"* is checkable and the Notes carry `ACCURATE — left alone`. **Falsifiable and preventive are different properties, and this AC has only the first.**

**The discriminator is unchanged by any of it, and it is why AC-6a is not worthless:** a citation left alone *because it is accurate* and one left alone *because nobody looked* are **byte-identical in the diff**. The only thing that separates them is a written verdict — the same reason story 01's AC-9b required "no change needed" in writing.

**⛔ THIS IS AN AC-WORDING DEFECT FOR WHOEVER REUSES THE PATTERN — IT IS *NOT* A FINDING AGAINST STORY 04, AND THE FILING MATTERS.** Story 04 is **done and correct**: it satisfied AC-6a, and the sweep it delivered is right. **A story must not carry a finding against itself for a weakness in a criterion it MET** — that inverts what a verdict section is for and would leave the durable record reading as though the delivery were short. **The defect belongs to the AC's TEXT, and its audience is the next author who copies this AC shape.** Re-routed on the dispatch lead's ruling.

**The reusable sentence is `ca-2`'s, and the credit is returned deliberately** — `cr5` declined it, its own account being that **it turned a verdict into a property of the instrument, which is cheap once someone else has done the measurement.** The measurement was `ca-2` reporting `_query_freshness` as ACCURATE *with the mechanism attached*:

> **An AC that permits the right outcome does not thereby forbid the wrong one.**

**The concrete comparison, and it is what makes this actionable rather than an aphorism: AC-6a says *"corrected **or** verified accurate"* — a DISPOSITION, with no ⛔ naming the non-member that must survive. AC-8's twin clause next door NAMES THE FILE THAT MUST NOT BE TOUCHED.** Same trap shape, **same epic**, one AC protected against it and one not. That is the whole diff between a reporting criterion and a protective one, available to copy.

**⚠ AND THE EVIDENCE HERE IS BETTER THAN AN EXPERIMENT COULD HAVE GIVEN — `cr5`'s point, recorded because it bounds what any future review of this class can establish.** A clean diff **cannot** distinguish *"the AC prevented the wrong edit"* from *"the implementer happened to check"* — **the two are byte-identical.** No amount of reviewing produces that discrimination. **`ca-2` closed it by reporting the MECHANISM rather than the outcome, which only the implementer was positioned to do**: it held because the implementer resolved each symbol to its definition before editing. **A direct measurement of the AC's sufficiency, from the only party who could take it.**

**HARDENING DEFERRED TO AN IDEA, NOT LANDED HERE.** The delivered work already satisfies a stronger form, so tightening changes nothing about this story — and tightening an AC after implementation and approval is the move I refused for story 03's `ReclaimResult` fold. **The next sweep-style AC needs a ⛔ naming that an ACCURATE citation must not be "corrected", with resolve-each-symbol-to-its-`def` as the operation.** Captured with the other closure ideas.

### `IDEA-103` remains open and is MINE

**A live stale citation, left for routing reasons rather than merit** — `.project/ideas/` is PM-owned. `cr5` flagged it **so the exemption does not become the hiding place AC-6 warned about**, which is my own phrasing returned to me. **On the closure list.**

## Notes
Routed to `claude-architect` by Routing Precedence in `.claude/rules/agent-routing.md`: a story whose files include a context-layer path routes there regardless of primary domain. Deliberately kept as its own story rather than folded into a `software-engineer` story, since a split story would strand half of itself against that rule.

Two related items are OUT of scope and are being captured as ideas rather than fixed here: the append-only migration rule exists only in `.claude/agents/data-engineer.md` and not in `.claude/rules/migrations.md`, so a non-DE implementer touching `migrations/` would never see it; and `docs/admin/operations.md` describes the migration set as `001`-`011` when `012_teams_innings_per_game.sql` exists.

---

## Implementation record (`ca-2`, 2026-07-27)

All citations were resolved against the STAGED worktree tree, which carries story 01's 379 insertions into `src/reports/lifecycle.py` — not against `main` and not against planning-era text. Symbols, not line numbers.

### AC-7a — the rule applied, and what it returned

Read `_TEAM_BASE_PRED`'s SQL literal in `src/reports/lifecycle.py`, ignoring the comment block above it. Applied the AC's syntactic class boundary — **the roots are the `NOT EXISTS` clauses over tables OTHER THAN `reports` and `games`**. The literal yields six `NOT EXISTS` clauses; discarding `reports.team_id` and the `games.home_team_id OR away_team_id` clause leaves:

| # | Table | Column |
|---|---|---|
| 1 | `opponent_links` | `resolved_team_id` |
| 2 | `opponent_links` | `our_team_id` |
| 3 | `user_team_access` | `team_id` |
| 4 | `scheduled_report_runs` | `own_team_id` |

**Four roots across three tables** (`opponent_links` carries two). Diffed against `canonical-seams.md`'s list: exactly one member missing, `scheduled_report_runs.own_team_id`. That is the whole delta; the other three were already correct and were not rewritten. The count was NOT taken from story 01, this AC, the epic, or the code comment — the comment is a document, and verifying against it is the consistency check the AC forbids, one file closer in.

### AC-7b — the pin-list guard

`("scheduled_report_runs", "own_team_id")` **is** present in `_TEAM_PIN_TABLES`, unlike `opponent_links` and `user_team_access` which are genuinely absent. The `exclude-not-clear, never destroyed or NULLed` qualifier is preserved verbatim; a clause was appended inside the same parenthetical so a reader cannot infer root-ness ⇒ pin-list absence. Nothing else in the bullet changed — the six game-child tables, the owns-its-transaction exception and the deferral behavior are untouched.

### AC-6a — every `src/reports/generator.py` citation in `data-model.md`

Regenerated by searching the file for the **bare path**, not from this story, the epic, or any review finding. Three citations, three verdicts:

| Symbol | Verdict | Action |
|---|---|---|
| `_delete_team_anchor_and_orphan_data` | STALE — defined in `src/reports/lifecycle.py` | CORRECTED |
| `_delete_team_scoped_data` | STALE — defined in `src/reports/lifecycle.py` | CORRECTED (AC-1) |
| `_query_freshness` | **ACCURATE** — `def _query_freshness` really is in `src/reports/generator.py` | left alone |

Post-edit, `src/reports/generator.py` occurs exactly once in the file, and that occurrence is the accurate one. Per the AC's own honest limit, this search is **not exhaustive**: a symbol cited with no path, or a differently-spelled path, would evade it. Re-confirmed there is no bare `generator.py` variant in this file (total `generator.py` occurrences = 1).

### AC-6 — `.md` sweep, three symbols

`_delete_team_anchor_and_orphan_data` — sole live site was `data-model.md`, now corrected. `.project/archive/**` and `.project/research/**` hits excluded as evidence. **Disclosed limit: that exclusion was applied by PATH, in bulk, without opening the files** — the criterion/evidence cut applied to a directory rather than to a file.

Surfaces deliberately left alone:

- `.claude/rules/architecture-subsystems.md` — already cites `src/reports/lifecycle.py`. Confirmed by opening, not assumed. No change needed.
- `migrations/005_scheduled_report_runs.sql` and the `docs/ROADMAP.md` QUARANTINE row — the AC-4 closed exemption list (TN-5). Both verified unmodified at the point of work by `git status`, discharging the one AC with no second-party check behind it.
- `.claude/agent-memory/data-engineer/migration-immutability-basis.md` — MENTIONS the stale citation without asserting it; quotes it *as an example of the defect*. Editing it would destroy the record. Also another agent's memory (own-memory carve-out).
- `.claude/agent-memory/data-engineer/reclamation-schema-lessons.md`, `.claude/agent-memory/product-manager/archived-epics.md` — name the symbol with no path; non-contradictory, and not mine to edit.
- `.project/ideas/**` — explicitly out of scope per AC-6's exemption. **`IDEA-103-dead-table-retention.md` carries the stale path and repeats the symbol in its checklist. It is a real defect and a criterion, not evidence, but `.project/ideas/` is PM-owned; editing it would be a routing violation even though the edit would be correct.** Left untouched for PM to discharge at closure.

Out of this story's three-symbol scope, named so nobody widens silently and the next sweep starts from a known floor: **`cascade_delete_team` carries stale `generator.py` citations in `IDEA-069`, `IDEA-070` and PM `archived-epics.md`.** Not touched.

### AC-6b — `.py` / `.sql` sweep, REPORT ONLY, nothing edited

Ran the three symbols across `*.py` and `*.sql`. **Result: the non-`.md` surface is clean of stale PATH citations, with exactly one exception, and that exception is already frozen.**

| Site | Content | Verdict |
|---|---|---|
| `migrations/005_scheduled_report_runs.sql` | `src/reports/generator.py::_delete_team_scoped_data` | STALE — but the AC-4 frozen surface (TN-5). Not edited. Already known; not a new finding. |
| `src/reports/lifecycle.py` (def + callers + one comment) | `_delete_team_scoped_data`, `_delete_team_anchor_and_orphan_data` | Accurate; no path asserted |
| `tests/test_report_generator.py` | `_delete_team_anchor_and_orphan_data` in a docstring, `_query_freshness` import + tests | Symbol only, no path. Clean |
| `src/reports/generator.py` | `_query_freshness` def + callers | Accurate |
| `migrations/002_report_generation_runs.sql`, `src/db/reconcile_at_load.py`, `tests/test_report_golden.py` | `_query_freshness` | Symbol only, no path. Clean |

So the `.py`/`.sql` surface is now a **recorded** clean rather than an unknown one — no follow-on idea or story is warranted from this sweep, because the only stale site it found is one the epic already froze by name.

### Two defects in the story file itself — REPORTED, not fixed

1. **`## Files to Create or Modify` lists only the two rule files**, yet AC-6, AC-6a, AC-6b and AC-7a all require recording in this story's Notes. Writing this section is therefore mandated by the ACs and unlisted by the file. Flagged rather than silently reconciled.
2. **`## Dependencies` still says AC-7 verifies "a FOUR-root count verified against `_team_orphan_pred`"** — superseded by AC-7a's rewrite to `_TEAM_BASE_PRED`. Those are different objects (composed = base AND NOT `_TEAM_STAT_EXISTS`), which is defect (1) of the two the AC-stress pass found, surviving in the rationale paragraph after being fixed in the AC. Story text is PM-owned; not edited.
