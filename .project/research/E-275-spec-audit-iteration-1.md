# E-275 Spec Audit — Iteration 1 (code-reviewer)

**Date**: 2026-07-27
**Auditor**: code-reviewer (spec-audit mode, not code review)
**Targets**: `epics/E-275-classifier-hardening/epic.md`, `E-275-01-legion-precedence-and-ambiguity-flag.md`, `E-275-02-constant-tripwire-and-fixture-pack.md`

> *(PM note, 2026-07-27 — the second target was **renamed** to `E-275-01-narrow-legion-precedence-fix.md` by the later trim pass, when the observability flag was cut to IDEA-213. **The old name above is left standing deliberately**: it records what this audit examined, under the name it had. Same file, same content at audit time — only the path moved. Follow the new name.)*
**Verdict**: **NOT READY** — **14 MUST FIX (F1–F14), 13 SHOULD FIX (S1–S13)**

> **Revision 3, 2026-07-27.** **F14 added** from the outside re-check of the six "already fixed" dispositions (table at the end of §2). That re-check found five genuinely resolved — three better than proposed — and one not: **F10's TN-4 half**. F14 is that residue.
>
> Count history, since this line has now been wrong twice and both misses were mine: original "11 MUST FIX, 12 SHOULD FIX" → corrected to 13/13 when F12/F13 were added → now **14/13**. The body always enumerated S1–S13. **The body is authoritative over any count line, including this one — re-derive it, do not re-read it.**
>
> **F1 claim 1 is REFUTED** — see the struck block in F1. F1 claim 2 stands. F12 and F13 are routed OUTSIDE this epic (IDEA-211, claude-architect) and neither blocks E-275 READY.
>
> **Blocking set for READY**: F1 (claim 2 only), F2, F3, F4, F10, F11, **F14**.
>
> ⚠️ **This file has more than one writer.** An edit on 2026-07-27 reported the file as modified on disk since my prior read. Anything below not in code-reviewer's voice is someone else's, and a section that contradicts another was probably edited by one of us and not the other — check both before trusting either.

All locations are anchored by heading / AC number / symbol. No line-number citations, deliberately.

---

## 0. Read this first — three framing items

### 0.1 The draft I audited vs. the revisions the brief describes — ARTIFACT WINS, and it conflicts

The brief told me PM has been editing: *"AC-7 annotation, SE's verbatim figures, api-scout's corrected provenance, an idea renumber."*

**None of those have landed in the epic directory.** Checked directly:

- `epic.md` last modified 2026-07-26 23:24:34
- `E-275-01…md` last modified 2026-07-26 23:25:33
- `E-275-02…md` last modified 2026-07-26 23:26:17

All three predate every read in this audit. There is no AC-7 annotation on disk, no SE verbatim-figure insert, and the corpus provenance in `epic.md` is still the pre-correction form. `IDEA-172` and `IDEA-178` are still at those numbers and both stories still cite them, so no renumber has landed either.

**So: this audit is against the CURRENT state of all three files, not a superseded draft.** Nothing here is a ghost. If PM has revisions in flight that are not yet written, they need to land before iteration 2, and any finding below that a pending revision already fixes should be closed by pointing at the landed text — not at the intent.

**However — the surrounding evidence base HAS moved, and it is decisive for two findings.** These landed after the epic was written and are untracked or modified in the worktree:

- `.claude/agent-memory/api-scout/proxy-corpus-team-name-sample.md` — **NEW**. This is the citable corpus provenance OQ-4 asks for. It exists now, and **it explicitly corrects a figure the epic pins.** See F10 and F11.
- `.project/ideas/IDEA-203-api-docs-prescribes-sentinels-the-pii-gate-blocks.md` and `IDEA-204-agent-memory-holds-real-identifiers-outside-gate-coverage.md` — **NEW**. Directly bear on TN-17. See F1.
- `IDEA-198` through `IDEA-207` — the Non-Goals captures. The epic references these as "captured as ideas" but cites no numbers.
- `.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md` — modified 00:14; I read it at its current state.

The epic cites **none** of these new artifacts.

### 0.2 Verification basis — how to triage each finding

Per the brief, every finding below is tagged:

- **`[SPEC]`** — verified entirely by reading spec artifacts, memory files, and idea files against each other. PM can act on these directly. No code behavior is asserted.
- **`[SPEC+STRUCT]`** — verified by reading spec artifacts plus a *structural* fact about the source (a symbol exists; an enumeration has N members; a literal appears in a config set). No behavioral claim. PM can act.
- **`[NEEDS SE]`** — the finding rests, in whole or part, on what the code *does*. **PM must not act until SE confirms by execution.** I did not conclude behavior from reading, and nothing below asks PM to trust that I did.

Count: 19 `[SPEC]` / `[SPEC+STRUCT]`, 4 `[NEEDS SE]`.

### 0.3 Criteria vs. evidence — applied before flagging any figure

Per the brief I sorted every number I touched by whether the reader must **MEET** it (criterion — correct it) or **SEE what was observed** (evidence — preserve it, correcting it destroys a record).

**Classified EVIDENCE and deliberately NOT flagged:**

- **TN-4's `14`** (the seniors/juniors-token denominator, `8 seniors / 2 Senior / 4 Junior / 0 juniors`). This records what was observed against coach's stated 30-50 floor. It is the load-bearing evidence for "the falsifier cannot be run." Correcting or sweeping it would destroy exactly the record TN-4 exists to preserve. **Leave it.**
- **AC-7's `14U → youth_travel` value.** Per the brief, coach has ruled this is evidence of today's precedence behavior, not an endorsement of the value as domain-correct. My F6 fix therefore **adds** a row and does **not** touch the recorded 14U value or its expected label.
- **The fixture pack's Tier 1 rows generally** (E-275-02 AC-4/AC-6). AC-6 already encodes the right rule ("expected label is the human-certified label, not the current output; where they differ the row belongs in Tier 2"). I found nothing to flag here.
- **TN-11's seed citations `:368` and `:523`.** These record what the *seed* claimed and are the evidence of its falsification. Do not re-anchor them; they are supposed to point at the wrong place.
- **`0 of 563`** in Background and TN-9. Observed result. Preserve — but see F11 for the bound that must accompany it.

**Classified CRITERION and flagged:** the `12 capture sessions` provenance (F11), AC-9's `14` (F10), TN-7's AC pointer (F2), TN-8's and TN-4's source pointers (S10), AC-5's TN-16 citation (F7).

---

## 1. DIRECT ANSWER — the seniors/juniors role-flip hunt

**NO. I found no surviving stale `seniors`/`juniors` fail-first expectation anywhere in the epic or either story.**

This is a confirmed absence, not an unexamined one. What I actually did:

1. Swept all three files for `four` / `seniors` / `juniors`, case-insensitively, and **read every hit in full** rather than judging from the match line.
2. Checked each hit's role: is this a *count of the pattern list* (legitimate — there are four Legion-family patterns) or a *claim about what moves* (would be stale)?

Result, hit by hit:

- `epic.md` **TN-1** — *"four Legion-family patterns"* is a list count, correct against `_LEVEL_WORD_PATTERNS`, and is immediately followed by *"**Exactly two entries move**: `american legion|legion` and `post \d+` … `seniors` and `juniors` stay where they are, behind `varsity`."* Correct.
- `epic.md` **TN-11 item 2** — *"'Three Legion patterns.' There are four."* Same list count, correcting the seed. Correct.
- `epic.md` **Background** — *"under both the original four-pattern move and the narrowed two-pattern move"* — explicitly contrasts the two, does not assert the four. Correct.
- `epic.md` **Non-Goals** — *"Promoting `seniors`/`juniors`. Deliberately excluded on evidence; see TN-3."* Correct.
- `epic.md` **Overview item 3, Success Criteria bullet 1, TN-3 heading and body, TN-5** — all consistent with the two-pattern narrowing.
- `epic.md` **Non-Goals, "the four adjacent MINORs from the seed"** — a different four (the MINOR count). Not a false positive.
- `E-275-01` **Context** — *"**Two patterns move, not four.**"* Correct, and it names the amendment.
- `E-275-01` **AC-4** — carries an explicit role-flip warning: *"**These two rows changed role** from CHANGE to GUARD when the ruling narrowed; do not inherit a fail-first expectation for them from any earlier list."* This is the strongest form of the fix and it is present.
- `E-275-01` **DoD** — the CHANGE list is `AC-1, AC-2, AC-8, AC-9, AC-10, AC-11`. AC-4 (the seniors/juniors row) is correctly in the GUARD list. No stale fail-first expectation.
- `epic.md` **OQ-3** — explicitly names the role change as a thing SE must re-confirm.

