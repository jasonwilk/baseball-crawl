# E-279-01 completion report — Write guard reads authoritative worktree state

**Author**: `ca-e279` (claude-architect) | **Date**: 2026-08-01 | **Round**: 2 of 2

Written to a file because the implementer→reviewer SendMessage leg failed twice
on this dispatch: neither the original completion report nor its hunk correction
reached `cr-e279`, while main-session→CR messages arrived normally. This file is
the artifact; it is not a relay of one.

**Anchors, not line numbers.** Line numbers in this report have rotted **twice**,
both times from this story's own edits: the SHOULD-FIX header edit shifted every
hook-header citation in the round-1 table, and the AC-8 insertion added two lines
to `worktree-isolation.md`, moving the branch-management ban from `:33` to `:35`.
Where a citation disagrees with the file, **the file wins.**

> **⚠️ This paragraph originally claimed "all line numbers below were re-derived
> after the final edit." That claim was false when written** — the two `:33`
> citations had been carried forward unchecked, and `cr-e279` found them. A blanket
> assurance of re-derivation is exactly the kind of claim that gets believed
> instead of spot-checked, so it is worth more as a corrected record than as a
> boast. Every `worktree-isolation.md` citation has since been re-derived against
> the post-edit file, item by item, and CR independently spot-checked the rest.

---

## Files Changed

