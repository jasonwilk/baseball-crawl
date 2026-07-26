# E-276 Residue Sweep — the claims the fix falsifies, and where they survive

*Story E-276-05 (claude-architect), 2026-07-26. Written to `.project/research/` rather than the epic
directory deliberately: the epic is archived at closure, and the category-(iii) flags below are
handoffs to agents who are not on this epic's team and may not be spawned for weeks.*

This file is the durable record for story 05 AC-6 and AC-9. It exists because a sweep whose product
is *"what I found and deliberately left alone"* is verifiable only once, by one party, in one
session, if it lives only in a completion message.

---

## What was retired, and therefore what was swept for

Four claims, three of them falsified by the fix and one **completed** rather than falsified:

| # | Retired / completed claim | Status after E-276 |
|---|---|---|
| R1 | *"the post-upsert read makes the health gate UNSOUND … until the fix lands, do NOT cite this gate as protection"* | **Retired** — the defect notice describes a state that no longer exists on game and player-line |
| R2 | *"the health-gate ratio's numerator and denominator MUST be drawn from the same population"* | **NOT false — INSUFFICIENT.** Completed with the temporal clause + the necessary-but-not-sufficient note (TN-10). Deleting it would remove a real invariant |
| R3 | *"a floor ratio guards every grain"* / *"the roster cap is layered under a floor"* / *"the universal floor still applies underneath"* | **Retired on the roster grain only.** That grain ships with NO floor; `MAX_ROSTER_DEPARTURES` is its sole guard |
| R4 | *"bias to refuse throughout"* and its dependants (*"a refused retire self-heals"*, *"grid clutter, never a corrupted stat"*, *"benign"*, *"conservative"*) | **Retired on the roster grain**, where the operator inverted the bias to prefer-delete. These are the **judgement** carriers — several share no token with R1–R3 |

## Method and scope — including where I did NOT look

Three steps per `.claude/rules/doc-sweep.md`, with the retirement-specific step 2 (enumerate the
*judgements that depended on the claim*, not only rephrasings).

- **Step 1 — token grep**: `same population`, `old ∪ fresh`, `health.gate`, `health-gate`, `floor`,
  `extra_guard`, `MAX_ROSTER_DEPARTURES`, `MAX_GAME_RETIREMENTS`, `KNOWN DEFECT`, `fix in flight`,
  `unsound`, `snapshot`, `prior.loaded`, `polluted`, `accumulate.only`, `reconcile`, `retire`,
  `churn`, `blast radius`, `truncated`, `uncapped`, `E-276`, `E-267`.
- **Step 2 — judgement / token-free carriers**: `self-heal`, `self heal`, `re-deriv`, `recoverable`,
  `tunable`, `bias.to.refuse`, `benign`, `conservative`, `irreversible`, `grid clutter`, `clutter`,
  `protection`, `degrade`, `four review layers`. **This step is what found the two hits no
  token grep reaches** (the coach's benign-failure-mode judgement, and the operator runbook's
  "in addition to the shrink ratio").
- **Step 3 — semantic read**: every hit above was opened and read in its section. Nothing below is
  ruled from a grep line.

