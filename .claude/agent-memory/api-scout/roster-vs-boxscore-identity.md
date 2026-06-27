---
name: roster-vs-boxscore-identity
description: Why a team's boxscore player-identity tables can hold MORE players than its roster -- the status="removed" mechanism and person_id non-unification
metadata:
  type: reference
---

# Roster vs boxscore player identity (the "removed" mechanism)

Empirically characterized 2026-06-21 on Elkhorn North Equitable Bank Reserve
(`public_id` PkMl2UWGdrgG, `gc_uuid` d51af44d-...; our DB teams.id=87, tracked).

## The fragmentation, explained

- **Roster** (`GET /teams/public/{public_id}/players`) returned **14** players --
  single-initial first names (`"W Horn"`), jersey numbers, 5 fields only
  (id, first_name, last_name, number, avatar_url). No athlete_profile_id, no
  status, no season flag.
- **Boxscore identity tables** (`game-stream-processing/{event_id}/boxscore`,
  team `players[]` array) contained a **constant 25-UUID superset in EVERY one
  of the 46 games** (the `players[]` array is a team-level identity table, NOT a
  per-game lineup). 14 of those = roster; **11 extra** UUIDs, full first names
  (`"Wes Horn"`), mostly jersey-less.
- Discriminator: `GET /players/{uuid}` returns a **`status`** field --
  `"active"` for the 14 roster UUIDs, `"removed"` for the 11 extras. **Roster
  endpoints return only `active`; boxscores retain `removed` players' historical
  stats.** This is the whole 14-vs-25 story.

## person_id does NOT unify duplicates

`GET /players/{uuid}` carries `person_id`, but `person_id == id` on EVERY record
sampled (active and removed, with/without user account). It is NOT a cross-record
key. Three humans (Horn, Krapp, Kaufman) exist as BOTH a `removed` early record
AND an `active` later record (e.g. Pierson "Kaufmann" removed 9303c7aa vs
"Kaufman" #7 active 1836d42f) -- each carries its own person_id = own id. **GC
exposes no field that links the two UUIDs of one human.** `/athlete-profile/{id}`
returns 403 for a non-managed team (and expects an athlete_profile_id, not a
player UUID). `user_id` (present only on claimed records) is the real
"has user account" signal -- NOT person_id (the old doc note was wrong; corrected).

## Temporal cutover pattern (inference, strongly supported)

All 11 `removed` UUIDs' stats are confined to games **on/before 2026-05-02**.
From **2026-05-06** onward every lineup entry is an `active` roster UUID
(shadow count = 0). Each duplicate pair (removed vs active for one human) has
**zero same-game batting overlap**. Inference: early games were scored with
manually-typed / unlinked player records; the roster was later set up properly
and those manual records marked `removed`. Of the 11 removed humans, 3 were
re-rostered as active twins; 8 were never carried to the active roster.

## Loader takeaway (for DE/SE, not yet implemented)

Our loaders ingest all 46 boxscores, so they pick up the `removed` players'
stats -> 23 distinct players in our compiled data vs 14 on the GC roster, with
duplicate-human splits (Pierson). To dedup/flag, the deterministic signal is
`GET /players/{uuid}.status == "removed"` (reachable for tracked teams). No
GC-side identity-unification field exists for the cross-UUID same-human case.

See [[exploration-findings]]. Docs corrected: `get-players-player_id.md`
(status enum, user_id/bats optional fields, person_id non-unification),
`get-teams-public-public_id-players.md` (auth REQUIRED: 401 w/o token, 200 with).
