# E-274: Read GameChanger's `age_group` as a structured level signal

## Status
`DRAFT`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->
<!-- NOT READY: three Open Questions are unresolved (OQ-1 gates story 02, OQ-2 gates the tie-break's
     sizing, OQ-3 is a wording confirmation). See Open Questions. -->

## Overview

GameChanger's `age_group` field is not an age bracket — it is a polymorphic three-family **level** field, and for school teams it names the varsity / junior-varsity / freshman tier directly. The report generator **already fetches it and already passes it into league detection**; only the matcher is blind to the school family. This epic teaches `detect_league_level` to read it, replacing a brittle team-name substring match with a structured signal on the one axis that selects a pitch-count rest table.

The change is one production file. The analysis behind it is large; the code is small, and that asymmetry is deliberate — most of the work was establishing what the field is and which of its values are unsafe to map.

**Read the measured value honestly (TN-10), because the epic's first framing was wrong.** This was drafted as "unlock cards for opponents whose team name carries no level word." api-scout then measured the real population: **0 of 73** school opponents lack a level word, so that case does not exist, and it does not exist for a *structural* reason (the fully-qualified names are exactly the reachable ones). The measured value is **3 of 73 (4%)** — all three cases where `age_group` is right and the **name matcher is wrong**, including one JV team currently misclassified into the **wrong league family**. Zero cases move in the under-resting direction. The honest case for this epic is **correctness and durability against name-matcher brittleness**, not coverage.

## Background & Context

**Promoted from IDEA-171** (`/workspaces/baseball-crawl/.project/ideas/IDEA-171-unmatched-age-group-forms-are-unread.md`), which began as "one unparsed `age_group` form" and was upgraded at E-272 closure to "a structured level signal we already receive and ignore."

`detect_league_level` (`/workspaces/baseball-crawl/src/reports/starter_prediction.py`) tests `age_group` against exactly two shapes — a `\d+U` bracket and the free-text range form. Every school-family value matches neither, so it falls through to team-name keyword matching while the field naming the level sits unread in the same response.

**The field is inert today, verified not reasoned** (software-engineer executed it): all seven school values produce results byte-identical to `age_group=None`. With an empty `ngb` and no team name, every one resolves `unknown` → card suppressed. Nothing currently depends on the behavior this epic changes.

**Prior work.** E-218 built `detect_league_level`; E-243-02 added the youth Pitch Smart fallback; IDEA-126 added the free-text range handling; **E-272** added the season × level → league model, the age-bracket ladder, and NRBL. E-274 extends the same ladder with a third `age_group` family. It does not revisit any rest-rule table.

**REDACTION NOTE — read this before trying to re-verify any named team below.** Real opponent team names have been replaced throughout this epic and its stories with fictional sentinels, so the artifacts clear the doc-PII byte-gate (`scripts/check_doc_pii.sh`, `.claude/rules/pii-safety.md`). The scheme uses only the fictional placeholder vocabulary `.claude/rules/api-docs.md` already sanctions (`Anytown`, `Springfield`, `Example`); no sentinel is derived from, truncated from, or a prefix of a real name. **The same sentinel always stands for the same underlying team**, so every worked example still reads as one coherent case:

| sentinel | stands for | property the argument turns on |
|---|---|---|
| `Anytown East` (+ `Reserve`/`Reserves`/`Sophomore`/`Sophomores`) | one real HS program and its sub-varsity squads | a `<City> <Direction>` school name carrying no level word, plus the tier token where one is present |
| `Anytown Preserve` | nothing — an invented string, as the original was | contains a level word only as a **substring** (`…Preserve` ⊃ `reserve`) without being that level |
| `Example Bank` | one real summer team | a **sponsor** name with no school name and no tier word |

LSB's own program name is deliberately left as-is: it is our program, not an opponent, and it already appears across the committed tree.

**What redaction costs, stated plainly:** a reader can no longer re-check any of these claims against live GameChanger from this file, because the `public_id` is reachable only via the real name. The real names and payloads are in the **untracked, uncommitted** probe outputs at `/workspaces/baseball-crawl/.project/research/E-274-probe/` (`resolve156.json`, `probe_results.json`). If those are gone, the measurements in TN-10 / TN-10b are no longer independently re-derivable and would need re-running.

## Goals

- `detect_league_level` reads the school family of `age_group` and resolves a level tier from it, ahead of every team-name-derived signal and behind DB fields and a recognized `ngb`, per Technical Notes TN-2.
- **The three measured misclassifications in TN-10 are corrected** — the JV team currently resolving `legion` off a "Seniors" substring, and the two `JV1` teams currently resolving `unknown` because `\bjv\b` finds no boundary before the digit.
- **Zero regressions in the under-resting direction**, verified against the 73-team population rather than argued.
- The school-family values outside our rule tables (`middle_12U`, `middle_13O`, `elementary`, `college`) **terminally suppress** with a specific data-quality note, per TN-3 — never falling through to the 15-18 Pitch Smart estimate.
- A value the matcher does not recognize falls through to today's behavior and emits an operator-visible WARN, so an unread signal is never silent again.

## Non-Goals

- **No schema change, no migration, no new crawling, no new HTTP request.** `age_group` appears in zero migrations; the generator already fetches and passes it. Confirmed by grep over `migrations/` and by SE's file-level audit.
- **Replacing team-name inference.** The structured signal is *preferred when reachable*, never a replacement — see TN-5. Any AC phrased as "replace inference" is wrong as written.
- **Changing any rest-rule table, cap, or rest-day value.** This epic changes only which table a team maps to.
- **The operator-picked competition level (E-263-02c).** Unchanged and un-edited by this epic — see TN-7.
- **IDEA-172** (`\bvarsity\b` ordering ahead of the Legion patterns). Separable; see TN-7.
- **The three `docs/api/**` `age_group` corrections and the `/search/opponent-import` 400.** Already landing as direct api-scout work, correctly outside this epic — see TN-7.
- **Reading `competition_level`.** It is authenticated-only and absent from the public profile; `age_group` is self-disambiguating by shape, so it is not needed.

## Success Criteria

