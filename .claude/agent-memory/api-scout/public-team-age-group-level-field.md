---
name: public-team-age-group-level-field
description: age_group on GET /public/teams/{public_id} is a polymorphic three-family LEVEL field (school/travel/recreational) carrying high_varsity/high_junior_varsity/high_freshman — CONFIRMED on non-managed opponents (25/25) and 100% populated across 91 teams; operator-entered, and its enum is not provably exhaustive
metadata:
  type: reference
---

# `age_group` is a LEVEL field, not an age bracket (verified live 2026-07-25)

`GET /public/teams/{public_id}` returns a top-level `age_group` string. **The name is
misleading.** It is not merely an age bracket — it is a **polymorphic level field** whose
value is drawn from one of three disjoint vocabularies, and for school teams it carries an
explicit varsity / JV / freshman token.

## The three families

| family | `competition_level` (auth-only) | `age_group` values |
|---|---|---|
| **school** | `school` | `elementary`, `middle_12U`, `middle_13O`, `high_freshman`, `high_junior_varsity`, `high_varsity`, `college` |
| **travel** | `club_travel` | `NNU` brackets — observed live: `8U 9U 10U 11U 12U 13U 14U 15U 18U` |
| **recreational** | `recreational` | free-text ranges rendering as `"Between 13 - 18"` |

Union is roughly 22 values, which is the likely referent of the operator's phrase
"levels of > 15" (i.e. the picker has >15 options — NOT a numeric level above 15;
the numeric reading was refuted by the sample). That phrasing was never confirmed.

## Provenance — GameChanger's own client code, NOT inference

The school family is **exhaustively enumerated** in GC's public web bundle
(`https://web.gc.com/static/js/index.*.js`, fetched unauthenticated). The display mapper:

```js
if (e.competition_level === Ja.SCHOOL) switch (e.age_group) {
  case "elementary":       return "Elementary School";
  case "high_varsity":
  case "high_junior_varsity":
  case "high_freshman":    return "High School";
  case "middle_12U":
  case "middle_13O":       return "Middle School";
  case "college":          return "College";
}
```

and the team-creation picker gives the labels:

```js
const dl = { [xt.HIGH_FRESHMAN]:"Freshman", [xt.HIGH_JUNIOR_VARSITY]:"Junior Varsity", [xt.HIGH_VARSITY]:"Varsity" };
```

**The bundle is the authoritative source for this enum.** Re-fetch it (hashed filename
changes per deploy — find it via `src=` in the team page HTML) rather than guessing values.
The bracket/range families' string literals are NOT in that bundle (generated dynamically);
those were observed empirically off live responses.

## Where it lives — zero extra cost

- **`GET /public/teams/{public_id}`** — top level, **no auth**. This is the response the
  report generator already fetches and parses. Available for teams we do **not** manage:
  an 18-team sweep of `membership_type='tracked'` opponents returned a populated
  `age_group` on **all 18**.
- `GET /teams/{gc_uuid}` (auth) — same field, plus `competition_level`.
- **`competition_level` is authenticated-ONLY — not on the public profile.** Mostly does
  not matter: `age_group` is self-disambiguating by shape (`high_*`/`middle_*` ⇒ school,
  `NNU` ⇒ travel, `Between N - M` ⇒ recreational).
- **NOT available from `POST /search`** — hits carry no `age_group`/`competition_level`
  at all (see [[search-endpoint-notes]]). The public profile is the only cheap source.

## It discriminates — verified live

`GET /me/teams`, own program, spring 2026, `competition_level: "school"`:
`high_varsity` ×1, `high_junior_varsity` ×1, `high_freshman` ×2. That is exactly the
varsity/JV/freshman split that `detect_league_level`
(`src/reports/starter_prediction.py`) otherwise guesses from team-name keywords.

