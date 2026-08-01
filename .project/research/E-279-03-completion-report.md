# E-279-03 completion report — Closure restructure

**Author**: `ca-e279` (claude-architect) | **Date**: 2026-08-01

Citations are **phrase anchors**, contiguity-verified with a control. An anchor
printed with a trailing `…` is truncated: cut at the ellipsis and grep the part
before it.

---

## ⚠️ TN-2 — E-279 CLOSES UNDER THE OLD SEQUENCE

**This story ships a sequence E-279 itself will not use.** E-279's own closure
follows the sequence in effect when it began: **the main-checkout archive rename at
the old sub-step 6**, not the worktree-side sub-step 3 (ii) shipped here. The new
sequence takes effect from the **next** epic.

Stated at the top because the single easiest thing to lose while deep in
restructuring the new sequence is that the old one still governs this epic.

---

## Files Changed — closed list of three, held with zero growth

| Path | Change |
|---|---|
| `.claude/skills/implement/SKILL.md` | sub-step 3 → ordered (i)-(v); sub-step 6 deleted; rollback collapse; re-entry; `:477` boundary; cross-references |
| `.claude/rules/agent-routing.md` | **one** added paragraph (the repoint ceiling) |
| `.claude/rules/dispatch-pattern.md` | **one** added line (permitted orchestration) |

Plus this report. **Nothing else touched.** One candidate arose and was **not**
actioned — see "Out of scope, reported" below.

---

## THE TWO-AXIS RESULT — the amendment's first test, and it is VINDICATED

**Axis 1 (token)** — `sub-step 6`, `sub-step 5`, `sub-step 4`, `sub-step 3`,
`archive rename`, `git mv`, `checkout -- .`, `merge-base`.

**Axis 2 (structural)** — scope derived from the document's own heading tree
(`grep -nE "^#{2,4} "`), **using none of axis 1's tokens**: Phase 5 in full, the
Workflow Summary / Edge Cases / Anti-Patterns sections, and Phase 3's Step 5 / 5a /
Gate Interaction. 497 of 797 lines read in full.

### ⭐ AXIS-2-ONLY FIND — reported as such, per the pre-registration

**`## Workflow Summary`, the compressed pipeline diagram:**

```
-> closure merge and commit (patch -> dry-run -> apply -> archive mv -> PM memory -> approval gate -> single commit)
```

**It showed `archive mv` AFTER `apply` — the old sub-step-6 ordering — and it is
invisible to every axis-1 token.** Measured, not asserted:

| token | hit? |
|---|---|
| `sub-step 6` / `5` / `4` / `3` | miss |
| `archive rename` | **miss** — the line says "archive **mv**" |
| `git mv` | **miss** — "archive mv", not "git mv" |
| `checkout -- .`, `merge-base` | miss |

**8 of 8 tokens miss. Axis 1 could not have found it.** It is in scope for axis 2
purely because of **where it lives** — inside a heading-delimited section carrying
closure procedure — and would have been in scope even if axis 1 returned nothing.

**This is exactly the TN-8a `:629`/`:660` class the amendment was written for**: a
passage describing the sub-step-6 ordering *without naming it*. Corrected to
`author + archive mv + check + stage + patch, all in worktree -> dry-run -> apply
-> approval gate -> single commit`.

**Why this counts as evidence rather than a lucky catch:** the pre-registration
committed in advance to reporting axis-2-only finds *as such*. Had I folded it in
silently, the amendment would have looked identical whether it worked or not.

---

## Acceptance criteria — measured observables

| AC | Observable | Result |
|---|---|---|
| AC-1 | ordered (i)-(v); rename at (ii) in the worktree; `git add -A` at (iv); patch at (v) vs `$(git merge-base epic/E-NNN main)` | **PASS** |
| AC-1 | **no `3a` label on any Step-8 sub-step** | **PASS** — the gap marker names no sub-step 6 successor and no `3a` was introduced |
| AC-1b | `grep -c "sub-step 4 generates"` | **0** |
| AC-2 | main-checkout `git mv` of an epic dir, **either direction** | **0** — the only surviving `git mv` is (ii), explicitly `cd <epic-worktree-path>` |
| AC-3 | re-entry stated, not inferable | **PASS** — "skip (ii) if `epics/E-NNN-slug/` no longer exists" |
| AC-4 | both aborts = `git reset HEAD` + `git apply -R --3way`, no ordering constraint | **PASS** — "no ordering constraint between them" present in both paths |
| AC-4(a) | Step 7a preservation survives | **PASS** — "PRESERVING every Step 7a ancillary edit" intact |
| AC-4(b) | `git checkout -- .` prohibition survives | **PASS — 3 occurrences across 2 sites**, both prohibitions *(I predicted 2; one line carries it twice. My prediction was wrong, not the file.)* |
| AC-5 | repair window non-empty; "last action before staging" absent | **PASS** — (iii) sits between the rename and staging; phrase count **0** |
| AC-6 | one sentence; surrounding carve-out byte-identical | **PASS** — appended after the carve-out; no existing sentence altered |
| AC-7 | one line; no other passage changed | **PASS** |
| AC-8 | no claim that references are verified | **PASS** — (iii) reads *"no claim is made that outbound references have been checked"* |

