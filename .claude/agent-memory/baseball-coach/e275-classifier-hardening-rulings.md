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

Related: [[league-pitch-rules]], [[e274-age-group-level-signal-consultation]],
[[probable-starter-model]]