| Path | State |
|---|---|
| `/tmp/.worktrees/baseball-crawl-E-279/.claude/hooks/worktree-guard.sh` | modified |
| `/tmp/.worktrees/baseball-crawl-E-279/tests/test_worktree_guard.py` | created |
| `/tmp/.worktrees/baseball-crawl-E-279/.claude/rules/worktree-isolation.md` | modified (AC-8, added to the story's file list by PM ruling 2026-08-01) |

The epic file and the story file also show modified in
`git status`. **Those are PM's edits, not mine** — I have touched no epic or story
file. *(Pre-archive epic-directory path elided at closure by PM, per TN-3's reword
remedy — the observation is unchanged; only the dead path literal is gone.)*

> **⚠️ Corrected 2026-08-01, and left visible because the correction is the
> point.** This paragraph originally read *"PM's status transitions —
> `TODO`→`IN_PROGRESS`, `READY`→`ACTIVE`."* That was accurate when written and
> went stale the same day: **PM's AC-8 addition landed in those same two files
> afterwards**, so the hunks are now status transitions *plus* the new AC-8 and
> the amended file list. A reader taking the original sentence at face value
> would conclude those files carried only status churn and skip them. The same
> misreading produced a brief main-session/CR conflict on this dispatch. It is
> the identical shape as the stale-measurement defect recorded under AC-6 below:
> a sentence true of a past state, asserted about the current one.

---

## Test Results — verbatim

Literal terminating summary lines, non-quiet mode. *(Round 1 gave these in `-q`
form, which does not emit the `===` banner at all; `cr-e279` could only treat the
requirement as met because it independently counted this file's tests — 3+7+1+4+2+7
= 24 — and that corroboration will not always be available.)*

```
$ python -m pytest tests/test_worktree_guard.py
========================================= 24 passed in 0.21s =========================================

$ python -m pytest tests/
=============================== 4367 passed, 1 warning in 97.46s (0:01:37) ===============================
```

> **⚠️ THESE FIGURES ARE EVIDENCE, NOT THE CURRENT COUNT — annotated 2026-08-01,
> deliberately NOT edited.** `cr-codex` flagged them as stale acceptance evidence:
> the targeted file now reports **32 passed** and the full suite **4375**, after
> the AC-7 restructure added six tests late in this story.
>
> **The transcript is not edited, and the reason is the criterion-versus-evidence
> cut applied to my own artifact.** This section is headed *"Test Results —
> verbatim"* and contains literal captured output. **Rewriting a verbatim
> transcript to read `32` would assert that this command produced output it never
> produced** — fabricating a record rather than correcting a claim. Same for
> `cr-e279`'s independent count `3+7+1+4+2+7 = 24` above: that was its arithmetic
> against the file as it then stood, and editing it would falsify what it did.
>
> **Codex's concern is nonetheless real and is what this note discharges:** the
> story is DONE, so a reader takes this section as *the acceptance figure*. That
> makes the same text evidence in its capture and criterion in its role. **The
> resolution is annotation, not substitution** — the record stands, and no reader
> can now mistake it for the current count.
>
> **Current, measured 2026-08-01: `32 passed` targeted, `4375 passed` full suite.**
> Story 02's report carries its own contemporaneous figures.

`bash -n .claude/hooks/worktree-guard.sh` → clean.

**Bound on the full-suite figure**: run from the epic worktree, so it exercises
the worktree's own `src/`, not the merged closure tree. It is not the
authoritative closure signal.

**Live end-to-end** — the shipped hook against the real registry, real payload:

```
$ echo '{"tool_name":"Write","tool_input":{"file_path":"/workspaces/baseball-crawl/docs/x.md"}}' \
    | bash .claude/hooks/worktree-guard.sh
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",
 "permissionDecisionReason":"Dispatch is active (worktree: /tmp/.worktrees/baseball-crawl-E-279). ..."}}
exit 0
```

### Mutation probes — the tests were verified to go RED

A green suite is worthless until the checks are shown to discriminate. Mutants
were written to the **scratchpad**; the real hook was never mutated
(`worktree-isolation.md` records that practice destroying a story's work at
E-267). Probe script: `<scratchpad>/mutation_probe.py`.

| Mutation | Test expects | Mutant gives | Verdict |
|---|---|---|---|
| Detection reverts to a directory glob | ALLOW | DENY | KILLED |
| Bound-5 mismatch check deleted | DENY | ALLOW | KILLED |
| Bound-2 precondition deleted | DENY | ALLOW | KILLED |
| Bound-2 generalised to the DEFAULT root | ALLOW | DENY | KILLED |
| AC-4 positive control removed | DENY | ALLOW | KILLED |

Re-run after every edit in this round; all five still killed.

**The first M1 probe reported SURVIVED, and that was the probe being broken, not
the test.** The mutant left an unbalanced `if`, so bash aborted and emitted
nothing — and **empty stdout is shape-identical to ALLOW in a guard that signals
denial via stdout**. With no error discrimination, a mutant that never ran read
as a mutant that survived, one step from "AC-1 is vacuous, redesign it." Fixed by
adding an exit-code/stderr guard to the probe and making the mutation
syntax-preserving. Recorded because the near-miss is worth more than the probe.

### One RED that is not constructible behaviorally

AC-1b bound 2's SET-ONLY red — *"an unset environment with no `/tmp/.worktrees`
denying a main-checkout write"* — **cannot be built against the real default
here**: `/tmp/.worktrees` exists whenever a dispatch has ever run, so the obvious
"unset it and expect ALLOW" test passes whether or not the defect is present.
That is the story's own warning: *invisible where it will be tested and total
where it will not.*

`test_missing_DEFAULT_root_must_not_fail_closed` therefore mutates **only the
default value** to an absent path, leaving every other byte alone, with
`assert source.count(original) == 1` so a substitution that failed to apply
cannot pass silently. `cr-e279` independently ran the generalized form against
the real default root and got ALLOW, reproducing the story's prediction — so this
substitution is forced, not merely defensible.

---

## Behavioral Changes

1. **Detection mechanism** — dispatch-active is decided by
   `git worktree list --porcelain`, not `ls -d /tmp/.worktrees/baseball-crawl-E-*`.
   A directory git does not report no longer selects mode 1. A registered-but-
   `prunable` worktree still does: **strictly stronger than the glob**, which
   would have gone quiet.
2. **New environment variable `BB_WORKTREE_ROOT`** — test-only injection knob,
   hazard documented at the variable. Unset, the root is the literal
   `/tmp/.worktrees` and production behavior is unchanged.
3. **Two NEW deny paths, both mode 1**, previously impossible: set-but-missing
   root, and set-but-wrong root (an epic worktree registered outside the
   configured root). Each carries its own reason text naming `BB_WORKTREE_ROOT`,
   distinct from the pinned "Dispatch is active" text. **Both are inert when the
   variable is unset.**
4. **Exit codes unchanged** — always 0, including on both new denials. Verified
   rather than assumed, because the header asserts it.
5. **Unchanged**: the `..` rejection, slash normalization, `jq` fail-open, mode-2
   denylist, worktree-path pass-through. See the AC-6 evidence below.

---

## AC-6 evidence — and a correction to what round 1 reported

**⚠️ The round-1 report's evidence sentence was wrong. Recorded rather than
silently fixed.** It read:

> "Confirmed by diff — **both hunks are the header block and the detection
> block**; all five pinned behaviors lie outside them and are byte-identical."

"Two hunks" is *literally true* at default context. The characterization is not:
hunk 2 contains the detection block **and** the site-12 comment change. Three
change regions; I named two.

**Root cause — a stale measurement, not hunk merging.** I ran `git diff` *before*
making the site-12 edit and wrote the sentence *after* it, without re-running.
The sentence described a diff that had ceased to exist. `pm-e279` flagged the
inconsistency and correctly declined to assert a defect it could not run
(no Bash); running it is what found the real cause. One Bash call, unspent.

**Method, now standing practice for the rest of the epic** (main session +
`cr-e279`, 2026-08-01): report the changed **OLD-file** ranges from
`git diff -U0`, and locate the pinned behaviors in the **pre-change** file via
`git show HEAD:<path>`. Both clauses are load-bearing and the second is the one
that gets dropped. `-U0` emits an old and a new range per hunk; a table built
from the `+` side answers a different question, is internally consistent, looks
right, and **carries nothing in its shape to reveal which side it came from.**
The pinned behaviors' line numbers refer to the pre-change file and to no other.
*(Companion, so it does not read as a defect on first sight: `-U0` renders a pure
insertion as `-N,0`, a zero-length old range. That is correct output.)*

Executed here rather than asserted — `git show HEAD:.claude/hooks/worktree-guard.sh`
is **119 lines**, and the five pinned behaviors were located in *that* file.
`cr-e279` ran the same derivation independently and reached the same ranges.

**Round 1 reported the correct OLD ranges with the wrong provenance**: the pinned
line numbers came from my own earlier read of the file, not from `git show HEAD:`.
The numbers were right and the method was not, so the table was correct by luck of
a read taken before any edit. Re-derived rather than left standing, because **"it
came out right" is not evidence the method was right** — which is this repo's
producibility rule (*re-derive a figure from the thing that would produce it, and
treat its agreement with the conclusion as no evidence at all*) applied to a
method instead of a figure.

**Corrected, re-derived after every edit in this round.** Changed OLD-file line
ranges, from `git diff -U0`:

```
@@ -5 +5 @@   @@ -7 +7,2 @@   @@ -14 +15 @@   @@ -20,3 +21,18 @@
@@ -85,2 +101,75 @@   @@ -92 +181,2 @@
```

→ changed old lines **{5, 7, 14, 20-22, 85-86, 92}**.

| Pinned behavior (AC-6) | Original lines | Intersects a change? |
|---|---|---|
| `jq` fail-open | 29-32 | No |
| Slash normalization (`tr -s '/'`) | 49 | No |
| Worktree-path pass-through | 53-56 | No |
| `..`-segment rejection (comment + `case`) | 61-83 | No |
| Mode-2 implementation denylist | 104-116 | No |

**No intersection with any changed range — all five byte-identical.** Site 12
(old line 92) is a comment inside the mode-1 block; the mode-1 `jq` emitter code
is untouched, and AC-6 pins *the CODE, not the comments describing it*.

`cr-e279` should re-measure rather than take this table:
`git diff -U0 .claude/hooks/worktree-guard.sh | grep '^@@'` reproduces it in one
call. **I have been wrong about this exact claim once**, and the correction above
is me re-checking my own assertion, which is the weakest form of check available.

---

## AC-6b — per-site written verdicts (hook header + body)

Sites re-derived **by phrase**, not from the story's list. The story named four
detection sites; phrase re-derivation found **three further detection-mechanism
sites** it did not — the **"Two modes, selected by whether…"** lede, the
**"2. NO DISPATCH"** heading, and the in-body **"(no worktree REGISTERED…)"**
parenthetical. **Five** rows carry "no change needed": **"This fails closed…"**,
**"The main session's git/Bash operations are unaffected"**, **"Worktree paths…
always pass"**, **"Denial is communicated via JSON output"**, and **"Own-memory
deliverables AND closure-time memory writes…"** — *corrected: the round-1 report
said four, missing the "Denial is communicated via JSON output" row because its
"verified, not assumed" framing filed it elsewhere in my head.*

> **⚠️ These ROW numbers were stale until 2026-08-01, and the reason indicts the
> anchor conversion itself.** They read `1, 5, 12`, `3, 4, 9, 10, 11` and `row 10`
> — correct before rows 8 and 9 were inserted above them. **The conversion
> protected the SITE citations and left the ROW citations, which rot on insertion
> in exactly the same way.** AC-8's table is immune only because it dropped its
> numeric column entirely; this one kept a `#` index, so **one axis was converted
> and the other left, in the very edit made to end the rot.**
>
> **Why no reader would catch it: the COUNT stays right while the IDENTITIES go
> wrong**, so every summary reconciles and only opening the table disagrees.
> Found by `pm-e279`; identities re-verified by grep rather than by reading.
>
> **Repaired by NAMING the rows, not by renumbering them** — renumbering buys a
> fourth generation on exactly the reasoning that retired the line numbers. My
> first repair *was* a renumber; `cr-e279` and the main session flagged it before
> it shipped.
>
> **This is a THIRD citation class and the taxonomy is the point.** Line numbers
> → phrase anchors fixed one class. The contiguity check guards a second. **An
> ordinal reference into a table that grows is a third: immune to the anchor
> conversion, invisible to a contiguity check, and broken by the very insertion
> (the prune row) that fixed AC-6b's RED.** One edit fixed one citation class,
> left a second untouched, and newly broke a third.

**Anchored by PHRASE, for the same reason as the AC-8 table below.** These rows
were re-derived four times and were stale again each time; the last generation was
created by the edit that fixed the previous one.

> **⚠️ Phrase anchors trade one failure mode for a WORSE one unless every anchor
> is verified CONTIGUOUS.** A rotted line number is visibly wrong; a wrapped anchor
> returns a **confident empty** that reads as *"this text was deleted"* — pointing
> a future reader at a deletion that never happened. Rendering hides the wrapping
> that breaks it, so an anchor drawn by eye from rendered prose is the high-risk
> case.
>
> **HOW TO GREP THESE ANCHORS — read this before concluding any text is missing.**
> An anchor printed with a trailing `…` is **truncated for display**. **Cut at the
> ellipsis and grep the part before it**; the full printed string will return zero,
> and that zero means *you grepped a truncation marker*, not *the text is gone*.
> Anchors without a `…` are literals and grep as printed.
>
> *(Live instance, 2026-08-01: verifying this very paragraph, a `grep -F "Cut at
> the ellipsis and grep the part before it"` returned **zero** — the sentence wraps
> after "Cut at the". The text was plainly present on screen. **The trap fired
> inside the check verifying the note that documents the trap**, which is the
> strongest available evidence that "read carefully" is not the remedy and
> truncate-then-grep is.)*
>
> **So verified, every anchor in both tables resolves to a single line with exactly
> one match**, with a deliberately-absent control in the same pass so a genuine
> zero is interpretable: **14/14 in this table, 12/12 in the AC-8 table**, control
> zero in both.

> **⚠️ The certification above previously overstated itself, and the overstatement
> defeated the note's own purpose.** It read *"Every anchor in BOTH tables was
> grep-verified as a single-line, single-match **literal**."* Measured by
> `cr-e279`: **13 of 26 return zero on a straight `grep -F` of the printed
> string** (AC-6b 6/14 literal as printed, AC-8 7/12) — because of the trailing
> display ellipses. They are all *usable*; they were not all *literals*, which is
> what the sentence certified.
>
> **This is not pedantry: the note exists to license a future reader to read a
> zero-hit grep as "this text was deleted." Under the claim as written, thirteen
> anchors would have produced exactly that false conclusion** — the note would
> have manufactured the failure it was written to prevent. Repaired by stating the
> truncation rule and *where to cut*, rather than by re-wording all 26 anchors.
>
> **Third generation of this shape inside this same note** — and this time in the
> **certification** rather than in the citations it certifies.
>
> **The count was wrong too: "14/14 in the AC-8 table" against 12 anchor rows.**
> `cr-e279` could not reproduce 14 and flagged that my message to the main session
> had said 12/12. Resolved by recount: **the AC-8 table has 12 rows; the artifact
> was wrong and the message was right.** The 14 came from my having tested 14
> *strings* across those 12 rows and then reporting the string count as a row
> count — **a figure that was never derivable from the table it described**, which
> is this epic's own producibility rule turned on its author for the second time.
>
> **The DECOMPOSITION, since an explanation of a counting error is itself a count
> and my first one was also wrong.** It read *"two rows carry two anchors"* — off
> by one, **in the same direction as the original error**, which is exactly PM's
> captured finding. Re-derived:
> ```
> 12  rows
>  +1  the constraint-list row carries TWO anchors      (the only doubled row)
>  +1  row 3's anchor then read "A PreToolUse hook … guards Write and Edit
>      operations … Two modes:" — an INTERNAL ellipsis needing TWO test strings
> = 14
> ```
> **Two different mechanisms each contributing +1**, and I had collapsed them into
> one. Tightening row 3 to a single literal — one of the four `(…)` fixes — then
> turned 14 into 13 without my re-deriving the figure. PM and `cr-e279` each
> independently counted 13 strings over 12 rows for the *current* table, which is
> correct; `cr-e279`'s tidier hypothesis (that the 14 was AC-6b's figure
> duplicated) was **tested and refuted** rather than adopted for fitting.
>
> **The check caught three anchors that the underlying text did NOT justify** —
> not because the text wrapped, but because I had written the ANCHOR with an
> *internal* ellipsis (`… Two modes:`, `output… Always exits 0`) or substituted a
> typographic `…` for the literal `...` in a path. Each was contiguous in the
> file and ungreppable **as printed here**. Tightened to literal substrings.
> *(This is the failure mode arriving through the citation rather than the source,
> which the "verify contiguity" instruction does not obviously cover — worth
> keeping, because the anchor is the artifact a reader actually copies.)*