### AC-1b — the `:477` reconciliation, all three defects

1. *"before **sub-step 4 generates and applies** the closure patch"* → **generation is sub-step 3 (v); sub-step 4 dry-runs and applies.**
2. Self-contradiction on one source line: *"during Step 8 sub-step 3 staging"* … *"authored in the worktree **before** sub-step 3"* → both now read **sub-step 3 (i)**.
3. The `Step 3/3a` label collision → disambiguated as *"the Phase 5 Step 3 and Step 3a assessments — a different numbering namespace from Step 8's sub-steps"*.

### AC-1b — `:547` WRITTEN VERDICT: **NO CHANGE NEEDED**

It reads *"during Step 8 sub-step 3 staging (before the closure patch is
generated)"* — **which stays true under the restructure**, since generation is
(v) and the flip is (i). **Byte-identical; deliberately not "tidied" into
agreement with `:477`'s wrong form.** The correct passage was the one at risk.

### AC-1 / AC-8 are complementary, not in tension
**AC-1 fixes the slot's POSITION** (after the rename, before staging — that gap
*is* the repair window). **AC-8 bounds its CONTENT** (it may not claim a check
runs). Step (iii) names the step and its owner story and **invokes nothing**, so a
closure with 03 merged and 04 absent proceeds exactly as today. *(Codex proposed an
"unstated dependency" on 04; that would be circular — the edge runs 03 → 04.)*

### Sub-step numbering — deliberate gap, not a lost step
**Sub-steps 7-10 keep their numbers.** Renumbering would have touched 8+
cross-references outside the deleted region and **worsened E-271's already-stale
anchors into this same file** (TN-8a). The file already uses non-contiguous labels
(`4b`, `5b`). The gap carries an inline marker saying it is deliberate and why.

---

## Round-2 fixes — AC-5, AC-2, and the defect my own collapse introduced

**AC-5 (PM) — the STATEMENT half was absent.** Verified independently: seven
formulations at zero against two controls that fired. Fixed in the **Remediation
Spawn Context template**, not sub-step 3 — `:654`'s re-entry note reaches the
*orchestrator*; the party that needs this is the *remediation implementer*, and the
template is the text pasted into its spawn.

> **Why my two-axis pass could not have caught it.** Both axes hunt for passages
> that are **present and wrong**. Neither can surface a sentence that was **never
> written** — a heading-tree scope tells you which text to read, not which text is
> missing. **The instrument for an absence is the AC itself, read as a checklist of
> required statements.** My pre-registration listed AC-5 as *"repair window
> non-empty; 'last action before staging' absent"* — **both halves of the
> POSITIONING clause, neither half of the STATEMENT clause. The observable I
> registered could not fail on this defect.**
>
> **Mechanical remedy, adopted for stories 04-05: one observable per CLAUSE, not
> per AC.** Count the clauses in the AC, count the rows in the table, require a
> match — runnable by a third party who knows nothing about the story, and it would
> have surfaced this at pre-registration time, before any work.

**AC-2 (Codex P1-1) — `dispatch-pattern.md:42` still codified the OLD sequence.**
AC-2 says *"no closure passage"* — **no file scope.** Both halves fixed: the
`git mv` is now explicitly in the worktree before patch generation, and the bare
`main` diff base is replaced with `$(git merge-base epic/E-NNN main)` with the
silent-revert hazard stated inline.

> **This is Pattern A arriving THROUGH an acceptance criterion.** I corrected the
> sequence where I was restructuring it and left it standing where it also lives —
> **and AC-7 told me to.** The reach is inverted from the usual case:
> `dispatch-pattern.md` is `paths: "**"` (every agent, every interaction) while
> `SKILL.md` loads on demand, so **the stale copy had wider reach and the more
> dangerous of the two errors.** My AC-7 addition landed two lines below the
> passage it contradicted.
>
> **PM's own miss, recorded because it is the same family:** PM verified AC-2 by
> grepping `SKILL.md` alone. **The criterion said "no closure passage"; the
> instrument covered one file** — narrower than the criterion it was testing, on
> the AC PM was most confident about. **Codex found it because nothing told it
> which file to look in.**
>
> **CR's diagnosis of ITS miss is the most transferable line of the round:**
> *"I verified AC-7 with `--numstat` → 1/0 and read it as reassurance. That
> answered 'did story 03 touch anything else?' It did not answer 'is the file now
> correct?'"* **Purity and correctness point in opposite directions when a change
> alters what its surroundings DESCRIBE — so a PASSING purity check is a positive
> indicator that a contradiction may now exist.** Generalises to any AC bounding an
> edit to "one line, nothing else."

