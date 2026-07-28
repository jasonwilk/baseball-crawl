---
name: public-games-timezone-and-fullday
description: /public/teams/{public_id}/games timezone is a per-EVENT operator-entered string that includes legacy tzdata aliases our runtime cannot resolve; is_full_day events carry a midnight-UTC date MARKER, not an instant. Both silently corrupt game_date.
metadata:
  type: reference
---

Measured 2026-07-27 across the full reachable corpus (28 public_ids = every team
we hold one for; 1064 schedule events; 28/28 fetched OK). Motivated IDEA-218 /
E-278. Companion to [[public-games-opponent-identity]] -- same endpoint,
different fields.

## `timezone` is per-EVENT, operator-entered, and NOT a safe IANA name

Every event carries the key (0 of 1064 omit it), so absence is always an explicit
`null`. It is **not** a per-team property -- three different values appeared
inside a single team's own schedule. It appears to be whatever the event's
creator entered.

Live distribution: `America/Chicago` 1005, `US/Central` 25, `America/Denver` 17,
`(null)` 6, `America/New_York` 6, `US/Pacific` 4, `America/Phoenix` 1.

**`US/Central` and `US/Pacific` are legacy tzdata "backward" aliases and raise
`ZoneInfoNotFoundError` in our runtime** -- `python:3.13-slim` omits the backward
links, `/usr/share/zoneinfo/US/` does not exist, and the `tzdata` PyPI package is
not installed. Verified by execution in BOTH the devcontainer and the running app
container, so this ships. `derive_local_date` catches it, WARNs, and returns the
**unconverted UTC date** -- so an evening game past 00:00Z lands one day LATE.

**The trap that fooled a careful reader**: the aliases are semantically identical
to their canonical zones (same offset), so reasoning about what the strings MEAN
concludes "they convert identically" and eliminates the real cause. They are
semantically identical and operationally not, because the lookup never happens.
Run it; do not reason about it. See [[measurement-discipline]].

## `is_full_day: true` means `start_ts` is a DATE MARKER, not an instant

Shape: `start_ts` at exactly midnight UTC, `end_ts` exactly 24h later,
`timezone: null`. Localizing that "instant" shifts it back into the PREVIOUS day.
All 6 full-day events in the corpus are mis-dated this way (one day EARLY).

`is_full_day` correlated perfectly with a null `timezone` in both directions
(6/6 each way) -- but n=6, so treat null-tz as a proxy and key on `is_full_day`,
the causal signal. **Nothing in `src/` reads `is_full_day`**; only the
authenticated `schedule.py` reads a differently-named `full_day`.

`scouting_loader.py` (~line 767) already documents this exact shift for the
synthetic `1900-01-01` sentinel and never generalized it to real full-day events.

## The two defects shift in OPPOSITE directions

Alias class **+1 day**, full-day class **−1 day**. A uniform date-shift repair
corrupts one population while fixing the other. Key any repair off the mechanism.

## Do not "fix" this with an alias normalization map

Two observed bad strings do not bound what GC can send -- the operator can enter
any of several dozen backward links (`US/Eastern`, `US/Mountain`, `Canada/*`...).
A 2-entry map is a denylist that fails OPEN on the first unseen alias. **Install
`tzdata`**: one dependency, covers the whole namespace including aliases never
seen. Same "observed-closed is not proven-closed" lesson as
[[public-team-age-group-level-field]] and [[public-team-ngb-off-map-values]].

## Three more live facts from the same sweep (2026-07-27, E-278 review)

- **`end_ts` is NOT an identity discriminator.** Two schedule listings of ONE real
  game carried `end_ts` two hours apart (a 1-hour and a 3-hour event) while their
  `start_ts` differed by 0.960s. An `end_ts` equality rule MISSES that duplicate.
  `games` has no `end_ts` column, so this divergence is invisible to any DB-side
  detector and visible only in the payload.
- **GC really does double-list one game under two event ids, and it PERSISTS.**
  Re-fetched live and both ids are still returned. So the duplicate is
  reproducible from the API and a re-scout RE-CREATES it -- prevention at load is
  load-bearing, not cleanup.
- **`game_status` gained a value: `"live"` is emitted** (2 of 1064). The endpoint
  doc previously asserted it had never been observed; corrected in place with a
  dated tombstone. Treat the status set as OPEN and gate on `== "completed"`.
  Same "observed closed is not proven closed" lesson as the alias set above.

## Method note worth reusing

The live-payload path and an independent re-derivation from stored rows produced
the SAME completed-population counts (9 and 2). Two independent measurement paths
agreeing exactly is the cheapest available check that a mechanism model is right.

Also measured: `start_ts` was present on 1064/1064 events, so
`scouting_loader`'s `start_ts or end_ts` fallback is real but UNEXERCISED.
