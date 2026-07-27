# E-275 — SE execution answers for audit findings F4, F6, S2, S6

**Written by software-engineer, 2026-07-27, consultation mode (no implementation files
touched).** Requested by team-lead so the answers survive PM's handover to a fresh instance.

Every claim below was produced by EXECUTING `src/reports/starter_prediction.py`, not by
reading it. Harnesses are in the session scratchpad (`h1`-`h8`); the executed facts are
restated here because the scratchpad is session-local and this file is not.

**Citation form for all four answers** (TN-7 demands an execution reference, not a comment
reference):

> Source: software-engineer execution against `src/reports/starter_prediction.py`
> at worktree `epic/E-275`, 2026-07-26/27 — `detect_league_level` and `_is_excluded`
> driven directly. Not sourced to the `_SUMMER_SEASON` comment block.

---

## F4 — the consecutive-days axis: the auditor's structural reasoning is CORRECT

**Confirmed: the auditor's structural observation and my execution agree.** The auditor
observed that the consecutive-days code sits inside the generic `_is_excluded` gate rather
than a league branch, and correctly declined to conclude behavior from that. Executed, the
behavior matches the structure.

**The universal stands unhedged. OQ-1 resolves "stands as written."**

Two independent grounds:

**1. Structural — it cannot be league-gated even in principle.** The rule reads two
module-level constants, `_NSAA_CONSECUTIVE_DAYS_MAX_APPEARANCES = 2` and
`_NSAA_CONSECUTIVE_DAYS_WINDOW = 3`. It does not read the `rules` argument, and it could
not: `PitchCountRules` declares exactly two fields, `max_pitches` and `rest_tiers`. **There
is no consecutive-days field for a league to vary.** Making it league-specific would require
a schema change to the dataclass.

**2. Executed — driven against all six rule constants.** Sentinel: appearances on ref-2
(20 pitches) and ref-1 (15 pitches). Both counts are ≤30, so every table requires 0 rest
days and the rest tiers cannot mask the result. All six —
`NSAA_PRE_APRIL`, `NSAA_POST_APRIL`, `NSAA_SUBVARSITY`, `LEGION`, `NRBL`,
`PITCH_SMART_15_18` — returned `excluded=True` with the identical reason string
`'2 appearances in last 3 days -- max 2 per 3-day period'`. Control with only one
appearance inside the window: not excluded under any of the six.

**The full axis enumeration**, since the universal quantifies over axes:
`_is_excluded` (`:625-692`) has **seven** decision branches. Four are cannot-evaluate paths
returning NOT-excluded: no appearances (`:626`), missing `game_date` (`:631`), unparseable
date (`:633`), negative rest interval (`:639`). **Three can exclude**: null pitch count on
the most recent game day (`:648`), rest-tier compliance (`:654-673`), consecutive-days
(`:675-690`). **Exactly one of the seven — rest-tier compliance — reads `rules` at all.**

The null-pitch-count branch is a third exclusion axis that neither the epic nor the audit
had enumerated. It is league-blind, so it does not qualify the universal, but any claim
about exclusion behavior should quantify over three axes, not two.

**Exhaustive counterexample search.** 478 synthetic profiles covering every pitch count at
and around each tier boundary (including `None` and 0), rest offsets 0-5 days, all
two-appearance combinations (exercising doubleheader aggregation and the consecutive-days
window together), and three-appearance profiles inside the window — so all three exclusion
axes are exercised, not just the tiers.

```
NSAA_PRE_APRIL  excludes but LEGION does NOT :  0
NSAA_POST_APRIL excludes but LEGION does NOT :  0
LEGION excludes but NSAA_PRE_APRIL does not  : 35   (non-vacuity)
LEGION excludes but NSAA_POST_APRIL does not : 21   (non-vacuity)
smallest witness: a 46-pitch outing with 1 day rest
```

The witnesses matter as much as the zero: they show the relation is strictly one-directional
somewhere, so the universal is not vacuously true from two tables behaving identically.

