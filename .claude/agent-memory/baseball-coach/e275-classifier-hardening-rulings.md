---
name: e275-classifier-hardening-rulings
description: E-275 rulings -- URGENT correction that 8U-14U travel-bracket teams currently bind to a 15-18 pitch curve and must suppress instead; plus unhandled age_group shapes (full vocabulary), little_league ngb recognition, USSSA/Perfect Game rules-exist correction, IDEA-172 Legion-vs-Varsity name precedence
metadata:
  type: project
---

Re-derived 2026-07-25 at team-lead's request after a prior ruling was lost mid-session
(idle summary preserved only a fragment). Re-derivation below CONFIRMS the fragment
("Under 13 suppresses, Over 18 stays guideline, 18O binds") rather than contradicting
it -- and that exact ruling, with full reasoning, was ALREADY durably captured in two
places before this session even started: `.claude/agent-memory/baseball-coach/league-pitch-rules.md`
("ADDITIONAL GAP FOUND 2026-07-25" under the Season x Level model) and
[[e274-age-group-level-signal-consultation]] ("Recreational-family under-rest hazard").
It also matches the shipped epic AC language for the school family in
`epics/E-274-age-group-level-signal/epic.md` TN-3. **E-275 planning should cite those
locations directly for the rec/school rulings rather than re-deriving from this file** --
this file's contribution is (a) confirmation the ruling survived independent re-derivation,
(b) the NEW travel-family and little_league/USSSA/Perfect-Game/IDEA-172 rulings requested
this round, and (c) falsifiers, which the prior capture did not state explicitly.

## URGENT CORRECTION (2026-07-25, same day) -- 8U-14U travel bracket must SUPPRESS, not bind

**This supersedes the "implemented, correct" status I gave the 8U-14U rows in Ruling 1
below when I first wrote this file, hours earlier the same day. That was wrong -- not
because the mechanism was mischaracterized, but because I had not yet weighed it against
the suppression standard I was simultaneously setting for `Under 13` and `middle_13O`.
Treat this section as authoritative over Ruling 1's original table; Ruling 1's table
below has been edited in place to match.**

**Verified directly against the code** (`src/reports/starter_prediction.py`), not taken
on trust: `_league_from_age_bracket` (lines 334-353) maps any `\d+U` bracket below 15
-- the entire `8U`-`14U` range -- to `"youth_travel"`. `get_rules_for_league` (line 547)
routes `"youth_travel"` to `PITCH_SMART_15_18` -- a 105-pitch-max curve whose own
constant name says `15_18`. The report renders this with `is_estimate=True`, producing a
small amber "Estimated rest" badge and a banner reading "This level doesn't publish
pitch-count rules, so rest and availability use a standard youth pitch-count guide. Treat
as a directional read, not a hard rule" (`scouting_report.html:664`). **I did not verify
the specific "43 teams, 42 youth_travel + 1 legion" population count myself** -- I have
no DB/query tool in this consultation, so that number is relayed, not independently
re-run. The MECHANISM is confirmed directly from source and does not depend on the exact
count: every team whose `age_group` bracket parses below 15U hits this path, whatever the
current population size turns out to be. (The one `legion`-resolving case in the relayed
count is unrelated to this defect -- Priority 1 of `detect_league_level` lets a tracked
team's own DB `program_type="legion"` override `age_group` entirely, a different,
DB-classification signal outside this ruling's scope. Don't fold it into the same fix.)

