# E-277-01: Pin audit rows as a reachability root; correct the root rationale

## Epic
[E-277: Reclamation Follow-Up Repairs](epic.md)

## Status
`DONE`

## Description
After this story is complete, an own team carrying `scheduled_report_runs` rows is excluded from the orphan-team set, so the reclamation sweep no longer deletes it or its non-regenerable audit history. The comment above the root-exclusion clauses in `_TEAM_BASE_PRED` carries a per-root verdict instead of the current false generalization, and three `tests/test_report_generator.py` fixtures are restored to the production shape they were flipped away from.

## Context
These three changes are ONE story because they are the same change seen from three sides. The new root clause lands directly beneath the comment whose claim is false — splitting those means whichever lands second silently reopens the other. And the three drifted fixtures were flipped precisely to survive the sweep this story adjusts, so restoring them depends on the keep-root existing.

Read epic Technical Notes TN-1 before starting: the audit handoff's framing of this defect is wrong, and the false version is the more persuasive one. TN-2 bounds what is actually at risk (placeholder slots only, and NOT the concurrency lease — do not write an AC claiming otherwise). TN-4 explains why own teams are in the orphan base set. TN-10 is binding on scope.

**Also read the epic Non-Goal "Protecting own teams in general" before writing any code**, because it bounds a different thing than TN-2 does and it is the bound most likely to be over-read from this story alone. What you are building preserves audit history for an own team *that has slots*. It does NOT make own teams undeletable — a no-games own team has zero slots, nothing pins it, and it is still swept and recreated harmlessly. Do not reach for membership awareness, `team_urls` awareness, or `is_active` to close that gap; it is deliberately open.

## Acceptance Criteria
- [x] **AC-1**: Given an own team in the exposed shape (`membership_type='tracked'`, no `reports` row, no `games` row, no `opponent_links` row, carrying `scheduled_report_runs` rows with `resolution_outcome='deferred_placeholder'`), when `reclaim_orphan_reference_data` runs, then the team row, its audit rows, its roster, and its roster-only players all survive, and `ReclaimResult.teams_deleted` is 0.
- [x] **AC-2**: Given the same team but with its `scheduled_report_runs` rows removed, when the pass runs, then the team IS deleted — demonstrating the new root produced AC-1's outcome and not some unrelated exclusion.
- [x] **AC-3**: Given a team deleted through a deliberate path (`cascade_delete_team`), when the deletion runs, then its `scheduled_report_runs` rows are still deleted — the cascade required by migration 005 is unchanged. Per epic Technical Notes TN-1.
- [x] **AC-4**: The `_TEAM_PIN_TABLES` tuple list is unchanged — no entry added, removed, or reordered — and its `scheduled_report_runs` entry carries a comment recording that it is deliberately retained as an FK-safety net, is unreachable while the keep-root stands, and must not be removed unless the keep-root is removed in the same commit. Per epic Technical Notes TN-10.
- [x] **AC-5**: The comment above the root-exclusion clauses states a verdict for each of the four roots individually — what it protects and under what conditions it fires — and contains no claim generalizing across all of them in either direction. **For any root the comment says cannot fire, it states the MECHANISM**, not merely the verdict, and per AC-6b that mechanism must be one a reader can check by opening the enforcing code. A restatement of the old false reasoning in per-root form ("resolved_team_id: no-op — a resolved team is out of the base set") does NOT satisfy this: the standard is that a non-author can check the claim from the text.
  - **AC-5a (added 2026-07-27 — the vocabulary must not force a false choice).** An earlier version of this AC offered exactly two labels, "a no-op on real data or load-bearing." **That binary is not adequate to the facts and is part of how the false verdict survived**: a root that is unreachable through the normal UI but reachable through a production write path fits NEITHER label, and an implementer forced to pick one must state something false. **The comment uses as many classes as the evidence supports, and each root's entry says what it means rather than relying on a label.** Where a root sits between "fires routinely" and "cannot fire," the entry states **both halves explicitly** — what reaches it and what does not — per the epic's two-sided-claim standard. A verdict of "cannot fire" is reserved for a root with **no** reachable write path, and requires the quoted enforcing line AC-6b demands.
  - **Deliberately NOT fixing the class COUNT here.** This AC does not say how many classes there are, because at the time of writing the taxonomy is still being re-derived by search and any number written now is a figure that rots. Derive the classes from the writers; do not fit the writers to a count.