| # | Site (phrase anchor, `worktree-guard.sh` header unless noted) | Text / subject | Verdict |
|---|---|---|---|
| 1 | "Two modes, selected by whether…" | was "whether an epic worktree **exists**" | **CHANGED** → "whether git reports a **registered** epic worktree". **UNLISTED SITE.** |
| 2 | "1. DISPATCH ACTIVE (git reports an epic worktree at" | mode-1 heading, keyed on directory existence | **CHANGED** → "git reports an epic worktree at `<root>/…`", root named. |
| 3 | "This fails closed -- any new path…" | denylist scope | **NO CHANGE NEEDED.** Still true. |
| 4 | "The main session's git/Bash operations are unaffected" | tool coverage | **NO CHANGE NEEDED.** Still true; hook still intercepts Write/Edit only. |
| 5 | "2. NO DISPATCH (git reports no epic worktree):" | was "(**no epic worktree**)" | **CHANGED** → "(git reports no epic worktree)". **UNLISTED SITE.** |
| 6 | "Detection: `git worktree list --porcelain`…" | was "Detection: glob for /tmp/.worktrees/…" | **CHANGED** → registry-based (RED form 1), **plus the two-sided qualifier** ("EXCEPT where the registry is unreadable and the glob fallback below runs"). |
| 7 | "A stale REGISTRY ENTRY from a crashed dispatch…" | was "A stale worktree … the user can clear it by removing the worktree directory." | **CHANGED, BOTH CLAUSES.** A stale **REGISTRY ENTRY** enforces (RED form 2); the remedy is **`git worktree remove <path>`, scoped** (RED form 3). Adds that deleting the directory alone **no longer clears dispatch mode** — the old remedy does not merely fail, it produces AC-2's DENY, misleading the one operator most likely to read it: someone already blocked and hunting for the exit. |
| 8 | "`git worktree prune` is NOT an interchangeable alternative" | *(new paragraph — Defect B)* | **ADDED.** Prune takes no path argument, cannot be aimed, and is repo-GLOBAL: one run clears every prunable entry including other epics' under concurrent dispatch. **This row did not exist until 2026-08-01** — see the note below. |
| 9 | "CHECK, DO NOT CLASSIFY, and note who this is addressed to" | *(new paragraph — Finding 3)* | **ADDED.** The remedy's SECOND home: the `prunable` discriminator, the actor, and the mode-2 fail-open hazard. |
| 10 | "The directory glob survives ONLY as the fallback…" | *(new paragraph)* | **ADDED.** Prevents "the glob is gone" over-reading; states why this is safe to land mid-closure (epic TN-2). |
| 11 | "Worktree paths (/tmp/.worktrees/...) always pass" | pass-through | **NO CHANGE NEEDED** — the honest one AC-6b predicts. Keys on `MAIN_PREFIX`, never references the root, so it holds under any root; the literal is an illustration, not a condition. Pinned as code, exempt as prose. |
| 12 | "Denial is communicated via JSON output" | denial channel (the "Always exits 0" line follows it) | **NO CHANGE NEEDED — verified, not assumed.** All deny branches `exit 0`, so it stays true. It would have become silently false had I used a nonzero exit. |
| 13 | "Own-memory deliverables AND closure-time memory writes…" | own-memory / closure-patch note | **NO CHANGE NEEDED.** Not a detection claim. |
| 14 | "(no worktree REGISTERED -- a leftover directory is no longer mode 1)" *(hook BODY, mode-1 block)* | was "(no worktree present)" | **CHANGED.** Outside AC-6b's literal "every header line" scope; changed under its "an unlisted site still owes a verdict" clause. PM confirmed this was right and requires no re-work. |