**Method correction, recorded deliberately.** The first pass searched all three NSAA tables
and returned 22 apparent counterexamples — every one `NSAA_SUBVARSITY`, which is the
stricter table and is **never a source or destination of the reorder**. The search had been
scoped to a comparison the fix cannot produce. Re-running the transition set confirmed the
reorder's only transition is `nsaa_varsity → legion`. Rescoped to the two tables an arm can
actually move between, the count is 0. *A count is only as good as the population it was
computed over, and that population is the part a reviewer cannot see from the number.*

**Naming caveat for TN-7.** The constants are `_NSAA_`-named while applying unconditionally
to Legion, NRBL and the Pitch Smart estimate. The function's own docstring (`:614`) says the
opposite of the name — *"Check pitch count rules and consecutive-days rule for any league"* —
and **the docstring is the accurate one**. The name is why this looked like an open
question. Same prose-versus-behavior defect class the epic is already fixing.

---

## S2 — the measured figure: FOUR items, not three

**The epic's "three pitch bands" understates the measured result, and the auditor is right
that it matches the forbidden comment block rather than the measurement.**

Measured, driven at every count 1-130 via `_is_excluded`:

```
NSAA_POST_APRIL vs LEGION: strictly less rest at 46-50, 61-70, 81-90        (three bands)
NSAA_PRE_APRIL  vs LEGION: strictly less rest at 46-50, 61-70, 81-and-above (unbounded)
neither NSAA table requires MORE rest than LEGION at any count 1-130
```

**Verbatim for Background:**

> `nsaa_varsity` requires strictly less rest than `legion` at three pitch bands post-April
> — 46-50, 61-70 and 81-90, one day less at each — and pre-April at those same two lower
> bands plus **every count from 81 upward without an upper bound**, because
> `NSAA_PRE_APRIL` has no tier above 90 and `_is_excluded` clamps any count past the top
> tier to that tier's rest days rather than excluding. At no pitch count in 1-130 does
> either NSAA table require more rest than `legion`.

