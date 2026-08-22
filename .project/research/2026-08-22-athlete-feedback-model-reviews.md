# Athlete-feedback-model adversarial reviews — 2026-08-22

Two independent Codex reviews of the exit-meeting feedback-model CONCEPT (pre-spec),
run against the brief archived in the chunk's ephemeral directory (unversioned).
Findings preserved verbatim below; full transcripts were session artifacts and are gone
with the ephemeral tree. All player references are fictional or placeholder.

## Review 1 — gpt-5.4, xhigh (ran first via silent model fallback; kept for the diff)

**Findings**
1. **Critical** — The team-band system is internally inconsistent and unsafe on these pool sizes. “Above team average” is wrong if the calc is median-based, and “top 25% / bottom 25%” is not meaningfully anonymous when only 6-10 players qualify; on 6 qualified hitters, “bottom 25%” is one kid. Spec edit: require a minimum qualified pool for four-band language, collapse smaller pools to simple above/below team middle, and define exact tie handling.

2. **Critical** — The “players on teams you played” league cohort is not a neutral comparison pool; it is a crawl-coverage artifact. Fully crawled opponents will dominate the strip, lightly crawled opponents will disappear below qualification floors, and aggregating across all of their crawled games mixes schedule strength and data completeness into one number. Spec edit: season+level match the cohort, impose explicit per-team coverage floors and equal-team weighting/caps, or delete the league lens until coverage fairness is provable.

3. **Critical** — The ladder treats “qualified to rank” as if it meant “qualified to characterize.” It does not. Your own coaching guidance already treats 20-50 PA and 15-30 IP as only an emerging picture, not “what went well / where to grow” territory ([docs/coaching/understanding-stats.md](/Users/jason/Documents/code/baseball-crawl/docs/coaching/understanding-stats.md:308), [.claude/agent-memory/baseball-coach/MEMORY.md](/Users/jason/Documents/code/baseball-crawl/.claude/agent-memory/baseball-coach/MEMORY.md:60)). Spec edit: separate floors for `COMPARE` and `CHARACTERIZE`, and make them stat-specific.

4. **Critical** — The trajectory block still manufactures meaning across incomparable seasons. A “better / worse / same” mark, even with a caveat, invites the kid and coach to treat spring varsity and summer Legion as one axis when level, role, lineup slot, and opponent quality moved. Spec edit: either remove evaluative trajectory entirely or require same competition family and similar role/workload; otherwise show the two season facts side by side and stop.

5. **High** — `sample × magnitude` is a bad selector for feedback priority. It will surface the loudest outlier, not the most trustworthy message, so a 24-PA extreme or 11-IP shiny run can outrank the boring but real 120-PA / 40-IP story. Spec edit: trust bucket first, then magnitude, or use stabilized/shrunken values instead of raw gaps.

6. **High** — Rate-stat superlatives are still a trap. The exact failure you already saw, “best ERA on the staff” from a small relief sample, still exists at 18-20 innings if the role is narrow and the stat is volatile. Spec edit: ban superlatives on rate stats; keep them only for workload/count facts like `most PA`, `most starts`, `most innings`.

7. **High** — Archetype detection from PA/IP alone will misframe players. It ignores defensive innings, `GS/GR`, lineup role, and season-to-season role changes, so the wrong section can lead the page. Spec edit: classify from share-of-team workload plus role markers, and allow a coach override manifest for injury/role context.

8. **High** — The claim ladder is missing an abstention/context rung. Honest outputs like “limited varsity offensive sample,” “mostly relief work,” “injury-shortened season,” or “not enough defensive chances to compare” do not fit `SHOW / COMPARE / CHARACTERIZE / SUPERLATIVE`, so the system will either force a bad claim or go silent. Spec edit: add a deterministic context rung with explicit triggers and templates.

9. **High** — Defense is still under-specified and likely to produce bad feedback. Reordering sections fixes one presentation bug, but it does not make raw fielding aggregates valid evaluation for a high-school shortstop, catcher, or first baseman. Spec edit: either keep defense descriptive only or require position-specific opportunity floors and ban evaluative defensive claims off error/fielding-percentage style stats.

10. **Medium** — The language system is harsher than you think because the sheet can stack deficit labels. A 15-year-old with 26 PA can walk out with “bottom 25%” in multiple places and no printed context about role/opportunity; then the coach spends the meeting undoing the paper. Spec edit: cap repeated negative labels, force every rung-3 claim to print its sample in plain language, and require one neutral context line for low-opportunity players.