> **⚠️ Row 8 was MISSING until 2026-08-01, and its absence was AC-6b's own RED.**
> The prune paragraph tells an operator what **not** to use, which is squarely
> inside AC-6b's *"or telling an operator what to do about it"* surface — so it
> owed a verdict and had none. Found by `pm-e279`. **I added that paragraph to the
> hook and did not add its row**, which is the verdict-free pass AC-6b exists to
> forbid, committed in the table that records the verdicts.
>
> **Row 7's verdict was also stale and is corrected here**: it still described the
> remedy as "`git worktree remove` / `git worktree prune`" after Defect B had
> narrowed it to `remove <path>`. PM caught the identical stale verdict in the
> AC-8 table; **this is the same claim in the second table** — one more instance
> of a correction landing where it surfaced and not where it also lived.

## Finding 3 — the fix had TWO homes and landed in one

The scoping fix went into `worktree-isolation.md` and **the same unscoped remedy
sentence was left standing in `worktree-guard.sh`'s header** — no actor, no
warning, no cross-reference. Now fixed in both.

`pm-e279`'s framing is the one worth keeping: **landing the fix in one location is
itself the judgement that the hazard is real, which makes the untreated twin
harder to justify than it was before the fix existed.** Exposure is lower — a hook
script is pulled, not pushed into every context — but **the path that reaches it
is exactly the hazardous one**: an agent blocked mid-dispatch, trying to
understand why, opens the guard.

This is Pattern A once more, and the count on this dispatch is now **five**.

## Finding 4 — RULING: correct the danger claim. Both halves were false.

`cr-e279` and `pm-e279` split on this. **PM said the claim *"clearing it destroys a
running dispatch"* is false for `git worktree prune`. CR independently reached the
same observation and dispositioned it the other way**, on the ground that spelling
out that `prune` is safe would invite an agent to run a prohibited command for no
benefit.

**Neither had run it. I did** — isolated throwaway repo, three probes:

| Probe | Result |
|---|---|
| `prune` while the live worktree's directory is **present** | **No-op.** Entry survives. |
| `git worktree remove` on a **dirty live** worktree | **REFUSES**: `fatal: '../live' contains modified or untracked files, use --force to delete it` |
| `prune` while a live worktree's directory is **transiently missing** | **Removes the entry — and restoring the directory does NOT bring it back.** |

