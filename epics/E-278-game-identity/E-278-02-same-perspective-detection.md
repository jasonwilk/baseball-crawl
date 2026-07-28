# E-278-02: Same-perspective duplicate detection at load

## Epic
[E-278: Game Identity — One Real Game, More Than One Row](epic.md)

## Status
`TODO`

## Description
After this story is complete, when GameChanger double-lists a single real game in
one team's schedule under two distinct event ids, the loader recognizes the
second listing as the same game and does not persist a second `games` row.
Genuine doubleheaders and consecutive-day tournament games continue to persist as
distinct rows.

## Context

**⚠️ THE DOUBLE-LISTING IS PERSPECTIVE-ASYMMETRIC, and one corollary is a trap.**
Measured by as-epicA on both sides of a second double-scored game (epic TN-16):
the team whose schedule carries the duplicate shows **2** listings; **the opponent
shows 1.** Three things follow, and the middle one is the trap:

- **A CLEAN GC RECORD IS NOT EVIDENCE THAT NO DOUBLE-SCORING OCCURRED.** The
  opponent's record reconciles exactly — zero collapsed groups — **precisely
  because it received one listing of a game that WAS double-scored.** Any check
  that reads a clean record as "this game was not double-scored" is exactly
  backwards. Do not build one.
- **Visibility depends on which team you scout**: two rows from one side, one from
  the other. That is this story's same-perspective shape.
- **So prevention MUST sit at load**, and cannot lean on the opponent's schedule to
  disambiguate — the opponent's schedule is where the evidence is missing. This is
  an independent confirmation of the design, arrived at from the payload side.

**This is a LIVE, RECURRING defect, not a historical artifact — verified against
the API on 2026-07-27.** as-epicA fetched the team's live public schedule and
both event ids are still listed right now, `start_ts` 21:00:00.**000**Z and
21:00:00.**960**Z, both `game_status: completed`. **So a re-scout after the prod
reset WILL re-create this duplicate.** That matters for how the epic's
forward-accuracy-only ruling reads here: this story is not cleaning up something
the reset disposes of, it is preventing something the next crawl reproduces.

GameChanger's own schedule lists one game twice, 0.96 seconds apart, under two
distinct event ids. Both listings share a perspective, so
`_find_duplicate_game`'s same-perspective tiebreaker
(`src/gamechanger/loaders/game_loader.py:1362-1372`) compares `start_time` by
byte equality, finds them unequal, and classifies them as a doubleheader. A
second row is inserted and the game is double-counted in season aggregates. This
is the only live wrong number the operator-staged ingestion audit found.

**Any fix must tolerate GC double-listing a game, and must NOT loosen the
schedule-count guard.** That guard (`game_loader.py:1258`) fires only when the
own crawl schedule reports exactly one game against this pair on this date AND
the DB holds exactly one candidate row. For this defect GC genuinely reports
**2**, so the guard correctly declines — and no count-based rule can discriminate
here, because the count is honestly 2 for both a double-listing and a real
doubleheader.

**Score agreement is the trigger; the sub-second time delta NARROWS it, and it is
never the trigger by itself** (epic TN-5, as SPLIT). ⚰ **This paragraph previously
read "the discriminator is agreement of scores AND play counts" — retired for the
LOAD path, where play counts are 0 and 0 and cannot corroborate anything. Do not
restore it here.** That discriminator survives, unchanged and validated, on the
**offline/audit** surface: measured by de-epicA in dev, identical scores plus a
play-count ratio ≥ 0.85 selects exactly one pair across all 37 same-date groups
with zero false positives. It uses the season's data to EXCLUDE rather than to
authorize a merge, and a wrong merge is the destructive direction. See Technical
Approach constraints 1 and 5 for which rule governs which surface.

**Separation evidence, labeled by locality — the two databases differ and neither
overrides the other:**

| Population | Doubleheader gap | Near-zero deltas |
|---|---|---|
| PROD | 150-180 min | the duplicate alone, at 0.96 s |
| DEV (measured) | **floor 90 min** | **four**: 0.96 s plus three same-date twins at exactly 0.00 s |