- **The three measured cases in TN-10 flip to the `age_group`-derived answer** — this is the anchor, replacing the "no level word in the name" case that measurement showed does not exist:
  - a JV-tier team whose name contains "Seniors" resolves `nsaa_subvarsity`, **not** `legion` (today's wrong league family);
  - a team whose name contains `JV1` resolves `nsaa_subvarsity`, **not** `unknown`.
- **The other 70 of 73 are unchanged.** `age_group` and the name path already agree on the resolved league for 70; a run over the population shows no other movement, and in particular none toward less rest.
- An opponent with `age_group="high_freshman"` / `high_junior_varsity` resolves to the sub-varsity family (`nsaa_subvarsity` spring / `nrbl` summer) and `high_varsity` to `nsaa_varsity` / `legion`, per TN-3 — including when the name carries no level word, even though no such opponent is currently observed.
- `middle_12U`, `middle_13O`, `elementary`, and `college` each suppress the card **terminally**, with a level-specific note distinct from the generic "league not detected" copy — and are NOT reachable by the team-name path afterwards.
- A team named "…Reserve"/"…Reserves" carrying `age_group="high_varsity"` takes the **plain structured-wins path** (varsity family) plus the general disagreement WARN — there is **no** Reserve carve-out (TN-4; the veto was ruled out on 0-of-17 evidence).
- An unrecognized `age_group` value (e.g. `"high_sophomore"`, `"High School"`) falls through to the team-name path exactly as today, and does not raise.
- No regressions: the full suite is green, and the five `starter_prediction` importer files pass (TN-8).

## Stories

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-274-01 | School-family level branch in `detect_league_level` | TODO | None | software-engineer |
| E-274-02 | Structured tier inside the recognized-`nsaa` branch | BLOCKED | E-274-01; **OQ-1** | software-engineer |
| E-274-04 | Reconcile the precedence ladder in `pitch-rules.md` | TODO | E-274-01 | claude-architect |

**E-274-03 (honest Freshman/Reserve label) was REMOVED from this epic on 2026-07-25 and re-filed as IDEA-177.** Its premise was falsified: OQ-4's read-only trace established that **no competition-level value is displayed to the coach at all today** — `StarterPrediction` has no league field, `renderer.py` never puts one on the context, and the LLM prompt actively bans the vocabulary. So the story was not "make an existing label honest" but "add a net-new coach-visible element to a bench artifact," which is a UX decision with an operator in it, carries a `browser-render-testing.md` headless-Chromium obligation, and was only ever SHOULD HAVE (baseball-coach revised its own MUST down once it checked where the label surfaces). The number is retired, not reused.

E-274-02 is `BLOCKED` on Open Question OQ-1, not on a sibling story. It is the only part of this epic that can regress a currently-working resolution, and its value is unproven — if OQ-1 shows no opponent carries a recognized `nsaa`/`nfhs` `ngb`, the story is ABANDONED and re-filed as an idea rather than dispatched.

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### TN-10: The measured population — what this epic is actually worth

api-scout measured the real opponent set rather than leaving the value proposition an estimate (PM asked for this specifically; a planning decision that turns on "is this rare or modal?" must not rest on intuition). Opponents of **all four** LSB 2026 school teams: 146 entries → 83 linked / 63 manual (43% manual) → **73 distinct linked opponents**, each resolved via `GET /teams/{progenitor_team_id}`. All 73 are `competition_level: school`; mix `high_junior_varsity` 29 / `high_varsity` 22 / `high_freshman` 22 — reproducing the peer probe's figures **at the row level**, so the two independent probes now corroborate exactly.

**Running the live `detect_league_level` over all 73 against the `age_group`-derived answer: 70/73 already agree.** The three that differ, all cases where `age_group` is RIGHT and the name matcher is WRONG:

| today | `age_group` says | why today is wrong |
|---|---|---|
| `legion` | `nsaa_subvarsity` | name contains "Seniors" → `\bseniors\b` → Legion. It is a **JV team**. A real misclassification into the **wrong league family**. |
| `unknown` | `nsaa_subvarsity` | name has `JV1`; `\bjv\b` finds no word boundary before the digit |
| `unknown` | `nsaa_subvarsity` | same `JV1` cause |

**Zero cases move in the under-resting direction** — the epic is safety-neutral-or-better on this population.

### TN-10b: The SUMMER population — measured 2026-07-25, OQ-7 CLOSED. The case is NON-ZERO and the two populations agree on rate.

**Population, stated first so the scope travels with the numbers** (the discipline whose absence caused the error below): opponents of LSB's **five 2026 non-school teams** — 223 entries → 167 linked / 56 manual (25% manual) → **134 distinct linked opponents**. Disjoint from the 73. Family mix: `club_travel` 83, `recreational` 35, **`school` 16**. Season: `summer` 130, `spring` 4.

Two scope facts that bind how these numbers may be used: the population is **not purely summer** (4 spring) and **not purely non-school** (16 school-family). **"Summer schedule" is a property of OUR team, not of the opponents on it.**

| | spring (73) | summer (134) |
|---|---|---|
| school-family, **no level word in name** | **0** | **3** (of 16 school-family) |
| resolve `unknown` today, `age_group` would resolve | 2 | 3 |
| different league family | 1 | 1 |
| **moving toward LESS rest** | **0** | **0** |
| total changed | 3 of 73 (4.1%) | 4 of 134 (3.0%) |

**Across both populations: 0 of 207 changes move toward less rest.** api-scout checked this against the actual rule tables rather than reasoning to it — the 3 `unknown`→bound cases go from *no rules at all* (card suppressed) to a binding rule, which is not a loosening; and the `legion`→`nsaa_subvarsity` case is strictly more conservative (max 90 vs 105, more rest at every tier, including 1 day after 1–30 pitches where Legion requires 0).

**The mechanism is the finding, not the rate.** All 3 no-level-word teams are **school programs playing summer ball under a SPONSOR name** — the team name is the sponsor, carrying no school name and no tier word, while `age_group` still reports the true school tier. So the spring redundancy was a property of *that schedule's naming convention*, never a property of the two signals.

**This is the case the epic exists for, and it is unreachable by any name-parsing improvement.** No amount of hardening `_LEVEL_WORD_PATTERNS` can extract a tier from a sponsor name that does not contain one. That is a stronger and more concrete form of the durability argument than "the matcher will meet new quirks."

**The honest ceiling, api-scout's words and PM's agreement:** this remains a small-volume correction — single digits per schedule — whose value is concentrated in cards that are **currently suppressed entirely**. Whether "3 opponents per summer schedule go from no guidance to correct guidance" clears the bar is the operator's call. What the data does refute is shelving it **as redundant with the name**.

### ⚠ SCOPE OF EVERYTHING BELOW IN TN-10: SPRING OPPONENTS ONLY. See TN-10b for summer.

**Read this before using any number below.** The 73 are **your school teams' SPRING opponents** (all 73 `season="spring"`). Every figure here — the 3-of-73 verdict, the 70/73 agreement, the anti-correlation finding — is measured on that population and **does not generalize to summer.** OQ-7 is open to measure it.

**A single summer team already breaks the headline claim.** `Example Bank` — summer, `age_group=high_varsity`, `ngb="[]"`, **no level word in the name**:

```
today:        unknown  ->  get_rules_for_league -> None  ->  CARD SUPPRESSED
with E-274:   summer + varsity class -> legion, 105, binding
```

The team told GameChanger it is varsity. We read the field and discard the answer, so a coach preparing for it gets **no Most Likely Arms section at all**. This is exactly the case struck through below as "0 of 73" — it exists, in summer.

**Do not over-correct in the favourable direction either.** Two of four summer teams shown so far are cases E-274 fixes. That is **n=4 anecdote, not a measurement**, and it does not replace n=73 — it only establishes that the spring measurement's scope is narrower than it reads. The honest position is *the value case is currently unmeasured for half the season*, not *the value is higher than we thought*. Same rigor in both directions.

**Two framings the SPRING measurement killed — one of which is now RE-SCOPED, not killed:**
1. ~~**"Opponents with no level word in the name" — 0 of 73**, structurally so, the signals ANTI-CORRELATED, do not restore.~~ **RE-SCOPED 2026-07-25: true of spring opponents only.** The structural argument (linked opponents carry fully-qualified names; the bare unqualified names are the manual entries where `age_group` is unreachable) holds for the spring population measured — but `Example Bank` is a summer counter-example, so **the anti-correlation is a property of that population, not of the signals.** PM wrote a do-not-restore marker on a claim narrower than it read; that marker was protecting an over-generalisation.
2. **The Reserve-tagged-`high_varsity` case — 0 of 73.** Stands (see TN-4), and note baseball-coach dropped the veto on this evidence — worth re-checking against summer if OQ-7 runs, since it is the same population caveat.

**What the 4% understates, and why the epic still earns its place.** All three failures are **name-matcher brittleness** (`JV1` defeating a word boundary; "Seniors" on a JV team). The name matcher will keep meeting new naming quirks; a structured enum will not. The argument is durability against an open-ended failure class, plus one live wrong-league-family fix — not coverage. State it that way and the 4% is not embarrassing; state it as coverage and the epic looks like theatre.

**Two limits api-scout stated and this epic does not paper over:**
- **One program, one season** (Nebraska HS spring 2026). The 100%-name-coverage result especially reflects how these particular coaches name teams.
- **The 70/73 baseline is a SIMULATION of the function, not a measurement of the pipeline** — api-scout passed `program_type=None` / `classification=None` / `season='spring'`. If the real call site passes a non-null `classification` for tracked opponents, the ladder short-circuits earlier and the baseline shifts. **software-engineer must confirm the real call-site inputs before this number is treated as settled** (folded into E-274-01, AC-12).

### TN-1: What the signal is, and the evidence behind it

`age_group` is a top-level string on `GET /public/teams/{public_id}` — **no auth**, and it is the response the generator already parses. It is polymorphic across three disjoint family vocabularies:

| Family | `age_group` values |
|---|---|
| **school** | `elementary`, `middle_12U`, `middle_13O`, `high_freshman`, `high_junior_varsity`, `high_varsity`, `college` |
| **travel** | `NNU` brackets (8U–18U observed) — the only family the ladder reads today |
| **recreational** | free-text ranges rendering as `"Between N - M"` |

**Authoritative citation: `docs/api/endpoints/get-public-teams-public_id.md` → `## The age_group level field`.** api-scout corrected and expanded that file during this discovery and asked explicitly that the epic cite **the endpoint doc, not either agent's memory** — the memory files are working notes and one of them has already been rewritten mid-discovery. Do not cite `.claude/agent-memory/api-scout/*` for this field.

**Evidence base (api-scout, live, 2026-07-25). Note this comes from TWO independent probes by two api-scout instances, which AGREE — that is stronger than one measurement, and neither subsumes the other:**
- **Availability on opponents is CONFIRMED, not extrapolated.** 25 non-managed opponent public profiles probed unauthenticated: `high_junior_varsity` ×19, `high_varsity` ×6, plus a separate confirmation of `high_freshman`. All three HS values are directly observed on teams we do not manage.
- **The public profile is a faithful mirror, verified on the FULL population.** Paired authenticated-vs-public comparison is **73/73 identical** (JV 29, varsity 22, freshman 22), zero mismatches. An earlier 7/7 figure was a sub-check, now superseded. This matters for provenance: the 73-team `age_group` distribution was gathered via the **authenticated** endpoint, while the generator reads the **public** one — the 73/73 identity is what licenses using those counts to reason about what the generator will see.
- **Population is ~100%.** 73 distinct opponents of our four school teams: populated 73/73 — zero null, zero empty, zero key-absent. With an earlier sweep that is **91 teams at 0% absent**.
- **Two probes, two populations, one conclusion.** The 65-entry figure covers LSB's **two** HS teams; the 144-entry figure covers **four** school teams. They are separate probes that independently land at ~40-42% manually-typed. Do not describe the larger as subsuming the smaller — PM did, and api-scout corrected it.
- **For the HS schedule the school family is total**: school ×73, travel ×0, recreational ×0. The `14U` / `18U` / `"Between 13 - 18"` values seen earlier came from the operator's **legion/summer** teams, not the HS program. In practice this branch handles a **three-value** field, and all three are common (`high_junior_varsity` ×29, `high_varsity` ×22, `high_freshman` ×22).
- **Shape is clean**: all 73 values are exactly lowercase-with-underscores; `lower()` and `strip()` are both identities. No casing or padding variants. No off-enum school-ish values observed (`high_sophomore`, `high_jv`, `high_junior`, bare `varsity`, bare `jv` were probed for and NOT found).

**Two caveats that bind the design:**
- **CAVEAT A — operator-entered.** The value is whatever the opposing coach selected at team creation. Authoritative about that selection, never ground truth about the team's actual league. It can be wrong or stale.
- **GameChanger has no "reserve" level.** The HS enum has three values; LSB runs four (freshman / reserve / JV / varsity). Per baseball-coach, the standard NSAA sub-varsity structure most schools run is Varsity / JV / Freshman — **which matches GC's enum exactly**. So this is an **LSB-specific** structural gap, not an opponent-side data-quality problem. Do not read `high_freshman` on an opponent as a hidden Freshman/Reserve split like ours; treat it as genuinely a freshman team.

### TN-2: Precedence — widen the existing step, do not add a rung

baseball-coach and software-engineer reached this independently and **agree**. `age_group` is ONE structured field filled by ONE creation flow; there is no principled basis for trusting `age_group="18U"` more than `age_group="high_varsity"`. So the existing recognized-`age_group` step is **widened** to cover all three families rather than a new precedence rung being introduced.

Ladder, strongest first — only step 3's scope changes:

1. DB `program_type` / `classification` — unchanged, season-blind.
2. A recognized `ngb` selects the **rule system** — unchanged. (`ngb` names the governing body; `age_group` names the tier *within* it. They are orthogonal axes, which is why the level token does **not** outrank `ngb`. Story E-274-02 uses the token for the *tier* inside the `nsaa` branch, which is not an exception to this.)
3. **A recognized `age_group` form** — travel bracket, **school family (new)**, or recreational range. Ahead of every team-name-derived signal.

   **The travel and recreational branches are UNCHANGED — do not touch them.** api-scout checked both against the live parser: `_AGE_BRACKET_RE` already handles `14U`/`18U`, and `_AGE_RANGE_RE` (added by E-262-03) already handles `"Between 13 - 18"`. Both work. This epic ADDS a third branch to the same chain; it does not rewrite the two that function. Scope the change to the school family only.

   **Put the school check FIRST in the chain.** Order is immaterial for *correctness* today — the three vocabularies are disjoint, and api-scout executed both regexes against all seven school values with zero matches (`middle_12U` included: it looks like it should trip `\b(\d+)U\b` and does not, because `_` is a word character). Order is not immaterial for *durability*: school-first guarantees `middle_12U` reaches its terminal suppression even if someone later loosens the bracket regex, whereas school-last leaves that suppression depending on a regex in another branch continuing not to match.
4. Team-name bracket, then `_LEVEL_WORD_PATTERNS` × season — unchanged.
5. `unknown`.

The three `age_group` families are **disjoint vocabularies of the same field** and cannot co-occur, so they belong in one mutually-exclusive chain — it must be structurally impossible for two to fire.

**Conflict rule:** `age_group` beats a `\d+U` bracket appearing in the team NAME. A name is free text (sponsors, division labels, stale naming); `age_group` is a controlled-vocabulary field the creator picked. This extends the trust order E-272 already established, rather than inventing one. The sole exception is TN-4.

### TN-3: School-family value mapping (baseball-coach ruling)

**STAKES CORRECTION (baseball-coach, 2026-07-25) — PM had this wrong throughout and it applies to this whole epic.** PM repeatedly framed these as "rest-safety calls." More precisely: **this rest gate governs OPPONENT-SCOUTING PREDICTIONS** — which of the opponent's arms is likely to start against us — **not LSB athlete safety and not NSAA/ALB compliance.** LSB's own roster's real rest and pitch-count compliance routes through the separate `teams.classification` DB field (Priority 1 in the ladder, which already has a genuine `reserve` value and is untouched by any `age_group`/`ngb` ambiguity). Getting an opponent's tier wrong here yields a **worse prediction**, not an overworked athlete or a sanctioned program. It is real — coaches plan matchups on this — but it is scouting-accuracy risk, several notches below athlete-safety risk.

**Do not over-weight this epic relative to an actual compliance gate.** And note what the correction does NOT do: baseball-coach issued it **in the same message as both rulings below** and did **not** revisit the suppression MUST in TN-3 or soften it. That MUST stands. Do not re-weigh it on the strength of this correction without going back to baseball-coach.

The school value resolves a level **CLASS**; season then picks the family exactly as it does for a name level word. The season axis is **unchanged** by this epic.

| `age_group` | Level class | Spring | Summer | Season absent |
|---|---|---|---|---|
| `high_varsity` | varsity | `nsaa_varsity` | `legion` | `nsaa_varsity` |
| `high_junior_varsity` | sub-varsity | `nsaa_subvarsity` | `nrbl` | `nsaa_subvarsity` |
| `high_freshman` | sub-varsity | `nsaa_subvarsity` | `nrbl` | `nsaa_subvarsity` |
| `middle_12U` | — | **SUPPRESS (terminal)** | SUPPRESS | SUPPRESS |
| `middle_13O` | — | **SUPPRESS (terminal)** | SUPPRESS | SUPPRESS |
| `elementary` | — | **SUPPRESS (terminal)** | SUPPRESS | SUPPRESS |
| `college` | — | **SUPPRESS (terminal)** | SUPPRESS | SUPPRESS |

**The suppression is a MUST, and it must be TERMINAL.** These four values must not fall through to the team name and must not map to `youth_travel` / `PITCH_SMART_15_18`.

- *middle/elementary rationale (baseball-coach, verified):* USA Baseball's Pitch Smart guidelines are age-**tiered**, and every younger band has a strictly lower daily max and lower per-tier breakpoints than the band above it. `PITCH_SMART_15_18` is calibrated for the **oldest** band, so applying it to a middle-school arm **under-rests** at matched pitch counts and over-permits raw volume. Worked examples given: a 25-pitch outing needs 1 day for a 7-8-year-old but 0 under the 15-18 tiers; a 40-pitch outing needs 2 days for a 9-10-year-old but 1 under the 15-18 tiers; and the daily cap gap is worse (real 50 vs 105). **See OQ-3** — the exact breakpoint figures are baseball-coach's recall from an environment with no web access, and the epic must not print them as cited fact.
- *`college` rationale:* NSAA / Legion / NRBL have no jurisdiction, and college pitch management is NCAA/conference-governed with norms we have no data on. There is no defensible table; inventing one is worse than declining.

**Why terminal matters — and a PM claim RETRACTED here, because the earlier version was wrong in the reassuring direction.**

An earlier draft of this section said *"there is **no live mis-classification today** … the hazard is created by the fix, not by the status quo."* **That is retracted.** It was over-narrowed, and the over-narrowing understated a live hazard. Two paths, and only one of them is clean:

- **The BRACKET path is clean.** `middle_12U` / `middle_13O` do not match `\b(\d+)U\b` — `_` is a word character, so there is no boundary before the digits. The underscore trap that hides `high_freshman` is currently *protecting* these from the travel ladder. That much was right, and it is what SE verified.
- **The NAME path fires TODAY.** `age_group="middle_12U"` with a team name carrying a level word resolves off the *name*, not the bracket — a middle-school team on an NSAA/Legion-tier table, live, right now. This is not created by any fix.

So both are true, and the retracted sentence asserted only the second while denying the first. The sequence is worth recording: PM reported the live hazard correctly, SE tested the enum values **with no team name** and found them inert, PM accepted that as a general correction, and both moved toward the more comfortable framing. **A test that omits the input which triggers the bug is not evidence the bug is absent.**

**What terminality is for, restated accurately:** suppression must terminate rather than fall through, because (a) the name path is a live hazard the fall-through preserves, and (b) IDEA-171's own recommended fix (normalize `_`→space) would additionally make `middle_12U` match `\b(\d+)U\b` and resolve `youth_travel` — a *second* under-resting route arriving as an accident of normalization. A non-terminal suppression leaves the first open and adds the second.

**A sibling hazard on a family this epic does NOT cover — do not assume it is handled.** GameChanger's create-team **recreational** family offers exactly `Under 13`, `Between 13 - 18`, `Over 18`, and **only the middle one is parsed** (`_AGE_RANGE_RE` needs digit-dash-digit). The travel family's `NNO` "and over" form (e.g. `18O`) is likewise unmatched by `\b(\d+)U\b`. All fall to the name path — PM traced `age_group="Under 13"` + a "Reserve" name + summer resolving to **`nrbl`, 105 max**. **A team whose coach declared "Under 13" on a Legion-equivalent pitch table, live today.** It is the same mechanism as TN-3's suppression but on a family baseball-coach was never shown, so **the ruling has NOT been extended to it** — routed to baseball-coach and tracked separately. This epic neither creates nor fixes it; do not let TN-3's school-family suppression be read as covering it.

**Mechanism.** `get_rules_for_league` (`starter_prediction.py:529`) returns `None` for any league id it does not recognize, and `compute_starter_prediction:1246` falls back to `_LEAGUE_WARNINGS["unknown"]` and suppresses. So suppression is cheap and fails safe by default; the work is supplying a **level-specific note** so a coach does not read a deliberate boundary as a data gap.

### TN-4: Tie-break — NO special case. The Reserve veto is DROPPED (baseball-coach re-ruling, 2026-07-25)

**RULED: drop it. Nothing replaces it.** The general rule — **`age_group` wins on disagreement, with a WARN** — is sufficient on its own. The Reserve case was never a rule that needed its own carve-out; it is one instance of the general disagreement WARN, which already gives an operator visibility if it ever fires for real.

baseball-coach reversed its own earlier carve-out on two converging grounds:
1. **Zero observed support** — 0 of 17 Reserve-named teams hit the case (15 `high_freshman`, 2 `high_junior_varsity`). CLAUDE.md's governing principle is directly on point: *"Simple first. Complexity as needed… not in anticipation of problems that might never arrive… When in doubt, leave it out."* A carve-out with no real occurrences is exactly the premature complexity that rules out. If a real occurrence appears, add it then — that is what "as needed" means.
2. **The stakes correction above** — even in the hypothetical, the cost is a worse opponent-scouting guess, not a compliance violation, which further weakens the case for pre-building defensive machinery.

**Language discipline for this epic:** this is not "the tie-break rule." It is *"confirmed no special case is needed — the general disagreement WARN covers the hypothetical, and real data (0 of 73) shows it is not a live concern."* Do not reintroduce tie-break framing; it implies conflicts are routine, and they are not.

**PM's lean was overruled and that was correct.** PM leaned keep-and-reframe on "it is one line, cheap insurance." That is precisely the anticipatory complexity the core principle bars, and PM should have weighed the principle rather than the line count.

**The measurement that produced the reversal, retained:** of 17 Reserve-named teams in the 73, **zero** carry `high_varsity`; coaches map Reserve toward the *safer* tier with near-total consistency. Software-engineer's "Anytown East Reserves tagged `high_varsity`" was constructed — the real *Anytown East Reserve* team is tagged `high_freshman`. Across the population there are 3 operational disagreements in 73, `age_group` correct in all three; the 14 apparent tier-label disagreements collapse to zero operational conflict since Reserve and Freshman both map to `nsaa_subvarsity`.

**Historical note — the superseded ruling.** The original carve-out was: name contains "Reserve"/"Reserves" AND `age_group == high_varsity` → veto the level class to sub-varsity. It is recorded here only so a future reader understands what was dropped and why; **do not implement it.**

**Read this first. The measurement arrived after the ruling and refutes its motivating example.** api-scout checked all 17 Reserve-named teams in the 73:

| `age_group` on a Reserve-named team | count |
|---|---|
| `high_freshman` | 15 |
| `high_junior_varsity` | 2 |
| **`high_varsity`** | **0** |

Software-engineer's "Anytown East Reserves tagged `high_varsity`" is **constructed**. There is a real *Anytown East Reserve* team in the data and it is tagged `high_freshman`. Coaches map Reserve → `high_freshman` with near-total consistency — that is, **systematically toward the SAFER tier**. The under-resting direction the veto defends against **was not observed once.** api-scout recommends dropping the tie-break entirely as a rule with no cases to govern.

**The general rule, which is now the ONLY rule here.** Where the structured value and a team-name level word disagree on tier, **`age_group` wins, and a WARN is logged.** No carve-outs. baseball-coach also rejected software-engineer's broader "stricter tier always wins on any disagreement" as too blunt — it would discard real information in the more common cases where the enum is simply correct and a differently-phrased name just does not happen to contain a matching keyword.

**Accepted-risk sentence (baseball-coach, adapted to the dropped carve-out, to be carried in the shipped code comment):**
> *"`age_group` wins over team-name keywords on disagreement — the same trust order E-272 already established for the bracket ladder — so a stale or mistaken structured value can move a team to the wrong table in either direction. This is an accepted, pre-existing trust call rather than a new risk, and stays bounded by the operator-facing WARN log for post-hoc correction."*

*(The verbatim original opened "Outside the narrow Reserve/Reserves-name carve-out…". That clause is removed because the carve-out is gone; the substance is unchanged. Flagged rather than silently edited, since it is a quoted ruling.)*

**Disagreement is operator-facing, never coach-facing.** A coach mid-prep does not need "GameChanger's metadata disagrees with the team name" on a bench artifact. Mirror the existing `_log_bracket_season_disagreement` observability pattern.

### TN-5: Unknown values — the set is OPEN, and the matcher must say so

**Do not describe this enum as closed.** api-scout attempted to certify exhaustiveness and **could not**: what was extracted is GC's display-mapper `switch` (7 values) plus the team-creation picker (3 options). Seven bundles were searched and the enum object's own definition was not located. Two signals it is open — GC's mapper carries a **`default:`** branch, and the picker offers only **3 of the 7**, so the other four arrive by paths other than team creation.

This **strengthens** the design choice and changes its justification. The reason to use an explicit known-value match rather than normalize-then-regex is not "the set is closed so a lookup suffices" — it is **"the set is open, so we need a matcher that fails visibly on values we have not decided about."** A normalize-then-regex approach would silently absorb a future `high_sophomore` via `\bsophomore\b`, sometimes right and never reviewed.

Requirements:
- Match on a **known-value allowlist** with an explicit unknown fallback. Never raise on an unrecognized value.
- An unrecognized value **falls through to the team-name path** — today's exact behavior, so an unknown value can never be a regression.
- A **prefix** match on `high_*` is NOT adopted, and software-engineer demonstrated why with the exact value we would reach for. `_LEVEL_WORD_PATTERNS` already carries `\bsophomore\b → SUBVARSITY` (`starter_prediction.py:313`), so today a future `high_sophomore` on a team named "Anytown East Sophomore" **already resolves `nsaa_subvarsity` correctly, for free, via the name path** (verified). A `high_*` prefix match would OVERRIDE that one working case with whatever default tier we picked — varsity would under-rest a sophomore team, sub-varsity would be guessing a tier on a value we have never seen while stepping on a matcher that already knew. The prefix match makes things worse in the only case that currently works. This is api-scout's "silently absorb" warning made concrete.
- **Fall-through is the only strictly non-regressive option**, and that is the deciding argument: the value is inert today, so falling through leaves behavior exactly as it is. Neither alternative is neutral — a prefix match can resolve *more* permissively than today, and a terminal `unknown` would *remove* a currently-working resolution (suppressing a "…JV" team because GameChanger added a value is a regression we caused).
- **Same resolution, different LOG.** Emit a **WARN** whenever a non-empty `age_group` matched **no family** — but distinguish a miss that *looks* school-family (`high_*` / `middle_*` / `college`-adjacent) from an arbitrary string. The former is strong evidence GC shipped a new enum value we owe a decision on; the former's message should say so. This puts the open-set risk where an operator can see it without letting an undecided value pick a rest table.
- Scope the WARN predicate to "matched **no family**," not "matched no school value." In an `if/elif` chain over `age_group` the `else` fires only when no family matched, so brackets and the rec form never reach it. Given school ×73 and travel/rec ×0 on the HS schedule, this should essentially never fire in production — which is what makes it signal rather than noise when it does.
- Do **not** reuse `_LEVEL_WORD_PATTERNS` against the `age_group` value: `\bfreshman\b` does not match `high_freshman` (`_` is a word character — SE-verified for all three HS values against all three relevant patterns).
- Do **not** feed `age_group` to `_nsaa_level_from_name`. That helper uses plain `in` substring matching, not `\b` (`starter_prediction.py:518-526`), so `_nsaa_level_from_name("high_freshman")` returning sub-varsity is **coincidence, not contract** — and the same looseness makes `"Anytown Preserve"` resolve sub-varsity.

### TN-6: Season interaction, and the IDEA-168 relationship

**The season axis is unchanged.** `age_group` supplies the **tier**; it says nothing about which league that tier plays in. `high_varsity` + spring = NSAA Varsity; `high_varsity` + summer = Legion. This epic makes the season axis **more** load-bearing, not less: every team that currently falls to `unknown` for want of a name keyword now arrives at the season matrix with a known tier. Convenient corollary — `team_season.season` and `age_group` come from the **same** response (`generator.py:1683-1689`), so there is no availability skew between them.

**REFUTED 2026-07-25 — the school family is NOT a season hint, not even a soft one.** baseball-coach offered the heuristic that a team would not carry a school tag while playing summer Legion/NRBL ball, "a different program context entirely." A real team does exactly that: **summer + `high_freshman`** (it resolved `nrbl` correctly, via the blank-`ngb` path). **Any AC treating a school value as implying spring is wrong.** Do not reintroduce the heuristic; derive season from `team_season.season` and nothing else.

This also **bounds** the "season is constant within the school family" caution recorded above: that is true of **our school teams' opponents** (73/73 spring), **not** of teams carrying school values generally. Fourth population-mismatch of this planning session, and the quietest — a caution rather than a headline number, so it would have propagated without anyone noticing it had a hidden scope.

**Season is PRESENT on 73/73, all `"spring"` — OQ-5 closed, premise INVERTED (2026-07-25).** api-scout distinguished four failure states separately (key missing, `team_season` null, inner key missing, present-but-empty) and **none occurred**. So season-absent-with-`age_group`-present is **0 of 73**, not merely unproven. **IDEA-168 does not need to sequence first**, and this branch's season-absent case is a defensive default rather than a live path.

**~~An AC trap: within the school family, `season` is CONSTANT.~~ REFUTED 2026-07-25 by the summer measurement — do not act on this.** It was recorded from the spring 73 (all `"spring"`) and framed as a property of the school family. It is not. The summer population carries **13 school-family teams with `season="summer"`**, so **`season` and `age_group` are INDEPENDENT axes, not correlated ones.** Anyone inferring the family from the season, or assuming a school value implies spring, would now be wrong.

This is the **same over-generalisation, from the same spring population, made twice** — once about the name signal (the anti-correlation claim, TN-10) and once about the season signal. Both were true of the 73 and neither was a property of the field. api-scout has corrected its own doc for both; PM had recorded both as durable cautions.

What survives, correctly scoped: **on the spring school schedule specifically**, season does not discriminate tiers, so a test that separates school tiers by season would do nothing *on that data*. The AC-1/AC-2 spring/summer parametrization in E-274-01 remains a legitimate synthetic exercise of the mapping — and is now known to be **more than synthetic**, since summer school-family teams demonstrably exist.

This does not contradict E-272's finding that season IS a discriminating signal — that came from a **mixed-family** population (a summer/legion schedule, where season separates *families*). Within a single HS season it is a constant. Both are true of different populations; api-scout has written the reconciliation into `docs/api/endpoints/get-public-teams-public_id.md` so the next reader does not rediscover it.

Consequence for this epic's tests: the spring/summer parametrization in E-274-01 AC-1/AC-2 is a **synthetic** exercise of the mapping, correct and worth keeping — a summer school-family team is not observed but is not impossible. Do **not** try to validate it against live data and do not treat finding only `"spring"` there as a defect.

**Season-absent case — decided.** Take the **same spring default the name path already takes** (`nsaa_varsity` for the varsity class). Rationale recorded accurately:

> The season-absent varsity default is IDEA-168's concern and is orthogonal in kind to this epic. E-274 adds no new risk *kind*: season-absent + "Varsity" in the name already resolves `nsaa_varsity` today via the name path, and season-absent + `high_varsity` resolves the same league by the same spring default — identical outcome, identical curve. The only delta is **population**, and that delta is bounded by an unobserved payload shape (a 200 whose body omits `team_season`).

Suppressing instead would discard the epic's value in exactly the case where it adds value. Software-engineer withdrew its "sequence IDEA-168 first" recommendation once the risk-kind analysis was done — **but conditionally, and OQ-5 is the condition.**

**Arithmetic correction, because PM got this wrong and it propagated.** PM reported that `high_varsity` at 22 of 73 (~30%) means "the IDEA-168 coupling lands on roughly a third of the population, not a corner," and team-lead relayed that to the operator. **That is wrong.** 22/73 is the share reaching the **varsity branch**; the IDEA-168 exposure is the **intersection** of that with season-absent. With season *present*, `high_varsity` resolves `nsaa_varsity` in spring / `legion` in summer — both correct, zero IDEA-168 concern. So the varsity-branch share does not by itself raise the coupling's weight at all. **The exposure is 22/73 only if season turns out to be absent for the school family**, which is exactly what OQ-5 measures.

**One correction to record, because PM got it wrong first.** PM proposed that season-absent-with-`age_group`-present is structurally unproducible because all five signals are set together inside one `if 200:` block. **That is too strong.** Software-engineer showed the signals are not co-located in the *payload*: `season` and `season_year` are read one level down behind a defensive `pub_data.get("team_season") or {}` (`generator.py:1683-1689`), so a 200 omitting or nulling `team_season` yields exactly `age_group` present + `season` None. What the coarse handler guarantees is that a **fetch failure** is all-or-nothing — a different and weaker claim than payload-shape completeness. The exposure is bounded by an unobserved payload shape (api-scout: `team_season` present and flat across all live samples), not by structure.

Note this means the existing docstring at `generator.py:1668-1670` — *"An isolated `season=None` alongside a usable `team_name` is not a shape this function can currently produce"* — is a claim about the **API** wearing the clothes of a claim about the **function**. **Out of scope for this epic** (the wording is load-bearing against a granular-error-handling refactor and must not be weakened casually); captured as an idea so it is not later cited as a structural guarantee it is not.

### TN-7: Relationship to adjacent work

- **E-263-02c (operator-picked level) — unchanged, and this epic does not edit it.** Both baseball-coach instances concluded independently that a populated `age_group` raises the inference **floor** but does not reach the **ceiling** operator knowledge covers: self-reports go stale, `college`/`middle_*`/`elementary` are cases inference structurally cannot resolve, and the Freshman/Reserve collapse can only be broken by an operator who knows the opponent. Frame E-274 as **narrowing how often the pick is needed**, not as reducing its priority. E-272's SELECTION-vs-MAPPING seam (its TN-6) is preserved: E-274 is a MAPPING-side input improvement.
- **IDEA-168 (season vocabulary drift + season-field absence): STANDS, not folded.** See TN-6. Its "do NOT close as superseded by the operator pick" note remains correct.
- **IDEA-172 (`\bvarsity\b` ahead of the Legion patterns): OUT, genuinely separable.** It reorders entries *inside* `_LEVEL_WORD_PATTERNS`; the school branch runs *before* that list is consulted. No textual or semantic conflict — software-engineer confirmed. E-274 arguably **shrinks** its blast radius, since school-family teams stop reaching the name path.
- **api-scout's `docs/api/**` corrections: OUT, already landing.** api-scout's own argument — the corrections describe what the endpoint *returns*, E-274 decides what we *do* with it, and nothing E-274 concludes can change the settled fact. Coupling a known-wrong factual record to an epic's schedule would leave three docs misleading for the duration, against `.claude/rules/api-docs.md`'s KEEP-always standard. api-scout is a direct-routing exception; the `get-public-teams-public_id.md` correction has already landed.
- **`/search/opponent-import` 400: OUT, unrelated.** The single thread is that its *inferred, never-verified* schema speculates its hits carry `age_group` — but it currently 400s, nothing has depended on it since E-168, and re-verifying needs an operator-captured browser curl via the ingest-endpoint skill, which is not a story an agent can execute.
- **`TeamProfile.age_group` is dead** (`src/gamechanger/team_resolver.py:45,132`) — parsed, never read, not on the report path. **Noted, not scoped.** Flagged for whoever plans the follow-up: a second consumer of this field arriving while a dead one sits unread is how duplication starts.

### TN-8: Test strategy

`detect_league_level` is **pure** — no connection, no sqlite, no filesystem, no network, no environment, no `date.today()`. Parametrized cases against the value literals need no fixture and no DB. `tests/test_league_detection.py` is the natural home.

**Importer sweep** (`.claude/rules/testing.md` test-scope discovery) — files importing the module: `tests/test_league_detection.py`, `tests/test_starter_prediction.py`, `tests/test_report_generator.py`, `tests/test_report_rendering.py`, `tests/test_llm_analysis.py`. Run all five plus story-scoped tests.

**Zero stale contracts expected — and that is a design signal, not a prediction.** No existing test passes a school-family `age_group`; the existing `age_group` references use `"14U"`, `"12U"`, `"18U"`, `"High School"`, `"Between 13 - 18"`, `"13-18"`. An allowlist match cannot touch any of them. **If an implementer finds an existing assertion that must change, treat it as a design-review trigger, not routine churn** — it means the branch is not as additive as designed.

**Two existing tests are a GUARD to keep green — a PM ruling, reversing PM's own first reading.** `TestAgeGroupDetection::test_age_group_high_school_falls_through` and `::test_age_group_high_school_still_falls_through_with_range_fix` (`tests/test_league_detection.py:157,181`) pass `age_group="High School"`. PM first read this as the Test-Validates-Spec defect shape (a fixture mirroring an assumed shape — `"High School"` is GameChanger's *display label*, never a wire value). Software-engineer's reading is better and is adopted: the property they pin is **"an unrecognized `age_group` falls through to the name,"** which is true and important, and the literal being unreal is a *feature* — it can never be silently absorbed by a future enum addition. **Keep the tests and their assertions unmodified.** But **rename them**: their current names assert coverage of "the high school case," which is exactly the case that stops falling through after this epic, and a guard whose name states the opposite of shipped behavior misleads the next reader.