**RULING: the sentence is corrected, and the finding is larger than either party
had it.** "Destroys a running dispatch" was overstated for **both** commands, not
just `prune`: a dispatch worktree is always dirty, so plain `git worktree remove`
**refuses**. Three agents reasoned about this sentence and none ran it; the third
probe is the one nobody predicted.

**The correction satisfies BOTH positions rather than picking one**, which is
possible because CR was rebutting a proposal PM did not make. CR objected to
*"spelling out that prune is safe."* PM proposed replacing the false danger with a
**different, real, and scarier** one. The landed text says nothing about either
command being safe:

> "**The danger is not only deletion.** If a LIVE worktree's directory is even
> transiently missing, `prune` drops its registry entry, restoring the directory
> does **not** bring it back, and the guard then falls silently to mode 2 --
> leaving the epic unprotected for the rest of the dispatch."

That hazard is **specific to the mechanism this story introduced** — the guard now
reads the registry, so deleting a registry entry is what disables it. And it is
reachable by an ordinary path: someone follows the *old* advice, deletes the
directory, then runs `prune` to finish the job.

**CR's underlying concern is honoured**: no text here distinguishes the two
commands by safety, and the operative rule (*never an agent's*) is untouched and
still carries the protection.

## Defect B — the REMEDY sentence, independent of Defect A, and I committed the exact failure CR predicted

Defect A was in the **warning** sentence. `cr-e279` then found a second, in the
**remedy** sentence, which offers `git worktree remove <path>` and
`git worktree prune` **as alternatives — and they are not, by construction.**

**CR's warning was explicit and I had already earned it**: the twin at
`worktree-guard.sh` carries the same remedy sentence, so it likely carries the
same false equivalence, and *"porting the check clause across and calling it done
is how a Pattern A fix becomes a Pattern A fix twice."* **That is precisely what I
had done** — I ported the check clause to the hook and left the remedy sentence
untouched at BOTH sites. Fixing Finding 3 by porting one property, while the
other defect sat in the same sentence I was editing around, is the sixth Pattern A
instance on this dispatch and the first I was warned about in advance.

**Verified on my own instrument, four probes:**

| Probe | Result |
|---|---|
| `git worktree prune -h` | `usage: git worktree prune [-n] [-v] [--expire <expire>]` — **no path parameter** |
| `git worktree prune <path>` | **Rejected** — prints usage. It cannot be aimed. |
| `git worktree remove <path>` on a **stale** entry (directory gone) | **Works, silently and scoped** — clears exactly that entry |
| One `prune` with **two** prunable entries + one live | **Removed BOTH** in a single run; the live one untouched |

*(The two-prunable-entry probe was run because my first attempt at this had only
one stale entry left, so it demonstrated nothing about global scope. Under-
demonstrating the load-bearing claim would have been the same defect again.)*

**Landed at both sites:** `git worktree remove <path>` is named as the remedy and
described as scoped; `prune` is explicitly marked **not an interchangeable
alternative** — no path argument, repo-global, one run removes **every** prunable
entry including other epics' under concurrent dispatch.

**Why this matters more than a wording nit:** under the concurrent-epic mode
trialled 2026-07-26, an operator aiming `prune` at one stale entry silently clears
all of them — and each cleared entry is one this guard then reads as "no
dispatch." **A fail-open, which is the precise inverse of what this story exists
to produce.**

**CR's self-assessment, recorded because it is the most transferable thing in this
exchange.** It had Defect A in hand and ruled the one-sidedness a deliberate,
correct choice:

> "My check asked *'is this one-sidedness harmless?'* and I answered it on the
> unexamined assumption that prune's only relevant property was **safety**. I
> never asked what else prune does against this guard. That is adjudicating the
> *direction* of an asymmetry without enumerating what is *reachable* through it."

And on why a wrong verdict is worse than silence: *"An unexamined claim invites the
next reader to check it. Mine said checked, and correct as written — converting an
open question into a closed one on the strength of a review verdict."* That is the
same hazard as my own formal ruling citing a criterion nobody opened: **a verdict
is the artifact least likely to be re-checked, so a wrong one is more durable than
a wrong guess.**

**Verified by ABSENCE.** Grepped all three RED forms across the whole file: **zero
matches each**, with a positive control in the same pass (34 `worktree` matches)
so the zero is verified absence rather than an unexplained empty.

---

## AC-8 — per-site written verdicts (`.claude/rules/worktree-isolation.md`)

Sites re-derived **by phrase** from a fresh on-disk read, not from PM's list and
not from ambient context (that file carries `paths: "**"`, so every running
agent's injected copy is now the stale one). **PM's three sites confirmed; no
fourth.** `cr-e279` independently derived the same three.

**Anchored by PHRASE, not by line number.** These citations rotted through five
generations, every time from this story's own edits, and the last generation was
created by the very edit that fixed the previous one. A sixth re-derivation only
buys a seventh. This table now cites the text, which does not move —
`.claude/rules/tool-output-integrity.md`'s "cite a stable anchor, not a line
range," applied after ignoring it four times. *(`cr-e279` made the call to convert
rather than re-derive; the report had already recorded the remedy at "the rot rate
here is the argument for phrase anchors" and then kept re-deriving anyway.)*

| Site (phrase anchor, `worktree-isolation.md`) | Text / subject | Verdict |
|---|---|---|
| "If your cwd is NOT `/workspaces/baseball-crawl`…" *(file preamble)* | cwd orientation | **NO CHANGE NEEDED.** Not mode selection. |
| "**Path pattern**: `/tmp/.worktrees/baseball-crawl-E-NNN/`" *(under `## Epic Worktree`)* | where worktrees live | **NO CHANGE NEEDED.** States location, not what selects a mode. |
| "guards Write and Edit operations on the main checkout. Two modes:" *(opens `## Hook Enforcement`)* | section lede | **NO CHANGE NEEDED.** Introduces the modes without stating the trigger. |
| "1. **Dispatch active** (`git worktree list` REPORTS an epic worktree at" *(mode-1 bullet)* | was "epic worktree at `/tmp/.worktrees/baseball-crawl-E-*` **exists**" | **CHANGED** → "(`git worktree list` **REPORTS** an epic worktree at …)". The operator-facing form of RED form 3: an agent blocked by the guard reads this, deletes the directory, and stays blocked. `cr-e279` **executed** the shipped hook to confirm the entry stands and the session is still denied — not inferred. |
| "2. **No dispatch** (git reports no epic worktree):" *(mode-2 bullet)* | was "(**no epic worktree**)" | **CHANGED** → "(git reports no epic worktree)". |
| "**A leftover DIRECTORY that git does not report is NOT a dispatch**…" | *(new paragraph)* | **ADDED.** A leftover directory is not a dispatch; deleting one is not how you clear mode 1; the remedy is **`git worktree remove <path>`**, scoped. Carries the counter-intuitive half explicitly: *removing the directory by hand leaves you blocked.* |
| "**`git worktree prune` is NOT an interchangeable alternative.**" | *(new paragraph — Defect B)* | **ADDED.** No path argument, repo-global, one run clears every prunable entry including other epics'. See "Defect B" below. |
| "⚠️ **Check, do not classify.**" | *(new paragraph — design ruling)* | **ADDED.** Gives the reader the `prunable` discriminator instead of a category, names the actor, and states the mode-2 fail-open hazard. See "Design ruling" below. |
| "Worktree writes (`/tmp/.worktrees/...`) always pass unconditionally in both modes" | pass-through | **NO CHANGE NEEDED.** Mirrors the hook's pass-through row — a main-prefix exclusion, true under any root. |
| "Note: mode 1 has NO agent-memory carve-out…" | was "…they happen **when no worktree exists** (mode 2)" | **CHANGED** → "when git reports no epic worktree (mode 2)". The exact twin of the hook's in-body site — the third copy of one claim, which is what made the Pattern-A case for folding this file in. |
| "**Own-memory deliverables go in the worktree**" *(constraint bullet)* | "Since mode 1 no longer carves out agent-memory…" | **NO CHANGE NEEDED.** Consequence of mode 1, not a selection claim. |
| "**No branch management**", "**NEVER restore a working-tree file from the INDEX", and the rest of `## Epic Worktree Constraints` | branch-management ban, index-restore hazard, own-memory rules | **NO CHANGE NEEDED — out of scope** per AC-8's reconciliation-not-rewrite bound, and **verified byte-identical**: no constraint-list line appears in the diff at all. |

> **⚠️ Line citations in this table have now shifted THREE times, every time from
> this story's own edits** — `:33`→`:35` after the AC-8 paragraph, then
> `:35`→`:37` (and `:26`→`:28`, `:28`→`:30`, `:37`→`:39`, `:38`→`:40`) after the
> actor clause. **Fourth and fifth generations, appended 2026-08-01:** the prune
> paragraph shifted this file's citations again (+2 here, +4 in the AC-6b table —
> two files, two deltas, each exactly its own insertion length), and the AC-6b
> table's own numbers had rotted a further +4 unnoticed.
>
> **⚠️ The closing sentence of this note has been REMOVED because it was false
> again.** It read: *"the only reason these are right is that they were re-derived
> after the last edit rather than the first."* They had been re-derived after the
> actor clause and **not** after the prune paragraph — **a claim asserting its own
> currency, inside the note warning about claims asserting their own currency,
> second generation.** The history above is left exactly as written: it is an
> accurate record of what moved when, and editing it would falsify that record.
>
> **The rot is now ENDED rather than re-derived**: both tables cite phrases, which
> do not move. Five generations of re-derivation bought a sixth every time; the
> remedy was recorded here after the third and ignored twice more before being
> applied. *(`cr-e279` made the call; `pm-e279` derived both deltas independently
> and explained each from its own insertion length, which is what showed the two
> tables had drifted by different amounts rather than by one shared offset.)*

**AC-6b's RED form 3 has NO INSTANCE in this file** — recorded as a verdict, not
an edit. There is no semicolon-joined "clear it by removing the directory" here;
that construction was specific to the hook header. **AC-8's surface is genuinely
narrower than AC-6b's.** Confirmed independently by PM.

## Design ruling — the remedy-vs-ban hazard (claude-architect, as `.claude/rules/**` owner)

*(Anchored by phrase, per the note on the AC-8 table. The two sites are the
**"No branch management"** constraint bullet and the **"A leftover DIRECTORY…"**
remedy paragraph.)*

The **"No branch management"** bullet forbids agents running `git worktree remove`;
the remedy paragraph this story added prescribes exactly that, a few lines earlier
in the same file. **The claims are consistent**
— the remedy is scoped to the state *"A crashed dispatch,"* and an agent inside a
live worktree is not in that state — **and consistency was not the problem.**

**`cr-e279` and `pm-e279` asked different questions and both answers are right.**
CR asked *are the claims consistent?* → yes, so do not touch the file. PM asked
*will a reader in a particular state act wrongly on it?* → yes. **PM's diagnosis
is the load-bearing one: self-classification is the step that fails.** An agent
blocked mid-dispatch, reading a remedy addressed as "you," could act on it
destructively. Treating these two as a contradiction and picking a winner would
have produced the wrong outcome.

> **⚠️ This sentence said "could run `git worktree prune` and destroy a live
> dispatch" until 2026-08-01.** That is the Defect A claim, refuted by my own probe
> table above (*"No-op. Entry survives"*) and by CR's — **surviving in the
> narrative ~140 lines from the table that disproves it.** Pattern A inside the
> report, in the section describing Pattern A. The accurate hazards are stated
> where they belong: `prune`'s is the mode-2 fail-open under transient absence
> (Defect A), and its repo-global blast radius (Defect B).
>
> **The identical phrase survives once more below and is deliberately NOT edited**
> — it sits inside a `>` blockquote **quoting the old text being corrected**. That
> is EVIDENCE of what was said, not a criterion anyone must meet, and editing it
> would falsify the record. Same cut that stopped the destructive re-deletion of
> the duplicate: **a sweep that fixes every stale-looking phrase destroys records.**

### ⚠️ This ruling was made TWICE. The first one was withdrawn — on its REASON, not its verdict.

**The first ruling declined-then-landed on the wrong ground.** The reason on
record — *"a scope clause at `:24` would widen the shipped text past AC-8's
reconciliation-not-rewrite bound"* — **is false.** The bound reads *"The rest of
the file — the constraint list, the index-restore hazard, the own-memory rules —
is out of scope."* It protects **pre-existing** content. `:24` is this story's own
new paragraph, so **the bound is silent on it and was never a reason to decline.**

**Four parties handled that claim and none opened the AC: `cr-e279` originated it,
the main session relayed it, I restated it in a formal ruling, and `pm-e279`
caught it — the agent who WROTE the sentence.** CR's own words: *"I asserted the
bound covered it without opening it, and it was one AC in a file I had read
twice."* TN-7's shape with four carriers. **A criterion is an inherited claim like
any other**, and a ruling that cites one is exactly where nobody checks, because
the citation looks like the authority rather than a claim.

### The re-made ruling: LAND A CLAUSE — but `cr-e279`'s form, not mine

**The bound does not reach `:24`, so this is decided on design grounds alone.**

**CR's argument beat my own and I adopted it against my first ruling.** I had
landed an ACTOR-scoped clause ("these commands belong to the operator, never an
agent"). CR's objection:

> *"a clause that asks the reader to classify themselves does not fix a
> self-classification failure"*

That is right, and it is this dispatch's own lesson aimed at a rule file: **prefer
removing the failure mode over documenting it.** An actor clause documents the
hazard and hands the failing faculty more work. **An observable check removes the
classification step entirely.** The landed form leads with the check:

> "**Check, do not classify.** Run `git worktree list`: an entry annotated
> `prunable` is stale; an entry **without** that annotation is LIVE, and clearing
> it destroys a running dispatch."

**The `prunable` behavior was EXECUTED, not reasoned to** — an isolated throwaway
repo in the scratchpad with two worktrees, one directory deleted:
`git worktree list` annotates the dead entry `prunable` and leaves the live one
unannotated. A rule that ships a command and a decision rule into an
always-loaded file must have had that command run.

The actor sentence is **kept but demoted to a subordinate clause**: *am I an
agent?* is reliably answerable, unlike *is this dispatch crashed?*, so it is not
the failing faculty — but it is no longer doing the work. The inference block is
retained verbatim, since it names the specific bad step.

**Why land anything at all**, given CR rates the risk low (five steps must all
occur, two already guarded): **this story created the hazard** — pre-edit the
remedy lived only in the hook header, where its audience was unambiguous — and the
file loads into every agent's context on every interaction. Scope held: changed
OLD-file ranges are **`{21-22, 26}`**, exactly AC-8's three sites, with **no
constraint-list line in the diff at all**. The **"No branch management"** bullet is
cross-referenced, never edited.

**Recorded from CR, because it is a better observation than either ruling:
PM asked the better question.** CR asked whether the text is internally consistent
and answered correctly. PM asked whether a reader acts wrongly on it — which is
what a safety note is *for*. Non-contradictory, not equally useful.

> **⚠️ An earlier joint ruling by PM and me that the "No branch management" ban
> was a non-conflict was made
> against the PRE-EDIT file, when the remedy was not in it.** That ruling's premise
> changed underneath it — the same expiry class this dispatch keeps producing,
> arriving this time as a **ruling** rather than a measurement. A ruling has a
> timestamp exactly as a measurement does.

> **⚠️ Corrected 2026-08-01 — the conclusion above is unchanged; its REASON was
> false and is replaced.** The original read: *"`:35` sits under `## Epic Worktree
> Constraints`, whose trigger the file defines at `:8` … so it binds agents
> working inside a worktree. Anyone reading the remedy is **by construction** not
> in one: they are being denied a write to the main checkout."*
>
> **The "by construction" premise is false.** This file carries `paths: "**"`, so
> it is injected into every agent's context on every interaction — worktree-
> resident implementers included — and **nobody has to be denied anything to read
> it.** Readership is not restricted to the blocked.
>
> **This document asserted the correct version of that same property elsewhere**
> (see the reviewer note at the end: *"every agent running now loaded it"*). Two
> statements in one report that cannot both be true — and the false one is the
> inverse of the ambient-staleness property this report itself raised and
> inoculated the team against. Held correctly in one paragraph, inverted in
> another, by the same author in the same document.
>
> **A right conclusion shielded a wrong premise**, which is the shape epic TN-7
> exists to record. Any check asking *"was the call right?"* passes. Caught by
> `cr-e279` opening the file, not by anyone re-reading the argument.
>
> **The rule file is deliberately NOT changed.** Adding a scope clause to `:24`
> would widen the shipped text past AC-8's reconciliation-not-rewrite bound. The
> defect was in this report's reasoning, so this report is what changes.

**Verified by ABSENCE, whole-file, one pattern carrying four stale forms plus a
known-present control:**

```
$ grep -niE "worktree at [^ ]* exists|\(no epic worktree\)|when no worktree exists|no worktree present|Hook Enforcement" \
    .claude/rules/worktree-isolation.md
17:## Hook Enforcement
```

Only the control matched. The four stale forms return **zero**, and the control
proves the pattern ran against the right file — so the zero is verified absence,
not an unexplained empty. A hunk could not have established this: a diff shows
what changed and is silent on what survived unchanged.

---

## Round-2 SHOULD FIX items

**(3) `worktree-guard.sh` — unqualified safety claim, now two-sided.** The
sentence read *"…can no longer wedge every agent's main-checkout writes"* — an
absolute, while the fallback still globs, so a phantom directory wedges exactly
as before whenever the registry read fails. The file was not self-contradictory
read whole (the fallback is described three paragraphs down), but **that is the
sentence that gets quoted**, and this repo documents the closing-generalization
of a safety note as where this defect concentrates. Repaired in the two-sided
form, in the sentence itself:

> "…can no longer wedge every agent's main-checkout writes (E-279-01) — **EXCEPT
> where the registry is unreadable and the glob fallback below runs, which is
> still directory-driven and still wedgeable. The wedge is closed on the
> authoritative path, not everywhere.**"

**(4) `tests/test_worktree_guard.py` — anti-leak fixture widened to its
criterion.** `_no_real_worktree_dir_leaked` checked one path
(`…baseball-crawl-E-999`) while AC-7's RED is *any* directory under the literal
`/tmp/.worktrees/`; a future test using a different epic number would leak past
it silently. Now snapshots `set(REAL_ROOT.glob("baseball-crawl-E-*"))` before and
after and compares. **Proven non-vacuous** rather than assumed: the snapshot
returns `{PosixPath('/tmp/.worktrees/baseball-crawl-E-279')}` on this machine, so
it is comparing real sets, not two empty ones. This was the guard being weaker
than its AC, not a live leak — CR verified the suite as shipped leaks nothing.

**(5) TN-11 item 4 / IDEA-116 narrowing — NOT ACTIONED, routed to PM.** Epic
file, PM's ownership. Recorded here so it is not read as an omission.

---

## AC status

AC-1 through AC-7: **PASS** — PM verified against the story file, and `cr-e279`
returned **APPROVED scoped to AC-1..AC-7 over the hook and its tests**.

**⚠️ That approval is SCOPED and the scope is not decoration. This is NOT
story-level DONE.** AC-8 was unsatisfied on disk and reviewed by nobody at the
time it was given. CR stated the bound in writing precisely because *a scoped
approval is the kind that gets quoted later without its scope line* — the same
qualified-claims-lose-their-qualifiers reasoning that produced AC-1b bound 5.
AC-8 is implemented in this round and is reviewed as the scoped increment.

### Reviewer rulings on the three judgement calls I raised

1. **Site 12 scope-taking — CORRECT, keep it, do not revert.** RED form 2's exact
   shape one screen below the header being reconciled; leaving it would have been
   the surviving-copy defect this epic catalogued four instances of. CR confirmed
   old line 92 falls in no pinned range.
2. **Bound-2 SET-ONLY substitution — not merely adequate, the ONLY reachable
   form.** CR ran the generalized form against the real `/tmp/.worktrees`
   independently and got ALLOW, reproducing the brick. The literal RED is not
   constructible without deleting a live directory.
3. **The M1 near-miss is load-bearing.** CR built its own battery *before* this
   report arrived — all five of these mutants plus a sixth of its own (fallback
   branch replaced with an authoritative empty answer). **All six kill.** Because
   its mutants were independently authored, the agreement establishes that the
   early SURVIVED was a broken probe rather than a weak test. CR notes the
   shipped `_assert_allowed` checks `returncode == 0`, so the test helper was
   never exposed to the empty-stdout trap — only the ad-hoc probe was.

### Failure classes on this dispatch, recorded for closure codification

> **⚠️ Corrected 2026-08-01. This section previously read "three instances of one
> shape," merging all five on the surface resemblance *something reported cleanly
> and was wrong*. `cr-e279` challenged the count and was right.** The wrong count
> originated in the main session's relay, was corrected with CR, and reached this
> report before the correction did — Pattern A again, and the third time on this
> dispatch that a correction landed where a claim surfaced rather than where it
> lived. Counts below are stated with their members so they can be derived.

**Class 1 — a broken check reports SHAPE-IDENTICALLY to a working one. Two
instances.** (a) The M1 mutant that never ran: bash aborted on an unbalanced `if`
and emitted nothing, and empty stdout is indistinguishable from ALLOW in a guard
that signals denial via stdout. (b) `cr-e279`'s glob-revert probe, contaminated by
the real default root, self-caught.
*Remedy: require an instrument to emit evidence that it OPERATED, separate from
its result.*

**Class 2 — a measurement or status claim, CORRECT when taken and used as a
criterion about the present. Two instances.** (a) This report's stale-diff
sentence: the diff was accurate when run, and I made the site-12 edit before
asserting it. (b) `pm-e279`'s delivery assertion, resting on an implementer report
that could only speak to a past state.
*Remedy: a verification claim expires when the artifact changes.*

**Class 3 — a PARTIAL READ, true in everything it shows and false in what it
implies. One instance.** `cr-e279`'s "two hunks: header and detection" — two hunks
is correct at default context, and naming hunk 2 by one of its three contents is
not. TN-13's shape.
*Remedy: a partial read that happens to be true is not a verified enumeration.*

**Why the split is worth keeping, and it is the whole reason not to merge these:**
my Class 2 error and CR's Class 3 error produced a **byte-identical wrong
sentence** from different defects. No reader can tell from the sentence which
produced it — so finding it tells you a claim is wrong and **nothing about which
check to re-run**. A merged codification aims the remedy at the wrong instrument.

**Every one was caught by a re-run or by a second party. None by re-reading**,
consistent with this repo's 8-of-8 authorship record.

**The disposition argument.** The governing rules for all five already exist and
load on **every interaction for every agent** (`.claude/rules/tool-output-integrity.md`
carries the remedy for each class verbatim). So the finding is not *a rule is
missing* but that **correctly-worded, always-loaded rules failed to bind
repeatedly, for agents who had them loaded and had recently invoked them.**
Adding text is the intervention that has demonstrably not worked here, and it is
the one a context-layer owner reaches for by reflex.

**The one intervention that did work on this dispatch was structural, not
textual**: moving this completion report from a message to a file did not remind
anyone to be careful — it removed the failing leg. That asymmetry is the argument
the closure codification should be built on. Disposition mine at closure;
recorded here so it does not die in a message.

> **⚠️ A stale duplicate of the paragraph above stood here until 2026-08-01,
> still reading "all THREE already exist" against the corrected "all five."**
> When I rewrote this section for the corrected taxonomy, the rewrite landed and
> the section's original tail survived below it. Found by `pm-e279`.
> **This is the FOURTH instance on this dispatch of a correction landing where a
> claim surfaced rather than where it lived — and it is inside the section that
> catalogues that exact class, three paragraphs under my own note calling it the
> third.** The remedy this repo prescribes is the one that would have caught it:
> when you correct a claim, grep for it before closing the correction; the
> correction is done when no other copy is wrong, not when the sentence in front
> of you is right. I did not grep, in the section about not grepping.

## Notes for the reviewer

- **The epic's own directory was untracked at review time** *(pre-archive path
  elided at closure by PM, per TN-3's reword remedy — the observation stands)*, so
  a `git diff`-based review is structurally blind to the epic and story files. The
  three files I changed are visible (two tracked-modified, one untracked-new).
- **Read `.claude/rules/worktree-isolation.md` from disk, not from ambient
  context.** It carries `paths: "**"`; every agent running now loaded it before
  this edit, so the injected copy is stale and disk wins.