- [x] **AC-6**: Each verdict asserted in AC-5 is established by the instrument appropriate to it, and the comment or Notes state which instrument backs which verdict.
  - **AC-6a (the two LIVE roots — `opponent_links.our_team_id` and the new `scheduled_report_runs.own_team_id`)**: confirmed by execution — a run with the clause present and a run with it removed, with the observed outcomes recorded in Notes. **The fixture MUST be built through the production path** (the canonical team upsert, the real slot writer) rather than hand-seeded: that is what makes the execution settle a verdict rather than merely demonstrate the clause, and it is the distinction AC-6c turns on. Each live root also names its production writer.
  - **AC-6b (the remaining two roots — `opponent_links.resolved_team_id` and `user_team_access.team_id`)**: their verdicts are DERIVED by auditing what production can WRITE, and recorded in Notes. **This AC states no verdict and names no gate; supplying either is what broke its first version.** The obligation, per root: (i) enumerate **every** site that writes the column, (ii) for each writer, **open the code that would have to prevent a row matching a team in the orphan base set and QUOTE the enforcing line**, and (iii) where no such enforcement sits on that write path, the verdict is **not** "cannot fire" — say what it is instead. An enumeration that finds writers and stops has not settled the verdict, and neither has one that names a gate without opening it.
    - **Two traps, stated without giving the answers away.** The two roots may not have the same verdict or the same reason — do not establish one and generalize to the other. And **a function that supplies the OPTIONS a form offers is not a gate on the write path**: a request is not restricted to the options a form rendered, so the enforcing line must sit between the submitted value and the INSERT.
    - **Why this AC was tightened, 2026-07-27 — log kept because the looser form was MET and still produced a false verdict.** The original text pre-labelled these two as "the two DEAD roots" and then supplied the mechanism for one of them (that grants are restricted to `membership_type='member'`, so none can attach to a `tracked` team). **Both the label and the mechanism were wrong**, and an AC that hands over the verdict and its reason cannot fail honestly — the implementer confirmed what it had been told, which is the handed-list failure this epic names elsewhere, embedded this time in the instrument meant to prevent it. The fix has two halves and needs both: **strip the pre-supplied answer** (spec defect — this AC's own content was false), and **require the gate be opened and quoted rather than named** (evidence standard — the loose form was satisfiable by naming a plausible gate).
  - **AC-6c (binding, and the reason 6a/6b are separated)**: a present/removed execution run against a seeded synthetic row MUST NOT be recorded as evidence for a no-op verdict. Every clause in a conjunctive predicate changes the outcome once its column is populated, so such a run returns the load-bearing signature for ALL FOUR roots — see Technical Approach. Recording it as confirmation produces the mirror image of the false comment this story exists to repair.
- [x] **AC-7**: The three drifted fixtures in `tests/test_report_generator.py` — `TestPublicIdBackfill::test_unique_collision_does_not_abort_report`, `TestGenerateReportFailures::test_credential_expired_sets_failed`, and `TestQueryBeforeCleanup::test_queries_run_before_cleanup` — carry `membership_type='tracked'` again and pass, all three pinned with an `opponent_links` row on `our_team_id` (the named default — see Technical Approach). If a different mechanism is used, all three use the SAME one and the deviation is recorded in Notes.
- [x] **AC-8**: Existing tests pass, and the two `cascade_delete_team` tests in `tests/test_report_generator.py` — `test_cascade_delete_team_preserves_games_row_when_other_perspective_remains` and `test_cascade_delete_team_drops_games_row_when_last_perspective` — pass **literally unchanged**. Note both named tests live in `tests/test_report_generator.py`, a file this story already modifies; they are not in the orphan-reclamation file.
  - **AC-8a (the carve-out, and its conditions)**: a pre-existing test whose FIXTURE encodes the pre-keep-root reachability semantics — i.e. it seeds an audit row on a team it then asserts the sweep deletes — asserts the negation of AC-1 and cannot pass under any correct implementation. Such a test MAY be updated, subject to all four of: (i) the edit is the minimum that removes the contradiction, (ii) an in-test comment records why the old shape is now impossible, (iii) any behavior that is still REQUIRED after this story is re-covered by a named new test, and (iv) every test updated under this carve-out is listed in Notes. **Semantics may not be edited to make a test pass** — only fixtures encoding the superseded reachability rule.
  - **Why AC-8 was re-authored rather than waived (PM ruling, 2026-07-27).** As originally written, AC-8 required existing tests to pass *unchanged* and was **not satisfiable alongside AC-1** — a genuine unsatisfiability, not a spec defect. `test_reclaims_tracked_orphan_team_and_its_pins` seeded a `scheduled_report_runs` row on its orphan fixture and asserted the sweep deleted it; once that table is a keep-root such a team is not an orphan by design, so the fixture contradicts itself and there is no version of the keep-root that leaves it green. Two things make the carve-out safe rather than a hole: the deleted assertion covered a behavior that is now **impossible by design**, not one merely inconvenient to keep; and the behavior that IS still required — audit rows dying with a DELIBERATELY deleted team, per migration 005 and AC-3 — is re-covered by `test_cascade_delete_team_still_removes_audit_rows`. **Coverage was re-pointed, not dropped.** The implementer flagged this for adjudication instead of reporting AC-8 satisfied, which is why it was caught as a spec problem rather than absorbed as an implementation liberty.
- [x] **AC-9**: Every site that ENUMERATES or COUNTS the reachability roots, **across ALL THREE files this story modifies** — `src/reports/lifecycle.py`, `tests/test_orphan_reclamation.py`, and `tests/test_report_generator.py` — is updated or explicitly justified as needing no change. The list of such sites is regenerated **by search across those three files** — not taken from this story, from the epic, or from any review finding — and what was searched and what was found is recorded in Notes. The root ADDITION falsifies these sites independently of the comment repair; see Technical Approach.
  - **The module-only scope was a defect in an earlier draft, and it is the same one this AC exists to prevent.** That draft swept `src/reports/lifecycle.py` alone. **At least one three-root enumeration is known to exist OUTSIDE that module, in a file this story already modifies** — its location is deliberately NOT named here, because naming it converts the sweep into a two-site checklist and an AC that checks a reviewer's named sites inherits that reviewer's fallibility. Search for it. If your search finds none, that is a result worth reporting, not a reason to stop.
  - **OUT of scope, and it is not an oversight**: `.claude/rules/canonical-seams.md` also carries a root enumeration that this story falsifies. It belongs to **story 04**, which owns both rule files and verifies the count against **`_TEAM_BASE_PRED`** (⚰ residue: said `_team_orphan_pred` until 2026-07-27; corrected when AC-7a was rewritten). Do not edit it here — two stories editing one file is the conflict the serial chain exists to avoid.
  - **AC-9a**: the sweep covers prose **this story itself writes**, not only pre-existing sites. AC-4's new `_TEAM_PIN_TABLES` comment makes a claim about the root set and is therefore in scope for AC-9 once written. Run the sweep AFTER the story's own edits land, or it misses the sites the story created — which is the same under-scoping the root-cause note in Technical Approach describes.
  - **AC-9b (the tightening, added 2026-07-27 AFTER this story's work was done — read the regress note before applying it).** Every site the sweep surfaces gets ONE of three dispositions, recorded in writing:
    1. **REMOVE the count where it is not load-bearing — PREFERRED.** A delete-step comment does not need to enumerate the root set to say what it never touches. This is the only disposition that SHRINKS the claim surface, and it is preferred because this story CREATED its own exposure: every count it added was a new thing to keep in step with the root list, and the ones it added were the ones that were wrong.
    2. **NAME THE UNIT where the count IS load-bearing** — "three roots across two tables". The domain has more than one unit of measure (roots, tables, columns, classes, clauses), so a bare count beside a plural noun is not checkable.
    3. **RECORD "no change needed" EXPLICITLY, in writing.** A sweep can surface a line and drop it at the ruling step; that gap, not the pattern, is what produced the round-2 failure.
    - **Counts in ANY FORM, notation included.** `x2` is a count. So is a numeral, a number-word, and a range. A pattern built for number-words reaches none of the others.
    - **The sweep's PATTERN needs a gap class that permits letters** — `[^a-z]` cannot span an intervening word, so "four **reachability** roots" silently does not match while "two roots" does.
    - **⚠ REGRESS NOTE, binding on how this AC is read.** This clause was written AFTER the round that prompted it, and **that round already satisfies it** — the regenerated sweep used a letter-permitting pattern, adjudicated every surfaced line in writing, and preferred REMOVE, leaving four load-bearing count-adjacent statements and no global tally. **So AC-9 passes under both the original and the tightened text, and this clause is NOT grounds to reopen it.** It binds the next story that adds a root. Stated because the alternative is a regress in which every round's lesson reopens the round that produced it — and because a later reader finding a tightened AC above an older PASS would otherwise reasonably conclude the verdict was unearned.
- [x] **AC-10**: Any `TN-N` marker inherited in rewritten module comments is qualified as `E-273 TN-N`, since those markers refer to E-273's numbering and this epic has its own numbered Technical Notes meaning different things. No bare `TN-N` referring to an E-277 note is introduced into module comments.

## Technical Approach
The orphan-team predicate is composed from reusable SQL fragments and defined once, then reused by the team producer, the player producer's surviving-roster test, and the orphan-held roster count. Add the exclusion to that single definition — do not add a second filter at any call site, and do not re-inline the predicate.

**Read AC-6c before you run anything — the obvious instrument gives a confidently wrong answer.** Software-engineer executed the present/removed matrix against the two roots this epic calls dead, seeding each root's own column, and got the SAME signature the load-bearing `our_team_id` root produces: clause present, the team survives; clause removed, the team is deleted. All four roots look load-bearing under that test. That is not a quirk of the seeding — it is what a conjunctive predicate does once the column is populated. So execution establishes the clause's MECHANISM and cannot establish whether the root fires on real data.

**Earlier drafts of this story said software-engineer "had already executed the per-root verdicts; AC-6 asks you to reproduce them, not discover them." That was wrong in the dangerous direction and is corrected here** — it would send an implementer to reproduce an instrument that answers the question for one root and actively misleads on two.

**The precise split, confirmed by software-engineer in the review round: ONE of the four verdicts is settled by execution; the other three rest on reading or enumerating production writers.** `our_team_id`'s verdict does rest on execution, legitimately, because that fixture was built through the production path rather than hand-seeded — which is exactly the distinction AC-6a and AC-6c encode. The new root's MAJOR-1 mechanism was executed, but its load-bearing STATUS rests on `_upsert_slot` being a real writer. `resolved_team_id` rests on writer enumeration alone. `user_team_access.team_id` rests on reading the grant path. Adopting a synthetic-seed execution as verdict evidence for the last two is precisely the failure AC-6c bars.

The verdicts, and the instrument behind each:
- `opponent_links.our_team_id` — **load-bearing**. Writer in `src/gamechanger/opponent_ladder.py` on the morning-run path. The only thing keeping a morning-run own team out of the orphan set.
- `scheduled_report_runs.own_team_id` (the new root) — **load-bearing**. Writer `_upsert_slot` in `src/reports/morning_run.py`. Fires on ordinary data, same class as `our_team_id`.
- `opponent_links.resolved_team_id` — **dead, for a stronger reason than the current comment gives: no site in `src/` or `scripts/` writes that column at all.** The only non-read occurrence is lifecycle's own cascade `UPDATE opponent_links SET resolved_team_id = NULL, ...`.
- `user_team_access.team_id` — **⚠ THIS BULLET WAS FALSE AND IS THE SOURCE OF A SHIPPED DEFECT. Do not restore it.** It read: "**dead**, for the reason the comment does give: `_get_available_teams()` … selects `WHERE membership_type = 'member'` only, so a grant cannot attach to a `tracked` team through the admin surface." **`_get_available_teams()` supplies the checkbox OPTIONS at render time and gates nothing**, and the admin surface is precisely where the write is unfiltered — the clause "through the admin surface" was not merely unsupported but backwards. **Derive this root's verdict yourself under AC-6b; this story deliberately no longer tells you what it is.** The correction was reached independently by code-reviewer and PM, each opening the write path; the original claim had passed planning, a Codex pass, and an implementation round.

So the honest comment describes two live roots and two dead ones. AC-6b asks you to regenerate the writer enumeration yourself rather than inherit this list. **If your enumeration disagrees with any of it, report that rather than deferring to it.**

Worth one line in the comment or nearby: the original claim was **outlived, not careless**. E-273 reasoned that `our_team_id` is always a member team because the morning run iterates the operator's own teams — sound against a world E-239 ended when it removed the member sync. Per epic Technical Notes TN-4.

For AC-5, note the failure mode being corrected. The existing comment is a one-sided generalization in the closing position of a safety note, which is where this repo has repeatedly shipped false claims. The fix is not a differently-worded blanket claim; it is a set of statements a non-author can check from the text.

For AC-7, software-engineer verified that flipping the collision partner back to `'tracked'` without a pin makes that test FAIL on its `public_id is None` assertion — the gameless tracked duplicate is swept at generate-start, the backfill then succeeds, and the UNIQUE collision the test exists for never occurs. Neutralizing the other two produces `FOREIGN KEY constraint failed` on `INSERT INTO reports`, because the sweep deletes team id=1 while the mocked `ensure_team_row_with_provenance` still returns a hardcoded `1`. The remedy they ran green on all three: keep `'tracked'` and pin the fixture team with a keep-root row. Either an `opponent_links` row on `our_team_id` or a `scheduled_report_runs` row will now serve — AC-7 requires one choice applied to all three so the fixtures stay uniform.

**Use `opponent_links` — this is the NAMED DEFAULT in AC-7, not a preference to weigh.** It was a preference in an earlier draft; two independent reasons upgraded it. Data-engineer: pinning with the NEW root couples three unrelated `test_report_generator.py` fixtures to the least-settled root in the codebase, so a future epic revisiting it fails three tests for reasons unrelated to what they test — `opponent_links.our_team_id` is the pre-existing, load-bearing root and the more stable anchor. Software-engineer: the two options are not equally cheap, and it ran the remedy green with `opponent_links`. A `scheduled_report_runs` pin requires `own_team_id`, `opponent_root_team_id`, `game_date` AND a `resolution_outcome` drawn from a four-value CHECK vocabulary; an `opponent_links` row needs three NOT NULL columns and no CHECK. Naming the default spares the implementer discovering a CHECK vocabulary to satisfy a test-only pin.

**Both options carry a `NOT NULL` trap, pre-empted here to save a cycle** (data-engineer hit the first doing exactly this): an `opponent_links` row requires `opponent_name`, and a `scheduled_report_runs` row requires a non-NULL `(own_team_id, opponent_root_team_id, game_date)` triple plus a CHECK-valid `resolution_outcome`. A fourth `'member'` seed elsewhere in that file predates the audit baseline and is out of scope.

**On blast radius — two different radii here, and conflating them is what under-scoped an earlier draft of this story.** The FALSE COMMENT has a blast radius of exactly one live site, and that is true. But **the ROOT ADDITION has a wider one**, and it is independent of the comment repair: any site that enumerates or counts the roots goes stale the moment a fourth root exists, whether or not the comment is touched. An AC written from the conflated premise will always under-scope, which is what happened — AC-9 exists because of it. Regenerate the site list by search (AC-9); do not work from any list handed to you, including this paragraph.

Note also that the module's comments carry bare `TN-N` markers from **E-273's** numbering, while this story's body cites **E-277's** notes. A rewrite that preserves bare markers silently rebinds them to the wrong epic's notes — AC-10.

The archived E-273 epic carries the same rationale twice; those are the dated record of what was decided — evidence, not criteria. Leave them.

Constraints: synthetic DBs from `migrations/` only; never touch `data/app.db`; no `bb` commands. Do not use real team names or `public_id` values.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-277-02, E-277-04, E-277-05

## Files to Create or Modify
- `src/reports/lifecycle.py`
- `tests/test_orphan_reclamation.py`
- `tests/test_report_generator.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-277-02**: The final shape of `_TEAM_BASE_PRED` and its comment. Story 02 edits the same module and must not disturb either.
- **Produces for E-277-04**: The keep-root itself — the fact that a `scheduled_report_runs` row excludes its own team from the orphan set. Story 04 writes that behavior into `.claude/rules/data-model.md` and cannot truthfully do so until this story has added the clause. **Also produces the FOURTH ROOT that falsifies `.claude/rules/canonical-seams.md`'s three-root enumeration** — story 04 owns that repair and verifies the new count against **`_TEAM_BASE_PRED`** (⚰ residue: said `_team_orphan_pred` until 2026-07-27), so leave the final shape of the predicate legible enough to be read off.
- **Produces for E-277-03**: A rewritten `_orphan_team_ids` docstring. Story 03 edits that SAME docstring for a different reason (its stale `999` citation), one line from the root enumeration this story rewrites. Serial execution makes this safe; it is stated so story 03 does not discover it.

## Definition of Done
- [x] All acceptance criteria pass
- [x] Tests written and passing
- [x] Code follows project style (see CLAUDE.md)
- [x] No regressions in existing tests

## PM AC Verdict (2026-07-27)

**ALL ACs PASS. Story 01 is AC-complete.** Boxes are ticked at the DONE flip, on the dispatch lead's confirmation of both gates; this section is the verdict of record until then.

| AC | Verdict | Basis |
|---|---|---|
| AC-1 (mechanism), AC-2, AC-3 | PASS | PM read the fourth root clause in `_TEAM_BASE_PRED`; behavior tests in Notes |
| AC-4 | PASS | PM read `_TEAM_PIN_TABLES` and its retention comment — all three required elements present, `_TEAM_STAT_EXISTS` precedent cited |
| **AC-5 / AC-5a** | **PASS** | **PM read the per-root comment in full.** Four per-root verdicts, three classes, no blanket claim either way. The self-falsified "only thing" claim is now historical and TWO-SIDED — it states the slot write is gated on `not dry_run and not slot.suppress_persist`, NOT on outcome, so overlap is the ordinary case, and it names the three link-without-slot states and the converse gap. "CANNOT FIRE" is used for exactly one root, the one with no writer at all |
| AC-6a | PASS | Notes' execution matrix, production-path fixtures |
| **AC-6b** | **PASS** | **PM read the corrected `user_team_access` bullet.** Gate opened and quoted, not named; writers enumerated; verdict is REACHABLE where no enforcement sits on the write path |
| AC-7 | PASS | Notes' fixture restores + anti-vacuity check (all three FAIL with pins neutralized) |
| **AC-8 / AC-8a** | **PASS** | See the AC-8a reasoning below — recorded rather than inherited |
| **AC-9 / AC-9a** | **PASS** | Regenerated sweep, every surfaced line adjudicated in writing. **See AC-9b's regress note: passes under both original and tightened text** |
| AC-10 | PASS | `cr` from the diff; the bare `(TN-2)` sits in a block this story did not rewrite |

**AC-8a's four conditions, ruled by PM rather than inherited.** `cr` recorded a tension: removing `scheduled_report_runs` from the test's reachable-pin list slightly exceeds "minimum" and was not needed to make the test green. **No violation, and here is why rather than merely that.** AC-8a's carve-out is scoped to *"a pre-existing test whose FIXTURE encodes the pre-keep-root reachability semantics."* **The pin-list entry IS such an encoding** — it asserts `scheduled_report_runs` is a pin the sweep reaches, which the keep-root makes false. Leaving it would have left the test green but VACUOUS, asserting deletion of a table that can hold no matching row. So removing it is inside "the minimum that removes the contradiction" once the contradiction is read as the encoded semantics rather than the failing assertion. Conditions (ii), (iii) and (iv) are met: comments explain why the old shape is impossible, `test_cascade_delete_team_still_removes_audit_rows` re-covers the still-required deliberate-path behavior, and the changes are listed in Notes.

**PROVENANCE — what PM verified vs. what PM takes from others.** This matters more here than anywhere, because **AC-9 was ruled PASS, then FAIL, then PASS by the same reviewer**.
- **PM read directly**: the fourth root clause; the full per-root comment including the corrected `our_team_id` and `user_team_access` bullets; `_TEAM_PIN_TABLES` and its retention comment; the Notes **in full**, including the Site B position and the retraction account; and, separately, the `isdigit()`-only validation at the two unfiltered admin write sites.
- **Taken from `se` and NOT independently re-derived**: the regenerated sweep's ~25 line-by-line verdicts, the suite result (`4279 passed`, exit 0), the ruff parity, and the three link-without-slot states.
- **Taken from `cr` and NOT independently re-derived**: the AC-10 diff ruling, the hunk-confinement proof (17 anchors unmoved), and the final micro-check.
- **PM did NOT re-run the sweep** and does not assert the four known unit errors were the last. AC-9's PASS rests on `se`'s regeneration and `cr`'s review, not on a PM enumeration.

## Notes

### AC-6a — execution matrix for the two LIVE roots (production-path fixtures)

Fixture built through `ensure_team_row` (canonical team upsert) plus the real production writer for each root — `_upsert_pending` from `src/gamechanger/opponent_ladder.py`, and `_upsert_slot` from `src/reports/morning_run.py`. Predicate clause removed by string replacement against `_TEAM_BASE_PRED`, with a control assertion that the clause was found verbatim before removal.

| root | clause PRESENT | clause REMOVED |
|---|---|---|
| `opponent_links.our_team_id` | `orphan_ids=[]` — survives | `orphan_ids=[1]` — deleted |
| `scheduled_report_runs.own_team_id` | `orphan_ids=[]` — survives | `orphan_ids=[1]` — deleted |

Both LOAD-BEARING, both confirmed against a fixture production can actually produce. Mirrored as permanent tests: `test_audit_root_keeps_placeholder_only_own_team` (AC-1) and `test_same_own_team_is_swept_once_its_audit_rows_are_removed` (AC-2).

### AC-6b — writer enumeration and gate-quoting for the remaining two roots

Regenerated rather than inherited. **Neither root's round-1 handling survived**, and the corrections are the substance of this AC. Answering the tightened form: every writer enumerated, and for each one the line that would have to enforce the constraint is **opened and quoted** rather than named.

#### `user_team_access.team_id` — verdict: **REACHABLE**

Three INSERT sites. Quoted per writer:

**(1) `src/api/auth.py::_assign_member_teams` — ENFORCED.** The enforcing line sits on the write path, selecting the ids it then inserts:
```
"SELECT id FROM teams WHERE membership_type = 'member'"
```
Every id reaching its INSERT comes from that SELECT, so this writer cannot produce a row on a `tracked` team.

**(2) `src/api/routes/reports_admin.py::_create_user` — NO ENFORCEMENT.** The whole write path:
```
for team_id in team_ids:
    conn.execute(
        "INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (new_user_id, team_id),
    )
```
There is no membership predicate anywhere between the request and this INSERT. The only transformation applied to the submitted values, in the `create_user` handler:
```
int_team_ids = [int(tid) for tid in team_ids if tid.strip().isdigit()]
```
That is a numeric-format filter, not a membership gate.

**(3) `src/api/routes/reports_admin.py::_update_user` — NO ENFORCEMENT.** Identical shape (`DELETE` then re-INSERT the submitted list), and its handler applies the same `isdigit()` filter and nothing else.

**The gate I cited in round 1 does not sit on the write path.** `_get_available_teams()` is:
```
"SELECT id, name FROM teams WHERE membership_type = 'member' ORDER BY name"
```
— but it is called only to render checkbox options and to re-render the form on error. Nothing constrains a POST to the options a form offered, so it cannot enforce anything about a submitted value.

**Verdict, per (iii): not "cannot fire" — REACHABLE.** Executed: a `user_team_access` row on a `tracked` team is accepted, and the orphan set goes `[1]` → `[]`.

**How the round-1 error happened.** My search corrections were real but fixed the wrong layer. I found all three writers (after widening past `INSERT OR IGNORE` — the TN-13 narrowing class, inside the AC written to prevent it), then **asserted the constraint from a SELECT that populates a form instead of opening the write path**. Enumerating writers is the easy half; I stopped there believing I had done both. This is exactly what the tightened AC now forbids, and I would not have caught it myself — `cr` did.

Also corrected: **three DELETE sites** (`reports_admin.py` ×2 plus lifecycle's cascade), not two as round 1 said. DELETEs cannot create a pin either way, but the count was presented as complete when it was not.

The absent server-side validation in `reports_admin.py` is **pre-existing and out of scope** — named as the reason for the verdict, not as a defect fixed here.

#### `opponent_links.resolved_team_id` — verdict: **CANNOT FIRE**

**Zero write sites**, so limb (ii) has no writer to open. The only SQL touching the column anywhere in `src/` or `scripts/` is this module's own cascade, which clears rather than sets it:
```
"UPDATE opponent_links SET resolved_team_id = NULL, resolution_method = NULL, "
"resolved_at = NULL WHERE resolved_team_id IN ({placeholders})"
```
No `INSERT` names the column, and no other `UPDATE ... SET resolved_team_id` exists. With no writer, there is no path that can produce a matching row — the verdict rests on absence, not on a gate.

**False positive found and classified:** a bare-name grep also hits `scripts/smoke_test.py` five times. Those are a LOCAL Python variable holding a GameChanger team id; that file contains **zero** occurrences of `opponent_links`. Pre-empted in the module comment so the next reader's grep does not read as counter-evidence.

**The two roots do NOT share a verdict or a reason** — one has no writer at all, the other has three writers of which two are ungated. Establishing one and generalizing to the other is precisely how round 1 failed.

- **`opponent_links.resolved_team_id` — CANNOT FIRE: no writer.** The only SQL touching the column is this module's own cascade (`UPDATE opponent_links SET resolved_team_id = NULL ...`). **False positive found and classified:** a bare-name grep also hits `scripts/smoke_test.py` five times; those are a LOCAL Python variable holding a GameChanger team id, and that file contains **zero** occurrences of `opponent_links`. Not a writer. Pre-empted in the module comment so the next reader's grep does not read as counter-evidence.
- **`user_team_access.team_id` — REACHABLE. ⚠ My round-1 verdict was WRONG; corrected here.** I originally certified this CANNOT-FIRE on the ground that both INSERT paths draw ids from a `WHERE membership_type = 'member'` SELECT. **That is false for two of the three INSERT writers**, as `cr` found by independently regenerating the enumeration. Only `src/api/auth.py::_assign_member_teams` filters on membership. The admin form handlers `_create_user` and `_update_user` in `src/api/routes/reports_admin.py` insert whatever integer team ids the POST supplies, with **no membership check** — `_get_available_teams()` populates the checkbox OPTIONS at render time and gates nothing on submit; the only filtering between form and INSERT is `[int(tid) for tid in team_ids if tid.strip().isdigit()]`. **Executed:** a `user_team_access` row on a `tracked` team is accepted, and the orphan set goes `[1]` → `[]`. So the clause is live protection, not a no-op.

  **How I got it wrong is the instructive part.** My search-method corrections were real but they fixed the wrong layer. I found the writers (after widening the pattern past `INSERT OR IGNORE` — the TN-13 narrowing class, hit inside the AC written to prevent it), and then **asserted the constraint from the SELECT that populates the form rather than tracing what the INSERT actually receives.** AC-6b's own words are "where writers exist, establish why no write can produce a row matching a team in the orphan base set" — enumerating the writers is the easy half, and I stopped there while believing I had done both. A grep finds writers; only reading each writer's data flow settles the verdict.

  Write-site census, corrected: **three INSERT sites** — `src/api/auth.py` (filtered, member-only) and `reports_admin.py` ×2 (**unfiltered**) — and **three DELETE sites** (`reports_admin.py` ×2 plus lifecycle's own cascade), not two as round 1 said. DELETEs cannot create a pin either way, but the count was presented as complete when it was not.

  The absent server-side validation in `reports_admin.py` is **pre-existing and out of scope for this story** — `cr` raised it only as evidence about the verdict, not as a defect to fix here.

### AC-9 / AC-9a — enumeration-site sweep

**Searched** (all three files, case-insensitive, run again after this story's own edits per AC-9a): count-word adjacent to `root` (`three|3|two|both|all|four`); every bare `root` occurrence minus id-column names; `TN-7` markers; lines naming both root tables; `survivor|root-excluded|pin-deleted`.

**Found and updated — `src/reports/lifecycle.py` (6):** the `_TEAM_BASE_PRED` root comment (the AC-5 rewrite); the FK-child audit classification (`scheduled_report_runs` now in TWO classes, so the classes are no longer mutually exclusive — stated explicitly); the `_TEAM_PIN_TABLES` preamble (its root/pin exclusion is no longer a partition); `_orphan_team_ids` docstring (three → four roots); `count_orphan_reference_data` docstring; the Step-4 delete comment.

**Found and updated — `tests/test_orphan_reclamation.py` (2):** the "three root survivors" section header, and `test_root_survivors_are_excluded_and_untouched`, which now covers a fourth survivor `(d)` in isolation.

**Found by EXECUTION, not by the search — 1 site, and this is the AC's own lesson:** `test_reclaims_tracked_orphan_team_and_its_pins` carries a pin-table enumeration as a *data list* (`for table, col in [...]`) plus a matching fixture seed. No prose token, so no wording pattern reaches it; it surfaced only as a test failure. A search over prose is not sufficient for enumerations expressed as code.

**Found and justified as needing NO change (2):** `lifecycle.py` "three root causes" refers to E-273's three orphan ROOT CAUSES (RC#1–3), not reachability roots. `test_orphan_reclamation.py`'s module docstring "the three predicates (team / player / roots exclusion)" counts predicates, not roots — still three.

**Out of scope, confirmed untouched:** `.claude/rules/canonical-seams.md` (story 04 owns it).

### AC-7 — fixture restores

All three restored to `membership_type='tracked'` and pinned with an `opponent_links` row on `our_team_id` (the named default). No deviation. **Anti-vacuity check:** with all three pins neutralized on a scratchpad copy, all three tests FAIL — two with `IntegrityError: FOREIGN KEY constraint failed` on `INSERT INTO reports`, one on its `public_id is None` assertion. The pins are load-bearing, so the fixtures now genuinely exercise the tracked production shape rather than passing for an unrelated reason.

### Behavioral Changes

**Not "None". Four externally observable changes.** The fourth was missed in round 1 and is the one worth noting: my first Behavioral Changes list was itself scoped to the consumer I had in mind, which is the same one-sided shape this story repairs.

1. **The reclamation sweep no longer deletes a `tracked` team carrying any `scheduled_report_runs` row.** Before: such a team, if gameless / reportless / `opponent_links`-less, was swept with its whole team-scoped surface including its non-regenerable audit history. Fires on ordinary morning-run data (placeholder-deferral slots), not only in a corrupt state.
2. **`ReclaimResult` counts drop for those inputs** — `teams_deleted`, `players_deleted`, `roster_rows_deleted` — and `count_orphan_reference_data` reports correspondingly fewer orphans. Anything trending reclamation counts across this change sees a step. *(The claim that the step IS the fix is mine and should be tested, not accepted.)*
3. **`_orphan_player_ids` and `_orphan_roster_row_count` narrow too**, because both embed the same predicate via `_team_orphan_pred`. A player whose only roster is on an audit-pinned team is no longer an orphan.
4. **`_warn_stat_referenced_gameless_teams` narrows — the FOURTH consumer of `_TEAM_BASE_PRED`, and not the orphan pass.** It composes `base AND stat_exists`, so a gameless team carrying **both** a stat row and an audit row no longer emits its WARN.

   **How it reaches that function matters more than the finding.** `git diff | grep -E "^[+-].*(warn_stat_referenced|_TEAM_STAT_EXISTS.format)"` returns **empty** — the function is textually untouched. The behavior travels through the shared `_TEAM_BASE_PRED` constant, not through any edited line. **A diff-reading author structurally cannot see this class of change**, which is why a caller audit is a separate obligation from reading one's own diff. I found it only because it was named to me; I did not find it, and I would not have.

   **My verdict: CORRECT IN DIRECTION, WITH A NAMED RESIDUAL — not "correct and harmless".** Two things are true and I want both on the record rather than the tidier one:

   - *Why the narrowing is right:* the WARN's stated job is to surface a team that the **stat clause** silently excluded, because that particular exclusion swallows the signal a reclamation-halting `IntegrityError` would have made loud. A team pinned by the audit root is excluded on a legitimate root *before* the stat clause is reached, so no signal is being swallowed, and the WARN's own wording — "excluded from reclamation despite no games" — would be actively misleading about why.
   - *The residual, which the reasoning above elides:* the underlying anomaly is a **gameless team carrying a game-child stat row**, and that anomaly does not stop existing because the team is pinned for an unrelated reason. For that one shape we now emit nothing at all, and no other surface reports it. So a genuine data-integrity oddity goes unreported.

   I judge the residual **acceptable but not zero**, bounded by the same argument that makes the whole stat clause belt-and-suspenders: the module already documents the shape as vacuous on real data, since a gameless team cannot carry a game-child row except in a synthetic corrupt state. Accepting it is a judgement about likelihood, not a proof of harmlessness, and it should be recorded as such rather than as "no effect."

   Pinned in both directions by `test_audit_root_suppresses_the_gameless_stat_warn` — the same team still WARNs without the audit row, so the narrowing is attributable to the audit root and not to the fixture.

**Explicitly NOT changed:** `cascade_delete_team` still deletes audit rows (migration 005's CASCADE MIRROR INVARIANT untouched, pinned by AC-3); `_TEAM_PIN_TABLES` byte-unchanged; no schema, migration, CLI or API surface change; a team with no audit rows is still swept and recreated exactly as before.

### AC-9/AC-9a REGENERATED SWEEP (round 3) — every surfaced line with a written verdict

Prior sweeps are treated as **unverified, not as a baseline**: `pm3` established that Sites A and B were both *in* my six-site list — reported as updated, and updated wrongly. An AC requiring sites be "updated or explicitly justified" is not met by updating them incorrectly.

**Regenerated, not patched, and not started from any list** — not `cr`'s four, not my two, not the remediation brief. Pattern: number-words, digits, and `x2` notation adjacent to `root|table|class|clause|predicate|pin|consumer|survivor`, across all three files, with SQL/identifier noise excluded.

**DISPOSITION (round 3, per `pm3`): three outcomes, and REMOVE is preferred over unit-naming.** The story created this exposure; every count claim it adds is a new thing to keep in step with the root list, so unit-naming everything *increases* the surface this story has demonstrated it cannot keep correct. A delete-step comment does not need to enumerate the root set to say what it never touches. Applied: **most counts are now GONE rather than unit-named.** The `_TEAM_BASE_PRED` bullets are themselves the enumeration, so the summary count above them was deleted rather than corrected — it existed only to be kept in sync. The Step-4 comment, the `_TEAM_PIN_TABLES` preamble and partition note, both docstrings, the FK-child classification and two test comments lost their counts entirely. Four count-adjacent statements remain, each load-bearing and none a global tally: that `opponent_links` carries two roots (the fact that makes root-count ≠ table-count), the historical "one root that is load-bearing", "the last two attempts to certify a root", and "via both its root columns".

**A count can hide in NOTATION, not just in a number.** The fourth error found here was `opponent_links x2` in the FK-child classification. `cr`'s pattern was `two of`; mine was number-words and digits. **Neither reaches `x2`.** That is a fifth costume for this defect, alongside: an enumeration as a data structure, a behavior change through a shared constant, a table count in root vocabulary, and a modified noun phrase a proximity gap-class cannot span.

**This found a THIRD unit error nobody had named** — `tests/test_orphan_reclamation.py`, the comment I added in round 2 to `test_count_excludes_roots_no_false_leak`, reading *"The docstring names three survivor roots; cover the other two here."* Those are three **TABLES**, not three roots, and the "other two" undercounts against four roots. **Mine, round 2, introduced while fixing this exact class.** That is the whole argument for regenerating over patching: a two-site patch would have shipped it.

**Verdicts — every line the sweep surfaced in the root/table/class domain:**

| Site | Verdict |
|---|---|
| `lifecycle.py` root-exclusion preamble ("the three from E-273 TN-7") | **FIXED** — now "THREE ROOTS … plus the ONE ROOT added by E-277-01" |
| `lifecycle.py` per-root taxonomy (four roots / three tables / three classes) | **NO CHANGE NEEDED** — units already named |
| `lifecycle.py` "one root that is load-bearing" | **NO CHANGE NEEDED** — unit named, singular |
| `lifecycle.py` "Neither root subsumes the other" | **NO CHANGE NEEDED** — unit named |
| `lifecycle.py` "The one CANNOT-FIRE clause" | **NO CHANGE NEEDED** — counts clauses, unit named |
| `lifecycle.py` "the last two attempts to certify a root" | **NO CHANGE NEEDED** — counts attempts |
| `lifecycle.py` FK-child audit ("opponent_links x2, user_team_access…") | **FIXED** — `x2` shorthand replaced with "THREE TABLES carrying FOUR ROOTS: opponent_links via TWO ROOTS…" |
| `lifecycle.py` "appears in TWO of those classes" | **NO CHANGE NEEDED** — counts classes, unit named |
| `lifecycle.py` `_TEAM_PIN_TABLES` preamble (**Site A**) | **FIXED** — was "two of the E-273 TN-7 roots" for two TABLES holding three ROOTS |
| `lifecycle.py` `_TEAM_PIN_TABLES` root/pin partition note (**Site A**) | **FIXED** — "TWO TABLES … carrying THREE of the FOUR ROOTS" |
| `lifecycle.py` `_orphan_team_ids` docstring | **FIXED** — units named throughout |
| `lifecycle.py` `count_orphan_reference_data` docstring | **FIXED** — was a bare 3-table list under "all four reachability roots"; now names both units |
| `lifecycle.py` Step-4 delete comment (**Site B**) | **FIXED** — see disagreement below |
| `lifecycle.py` "three root causes" ×2 | **NO CHANGE NEEDED** — E-273's RC#1–3, a different referent that merely shares the word "root" |
| `lifecycle.py` "two reusable SQL fragments" / "the ONE orphan-team predicate" / "TWO placeholders" / "two behavior-pinning cascade tests" | **NO CHANGE NEEDED** — count fragments, predicates, placeholders and tests; units named, domains unrelated |
| `test_orphan_reclamation.py` count-test comment | **FIXED** — the third error, above |
| `test_orphan_reclamation.py` "the FOUR root survivors" header | **NO CHANGE NEEDED** — "root survivors" names the unit; 4 is correct |
| `test_orphan_reclamation.py` "the three predicates" | **NO CHANGE NEEDED** — counts predicates |
| `test_orphan_reclamation.py` "two behavior-pinning cascade tests" / "the table's two team columns" | **NO CHANGE NEEDED** — count tests and columns |
| `test_report_generator.py` "all three restored fixtures" | **NO CHANGE NEEDED** — counts fixtures |

Re-run of the sweep after the fixes shows **every remaining count in the root/table domain carries its unit**.

### My position on Site B — UNRESOLVED on the reading, MOOT on the text

**Final record. It is not "I was right".** I reinstated my original finding on the grounds that `cr` conceded — which is the same deference failure as the retraction, pointing the other way. **"The reviewer disagreed" is not evidence, and neither is "the reviewer agreed."**

Engaging my own retraction argument rather than dropping it, since nobody refuted it: under a **column-scoped** reading of sentence 1, the text partitions the roots as `{resolved_team_id, user_team_access.team_id}` + "the other two roots" `{our_team_id, own_team_id}` = 4, and is self-consistent. **That argument still stands.** `cr`'s counter — the parenthetical exists only because sentence 1 is table-scoped, since a column reading leaves nothing to explain about "the same table" — is strong, but it is evidence about **which reading the author held**, not about which readings the text **licenses**. It does not refute the arithmetic under the column reading.

So the three positions answer three different questions and none refutes the others:

| Question | Answer |
|---|---|
| Is the text ambiguous / low-salience? | Yes — `cr` is the existence proof: a reader with the file open, actively hunting this conflation, landed on the column reading and certified it. |
| Which reading did the author hold? | Table-scoped, on the parenthetical evidence. |
| Is the count correct under the column reading? | Yes, 2+2=4. Under the table reading, no. |

**Both of my confident positions overstated.** "Wrong in three places" asserted the table reading as the only one; the retraction asserted the column reading as the only one. The accurate residue is that the sentence needed rewriting **under either reading** — and it has been, so the disputed text no longer exists in the file. **Unresolved on the reading, moot on the text.**

The transferable rule, symmetric: **a retraction needs the same standard of evidence as the original claim, and so does a reinstatement.** Conceding is not automatically the rigorous move; it is a way of being wrong that looks like being careful.

### How I retracted, which is the part worth keeping

Recorded in full because the retraction is more instructive than the finding.

**Round 2:** I reported Site B as wrong in three places. **Round 3, before `cr` conceded:** I re-read it, decided it partitioned by ROOT as `{resolved_team_id, user_team_access.team_id} + {our_team_id, own_team_id}` = 4, and **retracted, crediting `cr`.** **`cr` has since conceded and ruled my original finding correct.**

`cr`'s discriminating argument is the one I should have found and did not: **the parenthetical exists only because sentence 1 is table-scoped.** Had sentence 1 named two columns, `our_team_id` being "the same table" would be irrelevant — there would be nothing to explain. So sentence 1 is table-scoped, a table-scoped "two" apposed to "of the four reachability roots" is a unit error, and with three of four roots covered exactly **one** remains, not two.

`pm3` reaches the same remedy differently: **both readings are genuinely available, so the sentence is AMBIGUOUS rather than wrong**, and that fails AC-5's standard regardless of intent, because a non-author checking from the text gets two answers. Both routes are recorded; they differ on wrong-vs-ambiguous and agree on the remedy.

**What I got wrong is not the reading — it is why I changed it.** I retracted because a reviewer had ruled against me, having been told explicitly not to soften my position for that reason. It is the same deference failure I had named on MUST-4 one message earlier, aimed at a reviewer instead of a spec, and I committed it while congratulating myself for having spotted it. **A retraction needs the same standard of evidence as the original claim; "the reviewer disagreed" is not evidence.**

### AC-9 scope — my read

**Sites A and B are inside AC-9, and specifically inside AC-9a.** `cr` established from the diff that the removed lines carried **no numeral at all** — Site A was `(TN-7 roots)`, Site B was `(TN-7 roots, excluded from the orphan set by construction)`. Neither original miscounted because neither counted. Both counts are prose **this story introduced**, which is precisely AC-9a's subject. AC-9's PASS should not have held.

The sharper point: these were not sites my sweep **missed**. My sweep surfaced them and I wrote them wrong — a worse shape than an omission, and the one AC-9a exists to catch.

### Prior section — superseded



I reported two count errors against my own round-2 work. **On re-reading, only ONE of them was an error. `cr` is right about the other, and I am recording that rather than softening it.**

**Site A — the `_TEAM_PIN_TABLES` preamble — was genuinely wrong.** It called `opponent_links` and `user_team_access` "two of the E-273 TN-7 roots". Those are two TABLES, and between them they carry all THREE of E-273's roots, because `opponent_links` holds two. There is no partition under which that sentence is true — it labels tables as roots. Its companion, "the two roots that are not pins", is wrong the same way: THREE roots are not pins; TWO tables are not pin tables.

**Site B — the Step-4 delete comment — was NOT wrong. `cr` examined it deliberately and ruled it self-consistent, and `cr` is correct.** My report claimed three errors in it. Re-reading it as written, the text partitions the FOUR ROOTS as `{resolved_team_id, user_team_access.team_id}` plus "the other two roots", and its parenthetical names those explicitly as `opponent_links.our_team_id` and `scheduled_report_runs`. That is 2 + 2 = 4 and it is correct. **My error was applying a by-TABLE partition and then judging the text against it, when the text partitions by ROOT and uses table names only as labels for the first pair.** I diagnosed a unit confusion by committing one.

What is fairly said against Site B is much weaker than what I said: the opening clause is **ambiguous until the parenthetical resolves it** one sentence later, because "opponent_links / user_team_access — two of the four reachability roots" invites reading `opponent_links` as a single root when it carries two. Ambiguous-on-first-read is a real cost in a safety comment, but it is not the same claim as "wrong in three places", and I overstated it.

**Both sites are rewritten anyway**, because naming the unit cannot make a correct statement wrong and is strictly better than a correct bare number. Applied to every count in the module that sits near "root" or "table", including the ones I had already judged correct: the `_TEAM_BASE_PRED` taxonomy, the `_orphan_team_ids` docstring, both `_TEAM_PIN_TABLES` sentences, and the Step-4 comment. The form used throughout is **"FOUR ROOTS across THREE TABLES (`opponent_links` carries two)"**, which stays right when a fifth root lands.

**Why the sweeps missed these — MEASURED, and my earlier explanation was wrong.** I previously wrote that the sweeps' *category* was narrower than the defect class. **`cr` refuted that against its retained output — its pattern surfaced both sites verbatim.** I then tested my own round-1 AC-9a pattern against both site texts, and the measured answer is in **two halves, one matching `cr`'s and one not:**

- **Site A — surfaced by my own pattern and not verdicted.** `(three|3|two|both|all|four)[^a-z]{0,14}roots?` matches "the two roots that are not pins". It was in my output and I let it pass as background. Same failure as `cr`'s: the gap is between **surfacing and ruling**, not in the pattern. This is why "no change needed" must be written down per line — an unrecorded verdict is indistinguishable from an unread line.
- **Site B — genuinely NOT surfaced by my pattern, for a reason neither of us had named.** The gap class `[^a-z]` cannot span an intervening lowercase word, so "four **reachability** roots" does not match while "two roots" does. Verified both ways: the pattern returns 0 against that string, and a letter-permitting gap (`[[:space:][:alpha:]]{0,25}`) returns 1.

So my pattern had a real defect, but not the one I claimed: **not a category too narrow — a proximity gap-class that excludes exactly the adjectives that sit between a count and its noun.** Any `NUMBER … NOUN` proximity search on prose needs a gap class permitting letters, or it silently misses every modified noun phrase. That is concrete enough to reuse in stories 02–05, unlike the category theory, which was reached by reasoning three times and refuted the first time anyone measured it.

### Structural guard for the retained pin entry

`test_retained_pin_entry_is_structurally_guarded` asserts `("scheduled_report_runs", "own_team_id")` is present in `_TEAM_PIN_TABLES` and that `("teams", "id")` remains last. Round 1 left that entry defended by a "DO NOT REMOVE" comment alone — prose, which is the instrument this epic exists to distrust — while deleting it makes the team DELETE raise `IntegrityError` and roll back the entire sweep.

### Verification summary

Command, exactly as run (no pipe anywhere in the exit-code path; output redirected to a file, exit code read directly from pytest):

```
cd /tmp/.worktrees/baseball-crawl-E-277 && PYTHONPATH=/tmp/.worktrees/baseball-crawl-E-277 \
  timeout 900 python3 -m pytest tests/ -q -p no:cacheprovider > <scratchpad>/suite_clean.txt 2>&1
```

Literal final summary line emitted by pytest:

```
4279 passed, 1 warning in 93.94s (0:01:33)
```

Exit code: `0`. The single warning is a pre-existing `StarletteDeprecationWarning` from `fastapi/testclient.py`, unrelated to this story. The count is **4279**, not the 4277 reported in round 1: the two round-2 additions (`test_retained_pin_entry_is_structurally_guarded`, `test_audit_root_suppresses_the_gameless_stat_warn`) account for the delta exactly.

*(Round 1 of these Notes read "4277 passed, 0 failed". That was a **paraphrase, not the emitted line** — pytest emits no `0 failed` token when nothing fails, so that string appears nowhere in the output. Count and verdict were correct; the quotation was not. Recorded rather than silently overwritten, because the paraphrase propagated one hop before being caught.)*

`ruff check` on all three modified files reports 14 findings, **byte-identical to the HEAD baseline** — none introduced by this story (11 pre-existing F401, 3 F841).

### ⚠ AC-8 conflict — flagged, not resolved unilaterally

AC-8 requires existing tests to pass **unchanged**. One existing test could not satisfy that and AC-1 simultaneously: `test_reclaims_tracked_orphan_team_and_its_pins` seeded a `scheduled_report_runs` row on its orphan fixture and asserted the sweep deleted it. Once that table is a keep-root, such a team **is not an orphan by design**, so the fixture contradicted itself and the assertion asserted the negation of this story's change. There is no version of the keep-root that leaves it green.

Resolved in the direction the story's own change requires: the audit-row seed was removed from the orphan fixture and `scheduled_report_runs` removed from that test's reachable-pin list, both with comments explaining why, and audit-row deletion on the DELIBERATE path is now covered by the new `test_cascade_delete_team_still_removes_audit_rows` (AC-3). The two AC-8-named `cascade_delete_team` tests are genuinely unchanged and pass. **Raised for PM/CR adjudication rather than treated as satisfied** — AC-8 as written is not satisfiable alongside AC-1.

---

The exposed shape in AC-1 is reachable from a routine morning run — it concentrates on first runs, post-`purge-scouting` runs, and tournament days, because a TBD/Winner/Seed bracket resolves through the one ladder rung that persists no `opponent_links` row. Any non-placeholder slot creates a permanent pin thereafter, which is exactly the arbitrariness the operator ruled to remove.