**Two fixture traps, both of which produce green-but-blind coverage:**
1. **e2e fixtures already carry a school value.** `tests/fixtures/e2e/public_team_profile.json` and `tests/fixtures/e2e_degraded/public_team_profile.json` both carry `age_group: "high_varsity"` with `name: "Example Team Varsity"`, `ngb: "[]"`, `season: "spring"`. Structured and name **agree** (both → `nsaa_varsity`), so the e2e suite stays green **and is structurally incapable of discriminating whether the new branch works.** Per `.claude/rules/testing.md` ("annotating a fixture limitation is not covering it"), e2e green must not count as coverage here.
2. **The generator fixture can falsify this epic's own recorded rationale.** `tests/test_report_generator.py:3066-3080` (`TestSeasonThreadedIntoLeagueDetection`) builds the signal set by **direct attribute assignment**, bypassing `_fetch_public_team_info`. Today it pins `age_group_from_api = None` and parametrizes `season`, so it cannot produce the partial shape — but it is one line from doing so, and this epic will be tempted to extend exactly that class. Setting `age_group_from_api = "high_varsity"` while a parametrize leaves `season=None` yields a generator-level test asserting a behavior the live path essentially cannot reach: it will pass, and it will read as coverage while quietly contradicting TN-6.

Coverage the epic owes: all seven values × {spring, summer, absent}; the primary value case (value present, name with no level word → resolves instead of `unknown`); the Reserve veto; terminal behavior for the four suppressing values (including that they do NOT reach the name path); an unrecognized value falling through without raising. Pin the veto and any surprising precedence outcome with a test whose **docstring carries the reasoning**, following `test_unmapped_bracket_beats_nsaa_level_word` — that test is the model for making a surprising outcome meet its rationale before a maintainer decides it is a bug.