Do not write "150 minutes" or "four orders of magnitude" into a criterion — those
are PROD figures. The dev floor is 90 minutes and the separation is 3.75 orders.
**"The duplicate is the only thing near zero" is false in dev — corpus-wide.**
But all three of those 0.00-second pairs carry disjoint perspectives, so within
the same-perspective branch the duplicate *is* the only thing near zero. See
Technical Approach constraint 2; the distinction is what makes a near-zero
narrowing condition usable here at all.

**Why this story prevents rather than repairs.** `merge_duplicate_game` refuses
shared-perspective pairs, and that refusal is **structural, not stylistic** (epic
TN-6): `perspective_team_id` sits inside the UNIQUE key on every game-child
table, so when the perspectives are shared, every child re-point collides — 58
guaranteed `plays` collisions on the known pair alone. Loosening the refusal does
not produce a working merge; it produces one that aborts partway. The
same-perspective collapse primitive was CUT for that reason, which is what makes
prevention-at-load this story's whole job.

## Acceptance Criteria

- [ ] **AC-1**: Given two schedule listings that share a perspective, fall on the
      same date against the same opponent, carry identical per-team scores, and
      differ in start time by under a second, when both are loaded, then exactly
      one `games` row exists for that pair and date.
- [ ] **AC-2**: Given two same-perspective listings on one date whose per-team
      scores are **not equal** and whose start times are separated by at least the
      dev doubleheader floor (90 minutes), when both are loaded, then two distinct
      `games` rows exist. This is the FRESH-1..6 shape — identical perspectives,
      7200-second gaps, differing scores on every pair — which epic OQ-5
      adjudicated as genuine doubleheaders. **The predicate is exact score
      inequality and is deliberately NOT expressed via `_SCORE_TOLERANCE_RUNS`**:
      that constant governs the OFFLINE repair predicate, and importing it here
      would couple the load path to a threshold AC-6 may change on the other
      surface. Score AGREEMENT is the load-time trigger, so its negation is the
      right predicate.
- [ ] **AC-3**: Given a candidate pair for which the own crawl schedule reports a
      count of 2, when it is loaded, then the schedule-count guard at
      `game_loader.py:1258` does not fire for it. That guard's firing condition is
      unchanged by this story.
- [ ] **AC-4**: Given `merge_duplicate_game`, when this story is complete, then
      its shared-perspective refusal still refuses — a shared-perspective pair
      modifies zero rows. This story does not relax it.
- [ ] **AC-5** (cross-story regression guard): Given two same-perspective
      listings whose true venue-local calendar dates genuinely differ by one day —
      the consecutive-day tournament shape — when both are loaded **with
      E-278-04's corrected date derivation in place**, then they retain
      **different** `game_date` values and two distinct `games` rows exist.
      **Reachable RED**: E-278-04 changes the derived date, and an over-correcting
      derivation that collapsed a genuine consecutive-day pair onto one date would
      make them dedup candidates for the first time — this criterion goes red
      there. Per Technical Approach for why the earlier phrasing was
      unfalsifiable.
- [ ] **AC-6**: Given `_SCORE_TOLERANCE_RUNS` (`src/db/game_merge.py:101`), when
      this story is complete, then the implementer has recorded an explicit
      verdict on whether it should widen from 1 to 2, with the reason. Declining
      to widen is a valid verdict; changing the constant without a recorded
      reason, or leaving no verdict at all, violates this criterion. Per
      Technical Approach for the context.
- [ ] **AC-7**: Given the **recorded payload values in Technical Approach
      ("Fixture specification")**, when AC-1's fixture is built, then it encodes
      those values. **No live API call, no live DB query, and no external lookup
      is required or permitted** — the values are transcribed in this story
      precisely so the fixture has a durable, in-repo source. A fixture whose
      field values contradict that block violates this criterion, and that is
      checkable from the diff alone.
