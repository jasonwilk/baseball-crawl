# Deep Scout — adversarial design reviews (2026-07-18)

**Provenance:** Two independent adversarial reviews of the Deep Scout design threads
(a lightweight "our teams" selector; a prediction-accuracy eval loop; deterministic
predictions governed by named/versioned params), run 2026-07-18 after live Deep Scout
runs vs two American Legion opponents + grading one report against the finished game.

- **Reviewer 1:** Codex `gpt-5.6-sol` (xhigh reasoning, read-only sandbox).
- **Reviewer 2:** a Fable model (subagent).

Both reviewed the SAME self-contained, **PII-free** design brief
(`scratchpad/design-brief.md`, mechanisms only — no opposing-minor names). This file is
design/methodology only and carries no PII; it is the durable home referenced by
IDEA-132. The E-263 v1-scoped corrections from these reviews were folded into E-263 on
2026-07-18 (SIG-004/SIG-005/E-263-07/TN-5); the eval-loop / self-scout-auth / params
material below is deferred Thread B/C input (v2 / a future eval-loop epic), captured here,
built nowhere yet.

**Both converged on the same upstream reframe:** the threads as posed have the causality
slightly backwards. The dangerous version is "grade everything, centralize every knob,
then sharpen" — a deterministic feedback machine that mostly measures its own
definitions. Smallest defensible build: propagate starter uncertainty into the game plan;
persist one immutable PII-minimized prediction packet; grade only starter + lineup first
with coverage states + a naïve baseline; keep the 357-game backtest as the tuning gate.

---

# Reviewer 2 — Fable

## 1. Ideation — what's missing

**1. Pitch-budget table beats the probable-starter ranking — and it's 100% deterministic.**
Your own backtest says the ranked name is wrong 60% of the time even at top-2. But the
rest-rule gate itself is near-perfectly knowable: league pitch-count rules + each arm's
recent workload yields "max pitches available on our game date" per arm. Render that as
the headline: "Ace: 35 pitches available. #2: full 105. #3: full 105." A coach plans
differently against a capped ace (survive 2 innings, feast on the bullpen) than against a
fresh one — and that plan is robust to which arm actually starts. Eval implication: grade
gate recall ("was the actual starter in the eligible set?") separately from rank accuracy.
If gate recall is ~95% and rank top-1 is 20%, the ranking is mostly noise riding on a
genuinely valuable gate — consider killing the rank and presenting the eligible set with
usage shares. Simpler and more honest than "committee."

**2. Bullpen chain, not just starter.** At HS pitch caps, games are decided against the
second and third arms. Given each plausible starter, who is rest-eligible to follow, and
what's their command read? "Next arm out is wild reliever X" changes late-game decisions
(when to take pitches again, when to pinch-hit) more than the starter's identity does.
Same machinery you already have, applied one arm deeper.

**3. The fatigue cliff / first-inning split.** Your two-branch plan is game-level, but HS
command is regime-dependent within the game: notoriously wild in inning 1, degrading past
~50–60 pitches. Per-arm strike% by pitch-count bucket (or just inning-1 vs rest) turns "if
he's wild, take" into "take in inning 1 regardless; reassess at 15 pitches" — an
actionable in-game trigger. Directly addresses the n=1 lesson: the volatile arm wasn't
"wild or hittable," he was wild that day — intra-game triggers are how a paper report
survives day-of variance.

**4. Grade the emphasis, not just the calls — or your eval loop will miss its own
motivating failure.** The n=1 post-mortem failure was ordering: right content, wrong
headline (steal light led; walks won). A grader that joins predictions to box scores will
score the starter call a hit, the steal light "no attempts / ungradeable," and report
success — blind to the failure you experienced. Persist the report's lean and section
order as first-class predictions and grade "did the top-billed lever appear among the
top-2 realized run sources?" Otherwise Thread B cannot detect the one error class you've
already observed.

**5. Baselines, or the accuracy log is uninterpretable.** Log every predictor's naive
baseline: starter = "most-used eligible arm"; steal light = "always green"; branch =
"always wild." Skill = lift over baseline. 40% top-2 sounds weak; if naive gets 32%, the
model is barely paying rent — and you'd want to know that before building versioned params
to tune it.

