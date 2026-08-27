# The Athlete Feedback Model

**Last updated**: 2026-08-27 · **Source**: concept sessions of 2026-08-15..27; v1.3.5
(2026-08-27, independent-verifier round): contact-profile denominators must name what they
count (batted balls, never "trips"); display rounding always from raw components; even-pool
median, deadband inclusivity, band cutpoints, barometer thirds, and the WHIP deadband
(0.10, replacing a vacuous 1.5 fallthrough) all pinned — a parameter only the builder knows
is unverifiable by definition; v1.3.4
(2026-08-26, operator rulings from the Mason Hiatt half-view finding): every lens is
per-team-season — no "primary season" scope anywhere — and the barometer's subject obeys the
§4 relative-standing floors (the 20-PA pool-membership floor never applies to the subject);
v1.3.3 (2026-08-26): empty sections omit entirely, machinery vocabulary banned on sheets,
Meeting Notes reduced to the single coach-fillable "Where to grow" block; v1.3.2
(2026-08-26): no-self-narration rule (no disclaimers or page furniture, operator ruling);
v1.3.1 (2026-08-25): Where-To-Grow blank and coach-owned per assistant-coach ruling, its
derivations relocated to the staff provenance page; barometer aggregate bounds (2026-08-22)

**Status: DRAFT v1.3.5 — 2026-08-27.** Governs every player-facing feedback artifact this project
produces, starting with the exit-meeting player sheet. The design intent: this document carries
the intellectual work — what may be said, to whom, on what evidence, in what words — so that
producing the sheets is deterministic work any competent model or plain script can execute.

