---
name: game-duplicate-class-taxonomy
description: Four distinct duplicate-game classes in the live DB, which existing tooling reaches each, and the hard boundary (last_scoring_update is not persisted) on investigating date-split twins.
metadata:
  type: project
---

# Duplicate `games` rows: four classes, not one defect

Measured against the live dev DB (928 completed games) during E-278 planning, 2026-07-27.
Every verdict below came from RUNNING `is_offline_same_game` against the real rows, not from
reading the predicate.

| Class | n | Shape | Reached by existing tooling? |
|---|---|---|---|
| A | 1 | same-perspective, same date, sub-second start delta, identical scores + play counts | **No** — predicate False (perspectives not disjoint) |
| B | 2 | same-date, disjoint perspectives, scores differ by 1 run | **YES — `bb data merge-duplicate-games` collapses these today** |
| C | 1 | same-date, disjoint, scores differ by **2** runs (outside `_SCORE_TOLERANCE_RUNS = 1`) | No — grouped, then refused |
| D | 2 | different `game_date`, disjoint, identical scores + play counts | No — never grouped |

**Why:** the three detection surfaces (`_find_duplicate_game`'s `WHERE game_date = ?`,
`plan_duplicate_game_merges`' `(season_id, game_date, pair)` grouping, and the audit SQL) all gate
on date equality, so class D is structurally invisible to every one of them. Class B is not a gap
at all — it is an unrun command.

**How to apply:** never quote "the audit found 1 duplicate" as a census. Before scoping any
game-identity work, re-run the sweep; and check whether the instance in front of you is already
reachable by the offline tool before designing anything.

## The hard boundary on any `game_date` investigation

**`last_scoring_update` — the input `_derive_game_date` actually uses — is NOT PERSISTED.** It
lives only in the in-memory `GameSummaryEntry`. `games` carries
`game_id, season_id, game_date, home_team_id, away_team_id, home_score, away_score, status,
game_stream_id, start_time, timezone, created_at` and no migration mentions it. So the mechanism
behind a date-split twin is **unreachable from the DB by construction** and needs a live
game-summaries read. Do not accept a task to "establish the mechanism from the data."

## Two findings that inverted my prior

- ⚠️ **I GOT THIS BACKWARDS ONCE — do not repeat it.** I asserted that a timezone-string disagreement
  is a red herring because `US/Central` and `America/Chicago` are "tzdata aliases for one offset."
  **FALSE in this image.** Executed: `US/Central` and `US/Pacific` raise `ZoneInfoNotFoundError`; the
  `tzdata` pip package is not installed, `available_timezones()` = 498, `/usr/share/zoneinfo/US/*`
  absent. Dockerfile is `python:3.13-slim` installing only `curl sqlite3`. **Never assert a tz string
  resolves without calling `ZoneInfo()` on it in the target environment.**
  **The better diagnosis (se-epicA's, on its own parallel version of this error): "my branch
  enumeration was right and my PROBABILITY WEIGHTING was wrong."** SE had already identified the
  unresolvable-zone branch and filed it as an exotic invalid-zone case, because it assumed `US/Central`
  was a resolvable IANA name. Re-reading the enumeration would never have caught that — the list was
  complete and the weighting was not. **Enumeration completeness does not protect against reachability
  mis-weighting; only executing the branch does.**
  Corollary that explains the 9-of-24 split: **branch C compares LOCAL against UTC, not zone against
  zone.** Inter-zone gaps are ~1 hour, so "an afternoon start is nowhere near midnight" correctly kills
  the zone-vs-zone path — but the local-vs-UTC gap for Central is 5-6 hours, so every start at/after
  ~19:00 local crosses. That PREDICTS the evening/afternoon split rather than merely fitting it.
- **`last_scoring_update` is VESTIGIAL — it does NOT carry a book-touch instant on any live path.**
  `scouting_loader.py:773` sets `start_ts = game.get("start_ts") or game.get("end_ts") or ""` and
  line 813 assigns `last_scoring_update=str(start_ts)`. The real field belongs to the authenticated
  game-summaries endpoint whose loader entry points died in E-256. **Consequence: the derivation input
  IS recoverable from the DB** whenever `start_time` is non-NULL, so "the input is thrown away" is
  wrong. Note the two fields have DIFFERENT fallbacks — `last_scoring_update` falls back to `end_ts`,
  `start_time` does not — so an absent `start_ts` dates the game from its END instant and leaves
  `start_time` NULL, which `backfill_game_dates` then skips (its tier 3).

## THE date-split mechanism: unresolvable tz + a fallback that returns UTC instead of failing closed

`derive_local_date` catches `ZoneInfoNotFoundError`, logs a WARNING, and **returns the UTC date**
(`src/util/timezone.py:100-119`) rather than `None`. So a row whose payload carries a legacy `US/*`
string silently gets a UTC-slice date. **Measured: 24 rows carry an unresolvable tz (20 `US/Central`,
4 `US/Pacific`); all 24 stored a UTC-slice date; 9 have a genuinely WRONG `game_date`, off by one
day.** The other 15 are afternoon games where UTC slice coincidentally equals the local date.

This CREATES date-split twins: one perspective's row carries `America/Chicago` and dates correctly,
its twin carries `US/Central` and dates a day late, so the pair never groups. Fixing the resolution
would have prevented one of the two known class-D pairs outright — with a correct date the pair
becomes same-date with exactly matching scores, which the existing cross-perspective branch already
collapses.

**Do NOT use `backfill_game_dates(dry_run=True)` to measure this** — it re-derives through the same
`derive_local_date`, so it reproduces the bug and reports agreement. **The instrument shares the
defect it would measure.** Resolve the aliases by hand instead.

The OTHER class-D pair is a SECOND, OPPOSITE-POLARITY defect: the **all-day-event** mechanism
(established by api-scout against live payloads, E-278). One perspective sends an all-day calendar
event — `is_full_day: true`, `start_ts` at midnight UTC, a 24-hour span, null timezone — whose
`start_ts` is a **DATE MARKER, not an instant**. We localize it as though it were an instant and shift
it back a day. The other perspective encodes the same "no known start time" as midnight LOCAL, so the
5-hour gap is the zone offset BY CONSTRUCTION, not a disagreement.

⚠️ **Wording trap I fell into: I called both ECHO rows "correctly re-derived" when they are only
SELF-CONSISTENTLY re-derived** — the code's output matches what is stored, and the stored value is
still WRONG. "Re-derivation reproduces the stored value" says the pipeline is deterministic, NOT that
the answer is right. Never let those two collapse.

**POLARITY IS OPPOSITE BETWEEN THE TWO MECHANISMS — a uniform date-shift repair would fix one
population and corrupt the other:** alias rows are **+1 day**, full-day rows are **−1 day**.
Corpus scope (api-scout, 28 schedules / 1064 events; live-payload count and stored-row re-derivation
agree exactly): **11 mis-dated rows — 9 alias, 2 full-day — plus 4 more queued in not-yet-completed
full-day events.** **No single change closes class D.**

`is_full_day` is present in the payload and **read by nothing in `src/`** (grep finds only the
authenticated `schedule.py`, on a differently-named `full_day` key). `scouting_loader.py` ~767 already
documents this exact "UTC-midnight shifts back a day" failure for the synthetic `1900-01-01` sentinel
and never generalized it to REAL full-day events of identical shape. Corroborating DB signal I can
confirm independently: **both NULL-timezone rows sit at exactly midnight UTC** — in this corpus NULL
timezone is a usable proxy for a full-day event (n=2, so a finding aid, not a rule to key a fix on).

## `start_time` across perspectives: usually stable, NOT guaranteed

Measured over five disjoint-perspective pairs: three are **byte-identical (0.0 min)**; the other two
differ by 150 and 300 minutes. The code comment at the cross-perspective branch claims "~30-minute
offsets" — both outliers far exceed that. `.claude/rules/perspective-provenance.md` classifies this
field neither way; the honest classification is "usually stable, observed disagreements up to 300
minutes."

## The discriminator that beats the time-delta window

Applying **"identical scores AND play-count ratio ≥ 0.85"** to every same-date same-pair combination
in the season selects **exactly the class-A pair, zero false positives across all 37 same-date
groups.** No genuine doubleheader has both.

⚠️ **BUT IT IS AN OFFLINE DISCRIMINATOR AND CANNOT RUN AT THE PREVENTION POINT.** Prevention lives in
`_find_duplicate_game`, during the BOXSCORE load; the plays stage runs LATER in the generator. Two
rows created in the SAME run therefore have **zero plays** when the dedup decision is made, so the
play-count corroborator is unavailable exactly on the load that creates the duplicate. (It IS
available on a re-generation, where the prior run's plays are stored — so "unavailable" is
first-load-specific, which is the load that matters.) Caught by pm2-epicA, not by me: I measured
offline and never checked availability at the decision site. **When you validate a discriminator on
stored data, separately ask whether its inputs exist where the fix has to run.**

Substitute that looks available and is NOT sufficient: the candidate row's stat rows ARE committed at
decision time (`load_payload` commits per call). But the two class-A rows hold **different** line
counts — batting 18 vs 10, pitching 4 vs 1 — despite identical scores and identical final play counts.
So "identical player line sets" would not fire. **"Same game" and "same content" are not equivalent
here**, and that divergence is unexplained.

Empirical separation for reference: twins sit at delta {0s, 0.96s}; doubleheaders at **[5400s,
10800s] — the floor is 90 minutes, not the 150 that gets quoted (150-180 is a PROD figure; 90 is
dev).** Prefer score-agreement over a start-time window generally, because start_time is
scorekeeper-entered and nothing in the schema stops a doubleheader's game 2 carrying game 1's time.

**SCOPING CORRECTION (pm2-epicA).** I wrote "three same-date pairs sit at delta 0.00s, so 'only the
duplicate is near zero' is false" — true corpus-wide, **over-broad as a constraint on the
same-perspective branch**. Executed: all three 0.00s pairs are **CROSS-perspective (disjoint)** and are
resolved by the cross-perspective branch before the same-perspective tiebreaker is reached. Only the
class-A pair is same-perspective near zero. **Scoped to the same-perspective branch, a sub-second
delta has ZERO false positives in this corpus** — so a near-zero trigger IS defensible there, though
corpus-wide it is not. Always scope a false-positive claim to the branch the rule would run in.

## Same-perspective merge is a different OPERATION, not a loosened refusal

`merge_duplicate_game`'s shared-perspective refusal is structurally required, not stylistic. Every
game-child UNIQUE is perspective-scoped — `player_game_batting`/`_pitching`
`UNIQUE(game_id, player_id, perspective_team_id)`, `plays UNIQUE(game_id, play_order,
perspective_team_id)`, `game_perspectives PRIMARY KEY (game_id, perspective_team_id)`. Disjoint
perspectives make re-pointing collision-free; a SHARED perspective makes **every** child re-point
collide (the class-A pair would hit 58 `plays` collisions alone). So collapsing a same-perspective
twin is RECONCILIATION (per-child keep-A/keep-B/merge policy), not RELOCATION — a new primitive
alongside `merge_duplicate_game`, never a relaxation inside it.

## Adjudications that came back FALSE POSITIVE (do not re-investigate)

- **The "6 Freshman duplicates" operator standing item is 6 genuine DOUBLEHEADERS.** All six: identical
  (NOT disjoint) perspectives on both rows, start gaps of exactly 7200s, materially different scores.
  The planner already groups them (same date) and correctly refuses on the disjointness gate. Running
  the merge command against them would have been the destructive mistake.
- **A "116-play game" is not a double-load.** All 116 plays carry ONE `perspective_team_id`, contiguous
  `play_order`. The single-perspective distribution over 884 games is min 31 / median 59 / p95 74 /
  **max 116** — so it is the real maximum, an outlier not a defect.
- **UNIT CONFLATION, the reusable trap:** a two-perspective TOTAL (142 = 71+71) compared against a
  PER-PERSPECTIVE norm (47-77) manufactures alarm. **42 games** carry plays under >1 perspective,
  totals 60-150. A high plays count is only evidence after you group by `perspective_team_id`.

## Scored-but-unscorebooked own games (measured 2026-07-27, all subject teams)

**20 genuine cases across 12 of 28 subject teams**, per-team rates 2.4%-15.8% of own completed games.
17 of the 20 have plays from the OPPOSING perspective (played and charted, just not by this team).

**Two measurement traps, both of which I hit:**
1. **Restricting to games with a `game_perspectives` row undercounts catastrophically** (gives 1, not
   30) — that row is written AFTER stat data loads, so it is systematically absent from exactly the
   scored-but-empty population being measured.
2. **An uncollapsed twin generates TWO false entries**, because each row holds only one side's stats.
   10 of the raw 30 were this artifact. Always subtract known duplicate rows before reporting.

**How to apply:** this is the evidence base for the coach ruling that `_query_record` keeps
games-played semantics and must NOT gain a stat-row `EXISTS` gate — the gate would erase 20 real
games across 12 teams to remove 2 bad rows. Fix the rows, not the query.

## No storage-layer backstop for an unscoped plays aggregate

`plays` UNIQUE is `(game_id, play_order, perspective_team_id)` — the doubled shape is INTENDED. But
**no `plays` index includes `perspective_team_id`** (`idx_plays_game_id`, `_batter_id`, `_pitcher_id`,
and `idx_plays_fps` on `(pitcher_id, is_first_pitch_strike)`). So an unscoped aggregate
double-counts silently AND performs fine — nothing at the storage layer looks wrong or slow. The
consumer audit is the only check; there is no structural guarantee to fall back on.

Related: [[scouting_query_role_vs_dedup_filters]], [[games_row_vs_stat_rows_coupling]],
[[plays_boxscore_reconciliation_baseline]].
