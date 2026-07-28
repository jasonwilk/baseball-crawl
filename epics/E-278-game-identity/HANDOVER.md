# E-278 planning handover — PM drain, 2026-07-27

# ⚰ SUPERSEDED 2026-07-27 — DO NOT PLAN FROM THIS FILE

**This handover has been overtaken by the work it handed off. It is retained as a record of
what was known at the drain, not as guidance.** Two of its statements are now actively
wrong, and both would mislead:

1. **"No story files exist yet"** — all four exist. `epic.md`'s Stories table names them.
2. **"E-278-02's trigger is agreement of scores AND play counts"** (in the story-writing
   section below) — **RETIRED for the load path.** Play counts are 0 and 0 at the load
   decision point, so consulting them reads as vacuous agreement; story 02's AC-8 forbids
   it. That discriminator now governs the OFFLINE/audit surface only. See TN-5's SPLIT
   block in `epic.md`.

Several other items below were open questions that have since been ANSWERED (OQ-4, OQ-7,
and the two raised during story authoring). **`epic.md` and the four story files are the
durable record.**

---

**⚠️ THIS FILE IS A RELAY. `epic.md` is the durable record and wins wherever the two
disagree. Every citation below must be verified before you act on it** — that discipline
found four defects during this planning round, including two in artifacts that had already
passed review.

Written at a deliberate context drain. Nothing below is blocked on me; it is state that
would otherwise be lost.

## Where planning stands

Epic is `DRAFT`. **Story shape is FINAL at four** — do not re-derive it:

| Story | Scope | Gates |
|---|---|---|
| E-278-01 | Record header: count ties, pin games-played semantics | OQ-1 (operator may override) |
| E-278-02 | Same-perspective duplicate detection at load | **OQ-7** — decides fixtures |
| E-278-04 | tzdata + alias normalization + fail-closed + `is_full_day` | OQ-4 (bounding only) |
| E-278-05 | Rename the misleading derivation field; fix docstrings | none |

**No story files exist yet.** That is the next task and it was deliberately not started.

E-278-03 was **cut before instantiation** (TN-6). The number is **not reused**.

## Settled — do NOT re-open

- **Coach ruling on record semantics (TN-7).** Games PLAYED, not games with DATA. No
  `EXISTS` gate on `_query_record`. Ties always show the trailing `-0`, matching
  GameChanger. **Now backed by measurement, not just argument** — OQ-2 found 20 real games
  across 12 teams that the rejected fix would have erased.
- **IDEA-220 closed without a story** (TN-8). Its own promotion criterion is not met.
- **No historical repair, dev or prod.** Operator ruling. Data is resettable.
- **Do not widen the dedup natural key.** Argued against on executed evidence, twice
  (TN-14). Two distinct upstream defects produce these splits; a looser key masks both and
  loosens merges for consecutive-day tournament games, where a wrong merge is destructive.
- **Do not loosen `merge_duplicate_game`'s shared-perspective refusal.** It is structural,
  not stylistic (TN-6).
- **The standing six-Freshman-duplicates item is a FALSE POSITIVE** (OQ-5) — genuine
  doubleheaders. Merging them would have been destructive.

## Open, with what each decides

- **OQ-1** — triage file vs coach ruling on the record clause. Planning on coach.
  Operator override would change E-278-01.
- **OQ-3** — IDEA-219's creating path, unidentified. **Its row is the only known instance;
  it must not be reset away first.** Main is flagging this to the operator directly.
- **OQ-4** — which alias strings appear across the live payload corpus. as-epicA offered to
  measure. Bounds E-278-04's normalization surface; cheap, not blocking.
- **OQ-7 — CLOSED 2026-07-27. PAIR-ALPHA IS here.** DE supplied both row ids from a live dev
  query; `created_at` differs from the handoff's, so it is a real query, not an echo.
  **TN-11 was WRONG and is corrected — E-278-02 builds against live dev rows, no synthetic
  fixtures.** **No open question now blocks any story's acceptance criteria.**

