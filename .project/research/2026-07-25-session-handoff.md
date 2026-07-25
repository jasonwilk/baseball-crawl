# Session handoff — 2026-07-25

State at the end of a long session covering E-272 (shipped), E-274 (planned, DRAFT),
and two defects found by running the classifier against real teams.

---

## 1. E-272 — SHIPPED

Commit `d1af039` — "feat(E-272): season × level → league classification (+ NRBL)".
40 files, epic archived to `.project/archive/E-272-season-level-league-classification/`.
Both closure gates passed: full suite `4207 passed`, Step 1d runtime smoke clean
(`self_games: 0`, reconciliation gate passed, reference date correct).

Delivered: the 18U-Legion misclassification fixed; `NSAA_SUBVARSITY` rest tiers
corrected 0/1/2/3 → 1/2/3/4; NRBL added as a distinct binding league; season made a
first-class classification axis.

**Operator items still open from it:**
- Context-layer ratchet exception — E-272 own +101, inherited +871, total +972.
  Fourth consecutive closure taking an exception; baseline stale since E-262.
- Run the doc-PII byte-gate (agents are structurally blocked from `secrets/**`):
  `PII_DENYLIST_FILE=secrets/pii-denylist.txt scripts/check_doc_pii.sh docs/api`
- **IDEA-137 is ~3× its recorded size** — 17 files carry real identifiers (not 6), and
  42 files carry `<8-hex>-REDACTED` placeholders built from 33 *real* UUID prefixes,
  which `.claude/rules/api-docs.md` explicitly prohibits. Real exposure, not hygiene.