**6. Data-quality floors, not just sample-size floors.** GameChanger is scored by
volunteers. Quick-scored games produce garbage whiff%/strike%. A 60-pitch outing from a
quick-scored game passes your 20-PA floor while being fiction. Gate command reads on
pitch-event density per game (pitches recorded / expected), and flag which perspective
scored each game — home-scorer strike-zone bias is systematic.

**7. Catcher-conditioned steal light.** You already learned "condition on the arm, don't
average" — the steal light violates that lesson today. SB-allowed is catcher-specific;
WP/PB is battery-pair-specific; LHP vs RHP changes the running game. A team with a
strong-armed starter catcher and a JV backup has two different steal lights.

**8. Opponent's surrounding schedule as a starter-prediction feature (or at least a
display).** Coaches save the ace for the conference rival, not for you. "They play their
rival Tuesday, us Thursday" predicts the ace goes Tuesday better than any cadence model.
Even if you don't encode it, display their week's schedule next to the starter section.

## 2. Sharpening

**Thread A — collapse "our teams" into "matchup report" and the ontology problem
disappears.** The sharpest version isn't a selector at all: a report optionally accepts a
second public_id and renders matchup sections (A's runners vs B's battery, both freebie
ledgers). No "ours" concept in the data model, no registry, no `.env` list — "our teams"
becomes a UI convenience: a recents dropdown populated from teams already in the
reports/teams tables (zero new storage). Avoid `.env` specifically: it requires server
access + restart to edit, drifts from the form, and is the first step toward a
config-managed team registry — the deleted infra's skeleton. A form field with autofill is
simpler and holds the boundary better. Self-scout is then just matchup(us, us)-degenerate
or a single-id report on your own public_id — no new pipeline.

**Thread B — the backtest harness is your real eval loop; demote the live log to
corroboration.** One program, ~15–20 scouted games/season, many predictors, several often
ungradeable. The live log can never power a param decision within a season. You already own
a 357-game backtest — formalize it: retrodict every opponent game using only data-as-of-
date (leakage discipline), grade with the same grader, and make backtest delta the gate for
any param change; the live log's job is smoke-testing the grader and collecting anecdotes.
This is the honest answer to "sharpen only on patterns across many games" — many games
means 357, not 15. Also: (a) persist the input snapshot (the stat values that fed each
call) with the prediction — when a call misses you must distinguish "data was wrong"
(scorekeeper) from "logic was wrong," and the DB mutates by grading time; (b) pre-register
grading rules in the versioned params file ("wild-branch materialized ⇔ game BB/7 ≥ X") —
post-hoc branch-grading after you've watched the game is vibes.

**Thread C — version the model, not just the knobs; use git as the registry.** The params
file contains no PII (thresholds only), so git history IS the version registry. Version
stamp = short commit hash or a monotonic integer in the file, written into every prediction
row and report footer. Param change = commit whose message carries the rationale + backtest
delta. No params table, no admin UI, no migration of old predictions. Drop the fiction that
sharpening never touches logic: version = predictor code + params together; param-only
bumps are the cheap common case, logic changes bump the same version with the same
discipline.

## 3. Adversarial critique

**C's core guardrail contradicts your own best lesson.** "Sharpen = adjust a named param,
never rewrite logic" — but the one genuine first-principles fix you extracted from live play
("volatile-command arm → present both tails, never lean") is a structural rule change, not a
knob turn. Held strictly, the guardrail freezes exactly the class of fix you've proven you
need; held loosely, engineers launder logic rewrites as "params" (a
`lean_mode: both_tails_if_volatile` boolean is a code branch wearing a param costume). Fix:
version code+params as one unit; the real guardrail is "no change without a 357-game
backtest delta attached."