**On the fourth item's shape.** Coach's amendment says "plus the top tier pre-April", which
is directionally right but still bounded-sounding. The measured band is **unbounded above**
— I tested to 130 and the gap persists, because both tables clamp and the clamp values
differ (3d vs 4d). If the epic states a range, `81-105` is wrong (that upper bound comes
from Legion's top tier, and Legion clamps too). State it as "81 and above".

**Do not state the daily-cap difference as a mechanism** — see S6. `PitchCountRules.max_pitches`
is never read by the exclusion gate, so "post-April permits 110 vs Legion's 105" is true of
the tables and false of the engine. TN-8 already drops it; this is the executed reason why.

---

## F6 — AC-7: the auditor is right, the proposed row works, and there is a stronger one

**Executed. The "wrong implementation" was actually built** — a `detect_league_level`
variant that consults the four Legion name patterns *before* the age-bracket ladder,
which is precisely what AC-7 says it catches.

| row | today | post-fix | wrong impl | verdict |
|---|---|---|---|---|
| `Wexlom 14U Legion Varsity` (AC-7 row 1) | `youth_travel` | `youth_travel` | `legion` | **DISCRIMINATES** |
| `Quorrin 17U Post 41 Varsity` (AC-7 row 2) | `legion` | `legion` | `legion` | **CANNOT FAIL** |
| `Quorrin 14U Post 41 Varsity` (auditor's proposal) | `youth_travel` | `youth_travel` | `legion` | **DISCRIMINATES** |

All three recorded values resolve exactly as the audit states. **The auditor's proposed row
works.** PM can adopt the suggested fix as written.

**A sharper general statement than the audit's row-specific one.** The 17U row's problem is
not particular to `post \d+` — I checked `Wexlom 17U Legion Varsity` too, and it also cannot
fail (`post-fix=legion`, `wrong=legion`). **Any 17U-or-above row is inherently
non-discriminating for this defect, for every Legion pattern**, because the bracket ladder
resolves 17U+ to `legion`, which is the same value the wrong implementation returns. No
rewording makes a 17U row a guard. So "keep the 17U row and re-label it bin coverage, not a
guard" is exactly right, and the alternative the audit floats — asserting the resolution
*source* — is the only thing that would change that.

**A stronger third row than the proposal, if PM wants it.** `Quorrin 16U Post 41 Varsity`
→ `nrbl` (wrong impl: `legion`) **also discriminates**, and it is better on two counts:

1. The auditor's 14U row puts both discriminating rows in the same `youth_travel` bin. The
   16U row discriminates while covering a **third** bracket bin (`nrbl`), which satisfies
   the AC's own "two bracket bins" requirement with actual guard rows rather than one guard
   plus one bin-coverage row.
2. 15U-16U is the bin **adjacent** to the legion floor (`_BRACKET_LEGION_MIN = 17`), so an
   off-by-one in that constant surfaces there and nowhere else. `Quorrin 15U Post 41 Varsity`
   → `nrbl` likewise discriminates and pins the lower edge.

Recommendation: adopt the auditor's `14U Post 41` row **and** add `16U Post 41 → nrbl`. Both
discriminate; together they give `post \d+` guard coverage in two bins and pin the bracket
floor's adjacent boundary. Neither disturbs any recorded value.

For completeness, other verified discriminating rows: `Quorrin 12U Post 41 Varsity` →
`youth_travel`, `Wexlom 16U Legion Varsity` → `nrbl`, `Wexlom 12U Legion Varsity` →
`youth_travel`.

**Note:** none of the six rows changes value under the reorder itself (`today` == `post-fix`
in every case). They are guards against a mis-implementation, not change rows — AC-7 should
be labeled GUARD, and its rows are not fail-first candidates for the reorder.

---

## S6 — AC-1's "literal maximum": the gate reads `RestTier.max_pitches`, never `PitchCountRules.max_pitches`

**Answer: the exclusion gate reads the TIER-level field. The rules-level field is never
consulted by any gate.**

Both fields exist:
```
PitchCountRules.__dataclass_fields__ = ['max_pitches', 'rest_tiers']
RestTier.__dataclass_fields__        = ['min_pitches', 'max_pitches', 'rest_days']
```

Every `.max_pitches` read in `src/`:
```
:147  f"NSAA Pitch Count Rules (max {rules.max_pitches} pitches/game):"   <- DISPLAY only
:151  f"{tier.min_pitches}-{tier.max_pitches:<9} {tier.rest_days}"        <- DISPLAY only
:657  if tier.min_pitches <= total_pitches <= tier.max_pitches:           <- GATE (tier)
:665  if total_pitches > max_tier.max_pitches:                            <- GATE (tier)
```

`'rules.max_pitches' in inspect.getsource(_is_excluded)` → **False**. Both `:147` and `:151`
are inside `format_nsaa_rest_table`, a prompt-formatting helper.

**Executed discrimination** (not inferred from the greps):

- **Mutate `PitchCountRules.max_pitches` 105 → 60**: required-rest curve **identical at all
  130 counts**. No behavioural change. The rules-level cap is inert.
- **Mutate a `RestTier.max_pitches` 60 → 55** (the 46-60 tier): curve **changes at counts
  56-60** — from 2 days required down to **0**.
- **Mutate the TOP `RestTier.max_pitches` 105 → 200**: no behavioural change, because the
  fall-through clamp already applies the top tier's rest days above 105.

**Verbatim text for AC-1's required comment, sourced to execution** — supplied so PM does
not have to compose it and risk the next unverified prose claim:

> `PitchCountRules.max_pitches` is a DISPLAY value, not an enforced cap. The exclusion gate
> (`_is_excluded`) reads only `RestTier.max_pitches`, to select a rest tier and to detect a
> count past the top tier; `rules.max_pitches` is read nowhere except
> `format_nsaa_rest_table`'s prompt string. Verified by execution: setting this field to 60
> leaves the required-rest curve unchanged at every count 1-130. Pinning it guards the
> constant's integrity, NOT any enforced behavior.

**A finding that strengthens story 02's justification, from mutant B.** Narrowing one tier's
`max_pitches` created a **gap** in the tier table (56-60 matched no tier), and the
`for/else` fall-through only fires when the count exceeds the **top** tier's max. So counts
falling in a mid-table gap silently receive `required_rest = 0` — **a malformed tier table
under-rests silently rather than erroring**. That is a concrete reason the literal pins are
worth having: a tier-boundary typo produces a 0-rest recommendation, not a crash, and no
existing test would catch it on `NRBL` or `PITCH_SMART_15_18`.

### The malformed-table hazard — LATENT, not live (executed 2026-07-27)

**No shipped table has a gap. This is not a live defect.** All six rule constants were
audited for contiguity — first tier starts at 1, and every tier's `max_pitches + 1` equals
the next tier's `min_pitches`:

```
NSAA_PRE_APRIL     (1,30,0)(31,50,1)(51,70,2)(71,90,3)             contiguous 1..90   True
NSAA_POST_APRIL    (1,30,0)(31,50,1)(51,70,2)(71,90,3)(91,110,4)   contiguous 1..110  True
NSAA_SUBVARSITY    (1,30,1)(31,50,2)(51,70,3)(71,90,4)             contiguous 1..90   True
LEGION             (1,30,0)(31,45,1)(46,60,2)(61,80,3)(81,105,4)   contiguous 1..105  True
NRBL               (identical to LEGION)                            contiguous 1..105  True
PITCH_SMART_15_18  (identical to LEGION)                            contiguous 1..105  True
```

So the hazard is **purely "someone edits badly"** — a future tier-boundary typo, not
anything shipping today.

Mechanism, confirmed by execution on a deliberately gapped table (LEGION with its third
tier narrowed to 46-55):

```
counts 56-60 on the GAPPED table     -> [0, 0, 0, 0, 0] days required   SILENT ZERO
counts 56-60 on the well-formed table -> [2, 2, 2, 2, 2] days required
```

The `for/else` fall-through guards only `total_pitches > max_tier.max_pitches` — the TOP
tier. A count in a mid-table gap satisfies neither the loop nor the fall-through, so
`required_rest` keeps its initialiser of `0`.

Benign boundary cases, for contrast: `p=0` and negative counts also match no tier and yield
0 required rest, which is correct — the fall-through's `total_pitches > 0` guard is what
makes those safe.

**Why this is more than a footnote to S6.** The literal pins are not housekeeping about
constants drifting apart. On the two constants that lack pins, a tier-boundary typo produces
a **zero-rest recommendation on a real arm** with a green suite and no error — the exact
direction the project's standing under-rest principle exists to prevent.

**A separate idea is probably warranted (PM owns the call).** The pins detect a *changed*
value on the constants that have them; they do not defend the *gate*, which will keep
accepting a malformed table from any source, including tables that do not exist yet. The
structural fix is different in kind — a contiguity invariant asserted at import, or a gate
that refuses an unmatched count instead of defaulting to 0. That outlives this epic and
applies to every rule table, so it does not belong inside story 02's scope.

---

## ⚠ FOUR-PATTERN FIGURES SUPERSEDED — full re-sweep under the narrowed ruling (2026-07-27)

Coach narrowed the ruling to **two** patterns (`legion`/`american legion`, `post \d+`);
`seniors`/`juniors` are deliberately unpromoted (TN-3, story 01 AC-4). **Every figure SE
produced before that narrowing assumed a four-pattern move.** All reorder-dependent figures
were re-enumerated by walking the prior reports — not by recalling which ones felt
pattern-dependent — and re-run. Three changed, three stand.

| figure | four-pattern | **narrowed (authoritative)** | status |
|---|---|---|---|
| 12,096-combination blast radius | 60 changed, 5 names | **36 changed, 3 names** | CORRECTED |
| ngb sweep (792 combinations) | 36 changed, 3 names | **24 changed, 2 names** | CORRECTED |
| SE's round-1 fail-first AC list | 6 assertions | **4 valid, 2 INVALID** | SUPERSEDED |
| Finding C season-discrimination table | 7 discriminate / 3 guard-only | **unchanged** | STANDS |
| sub-varsity residual (7 sentinels) | all unchanged by reorder | **unchanged** | STANDS |
| transition set (scopes the 478-profile search) | `{(nsaa_varsity, legion)}` | **identical** | STANDS |

Names that move under the narrowed ruling: `American Legion Varsity`, `Legion Varsity`,
`Post 77 Varsity`. The two that no longer move are the `Seniors` and `Juniors` names.
36 is producible: 3 names × 3 non-summer seasons × 4 name-path-reaching `age_group` values.
24 is producible: 3 empty-`ngb` values × 2 moving names × 2 non-summer seasons × 2
name-path `age_group` values.

**The consequential one is the third row, and it was NOT among the two SE had flagged.**
SE's round-1 report proposed six assertions as "FAIL now and pass after the fix". Under the
narrowed ruling **two of the six are invalid** — they fail now and *still* fail after:

```
Zephyr Seniors Varsity   today=nsaa_varsity  four-pattern=legion  narrowed=nsaa_varsity
Zephyr Juniors Varsity   today=nsaa_varsity  four-pattern=legion  narrowed=nsaa_varsity
```

Pinned as written, those two would have been fail-first ACs that never pass. **The epic is
already correct** — story 01 AC-4 carries both names as GUARD rows asserting they stay
`nsaa_varsity`, and its note says outright that they *"changed role from CHANGE to GUARD
when the ruling narrowed; do not inherit a fail-first expectation for them from any earlier
list."* That instruction is aimed at exactly the superseded SE list above. The four
surviving CHANGE assertions are the `american legion`, `legion` and `post N` rows.

**Mechanism worth recording, because it is the session's fourth instance of one shape.** No
figure here was ever wrong about what it measured; each was produced under one set of
premises, stayed true of those premises, and was quietly attached to a different question
after the premises moved. `60` was a correct measurement of a reorder that is no longer the
reorder. Same shape as the seed's `81-105`, api-scout's `12 sessions`, and SE's own
`18-team sample` restatement. **Every one was caught by re-deriving, never by re-reading** —
and the two SE named unprompted were not the whole list, which is why the enumeration was
walked rather than recalled.

## Cross-reference: the constant population (settles an earlier relay conflict)

There are **six** `PitchCountRules` constants: `NSAA_PRE_APRIL` (`:111`), `NSAA_POST_APRIL`
(`:121`), `NSAA_SUBVARSITY` (`:170`), `LEGION` (`:188`), `NRBL` (`:208`),
`PITCH_SMART_15_18` (`:227`).

**The byte-identical set is exactly three** — `LEGION`, `NRBL`, `PITCH_SMART_15_18` — which
matches the epic. Verified by comparing loaded objects: all three `==` each other, all three
`is not` each other, observed curves identical 1-130.

An earlier SE report said "two of four have literal pins". That referred to a **pin-coverage
audit set**, not the byte-identical set, and the set was never named — SE's reporting error.
Full coverage over all six:

| constant | byte-identical trio | literal pin |
|---|---|---|
| `LEGION` | yes | **YES** — `test_starter_prediction.py:1471-1481` |
| `NRBL` | yes | **no** |
| `PITCH_SMART_15_18` | yes | **no** |
| `NSAA_SUBVARSITY` | no | **YES ×2** — `test_league_detection.py:416-423`, `:945-953` |
| `NSAA_PRE_APRIL` | no | **no** |
| `NSAA_POST_APRIL` | no | **no** |

Story 02 should pin `NRBL` and `PITCH_SMART_15_18` — the two members of the trio that lack
pins. `NSAA_PRE_APRIL` / `NSAA_POST_APRIL` are also unpinned but sit outside the
divergence-tripwire rationale; recorded, not proposed.