### TN-9: Consultation completeness (per-domain verdicts)

- **baseball-coach (coaching data, rest-rule safety): CONSULTED.** Precedence (TN-2), the value-by-value mapping and the middle/elementary/college suppression (TN-3), the Reserve veto and the binding-not-estimate ruling (TN-4), the Freshman/Reserve display finding (E-274-03), and the E-263 sequencing read (TN-7). Note: two baseball-coach instances answered (a team name-collision); team-lead reconciled them into a merged ruling of record, and they agreed on every substantive point they both addressed.
- **api-scout (GameChanger API, data availability): CONSULTED.** The blocking evidence gap closed positive, the population and family-mix sizing, the shape hazards, and the open-enum finding (TN-1, TN-5), plus the doc-corrections scoping call (TN-7).
- **software-engineer (Python implementation): CONSULTED.** Containment, the verified inert-today premise, the placement analysis, allowlist-over-normalization, the unknown-value branch, the IDEA-168 risk-kind analysis, and the test strategy including both fixture traps (TN-2, TN-5, TN-6, TN-8).
- **data-engineer (schema, ETL): WAIVED** — no schema, no migration, no ETL. `age_group` appears in zero migrations and is never persisted.
- **claude-architect (context layer): CONSULTED-BY-OUTCOME, and the verdict CHANGED during planning.** Originally WAIVED on the reasoning that no context-layer file was in scope and `pitch-rules.md` could be handled at the closure gate. That was wrong twice over: E-274-01 makes the file's step-3 precedence ladder wrong *in kind*, and the OQ-4 trace found a separate live falsehood in its "Tier 2: LLM Prompt Injection" paragraph. Both are now story **E-274-04**, following the E-272-04 precedent of a dedicated CA story rather than a closure-gate assessment. CA has not been consulted on that story's content; it is scoped from the trace findings and CA owns the execution.
- **ux-designer: WAIVED, and the original reason was falsified.** The first waiver read "E-274-03 refines existing inline copy, not layout" — the OQ-4 trace established that no level label exists to refine, so that reasoning was wrong. The waiver still stands, but on different grounds: the story it referred to has been **removed from this epic** (re-filed as IDEA-177) precisely *because* it turned out to be additive UX. ux-designer is genuinely relevant to **IDEA-177**, not to what remains here — E-274 now touches no coach-facing surface at all.

