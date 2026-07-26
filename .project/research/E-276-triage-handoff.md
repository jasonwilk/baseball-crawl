# E-276 — Triage Handoff (PM → successor PM)

> # ⛔ SUPERSEDED — HISTORICAL WORK ORDER. DO NOT CITE ANY FIGURE FROM THIS FILE.
>
> **Marked 2026-07-25 at the fifth-pass edge-walk.** This is a mid-flight handoff snapshot, not a record of what shipped. **The epic is the current spec; this file is the state on the day it was written.** Its MUSTs were executed and its status line (`DRAFT`) is long stale.
>
> **Two figures in it are RETIRED and were corrected in the epic after this was written** — recorded specifically because a reader lifting either would be quoting a number this epic went on to refute:
>
> | This file says | Current truth | Where corrected |
> |---|---|---|
> | *"19 tests, **13 direct `crawl_is_authoritative` calls**"* (MUST-2) | **7 call sites**, across 6 test functions. *(19 tests is right.)* | epic **TN-13** |
> | *"**exactly one assertion inverts** by design"* (MUST-2) | **TWO**, epic-wide — the vacuous-permit inversion **plus** story 03 AC-11's roster test | epic **Success Criterion 2** |
>
> **Why this marker exists rather than an edit to the body**: the body is a historical record and correcting it in place would destroy the evidence that these figures were once believed. **The 13 is itself one of this epic's recorded findings** — a count asserted inside the correction of another count, never measured. **Leave the body; read it through this header.**
>
> **How it was found, which is the transferable part**: an independent edge-walk noticed this file is one of **five** `E-276-*` research artifacts while the epic's banner accounts for only **two** (*"both files should be kept"*). **`.project/research/` sits outside story 05's sweep scope** (`CLAUDE.md`, `.claude/rules/`, `.claude/agent-memory/`), so no sweep this epic runs would ever have reached it. **A retired claim surviving in a sibling of the very directory story 05 is told to write into.**

**Date**: 2026-07-25. **Epic**: `/workspaces/baseball-crawl/epics/E-276-reconcile-health-gate-prior-capture/` — status **DRAFT**, correctly (open MUSTs below).

**Running total**: 24 findings triaged — 21 accepted, 3 dismissed. Sources: DE, SE, SE-2, PM self-audit, CR.

---

## ⚠️ READ FIRST: the CR audit is three rounds stale

The CR spec audit (16 findings, 8 MUST / 8 SHOULD) was written against text superseded by ~16 subsequent changes. **Verify every CR finding against current text before acting on it.** Three of its MUSTs were already fixed when it landed — confirmed by grep, not assumed.

CR itself sent a reconciliation map flagging the overlap; its "likely surviving" list is reliable, its "likely already resolved" list is confirmed resolved.

**CR's PASS list is usable.** It ran ~20 constructions that attempted and failed to break specific claims, and reported them as attempts rather than inspections. Do not re-run those.

---

## DONE — no action needed

- **MUST-1** — TN-10 rewritten for the conjunction (two gates, two populations; each internally same-population). The old wording claimed *"this module never reads its own prior set for the gate"*, which precondition (a) **requires** it to do. Would have shipped a self-contradicting paragraph into CLAUDE.md via story 05. Defect recorded in place, not quietly fixed.
- **MUST-2** — `tests/test_reconcile_at_load.py` added to TN-13 and story 01's file list (19 tests, 13 direct `crawl_is_authoritative` calls). `:144` `test_empty_payload_refused_even_with_empty_prior` asserts exactly what vacuous-permit inverts. AC-12 and SC-2 restated: 72 in the three grain files unchanged, **exactly one assertion inverts by design**.
- **MUST-3** — story 01 AC-5 and TN-2's matching paragraph both corrected. Old wording ("empty prior, short-circuits") was snapshot-only residue; implemented literally it re-opens the TN-3 deadlock.
- **MUST-5** — folded into SC-2: the divergence probes patched only player-line and game; **no roster figure exists**.

---

## OPEN — accepted, decided, not yet edited