- [ ] **AC-8** (anti-vacuity guard, and the destructive direction): Given the
      load-time rule this story implements, when it runs, then it does **not**
      consult `plays` row counts. A pair whose stored play counts are both zero —
      which is every pair at first load — must not be treated as corroborated on
      that basis. Per Technical Approach constraint 1 for why `0 == 0` reads as
      agreement and why that is the destructive direction.
- [ ] **AC-9** (forces the open design decision to be explicit): Given that the
      corroborator TN-5 names is unavailable at the load decision point, when this
      story is complete, then the implementer has recorded one of two verdicts
      with its reasoning: **either** a corroborating condition available in the
      payload at that point was identified and the rule consults it — in which
      case a pair with agreeing scores and a sub-second delta that the
      corroborator *rejects* must remain two rows, and a test demonstrates that —
      **or** score agreement narrowed by a sub-second delta, scoped to the
      same-perspective branch, was judged sufficient, with the supporting evidence
      and the residual risk stated. Silence fails this criterion; either verdict
      passes. Per Technical Approach.
- [ ] **AC-10** (the safety-relevant half of the harm): Given AC-1's collapsed
      pair, when the load completes, then the surviving game carries exactly one
      set of per-player pitching and batting rows for that perspective — no
      duplicated `player_game_pitching` or `player_game_batting` row survives
      under the surviving `game_id`. Per Technical Approach; asserting the
      `games`-row count alone does not satisfy this.

## Technical Approach

**Five constraints on the design space. The first three are de-epicA's
measurements; the fourth records the TN-5 split and the fifth is as-epicA's live
payload measurement, which rules out the most obvious corroborator.**