## Open Questions

- **OQ-1 (gates E-274-02, BLOCKED):** How many opponent profiles carry a **recognized** `ngb` (`nsaa` / `nfhs` / `american_legion` / `usssa` / `perfect_game`) at all? api-scout observed `ngb` as the junk-empty `"[]"` on 5 of 7 and `""` on 2 of 7 — i.e. **zero recognized** in that sample — which suggests the `ngb=="nsaa"` branch may be a path nobody traverses. If prevalence is ~zero, **ABANDON E-274-02** and re-file as an idea; do not ship a change that can regress a working path for no measured benefit. Owner: api-scout.
- **OQ-2 — CLOSED 2026-07-25. baseball-coach re-ruled with the measurement and DROPPED the Reserve veto** (see TN-4). Nothing replaces it; the general disagreement WARN suffices. It also issued the stakes correction now recorded at the top of TN-3. PM's keep-and-reframe lean was overruled, correctly — "it is one line, cheap insurance" is exactly the anticipatory complexity CLAUDE.md's core principle bars.
  <br>*Original question, retained:* api-scout found **0 of 73** Reserve-named teams tagged `high_varsity` (15 `high_freshman`, 2 `high_junior_varsity`) — coaches map Reserve toward the *safer* tier, and the veto's motivating case does not occur. Operational disagreements across the whole population: **3 of 73, `age_group` correct in all 3.** baseball-coach ruled the veto without this data; **it must now rule again with it.** Keep the one-line guard against an unobserved direction, or drop it as a rule with no cases? PM's lean is keep-and-reframe (see TN-4), but PM will not overturn or silently retain a rest-safety ruling on its own. Owner: baseball-coach.