| # | Fix |
|---|---|
| **MUST-4(a)** | Scope the Background reachability boundary to the **over-deletion direction**. It is falsified in the churn-inflation direction by the epic's own probe at TN-5's "decisive turn" (`P=10, fresh=8 ⊆ P, live=30` — today refuses, honest permits, **neither stated condition true**). Per CR: the 3-shape characterization must state **which** divergence it counts — observable-outcome, not gate-value — or the tighter number inherits the looser sentence's falsity. |
| **MUST-4(c)** | Put the derivable sizing rule **`a < b ≤ 2 ⟹ pre-load roster ≤ 3`** in **TN-11, beside the fixture table**. Story 03 AC-1's third worked example does not let someone derive a fourth; the rule is what closes the 5-vs-5 non-discriminating-fixture trap. |
| **MUST-6** | Add an AC to stories 01/02/03: the refusal WARN must name **which gate refused** and carry that gate's own population counts. The conjunction adds a fourth refuser; the existing reason cascades (`if not authoritative / elif not boxscores_complete / else <cap>`) will misattribute it. The module already has a ~20-line comment devoted to preventing exactly this class of mislabelled WARN. |
| **MUST-7** | Name the gate-outcome record **type and fields** in TN-11 or story 01's Handoff Context, as an interface 01 produces and 02/03 consume. Three stories require it across three dataclasses in one file; **none defines it**, and 02/03 are unordered (SHOULD-10). TN-17 fixed *reachability*, not ownership of the shape. |
| **MUST-8** | IDEA-186 **tense only** — the blocker was discharged by the loader run. Per CR: **Dependencies, Rough Timing AND Notes each independently assert it is pending; all three must move.** Also de-duplicate the repeated paragraph in the README row. Keep the epic's *abstention* from asserting a mechanism. |
| **SHOULD-9** | Story 02 Technical Approach: strike "to compute the intersection" (4 words). The intersection is REMOVED ENTIRELY per TN-1(b); the rest of the sentence is correct. |
| **SHOULD-10** | Stories 02 and 03 both modify `src/db/reconcile_at_load.py` with **no ordering** — required by `project-management.md`. Also: story 01 AC-9b and story 03 AC-8 both claim the precondition-(d) test; assign it once. |
| **SHOULD-11** | Story 01 AC-4 / TN-12: "the polluted numerator is 10 in both" — it is **11** and 10. Both still clear the floor of 8, so the cases still discriminate; only the number is wrong. |
| **SHOULD-12** | Every story's DoD over-claims fail-before/pass-after. Several required tests cannot (01 AC-3's 9/8 case refuses pre-fix; AC-5; AC-6/AC-8 are new-code tests; 02 AC-5 is a comment; 03 AC-3 is "identical to today"). **Scope the DoD line to the discriminating tests.** |
| **SHOULD-14** | TN-1(a)'s "public snapshot helpers the caller invokes" does not describe the **roster** grain (inline SELECT; story 03 says no loader change). State the exemption. Also unspecified: whether the corrected roster gate reuses `previously_rostered_ids` or takes a new parameter, **and whether the corrected half is exempt-filtered** — currently specified for the legacy half only. |
| **SHOULD-15** | Story 01 sizing: 12 ACs / 5 files, materially largest, never sized. If split, the only safe cut is moving the player-line grain's own tests to a sibling blocked by 01. Do **not** split the primitive out — the epic's sequencing note forbids it. |
| **SHOULD-16** | Epic SC-2's "72" must name its scope (the three grain files). **Partly done** in the SC-2 rewrite; verify no other bare "72" survives. |

### Also open — one new idea to file

`.claude/agent-memory/data-engineer/health_gate_prior_set_must_be_temporal.md` states the invariant in the **pre-conjunction** form ("pass `prior_ids` as a required parameter rather than letting the helper read the DB at call time"). Same superseded framing as MUST-1. **DE is not on the Dispatch Team**, so story 05's AC-6 sweep can only *flag* it — per the deletion-side-eviction ownership rule, only the owning agent edits its own memory. **File as an idea; verify the number by glob (185 and 186 are taken).**