**Late arrivals recorded after the first flush** (read TN-15 before trusting any earlier
expert summary): de-epicA withdrew its own tzdata-alias claim after executing it, so all
three agents now agree; PAIR-ECHO's two accounts are answering *different questions* and are
both right; PAIR-FOXTROT is settled as one game on as-epicA's evidence, superseding DE's
"do not write confirmed"; and `backfill_game_dates(dry_run=True)` **must not** be used as a
survey instrument because it shares the very defect it would measure.

## Four corrections this round made to artifacts that had already passed review

Carry these; each was a real defect in something authoritative.

1. **IDEA-218's stated remedy is false for its own case.** It claims the offline corrective
   already exists; `plan_duplicate_game_merges` groups by `(season_id, game_date, unordered
   pair)`, so it cannot reach a date-split twin. Verified by reading the grouping.
2. **IDEA-218's candidate 3 is refuted, and a fix aimed at it would be a no-op** — a
   *different* fallback fired, in a different function. The full-day mechanism (TN-14) is a
   **fourth candidate IDEA-218 does not list at all.**
3. **as-epicA's report cites "(migration 014)"** for `games.start_time` / `games.timezone`.
   No migration 013 or 014 exists; the set tops out at `012` and both columns come from
   `001_initial_schema.sql`. Columns real, provenance false.
4. **A refuted position briefly entered TN-3** — that `US/Central` and `America/Chicago`
   "convert identically". `ZoneInfo('US/Central')` raises in this runtime. TN-3 now carries
   the refutation explicitly so it is not restored.

## Method notes worth more than the findings they produced

- **TN-12**: a dedup-audit self-join ordered by `game_id` rather than by date checks only
  one direction and returns a confident, plausible, **incomplete** answer. It missed the
  confirmed pair. Any story writing such a query owes a both-directions check.
- **OQ-2's narrow framing returns 1 and is wrong** — restricting to rows carrying a
  `game_perspectives` row excludes the population being counted, because that row is
  written *after* stat data loads.
- **The 116-vs-142 comparison compared different measures** — a single-perspective count
  against a two-perspective total.
- **One alias confusion cost three agents independently**: DE a hypothesis, SE a
  recommendation, and it was the actual root cause as-epicA found. When experts disagree
  here, prefer the one who *executed* over the one who reasoned from meaning.

## When writing the story files

- Use **TN-13's neutral labels** (PAIR-ALPHA … FRESH-1..6). **Never put a real team name,
  `public_id`, or GC UUID in `epics/**`** — it trips the pre-commit doc-PII byte-gate and
  blocks the planning commit (TN-10).
- **E-278-02's trigger is agreement of scores AND play counts; the sub-second time delta is
  a NARROWING condition, never the trigger** (TN-5). Do not write "150 minutes" or "four
  orders of magnitude" into a criterion — those are PROD figures; dev's floor is 90 minutes.
- **Send draft ACs to coach-epicA** — it asked to review them, and asked to be told
  immediately if a live unscored-own-game case turns up. OQ-2 found 20; coach has not seen
  that number yet.
- Every AC needs a reachable RED and should assert a **property**, not an action.
- **Require an executed reproduction, not a code-reading argument.** Both experts arrived at
  this independently and de-epicA volunteered it against itself: *"both of my eliminations
  were reasoned from what values mean, both premises were correct, and both conclusions were
  wrong, because the runtime did something the semantics did not predict."* This session
  produced **four** such reversals — DE twice, SE twice — every one a correct premise under a
  wrong conclusion, and every one caught by execution rather than by review. Build it into
  E-278-04's criteria.
- **OQ-4's answer inverts the obvious story-04 scope**: do NOT build a timezone
  normalization map — install `tzdata`. A map is a denylist that fails open on the next
  unseen alias. Read the OQ-4 entry before writing that story.
- E-278-01 should include a **regression pin** so a future agent cannot quietly re-add the
  `EXISTS` clause the coach rejected.