- 9 `docs/api/**` files have uncommitted corrections (api-scout's, from this session).
- Carried from earlier epics: 6 duplicate games awaiting `bb data merge-duplicate-games`;
  E-257 baseline re-snapshot.

---

## 2. Two live defects in shipped code

### IDEA-178 — NRBL doesn't fire when `ngb` is tagged accurately
NRBL follows American Legion regulations, so coaches tag NRBL teams
`ngb = ["american_legion"]`. E-272 made recognized `ngb` authoritative at Priority 2,
above bracket, name and season — so those teams resolve `legion`, not `nrbl`.

Confirmed across four real Reserve teams: the two with blank `ngb` resolve correctly,
the two tagged `american_legion` do not.

Not currently harmful — `LEGION` and `NRBL` are byte-identical curves — but the feature
is inert for accurately-tagged teams, and it becomes a real wrong-table bug if the
curves ever diverge.

**Design settled by baseball-coach; promotable now.** 15U–16U bracket → `nrbl`; else a
summer sub-varsity *name word* → `nrbl` (the rung a bracket-only fix misses); else
`legion` stands. `usssa`/`perfect_game` stay fully dispositive.

### IDEA-179 — unhandled `age_group` shapes fall through to name-matching
`Under 13`, `Over 18` and `18O` match neither `\b\d+U\b` nor the digit-dash-digit range
form, so they fall through to name-keyword matching and can land on an inappropriate
table. All seven school-family values do the same.

~~**Coach ruled but the ruling was not captured before shutdown**~~ — the idle summary read
"Under 13 suppresses, Over 18 stays guideline, 18O binds". ~~**Re-obtain that ruling
before implementing.**~~

> **CORRECTED 2026-07-25 (next session).** **The ruling was never lost.** The
> rec-family and school-family rulings were already durably captured in TWO places that
> predate the claim — `.claude/agent-memory/baseball-coach/league-pitch-rules.md`
> ("ADDITIONAL GAP FOUND 2026-07-25") and
> `.claude/agent-memory/baseball-coach/e274-age-group-level-signal-consultation.md`
> ("Recreational-family under-rest hazard — RULED 2026-07-25") — and the school-family
> half is a shipped AC in this repo at `epics/E-274-.../epic.md` TN-3. The re-consult
> confirmed the fragment verbatim and produced genuinely NEW rulings (travel `18O`,
> `little_league`, USSSA/PG, IDEA-172) with falsifiers, so it was not wasted — but the
> gate it was clearing did not exist. **The memory system worked; the handoff
> misreported it.** E-275 should CITE the two files above for rec/school rather than
> re-derive, and cite
> `.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md` for the new
> travel/`little_league`/USSSA/IDEA-172 rulings.

### New, not yet filed
- **`little_league` is not in `_NGB_MAP`.** It hits the "ngb present but unrecognized"
  branch and returns `unknown` outright, never reaching bracket or name matching.
  Two live teams. Distinct failure mode from the unsupported-but-recognized leagues.
- **`\bseniors\b` misses the `Srs` abbreviation** (one live team).

---

## 3. E-274 — DRAFT, and its value case just changed

`epics/E-274-age-group-level-signal/` — three stories (01 SE, 02 SE BLOCKED, 04 CA).
**Not READY.** Gate remaining: OQ-1 (recognized-`ngb` prevalence, decides whether story
02 exists at all).

Premise: GameChanger's `age_group` is not an age bracket — it is a polymorphic
three-family level field, already on the response the generator parses, at zero extra
cost. The generator fetches it and passes it; only the matcher is blind.

**Vocabulary is now known exactly** (operator supplied screenshots of the create-team
flow, and ~200 probed teams produced zero off-picker values):
- travel: `8U`–`18U`, `18O`
- rec: `Under 13`, `Between 13 - 18`, `Over 18`
- school: `elementary`, `middle_12U`, `middle_13O`, `high_freshman`,
  `high_junior_varsity`, `high_varsity`, `college`

There is **no "Reserve" option anywhere** — confirmed at source. LSB's four
classifications don't map to GameChanger's three HS levels.

### The value measurement — three numbers, all real, measuring different things
- **3 of 73 (4.1%)** — spring HS opponents whose classification changes.
- **4 of 134 (3.0%)** — summer opponents, a disjoint population (OQ-7).
- **46 of 156** — teams in `teams.json` that resolve to `unknown` on the name alone and
  get a card once `age_group` is read. Different question, different population; this is
  the count of *currently-suppressed* cards, not of classification changes.

**The rate is flat across seasons (~3-4%). The mechanism is the argument, not the rate.**

All 3 summer no-level-word teams are **school programs playing summer ball under a
sponsor name** — the name carries neither the school nor a tier, while `age_group` still
reports the true tier. **No name-parsing improvement can ever reach them.** That is the
durable case for the epic: not "more teams", but "a class of team that is structurally
unreachable by the alternative".

**0 of 207 changes move toward less rest**, checked against the rule tables.

api-scout's recommendation is *build*, with an explicit ceiling: single digits per
schedule, value concentrated in cards currently suppressed entirely. Whether that clears
the bar is the operator's call. What the data refutes is shelving it *as redundant with
the name*.

Two cautions from the spring 73 were themselves over-generalisations and are struck:
the anti-correlation claim (TN-10, now scope-marked spring-only; TN-10b carries summer)
and "`season` is constant within the school family" (summer has 13 school-family teams,
so season and `age_group` are independent axes). Both carried do-not-restore markers.

One framing correction worth keeping: **"summer schedule" is a property of *our* team,
not of the opponents on it.** The real axis is sponsor-named vs school-named, which
correlates with summer rather than being it.

### Also worth knowing
- **No structured field can identify an NRBL team.** Four Reserve teams each picked a
  different family to describe themselves. Name inference is permanent infrastructure,
  not a fallback being phased out. That puts weight back on E-263-02c's operator pick.
- A summer team carrying `high_freshman` exists, which refutes the "school family
  implies spring" heuristic the planning team briefly worked from.

---

## 4. Ground-truth data on disk

`teams.json` (repo root, 760 teams) — 51 have a `public_id`; 709 are name-only.
156 resolve to `unknown` on the name alone.

Probe output, with full candidate lists so operator picks can be applied without
re-searching:
- `.project/research/E-274-probe/resolve156.json` — the 156, with `team_hits` per
  ambiguous entry
- `.project/research/E-274-probe/probe_results.json` — the earlier 51-team
  public-profile probe

> **All three ground-truth files are UNTRACKED and deliberately uncommitted**
> (operator decision, 2026-07-25). They are out of the scratchpad and into the repo
> working tree, so scratchpad cleanup no longer threatens them — but they exist on
> **this machine only** and are not in git history. Do not assume a fresh clone or a
> worktree has them, and do not `git add` them without asking.
>
> Reason: `resolve156.json` carries 156 real team names and ~1,460 real `public_id`s,
> `probe_results.json` 51, and `teams.json` 760 names. IDEA-137 exists because exactly
> this class of identifier accumulated in committed files one at a time. The PII
> scanner cannot adjudicate this — it scans credentials/email/phone, **not names**,
> so a clean `[pii-scan]` says nothing about these files.

> **CORRECTION (2026-07-25, next session).** The breakdown below accounts for
> 64 + 46 + 26 = **136 of the 156**. The missing **20 are the `NON_TEAM` bucket** —
> schedule placeholders stored as opponent team rows (`TBD May 16, 2026`,
> `South Tournament`, `TBD- 05/30/26, 3:00 PM`). So the honest denominator for the
> suppressed-card figure is **46 of 136**, not 46 of 156.
>
> Separately and more interesting: **TBD/tournament placeholders are becoming `teams`
> rows at ingestion.** That is an ingestion defect independent of the classifier and
> is not filed anywhere yet — route it to PM for capture.

### Needs operator labelling
- **26 STILL UNKNOWN** — 10 fetched but unresolvable by `age_group`; 8 are USSSA /
  Perfect Game (~~no rules exist~~ — **see correction below**); 2 `little_league`;
  6 not found by search.

  > **CORRECTED 2026-07-25 (next session, baseball-coach Ruling 3).** "No rules exist"
  > is **false**. `.claude/rules/pitch-rules.md` documents both organizations' published
  > regulations — USSSA innings-based, Perfect Game outs+pitches dual-unit — marked
  > *reference data only, not yet implemented in engine*. They are unimplemented because
  > `PitchCountRules` is **pitch-count-only** and structurally cannot express either
  > form, not because the domain has no rules. **Those 8 teams are UNBUILT, not
  > permanently unresolvable** — scoped deferred engineering with a starting point
  > already in the repo. This also explains why E-274 TN-2 treats both as fully
  > dispositive: "a different rule SYSTEM" presupposes rules that exist and differ in
  > kind. Anyone moving to bind these tables needs their own citation pass first —
  > coach did not re-verify the numbers against current published regs.
- **64 AMBIGUOUS** — 19 identical-name collisions across states/years; 45 bare
  town/school names where GameChanger indexes the *qualified* squad
  ("X Varsity", "X Reserve") and the DB holds only the program name.
  **Nine** of those returned the full squad set — one operator judgement each from
  resolving. The nine are not named here (doc-PII gate); they are the entries with a
  populated `team_hits` array in the untracked `resolve156.json`, which is the file the
  operator applies picks from anyway.
- **14 of the 46 resolved** were disambiguated only by a season-year tiebreak among
  identically-named teams. Verify before trusting.
- **Two likely wrong-team hits flagged** — named in the untracked `resolve156.json`
  (`bucket: RESOLVED`, flagged in `resolve156.log`), not here.

---

## 5. Ideas filed this session

`IDEA-168` season-vocabulary drift is silent · `IDEA-169` public-team header divergence ·
`IDEA-170` doc-PII gate cannot see `src/` · `IDEA-171` **PROMOTED** to E-274 ·
`IDEA-172` `\bvarsity\b` outranks the Legion patterns · `IDEA-173` send-cap reset destroys
its own measurement · `IDEA-174` docstring makes an API claim in structural clothing ·
`IDEA-175` consultation prompts should name the team roster · `IDEA-176` `\bsophomore\b`
has no plural · `IDEA-177` surface the level to the coach · `IDEA-178` NRBL/`american_legion`
· `IDEA-179` unhandled `age_group` shapes.

Next: epic **E-275**, idea **IDEA-180**.

---

## 6. Process notes worth keeping

Recorded in E-274's Closure Obligations, marked as surviving an ABANDONED outcome.

**Population mismatch was the session's dominant failure mode — five instances**, every
one a correct number attached to the wrong noun. Two properties visible only across all
five: *a caution propagates further than a number, because numbers get audited and
cautions do not*; and *a do-not-restore marker actively defends the over-generalisation
it is attached to*.

**A green suite and a passing runtime smoke are structurally incapable of detecting an
unreachable branch.** E-272 shipped, passed two closure reviews, a full suite and a live
smoke — and NRBL never fired. What found it was pointing the classifier at nine real
teams whose correct answers the operator already knew.

**A verdict's stated reason can rot independently of the verdict.** Two of six
consultation verdicts had reasons falsified during discovery while the verdicts happened
to survive. Any check asking "is there a verdict for each domain?" passes both. This
applies directly to the eight-trigger closure assessment and the ratchet exception.

**One recorded lesson has a wrong citation.** The Closure Obligations entry reading
"a test that omits the input which triggers the bug is not evidence the bug is absent"
cites SE's inertness test, which in fact ran 28 name/value combinations and did include
team names. Sound lesson, wrong artifact. SE offered a correctly-evidenced substitute
from the same session: it wrote "closed enum sourced from GC's own web bundle" when the
source only said the bundle *enumerates* the school family — upgrading "enumerates" to
"closes" without checking. **Fix the citation before that entry is filed.**

Also: **the database is not a historical record.** "37 reports, all legion/travel" was
read as "no HS report has ever been generated." Reports expire and are cleaned up.
Ask the operator rather than inferring history from surviving rows.