- **OQ-7 — ANSWERED 2026-07-25, gate CLOSED. See TN-10b.** The summer population (134 distinct linked opponents, disjoint from the 73) confirms the case is **non-zero**: 3 school-family teams with no level word in the name, all resolving `unknown` → card suppressed today. Rates agree across populations (4.1% spring / 3.0% summer, **0 of 207 toward less rest**), but the *mechanism* differs and that is the finding — the 3 are **school programs playing summer ball under a sponsor name**, so `age_group` is the only level signal and no name-parsing improvement can reach them. api-scout's read is **build**, with an explicit ceiling: single digits per schedule, concentrated in currently-suppressed cards. What the data refutes is shelving it *as redundant with the name*. It also re-confirmed baseball-coach's dropped Reserve carve-out on a second population (combined 23 school-family Reserve-named teams: 20 freshman-level, 3 JV-level, **0 varsity-level**).
  <br>*Original question, retained:* Run the same 3-of-73 comparison over a **SUMMER** opponent population. Every figure in TN-10 comes from spring opponents; `Example Bank` (summer, `high_varsity`, no name level word) already breaks the "0 of 73, anti-correlated" finding by resolving `unknown` → **card suppressed**, where E-274 would give binding `legion`. Two of four summer teams seen so far are cases E-274 fixes — anecdote, not measurement, which is exactly why this needs running. **If summer resembles spring the verdict holds and we lose an hour; if it does not, the epic's value is being judged on the wrong half of the season.** Also re-check TN-4's Reserve finding against summer, same population caveat. Owner: api-scout. PM concurs with team-lead's recommendation to run this before the operator decides.