**B grades interventions with outcomes the intervention caused — the steal light is
unfalsifiable as designed.** The report shapes the coach's actions; the game then grades the
report. Green light → you run → 1-for-3 → was the read wrong or were your jumps bad? Red
light → you never run → zero evidence ever accrues against a red light. Same for blueprint
levers: you execute the top-billed lever because it was top-billed (self-fulfilling) and
never try the bottom one. Scenario: five straight red lights, five station-to-station games,
grader logs five "no data" rows, and the steal light's accuracy remains formally perfect
while possibly costing you 8 bags. Partial fix: grade the inputs' forward validity — did
that battery allow steals to other teams at the predicted rate in subsequent games?
Confound-free and your crawler already collects it.

**The n=1 trap in its second, sneakier form.** You correctly refused to reorder the report
off one blowout — but you did extract a rule ("both tails for volatile arms") and a
validation ("per-arm beat aggregate") from that same n=1, and both are headed for the
codebase. Notice the asymmetry: conclusions you like get "first-principles fix" status;
conclusions you don't get "that's overfitting." The only defense is mechanical: every rule
extracted from a live game must reproduce as a backtest delta before it ships. Run
"both-tails-if-volatile" against the 357 games; if it doesn't improve branch-grading there,
it was a story you told about one Tuesday. Also apply this to Thread C's own founding
evidence: "hard partition beat graduated weights" is one backtest conclusion on one sample —
pin it as re-runnable, not doctrine.

**A's scope-creep gradient runs through the cron, and staleness is the shove.** The failure
sequence: matchup sections join our side vs their side → someone notices our side's data is
a week stale → "our teams should refresh automatically" → our teams enter the morning-run
path → you have rebuilt tracked-teams with a different table name. Tripwire to write down
now: "our teams" (or the second public_id) must never appear in any scheduled/cron code
path; matchup reports crawl both sides fresh at generation time, always. Corollary: the
steal pairing greenlights a runner who got called up to varsity last week — a stale-join
error wearing a confident green badge, with two different "Through [date]" truths silently
merged. Print both sides' game-coverage lines or don't render the pairing.

**Self-scout is the one report you must not leak, served on infrastructure built to
share.** The entire product is share-a-link. A self-scout report is a ranked list of your
own minors' exploitable weaknesses — the single artifact an opposing coach would most want,
one forwarded group-chat link away. And Thread B makes it worse: the eval log is a running
record of named 15-year-olds' predicted and realized failures. Storage discipline covers the
repo, but the leak vector is the workflow: the moment you "sharpen on patterns," someone
pastes "we missed on [kid's name] three straight times" into an epic doc, a commit message,
or an agent transcript. Rules: (1) self-scout/matchup reports get restricted expiry or auth,
decided at design time; (2) eval summaries that leave the server are aggregate and
role-labeled ("arm #2," "leadoff") — never named; (3) data dies with the season; only
PII-free params/rules persist in git.

**Determinism is confidence laundering unless the surface says otherwise.** "STEAL LIGHT:
GREEN (params v7)" reads as engineering to a coach. Underneath: volunteer-scored WP/PB, a
5-attempt floor (n=5 — one throw-out flips the light), season aggregates over a roster that
isn't the roster anymore. Determinism guarantees reproducibility, not correctness — v7 will
reproduce the same wrong green every time. The structural gap: all your params gate rates;
nothing gates regime change (new catcher up from JV, ace back from injury, post-tournament
fatigue), the dominant HS failure mode no season-aggregate knob can see. Cheapest
mitigations: a last-3-games column beside every season rate, and uncertainty language sized
to n on every recommendation. Related mislead already in production: 60% of the time the
actual starter isn't in your top-2, so every "conditioned on the arm" section is conditioned
on the wrong arm more often than not — the strongest argument for the pitch-budget table.