---

## DISMISSED — 3, with checkable reasons

All three: **fixed before the audit ran**. Verified by grep across `*.md` — `507`, `285`, `"under verification"`, `"NOT yet verified through the real producer"` appear **nowhere** in the epic directory or IDEA-186.

1. **MUST-4(b)** — "the epic still carries 222/507/285". Replaced by the derived 3-shape characterization.
2. **MUST-8 (file-level claims)** — IDEA-186's blocker language. Already updated to discharged. *(The tense items remain open above — that part was not dismissed.)*
3. **SHOULD-13** — "the three-instance pattern claim needs a stated scope". **Already bounded**, by the same two attacks CR ran.

### One item taken from inside SHOULD-13

CR's reclassification is a genuine improvement and is **accepted**: instance 2 (`crawl_is_authoritative`'s docstring) belongs under the **stale-contract class already codified in `.claude/rules/python-style.md`** — *"a stale sentence announces itself, a stale default does not"* — rather than under the bounded mechanism. It is falsifiable from inside its own file, so it fits the mechanism only if "artefact" means the sentence, which makes the mechanism near-vacuous.

**This matters because story 05's Notes hand the generalization to claude-architect for codification** — a mechanism fitted to three items that merely rhyme would be codified as a rule.

---

## Still outstanding

- **Codex** was running against the swept text when this handoff was written. **Its findings are not triaged.**
- **CR-2** is working DE's pre-registered falsifiers for the story-03 scope legs. Team lead has ruled in advance: if legs (1) "the cap is a tunable constant someone will change" and (2) "a post-upsert grain is the template the next grain copies" both fall, **story 03 stands on the executed demonstration alone, with the struck legs deleted rather than softened.**
- **Re-sweep** after the remaining edits. The consistency sweep has caught three defects created by edits this session; keep it a separate pass.

---

## ⛔ CR-2 LANDED AFTER THIS HANDOFF — F1 IS A HOLD-THE-EPIC FINDING

CR-2's audit (7 MUST / 7 SHOULD) arrived after the section above was written. It audited **current** text, unlike CR. Its counterexample list is extensive and its PASSes are usable.

### F1 — ACCEPT. The roster-lock fix-neutrality claim is FALSE, and PM's outgoing assessment was wrong.

The epic claims (TN-5 + IDEA-186) that the roster lock is **pre-existing and fix-neutral** — "E-276 neither causes nor worsens it." **CR-2 constructed a counterexample and it holds.** No churn and no truncated crawl required:

```
DB {a,b,c}; cap=2
Run 1  fresh {a,n1}   legacy 2>=2 PERMIT | cap 2<=2 PERMIT | corrected 1>=1.5 REFUSE
       TODAY retires b,c -> {a,n1}        FIX refuses -> {a,b,c,n1}
Run 2  fresh {n1,n2,n3}  TODAY retires a -> clean.  FIX refuses again -> {a,b,c,n1,n2,n3}
Run 3+ steady state, healthy crawl. Both gates PERMIT.
       cap: absent {a,b,c} ∩ previously = 3 > 2 -> CAP REFUSES, FOREVER.
```

**Today's code converges to a clean roster; the fix locks the team-season permanently** — `a,b,c` stranded on the coach-facing grid, and every future genuine departure blocked. H2 restored.

**Why it was missed, and it is this epic's own defect class**: the lock was ruled out for the adopted design by reasoning about the **candidate** population, and never re-checked via the **gate**. The conjunction *adds refusals* → refused rows persist → persisted rows enter the next snapshot → the cap counts them. TN-3 already describes this mechanism; nobody re-ran it against the conjunction. It sits inside the pre-load-roster-of-1-to-3 region the epic itself calls "not an exotic corner."