**Conclusion: the highest-risk defect you asked me to hunt is not present.** The narrowing was propagated completely, including to the two places most likely to be missed (the DoD's CHANGE/GUARD split, and the AC-4 body).

One adjacent observation, not a defect: AC-4's sentinels use the **plural** forms (`"Trandive Seniors Varsity"`, `"Vaskeld Juniors Varsity"`), which is correct — the patterns are plural-only. api-scout's new corpus note finds the singular `Senior Legion` attested and the plural `juniors` entirely unattested, and concludes *"the problem with `seniors`/`juniors` is the patterns themselves, not their POSITION in the list."* That sharpens TN-3's argument and is captured in IDEA-205/IDEA-206. See S13.

---

## 2. MUST FIX

---

### F1 — TN-17's binding constraint rests on an unconfirmed seed claim and states a false gate behavior
**Severity**: MUST FIX
**Location**: `epic.md` → TN-17 ("Sentinel naming — binding constraint"); echoed in both stories' **Notes** sections
**Criterion**: 4 (Technical Notes completeness) — and prose-with-behavior
**Basis**: `[SPEC+STRUCT]`

> ### ⛔ CLAIM 1 IS REFUTED — struck 2026-07-27, kept as a record rather than deleted
>
> **PM2 refuted claim 1 and PM2 is right. I was wrong.** Struck in place rather than removed, because *why* it was wrong is the most useful thing in this audit.
>
> **What I did**: concluded a gate's behavior from `SKIP_PATHS` (a literal that governs only the **pattern scanner**) plus a rule file. **I never opened `.githooks/pre-commit`.** I have since read it, and it refutes me:
>
> - `core.hooksPath` is set to `.githooks`, and `.githooks/pre-commit` is present and executable — the hook is wired and live.
> - After the pattern-scanner pass, under `--- doc-PII byte-gate over the planning trees ---`, it builds `GATE_TREES` by **literal prefix-match of every staged path against `epics` and `.project`**, snapshots the INDEX via `git checkout-index --ignore-skip-worktree-bits`, and runs `scripts/check_doc_pii.sh` per staged tree. A non-`0`/non-`3` exit sets `BLOCKED` and the commit fails.
> - It carries the counter check PM2 described: *"A gate that never ran is INVALID, not a pass"* — if `GATED` ≠ the number of staged trees, it blocks.
> - The hook's own comment states the division of labour: *"The pattern scanner skips epics/ and .project/ … The byte-gate greps them for literal known identifiers instead."*
>
> So **`epics/**` IS gated at pre-commit** and TN-17's sentence is substantially true. My first source was correct and about a different mechanism; my second source was stale (see F12).
>
> **This is the exact defect class this epic exists to fix**, committed inside the audit whose job was to find it: I resolved a behavioral claim against documents instead of the executable. Had my suggested fix landed, TN-17 would have read *"a real identifier here is caught by nobody — author discipline is the only control"* — false, and false in the more alarming direction, which is the direction that gets challenged least in a safety note.
>
> **What survives, relocated rather than withdrawn** — the direction-of-error point was right, the mechanism was not. The gate catches only identifiers already on the curated denylist, and it exits `3` (INCONCLUSIVE) in example mode, which is **non-blocking**: the hook prints `[doc-pii: INCONCLUSIVE — example mode]` and falls through to `exit 0`. **A novel real name is caught by nobody.** TN-17 must state both halves. PM2 reached this independently and has already applied it.
>
> **New residual from re-reading the hook — see F13**, which is the same "a check that RAN is not a check that WORKED" shape one layer out.

**Description (original text, superseded in part — claim 1 struck above, claim 2 stands).** TN-17 makes two claims, both load-bearing, both wrong or unconfirmed.

*Claim 1 — the gate covers `epics/**`.* ~~TN-17 says: *"Epic and story files live in a gated tree (`epics/**`), so a real identifier blocks the planning commit rather than surfacing at review."* This is false.~~ **REFUTED — see the block above.** The two sources I cited were:

- `src/safety/pii_patterns.py` → `SKIP_PATHS` contains the literal `"epics/"` and `".project/"`. **Still true — and it governs only the pattern scanner, not the byte-gate. This never supported the conclusion I drew from it.**
- `.claude/rules/pii-safety.md` states in prose that the doc-PII byte-gate is *"scoped to `docs/api/` only"* and that identifiers in planning artifacts *"rest solely on author discipline."* **Stale — the hook has moved past it. See F12.**

*Claim 2 — the standard taxonomy is unsafe here.* TN-17 declares the `Anytown`/`Springfield`/`Example` taxonomy *"NOT safe here"* because *"the doc-PII byte-gate has already blocked that class of sentinel once."* Two problems:

- `.claude/rules/pii-safety.md` instructs the **opposite** for this exact tree: *"When authoring `.project/**` or `epics/**`, never paste real names or identifiers — use the placeholder taxonomy in `.claude/rules/api-docs.md`."* TN-17 overrides a rule file without authority to.
- The "already blocked once" claim traces to **the seed**. The new `IDEA-203` records its provenance as *"Per the E-275 spec seed"* and lists as its first blocker: *"**Confirm the premise.** The seed is a relay and was found to carry five other claims that did not survive checking. **Nobody has reproduced the block against the prescribed taxonomy specifically.**"*

So the epic writes TN-11 ("five seed claims falsified — do not restore them") and then rests a binding constraint on an unfalsified-but-**unconfirmed sixth seed claim**, stated as established fact. IDEA-203 also notes the right diagnostic (*run `check_doc_pii.sh` against a file containing the prescribed placeholders and read the exit code — do not read the denylist*), which nobody has run.

**Suggested fix.** Keep the ACTION — invented sentinels are strictly safer than the taxonomy and cost nothing. Fix the rationale:

1. ~~Replace claim 1 with the true one: *"`epics/**` and `.project/**` are in the PII scanner's `SKIP_PATHS` and outside the doc-PII byte-gate's `docs/api` scope. A real identifier here is caught by nobody — author discipline is the only control. Hence invented sentinels."*~~ **WITHDRAWN — this proposed sentence is FALSE. Do not apply it.** The correct replacement states both halves: *"`epics/**` IS gated at pre-commit — `.githooks/pre-commit` runs the doc-PII byte-gate over the staged planning trees. But the gate matches only identifiers already on the curated denylist, and it is non-blocking in example mode, so a NOVEL real name is caught by nobody. Hence invented sentinels."* PM2 has applied this.
2. Downgrade claim 2 to its actual epistemic status and cite the capture: *"The seed reports the byte-gate blocking a sentinel of the `Anytown`/`Springfield` class; that report is unconfirmed (IDEA-203). We use invented tokens because they have no collision surface at all, not because the taxonomy is known-blocked."*
3. Cite `IDEA-203` and `IDEA-204` from TN-17 so the reader reaches the open question instead of a false certainty.
4. Route the "should the taxonomy change?" question to **claude-architect** — IDEA-203 already assigns it that domain.

---

### F2 — TN-7's PENDING marker points at the wrong AC
**Severity**: MUST FIX
**Location**: `epic.md` → TN-7, final line of the PENDING blockquote
**Criterion**: 4, 6
**Basis**: `[SPEC]`

**Description.** TN-7 closes with: *"It is marked here and in **E-275-01 AC-9** so it cannot be missed at review."*

The pending AC is **AC-12**. AC-9 is the observability over-broad-trigger guard and carries no pending marker of any kind. A reviewer following TN-7's own pointer lands on an AC with nothing pending, concludes the finalization already happened, and AC-12 ships unresolved — which is precisely the failure TN-7 was written to prevent.

**Suggested fix.** `E-275-01 AC-9` → `E-275-01 AC-12`. And after F3 lands, make it name all three locations.

---

### F3 — AC-12 is scoped to artifacts that do not exist in its own story, and story 02 carries no pending marker at all
**Severity**: MUST FIX
**Location**: `E-275-01` → AC-12; `E-275-02` → entire file
**Criterion**: 2 (dependency correctness), 6 (interface definitions)
**Basis**: `[SPEC]`

**Description.** Two coupled defects.

*First*: AC-12 reads *"No **fixture row's** post-fix league requires strictly less rest than its pre-fix league, at any pitch count."* The fixture pack is built in **E-275-02**, which is `Blocked by: E-275-01`. At E-275-01's Definition of Done there are **zero fixture rows**, so AC-12 is vacuously satisfiable in the story that owns it. The story cannot verify its own most safety-critical AC.

*Second, and this is the drop mode you asked me to check for*: **E-275-02 contains no pending marker, no reference to TN-7, and no AC carrying the safety property.** Its "Context files to load" lists TN-6, TN-9, TN-10, TN-11, TN-16, TN-17 — TN-7 is absent. So the property's marked locations are: TN-7 itself, AC-12's text, epic Success Criteria bullet 5, and the E-275-01 DoD line. **All four sit in the epic and story 01. The story that actually builds the fixture rows has none.**

Resolve TN-7 in its marked locations and the pack — the thing the property is *about* — is left unconstrained, with nothing red to show for it.

**Suggested fix.**
1. In E-275-01, re-scope AC-12 to that story's own outcomes: *"No name's post-fix league requires strictly less rest than its pre-fix league, at any pitch count"* — verifiable against AC-1 through AC-7.
2. Add the fixture-row-scoped form as a new AC in **E-275-02**, carrying the identical `(scope PENDING — see TN-7)` marker.
3. Add TN-7 to E-275-02's context-files list.
4. Update TN-7's closing line (see F2) to name all three: TN-7, E-275-01 AC-12, E-275-02's new AC.

---

### F4 — The safety universal is stated at three different strengths in three places
**Severity**: MUST FIX
**Location**: `epic.md` → Background ("Why the reorder is still worth doing anyway"); TN-3, second paragraph; TN-7
**Criterion**: prose-with-behavior; two-strengths-in-two-places
**Basis**: `[SPEC]` for the inconsistency itself; **`[NEEDS SE]`** for which strength is correct

**Description.** The same safety property appears at three strengths, one of them marked pending and two not:

| Location | Strength |
|---|---|
| **TN-7** | PENDING. Explicitly not established across all exclusion axes. |
| **TN-3 ¶2** | *"`legion` requires equal-or-more rest than `nsaa_varsity` at every pitch count, so even a wrong promotion fails toward over-rest — a bench day, not an arm."* Unqualified. |
| **Background** | *"the failure direction is confirmed safe."* Unqualified. |

What was actually certified, per `e275-classifier-hardening-rulings.md` (RULING 4 AMENDMENT): *"PM and SE have since confirmed by measurement that `legion` requires equal-or-more rest than NSAA Varsity at every pitch count and strictly more at three bands (46-50, 61-70, 81-90) plus the top tier pre-April."* **That is a rest-tier-axis result.** It says nothing about the consecutive-days axis, which is exactly what TN-7 flags as unreported.

TN-3 is not decorative here — it is load-bearing for a ruling. Its entire structure is *"the safety-direction argument no longer carries, so signal reliability is the sole surviving basis,"* and TN-3 opens by instructing future authors *"Do not write the safety-direction argument here; coach has retired it for this purpose."* **If the consecutive-days axis diverges, the safety argument is not retired and TN-3's instruction is wrong.** TN-3 currently asserts as settled the very thing TN-7 marks pending.

**Suggested fix.**
1. TN-3 ¶2 → *"…at every pitch count **on the rest-tier axis** (SE's measured curve). The consecutive-days axis is OQ-1 and could change this — see TN-7."*
2. Background → *"the failure direction is confirmed safe **on the rest-tier axis**; see TN-7."*
3. TN-7 then updates three co-located statements rather than one, and OQ-1's resolution has a complete blast radius.

**`[NEEDS SE]` — the execution question, which I did not answer and PM must not treat as answered.** The consecutive-days rule reads `_NSAA_CONSECUTIVE_DAYS_MAX_APPEARANCES` and `_NSAA_CONSECUTIVE_DAYS_WINDOW`. Structurally, the code using them sits inside `_is_excluded` — the single generic exclusion gate — rather than inside a league branch, and `_is_nsaa_excluded` is only a wrapper that passes `get_nsaa_rules(...)`. That **structure** suggests the axis is league-independent and that OQ-1 resolves "the universal stands as written." **I am not asserting that. SE must execute it.** The constants are `_NSAA_`-named while apparently applying to a `legion` resolution, which is exactly the shape that reads one way and behaves another — and this epic exists because four such claims read as plainly true and were false. Even if OQ-1 resolves "stands," TN-7 should still pre-write the diverging branch's text, per its own instruction that the scoping be explicit rather than achieved by deletion.

---

### F5 — Three ACs in story 01's fail-first list are structurally incapable of failing first
**Severity**: MUST FIX
**Location**: `E-275-01` → Definition of Done, second checkbox; and the section header *"The observability flag (all DISCRIMINATE — no such record exists today)"*
**Criterion**: 1 (AC testability), fail-first discrimination
**Basis**: `[SPEC]`

**Description.** The DoD requires: *"Every CHANGE row (AC-1, AC-2, **AC-8, AC-9, AC-10, AC-11**) demonstrated to FAIL against pre-change code — a fail-first demonstration, not an assertion that it would fail."*

Three of those six cannot be demonstrated:

- **AC-9 asserts an ABSENCE.** *"…then no record is emitted."* Against pre-change code no record is emitted for **any** name, because the feature does not exist. AC-9 passes trivially pre-change. There is no implementation of it that fails first. It is a GUARD on the new flag's *precision*, not a CHANGE row.
- **AC-10 is vacuous pre-change.** *"Given any name **that emits the record**, the league returned is identical to what is returned with logging disabled."* Pre-change the antecedent is never satisfied, so the conditional holds vacuously. It can only be made to fail first if its test *also* asserts emission — which is AC-8's job, not AC-10's. As written, GUARD.
- **AC-11 is a docstring correction** with no executable. A fail-first *demonstration* (as distinct from verification) would require a test asserting docstring content, which nothing in the story asks for and which would be brittle against any rewording.

The section header is what produced this. *"All DISCRIMINATE — no such record exists today"* is true of AC-8 and **false of AC-9 and AC-10 for the very same reason**: absence-of-feature makes an emission assertion discriminate and an absence assertion vacuous. One sentence, opposite consequences.

**Suggested fix.**
1. Split the flag section into CHANGE (AC-8) and GUARD (AC-9, AC-10) subsections, each GUARD naming the wrong implementation it catches — AC-9: an over-broad trigger firing on Legion-token-only names; AC-10: a flag wired as a resolution branch rather than a log.
2. Narrow the DoD CHANGE list to **AC-1, AC-2, AC-8**.
3. Give AC-11 its own DoD line with the correct verification mode: *"AC-11 verified by reading the corrected docstring against the defect TN-13 states"* — inspection, explicitly not a fail-first demonstration.

---

### F6 — AC-7's 17U row cannot fail under the wrong implementation it names
**Severity**: MUST FIX
**Location**: `E-275-01` → AC-7
**Criterion**: 1; GUARD-row decoration
**Basis**: `[SPEC]` for the discrimination analysis; **`[NEEDS SE]`** to confirm the resolved values

**Description.** AC-7's stated purpose: *"**Catches**: an implementation that moves Legion matching ahead of the age-bracket ladder, punching through the bracket floor."* It carries two rows:

- `"Wexlom 14U Legion Varsity"` → `youth_travel`. Under the named wrong implementation the name-word path would yield `legion` instead. **Different value — discriminates.**
- `"Quorrin 17U Post 41 Varsity"` → `legion`-by-bracket. Under the named wrong implementation the name-word path yields **`legion` as well**. **Same value — cannot discriminate**, because the AC asserts only the returned label, not which path produced it.

So AC-7's entire discriminating power rests on the 14U row — which exercises `legion`, not `post \d+`. The AC's own stated requirement, *"Two bracket bins and **both moved patterns** are required,"* is therefore unmet: `post \d+`'s bracket-floor guard is carried exclusively by the row that cannot fail.

**Suggested fix — additive, so the recorded evidence is preserved.** Per §0.3, AC-7's 14U value is evidence of today's precedence behavior and I am not proposing any change to it or to the 17U row's recorded value. Instead:

- **Add** a third row pairing the moved `post \d+` pattern with a sub-legion bracket — e.g. `"Quorrin 14U Post 41 Varsity"` → `youth_travel`. This discriminates (wrong implementation yields `legion`) and closes the `post \d+` gap.
- **Keep** the 17U row, and re-label it in the AC text as **bin coverage, not a guard**, so a future reader does not mistake a non-discriminating row for protection. Alternatively assert the resolution *source* rather than the label, which would make it discriminate — but that is a bigger ask on the implementation.

**`[NEEDS SE]`**: SE should confirm by execution that the three rows resolve as stated, and that the wrong implementation actually produces the divergence I describe for the 14U rows.

---

### F7 — Story 02 AC-5 cites six shape families "in TN-16"; TN-16 does not contain them
**Severity**: MUST FIX
**Location**: `E-275-02` → AC-5; `epic.md` → TN-16
**Criterion**: 4 (Technical Notes referenced by stories must exist and carry enough detail)
**Basis**: `[SPEC]`

**Description.** AC-5 reads *"Tier 1 covers, at minimum, **the six shape families in TN-16** that are implemented today: …"* and then enumerates all six itself.

TN-16's **Tier 1** paragraph is two sentences and enumerates nothing. The only six-member enumeration in TN-16 is the **Tier 2** member list (`18O`/`NNO`; rec-family `Under 13`; `Over 18`; `little_league` ngb; the school ladder; the bare-`seniors` misfire).

Both lists have six members, so a reader chasing the citation lands on a plausible-looking wrong list and the collision is silent. (For contrast, AC-7's *"Members are listed in TN-16"* **is** satisfied — that one points at the Tier 2 list correctly. Only AC-5's citation dangles.)

**Suggested fix.** Move AC-5's six-family enumeration into TN-16 as an explicit Tier 1 family list and have AC-5 cite it; or drop *"in TN-16"* from AC-5 and let the AC own its list outright. The first is better — TN-16 is where a future contributor appending a row will look.

---

### F8 — TN-10's named closure obligation is parked behind a conditional gate with no trigger, no owner, and no acceptance surface
**Severity**: MUST FIX
**Location**: `epic.md` → TN-10; `epic.md` → Dispatch Team
**Criterion**: 2
**Basis**: `[SPEC]`

**Description.** TN-10 opens: *"**This is a specific, pre-identified edit. It must not be lost inside a generic 'CA will assess at closure.'**"* Its deferral rationale then does exactly that: *"the Context-Layer Assessment Gate runs unconditionally at every epic closure and **dispatches claude-architect when a trigger fires**, so this routes the work to a gate that was already going to run."*

The two halves of that sentence are not the same claim. The **gate** runs unconditionally; the **dispatch** is conditional on one of eight triggers being judged to fire. TN-10 names no trigger, no owner, and no artifact that goes red if the sentence never lands. Both stories' DoD and the epic's Success Criteria are silent on it. If no trigger is judged to fire at closure, the obligation evaporates with a green suite and a clean closure.

**Suggested fix.** Give it a surface that can fail:
1. Name the specific context-layer trigger TN-10 asserts will fire.
2. Add an epic **Success Criterion**: *"`.claude/rules/pitch-rules.md`'s NRBL section states the IDEA-178 shadow consequence — that `ngb=american_legion` resolves before the NRBL branch is reachable."*

That converts a routing hope into something checkable at closure without spinning up a fourth dispatch agent, which was TN-10's actual concern.

---

### F9 — The Overview miscounts its own list and states its ordering backwards
**Severity**: MUST FIX
**Location**: `epic.md` → Overview, opening sentence and numbered list
**Criterion**: enumeration completeness; internal contradiction
**Basis**: `[SPEC]`

**Description.** Two defects in the epic's first paragraph.

1. *"**Two hardening changes and one new instrument**, in ascending order of durable value:"* announces **three** items. The list that follows has **four**: the fixture pack, the observability flag, the precedence fix, the tripwire. A missing-member-of-an-enumeration defect in the epic's opening sentence.

2. *"in **ascending** order of durable value"* means the **last** item is worth most — i.e. tripwire > reorder > flag > pack. The Background says the opposite, in bold: *"**The fixture pack and the observability flag, not the reorder, are what this epic is actually worth.**"* The list is in **descending** value order. A reader who trusts the Overview inverts the epic's central reframe — the exact thing Background exists to protect, and the thing the Overview's own next line (*"The value ordering above is deliberate and is not the order the work was originally proposed in"*) tells them to take seriously.

**Suggested fix.** *"Three hardening changes and one new instrument, in **descending** order of durable value:"* — or recount to intent. Either way the ordering word must agree with Background.

---

### F10 — AC-9's "14" is computed under a tier-word set that omits `reserve`, and the corpus breakdown does not partition
**Severity**: MUST FIX
**Location**: `E-275-01` → AC-9; `epic.md` → TN-5, TN-6; `E-275-01` → AC-6; `epic.md` → OQ-4
**Criterion**: producibility of a cited figure
**Basis**: `[SPEC]` — this is an arithmetic/definitional inconsistency across three spec artifacts, no code behavior involved

**Description.** First, the good news on the trap you flagged: **AC-9's `14` is not TN-4's `14`.** It traces to api-scout's breakdown — *"Of the 22 names carrying `legion`/`post N`: 14 carry no tier word at all, 4 a bracket only, 3 `seniors`, 1 singular `Senior`, and 0 `varsity`."* That is Legion-token-only names, which is what AC-9 claims. The two 14s are genuinely different quantities and AC-9 reached for the right one.

**The defect is that the 14 cannot be right as stated, and the epic gives a reader no way to notice.**

The 22-name breakdown sums to exactly 22 (14 + 4 + 3 + 1 + 0) and has **no `reserve` category** — yet the same api-scout artifact reports, separately, *"Five distinct names carry a Legion token together with `\breserves?\b`."* Those five have to be somewhere. Two readings, and the artifact does not settle which:

- **(a)** The five carry `legion`/`post N` + `reserves?`. Then they are inside the 22, the "14 carry no tier word at all" figure is **wrong** (it silently counts `reserve`-bearing names as tier-word-free), and the true Legion-token-only count is somewhere in **9–14**.
- **(b)** The five carry `seniors` + `reserves?` and no hard Legion token. Then the 22 breakdown is intact and the 14 is right — but the five are *school-family* names (`reserve` is a school tier), which would make them **five more instances of the bare-`seniors` misfire**, not one, and would mean TN-6 and coach's entire Legion+Reserve safety analysis were run against a shape (`legion` + `reserves?`) that may not occur in the corpus at all.

Reading (b) is arithmetically seductive — the artifact separately notes that exactly **5** `seniors`-without-a-hard-token names bridge its 22→27 count, matching the collision count exactly. But it contradicts how both TN-6 and the coach ruling characterize the case (*"an actual Legion/Post-N program"*, *"a Legion-named Reserve team"*).

The irony is instructive: api-scout's own artifact carries the warning *"PM's tier set omits `reserve`. The 5 Legion+Reserve collisions are real; they are invisible under PM's framing purely because of that omission"* — and the 22-name breakdown one section earlier appears to make the identical omission, uncaught.

**Why this is MUST FIX rather than a curiosity.** Three things rest on it:
- **AC-9's rationale figure** (is the over-broad trigger firing on 14 names, or 9?).
- **AC-6's guard shape.** Its sentinel `"Morvath Legion Reserves"` is a `legion` + `reserves?` name. Under reading (b) that shape does not exist in the corpus, and AC-6's claim to be *"the one collision shape that actually occurs in the real corpus (5 names, TN-6)"* is false.
- **TN-5's central value claim** — *"the flag fires on the 5 real names … from day one … the only part of this epic that produces new information about the live population."* Under reading (b) the flag still fires on those five (they carry `seniors` + `reserve`, both in the trigger set), so the *count* survives, but TN-6's safety reasoning was applied to the wrong shape.

**Suggested fix.**
1. **Promote OQ-4 to blocking** (see also F11) and route to **api-scout**: re-derive the Legion-token breakdown with an explicit, stated tier-word set that **includes `reserve(s)`**, and state which of readings (a)/(b) holds.
2. Carry the resulting breakdown into **TN-4** so AC-9's figure is producible from the epic rather than only from an agent-memory file the epic does not cite.
3. Once settled, correct AC-9's figure if reading (a) holds, and correct TN-6/AC-6's shape characterization if reading (b) holds.
4. **Do not touch TN-4's existing 14** — different quantity, and evidence (§0.3).

---

### F11 — The epic pins a provenance figure that its own source explicitly corrected and warned against pinning
**Severity**: MUST FIX
**Location**: `epic.md` → Background ("The measurement that reframed this epic"); TN-4, final paragraph; OQ-4
**Criterion**: criterion-class figure, stale against its source
**Basis**: `[SPEC]`

**Description.** The epic states, in three places, that the corpus is *"563 distinct team names drawn from 2,518 raw response bodies across **12 capture sessions**."*

api-scout's new `proxy-corpus-team-name-sample.md` corrects precisely this, with a warning naming the risk:

> **⚠ CORRECTED 2026-07-26 — the provenance is NARROWER than "12 sessions".** I first wrote "12 capture sessions" and **PM nearly pinned that in an operator-facing epic line.** 24 session dirs exist; 12 carry an `endpoint-log.jsonl`; **only 4 store response bodies at all.** … **So the corpus is a TWO-DAY window from four sessions, not a week across twelve. Cite it that way.**

The epic pins the number api-scout says not to pin. The prediction in that warning came true — it just landed in the epic instead of being caught.

This is a **criterion**, not evidence: it is a provenance claim a reader relies on to weigh the epic's central reframe (*"the reorder changes zero of 563 names"*), not a record of an observation. It must be corrected, not preserved.

**Two further items from the same source that the epic omits and should carry**, because they bound every conclusion drawn from the corpus:

- **Contributing sessions**: 4, date range **2026-03-11 to 2026-03-12**. `563` distinct names came from `1,754` JSON-parseable bodies out of the `2,518` stored.
- **Provenance skew**, which api-scout states bounds every conclusion: *"One program's network, one region, captured March 2026"*, with `/teams/{id}/opponents` contributing 313 of the names.

TN-9 asserts *"the real corpus contains no instance of the shape the reorder targets."* That is true of this corpus — and this corpus is a two-day window from one program's network. The epic should say so, not to weaken the finding but because TN-9's whole job is to stop a reader over-reading the pack's greenness.

**Suggested fix.**
1. Replace `12 capture sessions` with the corrected provenance everywhere it appears (Background, TN-4, OQ-4): **563 distinct names from 1,754 JSON-parseable bodies of 2,518 stored, across 4 contributing sessions in a two-day window (2026-03-11 to 2026-03-12).**
2. Add the skew bound to TN-9: one program's network, one region, March 2026.
3. **Cite `.claude/agent-memory/api-scout/proxy-corpus-team-name-sample.md`** from TN-4 — this is the citable form OQ-4 asks for, and it now exists.
4. **Close OQ-4 as resolved** once 1–3 land, or fold it into F10's re-derivation. Right now OQ-4 is also internally contradictory: marked *"does not block"* while saying the figures *"should be confirmed exactly before READY"* — and the confirmation, when run, changes the epic's text. It blocks.

---

### F12 — `.claude/rules/pii-safety.md`'s coverage section is stale against the hook, and the staleness is what produced F1
**Severity**: MUST FIX (outside this epic's scope — routed, not built here)
**Location**: `.claude/rules/pii-safety.md` → §"Coverage footgun — planning/idea/epic artifacts are UNGATED (IDEA-102)", including the heading
**Criterion**: prose-with-behavior; a rule file asserting a gate behavior it no longer has
**Basis**: `[SPEC+STRUCT]` — verified against `.githooks/pre-commit` directly
**Added**: 2026-07-27, after PM2's refutation of F1 claim 1

**Description.** The section asserts *"the doc-PII byte-gate is scoped to `docs/api/` only"* and therefore *"real identifiers — especially MINOR names — in idea/epic/planning artifacts rest solely on author discipline."* Both clauses are now false: `.githooks/pre-commit` gates the staged `epics` and `.project` trees. The section closes by tracking *"the systematic fix (extending gate coverage to planning artifacts)"* as IDEA-102 — **the fix appears to have landed and the rule was never updated**, so IDEA-102 may be closeable.

This is not an abstract staleness. It is what produced F1: a reviewer resolved a behavioral question against this file, got a confident and wrong answer, and nearly wrote it into a Technical Note. The file is loaded on PII-adjacent work, so it is positioned to keep doing that.

**Scope the remediation surgically — most of the section is still true and must not be swept.** Applying the criterion-vs-evidence cut inside the fix itself:

| Clause | Status | Action |
|---|---|---|
| Heading: *"planning/idea/epic artifacts are UNGATED"* | **False** | Correct |
| *"pre-commit `pii_scanner` has `epics/` + `.project/` in `SKIP_PATHS` and cannot regex-detect NAMES"* | **True** | **Preserve** — this is the mechanism that IS still uncovered |
| *"the doc-PII byte-gate is scoped to `docs/api/` only"* | **False** | Correct |
| *"rest solely on author discipline"* | **False as unconditional**; true only for a novel name / example mode | Correct, stating both halves |
| The IDEA-096 incident (a real minor's name in an idea file, caught by Codex) | **Evidence** | **Preserve verbatim** |
| The authoring convention (*never paste real names*) | Still good practice | Preserve |
| *"tracked in IDEA-102"* | Fix appears landed | Re-check and close IDEA-102 if so |

**Suggested fix.** PM2 has filed this as **IDEA-211** and attached it to TN-10 as closure obligation B with a Success Criterion. That is the right vehicle and the right routing (**claude-architect** — context-layer domain). Recording it here as well because the audit is what PM triages from, and because F1's retraction is unintelligible without it. The scope table above is the contribution beyond the idea: a fix that sweeps the whole section would delete a true sentence and an incident record.

---

### F13 — The operator-facing confirmation line does not discriminate a REAL gate pass from an example-mode non-pass
**Severity**: MUST FIX (outside this epic's scope — routed, not built here)
**Location**: `.githooks/pre-commit` → the `INCONCLUSIVE` branch; `CLAUDE.md` → Git Conventions
**Criterion**: a check that RAN is not a check that WORKED
**Basis**: `[SPEC+STRUCT]` — read directly from the hook
**Added**: 2026-07-27, found while verifying PM2's refutation

**Description.** When the byte-gate returns `3` (EXAMPLE MODE — the real denylist is absent), the hook prints `[doc-pii: INCONCLUSIVE — example mode]`, does **not** set `BLOCKED`, and falls through to print **`[pii-hook] PII scan passed.`** and `exit 0`.

`CLAUDE.md` → Git Conventions instructs the operator: *"After committing, verify the `[pii-hook] PII scan passed.` confirmation appears in the output — if it is missing, the safety scan may not have run."*

**That line is printed identically in both cases.** It appears when the gate ran REAL with 0 matches, and when the gate certified nothing at all. The discriminating output — `[doc-pii: REAL, 0 matches]` versus `[doc-pii: INCONCLUSIVE — example mode]` — is printed on the preceding line, and CLAUDE.md does not tell the operator to read it.

The hook's non-blocking choice is deliberate and correct, and its comment says why: *"Blocking here would make a fresh clone uncommittable and the hook would be uninstalled, taking the exit-1 detection with it."* The defect is not the fail-open; it is that **the instrument's evidence that it OPERATED is emitted and then not looked at** — the alarm printed above the summary line nobody reads.

**Suggested fix.** Amend `CLAUDE.md` → Git Conventions to have the operator verify the `[doc-pii: …]` line, not just `[pii-hook] PII scan passed.` — and to treat `INCONCLUSIVE — example mode` as "the byte-gate certified nothing on this commit." Fold into IDEA-211; same domain (**claude-architect**), same root cause, and it should not be a separate piece of work.

**Open operator question, which I could not answer and did not try to route around.** Whether this epic's planning commit is gated in REAL or EXAMPLE mode depends on whether the real denylist is present in the checkout the commit is made from. I attempted to check for the file's *existence* (not its contents) and the `secret-read-guard` hook correctly blocked it. I did not work around the guard. **IDEA-203 makes the same argument independently**: *"reading `secrets/pii-denylist.txt` to find out would pull real identifiers into an agent's context to avoid writing them, which is the wrong trade. The right diagnostic is to run `scripts/check_doc_pii.sh` … and read the exit code and path, not the token."* So: **the operator should read which `[doc-pii: …]` line appears on the planning commit.** That is free, needs no secret access, and settles whether TN-17's "blocks the planning commit" is true in practice here or only in principle.

---

### F14 — TN-4 announces the coincidence dissolved, while the live one is its own denominator
**Severity**: MUST FIX
**Location**: `epic.md` → TN-4, the paragraph beginning *"The 'second 14' is GONE"* and the sentence following it
**Criterion**: false closing generalization; a caveat fixed in one location of two
**Basis**: `[SPEC]`
**Added**: 2026-07-27, from the outside re-check of the six "already fixed" dispositions

**Description.** TN-4 closes: *"the coincidence that made this note necessary has dissolved … So only ONE 14 remains … **there is no longer a numeric coincidence to disambiguate.**"*

AC-9 says the opposite and is right: *"that is now **three** such collisions (two 14s, dissolved when one became 9; and **these two 22s**)."*

**One of the two colliding 22s is TN-4's own denominator** — TN-4's breakdown runs on 22 = hard-Legion-token names; AC-9's 22 = any TN-5 Legion-family token with no tier word; they share 17. The note whose entire purpose is keeping coinciding denominators apart now contains a live coincidence and asserts that none remains.

Second half of the same defect: TN-4 states flatly *"the correct figure is **9**"* with nothing marking that 9 answers **TN-4's** question only. AC-9 warns explicitly that substituting 9 there *"would have transplanted a figure across a definitional boundary."* A reader consulting TN-4 alone — which is what a Technical Note is for — takes away "the number is 9" and commits precisely the error AC-9 was rebuilt to prevent. **The disambiguation landed in the consumer and not in the note that owns the concern.**

**Suggested fix** — three sentences in TN-4, no restructuring:
1. Delete or invert *"there is no longer a numeric coincidence to disambiguate."*
2. Name the replacement where the old one was named: *"The two 14s dissolved; two 22s replaced them — this note's denominator (hard-Legion-token names) and AC-9's (Legion-family, no tier word), sharing 17 members. See AC-9's two-22s block."*
3. Qualify the 9 at the point it is stated: *"9 answers this note's question. It is not AC-9's figure — that one is 22 under different sets."*

**Why this is filed rather than mentioned.** It is the same shape as F2 and F3 — a pointer or caveat fixed in one location of two — which is now the third occurrence in this epic and the shape most likely to survive a re-read, because each location is individually coherent. TN-4's own instruction applies to itself: *"If you are checking a count in this epic, re-derive it — do not re-read it."*

---

### Outside re-check of the six "already fixed" dispositions (2026-07-27)

Verified against the landed text, by a party who did not write the fixes. **Five resolved, three of them better than proposed; one not resolved (F14 above).**

| # | Outside verdict |
|---|---|
| **F2** | **RESOLVED, better.** Three-location table as asked; keeping the wrong old `AC-9` pointer visible as a record improves on my silent correction. |
| **F6** | **RESOLVED, better.** The 17U row's *general* property is stronger than my row-swap; the 16U-adjacent-to-`_BRACKET_LEGION_MIN` guard I did not think of. Arithmetic checked: four rows, three bins, AC says three. |
| **F10 (TN-4 half)** | **NOT RESOLVED — see F14.** AC-9's half is excellent and fully resolved. |
| **F11 (provenance half)** | **RESOLVED, better.** The "honest bound" paragraph exceeds the ask; the self-correction footnote is the right form. |
| **S11 (tense)** | **RESOLVED.** Past tense, three readable anchors. |
| **S13 (substance)** | **RESOLVED, better.** That LEG 3 *predates the corpus work* and *"does not weaken when the misfire count drops"* is the point I missed, and it is what makes the narrowing robust to TN-4's sample-size problem. |

**S6 — my half was wrong, conceded.** PM2 refused my proposed "max_pitches is display-only" comment because TN-8 forbids demoting the cap clause to constants-level color. Correct: my proposal was exactly that demotion, filed one finding after I cited the rule forbidding it. SE's sharper form — the test **name** is itself the adjacent prose — stands.

---

## 3. SHOULD FIX

### S1 — The flag's tier-word list omits `frosh`
**Location**: `epic.md` → TN-5 (trigger definition); `E-275-01` → AC-8
**Criterion**: 1; exhaustive-class enumeration
**Basis**: `[SPEC+STRUCT]`

Both enumerate the tier set as `varsity`, `jv`, `freshman`, `reserve`, `sophomore`. `_LEVEL_WORD_PATTERNS` matches `\bfreshman\b|\bfrosh\b` — `frosh` is an alternate of the same pattern and is absent from the trigger set. A name like `"<sentinel> Legion Frosh"` is exactly the ambiguous shape the flag exists to surface and would not fire.

The epic relays coach's list faithfully (the rulings file has the same five), so this is a question for **coach**, not a relay error. The general point: the flag's trigger is a **new** enumeration being defined by hand against an existing pattern list, and an exhaustive-class claim should be regenerated from `_LEVEL_WORD_PATTERNS` rather than transcribed. (`junior varsity` is covered incidentally, since `\bvarsity\b` matches inside it — that is luck, not design.)

**Fix**: ask coach whether `frosh` belongs; state in TN-5 that the trigger set is derived from `_LEVEL_WORD_PATTERNS` and must be re-derived if that list changes.

---

### S2 — "Three pitch bands" understates the certifying artifact, and matches the source TN-8 forbids citing
**Location**: `epic.md` → Background ("The defect")
**Criterion**: provenance; producibility
**Basis**: `[SPEC]` for the discrepancy; **`[NEEDS SE]`** for the correct figure

Background says `nsaa_varsity` *"requires strictly less rest than `legion` at three pitch bands."* The RULING 4 AMENDMENT says *"strictly more at three bands (46-50, 61-70, 81-90) **plus the top tier pre-April**."* The epic drops the fourth item.

Separately: the comment block TN-8 explicitly forbids citing names **the same three bands and nothing else**. So the epic's figure agrees with the forbidden source and disagrees with the measured one. That is at minimum a provenance smell in the one epic that wrote TN-8 — and TN-8's rule is *"state the mechanism as rest-day requirements only, sourced to SE's measured curve … Never cite the comment block as evidence for a behavioral claim."*

**Fix**: get SE's measured result verbatim, state it with the execution citation TN-7 demands, and make Background match the artifact rather than the comment.

---

### S3 — TN-2's "actively harmful" is a non-summer-only claim stated unconditionally
**Location**: `epic.md` → TN-2
**Criterion**: prose-with-behavior; both sides of a safety trade
**Basis**: `[SPEC]` (internal consistency between TN-2 and TN-6); **`[NEEDS SE]`** to confirm the summer resolution

TN-2 argues that extending the reorder below the varsity boundary *"would be **actively harmful, not merely unnecessary**"* because the sub-varsity resolution is stricter. Per **TN-6**, in the **summer** branch a Legion-plus-sub-varsity name resolves `nrbl`, which TN-6 itself calls byte-identical to `LEGION` — so in that branch there is no rest-day delta and the harm is zero.

The conclusion still holds (TN-15 establishes non-summer as the live shape), but the premise is stated one-sidedly, in a note whose whole purpose is to stop a future reader treating the asymmetry as an oversight. A reader who checks the summer branch and finds no harm has been handed a reason to distrust the note.

**Fix**: *"…would be actively harmful **in every non-summer branch**…"*, with one clause noting the summer branch is label-only per TN-6.

---

### S4 — AC-3 is a weak guard; it names no plausible wrong implementation
**Location**: `E-275-01` → AC-3
**Criterion**: 1; GUARD-row decoration
**Basis**: `[SPEC]`

AC-3's stated catch is *"an implementation that alters summer behavior."* That is not a plausible wrong implementation of a two-entry list move — under both the correct reorder and the most likely wrong one (the front-move AC-5 targets), the summer result is unchanged.

**Fix**: either name a concrete wrong implementation it does catch — e.g. a "fix" implemented as a season-conditional special case inside the varsity branch instead of as a reorder, which is a real thing an implementer might reach for — or fold summer into AC-1/AC-2 as a fifth season value and drop AC-3.

---

### S5 — Story 02 bundles two unrelated changes, and the bundling has a scheduling cost
**Location**: `E-275-02` → whole story; `epic.md` → Stories table
**Criterion**: 3 (story sizing)
**Basis**: `[SPEC]`

The constant tripwire (AC-1–AC-3) has **no dependency on E-275-01**. The fixture pack (AC-4–AC-8) does. Bundling them puts the tripwire behind the entire precedence fix for no reason, and **OQ-2 blocks READY solely for the tripwire** — so the epic's READY gate is currently held by a component that could have shipped independently.

**Fix**: split into two stories, or at minimum state in E-275-02's Technical Approach that AC-1–AC-3 may be implemented before E-275-01 lands, and scope the `Blocked by: E-275-01` dependency to AC-4–AC-8 explicitly.

---

### S6 — AC-1's "literal maximum" is ambiguous between two different `max_pitches`, and the ambiguity is the one TN-8 warns about
**Location**: `E-275-02` → AC-1
**Criterion**: 1 (AC specificity)
**Basis**: `[SPEC+STRUCT]` for the two fields existing; **`[NEEDS SE]`** for which one the exclusion gate consults

There are two `max_pitches` in this module: one on `PitchCountRules` and one on `RestTier`. AC-1 says *"pinned to its literal maximum and rest-tier values"* without saying which.

This matters beyond precision. TN-8 rules that the daily-cap claim is *"dropped **entirely** from the mechanism — not demoted to constants-level color, **because a reader can infer enforced behavior from adjacent prose**."* A test literally named for pinning a "maximum" is adjacent prose of exactly that kind, and it will outlive this epic.

**Fix**: name the field explicitly in AC-1, and require the pin to carry a one-line comment stating that `PitchCountRules.max_pitches` is a display value, not an enforced cap — sourced to SE's execution, per TN-8. **`[NEEDS SE]`**: confirm which field the exclusion gate reads before the comment is written; do not let this comment become the next unverified prose claim.

---

### S7 — Both stories modify the same test module with overlapping content and no rule governs the overlap
**Location**: `E-275-01` → Files to Create or Modify; `E-275-02` → Files to Create or Modify, AC-5; `E-275-01` → Handoff Context
**Criterion**: 5 (file ownership), 6 (interface definitions)
**Basis**: `[SPEC]`

Both list `tests/test_league_detection.py`. The serial dependency (`E-275-02` blocked by `E-275-01`) means there is no write conflict — that part is right. But **AC-5 requires Tier 1 to cover *"the name-word conflict shapes from E-275-01 across all four non-summer season values plus summer"* and *"the bracket-versus-name-word conflict shapes"***, which is AC-1 through AC-7 restated in a different structure.

Nothing says whether the pack **absorbs** story 01's tests or **duplicates** them. Story 01's Handoff Context is vague in the same spot — the pack *"may sample"* the observability record.

**Fix**: state the rule in E-275-02's Technical Approach. Given TN-16's append-only framing and the pack's stated purpose as the durable instrument, absorption is probably right — but that is a call to make explicitly, not to leave to whoever implements second.

---

### S8 — The observability record's shape is unspecified, and it puts real team names into application logs
**Location**: `E-275-01` → AC-8; `epic.md` → TN-5
**Criterion**: 1 (testability); unstated operator decision
**Basis**: `[SPEC+STRUCT]`

Two gaps.

*Testability*: AC-8 requires *"exactly one observability record … identifying the name as ambiguous"* but specifies no log level, so a test cannot assert on it. TN-5's *"match `_log_bracket_season_disagreement`'s contract"* is about the never-change-the-resolved-value contract, not the level.

*Unstated decision*: the precedent function logs the **season**, not the team name. This flag must log the name to be useful, and per TN-5 it fires on real names from day one. So the epic silently introduces real team names into production logs. That may well be fine — team names are already in reports — but given how fastidious TN-17 is about names in artifacts, an epic that binds a sentinel constraint in one note and routes real names to logs in another should say so out loud and let the operator rule.

**Fix**: specify the level in AC-8; add one sentence to TN-5 stating that the record carries the raw team name and that this is an accepted operator decision (or route it to the operator if it is not).

---

### S9 — TN-17's constraint is scoped to the wrong tree for where the pack actually lives, and the target file's local convention contradicts it
**Location**: `epic.md` → TN-17; `E-275-02` → Notes
**Criterion**: 4
**Basis**: `[SPEC+STRUCT]`

The fixture pack lives in `tests/`, not `epics/`. TN-17's rationale is stated entirely about `epics/**` (and see F1 — that rationale is false anyway). Meanwhile `tests/test_league_detection.py` already carries real Nebraska place names and at least one real-sponsor-shaped team name in its existing fixtures. An implementer told to follow surrounding style will do exactly the wrong thing.

**Fix**: state in TN-17 that the constraint binds the pack in `tests/` too; that the surrounding file's existing convention is pre-existing and is **not** the standard; and that it must not be extended. Cross-reference `IDEA-204`, which captures the adjacent gap (agent-memory files hold real identifiers outside gate coverage — the coach rulings file is itself an instance, since `.claude/` is also in `SKIP_PATHS`).

---

### S10 — Line-range pointers that will rot
**Location**: `epic.md` → TN-8 (`:280-290`), TN-4 (`get-public-teams-public_id.md:121`), TN-11 item 4 (`:518`); `E-275-01` → AC-12 (repeats `:280-290`)
**Criterion**: citation durability
**Basis**: `[SPEC+STRUCT]`

These are **criteria** — pointers a reader is meant to GO to. Two of this epic's source citations have already drifted, which is why TN-11 exists.

TN-8's `:280-290` is already slightly off: the comment block starts earlier than 280 and its safety text begins before the cited range.

**Fix**: re-anchor by symbol — the comment block preceding `_SUMMER_SEASON`; `_nsaa_level_from_name`; and the endpoint doc's heading rather than its line.

**Explicitly leave alone**: TN-11's `:368` and `:523`. Those record what the *seed* cited and are the evidence of its falsification — they are supposed to point at the wrong place (§0.3).

---

### S11 — TN-4's "Both references are being corrected" is stale present-tense
**Location**: `epic.md` → TN-4, final paragraph
**Criterion**: accuracy of a status claim
**Basis**: `[SPEC]`

TN-4 says the RULING 4 and IDEA-172 "18-team sample" references *"are being corrected."* **Both already are** — the rulings file carries a dated correction kept as a pointer rather than a rewrite, and IDEA-172 carries a struck-through correction inline. api-scout's new corpus note adds a third, blunter one (*"Do not send anyone there again"*).

A reader takes the present tense as open work and goes looking for it.

**Fix**: past tense, and cite the three anchors so the reader can see the correction rather than hunt for the task.

---

### S12 — Three of the four Open Questions state only one branch
**Location**: `epic.md` → Open Questions (OQ-2, OQ-3, OQ-4)
**Criterion**: 6; resolvability
**Basis**: `[SPEC]`

OQ-1 is the model — TN-7 spells out both outcomes explicitly and says the scoping must be stated rather than achieved by deletion. The other three do not.

The consequential one is **OQ-3**. It asks coach to certify the CHANGE/GUARD matrix **and** SE to re-confirm each row's fail-first direction, and says nothing about what happens if a row fails certification. Given F5 and F6, at least three rows are going to move.

(OQ-3's own premise checks out, incidentally: I verified section-by-section that no CHANGE/GUARD matrix exists in the coach rulings file. The relay was wrong and OQ-3 is right to say so.)

**Fix**: state the disconfirmation branch for each. For OQ-3 specifically: a row that fails certification is re-labeled or dropped, and if a CHANGE row becomes a GUARD the epic returns to DRAFT for AC rework. **OQ-4**: see F11 — it is internally contradictory (*"does not block"* vs *"should be confirmed exactly before READY"*) and its answer, now that the api-scout artifact exists, changes the epic's text. It blocks.

---

### S13 — TN-3 omits the sharper finding its own source now carries
**Location**: `epic.md` → TN-3
**Criterion**: completeness of a Technical Note
**Basis**: `[SPEC]`

TN-3 argues signal reliability from the bare-`seniors` misfire, which is correct. But api-scout's new corpus note reaches a stronger and more actionable conclusion from the same corpus: the `seniors`/`juniors` patterns are **plural-only**, `Senior Legion` is attested only in the **singular**, `\bjuniors\b` is unattested across all 2,518 bodies, and widening to the singular would manufacture four false Legion signals out of four ordinary `Junior Varsity` teams. Its conclusion: *"the problem with `seniors`/`juniors` is the patterns themselves, not their POSITION in the list."*

That is a sharper statement of why the reorder is the wrong lever for these two patterns, and it independently supports the narrowing. It is captured in `IDEA-205` and `IDEA-206`, which the epic does not cite.

**Fix**: add one sentence to TN-3 and cite the corpus note plus IDEA-205/206. This strengthens the ruling rather than changing it — and it means a future reader who wants to revisit the narrowing finds the real reason instead of re-fighting the co-occurrence question TN-4 says cannot be answered.

---

## 4. Verified clean — reporting explicitly

Absences I confirmed by looking, not by not finding:

- **The seniors/juniors role flip** — see §1. Explicit **NO**. Swept and read every hit.
- **TN-13's grep trap is accurate.** Verified by *reading* the docstring: the claim *"Legion-specific words are"* ends one line and *"season-independent."* begins the next, so the literal phrase does not exist contiguously and a phrase grep returns zero against text that is plainly present. TN-13's warning is correct and should stay exactly as written. **Nothing in this report is derived from a grep hit or miss without a read behind it.**
- **All cited artifacts exist**: the spec seed, the coach rulings file, IDEA-172, IDEA-178, `.claude/rules/pitch-rules.md`.
- **All six named tests exist** in `tests/test_league_detection.py`: `test_nrbl_is_distinct_constant_from_legion`, `test_pitch_smart_is_distinct_constant_from_legion`, `test_legion_words_ignore_season`, `test_seniors_14u_is_youth_travel`, `test_14u_juniors_is_youth_travel`, and the Non-Goals' `test_legion_ngb_beats_14u_bracket`.
- **TN-1's structural claim matches the source exactly** — nine entries: four sub-varsity, then `varsity`, then four Legion-family, in the stated order. (Structural read of a list literal; no behavior inferred.)
- **TN-11's claim that the existing constant tests are relative-only** is consistent with what I read, and story 02's framing of why they are insufficient is sound.
- **OQ-3's premise is true** — no CHANGE/GUARD matrix in the coach rulings file.
- **No cross-file test-scope gap.** `detect_league_level` appears in `tests/test_report_generator.py` only inside a docstring, not as an import or call. The two stories' file lists are complete.
- **Sentinels**: `Wexlom`, `Quorrin`, `Trandive`, `Vaskeld`, `Zibbet`, `Morvath`. **None reads to me as a real place, team, or mascot.** `Vaskeld` and `Morvath` have a Nordic/fantasy cast but I could not associate either with a real toponym. No finding — and note that this is exactly the property IDEA-203 argues the *standard* taxonomy lacks.

---

## 5. Routing and sequencing

| Finding | Route to | Note |
|---|---|---|
| F1, S9 | **claude-architect** | TN-17 overrides a rule file; IDEA-203 already assigns the domain |
| F10, F11 | **api-scout** | One re-derivation answers both; the citable artifact now exists |
| F4, F6, S2, S6 | **SE** | `[NEEDS SE]` — execution required before PM acts |
| F2, F3, F5, F7, F8, F9, S3–S5, S7, S8, S10–S13 | **PM** | Spec-internal; actionable now |
| S1, and F5/F6 outcomes | **coach** | Feed OQ-3 |

**Sequencing that matters**: F5, F6 and S1 all change AC content, and OQ-3 asks coach to certify the CHANGE/GUARD matrix. **Hold coach's certification until F5, F6 and S1 land**, or coach certifies a matrix that is about to move — which is the same re-work loop OQ-3 exists to prevent.

**Blocking set for READY**: F1, F2, F3, F4, F10, F11. F5 and F6 block OQ-3 rather than READY directly, but in practice they precede it.