Provenance: assistant-coach request and rulings (2026-08-14 → 2026-08-20), operator rulings
(2026-08-15 → 2026-08-22), a cold baseball-coach agent consult, two adversarial Codex reviews
(gpt-5.4 and gpt-5.6-sol, findings preserved at
`.project/research/2026-08-22-athlete-feedback-model-reviews.md`), and three instructive
failures of ad-hoc generation (a 9-inning reliever crowned "best ERA on the staff"; a
"walk rate dropped" claim built on a 22-PA half; statistician vocabulary on a teenager's sheet).

All names in this document are fictional.

---

## 1. Purpose and audience

The artifact is a 1–2 page per-player sheet for end-of-season exit meetings: the player's
season, honest comparison, and the raw material for a development conversation. The reader is
a 15–17-year-old athlete; secondary readers are parents and coaching staff. Delivery is
digital-first (one PDF per player), staff-mediated, introduced live in the meeting.

**The model carries the pedagogy** (operator ruling, 2026-08-22). The coach delivering it is a
PE teacher and a decent coach, not a sports psychologist or statistician. Every default in
this model must therefore embody best practice for growing young athletes on its own: the
sheet scaffolds a good development conversation rather than assuming the deliverer will build
one. Direct, not gentle (assistant-coach ruling: "there is some value in them hearing that
they are at the bottom") — but structurally incapable of piling on, overclaiming, or
prescribing.

## 2. Design principles

1. **A statistical difference is not a coaching judgment.** The machinery must never make weak
   evidence look authoritative (the sol review's central finding). Precision of presentation
   is capped by precision of evidence.
2. **Direct per claim, bounded in aggregate.** Any single statement may be blunt; the sheet as
   a whole may not hammer. Caps and consolidation, not euphemism.
3. **The sheet describes; the coach and player prescribe.** Automated output never selects a
   development priority. "Focus" is chosen in the meeting, by people.
4. **Nothing unverifiable is claimed.** No comparison against a pool we cannot prove is fair;
   no word ("league") bigger than the data behind it.
5. **Absence of a claim is a designed output.** "Too little playing time to compare" is a
   correct, complete answer — never an error state to be papered over.
6. **Facts are never suppressed** — but a raw number below its evidence floor is presented as
   a count, not a rate, because a displayed `.500` on 2 PA is itself an implied claim.

## 3. The claim matrix

Every clause of rendered text is one atomic claim with a type, and each type has its own gate.
Compound sentences are compositions of separately-gated claims.

| Claim type | Example | Gate | Auto-generated? |
|---|---|---|---|
| Recorded fact (count) | "36 games, 81 trips to the plate" | source integrity | yes |
| Estimated rate | "OBP .445" | denominator floor (§4), else render the counts instead | yes |
| Relative standing | "top group of the 11 eligible hitters" | rate gate + pool validity (§5) + deadband | yes |
| Temporal difference | "OBP .368 spring → .445 summer ▲" | trajectory gate (§4) | yes |
| Context/abstention | "mostly relief work — too few trips to compare the bat" | trigger conditions (§6) | yes |
| Evaluative | "this went well" | **coach approval** | no |
| Prescriptive | "this is your focus" | **coach + player, in the meeting** | no |
| Causal / character | "because you…", effort, attitude, potential | — | **never** |

Superlatives are permitted only on counts ("most innings on the staff", "led the team in
trips"), never on rates. A high rate renders as top-group standing, not "best".

## 4. Evidence gates (parameters table)

All thresholds are named parameters, provisional until the fixture suite (§9) has exercised
them, and changed only deliberately with rationale.

| Parameter | Value | Rationale / status |
|---|---|---|
| Rate display floor, batting | 20 PA | below: counts only ("11 hits, 6 walks in 18 trips") |
| Rate display floor, pitching | 6 IP | below: counts only |
| Relative-standing floor, batting | 40 PA | one on-base event moves OBP ~50 pts at 20 PA — provisional |
| Relative-standing floor, K%/BB% (pitching) | 50 BF | rates gated on their own denominator, not IP |
| Relative-standing floor, WHIP/FPS% | 10 IP / 50 BF | ERA is **excluded from standing entirely** (starter/reliever confound, tiny staff pools) |
| Fielding | descriptive only | no cross-position comparison; counts + FPCT with chances shown |
| Trajectory arrow floor | 60 PA each half | below: both numbers shown side by side, unmarked |
| Trajectory magnitude | ≥.080 OBP/SLG; ≥8 pts K%/BB%/QAB% | approximates 1 SD of the between-half difference at the floor — provisional |
| In-season window floor | 40 PA per half-season window | measured 2026-08-22 on full crawls: 6 of 10 spring / 9 of 11 summer regulars clear it — provisional |
| In-season window boundary | midpoint game date of the team-season | deterministic; pinned here so two builders split identically |
| Arc stats | OBP, K% | the two most stable headline rates; one arc, not one per stat family |
| Band deadband | .015 OBP/SLG; 1.5 pts rates | values this close to a cutoff render "around the team middle"; INCLUSIVE — a gap of exactly the deadband is "around" (pinned v1.3.5, from a live boundary case) |
| Team median, even pool | mean of the two middle values | pinned v1.3.5 — was builder-defined, so unverifiable from this doc |
| Band deadband, WHIP | 0.10 | pinned v1.3.5: the builder's fallthrough default was 1.5 — vacuous at WHIP scale, every arm rendered "around the middle"; 0.10 ≈ one extra baserunner per ten innings — provisional |
| Band cutpoints (pool ≥8) | deadband first, then: top group v ≥ Q3 (Tukey upper hinge, ties widen the band); above the middle Q3 > v > median; below the middle median > v > Q1; bottom group v ≤ Q1 | pinned v1.3.5 from the builder's constants report (direction flipped for lower-is-better stats) |
| Barometer thirds | equal-team weighting (each pool player weighs 1/(qualifying players on their club)); weighted fraction-better ≥ 2/3 → top, ≤ 1/3 → bottom, else middle; no deadband — the §5 sensitivity check plays that role | pinned v1.3.5 from the builder's constants report |
| Display rounding | one rounding, from raw counting components; ties round half-even | never re-round a source's already-rounded rate column (v1.3.5: three sheets shipped double-rounded 1-dp rates); half-even matches GameChanger's own columns (.8125 → .812) |
| Four-band minimum pool | 8 qualified players | below: two bands only (above/below the team middle) |
| Standing-claim caps | ≤3 stood-out, ≤2 below-middle | one claim per correlated family (§7) |
| Went-Well total cap | 4 items (standing + count-facts + trends combined) | v1.3; count-facts were unbounded before |
| Pool membership | subject INCLUDED in his own team pool | pinned v1.2 (v1 build had to guess) |
| Family tie-break | first-listed stat in the family wins | pinned v1.2 |
| Workload-lead heuristic | mound leads when season BF > season PA | pinned v1.2 |
| Numeric comparisons | round to the stat's display precision BEFORE any gate comparison | IEEE754: a raw 0.079999… must count as .080 (caught by v1 fixture) |
| Consolidation trigger | below-middle in ≥4 families | render one pattern sentence, not an enumeration |

Ties are never split; a tie at a band boundary widens the band and the rendered count says so.
Whether the subject is in his own pool, quantile algorithm, odd/even handling, rounding order:
fixed in the build spec, exercised by fixtures, identical for every builder.

## 5. Comparison lenses

**Self over time (the season arc).** Spring HS and summer Legion are treated as two halves of
one long season (operator ruling: mostly-similar teams, not a JV→varsity jump). The lens
renders as ONE display, not competing widgets: the arc — up to four half-season windows
(spring 1st half → spring 2nd half → summer 1st half → summer 2nd half) for the §4 arc stats,
every point badged with its PA, a step marked ▲/▼/– only where that step clears the §4 gates
AND the two windows are adjacent among ALL windows (a mark never spans a hidden, floor-failing
window — v1.3; comparing across an invisible gap is a claim the reader can't inspect). An arc
with a single qualifying window renders that window plus the abstention line ("not enough
trips in the other stretches to compare"). The spring→summer step is one step of the arc, not
a separate feature. Exceptions and floors:

- A player who moved competition levels between halves gets numbers side by side, no marks on
  the cross-season step — identified via the coach context manifest (§6), not inferred.
- **Within-season windows are DB-sourced** (the authoritative CSV has no per-game grain) and
  are permitted only for a team-season that passes the verified-coverage gate: every
  STAT-BEARING scheduled game's per-game rows present, fresh. Coverage is counted with
  PERSPECTIVE FALLBACK (v1.3, mechanism found by the v1.2 build): a game's rows may live
  only under the OPPONENT'S perspective id — ownership of a stat row is `team_id`, never
  `perspective_team_id` — so the gate prefers own-perspective rows and recovers rows for this
  team's players from any other perspective, never double-counting. A listing with no stat
  rows under ANY perspective (a true forfeit/unscored listing) is EXCLUDED from the
  denominator and reported on the staff provenance page as listed-but-uncovered. Measured
  2026-08-22: spring passes 30 of 30 own-perspective; summer passes 44 of 44 (43 own + 1
  recovered via fallback). (v1.3 corrects v1.2, which misdescribed the recovered game as a
  forfeit.)
  A trend over the fraction of a season we happened to crawl is the same lie as an
  unverified pool.
- Windows below the §4 floor render no rate and no mark for that segment.
- **Count-based finish facts** ("reached base in 9 of your last 10 games") are recorded-fact
  claims, available at any sample, and are the only in-season trend form for part-time players.

**Team.** Anonymous bands against the player's own team-season, computed against the team
median but never worded "average". Vocabulary, in the coach's register but arithmetically
honest on small pools: *"top group of the 11 eligible hitters" / "above the team middle" /
"around the team middle" / "below the team middle" / "bottom group of the 11 eligible
hitters"*. The eligible count is always printed — "bottom 25%" is a false statement about a
pool of 11. Never a named teammate, never an ordinal rank (deducible on a 14-man roster).

**Verified opponent pool (the barometer).** Exists **only** when the cohort-validity gate
passes; otherwise the sheet ships team-lens only, with no placeholder. The gate (operator
ruling 2026-08-22: "we shouldn't wander in claiming a 'league' we haven't verified"):

- Every team on the subject's schedule fully crawled (full season), fresh within 14 days.
- Same season and competition class; one canonical formula per metric computed from
  compatible counting components on both sides (subject CSV vs pool DB) — fail closed on
  definition mismatch.
- **Pool teams are deduplicated by identity before weighting.** Duplicate team identities
  are a documented hazard of this repo's data (the 2026-08 dedup campaign existed because of
  them), and GameChanger itself lists the same club under multiple team pages (measured in
  Stage A resolution 2026-08-22: several opponents returned two search candidates with
  near-identical roster overlap under different public_ids). A naive pool builder would
  ingest such a roster twice — the coverage distortion entering through the identity door. A
  failed duplicate collapse blocks the lens exactly as a coverage failure does. (v1.2
  correction: v1.1 cited a same-DB three-team-ids measurement here that was refuted — a query
  bug had grouped by game, not team.)
- ≥8 qualifying teams; no single team contributes >15% of the pool; equal-team weighting.
- A club failing its own-schedule coverage may be DROPPED from the pool rather than failing
  the lens, provided the pool label counts only what remains and the staff provenance page
  names the dropped club and its gap (v1.3.2, from the first live 37-club evaluation: one
  club 1 game short — shrinking the pool honestly beats shutting the lens over 3% of it).
  The ≥8-club floor and share cap apply to the pool AFTER drops.
- Sensitivity check: recompute against the highest-coverage half of the pool; if the player's
  band moves, suppress the lens for that stat.
- **The subject obeys the §4 relative-standing floors** (40 PA batting; 50 BF / 10 IP
  pitching). The 20-PA membership floor qualifies POOL hitters only — pool noise averages out
  across hundreds of pooled players, the subject's does not (v1.3.4; the v1 builder reused
  the pool floor for the subject and ranked a 30-PA line). Below the floor: no strip for that
  family, no explanation — §8's omission rule.
- **Per team-season, like every lens** (v1.3.4): a pool exists per team-season, and strips
  render for each season whose gate passes and whose subject clears the floors. Each strip
  names its season ("this summer with the 18s", "this spring") — the phrase "this season" is
  banned on a two-season sheet as ambiguous.
- Rendering is **broad bands, never precise percentiles**: "top third of the hitters across
  the 37 teams you played (20+ trips each)". The pool is named as exactly what it is — the
  word "league" is banned unless the pool is a verified league population.
- **The barometer obeys the same aggregate bounds as the other lenses (v1.3 flip-run
  finding):** strips are family-scoped like the band table (one strip per §7 family), and
  when the §4 consolidation trigger fires (≥4 families in the bottom band on this lens), the
  section renders ONE plain summary sentence in place of the enumerated strips — say it once,
  completely, not four times. Per-stat detail stays available in the band table and the staff
  provenance page. Direct per claim, bounded in aggregate applies to every lens.

## 6. Context, abstention, and the coach manifest

A deterministic context rung produces honest framing sentences from data conditions: limited
varsity sample; primary role on the mound; low opportunity ("81 trips, mostly off the bench")
— exactly one neutral context line is REQUIRED on any sheet carrying a below-middle claim for
a low-opportunity player.

The **coach context manifest** is a small staff-authored file (never committed; lives with the
season's data) carrying what data cannot know: injury-shortened season, mid-season role
change, level moves between halves. Manifest entries can downgrade claims (trajectory → facts
only) and add context lines; they can never add evaluative claims.

## 7. Language system

- Plain-name stat map: "Getting on base — OBP", "Trips to the plate (PA)", "Strikeout rate".
  A stat without a plain name doesn't go on the sheet.
- Correlated families (one standing claim each): hitting {AVG} (singleton — assigned v1.3;
  v1.2 left AVG family-less and it silently vanished from sheets); on-base {OBP, BB%}; contact {K%, C%};
  power {SLG, XBH}; at-bat quality {QAB%, P/PA}; pitching command {BB% of BF, FPS%};
  pitching bat-missing {K% of BF}; pitching baserunners {WHIP} (singleton — added v1.2, the
  v1 build found it gated in §4 but family-less).
- Banned lexicon (asserted): quartile, percentile, median, average-when-median, BABIP, ISO,
  league (unless verified), and judgment adjectives (worst, weak, poor, lazy).
- Every negative claim is season-, metric-, and sample-bounded in plain words: "In 42 trips
  this summer, your strikeout rate was in the team's bottom group" — never "you are a bottom
  hitter".
- All rendered text comes from **fixed templates** selected by claim records (§9). No
  generative prose on the sheet.

## 8. Sheet structure and delivery

Sections qualify independently on their own evidence and order by share of the player's
workload (no named archetypes; no discontinuity where one PA reorders a page). A reliever's
sheet leads with the mound because his innings dominate his workload, not because a
classifier fired.

**Ordering rule (v1.3, replacing the inert v1.2 sentence):** the content inventory below is
fixed in CONTENT, not in page order. When the mound leads the player's workload (§4 heuristic:
season BF > season PA), the mound facts block and the arms band rows move AHEAD of the batting
season-lines table on page 1, and the batting table moves to page 2 with the field block; the
reliever's page 1 tells his mound season. All gates unchanged — this moves blocks, never
creates claims.

**Content inventory (NORMATIVE — v1.2).** The v1 build proved the claims logic without this
list and produced skeletal sheets: a spec that names claim types but not page content leaves
the design in the author's head. The sheet renders these blocks, each still subject to every
gate above (a block whose claims all fail their gates renders its abstention line, not
nothing):

- **Header**: name, class year, positions (by innings), team-season labels.
- **Season lines table** — Spring HS and primary-summer columns side by side. SHOW-rung rows:
  games; trips to the plate; AVG/OBP/SLG slash; OPS; strikeout rate; walk rate;
  doubles–triples–HR; RBI · runs; steals rendered "N of M (P%)" (v1.3 — a bare "3-4" is
  ambiguous between attempts and caught-stealing); quality at-bats; pitches seen per trip. Below the display floor a column renders its counts, never its rates. Cameo and
  no-varsity-spring notes attach here.
- **Season arc block** (§5) when its gates pass; otherwise the two seasons' numbers stand
  unmarked.
- **Where You Stood** — the COMPLETE band table for every stat with a passing standing gate,
  batting then arms rows. ⚠ Pinned against the v1 misreading: the consolidation rule governs
  the GROW section's derivation only — the band table is never consolidated away. Scope
  (v1.3): the table renders ONE row per correlated family (the family's first-listed gated
  stat), so it stays scannable; a table repeating one honest phrase is data, a bullet list
  repeating it is a drumbeat.
- **What Went Well** — derivations: standing claims within the §4 caps; plus these
  count-facts (recorded-fact rung, exempt from standing floors): basestealing (≥4 attempts,
  ≥75%), clean glove (≥15 chances, ≥.980), scoreless relief (6–10 IP, zero earned runs,
  rendered as innings and outings, never a rank), qualifying trend facts; "no automated item
  qualified" renders the abstention line.
- **Where To Grow — BLANK, coach-owned** (assistant-coach ruling 2026-08-25: "leave the
  'where to grow' part totally blank so that I can write or type into it"). The section
  renders as a header plus ruled blank lines, exactly like the meeting scaffold. The
  machinery that used to fill it (gap statements, cap 2, the §4 consolidation sentence) moves
  to the STAFF PROVENANCE PAGE as per-player meeting prep, so the coach writes informed by
  the data without the sheet pre-empting him. This is the claim matrix completing itself: the
  prescriptive rung was always coach-only; the coach claimed the space. (Digital "type into
  it": v1 is blank lines annotatable in any PDF viewer; true fillable form fields are a
  future refinement, not owed now.)
- **Page 2**: In the Field (per-season positions with innings, chances, errors, catcher
  throw-out line when applicable); On the Mound (facts block at ≥6 IP, one-line note below
  that; standing rows only above §4's pitching floors); contact profile (≥20 PA); barometer
  strips (§5, broad bands) when the cohort gate passes; the meeting scaffold.
- **Every section is per-team-season; there is no "primary season" scope (v1.3.4)**: each
  page-2 section (mound, standings, contact, barometer) evaluates EACH of the player's
  team-seasons against that section's own floors and renders every season that qualifies,
  labeled by season name. The v1 builder scoped page 2 to one designated primary season,
  which erased a 36-inning, 8-start varsity spring from a sheet whose mound section read
  "4.2 innings pitched" — the exact half-truth the claim matrix exists to prevent. A season
  that qualifies nowhere simply contributes nothing (§ omission rule); a designated "primary"
  may still order sections, never filter them.
- **No self-narration (operator ruling, 2026-08-26)**: the sheet never describes its own design,
  privacy properties, or provenance — no "this sheet contains/never names…" boilerplate, no
  disclaimers, and no renderer-added page furniture (file paths, print headers/footers).
  Information earns its place by informing the reader about BASEBALL; meta-information lives
  in this document and on the staff page's provenance sections, not on a kid's sheet.
- **Empty sections are OMITTED, never explained (operator ruling, 2026-08-26)**: a section
  with no qualifying content (no arc, no standing rows, no Went-Well items) renders NOTHING —
  no header, no placeholder sentence. Principle 2.5's "absence is a designed output" is
  expressed at section level by nonexistence. Machinery vocabulary — "gated," "floor,"
  "coverage," "standing floor," "sample" — joins the banned lexicon for player sheets; a
  context line may still accompany PRESENT content when it informs in plain baseball terms
  ("mostly relief work this summer"), never to explain an absence.
- **Formatting standards**: AVG/OBP/SLG/OPS three decimals with leading dot; ERA and WHIP two
  decimals; ERA computed and labeled on the team's regulation innings
  (`teams.innings_per_game` — these leagues play 7; print the basis when it isn't 9);
  percentages one decimal; every rate's denominator visible on the sheet (PA, IP, BF,
  chances).

Fixed scaffold at the end of every sheet (v1.3.3, operator ruling 2026-08-26 — replaces the
four-box scaffold): **Meeting Notes contains exactly one fillable block, "Where to grow,"**
with several ruled blank lines for the coach to write or type into. The earlier
Player's-read / Our-focus / How-we'll-measure-it / Next-check-in boxes are REMOVED.

Delivery: one PDF per player, filename `<Last>-<First>-<year>-exit.pdf`; the coach reviews
and approves the batch before anything reaches a player; sheets are introduced live, never
cold-sent; distribution stays staff-mediated. The staff gets a separate provenance page (pool
composition, coverage, freshness, discrepancy log) — none of that metadata appears on a
player's sheet. Generated sheets live only in unversioned data trees; committed fixtures use
fictional players; real minors' names never enter version control. Anonymity is understood as
exposure reduction, not guaranteed de-identification — which is why bands, not ranks.

## 9. Determinism and acceptance

The build produces a **structured claim record** per sheet before any rendering: every claim
with metric, value, denominator, pool id and size, eligibility evidence, claim type, direction,
deadband state, and template id. Rendering is a pure function of the claim record. Two
builders producing different claim records or different text from the same inputs means the
spec has a hole — file it, don't improvise.

Acceptance = all of:

1. Arithmetic cross-check of every displayed rate against the source's own rate columns, with
   a positive control (perturb one input; the check must fire).
2. Register assertions (banned lexicon, required sample-bounding on negatives).
3. Claim-matrix assertions: no rate below its display floor, no standing below its floor or
   pool minimum, no superlative on a rate, no evaluative/prescriptive text absent coach input.
4. Golden outputs over the synthetic fixture roster, which must include: floor−1/floor/floor+1
   opportunities; one-event rate swings; all-equal pools and ties at every cutoff; odd and
   even pools; a weak team's top player and a strong team's bottom player; a 10-IP reliever
   among starters; multi-position fielding; a player with no qualifying positive claim; a
   player below the middle in every family (consolidation must fire); a pool dominated by one
   team (validity gate must fail); rounding that would cross a threshold; long names and page
   overflow.
5. A named read-through pass, as the athlete and as the coach, on the two hardest live sheets
   before any batch is released.

## 10. Scope and non-goals

- **v1 ships the self and team lenses**, including the in-season arc where the §5 coverage
  gate passes — as of the 2026-08-22 crawls it passes for both LSB 2026 team-seasons under
  the v1.2 denominator rule, and measurement shows ~6–9 regulars per season clear the window
  floor; everyone else gets finish facts. The barometer ships only behind the §5 gate, which
  requires the full opponent crawl — a destructive-seam batch the operator sanctioned
  2026-08-22, never a side effect of sheet generation. Measured 2026-08-22 (v1.2 corrects
  v1.1's counts): 62 distinct opponents across the two team-seasons (26 spring / 36 summer),
  11 already crawled (3 / 8), 51 to crawl; Stage A roster-overlap resolution verified 42 of
  the 51, with 9 held for operator adjudication.
- Single year only. No cross-year tracking (project non-goal); the sheet's growth loop is the
  scaffold in §8, revisited at next season's exit meeting from fresh data.
- No effort, attitude, mechanics, potential, or coachability inference — ever (claim matrix,
  bottom row).
- Weight-room / training data: future signal (assistant coach, 2026-08-16), not in scope; the
  scaffold section is its interim home.
- The existing ad-hoc Track 1 scripts predate this model and violate it (priority language,
  20-PA standing floor, precise percentiles, sample×magnitude ranking — all now removed
  concepts). They are to be reconciled to this document before any sheet reaches a player.
