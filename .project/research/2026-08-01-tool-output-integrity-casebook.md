# Tool-Output Integrity — Casebook

**What this is.** The incident record behind `.claude/rules/tool-output-integrity.md`. Every rule in
that file was written because something specific went wrong; this file holds the episodes, and the
rule file points here.

**Why the split (E-280-01).** The rule file is loaded into **every** agent's context on **every**
interaction. Before this split it was 29,251 bytes — 32% of the ~92 KB always-on load every agent
pays every session — and most of that mass was narrative. The narratives earn their keep, because
this repo's record is that a rule stripped of its incident gets re-litigated; they just do not need
to be *resident* in every context window to do that job. **What moved here are the stories.** The rules
stayed — with one class of exception, stated plainly because an absolute here would be false: where a
directive's force sits in a sentence that only reads sensibly beside its episode, the directive moved
with the episode and the rule file points at it. That is a pass, not a loss, **provided the pointer
names its target** — and the rule file's opening says so rather than promising that every rule is
stated there in full.

**The rule file is AUTHORITATIVE on rule text wherever the two overlap.** Several rule sentences are
duplicated here verbatim so each incident reads standalone; that duplication is deliberate and it is
also a drift hazard, because this is the copy nobody loads. If a sentence here disagrees with
`.claude/rules/tool-output-integrity.md`, the rule file wins and this file is stale.

**This file is deliberately OUTSIDE the context layer.** `.project/research/` is not
`.claude/agent-memory/` — moving narrative into agent-memory would relocate it inside the same
layer (resident for all, deferred to one) rather than removing it. Read this file when you are
working on the rule it belongs to, when a rule seems arbitrary and you are about to argue with it,
or when you need the evidence to settle a dispute.