**Parser gap worth knowing:** that function's `age_group` branch tests only `\d+U\b` and
`\b\d+\s*-\s*\d+\b`. Every `high_*` value matches **neither**, so school teams fall through
to name-keyword matching while the field naming their level sits unread in the same response.

## CAVEAT A — operator-entered, not authoritative about the league

`age_group` is whatever the opposing coach **selected** when creating the team in
GameChanger. It is authoritative about that selection, **not** about the team's actual
league classification. It can be wrong, stale, or left at a default. Treat it as a strong
signal, never as ground truth.

## ~~CAVEAT B~~ — CLOSED POSITIVE 2026-07-25 (E-274 discovery)

**Resolved; do not re-probe.** The original caveat (varsity/JV seen only on our own teams,
so public exposure was extrapolated) is now **disproven as a limitation** — all three HS
levels ARE returned on the public profile of teams we do **not** manage.

Route: `/me/teams` → our school teams → `/teams/{id}/opponents` → `progenitor_team_id`
→ `GET /teams/{progenitor}` (yields `public_id`) → `GET /public/teams/{public_id}` (unauth).

- **25 non-managed opponent public profiles: 25/25 present-and-populated.**
  `high_junior_varsity` ×19, `high_varsity` ×6. Zero null / empty / absent / non-200.
- **0 auth-vs-public mismatches** — the public value always equals the authenticated one.
- Confirmed one public profile per distinct value: `high_varsity`, `high_junior_varsity`,
  and `high_freshman` all directly observed on non-managed teams.

## Population rate — 0% absent (measured 2026-07-25)

Across **73 distinct opponents** of our four school teams: `age_group` populated **73/73
(100%)**; zero empty-string, zero null, zero key-absent. With the earlier 18-team sweep that
is **91 distinct teams, no gaps**. It is a PRIMARY signal, not a narrow enhancement.

**Family mix is schedule-dependent — do not overgeneralize.** For the HS *school* schedule
it is 100% school family (`high_junior_varsity` ×29, `high_varsity` ×22, `high_freshman` ×22
— zero travel, zero recreational). The `14U`/`18U`/`"Between 13 - 18"` values come from the
operator's **legion/summer** teams, a different schedule.