**1. The play-count corroborator is NOT available where prevention has to happen,
and consulting it anyway is actively DANGEROUS.** Confirmed twice.
`_find_duplicate_game` runs inside `load_team` (`generator.py:1912`); plays are
crawled and loaded ~340 lines of pipeline later (`_crawl_and_load_plays`,
`generator.py:2253`). Both listings arrive in the same crawl — their `created_at`
values are one second apart — so at the dedup decision neither row has any
`plays` rows. de-epicA's 37-group measurement came from `SELECT COUNT(*) FROM
plays` on **stored** rows: validation that the discriminator separates cleanly,
not a prescription for where it runs.

**se-epicA established the failure modes, and they run in opposite directions:**

- **First load of a double-listed game: play counts are 0 and 0.** A naive
  implementation reads `0 == 0` as *agreement*, making the play-count
  corroborator **vacuously true for every candidate pair** — which leaves scores
  as the sole discriminator, and two genuine doubleheader games can carry
  identical scorelines. **That is a destructive merge**, the direction this epic
  must never fail in.
- **Re-scout: the existing row carries plays (58) and the incoming row has 0**, so
  a ratio never clears 0.85 and the duplicate persists on every regeneration.

**So this story MUST NOT consult play counts at the load decision point** — see
AC-8. Play-count corroboration stays correct for offline and audit surfaces,
where plays genuinely exist; it is unavailable on the first load, which is
exactly the load that creates the duplicate.

**2. The sub-second delta IS usable inside the same-perspective branch. TN-5's
prohibition is correct corpus-wide and over-broad as a constraint on this
branch.** de-epicA re-ran every same-date same-pair combination with a start
delta under 90 minutes: the three 0.00-second pairs all carry **disjoint**
perspectives (and all three also disagree on score, which is why the
cross-perspective branch does not already collapse them — a separate Class B/C
question). Exactly one near-zero pair shares a perspective, and it is PAIR-ALPHA.
Since cross-perspective candidates are resolved in an earlier branch before the
same-perspective tiebreaker at `:1362-1372` is reached, those three cannot be
false positives for a rule that only runs there. In de-epicA's restatement: *"the
duplicate is not the only thing near zero corpus-wide — but it is the only
same-perspective thing near zero, and the same-perspective branch is the only
place a near-zero rule would run."* Score agreement remains the trigger; the
sub-second delta narrows it.

**3. "Same game" and "same content" are NOT equivalent here — which rules out the
obvious substitute for the play-count corroborator.** Because `load_payload`
commits per call, the first row's stat rows *are* committed and readable when the
second row's dedup check runs, so a corroborator comparing the incoming payload's
player lines against the candidate's stored lines is mechanically available. But
the two rows carry **materially different content**: 18 batting rows versus 10,
and 4 pitching rows versus 1 — even though the scores match exactly and both
ended with 58 plays. **A naive "identical player line sets" test would therefore
not fire on this pair.** Something subset- or overlap-shaped might, but that
would be designed on a single observed instance; de-epicA declined to recommend a
predicate on n=1 and so does this story. Take it as a constraint discovered
rather than a solution offered. The fact that one real game's two rows disagree
this much on boxscore line counts is itself unexplained, and it is a further
argument for keeping the ACs outcome-shaped (one row versus two) rather than
pinning a mechanism.

**4. `end_ts` is a measured NON-DISCRIMINATOR. Do not build the corroborator on
it.** This is the single most expensive thing to rediscover, because `end_ts` is
an obvious candidate and the failure is silent. On the live payload for the real
pair, the two listings' end instants are **two hours apart**:

- listing 1: 21:00:00.000Z → 22:00:00.000Z (a 1-hour event)
- listing 2: 21:00:00.960Z → 2026-07-26T00:00:00.960Z (a 3-hour event)

A corroborator has to do two things: **agree for the duplicate** and **disagree
for a genuine doubleheader**. `end_ts` fails the first half outright — any
equality rule on it would MISS this duplicate, which is the pair the story exists
to catch. If a review or a suggested fix proposes `end_ts` as a payload-level
corroborator, this measurement is the reason to decline it. The other candidates
sometimes named alongside it (`home_away`, `has_videos_available`) are unmeasured
here: `home_away` is necessarily equal for two same-perspective listings, so it
cannot discriminate a duplicate from a doubleheader either. Measure before
adopting any of them, and note that AC-9 permits declining a corroborator with a
reasoned verdict rather than forcing a weak one.

**Two known FALSE POSITIVES for detector shapes adjacent to this one** (epic TN-17,
relayed from a Live-side investigation). Neither affects this story's chosen
rule, and both are recorded so nobody builds them later:

- **A FORFEIT is a false positive for any "the counterparty's schedule lacks this
  game" detector** — identical signature, entirely benign cause. That detector
  shape is tempting precisely because of the perspective asymmetry above; do not
  reach for it without handling forfeits.
- **GC itself lists two games 75 minutes apart against a literal `"Triple Crown
  Tournament"` opponent string.** Upstream data entry, not our defect. Detection
  that treats it as one game would be wrong.

**5. TN-5 splits into an OFFLINE discriminator and a LOAD-TIME rule, and AC-9 is
where that split gets decided.** TN-5 as originally written could not be honoured
at this site: its discriminator (scores AND play counts) is unavailable here, and
the residual rule (scores AND a sub-second delta) makes the delta the effective
discriminator, which TN-5 forbids. Both halves cannot hold at once, so the epic
now separates them:

- **Offline / audit surfaces** keep scores + play-count ratio ≥ 0.85 — validated
  across 37 same-date groups with zero false positives. That statement is sound
  and stays.
- **The load-time rule** takes score agreement as the trigger, with the
  sub-second delta as a narrowing condition, scoped to the same-perspective
  branch — where de-epicA's re-measurement found zero false positives, because
  all three other near-zero pairs are cross-perspective and never reach it.

What is genuinely unsettled is whether score-plus-delta is *enough* on its own,
which is why AC-9 demands a verdict rather than assuming one. If you look for a
payload corroborator, note the precedent: `incoming_schedule_count` is resolved
at the call site in `_load_boxscore_data` and threaded in as a plain parameter
(`game_loader.py`, around the `_find_duplicate_game` call), and a
boxscore-derived corroborator would take the identical shape. **But check it
against constraint 3 first** — the two real rows differ at 18 vs 10 batting rows
and 4 vs 1 pitching, so any corroborator built on *equality* of line counts will
not fire on the very pair this story exists to catch.