**Figures here are EVIDENCE, not criteria** — a reader is meant to see what was observed, not to
meet a number. They are preserved verbatim from the rule file and must not be "tidied" by a
consistency sweep. (That cut is itself a rule; see [§4207](#e-276--one-figure-that-was-criterion-and-evidence-four-criteria-apart).)

---

## Failure taxonomy

### E-231 — corruption of a bare `echo`

First-hand evidence for the **Garbled** mode lives in
`.project/research/E-231-harness-repro/harness-output-reliability-report.md` — including corruption
of a bare `echo`, which has no file to change and so **cannot** be explained away by the two-cause
differential. This is why "garbled" survives as a real category even though most disagreements turn
out to be a moved file.

Observed shapes: line numbers that disagree with an independent count (a Read reporting 17-19 lines
while `cat -n` shows a clean 1-31 on the same file), a different file's bytes, or a command echoed
back instead of executed.

---

## Grep is not a witness

### Why this became its own section

These entries had no heading of their own until 2026-07-26; they read as footnotes to the failure
taxonomy and were skimmed past. **The first one alone bit the E-276 dispatch twice in one epic, with
the rule file loaded both times** — the content was never missing, it was buried. That is the
argument for headings over footnotes, and it generalizes past this file.

### E-256-15 — ugrep's silent empty

The environment's `grep` is ugrep, which returns EMPTY (no error) for
`grep -rn "a\|b" <path…>` — recursive BRE alternation over multiple path args. In E-256-15 this
exact quirk returned "no matches" for symbols that **were present**, and driving a deletion-eviction
sweep off it would have shipped a false-clean no-op.

### E-277 — five ways a correct pattern narrows, none of them a content change

All five come from one session, and **not one was a content change** — in every case the content was
intact and the SHAPE moved:

| Shape | What was observed |
|---|---|
| Inline emphasis interpolated inside a phrase | `adequate **bound** on` vs a literal search for `adequate bound on` — **2 hits where emphasis-normalized returned 7** |
| Blockquote nesting deepened around a preserved quotation | a still-correct anchor **returned 1 where it had returned 2**, *indistinguishable from the passage having been deleted* |
| A quoted phrase wrapping across a line break | single-line pattern, **EMPTY** against text that is present |
| Hyphenation | `zero adequacy` finds nothing where the text reads `zero-adequacy-content` |
| Letter case | `DO NOT label it` returned **zero** against `Do NOT` — run by the author of this catalogue while being careful, **inside the check the catalogue exists to protect** |

`doc-sweep.md`'s synonym expansion does not reach any of these: they are not synonyms, they are the
same words with markup or whitespace between them.

### E-277 — an unexpected count in either direction, and the fabrication it nearly justified

One match where there were two looks exactly like a deletion; two hits where you expected none look
exactly like a live defect. **Both were wrong in the session that produced this list**, and each was
one step from a fabricated finding — *"this section cites a docstring phrase that does not exist"*
was the sentence a line-break narrowing was about to justify.

### E-277 story 05 — the wrong member returned, and the instruction INVERTED

Story 05 carried **two byte-identical sentences**: the twin that must NOT be edited sat on one line,
while the true target WRAPPED between `emitted` and `per entry`. `grep -n "One WARN was emitted per
entry"` returned **the twin alone** — one confident, plausible hit, with exactly the count expected.

An implementer following the AC literally would have edited the sentence that must not change and
never seen the one that must: **the instruction inverted rather than weakened, inside the AC written
to guard that very twin.** This is the case an unexpected-count reflex cannot catch, because the
count is right.

Supporting figures for the over-match-with-resolution rule: bare `refusals` returned **20 sites**,
`\.refusals` returned **9**, and the must-fix target sat in the **11** the dotted form missed.

### E-277 — the site that survived two independent worklists

One site sat on two independently generated lists and survived both: the implementer surfaced it,
updated it **wrongly**, and reported complete; the reviewer surfaced it, **misadjudicated** it, and
reported PASS. The pattern was right both times. The failure sat between surfacing and ruling —
which is why the remedy binds the implementer as much as the reviewer, and why widening the pattern
would have fixed nothing.

---

## A read that disagrees — the two-cause differential

### E-267 story 03 round 2 — the read was accurate and the file moved

*Re-adjudicated 2026-07-25 from transcripts. This case was recorded in the rule file as the sharpest
known garble; that was wrong, and the correction is the reason the differential exists.*

A PM Read of `src/db/reconcile_at_load.py` returned nonempty, well-formed Python showing precisely
the defect the round was hunting: a restored global OR'd flag (`_pop = any(b.populated for b in
blocks)`, a `frozenset().union(...)` of the id sets) and a `team_id` accepted by
`_prior_line_player_ids` but dropped from its SQL. PM was one step from reporting that the
implementer had shipped a cosmetic fix with its verification mutation left in; a second Read
disagreed and a grep for those tokens returned no matches, so PM concluded the first read had been
garbled.

**It was not a garble.** The timeline:

| Time | Event |
|---|---|
| 21:35:44Z | SE writes exactly those lines into the worktree file as a **mutation-testing mutant** |
| 21:36:02Z | PM's Read lands, rendering them at lines 694-697 |
| 21:36:12Z | SE restores from its scratchpad backup |
| 21:36:20Z | PM's second Read — correctly finds nothing |
| 21:36:28Z | PM's grep — correctly finds nothing |

Both reads were accurate; the file was oscillating on a ~30-second cycle under a concurrent writer.
**The cross-check produced the right ACTION (do not report it) for the wrong REASON** — and had SE
not restored, that same reasoning would have dismissed a mutation that was really there.

Two things to carry: a read that hands you exactly the defect you were looking for is a cross-check
trigger, not a finding; and in a dispatch worktree, an implementer proving a test discriminates **is
a writer of the file you are reviewing** (`.claude/rules/worktree-isolation.md` records that same
practice destroying that same file).

---

## Response protocol

### E-230 — findings characterized before they were read

The E-230 fabrication failure was exactly this: findings characterized before they were read. The
ad-hoc main-session triage context is the thin spot — a preview, a `head`/`tail`, or a truncated
view is not the content, and a large output's first screen is not its findings.

---

## Prose you author is a claim too

### E-270 — six prose defects across five shapes, on a green suite

Prose is unexecutable, so a green suite says NOTHING about it. E-270 shipped six such defects across
five shapes:

- a docstring citing a **test name that existed in no file**
- a comment claiming **"both callers"** when one did not exist
- a spec citation pointing at **a path that could never exist**
- **two consequence claims that were exactly backwards**

Supporting cases for the individual rules:

- **Execute, don't reason.** The claim "a KEEP->PURGE FK aborts the purge" was true only for a
  default-action FK; running it showed an `ON DELETE CASCADE` edge **raises NOTHING and commits**.
- **Line numbers rot.** Twice in E-270 — once to the epic's own text between planning and its final
  story.
- **Over-correction lands in the closing generalization too.** E-270 fixed an understatement into a
  categorically false rule in exactly that position.

### E-277 — the announcement that made an author a reader

The quote-the-literal-bytes rule fired twice on one agent's own text in E-277: a closing sentence
that was symmetric and false in one direction, and a claim asserting a control that was never
staged.

In its author's words: *"an announcement that says 'I am going to fix the docstring' would have
caught neither defect."* The mechanism is that **quoting your own text into an announcement makes
you read it as a READER rather than as its author** — which is why it transfers where *look harder*
does not.

**Bound, and it matters against the 8-of-8 record below: only the PROCEDURAL catch transfers.** One
of those two was attention at drafting and generalizes to nothing; in the one that transfers, the
author did not catch it unaided — the announcement made them a reader. The external count is not
amended by either.

### E-278 — the false claim inherited from a diff

A reviewer took a false claim from a `tests/` diff hunk at the top of a review and restated it.

**A diff is the one channel that announces itself as PRIMARY evidence** — which it is, *about the
code*. The prose between the `+`/`-` lines is someone else's claim arriving under the surrounding
evidence's authority and with none of the suspicion a brief attracts. In the reviewer's own words:
*"a reviewer reading a diff has no reason to think of itself as relaying anything."*

The transferable form is the **mode switch that never happens**, not "read diffs carefully": one
artifact carries evidence and hearsay under a single apparent epistemic status.

*[Recorded by code-reviewer, E-278.]*

### E-272 — one false safety sentence, three downstream carriers

One false sentence in a Technical Note — *"the season-absent default is the stricter table, so an
ambiguous season over-rests"* — reached a shipped **code comment**, an idea file's **urgency
rating**, and a **rule-file draft** before anyone did the arithmetic. It was true for the
sub-varsity branch and **backwards** for the varsity one.

### 2026-07-25 — the retraction that was wrong twice while the verdict stayed right

A verdict's stated REASON rots independently of the verdict, and a correct conclusion immunizes its
false premise: any check that asks "was the call right?" passes, so only reopening the cited file
catches it.

This bites hardest in a RETRACTION, where the relief of having caught an error is what stops the
reason being read. On 2026-07-25 a retraction (*"that text is not in the file"*) was wrong about the
file, and its own correction (*"the rationale applies to a different constant pair"*) was wrong
again — while the verdict, **do not edit the file**, was right all three times.

### 2026-07-25 — the handoff corrected 45 seconds too late

| Time | Event |
|---|---|
| 06:21:08Z | Predecessor session writes a handoff |
| 06:21:53Z | Successor's kickoff prompt generated **from it**, 45 seconds later |
| 06:23:05Z | Successor reads the file |
| 06:27:20Z | Predecessor **strikes the handoff's central claim** — announcing the correction in its own thread, where the already-launched successor could not see it |

A handoff note, research file, or kickoff prompt written for another session to consume is mutable
until it is committed, and correcting it afterwards does not reach a reader who has already read it
or a prompt already handed out.

### E-277 — a correct zero used as a criterion about the present

A reviewer's grep returned a **correct zero** (five known-landed positive controls in the same
call), then it asserted "still unlanded" for **~15 minutes** across two file movements it had itself
`stat`-ed, **stopping an implementer mid-story**.

Its own diagnosis: **the zero was EVIDENCE of a past state, used as a CRITERION about the current
one** — the same cut it had invoked against someone else two messages earlier. In its words: *"I
bracketed my reviews and did not bracket my reporting."* Its bracketed verdicts all stand; only the
unbracketed reporting failed.

**Companion — a repeated assertion is not a repeated measurement.** One measurement re-stated was
reported as "twice, same reviewer," implying a repeating instrument fault, and nearly bought a
permanent residual against every clean verdict that reviewer had issued. That was **counting
STATEMENTS and reporting them as OBSERVATIONS** — committed while writing up that very error.

### E-276 — six one-sided drifts, in both directions

E-276 produced six one-sided drifts in both directions: `self-healing`, `<=2 as a total`, `bounded`
vs `rate`, and an **inverted fail-closed polarity**.

Neither the alarming nor the reassuring qualifier is the defect; **the asymmetry is**. The two-sided
form is the only one a non-author can run from the text alone, having read nothing else.

---

## A check that RAN is not a check that WORKED

### E-276 — `18 of 18`, the figure that was never producible

`18 of 18` rode four artifacts — a research file, a Technical Note and two acceptance criteria —
through **six review passes**.

The true value was **`9 of 18`**: the numerator is bounded by `|fresh| = 9`. And **the false figure
changed no verdict** — both permit, the corrected gate reads **`0 of 9`** and refuses, and the
surrounding conclusion (this gate is broken) was right throughout.

That is exactly why six passes let it through. **Every pass asked whether the number fitted the
argument, which it did; not one asked whether the number was derivable, which it was not.**

### E-276 — one figure that was criterion and evidence four criteria apart

From E-276 story 02, the "Do NOT sweep the `4207` in AC-8" note. The same `4207` carried both roles
in one file:

- As a **stale acceptance baseline** — a CRITERION, and **removed rather than updated**, because
  updating an absolute baseline that a preceding story will move again merely resets a timer.
- Four criteria below, as **the suite size at which a measurement was actually run** — EVIDENCE, and
  editing it would falsify the record of what was observed.

The cut descends from the same ruling for line numbers: a line number is a **citation** when a
reader is meant to GO there, and **evidence** when the reader is meant to see that it MOVED.

**Applied again in review:** two surviving `season-ambiguous` references — in an archived epic
record and in a review scorecard — were left alone as evidence, not criteria. There, editing would
have been the error.

**Provenance worth keeping:** code-reviewer applied this cut by hand, unprompted, on a stale-looking
denominator **before the rule was named**. A rule reinvented independently under load is worth more
than a rule agreed to, so carry the reinvention rather than anyone's concurrence.

### The detection record — who can catch what, and the 8-of-8

Two classes, and merging them overstates a true finding into a false one.

| Class | What it is | Caught by execution/measurement | Caught by careful re-reading |
|---|---|---|---|
| **A** | A FALSE PREMISE under a CORRECT conclusion | **4 of 4** | **0 of 4** |
| **B** | A MISSING MEMBER of an enumeration | — | Yes, **but never by the author** |

Class A's 0-of-4 was **not for want of reading**: someone had the material open every time, and two
were produced by the people who had written the rule against them hours earlier.

**Unifying fact: in 8 of 8, the author never caught their own.** Reading works only from OUTSIDE the
claim's authorship — and against a false premise under a right conclusion, not even then.

**Companion shape:** where an artifact states one conclusion twice at different strengths, EXECUTE
the stronger statement; where it is not executable, the pairing is itself the trigger, because the
weaker claim would be true either way and so certifies nothing about the stronger.

### E-278 — Class A's mirror: a TRUE clause welded to a FALSE INFERENCE

Class A defeats the check "was the conclusion right?". **The mirror defeats the check "was the
premise right?"** — which is the remedy Class A hands you. The two are only legible together.

The claim: *"the CLI reads every summary key by name, so adding a counter raises `KeyError`."*

- The **author** held a TRUE premise (the CLI reads seven keys; the backfill returns those same
  seven) and a false inference (a consumer reading a subset is unaffected, so nothing raises).
- The **refutation** held a TRUE premise (it IS a subset) and its own false inference (therefore
  "every key" is false — which does not follow for an **improper** subset).

**Neither party held a false premise; premise-checking would have cleared both**, and every
individual sentence in the whole episode was true, so no truth-check anywhere would have flagged any
of it.

**Topology:** two carriers were siblings from one author and the third DESCENDED from the second
through a diff — so count the topology as a TREE before reporting N independent sightings. This was
established by **asking the third party directly**, not by inferring it.

The individual form is in `dispatch-pattern.md`: the first concession here was itself false,
conceding felt like the disciplined move, and it produced a new false claim inside a thread about
false claims.

### E-276 — the control that was line-wrapped, and the alarm nobody read

**A bad positive control's empty looks exactly like a tool failure's empty.** A control string was
line-wrapped in the source so no contiguous match existed — one step from a reported harness outage.
A control drawn by eye from **rendered** prose is the high-risk case, because rendering hides the
wrapping that breaks it.

**A mutation probe whose mutation never applied reports the same green as one that did.** The
anti-vacuity guard fired correctly and the probe still reported **`28 passed`**, because the alarm
printed **above** the summary line nobody read. A precondition check whose alarm is discarded is not
a check.

Same shape one layer out: a green test over a fixture that does not do what its name says.

### E-278 — four vacuous assertions, all of them inside guards

All four sat INSIDE guards — the line that reads as the rigour:

1. an `assert local != X` following an `assert local is None` (**unreachable by construction**)
2. a `!= _SENTINEL_DATE` conjunct **comparing two module constants**
3. a `fetchone()` that **returned identically** whether or not the behavior under test occurred
4. an `assert "15-5-<" not in html` that **could never fire** because the header renders a newline
   there

Each was written as the check PROTECTING a criterion. Each passed. **Every one was found by someone
other than its author** — consistent with the 8-of-8 record above.

### E-276 — the audit that ranked its own output backwards

An instrument can be accurate and rank its own output backwards. An E-276 audit led with **nine
`TypeError` call sites** and filed, as "two softer ones", a probe still running against a
configuration that no longer ships.

A `TypeError` is self-announcing — anyone who runs it learns immediately. **The quiet finding, which
produces a plausible number and reports nothing wrong, is the dangerous one**, and no amount of
verifying the findings will catch a wrong ordering of them.

---

*Source: `.claude/rules/tool-output-integrity.md`, split out by E-280-01 (2026-08-02). Nine epics
are represented: E-230, E-231, E-256, E-267, E-270, E-272, E-276, E-277, E-278.*

## E-280 — the partial ruling that passed its own audit

E-280-08 retired the context-layer size gate. Its AC-6 required a regenerated sweep with **a written
verdict per site, `no change needed` included** — the repo's most-repeated finding, and the
implementer pre-registered the enumeration before editing, exactly as the rule prescribes.

`context-layer-assessment.md`'s Assessment Procedure step 3 was **surfaced** by that sweep and ruled
**`no change needed`**, on this reasoning: the line contains *"Triggers 7 and 8 additionally invoke the
Learning-Loop Lifecycle"*, an **ordinal** reference, and AC-11 explicitly protects ordinals while
forbidding cardinal counts. **That reasoning was correct.** The ordinal did have to survive, and it did.

The same line ended with a parenthetical enumerating the Lifecycle's parts: *"(offset accounting,
promote-to-load-target, deletion-side eviction, memory retirement)"*. The story had just retired the
offset-accounting component. **Nobody looked at that half of the line.** The verdict was true about the
ordinal and silent about the dead member sitting fourteen words away.

Every downstream check passed. The site appeared on the enumeration; it carried a written verdict; the
verdict was defensible when read. **An audit asking "did every surfaced site get a written verdict?"
cannot distinguish this from a complete ruling** — which is what separates it from the E-277 case, where
two worklists surfaced a site and both ruled it *wrongly*. Here the ruling was not wrong. It was partial.

**Two further things were true and neither caught it.** The implementer's AC-5 verify-by-absence list
carried `offset the growth` but not bare `offset` — a token narrower than its class, which was **the
lesson its own previous story had produced**, recurring one story later inside the sweep of the agent
that had just written it up. And the implementer authored the enumeration, so by this file's 8-of-8
authorship record it was the party least able to catch it.

**It was found by Codex on a clean external pass**, and the diagnosis had to be adjudicated rather than
pattern-matched: a surviving `offset` token is not by itself a surviving claim, and the three candidate
readings (dangling pointer / live residual breaching AC-5 / a phrase that now means something else)
called for three different repairs. Reading the Lifecycle body settled it — no offset-accounting
component survived anywhere, and `offset` occurred exactly once in the file, in trigger 7's negation.

**Transferable form**: name which CLAIM a verdict is about, not merely which site. A per-site verdict
column is satisfied by a ruling that read one clause of the line.