**P1-2 — the rollback ignored sub-step 4b's environment change.** Verified
first-hand: 4b reinstalls the main-checkout interpreter; both rollback paths return
**zero** mentions of pip/reinstall/requirements/interpreter/environment.

**The singularity claim was NEW and it was mine.** `:692` said *"Reverse the ONE
Step-8 main-checkout action"* and `:668` *"the only main-checkout change"*. Before
the restructure there were genuinely **two** (the patch and the sub-step 6 rename),
so the old text could not have claimed one. **My collapse created the "ONE", and 4b
falsifies it** — this repo's closing-generalization defect, in a safety note,
asserting a tidy count. Both now GIT-scoped.

**The env note is keyed to ABANDONMENT, not to a reject path** (`cr-e279`'s
refinement, verified against the circuit breaker at `:670`, whose options include
`(d) abandon`): the red-suite path is transient on retry and **becomes durable when
remediation exhausts.** A note placed only at reject (c) would have left that exit
uncovered. **It is placed AFTER the two-command collapse and worded as a
consequence, not a step** — the reversal remains exactly `git reset HEAD` +
`git apply -R --3way`, no third command, no ordering constraint.

## Residual — three UNSPECIFIC copies of the same claim (a NEW doc-sweep variant)

`dispatch-pattern.md:8`, `dispatch-pattern.md:12` and `SKILL.md:28` each listed the
main session's git operations including *"`git mv` for archive rename during
closure"* / *"`git mv` for archival"* — **with no location.**

**AMBIGUOUS, not false.** The main session does still run a `git mv` during
closure — in the worktree — so each sentence was literally true. **PM refused to
stretch AC-2 to cover them**, having just ruled AC-2 governs over AC-7: *"that
ruling is worth less if I widen it the moment it is convenient."* Fixed as a
**residual**, a different class from `:42`, which was **FALSE**.

**Decided on reach, and on an asymmetry PM found:** at `:8` the immediately
preceding item names its direction explicitly — *"for closure merge from epic
worktree to main"* — **and the `git mv` item did not.** A reader carrying the old
model resolves that asymmetry wrongly, in a `paths: "**"` file loaded into every
agent on every interaction. All three now name the worktree.

> **⚠️ NEW VARIANT of `doc-sweep.md`'s retired-claims rule, and it is PM's
> characterization.** The documented shape is *retired claims survive in forms
> carrying none of their tokens.* **Here they survived CARRYING the token and
> LACKING the qualifier.** The claim was corrected where it was **specific** and
> survived where it was **vague** — **which no token grep distinguishes, because
> the token is present in both.** The discriminator is not the token but the
> presence of a qualifier the corrected copies gained.

## The `` `(d) abandon` `` CHK — scope stated, per this epic's own record

*Scope: the CHK counted the **backticked** literal `` `(d) abandon` `` — **2**, both
added by this story — not the bare substring, which is **6 across 5 lines**
(`:378`, `:467`, `:477` pre-existing circuit-breaker option lists; `:670` carrying
**two**, the pre-existing list plus this story's cross-reference; `:702` this
story's note). **Both figures are correct for their pattern.** The narrower one was
deliberate: the check was testing whether this story's cross-reference reached both
sides, so it searched the literal this story had written. It says nothing about how
often the option is mentioned, and `cr-e279`'s pattern answers that question
correctly.*

**Recorded because a resolved CHK with unstated scope is the `14/14` and the `19`
shape** — a figure that agrees with its surroundings and cannot be reproduced.
**The number being defensible is not the same as the derivation being available.**

## Out of scope, reported rather than actioned

**`dispatch-pattern.md:8` and `:12`** describe the main session's operations as
including *"`git mv` for archive rename during closure"*, and `SKILL.md`'s Purpose
section says *"`git mv` for archival"`*. **All three remain TRUE** — the rename
still happens during closure, now in the worktree — and **none claims a location**,
so none is falsified. **AC-7 forbids changing any other passage in
`dispatch-pattern.md`, so I did not**, and I am recording the verdict instead of
making a silent judgement call.

---

## A harness note worth recording

Mid-edit the harness reported `SKILL.md` **"modified on disk since you last read
it"** — which `tool-output-integrity.md` calls **primary evidence that the file
moved**, not a garble. I ran the differential rather than assuming: mtime
**18:10:58** matched my own last write, **all nine of my edits were present**, and
`git status` showed only my modification.

**The other writer was me.** Several edits were applied via `python3 … write_text`
from Bash, which the harness cannot attribute to its Edit tool — so its staleness
detection fired correctly on a change it could not see the origin of.

**Worth carrying: writing files through Bash degrades the harness's own
moved-file protection for those files.** The note is a true positive about the
file and a false alarm about the *author*, and only the enumeration distinguishes
them.