- **OQ-6 — RETRACTED 2026-07-25. It rested on a FALSE INFERENCE, corrected by the operator.** It claimed "no high-school opponent report has ever been generated," and escalated generating one to the highest-value action ahead of any build decision. **Dozens of HS-opponent reports have been generated**; they are simply no longer in the database.

  The measurement was real and the inference from it was not. api-scout correctly counted **37 reports across 18 distinct target teams, none of them school-family** — but **the `reports` table is CURRENT STATE, not a historical record.** `cleanup_expired_reports()` unlinks expired reports, `bb report cleanup` runs opportunistically at the start of every `generate`, and `bb db purge-scouting` wipes the tier outright. A report that ran and expired leaves nothing to count. So "no HS report exists in the DB" was measured correctly and means only that; "no HS report has ever been generated" was never measured and is false.

  **What the escalation produced anyway, worth keeping on the record:** the operator supplied nine teams and reports were generated for all nine — 9/9 succeeded, zero failures, and **zero orphan deletions across all nine** (the destructive passes deleted nothing). Two were genuine spring HS teams (a Varsity and a JV from the same school), three Reserve, two Legion Seniors, one Legion Juniors, one 18U travel. **The three Reserve teams are the first to exercise E-272's NRBL path against real teams** — that claim does hold, because the code shipped hours earlier and did not exist before. Separately and outside this epic's scope: the reference-date invariant held across a **venue-local midnight boundary** mid-batch (eight reports dated `2026-07-24`, the ninth `2026-07-25`, both correct) — a live confirmation of E-253's derivation that no test could have produced.

  **Net: the gate closes as INVALID, not as answered.** Nothing else in the epic changes; the 3-of-73 measurement stands and the operator still holds the build/shrink/shelve call.
- **OQ-3 (confirmations before READY):** (a) Confirm the TN-4 veto sets the level **CLASS** (season then picks the family) rather than resolving `nsaa_subvarsity` directly — a literal reading of the ruling would bypass the season axis the same ruling confirms unchanged. (b) The TN-3 Pitch Smart breakpoint figures are baseball-coach's recall from an environment with **no web access**; baseball-coach staked the *direction* of the claim but explicitly told us not to trust the exact numbers. The epic must not print them as cited fact — either obtain a citation or state the direction without the table. Owner: baseball-coach.

- **OQ-5 — ANSWERED, premise INVERTED. Gate closed.** `team_season.season` is present on **73/73, all `"spring"`**; api-scout checked four failure states separately and none occurred. Season-absent-with-`age_group`-present is 0 of 73, so **IDEA-168 does not sequence first** and TN-6's season-absent case is defensive rather than live. The answer also produced the AC trap now recorded in TN-6 (season is *constant* within the school family, so it cannot disambiguate school tiers). One provenance note from the answering: the question was framed as a re-slice of data already held, and it was not — the held counts came from the **authenticated** endpoint's flat `season_name`, a different field on a different endpoint from the public profile's `team_season.season` that the generator actually reads. api-scout ran fresh calls and said plainly that answering from the held data would have produced a wrong answer.
  <br>*Original question, retained: what `team_season.season` value do those 73 school-family opponents carry?* Nobody has looked, and it is the same field on the same payloads api-scout already counted `age_group` from. Software-engineer raised it as the load-bearing unknown: `starter_prediction.py:273-291` records lowercase `"summer"` as the **only** token ever observed in the proxy corpus, with `"spring"` explicitly *unconfirmed* — and these 73 are spring-HS opponents. Two outcomes, and they point opposite ways:
  - They carry `season: "spring"` → season is present, `high_varsity` resolves correctly, IDEA-168 exposure stays bounded and unobserved, **TN-6 stands as written.**
  - They carry `null`, omit the field, or carry an unrecognized token → **season-absent-with-`age_group`-present is not a rare payload shape, it is the MODAL case for the entire school family.** IDEA-168 becomes load-bearing across the varsity share, software-engineer reverses to "sequence IDEA-168 first," and this epic is delayed behind it.

  Report raw values with **null and key-absent as distinct buckets**. Team-lead has independently agreed that if the reachability argument does not hold, sequencing IDEA-168 first is correct even at the cost of delaying E-274 — converting newly-resolved cards onto a branch with a known season-absent under-rest is not a trade to make silently. Owner: api-scout (measuring now).