**Thread B's quiet definitional rot.** "Grade every predictive output" hides that half your
outputs aren't predictions in the gradeable sense: hitter tendencies get ~3 PA per hitter
per game against your pitcher (their first-pitch swing rate vs your ace is not their
tendency — it's your ace); lineup-slot reconstruction may itself be wrong game-to-game.
Say explicitly which predictors are live-gradeable (starter gate, starter rank,
branch-materialized, lever-realized) and which are backtest-only (tendencies, steal inputs),
or the log fills with noise rows someone will average into a "score."

## Bottom line
- Highest-leverage build: pitch-budget table + gate-vs-rank split grading.
- Thread A: two-public_id matchup report with a recents dropdown — no registry, no env, no
  "ours" ontology, fresh-crawl-both-sides invariant, written cron tripwire.
- Thread B: backtest is the eval loop; the live log is an anecdote collector. Add
  emphasis-grading, input snapshots, baselines, pre-registered grading rules.
- Thread C: git is the registry, version = code+params, the real guardrail is "no change
  without a backtest delta." The "params only, never logic" rule is already contradicted by
  your own best lesson.

---

# Reviewer 1 — Codex gpt-5.6-sol

## Blunt verdict

The largest design error is upstream of Threads A–C: you are aggressively conditioning the report on a probable starter when your top-2 misses roughly 60% of games. Per-arm analysis is better than staff averaging **if you know the arm**. Pregame, you often do not. Conditioning can therefore amplify starter-selection error into an entire wrong game plan.

The second error is calling every output a “prediction.” Several are descriptive tendencies or conditional advice. If you force them into one accuracy loop, you will manufacture accuracy for unfalsifiable claims and punish sound recommendations for events that never had an opportunity to occur.

Thread A is small enough to ship, but its proposed self-scout content creates a tactical/privacy leak in a report currently served without authentication. Thread C is useful bookkeeping, but named parameters alone do not make a model reproducible, valid, or resistant to overfitting.

## Highest-leverage changes

### 1. Propagate starter uncertainty through the report

Do not join every downstream section to only the top-ranked arm. With top-2 accuracy around 40%, that is structurally unsafe.

Use a simple candidate-set presentation:

- **Robust across likely arms:** advice that holds for all top candidates.
- **The fork:** the one meaningful difference between Candidate A and Candidate B.
- **Identification cue:** what coaches should observe in the first 10–15 pitches to choose the branch.
- **Unknown/new arm fallback:** a generic read-and-adjust plan for the frequent case where the starter was outside the ranked set.

No probability-weighted mixture is needed. A hard “common vs divergent” partition fits your existing finding that soft weights add little.

Also, top-2 hit rate is incomplete. Report Hit@1/2/3, average candidate-set size, reciprocal rank, coverage/abstention, and a naïve baseline. Listing three of five plausible arms can produce an impressive-looking hit rate without much skill.

### 2. Stop treating unlike outputs as one accuracy problem

| Output | What it actually is | Defensible evaluation |
|---|---|---|
| Probable starter | Forecast | Hit@k, reciprocal rank, candidate width, coverage, naïve-baseline improvement |
| Rest eligibility | Rule determination | Audit inputs and ruleset; actual non-use is not a miss, and actual use does not prove legality |
| Command read | Estimated tendency plus conditional policy | Compare observed command regime with the pregame distribution; a branch is only gradeable if it has a predeclared trigger |
| Steal light | Conditional decision aid | Grade outcomes only when an attempt/opportunity exists; zero attempts is not “wrong” |
| Loss blueprint | Historical association/hypothesis | Prospective lift over the opponent’s win/base rate; never causal “accuracy” |
| Hitter tendencies | Per-event rate estimates | Calibration over PAs/BIP, clustered by game/player; grade lineup reconstruction separately |

A two-branch “if wild / if locating” plan is currently nearly unfalsifiable: every outing lands in a branch. To make it useful and evaluable, define the live switch cue—such as early strike rate, first-pitch strikes, or three-ball counts—and the corresponding action.

### 3. Separate prediction quality from decision use

The blowout did not establish what the current interpretation says it did:

- A top-2 hit is an anecdote, not evidence of starter-model skill.
- Zero steals does not falsify a green light. There may have been no suitable runner, score state, or tactical reason.
- Winning with walks does not prove walks caused the win.
- One wild outing does not prove the season command lean was miscalibrated.
- Looking backward at the realized starter and observing that his per-arm profile fit better is partly hindsight conditioning.

What the game did reveal is a **report-prioritization problem**. You need a headline-eligibility gate, not another weighted ranking model. A signal should lead only if it is:

- Actionable;
- likely to encounter an opportunity;
- sufficiently supported;
- robust across plausible starters.

That would have prevented an opponent-only steal rate from becoming “THE exploit” without tuning the steal threshold after one game.

## Thread A — “our teams” selector

### Sharpen it

Use one runtime mapping of short alias → exact `public_id`, consumed by both CLI and admin dropdown. The generated report should freeze:

- Our exact team identifier and resolved season;
- opponent identifier;
- target game identifier, not merely a date;
- game date/time;
- competition/ruleset level.

Date alone is insufficient for doubleheaders. Team name is insufficient for common-name or wrong-season matches.

Do not add a table, CRUD screen, membership, synchronization timestamp, roster cache, default ownership, or background refresh. The scope boundary should be mechanical: the config is read at generation time and has no lifecycle inside the application.

### Where it breaks

- An `.env` “array” is awkward structured configuration and easy to misparse. A tiny git-ignored JSON/TOML file is clearer if there are more than two entries.
- Pairing two noisy rates does not create a strong estimate. “Our runners 4/5” × “their battery 5/6” is two tiny samples multiplied together. Prefer a conjunctive gate—both sides must independently clear evidence floors—rather than manufacturing an expected success percentage.
- Manual reports need the target date and ruleset explicitly. Selecting “our team” alone does not establish rest eligibility.
- Most importantly, self-scout content should not automatically enter the current public-link artifact. The report serving convention is unauthenticated ([architecture rule](/workspaces/baseball-crawl/.claude/rules/architecture-subsystems.md:64)). Publishing our probable starter, first-inning weakness, or runner profile creates a useful report for the opponent too.

The simplest safe boundary is: Thread A may initially drive anonymized matchup calls, but named self-scout stays out of the public report until there is a genuinely staff-private delivery mechanism.

## Thread B — evaluation loop

### Make the stored unit one immutable prediction packet

One runtime row per report generation is enough:

- Target game identity;
- generated time and first-pitch time;
- data cutoff and games included;
- exact fact-sheet inputs used, including denominators and thin/no-data states;
- prediction outputs;
- predictor logic versions, ruleset version, and parameter fingerprints;
- nullable postgame truth and grade;
- ground-truth coverage status.

Persisting only the displayed output is insufficient for diagnosis. Persisting the whole database again is unnecessary. Reuse the deterministic fact sheet already produced for rendering.

When multiple reports are generated for one game, retain them for audit but aggregate only the **latest valid snapshot before first pitch**. Otherwise regenerations inflate sample size and invite cherry-picking.

### Required grader states

The grader needs more than correct/incorrect:

- `scorable`;
- `no_opportunity`;
- `missing_charting`;
- `target_unresolved`;
- `source_incomplete`;
- `postgame_generation/leakage`;
- `parser_failure`.

Accuracy must always appear beside coverage. Missing play-by-play must never become a negative event, and abstentions must not quietly disappear.

Also beware self-confirmation: if the same plays parser produces both the pregame tendency and postgame “ground truth,” correlated parser errors can make the model appear calibrated. Where an independent box-score target exists, use it. Otherwise label the result same-source consistency, not ground-truth accuracy.

### Start much narrower

First automate only:

1. Starter identity/rank;
2. lineup identity/slot reconstruction;
3. clearly defined per-event hitter forecasts.

Do not automate grading of “work counts,” “run,” or “force errors” until you have opportunity definitions and a causal story. A 30-second human “decision receipt”—used/not used/no opportunity/surprise—will tell you more about those recommendations than a box-score join.

There is also a methodological conflict: a single season of generated reports may never produce enough independent cases to tune rare predictors. Cross-season player tracking is correctly out of scope; **deidentified cross-season model evaluation is a different thing**. If even that is forbidden, freeze the parameters and accept that meaningful tuning may take years.

## Thread C — named/versioned parameters

### Split the manifest into distinct classes

Do not put everything into one tunable config:

- **Ruleset:** league pitch-count/rest rules, effective date, competition level. Not tunable from accuracy.
- **Logic version:** algorithm and feature definitions.
- **Parameter set:** the genuinely empirical thresholds.
- **Trust policy:** sample floors and abstention rules.
- **Presentation policy:** headline/order decisions.

Otherwise a future “accuracy improvement” can accidentally tune a safety rule, stat definition, or evidence floor.

Use an automatically generated content hash plus a human-readable release label. A manually incremented `params_version` will eventually be forgotten. Store the application build/commit identifier too; “data + params” is not reproducible when the code changed.

“Never rewrite logic” is an impossible guardrail. Bugs, definition corrections, and new predictors require logic changes. The honest contract is: old predictions remain immutable, logic changes receive a new predictor version, and no historical output is silently rewritten.

### Prevent versioning from becoming MLOps theater

- No parameter registry service.
- No tuning UI.
- No optimizer.
- No per-team parameter sets.
- Prefer per-predictor hashes so changing a steal threshold does not split the starter model’s already-small sample.
- Run candidate parameters in shadow and promote prospectively.
- Normally freeze the live version for a season or a predeclared evaluation tranche; midstream changes should be correctness fixes, not reactions to outcomes.

## Missing high-value signals and report mechanisms

1. **Actual command volatility.** Moderate aggregate strike% plus high BB/7 is not evidence of volatility. Volatility means across-outing dispersion. Show the last several starts or median plus range/IQR. With too few outings, call volatility unknown. Otherwise “both tails” becomes generic baseball advice attached to every arm.

2. **Starter-miss recovery and bullpen chain.** Given the starter model’s miss rate, the likely second arm, coach pull tendency, and “unknown starter” response may be more valuable than further tuning top-1 rank.

3. **Lineup stability.** Separate “who will start and where” from “what this hitter tends to do.” Recency, pitcher rest, substitutions, and courtesy-runner usage affect lineup identity. Do not grade a tendency miss when the real error was lineup reconstruction.

4. **Opponent-specific lift in loss forensics.** “Occurred in a majority of losses” is misleading. A lever matters only if it occurs materially more in losses than wins or the opponent’s normal games. “Scored first” is generically associated with winning; raw 4+ walk and 2+ steal thresholds are also exposure-sensitive. Show counts and lift, or label it a historical thread rather than a blueprint.

5. **Metric-definition discipline.** Every rate needs its own denominator and coverage floor. Fifteen IP does not make FPS% trustworthy if few pitches were charted. Do not conflate whiff-per-swing with swinging-strike-per-pitch. Do not call left/right spray “pull/opposite” unless handedness is known.

## PII and ethics failure modes

Git-ignore is necessary but nowhere near sufficient. The new eval log creates a durable minor-performance dataset even after report HTML expires.

You need:

- Season-end deletion or deidentification of event-level eval records;
- no names in prediction packets when opaque runtime IDs suffice;
- no prediction payloads in logs, exceptions, email, analytics, support bundles, or test fixtures;
- explicit backup retention and access rules;
- no real postgame examples copied into epics, research notes, or parameter-change comments;
- scrutiny of what the optional LLM sends to a third party, independent of whether it computes predictions.

Repo-specific warning: the existing scanner does not detect names, and planning/idea artifacts are explicitly an ungated gap ([PII rule](/workspaces/baseball-crawl/.claude/rules/pii-safety.md:48)). An eval workflow will repeatedly tempt people to paste named examples into exactly those files.

## Smallest defensible sequence

1. Add minimal our-team + target-game context, with no registry and no named self-scout in the public artifact.
2. Propagate candidate-set uncertainty into the game plan.
3. Persist one immutable, PII-minimized fact/prediction packet.
4. Grade only starter and lineup forecasts first, with coverage and naïve baselines.
5. Add logic/rules/parameter fingerprints—no registry or tuning machinery.
6. Extend grading predictor by predictor only after each has an observable, non-causal target.

The dangerous version is “grade everything, centralize every knob, then sharpen.” That will produce a beautifully deterministic feedback machine which mostly measures its own definitions.