**Trees swept**: `CLAUDE.md`, `.claude/rules/`, `.claude/agent-memory/` (AC-6's mandated scope), plus
`.claude/agents/` and `docs/` swept **voluntarily** — neither is in AC-6's scope, and the `docs/`
sweep found the most consequential surviving copy of R3/R4 (see F-5).

**Trees NOT swept, so a reviewer knows where I did not look**: `epics/`, `.project/` (PM is running
its own sweep of both at closure), `src/` and `tests/` beyond the specific sites named below
(in-module prose ships inside the grain stories per TN-9), and `.project/archive/` — deliberately
untouched per **AC-8**: the E-267 and E-270 archives are frozen historical records and correctly
continue to carry the original claim.

**Tool note**: the environment's `grep` is ugrep. `grep -rn "a\|b" <multiple paths>` returns EMPTY
with no error. Every invocation above used `-rnE` with one pattern and one path at a time.

---

## (i) CORRECTED — in files this story owns

| Site | What was corrected |
|---|---|
| `CLAUDE.md`, **Canonical reconcile-at-load (retire-absent)** Architecture bullet | The whole `KNOWN DEFECT (2026-07-25 audit, fix in flight)` paragraph is replaced by a description of the shipped behaviour (AC-1). It now separates the **CANDIDATE** population (live read, `old ∪ fresh`, uniform, unchanged and correct) from the **HEALTH-GATE** population (per grain), and states all three grains as they landed rather than smoothing them (AC-3): game + player-line take a caller-supplied pre-upsert snapshot; **roster has no floor gate at all**, with `MAX_ROSTER_DEPARTURES` as its sole guard and less gating than it started with. Ends by stating both sides of the trade — what the correction does **not** buy (one-run guarantee, a refusal still writes, partial churn still retires, the cap is a rate) — so no reader is left either distrusting a working gate or over-trusting it. |
| `CLAUDE.md`, same bullet, "Two invariants that are easy to break" | **AC-2b.** The second copy of the same-population invariant — two paragraphs from its own replacement, in the file every session loads — is **completed, not deleted**: same-population is now stated as NECESSARY but NOT SUFFICIENT, with the temporal clause named as the load-bearing half and *"same population, therefore sound"* explicitly barred (TN-10, AC-2). |
| `CLAUDE.md`, same bullet, "Bias-to-refuse throughout" | A **judgement that depended on R3** and carries none of its tokens. Scoped to game and player-line, with the roster inversion named. Found by step 2, not step 1. |
| `.claude/agent-memory/claude-architect/epic-codifications.md`, E-267 entry, T1/T2 bullet | **AC-5.** The pinned same-population invariant is brought to TN-10's wording in place: as pinned it was satisfied *by the broken code*, so it passed the defect; the completing half is temporal. Also records that the invariant is no longer uniform (roster has no ratio to state one about). The surrounding record of what E-267 codified is intact. |
| `.claude/agent-memory/claude-architect/epic-codifications.md`, "STANDING CODIFICATION CHECK" paragraph | **AC-4.** The *"benign, since dedup would have merged the rows anyway"* ruling is corrected in place as **refuted by execution** (9 live lines hard-deleted), with the three reasons in the epic's order of decisiveness and **ordering named as decisive on its own** — the retire runs *before* `dedup_team_players` by explicit design in both grains, so dedup cannot have merged anything yet. The check itself is extended, because it did not save me from the clause beside it: **a mitigation is a conclusion too**, and *"X would have caught this anyway"* requires establishing that X runs after the harm and can see it. A dismissal is the claim nobody re-opens, precisely because the finding above it was correct. |
| `.claude/rules/python-style.md`, missing-safety-signal rule, **Exclusion** paragraph | **TN-9 row assigned to story 05.** *"…and the universal floor still applies underneath"* is **SCOPED, not deleted**: true on game and player-line, false on roster, where `retire_departed_roster_players` does not call `crawl_is_authoritative` and `extra_guard=None` has nothing beneath it. Evidence is EXECUTED, not reasoned — 13 stored ids / 1 fresh, `extra_guard=None`: **12 classify REMOVED, where the floor made it 0** (re-run by me this story against the shipped code, not relayed). The EVIDENCE-vs-policy-hook distinction and the carve-out itself are untouched. ⚠️ **See the file-list note below — this file is not on story 05's Files list.** |

### ⚠️ File-list discrepancy, declared rather than silently widened

`.claude/rules/python-style.md` is **not** on story 05's *Files to Create or Modify* list, which
names only `CLAUDE.md`, `epic-codifications.md` and this file. TN-9 nevertheless assigns that row to
**story 05** (the row was added 2026-07-26, after the Files list was written), Success Criterion 4
measures "no prose still states the falsified claims (TN-9)" against that inventory, and `.claude/rules/`
routes to claude-architect under the Routing Precedence in `.claude/rules/agent-routing.md`. Story 05
is the last story, so flag-only would leave SC-4 unsatisfiable with no story left to satisfy it.

I made the edit and am declaring it here and in the completion report. If PM rules otherwise, the
edit is one paragraph and reverts cleanly. **AC-6's prohibition is on *silent* widening; this is the
opposite of silent.**

---

## (ii) LEFT ALONE DELIBERATELY — with the reason

| Site | Why it stays |
|---|---|
| `.claude/agent-memory/claude-architect/MEMORY.md`, the per-epic codification index line (E-267 clause: *"health-gate on the FRESH payload with no snapshot table"*) | **Re-checked by reading the literal line, as the story's Technical Approach asked.** Still true post-fix: there is still no snapshot *table* (the snapshot is an in-memory `frozenset` captured by the caller, no migration), and the gate is still a health gate on the fresh payload. It does not restate the retired claim. **No change** — the expected outcome, confirmed rather than assumed. |
| `CLAUDE.md`, *"report deletion AND generation are DESTRUCTIVE"* bullet, and the `reconcile-at-load` mention in the orphan-reclamation bullet | Both are **strengthened** by this epic, not falsified: generation is still destructive via reconcile-at-load, and the retire helpers are still connection-in/no-commit (the named exception the reclamation bullet contrasts itself against). |
| `.claude/rules/data-model.md`, plays *"Never delete-and-reinsert"* rule and its E-267 scoping | The scoping sentence (*"does not bar the E-267 game-grain retire"*) is unaffected by a gate-population change. Accurate as written. |
| `.claude/rules/testing.md` *"absence claim needs proof the mechanism COMPLETED CLEANLY"*, `.claude/rules/worktree-isolation.md` `git checkout --` rule, `.claude/rules/tool-output-integrity.md` E-267 concrete case | E-267-derived rules about **process**, not about the gate's population. Untouched by this fix. |
| `.claude/agent-memory/code-reviewer/ratio_gate_population_claims.md` | A **finding-record** about the E-267-02 numerator/denominator mismatch. Its algebra is correct for the population it names and it asserts nothing about *when* the prior set is read, so E-276 does not falsify it. (It is also CR's own directory — had it needed a change it would be category (iii).) |
| `.claude/agent-memory/data-engineer/MEMORY.md` index hook for the health-gate file | Read in full: it carries the temporal claim and the cap-masks-a-broken-gate claim, both still true, and does **not** carry the retired self-heal / re-derivability reasoning. The index-row position `doc-sweep.md` warns about is clean here. Independently reached by DE-R1's own sweep and confirmed by my read. |
| `.project/archive/**` | **AC-8.** Frozen historical records. The E-267 and E-270 archives carry the original claim and correctly continue to. |

---

## (iii) FLAGGED, NOT EDITED — someone else's file; PM to route at closure

### F-1 · F-2 · F-3 — `.claude/agent-memory/data-engineer/health_gate_prior_set_must_be_temporal.md` (**AC-9**)

**The file was READ ONLY and is unmodified by this story.** It is data-engineer's own memory
directory; under the ownership clause in `.claude/rules/context-layer-assessment.md` and the
own-memory carve-out in `.claude/rules/agent-routing.md`, only the owning agent edits it. Editing it
would fail AC-9.

Verified against a clean read of the committed file on 2026-07-26: **41 lines** (`wc -l`), and each
paragraph below quoted from that read, identified by opening words rather than by coordinates.

**F-1 — the missing cross-reference (structural). Filed as [[IDEA-187]].**
The per-grain paragraph opening **"Where E-276 actually landed (corrected…)"** — the one stating
*"the roster grain gets NO floor ratio at all"* — sits below the midpoint with several substantive
sections beneath it, while the rule, the **"Required wording"** and the recall-deciding
`description:` frontmatter sit at the top **with no pointer down to it**. A recall that stops at the
description learns the rule and not its scope. **This is a pointer request, not a correction
request**; IDEA-187 records it as DE's call, including "not worth it."
*(Dated evidence, not an address: as of 2026-07-26 that paragraph opens at line 21 of 41. Three
positional claims about this one paragraph have now been wrong, each differently — "the bottom",
"the last third", and a stale denominator that rotted when DE legitimately appended below it while
the numerator stayed correct. Verify by opening the file, never by consulting a summary of it.)*

**F-2 — the roster-exemption rationale restates BOTH framings this epic retires. NOT covered by
IDEA-187, and it has no idea file at all.**
The paragraph opening **"Why the roster grain is exempt — the reasoning, because the conclusion does
not travel."** Two clauses of **opposite status**, and this is a **clause-level** edit request:

- **RETIRED** — everything up to and including *"the operator ruled prefer-deleting on that basis"*:
  the re-derivability premise, *"a wrong delete self-heals"*, and the attribution of the operator's
  ruling to that basis. The epic's roster banner names counter-statements for both: V1's pre-existing
  loss is **permanent-while-broken, not self-healing** (re-derivability is conditional on a
  subsequent healthy crawl, and sustained truncation — the deciding input — has none); and
  **re-derivability is not what carries the case** — the load-bearing argument is *which-wrongness*
  (a wrong delete converges on the only evidence available; a strand persists *against* evidence).
  A third, smaller point rides along: *"fully re-derivable"* is unqualified, but only the **row** is
  re-derivable — the delete's downstream effect on the identity graph is not.
- **LIVE, and now independently corroborated** — everything from *"**Do NOT port this to
  `player_game_*`**"* onward. DE's own newer paragraph in the same file measured that transfer
  failing (*"18 rows / 54 AB, a permanent 2× inflation of the query-time season line"*).

**Striking the sentence deletes live, load-bearing guidance; keeping it intact preserves the retired
premise. The split has to be named or one of those two happens.** Note also that the fresh
supporting evidence now sits adjacent to the retired clause, so a reader arriving there is likelier
to read the whole hit as already accounted for — `doc-sweep.md`'s *"error hiding behind a legitimate
neighbouring use"*. The live half got harder to lose and the retired half got harder to see.

**Report it as this, not as staleness**: *a sentence refuted by its own file, four paragraphs down,
in a way no token search connects.* The refuting paragraph is the `MAX_ROSTER_DEPARTURES`-sets-a-RATE
material ending *"The protection runs backwards with respect to severity"* — which is exactly what
makes *"a wrong delete self-heals"* false, and it shares **no token** with the sentence it kills.
That is this project's doc-sweep rule running in **reverse**: the catalogued case is a retired claim
surviving in forms carrying none of its tokens; here it is the **refutation** carrying none of the
claim's tokens, so no grep for the retired claim can ever surface the sentence that kills it.

**This is a re-scoping request, not a challenge to the design.** The conclusion — roster is exempt,
prefer-delete — is what shipped and is correct. Only the stated REASON is retired. A correct verdict
resting on a retired reason passes every *"was the call right?"* check; only reopening the cited
sentence catches it.

**F-3 — retired-prediction residue.** The file carries the *"a guard whose only protection is a
second, **tunable** guard is not a guard"* wording — ancestor of story 03's *"independently-owned
policy constant"*. The *"someone will tune the cap"* prediction was pre-registered as a falsifier and
falsified, so this is **residue**, not a wording discrepancy between two artifacts. Framing matters:
a discrepancy invites a reader to decide which is canonical; retired residue is a claim withdrawn in
one place that survives in another, in a file read cold months later by someone with no thread to
check it against.

**Do NOT characterise any of F-1/F-2/F-3 as "the pre-conjunction form."** The conjunction does not
ship; the baseline is the current TN-10 — one gate per grain, roster with none.

**Why a grep will not surface any of the three**: F-1 is an **absence** (no string to match), F-2 is
a **justification** sharing none of the vocabulary of the sentence that retired it, F-3 is a
**retired prediction** surviving as an adjective.

### F-4 — `.claude/agent-memory/baseball-coach/e267_reconcile_at_load_review.md`, Verdict 3, roster drop-cap bullet

**Found by step 2 (judgement expansion); no token grep reaches it.** The bullet's closing
justification reads *"NOT a blocker because the failure mode is benign (stale grid clutter, never
wrong STATS -- no coach-facing number corrupts, unlike the other two grains)."*

That is the coach-side twin of the *"grid clutter, never a corrupted stat"* sentence TN-9 requires to
be **SCOPED, not deleted**, in `retire_departed_roster_players`' docstring — expressed in entirely
different words, which is why it survived every sweep this epic ran. Under V1 it is **false in the
band régime**: a roster delete can collapse a dedup fork the planner had REFUSED into a mergeable
pair, and the same run's dedup sweep then executes the merge, destroying a stat row on one branch
and silently reassigning one on the other ([[IDEA-188]]).

**The verdict almost certainly survives** — the chain exists in today's code too, and V1 extends its
reach rather than introducing it — so this is *scope the reason*, not *reopen the call*. It is
baseball-coach's own memory directory.

*Adjacent observation, NOT caused by E-276 and lower priority*: the same bullet describes the
conservative default as *"refuse >1-player single-run drop"*, while the shipped
`MAX_ROSTER_DEPARTURES = 2` refuses at **more than two**. That bullet is explicitly a record of a
pre-dispatch DE decision, and this epic changed no cap (explicit Non-Goal), so it is pre-existing
drift, not residue of a retired claim. Mentioned only because coach will be reading the paragraph
anyway.

### F-5 — `docs/admin/operations.md`, "Reconcile-at-Load: Generating a Report Can Now Delete Stale Data" → **Bias to refuse** paragraph

**The most consequential surviving copy of the retired claim, and it is operator-facing.** It reads:

> **Bias to refuse.** A retire happens only when the fresh crawl is corroborated healthy -- it
> fetched successfully, returned a non-empty payload, and did not shrink catastrophically against
> what is already loaded (**the roster grain applies its own stricter absolute cap of two departures
> per run in addition to the shrink ratio**, since a 12-15 player roster tolerates almost no slack).

E-276-03 makes the emphasised clause **exactly backwards**: on the roster grain there is no shrink
ratio for the cap to be "in addition to" — the cap is the **sole** guard, and the bias on that grain
was deliberately **inverted** to prefer-delete. The paragraph's closing reassurance (*"a partial/
degraded crawl never causes data loss"*) is the dependent judgement, and it is what an operator
reads before deciding whether a report run is safe against a degraded feed.

Two things worth recording beyond the fix itself:

1. **TN-9's inventory has no `docs/` row at all**, and neither AC-6's mandated scope nor any other
   sweep in this epic covers that tree. This hit was reachable only because I swept it voluntarily.
   Success Criterion 4 (*"no prose still states the falsified claims"*) would have passed with this
   standing.
2. `docs/admin/operations.md` is docs-writer's file. **Not edited.** It needs a docs-writer
   dispatch at closure; the two other paragraphs in that section (*forward-only, not a repair*;
   *roster departures only reconciled on a load that produced boxscores*) were read and remain
   accurate.

### F-6 — `.claude/agent-memory/product-manager/MEMORY.md` (E-276 entry) and `e276-health-gate-triage.md`

Both describe the defect in the **present tense** (*"reads its 'prior' AFTER the run's own writes —
live uncapped loss on a routine `bb report generate`"*) and record the epic as **READY, NOT
DISPATCHED**. Accurate when written, retired by this epic. PM's own directory and PM's own
closure-time memory work — flagged for completeness, not as a request.

### F-7 — `src/db/reconcile_at_load.py`, `crawl_is_authoritative` docstring, `permit_empty_prior` Args entry (**report-back, not sweep scope**)

Carried into this story by PM from CR's round-2 observation, and outside AC-6's tree (in-module prose
ships inside the grain story that changes the behaviour). The shipped sentence reads:

> No caller derives it from a live read today; **the default protects the next one that does.**

**A stranger's eye, with the mechanism executed rather than reasoned** — this sentence has been false
twice in opposite directions, so I checked the code instead of the argument:

```
prior_count == 0  ⇒  the protected set is empty  ⇒  absent = prior − fresh = ∅
```

Executed against the shipped code: `crawl_is_authoritative(fetch_ok=True, fresh_count=0,
prior_count=0, permit_empty_prior=…)` returns `False` / `True` as documented, and
`classify_absences([], {"x"}, crawl_authoritative=<either>)` returns `{}` **both ways**. So for a
caller whose gate population *is* its candidate population — the single-population live-fed shape CR
had in mind — refusing and permitting delete exactly the same zero rows. **The default protects
nothing there; it forces the next caller to choose explicitly.**

CR's weaker form is the right one, and it needs one qualifier CR did not state: the default *does*
change an outcome for a caller whose gate population **differs** from its candidate population, since
`prior_count == 0` then says nothing about how many candidates exist. Suggested honest floor:

> No caller derives it from a live read today. Where gate population and candidate population are the
> same set, `prior_count == 0` means there is nothing absent to retire and both settings delete
> nothing — so the default is not protection there, it forces the next caller to **choose
> explicitly**. It bites only on a caller whose gate population differs from its candidate
> population, which is exactly the shape whose author most needs to think about it.

Routed to PM as a story-01 prose item; **not edited here** — it is a `src/` site, and per this
story's Handoff Context a stale `src/` prose site is reported, not absorbed.

---

## Three-outcome summary

- **(i) CORRECTED**: 6 sites across 3 files (`CLAUDE.md` ×3 passages, `epic-codifications.md` ×2,
  `python-style.md` ×1 — the last declared above, not silently widened).
- **(ii) LEFT ALONE DELIBERATELY**: 7 sites, each with the reason it is still true or out of scope.
- **(iii) FLAGGED, NOT EDITED**: 7 findings across 5 files owned by data-engineer (3), baseball-coach
  (1), docs-writer (1), product-manager (2 files, 1 finding), and software-engineer's story-01
  surface (1). **F-2, F-4 and F-5 have no idea file and no other durable record**; F-5 is
  operator-facing and reads exactly backwards.