**A knock-on worth raising rather than absorbing:** epic TN-6 cut the
same-perspective collapse primitive on the ground that this story "stops it at
load." That justification assumed a load-time rule was straightforwardly
available. If AC-9's verdict is that no adequate corroborator exists at the
decision point, TN-6's reasoning should be re-examined rather than treated as
settled — raise it to PM instead of working around it.

**Why AC-5 was rewritten (2026-07-27).** It previously read *"two
same-perspective listings on consecutive calendar dates produce two rows"* and
carried an honest note that it **could not fail** — `_find_duplicate_game`'s
candidate query gates on `WHERE game_date = ?`, so consecutive-date listings never
group and never reach any rule this story writes. Labelling an unfalsifiable
criterion does not repair it: the project's binding standard is that every AC has
a reachable RED, and a criterion that cannot go red is prose that will pass every
review. **The guard-rail intent was worth keeping, so it was re-pointed rather
than deleted** — at a hazard that is genuinely reachable, because E-278-04 (which
runs first) changes the very `game_date` this story's dedup groups on. An
over-correcting derivation that collapsed a real consecutive-day pair onto one
date would create dedup candidates that do not exist today, and AC-5 now catches
exactly that.

**On AC-10, and why it is not redundant with AC-1.** The double-count harm is not
confined to season batting and pitching lines: a double-counted pitching
appearance inflates pitch count, innings pitched, and appearance order — the
exact inputs to pitch-count rest-day compliance and the Most Likely Arms
predictor. Those are safety-relevant, not cosmetic. Whole-game idempotency
probably already prevents a second stat-row write under the surviving `game_id`,
but "probably" is doing real work in that sentence given what depends on it, and
constraint 3 shows the two rows' stat content is not identical — so the
collapse's effect on the losing row's stat rows deserves an assertion rather than
an assumption. baseball-coach raised this; the ask is that AC-1's tests assert
stat-row counts, not only the `games`-row count.

### Fixture specification (AC-7) — the durable, in-repo source

**These values are transcribed here so the fixture needs no live lookup.** They
come from the live public schedule payload (as-epicA, 2026-07-27) corroborated
against the stored dev rows (de-epicA). Identifiers are deliberately absent per
epic TN-10 — invent neutral ids and team names for the fixture.

| Field | Listing 1 | Listing 2 |
|---|---|---|
| `start_ts` | `2026-07-25T21:00:00.000Z` | `2026-07-25T21:00:00.960Z` |
| `end_ts` | `2026-07-25T22:00:00.000Z` | `2026-07-26T00:00:00.960Z` |
| `game_status` | `completed` | `completed` |
| per-team scores | 0-3 | 0-3 (identical) |
| `timezone` | same on both | same on both |
| perspective | one shared `perspective_team_id` | same shared value |
| event id | distinct | distinct |

Derived facts, for assertions rather than fixture fields: start delta **0.96 s**;
`end_ts` delta **two hours** (a 1-hour event vs a 3-hour one) — the
non-discriminator of constraint 4; **58 plays on each stored row**; `created_at`
one second apart, the signature of two loads inside one run.

**Why the payload and not the stored rows:** `games` has no `end_ts` column, so a
fixture derived from stored rows alone **cannot express the two-hour divergence**
that constraint 4 turns on. That is also why the table above is the artifact —
without it, AC-7 would name a source no dispatch worktree can reach.

**Background.** Epic OQ-7 is ANSWERED: PAIR-ALPHA is genuinely in
this database — de-epicA supplied both row ids from a live dev query whose
`created_at` differs from the handoff's, so it is a real query and not an echo of
the handoff. Epic TN-11 said the opposite and **has been corrected**; do not
plan against its superseded text. The observed shape is two rows, same
perspective, same date (2026-07-25), start times 0.96 seconds apart, identical
scores and orientation, and 58 plays on each row. Their `created_at` values sit
one second apart — the signature of two loads of one game inside a single run,
and the evidence that distinguished a real dev query from the handoff echoed
back.