**Ruling: reclassify the ENTIRE below-15U travel bracket (`8U` through `14U`) from
BINDING GUIDELINE ESTIMATE to SUPPRESS, terminal -- identical treatment to `Under 13`
and `middle_12U`/`middle_13O`/`elementary`/`college`.** This is a **live, shipped defect
requiring a code fix**, not a gap needing a first-time ruling -- it directly contradicts
a ruling I made in this same consult session (`Under 13` suppresses because "every table
we have is calibrated for 15+ and would under-rest a younger arm at matched pitch
counts"). `13U`/`14U` is the identical hazard under a different family label, and
`middle_13O` -- the SCHOOL family's name for the same 13-14 age population -- already
suppresses. Today the same real child gets a hard "no rest data" wall if their coach
picked `middle_13O`, but a confident 105-pitch number if their coach picked `14U` on
GameChanger's team-creation picker. That is not a defensible distinction; it is a coding
accident of which family happened to get built first (E-243-02 chose the estimate path
before the suppression standard existed), and it must resolve to ONE answer per age, not
per input family.

**Is the labeled estimate sufficient mitigation? No, and this is a different kind of
caveat than the ones "Never suppress, always contextualize" is built to handle.**
`.claude/rules/display-philosophy.md`'s core principle governs STAT ROWS and sample-size
uncertainty -- "the coach decides what matters, not the code," with badges replacing
hiding. That reasoning does not transfer here, and the same file says so explicitly: the
starter card's suppress state is "an honest absence of a projection, not the hiding of
present data" and is carved out from the "never suppress" principle for exactly this
reason. The estimate badge/banner as WRITTEN reads as generic imprecision ("directional
read, not a hard rule") -- appropriate for genuine uncertainty about which league applies.
It is NOT appropriate here, because there is no uncertainty about the team's age: the
bracket is a clean, confident numeric match. This isn't "we don't know this team's level,
here's our best generic guess" -- it's "we know exactly what level this is, and we are
knowingly applying a curve we ourselves have already ruled doesn't fit it." A softened
label doesn't change that the underlying number is wrong-band, not merely imprecise, and
a coach under game-day pressure reading "0 rest days needed after 30 pitches" can anchor
on the number regardless of the badge next to it -- the same anchoring risk my `college`/
`middle` ruling already weighed and rejected in favor of hard suppression rather than any
softened estimate.

**The rec free-text range form ("Between 13-18") is UNCHANGED by this correction** and
stays on the youth-estimate path as previously ruled -- it is a genuinely different
situation: that population spans INTO the 15-18 band the curve is calibrated for (a mix
of 13-14 and 15-18 kids), so borrowing the curve is an imperfect-but-real approximation.
An `8U`-`14U` travel bracket is a CONFIDENT, 100%-below-15 population; there is no
mixture to hide behind.

**Why this outranks the rest of this file's rulings, per the operator's reframe conveyed
by team-lead:** this project now serves real USSSA 8U-14U youth coaches as a CORE
audience, not an HS-program edge case (`docs/VISION.md`, named explicitly since
2026-07-05). A miscalibrated pitch cap silently under-resting a real 9-year-old's arm
under a real coach's care, presented with a routine-looking amber badge, is exactly the
shape of harm this project's under-rest-hazard standard exists to prevent -- and unlike
most of today's other findings, this one is a LIVE, SHIPPED, actively-serving-wrong-
numbers defect, not a gap in unimplemented coverage.

**Answering the four questions directly:**
1. **13U/14U and below in the travel family: SUPPRESS, terminal.** Applies to the whole
   `8U`-`14U` range, not just 13-14 -- the younger the band, the WORSE the mismatch
   against a 15-18 curve, so there is no principled place to draw a narrower line.
2. **The rec/travel asymmetry is NOT defensible.** Age must govern regardless of which
   family the value came from. Governing principle going forward: any recognized age
   signal below 15, from any family (rec `Under 13`, travel `8U`-`14U`, school
   `middle_12U`/`middle_13O`/`elementary`), suppresses terminal with a level-specific
   note. Which picker the coach happened to use when creating the team in GameChanger
   must never change the safety verdict for the same actual age.
3. **A correct youth table is legitimate future work, but NOT the blocker for this
   ruling.** I am not asserting real Pitch Smart 7-8/9-10/11-12/13-14 breakpoints here --
   same discipline as OQ-3 and my `little_league` ruling, no number without a sourced
   citation pass. But suppression is right INDEPENDENT of whether or when that table gets
   built: we should not keep showing a wrong number while a right one is unbuilt. Given
   the newly-elevated USSSA-youth audience, building real age-tiered youth tables (7-8
   through 13-14 bands, each with materially lower daily maxes and earlier rest triggers
   than 15-18) is a legitimate epic-level investment to recommend separately -- distinct
   from this suppression fix, and not a prerequisite for it.
4. **Falsifier: this is wrong if my understanding of the age direction is backwards** --
   i.e., if the true 13-14 (or younger) Pitch Smart curve turns out to require LESS rest
   per pitch count than the 15-18 curve, applying `PITCH_SMART_15_18` to a younger arm
   would OVER-rest rather than under-rest, and the harm direction this ruling is built to
   prevent would not exist. I have moderate-not-citation-grade confidence younger bands
   need MORE rest per pitch (adolescent growth-plate vulnerability, echoing the same
   direction argument in TN-3's middle/elementary rationale) but have not sourced this
   specific comparison in this consult. It is also wrong if the operator/PM judges that a
   MUCH MORE STRONGLY WORDED estimate banner (not today's mild "directional read" copy,
   but explicit "this age is below our supported tables -- no safe number available, use
   extreme caution") is an acceptable middle path instead of outright suppression for
   product-engagement reasons -- that is a legitimate alternative I did not choose, and a
   PM/product call to weigh against my domain recommendation, not a pure domain question.

## RULING 1 -- unhandled `age_group` shapes, full vocabulary

Three families, each ruled independently -- **do not flatten to one answer per family,
and do not flatten across families**. The travel and school ladders were already
implemented/ruled before this round (travel `\d+U` via `_AGE_BRACKET_RE`, school via
E-274 TN-3); this ruling covers what's still open plus RE-CONFIRMS what's settled, all
in one table for E-275 planning convenience.

| Value | Family | Binds / Suppresses / Guideline | Status |
|---|---|---|---|
| `8U`-`14U` | travel | **SUPPRESS, terminal** (was: BINDS to `youth_travel` guideline estimate) | **LIVE DEFECT -- see "URGENT CORRECTION" above.** Currently implemented as a wrong bind; ruling reverses it. |
| `15U`-`16U` | travel | BINDS to `nrbl` | implemented |
| `17U`-`18U` | travel | BINDS to `legion` | implemented |
| `18O` | travel | **BINDS**, folded into the 17U+ rule (not a new case) | **RULED, not yet implemented** (regex needs an `NNO` form) |
| `Under 13` | rec | **SUPPRESS, terminal** | **RULED, not yet implemented** |
| `Between 13 - 18` | rec | BINDS/estimates via `_AGE_RANGE_RE` -> `youth_travel` | implemented |
| `Over 18` | rec | **GUIDELINE** (`is_estimate=True`), falls through to bracket/name inference, never suppressed | **RULED, not yet implemented** |
| `high_varsity` | school | spring `nsaa_varsity` / summer `legion` | RULED (E-274 TN-3), implementation status per E-274 stories |
| `high_junior_varsity`, `high_freshman` | school | spring `nsaa_subvarsity` / summer `nrbl` | RULED (E-274 TN-3) |
| `middle_12U`, `middle_13O`, `elementary`, `college` | school | **SUPPRESS, terminal** | RULED (E-274 TN-3) |

**Reasoning, restated for the parts this round actually re-derived (rec family):**
- `Under 13` hard-suppresses identically to the school-family suppress set. The under-rest
  hazard is real and specific: applying any of our tables (all calibrated to the 15-18
  band at the loosest, NSAA sub-varsity at the strictest) to a 7-12-year-old arm
  under-rests at matched pitch counts and over-permits daily volume, mirroring the
  middle/elementary rationale exactly (age-tiered guidelines exist; ours isn't
  calibrated for this band). Must veto BEFORE the name-keyword path, same structural
  placement as school-family suppression -- a "Reserve"-named Under-13 team must never
  reach `_league_from_level_word`.
- `Over 18` does NOT suppress. Falls through to bracket/name inference as today, landing
  on `youth_travel`/estimate or `unknown` depending on what else is present. The
  under-rest hazard is age-DIRECTIONAL (growth-plate/overuse risk concentrates in
  immature arms); it doesn't transfer to an adult population, where existing hard tables
  are already at least as protective as a mature arm needs. But free-text "Over 18" spans
  a 19-year-old and a 55-year-old with genuinely different injury profiles we have no
  table for -- so it stays low-confidence rather than binding.
- `18O` binds by folding into the existing 17U+->Legion-age rule -- a narrow, adjacent
  bracket extension, not a new ambiguous case. Same underlying age population as the top
  of the already-verified-safe travel ladder.

**"No rules apply" vs. "we don't know" -- RULED: these MUST be distinguishable to a
coach, and the mechanism to do it already exists and is already mandated for the school
family; extend it to every suppress-terminal value, present and future.**

The distinction is not cosmetic. Two epistemic states are genuinely different:
1. **Recognized value, deliberately no table** (`college`, `middle_12U`/`middle_13O`,
   `elementary`, and now `Under 13`) -- we know exactly what this team is and have
   *decided* not to guess, because guessing would be actively wrong (under-rest) or
   jurisdictionally meaningless (college has no NSAA/Legion/NRBL authority; inventing a
   number is worse than declining).
2. **Genuinely unrecognized value** (an unmapped `age_group` string, an `ngb` value that
   matches no known family) -- we don't know what this team is at all. This is a data-
   quality gap, potentially a new GC enum value we owe a decision on (per E-274 TN-5's
   open-set handling).

Collapsing both to one generic "league not detected" message would be a real loss: state
1 is a coaching-informative fact ("this team is below our supported bracket" / "college
ball isn't a table we track") the coach can act on immediately, while state 2 is a system
limitation that says nothing about the opponent. **This exact distinction is already an
epic AC** (E-274 TN-3: "a level-specific note distinct from the generic 'league not
detected' copy... so a coach does not read a deliberate boundary as a data gap") and
already has a code precedent (`_LEAGUE_WARNINGS["usssa"]` = "USSSA pitch rules not yet
supported" vs. the bare `"unknown"` warning) -- a THIRD tier already exists in the code
today: recognized-org-but-unimplemented gets its own string, distinct from both a bound
table and generic unknown. E-275 should extend this three-way split (bound / recognized-
no-table / generic-unknown) to every value in the table above that suppresses or falls
through unresolved, rather than inventing a new two-way split.

**Falsifier for Ruling 1:** this would be wrong if either (a) a real `Under 13` team is
observed carrying a legitimate binding-table need we're not aware of (e.g., GameChanger
adds a distinct youth pitch-count regulation body we should bind to instead of
suppressing), which would argue for GUIDELINE rather than SUPPRESS at that age band; or
(b) `Over 18` populations turn out to skew overwhelmingly toward one narrow, well-defined
sub-population (e.g., almost entirely post-HS/Legion-age adult rec, never true masters
league) -- in which case BINDING it to the Legion/Pitch-Smart curve might be defensible
instead of leaving it a guideline. Neither is measured; this ruling holds until measured
otherwise.

## RULING 2 -- `little_league` is not in `_NGB_MAP`

**Ruled: recognize it, do not leave it dead-ending, do not build its rule table yet.**

Mechanism confirmed in code (`src/reports/starter_prediction.py:446-463`): the
`if ngb_list:` block iterates `_NGB_PRIORITY` (`nsaa`, `nfhs`, `american_legion`,
`usssa`, `perfect_game`) looking for a match; when a team's only `ngb` value is
`little_league`, no priority entry matches, and the block falls through to `return
"unknown"` at line 463 -- BEFORE the empty-ngb region (age bracket, name-word ladder)
ever runs. This is a genuinely different failure mode from USSSA/Perfect Game (Ruling 3
below): those ARE in `_NGB_MAP`, resolve to a real league id, and hit the
"not yet supported" warning. `little_league` resolves to the SAME generic `"unknown"`
warning as a garbage/typo'd `ngb` value -- indistinguishable in the coach-facing copy
from "we have no idea what this is."

**Little League Baseball is a real, well-known governing body with its own published
pitch-count regulations** (age-tiered, broadly similar in structure to Pitch Smart/NSAA
-- lower daily maxes and breakpoints than the 15-18 band, since Little League's core
divisions run younger than HS). It deserves the SAME "recognized-but-unsupported"
treatment already established for USSSA and Perfect Game, not the generic-unknown
treatment: add `little_league` to `_NGB_MAP` mapping to its own league id, which
`get_rules_for_league()` returns `None` for today (same as `usssa`/`perfect_game`) and
which gets its own `_LEAGUE_WARNINGS` entry ("Little League pitch rules not yet
supported") rather than falling into the bare unrecognized-ngb branch.

**Explicitly NOT ruling on the actual rule table.** I do not have Little League's exact
current breakpoints memorized with citation-grade confidence (same caveat E-274 OQ-3
raised about my own Pitch Smart recall) and this consultation is scoped to
classification, not table construction -- building the table is separate future work,
lower priority given n=2 observed teams, and should cite an authoritative source
(Little League International's official regulations) before any number is printed as
fact or bound as a hard gate.

**Falsifier for Ruling 2:** wrong if the 2 observed `little_league` teams turn out to be
mislabeled/noise (e.g., a coach picking `little_league` for an org that's actually
something else) rather than a real, ongoing population -- in which case the map-entry
cost still isn't harmful (it's strictly better than today's dead-end either way) but the
"deserves recognition" framing would be overstated. Also wrong in the unlikely case that
Little League's regulations turn out to numerically coincide with an existing table
(would argue for aliasing rather than a distinct constant) -- given Little League's
younger core age range this seems unlikely, but I haven't checked.

## RULING 3 -- USSSA and Perfect Game: rules DO exist, they're just unbuilt

**The handoff's framing ("no rules exist for them") is WRONG. Correcting it.**

Per this project's own context layer (`.claude/rules/pitch-rules.md`, sections "USSSA
(Youth Travel, 7U-18U)" and "Perfect Game (7U-14U)"), both organizations publish
concrete pitch-management regulations:
- USSSA: innings-based (max innings to pitch next day, 1-day and 3-day innings caps by
  age band, mandatory rest triggers).
- Perfect Game: outs-and-pitches dual-unit (daily max pitches by age, mandatory rest at
  >9 outs/day, consecutive-day and multi-day tournament limits).

Both are marked in that file as **"Reference data only -- not yet implemented in
engine"** specifically because they need a **structural** engine extension (the current
`PitchCountRules` dataclass model is pitch-count-only; innings/outs-based rules need a
different unit system), not because no rules exist to encode. This is also why TN-2 in
the E-272 classification model treats `usssa`/`perfect_game` as fully dispositive at
Priority 2 -- they are recognized as **genuinely different rule SYSTEMS**, which is a
statement that rules exist and differ in kind, not that none exist.

**Correction, stated plainly: the 8 still-unknown USSSA/Perfect-Game teams are NOT
permanently unresolvable. They are unbuilt.** The gap is engineering effort (a
structural extension to support innings/outs-based rule sets), not a domain absence.
This changes how E-275 (or a future epic) should frame that population -- not as "no
data available, nothing to do," but as "known, scoped, deferred work with an existing
reference-data starting point already in the repo."

**Falsifier for Ruling 3:** would be wrong if `.claude/rules/pitch-rules.md`'s USSSA/
Perfect Game rule content is itself unsourced or unreliable -- I did not re-verify those
specific numbers against USSSA/PG's current published regulations in this consultation
(I'm relying on the existing context-layer file, not a fresh citation check). If E-275
or a follow-up epic ever moves to actually BIND these tables, that content needs its own
citation pass first, same discipline as OQ-3 required for the Pitch Smart figures.

## RULING 4 -- IDEA-172: Legion-explicit name words should outrank `\bvarsity\b`

**Ruled: reorder. An explicit governing-body/organization token in the name should beat
a generic tier word, mirroring the precedence already established for `ngb` and
`age_group` (specific evidence beats generic evidence).**

Current order in `_LEVEL_WORD_PATTERNS` (`src/reports/starter_prediction.py:309-319`):
`junior varsity/jv` -> `freshman/frosh` -> `reserve(s)` -> `sophomore` -> **`varsity`**
-> `american legion/legion` -> `post \d+` -> `seniors` -> `juniors`. First match wins, so
a name containing both an explicit Legion signal and "Varsity" resolves off "Varsity"
first.

The four Legion-explicit patterns (`american legion|legion`, `post \d+`, `seniors`,
`juniors`) should move ahead of `\bvarsity\b` in the list. Reasoning: "Varsity" is a
generic tier descriptor used across HS, Legion, and other summer orgs alike (some Legion
programs internally label their top squad "Varsity" as opposed to their Juniors squad,
distinct from HS's Varsity/JV split) -- it says nothing about WHICH governing body the
team plays under. "Legion," "American Legion," and "Post N" are name tokens that
essentially only occur in an American Legion context; "Seniors"/"Juniors" are weaker
(see falsifier) but still Legion's own division-naming convention. A name carrying an
explicit organizational marker is telling you more than a name carrying only a
generic-tier marker, and the classifier should trust the more specific signal, exactly
as it already does for the `ngb` field outranking name inference and for a mapped age
bracket outranking every level word.

This does not change the season-dependent behavior in the common case: Legion patterns
already resolve to `legion` season-independently (per `_league_from_level_word`), so
"Legion Varsity" in summer already resolves correctly via the season-family route today.
The reorder only matters when season is absent or drifts -- which IDEA-172 already
identifies as the exact condition that currently MASKS this ordering bug. Confirming the
reorder is correct removes that mask rather than leaving it live.

**Scope check requested by IDEA-172 itself:** verify against the two existing guard
tests (`test_seniors_14u_is_youth_travel`, `test_14u_juniors_is_youth_travel`) that this
reorder does not disturb the (correct, higher-priority) rule that a mapped age bracket
beats EVERY level word regardless of order within the level-word list -- the bracket
ladder runs before `_league_from_level_word` is ever consulted, so this reorder is
scoped entirely within the level-word tier and should not interact with the bracket
floor. I'm not the owner of that verification (it's a code-level check), but flagging it
so E-275 doesn't skip it.

**Falsifier for Ruling 4:** the risk concentrates in `seniors`/`juniors`, which are
plain English words that could appear in a non-Legion context more plausibly than
"Legion" or "Post N" could (e.g., a class-based descriptor, a school named after a
"Legion" landmark, or a summer program using "Seniors"/"Juniors" to mean age cohort
rather than Legion's Senior/Junior divisions). If real HS- or non-Legion-context team
names are observed carrying "Seniors"/"Juniors" alongside "Varsity"/"JV" for reasons
unrelated to American Legion, the reorder would be wrong specifically for those two
patterns (not for `legion`/`post \d+`, which remain low-risk). I have not checked this
against a live sample -- IDEA-172's own open question ("is 'Legion Varsity' a real
naming convention, or a constructed example?") is exactly this check, and per IDEA-172's
notes it was never run against api-scout's 18-team sample. E-275 should run that check
before implementing, not assume my ruling substitutes for it.

**[Correction, 2026-07-26 -- kept as a pointer, not a rewrite, since the paragraph above
is a historical record of what I claimed at the time.]** "Api-scout's 18-team sample"
did not exist as a name corpus and could never have answered this check -- it was an
`age_group`-population sweep (`docs/api/endpoints/get-public-teams-public_id.md:121`).
The paragraph above is wrong to imply that sample was a legitimate-but-unused resource;
it wasn't a candidate at all. The check DID get run, against a different, real corpus
api-scout separately assembled from stored proxy captures (563 names) -- see the RULING
4 AMENDMENT immediately below for what that check actually found.

## RULING 4 AMENDMENT (2026-07-26) -- narrowed to `legion`/`post N` only, on real-corpus evidence

**Superseding note: RULING 4's original text above said "reorder the four Legion
patterns ahead of `\bvarsity\b`." That is now NARROWED to two of the four.** The
scope-boundary confirm I gave team-lead earlier the same day (varsity tier only, not
sub-varsity) still stands unchanged -- this amendment narrows WHICH patterns move at
the varsity boundary, not whether the boundary itself moves further down.

**Evidence, from api-scout, sourced to a real corpus I did not have when I wrote the
original ruling.** **[Corrected 2026-07-27, confirmed first-hand by api-scout directly
(not via relay) -- supersedes the "12 capture sessions"/"2,518 raw response bodies"
framing this bullet block originally used, which conflated two different counts]**:
563 distinct team names harvested from 1,754 JSON-parseable response bodies (2,518
stored, out of 16,665 logged requests), captured across 4 proxy sessions that store
response bodies (of 12 total session logs -- the other 8 carry request metadata only,
zero stored bodies, zero names) on 2026-03-11 and 2026-03-12, `proxy/data/sessions/` --
superseding the abandoned "18-team sample" IDEA-172 pointed at, which api-scout
confirmed was never a name corpus at all,
`docs/api/endpoints/get-public-teams-public_id.md:121`:
- The reorder is a behavioral no-op on every observed name today (0/563 divergences),
  for both the full four-pattern move and the narrowed two-pattern move alike -- so
  narrowing costs nothing measurable now, only removes a promotion with no
  observed benefit and one observed cost (below).
- `\bjuniors\b` matches 0 of the 563 distinct team names; the bare case-insensitive
  substring `juniors` appears in 0 of 2,518 stored response bodies -- i.e. nowhere in
  the captured dataset, in any field. **Confirmed first-hand by api-scout as a real
  substring search run BEFORE the JSON-parse filter (so it covers all 2,518, not just
  the 1,754 that parsed), stronger than a word-boundary claim since it also rules out
  `juniors` occurring inside a longer word.** A SEPARATE, weaker claim answering a
  DIFFERENT question: of the 22 real names carrying a hard Legion token, 0 use
  `juniors` as a self-naming word -- a weak null (small denominator, asks "do Legion
  teams call their divisions Juniors?"), not to be conflated with the strong
  dataset-wide absence above (asks "does the word occur anywhere at all?"). Every
  observed singular `Junior` occurrence (4 of 4, general population) is `Junior
  Varsity`; zero are `Junior Legion`.
- `seniors` has ONE CONFIRMED LIVE misfire on a non-Legion, school-family team,
  verified from source by api-scout (`src/reports/starter_prediction.py:476-490`): a
  team with `age_group=high_varsity`, no Legion token, no age bracket, carries
  "Seniors" in its name (school-graduating-class sense, not Legion's Senior division)
  and falls through to `_league_from_level_word` (since `high_varsity` matches neither
  the bracket nor the range regex), where `\bseniors\b` matches and resolves `legion`.
  Of four candidate names total (bare `seniors`, no Legion token, no bracket), this is
  the ONLY confirmed live misfire -- one is caught upstream by `_AGE_RANGE_RE` before
  the level-word path ever runs (`age_group="Between 13-18"` resolves `youth_travel`
  directly, per the in-code comment at :478-480 -- not a misfire), and two are
  unclassifiable for want of a captured `age_group` field (may or may not be misfires;
  the corpus doesn't say). **[Corrected 2026-07-27: I originally described this as
  confirmed in "TWO independent corpora," reasoning the prior E-274 instance was
  probably the same program's sibling squad (both used a "Seniors N" numbering
  convention). api-scout tested that reasoning directly and RETRACTED it -- this
  corpus has exactly one `Seniors 1`-style name and no `Seniors 2`, and the E-274
  instance survives only as an elided string with its program prefix never persisted,
  so same-program is UNTESTABLE, not merely unproven. The independence claim now rests
  on a simpler, certain fact instead: both observations come from the same operator's
  network, which alone defeats independence regardless of whether they're the same
  program. Correct statement: two observations, same operator network, occurrence
  established, RATE not established.]** This is a PRE-EXISTING defect independent of
  the reorder (no preceding pattern matches this name either way, so order doesn't
  change its outcome) -- but it is direct evidence that `seniors` functions as a
  generic English word in real team names more than as Legion's own division
  convention, which undercuts the "still Legion's own division-naming convention, just
  weaker" framing I gave `seniors`/`juniors` in the original ruling text above.
- Of the 22 real names carrying a Legion token, 9 carry no tier word at all, 5 carry
  `reserve(s)` (the Legion+Reserve collision this file rules on separately below), 4 a
  bracket only, 3 `seniors`, 1 singular `Senior`, 0 `varsity` -- `legion`/`post N` are
  well-attested (22 names) and clean; `seniors` is thin and already shown unreliable.
  **[Corrected 2026-07-27, via team-lead relaying api-scout's re-derivation]: the
  original "14 carry no tier word" figure omitted `reserve(s)` from the tier-word set it
  checked against, so the 5 Legion+Reserve names were miscounted into the no-tier-word
  bucket. Corrected to 9. This also independently CONFIRMS the Legion+Reserve collision
  analysis below was reasoned about the right shape -- all 5 carry a hard Legion token,
  not a softer `seniors` match as one audit pass worried -- so that guard row stands
  unchanged.]**

**CORRECTION (2026-07-26, same day, before this reasoning reached team-lead) -- the
"0/563" framing below overstated the co-occurrence evidence. api-scout flagged this
directly: my own stated sufficiency floor for the co-occurrence falsifier was 30-50
names CONTAINING a seniors/juniors token; the corpus contains only 14 such names total
(8 `seniors`, 2 singular `Senior`, 4 singular `Junior`, 0 `juniors`). 0/563 is the wrong
denominator for that specific question -- the relevant base is 14, not 563, and 14 is
under half my own floor. So: **the co-occurrence falsifier CANNOT be run on this
corpus, not "was run and returned clean."** That distinction matters and is preserved
below rather than smoothed over.**

**Ruling (revised ground): narrow the reorder to `legion`/`post N` only. Leave
`seniors`/`juniors` in their current position (after `\bvarsity\b`), unpromoted --
but not for the co-occurrence-safety reason I originally reached for.**

Team-lead raised the real counterargument, and it holds: PM and SE have since confirmed
by measurement that `legion` requires equal-or-more rest than NSAA Varsity at every
pitch count and strictly more at 46-50, 61-70 and 81-90 post-April; and at 46-50, 61-70
and 81-upward WITH NO UPPER BOUND pre-April. **[Corrected 2026-07-27 via SE's
execution, relayed by team-lead]: pre-April is not a bounded "top tier" divergence --
both tables CLAMP rather than exclude above their own top tier, and the clamp values
differ (NSAA pre-April locks at 3 days, Legion locks at 4 days), so the gap never closes
no matter how high the pitch count runs; SE drove it to 130 and it persisted. The
original spec seed wrote this band as bounded at 81-105 (Legion's declared cap), which
is wrong for the same reason the already-dropped "110 vs 105 daily cap" clause was wrong
-- neither cap is actually enforced by the exclusion gate, so neither bounds anything.]**
-- so even a WRONG promotion-driven collision (a non-Legion team misread as
Legion) fails toward over-rest, a bench-day cost, not an arm-safety one. **[Correction,
2026-07-27, pointer not rewrite: "fails toward over-rest" overstates this -- SE's
verbatim, now in the epic, is the accurate form: "never under-rests: in the three bands
where the tables differ at all it costs a bench day, not an arm, and everywhere else it
changes nothing." "Never under-rests" asserts the ABSENCE of the bad direction; "fails
toward over-rest" asserts a POSITIVE one that's false across most of the pitch-count
range, since the bands where the two tables agree produce no over-rest either. Read
every "fails toward over-rest" / "fail toward over-rest" in this section as "never
under-rests" -- the conclusions below are unaffected, only this phrase is wrong.]** That
weakens, correctly, the safety-direction argument I originally leaned on for keeping
`seniors`/`juniors` unpromoted -- if the co-occurrence sample had come back clean, I
would no longer treat "it's still theoretically risky" as a reason to hold the line,
given confirmed-safe failure direction.

**What survives, and is enough on its own -- FINALIZED 2026-07-27, this is the settled
position, superseding the framing below.** This isn't a safety argument (retired, see
above) and it isn't primarily a misfire-count argument either -- that leg weakened
across this session (co-occurrence sample too thin to run at all; the misfire count
corrected from an implied "confirmed twice" down to one confirmed live instance, one
operator network, independence unestablished) and I should not have let my own
phrasing make it look load-bearing. **The argument that actually carries the ruling is
structural, and it doesn't need a sample size at all.** It's the same concern in
RULING 4's ORIGINAL falsifier text, written before any corpus work existed:
`seniors`/`juniors` are plain English words carrying real non-Legion meanings that
`legion`/`post N` essentially never do. The corpus work sharpened that argument with
concrete FORM rather than replacing it with a count: real attested Legion usage in
this dataset trends toward the SINGULAR adjective form ("Senior Legion," one
instance), the classifier's patterns are PLURAL, plural `juniors` is entirely
unattested anywhere in the 2,518-body dataset (the strong null, confirmed above), and
the one word in that grammatical family that DOES appear at volume -- plural
`seniors`, 8 attestations -- is exactly the one with a common, competing non-Legion
meaning (graduating class). Widening either pattern to the singular form the data
suggests is the real convention would manufacture false Legion signals against
`Junior Varsity` (4 attestations, zero Legion co-occurrence) -- api-scout's own
finding, and the reason not to "fix" the pattern-form problem by loosening it either.

The one confirmed live misfire is corroborating color for this argument, not its
foundation: it shows the failure mode is REAL, which the structural argument alone
couldn't establish on its own. But the structural argument is what survives
sample-size scrutiny, and it's the leg the epic's Technical Note should lead with.
Precedence should track signal RELIABILITY (`varsity`: 31 clean attestations, zero
known misfires; `seniors`: one demonstrated false-positive) as much as
failure-direction safety, which is itself neutralized now that a wrong
promotion-driven collision is confirmed to **never under-rest** (see the correction
above -- costs a bench day in the three bands where the tables diverge, changes nothing
everywhere else), not to fail toward over-rest as this section originally said.

`juniors` has NO misfire evidence (0/2,518 raw bodies, entirely unattested) and no
attested co-occurrence either way -- genuinely a coin flip on current evidence, harmless
to move per team-lead's own read. I'd keep it paired with `seniors` rather than split
the two: they're a singular family (Legion's own Senior/Junior division names, plural
form), and `seniors`'s demonstrated ambiguity is suggestive -- not proof -- that its
lexical cousin carries the same generic-word risk even without its own caught instance
yet. This is a judgment call, stated as one, not a corpus finding.

`legion`/`post N` have no misfire evidence against them (22 well-attested, clean names)
and close a real masked under-rest hazard (IDEA-172/RULING 4's original case) -- keep
those two promoted regardless of the above.

**The bare-`seniors`-misfires-on-a-school-team defect itself is OUT of E-275's scope**
(same discipline as the operator's MINOR-to-idea policy for this epic) -- it is not a
precedence-ordering bug, it exists regardless of any reorder, and fixing it would mean
making the `seniors` pattern itself more selective (e.g., requiring an adjacent numeric
division marker or excluding known school-context co-signals), which is new work, not a
guard-test fix. Flagging for an idea file: `seniors`-alone is an unreliable Legion
signal and should get its own look, separate from this epic.

**Legion + Reserve collision (api-scout's finding (b)) -- already covered, confirmed
safe, no code change needed.** 5 of 563 real names carry a Legion token together with
`\breserves?\b`. `reserve` sits at priority 3, ahead of `varsity` and ahead of Legion
patterns in BOTH the original and the now-narrowed order, so these resolve to the
sub-varsity CLASS either way -- this is the exact case my sub-varsity-tier scope
confirm to team-lead already ruled out of the reorder (RULING 4 stays scoped to the
varsity boundary, not the sub-varsity one). Working the mechanism through with the
authoritative tables in [[league-pitch-rules]] (not asserting from memory, reading the
sourced table): season then picks the FAMILY within the sub-varsity class per the
Season x Level table there --
- **Summer** (the realistic season for an actual Legion/Post-N program): resolves
  `nrbl`. NRBL and Legion are BYTE-IDENTICAL curves today (both 30/45/60/80/105, same
  source line: nrbl.net "adopts standard ALB pitching regulations") -- so a
  Legion-named Reserve team gets IDENTICAL rest-day numbers whether it resolves
  `legion` or `nrbl`. Zero safety stakes; only the internal label differs (matches the
  file's own standing note that Legion/NRBL divergence is a labeling risk, not a
  rest-day risk, until the two bodies' rules actually diverge).
- **Spring or season-absent**: resolves `nsaa_subvarsity`. Point-by-point against the
  Legion table (both tables sourced in [[league-pitch-rules]]): NSAA Sub-Varsity
  requires 1/2/3/4 rest days at 30/50/70/90 pitches; Legion requires 0/1/2/3/4 at
  30/45/60/80/105. At every pitch count NSAA Sub-Varsity's requirement is equal to or
  GREATER than Legion's (strictly greater at the low end, equal in the middle bands,
  and NSAA Sub-Varsity's own max cap of 90 is inside Legion's still-permitted range) --
  never less. Confirms the same "at least as conservative" property SE verified by
  execution for the general sub-varsity-vs-Legion/NRBL comparison, now traced through
  this specific collision by hand against the sourced tables.

So: no ruling change needed for Legion+Reserve, and no code fix required for it either
-- the existing precedence (Reserve ahead of Legion, unaffected by the narrowed
reorder) already resolves it to the safe side in every season branch. This closes
api-scout's open question (b) definitively rather than leaving it as a follow-up.

**Observability flag: keep it, widen its trigger.** Originally proposed as a condition
on promoting `legion`/`post N` only. Widen it to fire on ANY name carrying a
Legion-family token (`legion`, `american legion`, `post N`, `seniors`, `juniors`) beside
ANY generic tier word (`varsity`, `jv`, `freshman`, `reserve`, `sophomore`), regardless
of which patterns actually get reordered. **[Correction, 2026-07-27, pointer not
rewrite: this five-word list is incomplete -- `frosh` is missing, a real alternate the
classifier already matches (`\bfreshman\b|\bfrosh\b` is one pattern), so a name like
"<sentinel> Legion Frosh" would not fire. Ruled since: add `frosh`, AND don't hand-list
this set at all -- derive it from `_LEVEL_WORD_PATTERNS` (its sub-varsity/varsity
alternates) so it can't drift the way this omission just proved it can. TN-5 should
state the trigger set as the current membership of a rule, not a fixed list someone has
to remember to update.]** -- the flag's job is "an ambiguous name exists,
a human should sanity-check it," not "a name changed resolution." Its value doesn't
depend on which patterns are promoted, and the `seniors` reliability finding argues FOR
more observability on that pattern specifically, not less, even though it's not being
given more decision authority.

**`juniors`-vs-`Junior Varsity` read (flagged for PM to record, NOT an E-275 scope
item):** my hypothesis, not a confirmed fact -- the plural `\bjuniors\b` pattern may be
aimed at the wrong word FORM. Legion's own division naming (per ALB rules) uses
"Junior"/"Senior" as adjectives describing the division ("Legion Junior division"), a
form a coach naming a team would render as singular ("Post 9 Junior"), not plural
("Post 9 Juniors" as a noun). That would explain why plural `juniors` is entirely
unattested (0/2,518 raw bodies) while singular "Junior" appears 4 times, always as
"Junior Varsity" (an HS/school-context pairing, not Legion). Plural `seniors` breaks
this pattern (8 attestations, more common than I'd expect if the hypothesis were
clean) -- likely because "Seniors" also has an ordinary, very common non-Legion English
meaning (graduating class) that "Juniors" as a plural noun does not carry as readily.
Worth a dedicated look outside this epic; not asserting the regex needs to change
without a citation-grade check of actual Legion team-naming convention, same discipline
as every other numeric/regex claim in this file.

**Confirmed items from this round, recorded for the story writers:**
- The stronger safety AC PM proposed ("no fixture row's post-fix league may require
  strictly less rest than its pre-fix league, at any pitch count") is the right
  encoding of the coaching standard -- confirmed, not over-constraining. It catches the
  failure mode a plausible misreading of RULING 4 would produce (moving Legion patterns
  to the FRONT of the whole list rather than just ahead of `\bvarsity\b`, which would
  flip a Legion-plus-sub-varsity name from the conservative sub-varsity table to
  Legion's looser one) even when no fixture row happens to encode that exact name.
- Sub-varsity-tier non-extension: reconfirmed deliberate, not an omission (see the
  full reasoning already delivered to team-lead the same day -- extending would flip a
  currently-conservative resolution to a less-conservative one and manufacture a new
  masked under-rest risk in the exact spot this epic exists to remove one from).
- Bracket-floor AC narrowed to `\d+U` + the free-text range form, with `18O`/`NNO`
  recorded as pending rather than implemented: confirmed correct. The coaching property
  ("a confidently-known bracket beats every level word") is unchanged; only its
  currently-testable extent shrinks, and implementing `NNO` would be scope expansion
  the operator has already ruled out for this epic.
- Tier 1 (executes) / Tier 2 (data block, ruled-but-unimplemented, cited not asserted)
  fixture-pack split: no coaching-side objection to the data-block-only mechanism for
  Tier 2. The content is already durably preserved in this file with full reasoning and
  linked from the epic, which is what actually protects it from going stale -- a
  self-announcing failing-test trick is an engineering call, not one I need to weigh in
  on further.

Related: [[league-pitch-rules]], [[e274-age-group-level-signal-consultation]],
[[probable-starter-model]]
