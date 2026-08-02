# E-280-01 — per-rule inventory for `.claude/rules/tool-output-integrity.md`

**Purpose.** This is the AC-1 worklist for E-280-01. Every rule stated in the pre-change file gets
one row quoting its pre-change literal text, and (AC-3) a written verdict naming where that rule
lives after the distillation — including the verdict `carried unchanged`. **No row carries a removal
verdict** (AC-4).

**Pre-registration order matters and is the point.** Rows **1–76** and their quoted text were written
to disk and reported to the dispatch lead **before the first edit to the rule file**, so AC-3 and AC-4
are checkable against a fixed list rather than reconstructed from the diff. **Row 77 is a post-hoc
addition from round-1 remediation and is marked as such** — it is not covered by that claim. The rule file's own
record (row 60: *"in 8 of 8, the author never caught their own"*) is why.

**Source of the enumeration.** The pre-change file was read **from disk in this session**
(`/tmp/.worktrees/baseball-crawl-E-280/.claude/rules/tool-output-integrity.md`), not from the
ambient/injected copy, per the story's Context hazard. Each of the file's paragraphs is a single
physical line, so no quoted fragment spans a line break.

**How the verdicts were established — not by eye.** Three scripted checks, each with a negative
control proving it can fail:

| Check | Result | Negative control |
|---|---|---|
| Every quoted fragment appears verbatim in the pre-change blob (AC-1 RED) | **83 spans, 0 failures** | planted a fabricated quote → flagged |

**What "spans" counts, stated because the figure is not `77` and a reader will ask.** A *span* is one
double-quoted fragment in the row table's rule column — **not** a row. Five rows quote more than one
fragment (rows 23, 27, 40 and 52 carry two each; row 60 carries three), contributing **+6** over the
row count. So rows 1–76 hold **82** spans and row 77 adds one, giving **83**.

That arithmetic is recorded because the figure went stale once and the staleness was invisible: `82`
was **correct and producible** when the table had 76 rows, and it survived the row-77 amendment
because remediation updated the AC-3 row's `76 of 76 → 77 of 77` and missed this cell. Re-derived
here from the generating script, not reasoned to.
| Every rule resolves into its named location (AC-3 / AC-4) | **77 of 77 present** (76 in RF, row 77 in CB with its pointer named) | fabricated rule text → correctly absent |
| Every casebook narrative has an inbound pointer and every pointer resolves (AC-8, both REDs) | **24 pointers ↔ 24 narratives, 0 dangling, 0 orphans** | corrupted a pointer → RED-a; added an unpointed heading → RED-b |

---

## AC-2 / AC-5 / AC-5a / AC-6 — measurements

| Measure | Before | After | Delta |
|---|---|---|---|
| **Rule file bytes (AC-5, PRIMARY)** | **29,251** | **23,172** | **−6,079 (−20.8%)** |
| Rule file lines | 98 | 91 | −7 |
| Rule file words | 4,850 | 3,849 | −1,001 |
| **Always-on load, all agents (AC-5a)** | **92,419** | **86,340** | **−6,079 (−6.6%)** |
| This file's share of that load | 31.6% | 26.8% | −4.8 pts |
| **`.claude/rules` subtree lines (AC-6, secondary)** | **2,649** | **2,642** | **−7** |

**Round-1 remediation cost 283 bytes** (22,889 → 23,172), spent restoring SF-1's antecedent and
guard, SF-2's population, and restating the RF absolute. The win moved from −21.8% to −20.8%. That
trade is correct on this epic's own terms: the epic's binding principle is to shrink the
**error-generating** surface, and three of those bytes' worth of clauses were load-bearing guards on
figures that stayed. A byte win bought by leaving `8 of 8` unguarded and `4 of 4` without its
population would be the wrong kind of win.

Bytes measured with `wc -c` directly on the file, per AC-5. Always-on load measured with the epic
TN-9 one-liner. Subtree lines read from `.claude/hooks/context-ratchet.sh` (an on-demand diagnostic,
not a gate; nothing here is offset or excepted).

Per-file always-on breakdown, measured **before** the change — reproduces all eight of epic TN-9's
figures and the 92,419 total **exactly**:

| File | Bytes |
|---|---|
| `CLAUDE.md` | 22,157 |
| `.claude/rules/tool-output-integrity.md` | 29,251 |
| `.claude/rules/workflow-discipline.md` | 12,035 |
| `.claude/rules/dispatch-pattern.md` | 11,433 |
| `.claude/rules/worktree-isolation.md` | 6,727 |
| `.claude/rules/agent-routing.md` | 6,095 |
| `.claude/rules/agent-team-compliance.md` | 3,586 |
| `.claude/rules/vision-signals.md` | 1,135 |
| **total** | **92,419** |

**These pre-change figures are EVIDENCE of the pre-state, not criteria** (AC-5a's own instruction).
They agree with TN-9 to the byte; had they disagreed, the divergence would have been reported rather
than reconciled to the stated number.

**AC-6 was RED on the first attempt, and the fix was structural rather than cosmetic.** The first
distillation cut 6,384 bytes but took the file from 98 lines to **109** — pointers and their
surrounding blank lines cost more lines than the deleted narrative freed, because narrative lives in
few very long lines. That is epic TN-4(b) exactly: a line count is the wrong instrument for
long-paragraph prose. Rather than reflow the file to buy a number, the six standalone pointer blocks
were folded onto the end of the last paragraph of each section — where they read better anyway — and
the casebook-orientation paragraph merged into the opening. **The byte result is essentially
unchanged (22,867 → 22,889, +22 B); the line result moved 109 → 91.** Recorded because it is a live
demonstration of the divergence the epic asserts.

---

## Narrative census (AC-8 scope)

Independent count of epic-ID tokens in the pre-change file, reproducing the story Context census
exactly: **9 epics, 24 mentions** — E-276 ×7, E-278 ×4, E-277 ×4, E-270 ×4, and E-272 / E-267 /
E-256 / E-231 / E-230 ×1 each. Reading the file surfaced **no tenth epic**, so the story Notes'
"floor, not target" caveat resolves to the same number. Those nine epics decompose into the **24
casebook narratives** enumerated below.

---

## Externally-cited anchors — enumerated BEFORE editing, all preserved

Inbound citations from outside the rule file. Renaming or deleting any of these breaks a live
reference elsewhere, including one in **executable code**. Enumerated before the design so they
constrained it, rather than being discovered by breaking them.

| Anchor | Cited by | Status |
|---|---|---|
| `## A check that RAN is not a check that WORKED` (heading) | `doc-sweep.md:31`; `epic-codifications.md:163`; `IDEA-232`; `IDEA-233` | **preserved verbatim** |
| Prohibition numbered exactly **3** | `doc-sweep.md:53`; **`.claude/hooks/dispatch-telemetry.py:14` and `:224` (code)**; `dispatch-telemetry-design.md:84` | **preserved, still third** |
| **A claim you RELAY is a claim you AUTHOR** | `claude-architect/MEMORY.md`; `epic-codifications.md:154` | **preserved verbatim** |
| **A handoff artifact is a claim with a timestamp** | `claude-architect/MEMORY.md:105`; `product-manager/e276-health-gate-triage.md:197` | **preserved verbatim** |
| Two-cause differential section | `claude-architect/MEMORY.md:105`; `product-manager/feedback_clean_reread_before_defect.md` | **preserved**, heading unchanged |
| Detection record with **Class A's MIRROR immediately after it** | `epic-codifications.md:199` (cites the *adjacency*) | **preserved, adjacency intact** |
| Criterion-vs-evidence cut | `IDEA-224`, `IDEA-228`, `IDEA-231`, `code-reviewer/run_the_shipped_gate_against_its_own_epic.md`, `implement/SKILL.md:652` | **preserved verbatim** |

**One intra-file pointer was re-aimed.** The differential's item 1 read *"In the 2026-07-25 incident
under \"A handoff artifact is a claim with a timestamp\" below"*. The bold rule-sentence still
exists, but the *incident* moved to the casebook, so the phrase now reads **"In the 2026-07-25
handoff incident"** — which resolves against both the surviving rule sentence and the casebook
narrative. Left unedited it would have pointed at a rule that no longer carries the episode.

---

## The rows (AC-1) with verdicts (AC-3) and no removals (AC-4)

Verdict vocabulary:
- `carried unchanged` — the rule survives verbatim in the distilled rule file.
- `carried unchanged*` — survives, differing **only** in emphasis markers, letter case, or terminal
  punctuation. Six rows; all six confirmed present under the three normalizations the file itself
  prescribes (strip `**`/`__`, case-insensitive, punctuation-tolerant). See the note below the table.
- `+ narrative → CB` — the rule stays in the rule file; only its *episode* moved, and the rule file
  points at it.

`RF` = the distilled `.claude/rules/tool-output-integrity.md`.
`CB` = `.project/research/2026-08-01-tool-output-integrity-casebook.md`.

| # | Rule — verbatim pre-change fragment | Pre-change site | Verdict | Post-change location |
|---|---|---|---|---|
| 1 | "No tool can detect a garbled-but-nonempty read; only an agent applying this discipline can." | L8 opener | carried unchanged | RF opening |
| 2 | "Treat any of these as a tool-output FAILURE, not as truth:" | L12 | carried unchanged | RF § Failure taxonomy |
| 3 | "**Empty** -- a read/command returns nothing for a target you know or expect to be non-empty." | L14 | carried unchanged | RF § Failure taxonomy |
| 4 | "**Truncated** -- output is cut off (tail missing, a partial edit that did not fully land)." | L15 | carried unchanged | RF § Failure taxonomy |
| 5 | "**Garbled** -- output is nonempty but wrong." | L16 | carried unchanged | RF § Failure taxonomy |
| 6 | "Content that merely disagrees with a LATER read is not yet in this class: run the differential below before you name it." | L16 | carried unchanged | RF § Failure taxonomy |
| 7 | "First-hand evidence for this mode lives in `.project/research/E-231-harness-repro/harness-output-reliability-report.md`" | L16 | carried unchanged | RF § Failure taxonomy (external evidence path deliberately kept in the rule file) |
| 8 | "the environment's `grep` is ugrep, which returns EMPTY (no error)" | L22 (Grep 1) | carried unchanged + narrative → CB | RF § Grep 1; CB § "E-256-15 — ugrep's silent empty" |
| 9 | "Use `grep -rnE \"a\|b\"` (ERE), or a single pattern / single path." | L22 (Grep 1) | carried unchanged | RF § Grep 1 |
| 10 | "Treat an unexpected empty grep as an **Empty** FAILURE to cross-check (re-run with `-E` or per-file), never as proof of absence" | L22 (Grep 1) | carried unchanged | RF § Grep 1 |
| 11 | "A CORRECT grep pattern silently NARROWS when the document's markup moves beneath it" | L24 (Grep 2) | carried unchanged + narrative → CB | RF § Grep 2 keeps all five shapes; per-shape figures in CB § "E-277 — five ways a correct pattern narrows, none of them a content change" |
| 12 | "three normalizations, not one: strip `**`/`__`, expect hyphenation and inflection variants, and match case-insensitively." | L24 (Grep 2) | carried unchanged (**CRITERION**, kept verbatim) | RF § Grep 2 |
| 13 | "an unexpected COUNT is a cross-check trigger, never a finding -- ANY count you did not predict, in EITHER direction." | L26 (Grep 3) | carried unchanged + narrative → CB | RF § Grep 3; CB § "E-277 — an unexpected count in either direction, and the fabrication it nearly justified" |
| 14 | "`doc-sweep.md`'s synonym expansion does not reach any of these: they are not synonyms, they are the same words with markup or whitespace between them." | L26 (Grep 3) | carried unchanged | RF § Grep 3 |
| 15 | "A narrowed pattern does not only go EMPTY -- it can return the WRONG MEMBER and look successful" | L28 (Grep 4) | carried unchanged + narrative → CB | RF § Grep 4; CB § "E-277 story 05 — the wrong member returned, and the instruction INVERTED" |
| 16 | "When the discriminating token is not present at the sites you are ruling on, the check is a JOIN, not a grep" | L28 (Grep 4) | carried unchanged | RF § Grep 4 |
| 17 | "**An unresolvable site is a finding, not a default to the likelier owner.**" | L28 (Grep 4) | carried unchanged | RF § Grep 4 |
| 18 | "under-match is silent, over-match is visible" | L28 (Grep 4) | carried unchanged; supporting figures → CB | RF § Grep 4; the 20 / 9 / 11 `refusals` figures in CB § "E-277 story 05 — the wrong member returned, and the instruction INVERTED" |
| 19 | "but **only while unresolvable sites must be REPORTED**; without that clause over-matching degrades into quiet judgement calls and is no better." | L28 (Grep 4) | carried unchanged | RF § Grep 4 |
| 20 | "A sweep is a WORKLIST, not a scan, and its failure can sit between SURFACING and RULING rather than in the pattern." | L30 | carried unchanged\* + narrative → CB | RF § Grep, "Two rules that survive"; CB § "E-277 — the site that survived two independent worklists" |
| 21 | "Every surfaced line gets a WRITTEN verdict, \"no change needed\" included, and this binds the IMPLEMENTER as much as the reviewer" | L30 | carried unchanged | RF § Grep, "Two rules that survive" |
| 22 | "Do not respond by widening the pattern." | L30 | carried unchanged | RF § Grep, "Two rules that survive" |
| 23 | "design the first run so its empty is already interpretable" / "a known-present term carried in the same OR-pattern is a free positive control" | L30 | carried unchanged | RF § Grep, "Two rules that survive" |
| 24 | "So name the cause from evidence that does:" (two causes, symptoms identical, neither discriminates) | L34 | carried unchanged | RF § two-cause differential, opener |
| 25 | "A harness note that the file \"has been modified on disk since you last read it\" -- including an Edit rejected on that ground -- is PRIMARY EVIDENCE that the file moved." | L36 (item 1) | carried unchanged; **intra-file pointer re-aimed** | RF § differential item 1; episode in CB § "2026-07-25 — the handoff corrected 45 seconds too late" |
| 26 | "**`stat -c '%y' <file>`** against the time of your read. An mtime later than your read settles it." | L37 (item 2) | carried unchanged | RF § differential item 2 |
| 27 | "Enumerate who else can write this tree" / "\"Nobody else is writing\" is an assumption until you have checked it." | L38 (item 3) | carried unchanged | RF § differential item 3 |
| 28 | "grep the other writer's transcript for the text you remember." + `~/.claude/projects/<cwd-slug>/<session-id>.jsonl` | L39 (item 4) | carried unchanged | RF § differential item 4 |
| 29 | "The two causes demand OPPOSITE actions, which is what makes the misfile expensive." | L41 | carried unchanged | RF § differential, closing |
| 30 | "a read that hands you exactly the defect you were looking for is a cross-check trigger, not a finding" | L43 | carried unchanged + narrative → CB | RF § differential, closing; CB § "E-267 story 03 round 2 — the read was accurate and the file moved" |
| 31 | "in a dispatch worktree, an implementer proving a test discriminates IS a writer of the file you are reviewing" | L43 | carried unchanged\* + narrative → CB | RF § differential, closing; CB § "E-267 story 03 round 2 — the read was accurate and the file moved" |
| 32 | "**Treat it as a FAILURE** -- do not act on it or report it as the result." | L49 (protocol 1) | carried unchanged | RF § Response protocol, item 1 |
| 33 | "**Cross-check via an independent channel** -- a different tool, or a different command against the same target." | L50 (protocol 2) | carried unchanged | RF § Response protocol, item 2 |
| 34 | "**Retry** to obtain a clean result." | L51 (protocol 3) | carried unchanged | RF § Response protocol, item 3 |
| 35 | "**Escalate rather than assert** if a clean result still cannot be obtained." | L52 (protocol 4) | carried unchanged | RF § Response protocol, item 4 |
| 36 | "**Read persisted review/tool findings to completion BEFORE characterizing, summarizing, or triaging them.**" | L53 (protocol 5) | carried unchanged; E-230 attribution → CB | RF § Response protocol, item 5; CB § "E-230 — findings characterized before they were read" |
| 37 | "When two channels disagree, **the clean read wins** over a flaky empty or garbled result -- but only once the differential has ruled out a moved file." | L55 | carried unchanged | RF § Response protocol, closing |
| 38 | "A \"no files found\" Glob is NOT proof of absence under a flaky channel" | L55 | carried unchanged | RF § Response protocol, closing |
| 39 | "Prose is unexecutable, so a green suite says NOTHING about it" | L59 | carried unchanged\*; E-270 census → CB | RF § Prose, opener; CB § "E-270 — six prose defects across five shapes, on a green suite" |
| 40 | "**Enumerate every symbol AND path the prose cites**" / "Where a reference is missing, establish WHY rather than noting it." | L63 (prose 1) | carried unchanged | RF § Prose, item 1 |
| 41 | "**EXECUTE behavioral claims rather than reasoning to them.**" | L64 (prose 2) | carried unchanged; FK example → CB | RF § Prose, item 2; CB § "E-270 — six prose defects across five shapes, on a green suite" |
| 42 | "**Cite a stable anchor, not a line range.**" | L65 (prose 3) | carried unchanged; "twice in E-270" → CB | RF § Prose, item 3; CB § "E-270 — six prose defects across five shapes, on a green suite" |
| 43 | "QUOTE THE LITERAL BYTES to a reader who will check them." | L67 (prose 4) | carried unchanged | RF § Prose, item 4; CB § "E-277 — the announcement that made an author a reader" |
| 44 | "only the PROCEDURAL catch transfers" (the bound on row 43) | L67 (prose 4) | carried unchanged | RF § Prose, item 4 |
| 45 | "**Verify a prose fix by ABSENCE, not by presence.**" | L68 (prose 5) | carried unchanged | RF § Prose, item 5 |
| 46 | "**A claim you RELAY is a claim you AUTHOR.**" | L70 | carried unchanged (**externally-cited anchor**) | RF § Prose, RELAY paragraph |
| 47 | "**That list reads closed and is not**" | L70 | carried unchanged | RF § Prose, RELAY paragraph |
| 48 | "**A diff is the one channel that announces itself as PRIMARY evidence**" | L70 | carried unchanged + narrative → CB | RF § Prose, RELAY; CB § "E-278 — the false claim inherited from a diff" |
| 49 | "**A verdict's stated REASON rots independently of the verdict**" | L70 | carried unchanged | RF § Prose, RELAY paragraph |
| 50 | "This bites hardest in a RETRACTION, where the relief of having caught an error is what stops the reason being read" | L70 | carried unchanged + narrative → CB | RF § Prose, RELAY; CB § "2026-07-25 — the retraction that was wrong twice while the verdict stayed right" and CB § "E-272 — one false safety sentence, three downstream carriers" |
| 51 | "**A handoff artifact is a claim with a timestamp.**" | L72 | carried unchanged (**externally-cited anchor**); timeline → CB | RF § Prose, handoff paragraph; CB § "2026-07-25 — the handoff corrected 45 seconds too late" |
| 52 | "**A STATUS claim decays exactly like a verdict, and nobody brackets those**" / "**Attach the measurement and its time to a status assertion, or do not make one.**" | L74 | carried unchanged + narrative → CB | RF § Prose, STATUS paragraph; CB § "E-277 — a correct zero used as a criterion about the present" |
| 53 | "**a repeated assertion is not a repeated measurement.**" | L74 | carried unchanged\* | RF § Prose, STATUS paragraph |
| 54 | "**The safety-comment sub-class (where this defect concentrates).**" | L76 | carried unchanged | RF § Prose, safety-comment paragraph |
| 55 | "the tidy general rule at the END of a safety note is where this lands" | L76 | carried unchanged | RF § Prose, safety-comment paragraph |
| 56 | "**The check is NOT \"does this sound appropriately grave\" -- it is \"are BOTH sides of the trade stated?\"**" | L76 | carried unchanged + narrative → CB | RF § Prose, safety-comment; CB § "E-276 — six one-sided drifts, in both directions" |
| 57 | "**Re-derive a figure from the thing that would produce it, and treat its agreement with the conclusion as no evidence at all.**" | L80 | carried unchanged; figures → CB | RF § A check that RAN, producibility; CB § "E-276 — `18 of 18`, the figure that was never producible" |
| 58 | "***a figure is a CRITERION when a reader must meet it, and EVIDENCE when a reader must see what was observed. Correct the first; preserve the second.***" | L82 | carried unchanged\* (**externally-cited**); episode → CB | RF § A check that RAN; CB § "E-276 — one figure that was criterion and evidence four criteria apart" |
| 59 | "So a consistency sweep that \"fixes every stale-looking figure\" is not a safe default; it destroys records." | L82 | carried unchanged | RF § A check that RAN |
| 60 | "**Class A -- a FALSE PREMISE under a CORRECT conclusion**" / "**Class B -- a MISSING MEMBER of an enumeration**" / "**Unifying fact: in 8 of 8, the author never caught their own.**" | L84 | carried unchanged (4-of-4, 0-of-4 and 8-of-8 **retained in the rule file**) | RF § A check that RAN, detection record |
| 61 | "where an artifact states one conclusion twice at different strengths, EXECUTE the stronger statement" | L84 | carried unchanged | RF § A check that RAN, detection record |
| 62 | "**Class A's MIRROR -- a TRUE clause welded to a FALSE INFERENCE -- and the two are only legible together.**" | L86 | carried unchanged (**adjacency to the detection record preserved**) + narrative → CB | RF § A check that RAN; CB § "E-278 — Class A's mirror: a TRUE clause welded to a FALSE INFERENCE" |
| 63 | "**When a premise checks out and the conclusion still looks wrong, check the INFERENCE -- \"was the premise true?\" terminates too early.**" | L86 | carried unchanged | RF § A check that RAN, mirror paragraph |
| 64 | "count the topology as a TREE before reporting N independent sightings" | L86 | carried unchanged | RF § A check that RAN, mirror paragraph |
| 65 | "**And the running can lie: a broken check's output is SHAPE-IDENTICAL to a working one's.**" | L88 | carried unchanged + narrative → CB | RF § A check that RAN; CB § "E-276 — the control that was line-wrapped, and the alarm nobody read" |
| 66 | "**confirm your control exists CONTIGUOUSLY in the target before concluding the tool failed**" | L88 | carried unchanged | RF § A check that RAN |
| 67 | "**a precondition check whose alarm is discarded is not a check.**" | L88 | carried unchanged | RF § A check that RAN |
| 68 | "**So run the check AND validate the check's own preconditions, and require an instrument to emit evidence that it OPERATED, separate from its result -- then do not filter that evidence away.**" | L88 | carried unchanged | RF § A check that RAN |
| 69 | "**And the vacuity concentrates in the ANTI-VACUITY line itself, because that is the line that reads as the rigour.**" | L90 | carried unchanged + narrative → CB | RF § A check that RAN; CB § "E-278 — four vacuous assertions, all of them inside guards" |
| 70 | "**make the guard FAIL on purpose before you trust it**" | L90 | carried unchanged | RF § A check that RAN, vacuity paragraph |
| 71 | "prefer an assertion whose negative form is constructible (a regex with a lookahead, an explicit `pytest.raises`) over a substring or inequality whose non-match has many innocent causes." | L90 | carried unchanged | RF § A check that RAN, vacuity paragraph |
| 72 | "**Severity ordering is a claim, and it is the least-checked kind, because every finding under it is true.**" | L92 | carried unchanged + narrative → CB | RF § A check that RAN; CB § "E-276 — the audit that ranked its own output backwards" |
| 73 | "The quiet finding, which produces a plausible number and reports nothing wrong, is the dangerous one" | L92 | carried unchanged\* | RF § A check that RAN, severity paragraph |
| 74 | "**Never assert or relay file content or a tool outcome you have not seen cleanly in your own context.**" | L96 (Prohibition 1) | carried unchanged | RF § Prohibitions, item 1 |
| 75 | "**Never co-batch a relay or report with the same-batch command whose output it reports.**" | L97 (Prohibition 2) | carried unchanged | RF § Prohibitions, item 2 |
| 76 | "**Never rule on a grep / OR-pattern match -- Read and quote the literal line.**" | L98 (Prohibition 3) | carried unchanged (**still numbered 3** — cited from `.claude/hooks/dispatch-telemetry.py`) | RF § Prohibitions, item 3 |
| 77 | "so carry the reinvention rather than anyone's concurrence" | L82 (closing clause) | **added post-hoc — see note below**; carried, relocated to CB with its target named | CB § "E-276 — one figure that was criterion and evidence four criteria apart"; reachable from RF § "A check that RAN is not a check that WORKED" |

**77 rows, 77 verdicts, zero removals.**

### Row 77 was NOT pre-registered, and saying so is the point

Rows 1–76 were written and reported before the first edit. **Row 77 was not** — it was added during
round-1 remediation, and the clause was surfaced by **code-reviewer**, not by me. Recording that
distinction rather than quietly renumbering to 77, because the pre-registration property is exactly
the kind of claim that decays into a false absolute if the artifact is edited later without saying so.

CR found it with a **directive-sentence sweep** — enumerating imperative clauses and asking which
resolve to neither the rule file nor an inventory row. My AC-1 definition ("any numbered rule or
bolded rule-sentence") does not reach an unbolded imperative clause riding the tail of a narrative
sentence, so my enumeration could not have surfaced it however carefully I ran it. **That is the
Class B shape this file's own row 60 describes: a missing member of an enumeration, caught by
reading, never by the author.** The 8-of-8 record holds; this is the ninth.

⚠️ **Disposition, so this sentence does not license the edit it invites: do NOT update the 8-of-8
figures in `.claude/rules/tool-output-integrity.md` to nine.** The figure appears there in **two
forms across four sites**, and a sweep that normalizes only one form will silently miss the rest —
cited by anchor rather than line, because line numbers rot:

**"Site" here means a matchable PHRASE, not an anchor or paragraph** — ruled explicitly, because the
two readings give different counts and a table a sweeper cannot use phrase-by-phrase is the failure
this item exists to prevent. Prose item 4 contains **two** occurrences, so by the anchor reading
there are four sites and by the phrase reading five. Every row below quotes a distinct phrase, which
is the phrase reading, so **five is the number**:

| # | Site (verbatim phrase) | Form |
|---|---|---|
| 1 | Prose item 4's bound — *"the 8-of-8 author record below"* | hyphenated |
| 2 | Prose item 4's guard — *"the 8-of-8 count is not amended by either"* | hyphenated |
| 3 | The detection record — *"in 8 of 8, the author never caught their own"* | spaced |
| 4 | The vacuity paragraph — *"consistent with the 8-of-8 authorship record above"* | hyphenated |
| 5 | The casebook pointer naming the heading *"The detection record — who can catch what, and the 8-of-8"* | hyphenated |

A literal `grep -c "8 of 8"` returns **1** against these five sites; `grep -oE "8[- ]of[- ]8"` returns
**5**. That under-match is the hyphenation shape from this file's own Grep entry 2, and it fired here
while writing this very disposition.

**Row 2 was missing from the first version of this table, and it is the one this remediation itself
added** — the SF-1 guard clause, on the same line as row 1. So the enumeration guarding a figure
omitted the occurrence created by the edit that prompted the guard. It was found by a non-author
re-enumerating **from the file rather than from this clause**, which is the only method that works:
an enumeration checked against its own generating definition cannot detect a member that definition
excludes. Those sites record a
**closed series** — a reader is meant to see what was observed, which makes them EVIDENCE, and
editing evidence to reconcile it against a later observation falsifies the record. The ninth instance
is a **separate observation recorded here**, not a revision of that series. A consistency sweep that
"fixes" the apparent disagreement between this file's "ninth" and the rule file's "8 of 8" would be
doing exactly what the criterion-versus-evidence cut forbids.

The relocation itself is legitimate under TN-5 (a rule that moved to a pointer is a pass with its
target named, and CB is reachable from RF § "A check that RAN is not a check that WORKED"). What was
defective was the pair of absolutes I authored around it — see the MUST FIX note below.

### Round-1 remediation: two absolutes I authored were false

The casebook opened *"**No rule moved here. Only stories did.**"* and the rule file opened *"Every
RULE is stated here in full."* **Both are false, and row 77 is the counterexample** — a directive
(*"so carry the reinvention rather than anyone's concurrence"*) that moved to the casebook with no
counterpart in the rule file.

Neither absolute was asked for. **TN-5's actual bar is weaker**: *"a rule that moved to a pointer is
a pass with its target named."* I wrote a stricter claim than the epic required and then failed it —
and both sentences sit in the position this file's own safety-comment rule flags as least likely to
be challenged, one of them being the **first thing every agent reads**.

**Remedy taken: restate both to TN-5's bar** rather than restore the clause to the rule file. The
choice is deliberate. Restoring one clause fixes one instance; the absolutes would still be stricter
than the epic's own standard and would be falsified by the next legitimate pointer-relocation. The
failure mode CR named — a later trim pass reading *"No rule moved here"* and treating the casebook as
safely ignorable — is caused by the absolute, not by the relocation, so the absolute is what changed.
The casebook now also states that the rule file is **authoritative on rule text wherever the two
overlap**, which is the drift guard for the deliberate RF↔CB duplication.

### The six `carried unchanged*` rows, and why they are worth naming

Rows **20, 31, 39, 53, 58, 73** fail a *verbatim* match against the distilled file and pass a
normalized one. Every difference is one of: bold markers moved across a sentence boundary
(20, 31, 39), a terminal period moved outside an emphasis span (53), or a leading letter
recapitalized because the sentence no longer follows a colon (58, 73).

**This is the file's own Grep entry 2 firing on the check written to enforce it** — the same five
shapes (emphasis, case, punctuation) that make a correct pattern narrow silently. It also fired
earlier, on the pre-registration itself: the first run of the AC-1 verbatim check reported four
failures, three of which were quotes I had lifted ending in `**` where the source's bold span runs
wider than the fragment. In both cases the content was intact and the **shape** had moved. Recorded
because it is first-hand evidence for the rule, produced while applying it.

---

## AC-9 — every figure the change touched, classified

The cut applied is row 58's own: a figure a reader must **meet** is a CRITERION and may be restated;
a figure a reader must **see as observed** is EVIDENCE and is preserved verbatim.

| Figure | Class | Disposition |
|---|---|---|
| `three normalizations, not one` | **CRITERION** | Kept verbatim in RF — a reader must meet it |
| `four separate ways it lies` (section heading) | **CRITERION** | Kept; still matches exactly four numbered entries |
| `five observed shapes` (Grep 2) | **CRITERION** | Kept; still matches the five shapes listed in RF |
| Prohibition numbering `1` / `2` / `3` | **CRITERION** (cited from code) | Kept; ordering preserved |
| `4 of 4` and `0 of 4` (Class A detection) | **EVIDENCE** | **Retained verbatim in RF** — load-bearing for what the rule claims reading can and cannot catch |
| `8 of 8` (author never caught their own) | **EVIDENCE** | **Retained verbatim in RF** — **five matchable occurrences in two forms**; see the disposition table under "Row 77 was NOT pre-registered" for the site-by-site list. Do not update any of them to nine. |
| `17-19 lines` vs a clean `1-31` (the Garbled example) | EVIDENCE | Moved to CB § "E-231 — corruption of a bare `echo`", values unaltered |
| `2026-07-26` (the date the Grep section gained its heading) | EVIDENCE | Moved to CB § "Why this became its own section", date unaltered |
| "bit the E-276 dispatch **twice** in one epic" | EVIDENCE | Moved to CB § "Why this became its own section", value unaltered |
| E-267 `~30-second` oscillation cycle; `lines 694-697` | EVIDENCE | Moved to CB § "E-267 story 03 round 2 — the read was accurate and the file moved", values unaltered |
| `2 hits` / `7` emphasis-normalized; `1` where `2` (Grep 2 shapes) | EVIDENCE | Moved to CB, values unaltered |
| `20 sites` / `9` / `11` (`refusals`) | EVIDENCE | Moved to CB, values unaltered |
| `18 of 18` / `9 of 18` / `0 of 9` / `\|fresh\| = 9` / four artifacts / six passes | EVIDENCE | Moved to CB, values unaltered |
| `4207` (criterion-and-evidence case) | EVIDENCE | Moved to CB, value unaltered |
| `28 passed` (mutation probe) | EVIDENCE | Moved to CB, value unaltered |
| `~15 minutes`, `five known-landed positive controls` | EVIDENCE | Moved to CB, values unaltered |
| `nine TypeError call sites` | EVIDENCE | Moved to CB, value unaltered |
| `six defects across five shapes` (E-270); `six one-sided drifts` (E-276) | EVIDENCE | Moved to CB, values unaltered |
| `seven keys` (E-278 mirror); `four vacuous assertions` (E-278) | EVIDENCE | Moved to CB, values unaltered |
| E-267 timeline `21:35:44Z` → `21:36:28Z`; handoff timeline `06:21:08Z` → `06:27:20Z` | EVIDENCE | Moved to CB, **values unaltered**; rendered as tables — presentation changed, no figure changed |
| Pre/post byte, line and load figures for this story | EVIDENCE | Recorded in this inventory (AC-2 / AC-5 / AC-5a / AC-6), not in RF |

### One figure was REMOVED rather than relocated, and it is the only one

The pre-change Grep section opened: *"**These three** had no heading of their own until
2026-07-26."* The section heading says **four** ways, and four numbered entries follow — so the
count was **already stale in the pre-change file**, having gone wrong when a fourth entry was added.

It is neither a criterion (no reader must meet it) nor evidence of an observation (it describes the
document, not an incident). It is a stale self-description, and the rule file's own disposition for
a stale absolute that a later change will move again is **removed rather than updated** — updating
it to "four" merely resets the timer until a fifth entry lands. The paragraph's substance is
preserved in CB § "Why this became its own section", where the sentence now reads *"These entries
had no heading of their own until 2026-07-26"*: the **date is preserved verbatim** as evidence, and
the load-bearing claim (E-276 was bitten twice with the file loaded, because the content was buried
rather than missing) is preserved in full.

Flagged explicitly because silently changing a number inside material being moved is precisely what
the criterion-versus-evidence rule exists to prevent, and a reviewer should be able to rule on this
one call rather than discover it.