⚰ **Two paragraphs here previously instructed the implementer to "establish the
field values from the payload, then encode them in the fixture." RETIRED
2026-07-27 as a conflicting second source instruction** — it sent the implementer
to a live payload that a dispatch worktree cannot reach (no `data/`, no `.env`,
per `.claude/rules/worktree-isolation.md`), while the Fixture specification block
above already carries the values. **One rule: the table above is the source.**

What survives from those paragraphs, because it is the reason the table exists:
the payload carries fields the `games` schema does not — most importantly
`end_ts`, which has no column and whose two-hour divergence constraint 4 turns on
— so a fixture derived from stored rows alone is lossy. And per epic TN-10 the
fixture must carry no real team name, `public_id`, or GC UUID; that content would
block the commit at the pre-commit doc-PII gate.

**On AC-6.** `_SCORE_TOLERANCE_RUNS` gates `is_offline_same_game`, the OFFLINE
operator repair predicate — not the load path this story changes. PAIR-DELTA (a
cross-perspective pair whose scores differ by 2) is grouped and then refused by
it today. de-epicA leans against widening the constant and toward letting a
stronger corroborator carry the case; the epic records this as a design call for
this story rather than a settled decision. Note the tension when you rule: the
constant lives on the historical-repair surface, and historical repair is an
explicit epic non-goal, so "decline, with reason" is a coherent verdict.

**On writing any dedup-audit query** (epic TN-12): a same-date self-join ordered
by `game_id` rather than by date checks only one direction and returns a
confident, plausible, **incomplete** answer — that is what missed the confirmed
pair on the first attempt. Any query of this shape owes a both-directions check.

**Identifier hygiene** (epic TN-10): refer to rows by date and role only. Never
put a real team name, `public_id`, or GC UUID in a fixture or comment under
`epics/**` — and never truncate or prefix a real name to disguise it.

## Dependencies
- **Blocked by**: E-278-04. Both stories modify
  `src/gamechanger/loaders/game_loader.py`, so the sequencing rule requires an
  explicit ordering. **04 runs first for a semantic reason, not just a textual
  one**: 04 changes the derived `game_date`, and that value is the key
  `_find_duplicate_game` groups candidates by — so dedup behavior is defined
  against corrected dates rather than against dates this epic is about to move.
- **Blocks**: E-278-05 (which renames a field in the same module) and **E-278-01**
  (which must update the exact-dict `_query_record` assertions in
  `tests/test_loaders/test_game_dedup.py`, a file this story also modifies).

**⚠️ Line numbers in this story are accurate as of planning (2026-07-27) and will
ROT.** E-278-04 edits `_derive_game_date` and `GameSummaryEntry`, both of which
sit *above* every `game_loader.py` line this story cites, so each citation will
have shifted by the time this runs. Navigate by SYMBOL — the same-perspective
tiebreaker branch inside `_find_duplicate_game`, the schedule-count guard at the
top of the same function — and treat the numbers as hints to be re-confirmed, per
`.claude/rules/tool-output-integrity.md` ("cite a stable anchor, not a line
range").

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` — `_find_duplicate_game`, the
  same-perspective tiebreaker branch
- `tests/test_loaders/test_game_dedup.py`
- `tests/test_loaders/test_game_loader.py`
- `src/db/game_merge.py` — only if AC-6's verdict is to widen; otherwise
  unmodified and the verdict is recorded in the story's completion report

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-278-05**: the final state of `game_loader.py`'s
  same-perspective branch, which E-278-05's rename must sweep.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes

The standing "six duplicate Freshman games" operator item is a **false positive**
(epic OQ-5) — those six pairs are genuine doubleheaders with identical
perspectives, exactly 7200-second start gaps, and materially different scores on
every pair. Running a merge against them would have been destructive; the
existing planner groups them by date and then correctly refuses on the
disjointness gate. AC-2 pins that they keep behaving that way.

Epic OQ-3 is open and unrelated to this story's mechanism: IDEA-219's
mis-attribution phantom has an unidentified creating path, and its row is
currently the only known instance, so it must not be reset away before the path
is identified.