**It does NOT contradict deletion-neutrality** (TN-5's blanket form is only about never *permitting* what today refuses — CR-2 attacked that five ways and it holds). It contradicts the separate **fix-neutrality** claim about the lock. Keep those apart.

**Required**: retract "E-276 neither causes nor worsens it" from TN-5 **and** IDEA-186; strike "clutter identical to today"; amend IDEA-186's open question *"is the entry condition really a truncated crawl"* — **the answer is no, and this epic creates a route.** Then either add a story-03 AC requiring a three-run test that a conjunction-refused run does not push the next run over the cap, or state it as an accepted residual **with the harm named** (permanent stale roster + all future departures blocked).

### CR-2's other MUSTs — all ACCEPT, all verified against current text

- **F2** — story 01 AC-5 is *still* wrong after PM's MUST-3 edit. The short-circuit is `if not prior_ids: continue` on the **live** read, which is non-empty on a first load, so no short-circuit occurs and the spy assertion fails. PM's rewrite fixed the premise but the "no gate computed" half survives. **Danger**: the obvious repair (`if not snapshot: return`) is harmless at player-line and becomes the template story 03 copies — where it re-opens the TN-3 deadlock.
- **F3** — the player-line scope key omits `table`. The gate is computed per `(block, table)`; batting and pitching are "separate diffs, separate health gates". State it as `(table, canonical game_id, perspective_team_id, team_id)` — **four snapshot sets per game**. Fix in TN-2 *and* the TN-5 ⚠️ box.
- **F4** — AC-6's "the shared authority check implements the vacuous-permit rule" would apply it to the **legacy** gate too, flipping the pinned assertion and making precondition (a) false. Require an opt-in form (keyword or separate wrapper).
- **F5** — TN-13's 9 sites is a **whole-epic** inventory that story 01 cites as its own. Split by story: 01→player-line (1), 02→game (6), 03→roster (2); remove the two grain test files from story 01's list.
- **F6** — `tests/test_reconcile_at_load.py` is in **no** story's Files list. *(PM added it to story 01 — verify it landed; CR-2 may have read pre-edit.)*
- **F7** — **a second copy of the falsified invariant survives in the same CLAUDE.md bullet story 05 edits**: *"the health-gate ratio's numerator and denominator MUST be drawn from the same population"*. Story 05 replaces only the KNOWN DEFECT paragraph, so this sits uncorrected two paragraphs from its own replacement. Add a TN-9 row. Also add `reconcile_at_load.py:591`.

### CR-2's SHOULDs

**S1 is a genuine precondition (e)** — population-**filter** congruence, on an axis outside the four: the exempt filter is applied to the live read but not the snapshot, which makes the corrected gate strictly **looser**. Worked case in CR-2's report. **S2**: the three-shape bound is `S <= 2·cap − 1` — `cap = 2` is that count's space, and the epic argues the cap is tunable. **S3**: name the 2197/6560 sweep *dimensions*, not just their ranges. **S4**: the roster test that actually changes meaning is `test_previously_rostered_ids_scopes_the_cap_population` — a **positive**-property name, so story 03's negative-name grep heuristic misses it. **S5**: AC-6's sweep hits DE's memory dir, which no dispatch-team agent may edit — add DE to the team or route to the main session. **S6**: story 01 AC-4's polluted numerator is **11**, not 10. **S7**: TN-15 is titled a non-goal but absent from Non-Goals; TN ordering is scrambled; stories 04/05 omit `## Handoff Context` without N/A.

### CR-2's failed attacks — do not re-run

Deletion-neutrality (5 ways), DE's whole-set construction, the three-shape bound (re-derived independently), DE's four competing counts (all fit one enumeration `c(n) = (3n−2)(n−1)/2` — the artifact-of-bounds reconciliation **survives**), story 02 AC-4's twin-merge refutation (**holds — do not reinstate the intersection**), TN-17's patch-target table, TN-13's 9 sites, the single `INSERT INTO games`, the pre-fix-false docstring, and all fixture arithmetic except S6.

---

## DE's pre-registered falsifiers — VERDICTS IN. The advance ruling does NOT trigger.

Team lead ruled in advance that if legs (1) **and** (2) both fell, story 03 would stand on the executed demonstration alone with the struck legs deleted. **Only one fell. Leg (2) holds, and is better-supported than its own author expected.**

### Leg 2 — "a post-upsert grain is the template the next grain copies" → **HOLDS**

DE flagged this as its weakest and expected it to fall. It is the stronger of the two, and the evidence is **DE's own prior work, predating this epic**.

`.project/ideas/IDEA-154-per-perspective-game-retire.md` (CANDIDATE, indexed live, filed 2026-07-19 during E-267-02 AC verification) proposes exactly a fourth grain and carries a DE costing note: *"A refused game has NO grain positioned to retire it… this is NOT a small extension of an existing grain — it needs its own retire path with its own perspective-scoped delete surface and its own bias-to-refuse corroboration. Cost it as new work."*

So the "next grain" is a **costed backlog item**, not a supposition — and its gap sits inside `games`/`player_game_*`, the reconcile seam's own territory, **not** absorbed by E-273's reference tier. A future author writing "its own bias-to-refuse corroboration" copies from the three in-tree examples; leaving one of three broken leaves a broken template.

**Precision worth keeping**: three adjacent ideas exist and only one counts. IDEA-146 and IDEA-147 are **refresh** ideas (changed-in-place rows), not retire grains — IDEA-146 says so itself. IDEA-140 is PROMOTED and *became* E-267's game grain. **The surface is open by exactly one documented item.** A looser reading gets this wrong in either direction.

### Leg 1 — "the cap is a policy constant someone will eventually tune" → **FALSIFIED**

`MAX_ROSTER_DEPARTURES = 2` at E-267, E-270 and HEAD; E-267 **locked** it deliberately ("LOCKED as a real spec value… no dangling calibrate-before-dispatch decision"); E-270's only `git log -S` hit is a *reference* addition. Full-tree grep found **no proposal to change the value anywhere**. IDEA-160 proposed a *different, new* cap; **IDEA-186 proposes changing the cap's SCOPING, not its value, and was filed by the claim's own author during this epic's planning** — circular, cannot support it.

**Split the claim, because half survives:**
- *"it is a policy constant"* — **HOLDS** independently (the operator personally set the sibling `MAX_GAME_RETIREMENTS = 2` by explicit decision, 2026-07-21).
- *"someone will eventually tune it"* — **UNSUPPORTED**. A prediction about the future doing load-bearing work in a scope argument, which is exactly what the falsifier was written to catch.

**CR-2's caveat against its own verdict, recorded because it argued against itself**: the observation window is ~5 days and two epics, so *"stable since E-267"* is near-trivially true and the stability conjunct is weak. **The verdict rests on the second conjunct** — after a deliberate lock and one subsequent epic that re-affirmed it unchanged, nobody has proposed moving it. That conjunct is not window-limited.

### What the successor must do

1. **Strike the predictive half of leg 1** from the roster scope justification — delete it, do not soften it. Keep *"dead code masked by a constant that is currently locked"*, which is true and non-predictive.
2. **Keep leg 2 and strengthen its citation** — it now rests on IDEA-154 rather than on assertion. Name the idea.
3. **S2 stands in reduced form**: the three-shape bound is still cap-dependent (`S ≤ 2·cap − 1`, so `S ≤ 3` only because `cap = 2`) — state `cap = 2` as that count's space. **Drop the "and it will be tuned" framing**, which leg 1's falsification removes.
4. Story 03 survives on the executed demonstration **plus** leg 2 **plus** the template argument. Team lead owns the final call.

## Two things worth carrying

**Four of CR's eight MUSTs were framing defects**, in exactly the surface PM had named as where its errors would live ("what is mine and untested is the framing: which properties became ACs, which became Technical Notes, what I judged prominent") — named *before* the audit confirmed it. An argument for asking authors to identify their own weak surface rather than having reviewers guess.

**MUST-2 was the seventh host inside the epic's own success criteria.** `34+20+18 = 72` is exactly the figure inherited from the commissioning handoff and never measured, so the regression frame was drawn around a count over a self-chosen space presented as the whole — two rounds *after* the epic swept itself for that mechanism. It is also the **third defect inherited from the brief**, after the non-discriminating 9-vs-9 roster fixture and the stale symbol claim. **Inherited numbers need their space named as much as authored ones.**