- **OQ-4 — ANSWERED, and the answer removed a story. Both authorities were wrong; the truth is "neither."** A read-only trace established that **no competition-level value reaches the coach at all**: `StarterPrediction` (`starter_prediction.py:72-88`) has no league field — `league` is an argument, never an output; `generator.py:2432-2447` computes it, passes it, and drops it; `renderer.py:812-813` never puts it on the context; and `llm_analysis.py:63` actively **bans** the vocabulary in the system prompt. The only coach-visible "level" text is static template prose with nothing interpolated (`scouting_report.html:660`, `:664`). So E-274-03 was additive UX, not a copy correction — removed from the epic, re-filed as **IDEA-177**. The two authorities diverged because `pitch-rules.md` "Display" is about the exclusion **reason** string (correct, but not about level) and its "Tier 2: LLM Prompt Injection" paragraph is **stale** — see E-274-04.
  <br>*Original question, retained: is the coach-facing level label engine-produced deterministic text or LLM-narrated?* baseball-coach grepped `src/api/templates`, found no template-level rendering, and concluded it is narrated text driven by the rest table. `.claude/rules/pitch-rules.md` ("Display") says the opposite — that the exclusion reason string is *passed through from the engine to the display layer*. Both cannot be right, and the answer determines E-274-03's file list, its testability (an LLM-narrated surface cannot be pinned by a deterministic assertion), and whether the rule file is stale. E-274-03 currently carries a candidate file list rather than a settled one because of this. **PM's quality checklist bars a READY epic with an unsettled Files-to-Modify list**, so this must close before READY even though the story itself is well-formed. Owner: software-engineer (a read-only trace, routable to `Explore`).

## Closure Obligations

Four captures are **deferred to closure by team-lead's instruction** (do not churn the ledger now). Recorded here so the deferral is a commitment rather than an intention — if this epic is ABANDONED rather than completed, these still get filed, because none of them depends on the epic shipping.

0. **A measurement over one population, reported as a statement about a different one — file FIRST, and it is now the session's dominant failure mode with FIVE instances.** This displaces verdict-reason rot from the top slot on evidence (team-lead ranked that first at two instances; this has five). Every one had the number right and the population wrong:
   - **(d) A test that omits the input which triggers the bug is not evidence the bug is absent.** SE tested the school enum values **with no team name**, correctly found them inert, and PM over-read that as a general all-clear — retracting a live hazard PM had originally reported correctly. This one produced a **false ALL-CLEAR**, which is worse than a false alarm.
   - **(e) The load-bearing one: the 3-of-73 value verdict was measured on SPRING opponents only**, and a summer team (`Example Bank`) breaks its headline "0 of 73, signals anti-correlated" finding outright. PM had written a **do-not-restore marker** on that claim — protecting an over-generalisation rather than a finding. Unlike the others this fed a **build/shelve recommendation put to the operator**.
   - **Two properties that make this family hard to catch, both visible only across five instances:** a *caution* propagates further than a *number* because numbers get audited (instance (c)); and a **do-not-restore marker actively defends the over-generalisation**, converting a scoping error into a durable one. Original three: (a) the `high_varsity` **branch share** (22/73) reported as **IDEA-168 exposure**, which is the intersection with season-absent; (b) the `age_group` counts, gathered from the **authenticated** endpoint, treated as measurements of the **public** endpoint the generator actually reads; (c) **"no HS report exists in the DB"** reported as **"no HS report has ever been generated"** — the `reports` table is current state, not history, so expiry and purge erase the evidence. Only (b) was caught before it did damage; (c) escalated a false premise to the operator as the single highest-value action. **The tell is that the number is real and verifiable, so it survives every check aimed at accuracy** — what needs checking is the noun the number is attached to. Note (c) also has a distinct sub-shape worth naming: **a current-state table read as a historical record**, which will recur anywhere someone counts rows to answer "has X ever happened."
1. **Verdict-reason rot (file SECOND — still substantive).** A per-domain consultation verdict is a claim with a **stated reason**, and the reason can rot **independently of the verdict**. Every other lesson in the context layer covers a claim whose *conclusion* went stale; this is one whose conclusion survived while its *justification* died underneath it — strictly harder to catch, because nothing in the artifact looks wrong and any check asking "is there a verdict for each domain" passes cleanly. Two of this epic's six TN-9 verdicts had it (`ux-designer` and `claude-architect`), and one survived by luck. **It generalizes past consultation verdicts**: the closure context-layer assessment is eight per-trigger verdicts with stated reasons, and the ratchet exception is a verdict with a reason. Same structure, same exposure, and both are decision points an operator reads.
2. **Consultation phrasing determines derivation vs. compression.** An agent asked *"what does X say"* re-derives; an agent asked *"confirm X"* is being invited to compress. api-scout twice refused to compress from data it already held (a peer's prose summary, then its own stored payloads) and was right both times; team-lead produced the inverse failure repeatedly in the same session. Distinct from [[IDEA-175]] — that one is about *who* is addressed, this is about *how the ask is phrased* — and it would be lost if folded in.
3. **Removing a story mid-planning leaves references in at least four places.** Deleting E-274-03 orphaned pointers in a `Blocks:` dependency line, a Handoff Context block, and **two consultation verdicts** — four sections, only one of which is where anyone would look first. Found by grepping rather than trusting that the Stories-table edit had covered it. Worth a fixed checklist.

## History
- 2026-07-25: Created (DRAFT). Promoted from IDEA-171. Discovery consulted api-scout, baseball-coach, and software-engineer; the blocking evidence gap (whether the school family appears on non-managed opponents' public profiles) closed **POSITIVE** on 25 live unauthenticated probes.
- 2026-07-25: **Both api-scout probes and their attribution.** The 73/144 dataset came from a *second* api-scout instance, not the one on this team; the on-team instance corrected PM for attributing it to itself and for describing the larger probe as subsuming the smaller. They are two independent probes over two populations that agree at ~40-42%. Recorded because the correction improves the evidence (independent agreement beats a single sample) while removing PM's ability to ask for a re-slice — a distinction that only surfaced because api-scout volunteered it.
- 2026-07-25: **The convergence-on-the-alarming-framing note.** PM reported the `middle_12U`-on-varsity-table case as a LIVE hazard; team-lead amplified it to the operator as a live bug; software-engineer's execution showed there is **no live mis-classification** and the hazard is **created by the fix**. Separately PM reported `high_varsity` at 22/73 as making the IDEA-168 coupling "roughly a third of the population," team-lead relayed that, and software-engineer showed the exposure is the *intersection* with season-absent, not the branch share. **Two people converged on the more alarming framing twice, in the same direction, on findings we were pleased with.** That is the pull `.claude/rules/tool-output-integrity.md` names in its safety-comment sub-class, arriving in planning prose rather than code comments. Both corrections have been passed back to the operator.
- 2026-07-25: **Process note for closure —** four claims reached PM during discovery that did **not** survive verification, and all were caught by checking rather than by scoping the work they implied. Team-lead has counted four relay-without-verification errors on its own side across the session (this epic's `team_season.season.year` claim and the "closed enum" framing among them); software-engineer owns the "closed enum" origination and said so unprompted. (1) A relayed claim that tests encode a fabricated `team_season.season.year` nesting: no test or fixture does; the one live occurrence is `.claude/rules/testing.md:116`, which carries it *deliberately* as the labelled wrong example. Team-lead identified the mechanism as forwarding a specialist's compound statement as a single unit after verifying only the half inside that specialist's direct observation. (2) PM and software-engineer both asserted a "closed enum"; api-scout could not certify it (TN-5). (3) PM asserted a structural unreachability that software-engineer showed was too strong (TN-6). This belongs in the epic record because two of the three were PM's own, and a discovery that only logs other agents' errors is not measuring itself.
