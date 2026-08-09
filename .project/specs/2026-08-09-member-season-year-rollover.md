<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# Member team `season_year` at a season rollover

**Date**: 2026-08-09 · **Status**: `PARKED` — set aside deliberately by operator ruling
(2026-08-09): the likely real answer is OPERATIONAL, not code, so do NOT build the force-update.
**Revisit near spring 2027**, when a rollover actually happens and the premise below can be tested
against reality instead of reasoned about. Stub depth on purpose — there is no plan here, and there
should not be one until the revisit.

**Source**: found twice, independently, during the execution of
`2026-08-05-rung-c-season-year-filter.md` — once by `claude -p "/code-review"` and once by the
operator-typed `/code-review`, which corrected the first one's mitigation reasoning.

## The observation

Nothing refreshes a MEMBER team's `teams.season_year` once it is set.

- `ensure_team_row` backfills NULL→value only (`_backfill_season_year`, `src/db/teams.py`), so
  morning-run's fill can create the value but never update it.
- `src/reports/generator.py`'s force-update (`season_year = COALESCE(?, season_year)`) does **not**
  reach this row. In morning-run, `generate_fn` is called with the OPPONENT's `public_id`, so that
  UPDATE always targets the opponent's `teams.id`, never the member's. ⚠ This is the specific claim
  that was asserted the other way earlier in the chunk and then refuted — do not re-derive it from
  memory, it reads plausible and is wrong.

Since the rung-(c) season filter landed, that column is load-bearing. A team first seen in spring
2026 is pinned at 2026; in 2027 every `POST /search` hit carries `season.year = 2027`, every hit
drops, and rung (c) auto-accepts **nothing** for that team — with no self-heal short of editing the
row by hand. It fails CLOSED (opponents go to the operator queue, no wrong-team resolution), so this
is a capability outage, not a correctness hole.

## Why this is probably NOT a code problem (the operator's ruling, and the thing to test in 2027)

Under single-season doctrine (CLAUDE.md: "One season, one report at a time") a new season is expected
to begin with a **reset + re-scout**, which recreates `teams` rows from scratch carrying the new
year. If that is how the rollover actually happens, the pinned value never survives to matter and
the force-update would be machinery against a case that cannot occur.

**That is a premise, not a measurement.** It is exactly the kind of claim this repo has been bitten
by before, so it is written down to be CHECKED rather than assumed. The revisit asks one question:
*at the 2027 rollover, did the member rows get recreated, or did a stale year survive?*

## If the premise proves wrong

Preferred fallback is **derive-at-read**, not the force-update: have the ladder resolve the member's
current season year at resolution time rather than trusting a stored column. Rationale for the
preference — a force-update writes `teams.season_year`, which feeds
`derive_season_id_for_team()` and therefore the `season_id` that games are filed under
(`.claude/rules/architecture-subsystems.md`). That blast radius is the reason it was declined here,
and it does not shrink later. Deriving at read changes no durable state.

## What was built instead (already landed, do not redo)

DETECTION only, which the operator accepted as sufficient for now: when the season filter drops
EVERY team hit, `_resolve_via_search` logs a WARNING that names the suspicion, and distinguishes
"different year" from "no usable year" so an upstream API shape change is not misread as a stale
member row. A rollover outage is therefore loud in the logs rather than silent.

## Out of scope

- **The force-update itself.** Explicitly declined 2026-08-09. Do not build it as a "small fix".
- **Backfilling or migrating existing `season_year` values.**
- **`--dry-run` writing the own-team row.** `bb report morning-run --dry-run` does create and commit
  the team row (pre-existing behavior, not introduced by the filter chunk), so a dry run against a
  profile pins a year. Noted here because it is the same column; it is not this stub's question.