11. **Medium** — The determinism thesis is not credible yet because core choices remain open. The spec does not fully define the candidate stat universe by archetype, polarity math, tie-breakers, contradiction handling between team and league lenses, or the exact meaning of “distance from the middle.” Spec edit: turn narrative selection into an explicit ordered algorithm and back it with golden expected outputs.

12. **Medium** — The acceptance gates catch arithmetic and vocabulary, not bad feedback. They will not detect pool contamination, false anonymity, median/average wording drift, a builder choosing the wrong narrative among several valid candidates, or a sheet that is technically compliant but pedagogically reckless. Spec edit: add synthetic edge-case fixtures and exact-output tests for them.

13. **Medium** — The schedule-network league lens is over-engineered for a 15-player batch run twice a year. It is the most expensive component, the least trustworthy component, and the one most likely to be overread because the percentile strip looks precise. Spec edit: cut v1 to team-season facts plus tightly gated team comparison, and treat league comparison as a separate later spec once coverage fairness is proven.

The core error is that the model converts tiny, uneven samples into sorted labels too early. The fastest hardening edits are: kill rate-stat superlatives, require minimum pool sizes for team bands, split `COMPARE` from `CHARACTERIZE` with stat-specific floors, and either delete or radically constrain the schedule-network cohort.

## Review 2 — gpt-5.6-sol, xhigh (the requested reviewer)

The central defect is that the model confuses an observed statistical difference with a meaningful coaching judgment. Its machinery can make weak evidence look authoritative, then turn “different from the middle” into “needs development.” That will produce both false praise and unjustified discouragement.

## Ranked findings

### 1. Critical — The league cohort is not a defensible comparison population

“Players on teams you faced” sounds representative, but the actual population is “players who accumulated enough recorded appearances on whichever opponent teams happened to be crawled deeply.” Those are materially different groups.

Concrete failure:

- The program faced ten teams.
- Two were fully crawled and contribute 70 eligible hitters.
- Eight have three recorded games each and contribute 15 eligible hitters combined.
- The sheet says “better than about 65% of the 85 hitters on teams you played.”
- In reality, it mostly says where the player ranked against two unusually observable programs.

There is a second mismatch: the player’s CSV contains a full season, while opponent players may have partial seasons. A full-season .390 OBP is being ranked against rates accumulated in five, ten, or twenty selectively captured games. A 20-PA floor does not make those observation windows comparable.

“Pool freshness” does not correct selection bias. Nor does naming the cohort.

Spec edit:

- Disable league percentiles unless a separate cohort-validity gate passes.
- Require the same season, age/competition class, stat definition, and comparable observation window.
- Define minimum opponent-team coverage, minimum number of qualifying teams, maximum contribution from any one team, duplicate/transfer handling, and team weighting.
- Run a sensitivity check against a high-coverage-only cohort; suppress the comparison if the player’s band materially changes.
- Call it an “available opponent sample,” not “league,” unless it is actually a league population.
- Use broad bands, not “65%,” even after validation.

With the current data contract—full-season CSV for the subject and partial database records for opponents—the honest outcome may be that league comparison is not yet supportable.

### 2. Critical — The proposed floors are far too low for the claims they unlock

At 20 PA, one additional on-base event moves OBP about 50 points. At 10 IP, one earned run moves ERA by 0.90. Those thresholds are administrative cutoffs, not evidence that rankings or characterizations are stable.

The trajectory rule is especially unsound. Around a .350 OBP, the sampling error from 30 PA is roughly nine percentage points for each season. A spring-to-summer difference of .040 is much smaller than ordinary sampling noise.

Concrete failure:

- Spring: 10 times on base in 30 opportunities, .333.
- Summer: 11 in 30, .367.
- The sheet renders “better.”
- The entire trajectory is one event, played at a different level against different opponents.

A caveat about different levels does not neutralize a green upward arrow or the word “better.” The visual remains an improvement claim.

The earlier nine-inning ERA problem is also not solved: at 10.0 IP the player becomes eligible for a top-band comparison and a “went well” statement. One additional inning flips the epistemic status of the same performance.

Spec edit:

- Separate counts from rates. Below a metric-specific denominator, show counts only or explicitly mark the rate “too little playing time to compare.”
- Define floors by metric denominator: PA or relevant opportunities for batting; batters faced for K%/BB%; outs or batters faced for pitching; chances by position for fielding.
- Add a low-sample sheet mode in which absence of characterization is an intended result.
- Remove better/worse trajectory arrows. At most show “spring number” and “summer number,” with “these seasons are not directly comparable.”
- If directional trajectory language is retained, require a substantially larger sample, a practical-effect threshold, and a stability/uncertainty test—not a raw .040 or four-point rule.

### 3. Critical — “Distance from the middle” is not a development priority

The team median is a descriptive reference point, not a performance standard. Yet “the biggest gap to close” silently converts it into a prescription. That directly contradicts “the sheet describes; the coach prescribes.”

Relative standing also creates zero-sum nonsense:

- On a weak hitting team, a .310 OBP might become a printed strength because it is top-quarter.
- On an excellent team, a .400 OBP might become a growth item because it is below the team middle.
- If everyone is clustered from .330 to .345, someone is still assigned to the bottom group despite a trivial difference.

“What went well” and “where to grow” cannot be determined from relative rank alone. They need role expectations, coach-defined standards, individual goals, or an explicitly limited label such as “relative result.”

Spec edit:

- Ban “gap to close,” “focus,” “needs improvement,” and equivalent priority language from automated claims.
- Rename the sections to something epistemically accurate, such as “Results that stood out” and “Results below this comparison point.”
- Permit “went well” or “development priority” only after explicit coach selection.
- Add practical deadbands so no strength or lower-result item is forced merely because somebody must rank first or last.
- Allow “no automated item qualified.”

### 4. Critical — `sample × magnitude` is not a valid candidate score

The score is dimensionally incoherent and statistically backwards.

- A K-rate gap can be represented as `10` percentage points or `.10`; that storage choice changes its score by 100×.
- OBP, SLG, ERA, fielding percentage, walk rate, and strikeout rate do not have commensurate units.
- Precision generally improves roughly with the square root of sample size, not linearly with sample.
- Searching many correlated metrics guarantees winner’s-curse selections: AVG, OBP, and SLG can all nominate the same hot stretch as three apparent strengths.

Concrete failure:

- 100 PA × .030 OBP gap = 3.
- 30 PA × 10 percentage-point K% gap = 300—or 3 if the rate is stored as `.10`.
- The “biggest” growth item depends on serialization rather than baseball evidence.

Spec edit:

- Delete cross-metric `sample × magnitude` ranking.
- Establish a small coach-approved metric allowlist and fixed domain priority.
- Define metric-specific practical thresholds and denominators.
- Allow at most one claim from each correlated family.
- If cross-metric ranking is unavoidable, define normalized units and tie-breaking explicitly, but do not call the winner “the biggest gap to close.”

### 5. High — Team bands are mathematically misleading on small pools

“Above team average” is false if the calculation uses the median. Average normally means arithmetic mean.

Four quartile-like bands are also not cleanly definable for approximately ten eligible players:

- With ten players, “top 25%” means either two players, or three players—20% or 30%.
- A tie at the boundary must either split identical results or make the band larger than advertised.
- A player exactly at the median has no specified band.
- With many identical rates, top/bottom status can become arbitrary after rounding.
- Whether the subject is included in the comparison pool can change the cutoff.

Spec edit:

- Replace “average” with “middle” everywhere if the reference is the median.
- Add an “around the team middle” band.
- Define minimum pool size, inclusion of the subject, quantile algorithm, exact tie behavior, odd/even handling, missing values, and the order of rounding versus ranking.
- Never split ties.
- Prefer “top group among 11 eligible hitters” over an inaccurate “top 25%.”
- Require a practical distance from the cutoff before printing a high/low band.

### 6. High — The comparisons ignore role and opportunity context

A rate can be correctly calculated and still be an invalid basis for comparison.

Concrete failures:

- A reliever’s ERA is compared with starters despite different inning lengths, inherited-run treatment, and opponent exposure.
- A shortstop with a .930 fielding percentage over 100 difficult chances ranks below an outfielder who was 5-for-5 on routine chances.
- A hitter used primarily against strong pitching ranks below one used selectively against weaker pitching.
- A pitcher-first player’s sparse batting rates remain printable and may still receive visual prominence even if they cannot be ranked.