**The real coverage ceiling is UPSTREAM, not this field.** 61 of 144 visible opponent
entries (**42%**) have no `progenitor_team_id` — manually-typed opponents with no reachable
`public_id` at all (consistent with `get-teams-team_id-opponents.md:148`: HS varsity programs
are often absent from GC's searchable index). That constrains opponent RESOLUTION, not the
level signal: conditioned on a report being generatable from a `public_id`, population is
100%. Never quote a degraded coverage figure for this field on account of the 42%.

## Parser shape hazards (measured 2026-07-25)

- **No casing or whitespace variants.** All 73 school values are exactly
  lowercase-with-underscores (`value.lower() == value` and `value.strip() == value`).
- **No off-enum values observed.** Explicitly checked for and NOT found anywhere:
  `high_sophomore`, `high_jv`, `high_junior`, `varsity`, `jv`.
- **The rec form is a single observation.** Only the literal `"Between 13 - 18"` has ever
  been seen; no rec team appears on the HS schedule. Do NOT treat `"Between N - M"` as a
  validated pattern.
- **The web-bundle enum is NOT provably exhaustive.** What was extracted is the display
  mapper's `switch` (7 school values) plus the creation picker (3 HS options). The `xt` enum
  OBJECT definition was never located — searched `index.js` plus `gamechanger-sabertooth`,
  three `app-chunk-*`, `react-and-state`, `gamechanger-auth`; the value strings appear only
  inside the switch. Two signs it is open: the mapper has a `default:` branch (GC itself
  handles unrecognized values), and the picker offers only 3 of the 7, so other values must
  arrive by non-creation paths. **A parser must use an allowlist + explicit unknown
  fallback, and must not raise on an unrecognized value.**

## Additional limit — GameChanger has no "reserve" level

The HS enum is three values. LSB's four classifications (freshman / reserve / JV / varsity)
do **not** map 1:1 — note the two `high_freshman` teams above, almost certainly Freshman +
Reserve collapsed. Harmless for pitch-rest rules (both sit in `nsaa_subvarsity`), but real.

## Doc corrections — LANDED 2026-07-25. Nothing owed.

All of it is now in `docs/api/`; **read the docs, do not re-derive from this file.**
`docs/api/endpoints/get-public-teams-public_id.md` carries the canonical section
("The `age_group` level field") — three-family table, bundle provenance, the non-managed
evidence, population rate, the 42% upstream entry bound, and the parser requirements.
The other five files that mention `age_group` now point at it rather than restating:
`get-teams-team_id.md`, `get-me-teams.md`, `get-me-archived-teams.md`,
`get-organizations-org_id-teams.md`, and `post-search.md` (the negative: search carries no
level field at all).

## The joint distribution vs TEAM NAME — measured n=73, 2026-07-25 (E-274 fork)

**Read this before anyone argues about an `age_group`-vs-name tie-break.** Measured over all
73 distinct coach-linked opponents of the four 2026 school teams (146 entries, 83 linked,
63 manual = **43% manual**; the 73 reproduce the peer probe's mix exactly).

- **SPRING: 73/73 also carry a level word in the NAME** (72/73 an HS-tier word).
  **⚠ I generalized this into "the signals are ANTI-CORRELATED" and that was WRONG.**
  A second run over a SUMMER population (134 distinct linked opponents of the five 2026
  non-school teams; 223 entries, 167 linked, 25% manual) found **16 school-family teams of
  which 3 carry NO level word** — all 3 resolve `unknown` today, so `age_group` is their ONLY
  level signal. Mechanism: they are **school programs playing summer ball under a SPONSOR
  name** (no school name, no tier word), while `age_group` still reports the true tier.
  **The redundancy was a property of the spring schedule's NAMING CONVENTION, never of the
  signals.** Lesson: a clean 100% on one population is exactly where over-generalization
  hides — PM demanded a second population and was right to.
- **"Reserve" maps DOWN, never up — now across TWO populations.** Combined 23 school-family
  Reserve-named teams: `high_freshman` ×20, `high_junior_varsity` ×3, **`high_varsity` ×0**
  (spring 15/2/0, summer 5/1/0). The recurring hypothetical "a Reserve team tagged
  `high_varsity`, so reading the field under-rests them" is **CONSTRUCTED — it does not
  occur.** The real team the hypothetical named is `high_freshman`.
- **Operational disagreement is 3/73, and `age_group` is right in all 3.** Fourteen teams
  "disagree" on tier LABEL (Reserve-named, `high_freshman`), but Reserve and Freshman both map
  to `nsaa_subvarsity`, so those collapse to zero real conflict. Running the live
  `detect_league_level` over the 73 (`ngb='[]'`, `season='spring'`) gives
  `nsaa_subvarsity` 48 / `nsaa_varsity` 22 / `unknown` 2 / `legion` 1 — **70/73 already agree**
  with the `age_group` answer. The 3 that differ: `"... Seniors 2"` → `legion` (wrong family;
  it is JV), and two `"JV1"` names → `unknown` (`\bjv\b` fails before a digit).
- **Zero cases move in the under-resting direction.** Reading the field is safety-neutral-or-
  better on this population.

**Caveat:** one program, one season, one state — and the `detect_league_level` figure is a
SIMULATION of the function (I passed `program_type=None`/`classification=None`); if the real
call site passes a non-null `classification` the ladder may short-circuit earlier. Treat 70/73
as a measurement of the function, not of the pipeline.

**OQ-5 (season presence) ANSWERED 2026-07-25 — the worry was INVERTED.** 73 public-profile
calls: `team_season` present + non-null, `season` key present, `year` key present — **73/73**,
value `"spring"` ×73 / `2026` ×73, **0 absent/null/empty**. So "season-absent with `age_group`
present" is **0 of 73**, not the modal case. Spin-off: the auth-vs-public `age_group` match is
now **73/73** (was a 7-team sub-check).

**⚠ Correction to my own OQ-5 spin-off claim.** I also wrote "`season` is CONSTANT within the
school family." That was another spring-only over-generalization. The summer run found **13
school-family teams carrying `season: "summer"`** (and 4 non-school teams carrying
`"spring"`), and **ALL THREE HS values appear on a `"summer"` team** — `high_varsity` ×7,
`high_freshman` ×5, `high_junior_varsity` ×1. **`season` and `age_group` are INDEPENDENT
AXES** — season = when they play,
age_group = their level. Never infer family from season, or season from family. Season
PRESENCE is still reliable (0 absent across both populations).

**Also**: no high-school opponent report has EVER been generated in the dev DB — all 18 report
target teams are legion/travel/reserve/summer. So the 43%-unreachable bound is **untested in
practice**, in either direction.

## Two adjacent facts from the same probe, worth not re-discovering

- **`ngb` has TWO empty forms and one is not valid JSON.** Observed `"[]"` on 5 of 7 and the
  **empty string `""`** on 2 of 7. `json.loads("")` raises — a naive double-parse crashes on
  the `""` form. And `"[]"` is truthy, so a bare truthiness test does not detect "no
  affiliation" either. Treat empty-or-unparseable as an empty list.
- **The public profile key set is stable and closed**: `age_group, avatar_url, id, location,
  name, ngb, player_count, sport, staff, team_season` — identical across all 7 sampled.

## The SUMMER/LEGION population — n=51, 2026-07-25 (the complementary sample)

The 73-team sample above is one HS *spring* schedule. A separate probe hit the 51
`public_id`-bearing teams in the dev DB's `teams` table (the actual report-target
population: legion/travel/reserve/summer). **51/51 HTTP 200**, identical 10-key key set,
`team_season` always `{record, season, year}`, zero absent/null/empty `age_group`. This is
the population where the level field is WEAKEST, and it inverts several spring-sample
conclusions:

- **`season` DOES discriminate here**: `summer` ×48 / `spring` ×3 (years 2026 ×50, 2025 ×1).
- **School-family `age_group` with `season="summer"` is REAL and not rare — 6 of 51**
  (`high_freshman` ×5, `high_varsity` ×1). A summer Legion/NRBL-tier team carrying a
  school-family level token is a live shape; do not assume school ⇒ spring.
- **`age_group` vocabulary is CLOSED on this sample.** Nine distinct values, ALL inside
  GC's create-team picker set: `Between 13 - 18` ×19, `18U` ×9, `15U` ×6, `high_freshman`
  ×6, `17U` ×4, `14U` ×3, `16U` ×2, `high_varsity` ×1, **`18O` ×1**. `18O` is the first live
  observation of the travel over-18 value. Combined with the 91-team spring corpus that is
  **142 teams with no off-picker value** — the "does the API emit values the UI cannot
  produce?" question is unanswered-but-unfalsified, NOT open evidence of divergence.
- **The rec range form is no longer a single observation** — `"Between 13 - 18"` ×19 here.
  Still only ONE distinct literal ever seen, so the `"Between N - M"` *pattern* remains
  unvalidated; the literal is now well-attested.
- **`ngb` is populated and dominant on this population**: `["american_legion"]` ×35,
  `[]` ×10, `["usssa"]` ×4, `""` ×2. Because a recognized `ngb` outranks `age_group` in
  `detect_league_level`, the level field is never even READ on 39 of 51 teams here — the
  opposite of the school population, where `ngb` is empty and `age_group`/name decide.
- **Name-vs-`age_group` anti-correlation does NOT hold here.** 10 of the 51 carry no level
  word in the name at all (sponsor-only names like "Superior Bingo", "Mings Restaurant").
  The spring sample's "73/73 also carry a level word" is a school-schedule artifact.

## THIRD population — n=160 live profiles, 2026-07-25 (E-274 partition-3 probe)

184 name-only DB teams resolved via `POST /search` → public profile (160 reached a profile;
22 AMBIGUOUS, 2 NO_HITS). This is a MIXED, mostly out-of-state population (MN/SD/KS/MO/CO/TX,
one Canadian), not one program's schedule. Confirms and extends the above:

- **`age_group` enum STILL CLOSED — zero off-vocabulary values at n=160.** Thirteen distinct
  values, every one inside the known three-family vocabulary: `14U` ×46, `18U` ×25, `17U` ×22,
  `Between 13 - 18` ×18, `15U` ×17, `16U` ×10, `high_varsity` ×7, `high_freshman` ×5, `18O` ×3,
  `Over 18` ×2, `high_junior_varsity` ×2, `13U` ×2, `Under 13` ×1. Running corpus is now
  **~300 teams with no off-picker value.**
- **`18O` is no longer a single observation** (×3 here), and the rec family gained TWO NEW
  LITERALS beyond `"Between 13 - 18"`: **`"Over 18"`** ×2 and **`"Under 13"`** ×1. So the rec
  vocabulary is a fixed 3-literal set (`Under 13` / `Between 13 - 18` / `Over 18`), NOT a
  free-text `"Between N - M"` template — the template reading is now positively disconfirmed
  for the two open-ended ends.
- **`ngb` empty-string form reconfirmed at scale**: `["american_legion"]` ×57, `"[]"` ×54,
  `["usssa"]` ×30, **`""` ×12**, `["perfect_game"]` ×7. The `""` form is ~7.5% of profiles —
  common enough that a naive `json.loads` will hit it in normal operation.
- **`age_group` is freely WRONG on this population, unlike the spring school sample.** A
  Legion senior team tagged `Under 13`; a spring HS Reserve team tagged `14U`; a summer
  `high_freshman` team named `Marshall VFW Orange 15U`. Operator entry is unconstrained by the
  team's actual level (CAVEAT A, now with teeth).
- **The school-family parser gap (line ~75) is MEASURED here: 14 school-family profiles, and
  `detect_league_level` reads the field on ZERO of them.** All 14 outcomes came from the NAME
  word or an `ngb`; 3 landed on a non-NSAA league (`legion` ×2, `nrbl` ×1) with the correct
  tier sitting unread in the same response.
- **New adjacent hazard — the `\d+U` bracket outranks a sub-varsity NAME word AND the season,
  so an operator-entered `18U` on a spring/winter HS team yields `legion`/105 instead of
  `nsaa_subvarsity`/90** (`Lincoln Southeast Reserves` 18U/spring, `Westside JV` 18U/winter).
  This does NOT contradict the "zero under-resting" line in the spring sample — that measured
  READING `age_group` on school-family values; this is the bracket branch, a different path.

Method notes for a re-run: 349 requests at a 2.5 s floor ≈ 15 min for 184 teams; exact-name +
`season.year` narrowing resolves 87 uniquely and 73 by year, leaving 22 genuinely ambiguous
(common club names return up to 19 exact same-name hits across seasons). Search hits carry
`season` as a **dict** `{name, year}` — the public profile carries `season` as a bare string
with `year` FLAT (see [[public-team-profile-season-shape]]); do not copy one shape onto the
other. Search returns 0 hits for some plainly-named real teams (`Hastings Reserves`,
`Hastings Reserve` — both 0), so NO_HITS means "not in the index", never "does not exist".

## FOURTH population — n=163 live profiles, 2026-07-25 (E-274 partition-2 probe)

185 name-only DB teams (a different slice than partition 3; NE/MN/SD/ND/KS/MO/CO/TX/WY/AR/OK,
one Canadian) resolved via `POST /search` → public profile. 163 reached a profile; 20
AMBIGUOUS, 2 NO_HITS, **0 NON_TEAM** (this slice had no TBD/bracket placeholder rows at all).
Independently reconfirms partition 3 and adds three things:

- **`age_group` enum STILL CLOSED — zero off-vocabulary at n=163.** Eleven distinct values,
  all in-vocabulary: `14U` ×47, `18U` ×24, `Between 13 - 18` ×22, `16U` ×18, `17U` ×16,
  `15U` ×10, `high_varsity` ×9, `high_freshman` ×8, `high_junior_varsity` ×5, `18O` ×2,
  `13U` ×2. Combined running corpus **~460 teams, no off-picker value ever.**
- **`season` has a FOURTH literal: `"fall"`** (×2, both live, both travel-family). Observed
  distribution here: `summer` ×115, `spring` ×46, `fall` ×2 — and `winter` was seen in
  partition 3. So the vocabulary is at least {summer, spring, fall, winter}. **The comment in
  `src/reports/starter_prediction.py` above `_SUMMER_SEASON` ("Lowercase `summer` is the ONLY
  season token observed anywhere in the proxy corpus (api-scout, E-272 OQ-1)") is STALE** —
  behaviour is unaffected (all four route through the non-summer NSAA default, and
  `_KNOWN_NON_SUMMER_SEASONS` already lists spring/fall/winter), but the claim is no longer
  true and should not be cited as evidence of a closed season vocabulary.
- **`ngb` empty-string reconfirmed a third time**: `["american_legion"]` ×63, `"[]"` ×45,
  `["usssa"]` ×34, **`""` ×14 (8.6%)**, `["perfect_game"]` ×7.

Classifier-behaviour measurements from the same 163 (all label-only unless stated):

- **A recognized `ngb` outranking the `\d+U` bracket fires on 55 of 163 (34%).** 15U/16U +
  `["american_legion"]` → `legion` where the bracket alone gives `nrbl`; 13U/14U +
  `["usssa"]`/`["perfect_game"]` → `usssa`/`perfect_game` where the bracket gives
  `youth_travel`. The legion-vs-nrbl half is **numerically inert** (`LEGION`, `NRBL` and
  `PITCH_SMART_15_18` are byte-identical tables today), so this is a LABEL divergence, not a
  rest-day one. Do not report it as a safety finding.
- **The `usssa`/`perfect_game` half is NOT inert — it is a COVERAGE INVERSION.** Those two
  leagues map to `None` in `get_rules_for_league`, so a 14U team **with** an `ngb` gets NO
  pitch guidance while an identical 14U team with `ngb=[]` gets the `PITCH_SMART_15_18`
  labeled estimate. Having the affiliation signal makes the system strictly less helpful:
  **41 of 185 (22%) suppressed, and every one is `usssa` (×34) or `perfect_game` (×7).**
- **School-family + `season="summer"` → 105 instead of 90 (2 of 163).** A `high_freshman`
  team → `nrbl`/105 and a `high_junior_varsity` team → `legion`/105, both via the name word
  plus the summer season, with the school tier unread. This is the ONE direction that moves
  toward UNDER-resting a 9th-grade/JV roster. It may well be correct (a summer HS-age team is
  playing NRBL/Legion ball, not NSAA), but it is the case to put in front of the coach.
- Method caveat for the operator table: **4 of 163 resolved to a profile whose `year` is not
  the DB `season_year`** (2022, 2025, 2018, and one 2026-vs-2025) — all `exact_unique`, so
  year narrowing never ran. An `exact_unique` hit is NOT season-verified; treat those four
  rows' `age_group`/`ngb`/`season` as belonging to an older season of that name.

Related: [[public-team-profile-season-shape]], [[public-team-accept-header-inert]],
[[search-endpoint-notes]], [[search-opponent-import-regression]].
