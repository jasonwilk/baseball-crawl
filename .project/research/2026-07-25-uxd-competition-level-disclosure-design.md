# UX Design: Disclosing the Detected Competition Level on the Scouting Report

**Author**: ux-designer
**Date**: 2026-07-25
**Trigger**: IDEA-177 / team-lead consultation, ahead of E-275 (classifier hardening) and a
successor to E-274-03 (retired from E-274, re-filed as IDEA-177)
**Format**: Layout specification + component inventory + copy spec + ASCII wireframes.
Lightest format that fully communicates placement, states, and copy — a full HTML/Tailwind
mockup is unnecessary because the target surface (`scouting_report.html`) is **not**
Tailwind; it is a self-contained hand-written stylesheet (see Stack Note below), so a
Tailwind mockup would model the wrong idiom. This spec instead follows the report's own
existing CSS-class conventions so software-engineer can implement directly.

## Stack Note (read before implementing)

`src/api/templates/reports/scouting_report.html` does **not** use Tailwind. It is
self-contained HTML with an embedded `<style>` block using hand-written classes
(`.heat-0`, `.starter-estimate-badge`, `.trust-quiet`, etc.), rendered once by
`src/reports/renderer.py` with everything inlined and served from disk with no
serve-time templating. This is different from the admin tools-hub, which does use
Tailwind CDN. Every class name proposed below follows the report's own naming
convention (`starter-*` prefix for Most Likely Arms elements, matching
`starter-estimate-badge` / `starter-estimate-banner` / `starter-sublabel` already
in the file) — not Tailwind utility classes.

## Recommendation Summary

Disclose the detected competition level **inline at the top of the "Most Likely
Arms" section**, not in the footer and not as a new report-wide masthead element.
Use a three-state model — **Bound**, **Boundary** (recognized, no table),
**Unknown** — that maps directly onto the engine's existing `suppress_reason`
discriminator plus one new split inside it. Show the resolved level's coach-facing
name in all three states where a name exists; show provenance ("from team name")
only as a light qualifier, only in the Bound state, only when the source was a
name-keyword fallback rather than a structured field.

## Answering the two judgment calls directly

**1. Does the coach need to see which input decided — structured field vs. name
keyword?**

Partially, translated into coach language, not exposed as system internals. Full
provenance (which of DB field / `ngb` / `age_group` / name-regex fired) is
debug information — a coach doesn't act differently knowing it was `ngb` versus
`age_group`, and printing that vocabulary on a bench artifact directly
contradicts `.claude/rules/display-philosophy.md`'s internal-diagnostics-stay-internal
rule (the `data_note`/`suppress_reason` split that already governs this card).

But there is a real trust distinction underneath: a level read off a **structured
field** (DB `program_type`/`classification`, `ngb`, `age_group`) is a confident
signal; a level read off a **team-name keyword** is a fallback guess that can be
wrong (a sponsor name, a stale name, a substring collision — the exact class of
bug E-274/E-275 spent a full planning session hardening). That distinction is
worth one bit of coach-legible signal, not a debug trail. So: append a single soft
qualifier — `(from team name)` — to the level tag **only** when the source was
the name-keyword fallback, and say nothing when it was a structured field (the
unqualified tag is the default, majority case, and stays clean). This gives a
coach who's mid-scan a reason to pause and sanity-check without turning the report
into a system trace. It does NOT name which structured field won when structured
data WAS used — "NSAA Sub-Varsity" needs no further hedge, because a structured
source rarely lies about its own tier.

**2. One treatment for all three states, or different visual weight?**

