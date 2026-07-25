---
name: e275-classifier-hardening-rulings
description: Four E-275 rulings -- unhandled age_group shapes (full vocabulary), little_league ngb recognition, USSSA/Perfect Game rules-exist correction, IDEA-172 Legion-vs-Varsity name precedence
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

## RULING 1 -- unhandled `age_group` shapes, full vocabulary

Three families, each ruled independently -- **do not flatten to one answer per family,
and do not flatten across families**. The travel and school ladders were already
implemented/ruled before this round (travel `\d+U` via `_AGE_BRACKET_RE`, school via
E-274 TN-3); this ruling covers what's still open plus RE-CONFIRMS what's settled, all
in one table for E-275 planning convenience.

| Value | Family | Binds / Suppresses / Guideline | Status |
|---|---|---|---|
| `8U`-`14U` | travel | BINDS to `youth_travel` (Pitch Smart guideline estimate, `is_estimate=True`) | implemented (bracket ladder) |
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