The role archetype only changes section order. It does not make the underlying comparisons valid.

Spec edit:

- Define an allowed-claims matrix by metric and role.
- Do not compare fielding rates across positions; require position-specific opportunity floors or show fielding counts only.
- Separate starter and reliever comparisons if adequate cohorts exist; otherwise avoid context-heavy pitching comparisons such as ERA.
- Treat playing time as context, not player merit.
- Make section inclusion independently evidence-based instead of assuming that page ordering solves eligibility.

### 7. High — The claim ladder collapses fundamentally different claim types

The ladder is not actually ordered by evidentiary strength:

- “Bottom 25%” already characterizes a player; it is not a neutral comparison.
- “Went well” adds normative meaning, not merely greater statistical magnitude.
- “Biggest gap to close” is both a cross-metric superlative and a development prescription.
- “Led the team in plate appearances” is an exact count superlative that may require no rung-three magnitude.
- “Best ERA” is a value judgment about a noisy rate even when workload is substantial.
- A displayed `.500` from two PA implicitly communicates performance despite being classified as mere SHOW.

Compound sentences contain several separately gated claims. “K% 27.2% vs team middle 16.6%—the biggest gap to close” contains:

1. A recorded rate.
2. A comparison.
3. A cross-metric extremum.
4. A value judgment.
5. A prescribed priority.

Rung three currently authorizes all five at once.

Spec edit:

Replace the ladder with an atomic claim matrix containing separate gates for:

- Source/data integrity.
- Denominator adequacy.
- Cohort validity and comparability.
- Practical magnitude and stability.
- Claim type: recorded fact, estimated rate, relative standing, temporal difference, evaluative judgment, causal explanation, or prescription.

Only the first four claim types should be automatically generated. Evaluative and prescriptive claims need explicit coach input. Every clause in rendered text should retain its own claim type and eligibility evidence.

For superlatives, distinguish:

- Factual count leaders: “tied for most innings recorded.”
- Rate leaders: normally render as a high group, not “best,” and require metric-specific eligibility plus tie handling.

### 8. High — The model has no criterion-based definition of success

A peer norm answers “where did this player rank?” It does not answer “was this good baseball?” or “what should this player develop?”

A coaching-pedagogy expert would object that the model lacks:

- Role expectations.
- Coach-defined performance standards.
- Prior player goals.
- Tactical or situational context.
- Qualitative observations unavailable in aggregates.
- A distinction between controllable processes and noisy outcomes.

A sports-psychology expert would object that it:

- Makes social comparison the organizing principle.
- Risks turning seasonal outcomes into identity labels.
- Provides no player voice or self-assessment.
- Can introduce a negative ranking as a permanent screenshot.
- Lets automated output preselect the “biggest” weakness.
- Does not distinguish poor outcome from effort, learning, or decision quality.

Spec edit:

- Make all negative language season-, metric-, and sample-bounded: “In 42 PA this summer, your recorded strikeout rate was in the lower team group,” never “you are a bottom hitter.”
- Limit automated lower-result items to one or two.
- Add structured space for “Player’s read,” “Coach + player focus,” “how we will measure it,” and “next check-in.”
- Require the coach to approve every player-facing characterization before release.
- Specify that rankings are introduced live, privately, and not first delivered through an unattended email.
- Never infer effort, attitude, mechanics, potential, or coachability from statistics.

### 9. High — “Ground truth” is too strong, and the two sources may not share definitions

The staff CSV is a source of record, not ground truth. It can contain scoring errors, incorrect player attribution, and rate definitions that differ from database reconstruction.

More importantly, comparing a CSV-derived player rate with database-derived opponent rates requires identical formulas and event coverage. Logging discrepancies does not make the comparison valid.

Spec edit:

- Rename the CSV “authoritative program record.”
- Define one canonical formula and denominator for every compared metric.
- Require both subject and cohort values to be produced from compatible counting components.
- Fail closed when required components or definitions differ.
- Give the player/coach a correction path for apparent scorekeeping mistakes.
- Specify whether an arithmetic mismatch blocks the sheet; merely logging it is insufficient.

### 10. High — The determinism thesis is not credible yet

Two competent builders will still disagree about:

- Eligible metrics and their directionality.
- Whether the player belongs in his own pool.
- Quantile algorithm and tie treatment.
- Minimum cohort size.
- Meaningful team workload share.
- Pitcher-first, position-player, and two-way boundary cases.
- Primary position and multi-position fielding treatment.
- Raw versus rounded values at thresholds.
- Definition of magnitude and “same.”
- Number and ordering of claims.
- Correlated-stat deduplication.
- Missing and zero-denominator behavior.
- League season, level, weighting, duplicate players, and transfers.
- Visual color, strip scale, truncation, and page-overflow behavior.
- What happens when no strength or growth candidate qualifies.

If a model is allowed to compose prose, output will also vary in tone and implied judgment. A banned-word list does not create semantic determinism.

Spec edit:

- Use fixed templates, not generated narrative.
- Define a structured intermediate claim record with metric, value, denominator, pool, eligibility reasons, claim type, direction, confidence state, and exact template ID.
- Fully specify rounding, tie-breaking, ordering, omission, and fallback behavior.
- Add golden outputs for synthetic players. If two implementations do not produce the same structured claims and text, the spec is not deterministic.

### 11. High — The acceptance gates verify mechanics, not truth

The current gates can certify a harmful sheet:

- Arithmetic checks prove only that a possibly inappropriate rate was calculated correctly.
- A positive-control mutation proves the check can fire, not that the formula or denominator is right.
- A banned lexicon catches “quartile” but permits “worst,” “weak,” “far behind,” or misleading visual red.
- Claim-ladder assertions do not detect a biased cohort, role mismatch, near-tie, incorrect direction, or inappropriate metric.
- Reading two archetype sheets will miss the actual edge cases and is neither executable nor reproducible.

Spec edit:

Create synthetic acceptance fixtures for at least:

- Zero, one, floor-minus-one, floor, and floor-plus-one opportunities.
- One-event rate changes.
- All-equal pools and ties at every cutoff.
- Odd and even pool sizes.
- A weak team’s “top” player and a strong team’s “bottom” player.
- A 10-IP reliever versus starters.
- Multi-position fielding.
- Exact archetype boundaries.
- A player with no qualifying positive claim.
- A player below the middle in every metric.
- A league pool dominated by one or two teams.
- Rounding that would cross a threshold.
- Missing counts and incompatible stat definitions.
- Long names and PDF overflow using fictional data.

Add semantic assertions for metric direction, pool validity, practical deadbands, position/role compatibility, and prohibited prescriptions. Rendered-PDF QA must verify note-space dimensions and that visual color/order does not add an ungated judgment.

### 12. Medium — The archetype classifier adds discontinuities without solving the real problem

A player at 19 PA and 10 IP becomes pitcher-first; at 20 PA and 10 IP he may become two-way. A player at 19 PA and 9⅔ IP may fit nowhere. One plate appearance or one out can reorder an entire sheet.

Spec edit:

- Remove named archetypes from decision logic.
- Evaluate batting, pitching, and fielding independently.
- Order qualifying sections by meaningful workload share, with a deterministic tie-breaker.
- If archetype labels remain, define all boundaries, precedence, and fallback states.

### 13. Medium — The privacy model is incomplete for a screenshot-oriented artifact

Anonymous teammates are not genuinely anonymous on a 14-player roster. Players often know who occupied each role, and public GameChanger numbers may make bands reversible. The subject’s PDF also contains identifiable performance data regardless of whether names enter version control.

Spec edit:

- Define output storage, access, transmission, retention, and deletion.
- Separate player-facing output from a staff-only provenance/coverage report.
- Do not place crawl diagnostics or reconstructable teammate details on the player sheet.
- Use fictional fixtures for every committed test and golden PDF.
- State that anonymity reduces exposure; it does not guarantee de-identification.

## What to cut

The highest-cost, lowest-value elements for a 15-player batch are:

1. League percentile strips built on uneven crawl coverage.
2. The cross-metric `sample × magnitude` optimizer.
3. The three-archetype classifier.
4. Generative prose plus a banned-word policing system where fixed templates would be safer.
5. Player-facing pool freshness metadata.
6. Precise percentile language such as “better than 65%.”

A smaller defensible model would show authoritative counts, selectively show adequately sampled rates, use cautious tie-aware team context, explicitly say when evidence is insufficient, and leave all development prioritization to a structured coach-player conversation. The current concept instead spends substantial machinery making unreliable ordinal judgments look exact.