Two visual treatments, not three, but three distinct COPY blocks. Bound gets the
existing low-key sublabel/badge treatment (unweighted, matches how the card
already discloses "Estimated rest"). The two suppressed states — Boundary and
Unknown — share ONE visual container (a new quiet-slate note box, styled to match
the footer's `.trust-quiet` tone) because both are **honest absences of a
projection**, not errors, and `.claude/rules/display-philosophy.md` already
carves that whole card state out from "never suppress" on exactly that basis —
giving Boundary a louder/warmer treatment than Unknown would misread as "system
found a problem" when nothing is wrong on either side. What must differ between
them is the **words**, not the color: Boundary bolds the recognized level name at
the start of its sentence (so a coach scanning sees "USSSA" or "College" at a
glance even without reading the full note); Unknown has no name to bold and reads
as a plain data-gap sentence. This satisfies E-274 TN-3's AC ("a level-specific
note distinct from the generic 'league not detected' copy") through text weight
and content, not through alarm-coded color — which stays consistent with the
Prohibited Patterns list in `display-philosophy.md` (no dimming/asterisks/color
signaling sample-size-style uncertainty applied to an honest-absence state).

## Why Most Likely Arms, not the footer or a new masthead

The detected level affects exactly one computed output on the report: the
Most Likely Arms rest/availability table. It does not change how any batting or
pitching stat should be read — those are already calibrated to season length, not
competition level (`display-philosophy.md`'s graduated heat tiers). So the
disclosure belongs at its point of use, not as ambient masthead real estate above
every section of an already-dense report.

This also means the disclosure is a **structural retirement of `data_note`-as-hidden**,
not new real estate on top of the current layout: today's suppressed state already
renders a note in that exact spot (`.sort-annotation` under the h2, template lines
655-660) — this design replaces that note's copy and, for the Bound state, adds one
short line above the existing sublabel. Net new vertical space in the common
(Bound, non-estimate) case is one line, roughly 12-14px.

The footer trust block (`trust-block`, "Through {date} (N of M games)") is a
different epistemic axis — data currency/coverage, not classification confidence
— and the standing vision-signal about spot-checking (`docs/vision-signals.md`,
2026-04-12) reads as being about that axis (dates, scores, game counts a coach can
reconcile against the GC app), not about which pitch-count table applies. Folding
level disclosure into the footer would blur two different trust questions into one
block. I recommend against duplicating the level tag there. If the operator later
decides a report-wide masthead badge is worth the real estate (e.g., for a coach
who never scrolls to Most Likely Arms), that is a legitimate Phase-2 follow-up —
flag it to PM as a separate idea rather than scope-creeping this design, per the
"additive UX on a bench artifact" caution IDEA-177 already raised.

One structural caveat: this placement is meaningless when `show_predicted_starter`
is off (env-flag gated) or when `starter_prediction is None` (no pitching data at
all) — in both cases there is no Most Likely Arms section to host the tag. That's
acceptable: the level classification exists *to* drive that section's rest table,
so when the section itself is absent, the disclosure has nothing to attach to and
nothing to say. Flag to PM/SE, not designed further here.

## The Three States

| State | Engine condition (today + after E-275) | Coach reads this as |
|---|---|---|
| **Bound** | `get_rules_for_league()` returns a rule set — includes the narrow `is_estimate=True` Pitch Smart 15-18 case (ambiguous free-text age range only, post-E-275 correction) | "Here's the table we're using; the rest numbers below come from it." |
| **Boundary** | `suppress_reason == "unsupported_level"` AND the level is a *recognized* value we deliberately don't have a table for (USSSA, Perfect Game, Little League, College, Middle/Elementary school, and — after E-275's urgent correction — the entire 8U-14U youth travel bracket) | "We know exactly what this team is; we just don't have a rest table for it yet. Not a data gap." |
| **Unknown** | `suppress_reason == "unsupported_level"` AND the level could not be resolved to any recognized value at all | "The system couldn't figure out what level this team plays at. That's on us, not a fact about the opponent." |

This is the same three-way split baseball-coach's E-275 consultation already
established in code precedent (`_LEAGUE_WARNINGS["usssa"]` vs
`_LEAGUE_WARNINGS["unknown"]`) — this design extends it to render, and generalizes
it to every recognized-but-unbuilt value E-275 adds, not just the two that exist
today.

## Component Spec

### 1. Level tag (Bound state) — new element

Placed immediately under the `<h2 class="section-header">Most Likely Arms</h2>`
line, above the existing `starter-sublabel` / `starter-estimate-banner`. New CSS
class `starter-level-tag`, styled as a plain small-caps-adjacent gray line —
visually a sibling of `.sort-annotation` (same font-size/color family: 8pt,
`#6b7280`) so it reads as metadata, not as content competing with the ranked list
below it.

```html
<div class="starter-level-tag">Rest rules: {{ level_label }}{% if level_source == "name_fallback" %} <span class="starter-level-source">(from team name)</span>{% endif %}</div>
```

Suggested CSS:
```css
.starter-level-tag { font-size: 8pt; color: #6b7280; margin: 2px 0 4px; }
.starter-level-source { font-style: italic; }
```

`level_label` is the coach-facing name of the resolved league — "NSAA Varsity",
"NSAA Sub-Varsity", "American Legion", "NRBL", or (in the narrow surviving
`is_estimate` case) "Youth 15-18 estimate". This sits ABOVE the existing amber
`starter-estimate-banner` when `is_estimate=True` — the tag names *what* estimate
is being used; the existing banner explains *why* to treat it as directional. Do
not merge the two into one sentence; they answer different questions ("which
table" vs. "how much to trust it") and a coach may only need one on a given read.

### 2. Boundary / Unknown note — replaces today's `.sort-annotation` suppress line

New CSS class `.starter-boundary-note`, reusing the footer's `.trust-quiet` color
pair (bg `#f1f5f9`, text `#475569`) so a coach who has already learned "this
slate-gray box means an honest disclosure, not an error" (from the footer trust
block) recognizes the same visual language here — deliberate cross-surface
consistency rather than a new color vocabulary.

```css
.starter-boundary-note {
  margin: 4px 0 6px;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 8.5pt;
  line-height: 1.45;
  background: #f1f5f9;
  color: #475569;
  border: 1px solid #e2e8f0;
}
.starter-boundary-note b { color: #334155; }
```

Markup (replaces template line 660's single conditional string with a 3-way
branch — Boundary bolds the level name, Unknown does not):

```html
{% if starter_prediction.suppress_reason == "unsupported_level" %}
  {% if starter_prediction.level_label %}
  <div class="starter-boundary-note"><b>{{ starter_prediction.level_label }}</b> — {{ starter_prediction.boundary_copy }}</div>
  {% else %}
  <div class="starter-boundary-note">{{ starter_prediction.unknown_copy }}</div>
  {% endif %}
{% else %}
  {# existing insufficient_data copy, unchanged #}
{% endif %}
```

### 3. Mobile

No new responsive rules needed. Both new elements are block-level text (not
tables), so they inherit the existing `@media screen and (max-width: 640px)`
font-size cascade (`body { font-size: 8pt }`) the same way `.starter-narrative`
and `.starter-estimate-banner` already do — verified by reading the existing
mobile block (`scouting_report.html` lines 458-481), which touches only tables,
`.key-players`, and `.roster-grid`, none of which these new elements belong to.
At 375px the level tag wraps to at most two lines ("Rest rules: NSAA Sub-Varsity
(from team name)" is ~40 characters); the boundary note wraps like any other
paragraph-width note box on the page. No horizontal scroll risk — these are prose
lines, not tables.

## Copy Spec

**Bound, structured source, no estimate** (majority case):
> Rest rules: NSAA Sub-Varsity

**Bound, name-fallback source**:
> Rest rules: American Legion *(from team name)*

**Bound, `is_estimate=True`** (narrow surviving case post-E-275 — ambiguous
free-text age range only):
> Rest rules: Youth 15-18 estimate
> *(existing amber banner, unchanged wording, immediately below)*

**Boundary — recognized, no table** (level name bolded, then one sentence):
> **USSSA** — this level publishes its own pitch-count rules, but we don't apply
> them yet. Most Likely Arms can't be calculated for this matchup.

> **College** — there's no governing pitch-count table for college ball we can
> apply here. Most Likely Arms can't be calculated for this matchup.

> **12U** — pitch-count guidance for this age isn't built into our system yet
> (our tables start at 15U). Most Likely Arms can't be calculated for this
> matchup.

Each `level_label` in the Boundary state should be the SPECIFIC recognized name —
"USSSA", "Perfect Game", "Little League", "College", "Middle School",
"Elementary", or the specific age bracket ("12U", "9U") for the post-E-275
suppressed youth-travel range — never a generic "youth" placeholder. This is a
direct requirement of E-274 TN-3's AC and the E-275 urgent correction: the coach
needs to see the ACTUAL age/org, because that is the coaching-informative fact.

**Unknown — genuinely unresolved**:
> We couldn't determine this opponent's competition level from the data
> GameChanger provides, so rest and availability projections aren't available for
> this matchup.

This replaces today's single sentence ("Likely-arm projections aren't available
for this matchup — this team's level doesn't have pitch-count rules we can
apply") which currently serves BOTH states with copy actually written for
Boundary ("doesn't have... rules") — leaving Unknown mis-worded today as if the
system knows something about the opponent's level that it does not.

## Data Requirements Flagged to SE (not designed here — engine/dataclass shape is SE's call)

The template above needs new fields the engine does not currently expose on
`StarterPrediction` (`src/reports/starter_prediction.py`). **Revised per
2026-07-25b above** — `level_label` from the original design splits into two
fields for the Bound state; Boundary/Unknown keep a single label as before.

1. **`rules_label: str | None`** — the coach-facing name of the rule table
   actually applied ("American Legion", "NSAA Sub-Varsity", "NSAA Varsity",
   "Youth 15-18 estimate"). Populated whenever a rule table is bound (i.e. not
   in the Unknown/Boundary states). Natural sibling to the existing
   `_LEAGUE_WARNINGS` dict, not a new pattern.
2. **`level_label: str | None`** — the coach-facing name of the specific tier
   detected, independent of which table won. Equals `rules_label` for every
   branch except the Legion family, where it is "NRBL" or "American Legion"
   per the reserve-age signal (bracket, then name word) — computed WITHOUT
   changing precedence/resolution, per the scope note above. In the Boundary
   state this is the bolded recognized name (unchanged from the original
   design — "USSSA", "College", "12U", etc.); `None` only in the Unknown state.
3. **`level_source: Literal["structured", "name_fallback"] | None`** — whether
   the winning signal for `level_label` was a structured field
   (DB/`ngb`/`age_group`/bracket) or a team-name keyword fallback. Consumed in
   the Bound state per the design above (attaches to whichever of the
   Rules/Level lines the fallback-derived value lives on).
4. **A Boundary/Unknown split inside `suppress_reason == "unsupported_level"`** —
   today `_LEAGUE_WARNINGS` already has this shape internally (`usssa` /
   `perfect_game` / `unknown` as distinct dict entries); the template needs it
   surfaced as a queryable field (e.g., `level_label is not None` doubling as the
   Boundary/Unknown discriminator, so no separate boolean is strictly required —
   SE's call whether to add one explicitly for clarity).

None of this requires new HTTP calls, schema changes, or crawling — it's
plumbing existing `detect_league_level()` output through to the render context,
following the exact precedent `is_estimate`/`suppress_reason` already set
(`.claude/rules/display-philosophy.md`, "Coach-Facing Copy: Internal Diagnostics
Stay Internal"). I have not designed the dataclass/label-map shape itself — that
is SE's implementation decision — only the coach-facing strings and states it
must be able to produce.

## ASCII Wireframes

**Bound, structured source:**
```
┌──────────────────────────────────────────────────┐
│ MOST LIKELY ARMS                                  │
│ Rest rules: NSAA Sub-Varsity                      │
│ Likeliest starter(s) for this matchup — usually   │
│ one of these.                                     │
│ ┌────────────────────────────────────────────┐   │
│ │ 1  J. Smith (R)              [Ready]        │   │
│ │    8 of 10 starts (80%) · 3d rest           │   │
│ └────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

**Bound, `is_estimate` (existing amber banner retained, tag added above it):**
```
┌──────────────────────────────────────────────────┐
│ MOST LIKELY ARMS            [Estimated rest]      │
│ Rest rules: Youth 15-18 estimate                  │
│ ┌────────────────────────────────────────────┐   │
│ │ This level doesn't publish pitch-count      │   │  <- existing amber banner
│ │ rules, so rest and availability use a       │   │
│ │ standard youth pitch-count guide. Treat as  │   │
│ │ a directional read, not a hard rule.        │   │
│ └────────────────────────────────────────────┘   │
│ Likeliest starter(s)...                            │
```

**Bound, Legion family, level and rules diverge (2026-07-25b revision):**
```
┌──────────────────────────────────────────────────┐
│ MOST LIKELY ARMS                                  │
│ Rest rules: American Legion                       │
│ Level: NRBL (Summer Reserve)                      │
│ Likeliest starter(s) for this matchup — usually   │
│ one of these.                                     │
│ ┌────────────────────────────────────────────┐   │
│ │ 1  J. Smith (R)              [Ready]        │   │
│ │    8 of 10 starts (80%) · 3d rest           │   │
│ └────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

**Boundary (recognized, no table):**
```
┌──────────────────────────────────────────────────┐
│ MOST LIKELY ARMS                                  │
│ ┌────────────────────────────────────────────┐   │
│ │ USSSA — this level publishes its own        │   │  <- slate-gray box,
│ │ pitch-count rules, but we don't apply them  │   │     same tone as
│ │ yet. Most Likely Arms can't be calculated   │   │     footer trust-quiet
│ │ for this matchup.                            │   │
│ └────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

**Unknown:**
```
┌──────────────────────────────────────────────────┐
│ MOST LIKELY ARMS                                  │
│ ┌────────────────────────────────────────────┐   │
│ │ We couldn't determine this opponent's       │   │  <- same box, no bold
│ │ competition level from the data GameChanger │   │     level name (none
│ │ provides, so rest and availability          │   │     to show)
│ │ projections aren't available for this       │   │
│ │ matchup.                                     │   │
│ └────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

375px mobile is the same stacked structure at the existing 8pt/7pt cascade — no
layout change, just narrower wrapping.

## Revision 2026-07-25b: Level vs. Rules split (Legion/NRBL)

**Trigger.** Operator ruling, verified against code: *"NSAA reserve is 'subvarsity'.
Summer reserve is NRBL... essentially legion rules. So just classify NRBL as
legion for the case of pitching rules."* Confirmed independently — `LEGION` and
`NRBL` in `src/reports/starter_prediction.py` are byte-identical
`PitchCountRules` (105 max, tiers 1-30/31-45/46-60/61-80/81-105). This makes the
live defect in IDEA-178 (`ngb=american_legion` wins Priority 2 and returns
`"legion"` before the bracket ladder or name-word path can resolve `"nrbl"`,
discarding a real reserve-age signal — 15U-16U bracket or a summer sub-varsity
name word) **produce zero difference in any computed rest number** — but the
operator's own phrasing ("summer reserve is NRBL... a real thing") shows the
LABEL still carries scouting meaning the rules-collapse discards. That is the
same shape as IDEA-177's Freshman/Reserve honest-label case, already in this
brief's motivation, now confirmed on a second, independently-ruled pair.

**This changes the design from one disclosure to two, for this case only.**

The engine's resolved league id conflates two questions that used to travel
together and no longer do: *what tier is this opponent* (the scouting fact) and
*which rule table computes the rest numbers* (the safety/computation fact). For
the Legion family specifically, a team can be a summer Reserve/NRBL squad
(scouting fact) governed by Legion's pitch-count curve (computation fact,
identical either way per the ruling). Flattening both into one label — "American
Legion" — for a team the operator would call NRBL is the same erasure IDEA-177
warned about: the math doesn't care, the coach does.

**Recommendation: split `rules_label` (what table governs the numbers below)
from `level_label` (what tier this opponent actually is), and render as one
line when they coincide, two when they diverge.** This generalizes my earlier
single `level_label` field into two fields with a collapse rule, not a full
rewrite of the design:

- `rules_label: str | None` — the rule table's own name: "American Legion" /
  "NSAA Sub-Varsity" / "NSAA Varsity" / "Youth 15-18 estimate". For the whole
  Legion/NRBL family this is uniformly **"American Legion"** — per the ruling,
  the rule SOURCE is Legion's curve regardless of which of the two teams is
  playing it, so the rules line should never say "NRBL" (there is no longer a
  rules-distinct NRBL curve to name).
- `level_label: str | None` — the finer scouting-fact tier, computed
  independently of which table wins. For the Legion family: "NRBL" when a
  15U-16U bracket or a summer sub-varsity name word (Reserve/Reserves/JV/Junior
  Varsity/Freshman/Frosh/Sophomore) is present, "American Legion" otherwise
  (17U+ bracket, or a Legion-explicit name word with no reserve-age signal).
  Elsewhere (NSAA, USSSA, etc.) `level_label` equals `rules_label` today — see
  scope note below — so nothing changes for those branches.

**Render rule**: when `level_label == rules_label`, show the single line from
the original design ("Rest rules: {rules_label}"). When they diverge (today,
only the Legion-family case), show two lines:

```
Rest rules: American Legion
Level: NRBL (Summer Reserve)
```

Order is deliberate: Rules first, because it explains the numbers directly
below it (the primary utility of this whole disclosure); Level second, as the
scouting-fact gloss on why that table applies to this specific opponent. Apply
the existing `(from team name)` provenance qualifier to whichever line's value
came from a name-keyword fallback rather than a structured field — for the
Legion family that is usually the `Level` line (a 15U-16U bracket is
structured; a "Reserve"/"JV" name word is not):

```
Rest rules: American Legion
Level: NRBL (Summer Reserve) (from team name)
```

**CSS**: no new classes needed beyond `.starter-level-tag` from the original
design — render as two stacked `.starter-level-tag` divs when both labels are
present and differ, one when they coincide. No visual weight change (both stay
the same plain 8pt gray metadata line — this is still the Bound state, still
low-key).

**Scope discipline — do not generalize to the HS Freshman/Reserve case in this
pass.** The same two-field pattern would also fit IDEA-177's original
motivating case (GameChanger's HS enum has no Reserve tier, so a Reserve
opponent reads `high_freshman`) — but that case is structurally different: GC's
own `age_group` enum genuinely does not distinguish Freshman from Reserve, so
there is no discarded structured signal to recover, only a discarded NAME
signal, and recovering it would mean overriding a Priority-1 `age_group` read
with a lower-precedence name keyword — a real precedence question E-274 TN-2/TN-4
already settled the other way (`age_group` wins, no Reserve carve-out, on 0-of-17
observed disagreement). Bundling that decision into this revision would blur two
separate rulings, the same warning IDEA-178's own notes give about not folding
into E-274. I'm flagging the parallel because it strengthens this design's
coherence (one reusable two-field pattern, not two unrelated ad hoc fixes), not
because I'm recommending it be built now.

**Consequence for IDEA-178 worth flagging to PM/team-lead directly**: this
design **resolves IDEA-178's "why it matters" concern (the mislabel) as a
display-layer read, without needing IDEA-178's proposed precedence
change.** IDEA-178 asked to change which table `american_legion` resolves to
(refine precedence so a reserve-age signal can override `ngb` and select
`nrbl`) — a resolution-layer change the operator's ruling makes unnecessary,
since the two tables are now explicitly declared identical. What's still
needed is exactly the SAME reserve-age signal check IDEA-178 already specified
(15U-16U bracket, then summer sub-varsity name word), reused as a **display-only
overlay** that never touches precedence or which `PitchCountRules` object gets
applied. This is materially lower-risk than IDEA-178's original ask (no
resolution-path change means no regression surface on the rules themselves) and
worth relaying to PM, since it may change how IDEA-178 gets triaged (its
detection logic is still wanted; its precedence-change proposal likely is not).

## Explicitly Out of Scope (flag to PM, do not fold into this design)

- The optional footer echo mentioned above (Phase-2, only if the operator wants
  level visible even when a coach never reaches Most Likely Arms).
- A report-wide masthead/level badge — rejected above as unnecessary real estate
  given the level only informs one section.
- The exact `level_label` string for every recognized value (USSSA, Perfect
  Game, Little League, middle/elementary/college, every travel age bracket) —
  I've specified the PATTERN (bolded specific name, never a generic placeholder)
  and given representative examples; the full label map is an implementation
  table SE builds alongside `_LEAGUE_WARNINGS`.
- Any change to the existing `is_estimate` amber banner's own wording — it is
  narrower in scope after E-275's urgent correction (ambiguous free-text age
  range only) but its existing copy is still accurate for that narrower case, so
  I left it unchanged.
