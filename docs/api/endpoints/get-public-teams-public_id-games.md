---
method: GET
path: /public/teams/{public_id}/games
status: CONFIRMED
auth: none
profiles:
  web:
    status: confirmed
    notes: >
      No auth required. 32 records confirmed for team QTiLIb2Lui3b (2026-03-04).
      Re-confirmed 2026-06-12 against a different team (WThfCgtHecNF, 34 records):
      response now includes UPCOMING/scheduled games (game_status null, future
      start_ts), not just completed games. opponent_team carries name +
      optional avatar_url ONLY -- no opponent identity ID of any kind.
  mobile:
    status: not_applicable
    notes: Public endpoint -- no auth profile distinction.
accept: "application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: data/raw/public-team-games-sample.json
raw_sample_size: "32 game records, 25.7 KB"
discovered: "2026-03-04"
last_confirmed: "2026-07-20"
tags: [games, team, public]
caveats:
  - >
    opponent_team carries `name` and an optional `avatar_url` ONLY. There is NO
    opponent identity ID in this payload -- no `public_id`, no `root_team_id`, no
    `progenitor_team_id`, no slug -- for ANY game, completed or upcoming, and
    regardless of how the coach entered the opponent (manual typing vs. team
    lookup). The own-team public schedule therefore CANNOT auto-resolve an
    opponent's public_id. A scheduler must resolve opponents by name (e.g., via
    `POST /search`) or fall back to operator input. See "Opponent identity" below.
  - >
    Response now includes UPCOMING/scheduled games (confirmed 2026-06-12), not
    just completed ones. Upcoming games have `game_status: null` and a future
    `start_ts`; they omit `score`, `game_status` value, and `has_videos_available`
    in observed records. The earlier "completed games only" claim is superseded.
  - >
    PERSPECTIVE-SPECIFIC `id`: the `id` returned here is specific to the queried
    team's schedule -- the SAME real-world game gets a DIFFERENT `id` depending on
    which team's public schedule you query. Unlike the authenticated
    `game-summaries` (stable `event_id`/`game_stream_id` per game), this endpoint's
    `id` cannot be used to dedupe the same game across two teams' schedules. It
    still works as the boxscore/plays `event_id` for the perspective it came from.
  - >
    ACCEPT IS STRICT -- a WRONG vendor resource type returns HTTP 415, not a
    fallback representation (verified live 2026-07-26). The plausible-looking
    `application/vnd.gc.com.public_game:list+json; version=0.0.0` is NOT this
    endpoint's type and 415s; the correct type is `public_team_schedule_event`
    and is not guessable from the path. A GENERIC `application/json, text/plain,
    */*` returns a normal 200 with the full body -- so the 415 fires on a
    MISMATCH, not on the absence of a vendor type. Read a 415 here as "check the
    Accept header", never as "endpoint broken or removed". See
    `../error-handling.md` ("415 on a Mismatched Vendor Accept Type").
related_schemas: []
see_also:
  - path: /game-stream-processing/{event_id}/boxscore
    reason: The `id` field from this response IS the event_id for boxscore (confirmed 2026-03-12, terminology corrected 2026-03-19) -- no bridge call needed
  - path: /public/teams/{public_id}/games/preview
    reason: Near-duplicate endpoint; uses event_id instead of id, lacks has_videos_available; prefer /games
  - path: /public/teams/{public_id}
    reason: Team profile (also no-auth)
  - path: /teams/{team_id}/schedule
    reason: Authenticated schedule including practices and other events
  - path: /public/game-stream-processing/{game_stream_id}/details
    reason: Inning-by-inning line scores for individual games (no-auth)
---

# GET /public/teams/{public_id}/games

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-06-12 (34 records, team WThfCgtHecNF; previously 32 records, team QTiLIb2Lui3b, 2026-03-04). **AUTHENTICATION: NOT REQUIRED.**

Returns a team's games -- both **completed** and **upcoming/scheduled** -- with final scores (completed only), opponent **names** (no opponent ID), and home/away status. No credentials required. Provides scores and opponent names for any team with a known `public_id`, enabling scouting without authentication.

> **Opponent identity (verified 2026-06-12):** `opponent_team` carries `name` and an optional `avatar_url` ONLY. There is **NO** opponent identity ID of any kind in this payload -- no `public_id`, no `root_team_id`, no `progenitor_team_id`. This holds for every game and is independent of the coach's opponent entry mode (manual typing vs. team lookup). See the **Opponent Identity** section below for what this means for schedulers.

```
GET https://api.team-manager.gc.com/public/teams/{public_id}/games
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `public_id` | string | Alphanumeric public ID slug (e.g., `"QTiLIb2Lui3b"`). NOT a UUID. |

## Headers

```
Accept: application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0
User-Agent: Mozilla/5.0 ...
```

Do NOT include `gc-token` or `gc-device-id` headers.

## Response

Bare JSON array of game records (completed and upcoming). 34 records in a single response (no pagination observed for this team). Upcoming games have `game_status: null` and a future `start_ts`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | **This IS the `event_id`** used by the boxscore and plays endpoints. Pass directly to `GET /game-stream-processing/{event_id}/boxscore` (and `.../plays`) -- no bridge call needed (confirmed 2026-03-12, terminology corrected 2026-03-19). Same value as `event_id` in the authenticated flow (game-summaries) and as the `event_id` field in `/games/preview` (identical value, different field name). **Perspective-specific**: this `id` is specific to the queried team's schedule -- the same real-world game has a different `id` in the opponent's schedule (see Known Limitations). |
| `opponent_team` | object | Opponent team info. **Carries `name` and optional `avatar_url` ONLY -- no identity ID.** See Opponent Identity below. |
| `opponent_team.name` | string | Opponent team name (free-text label; not guaranteed to match any GC team record). |
| `opponent_team.avatar_url` | string or absent | Opponent avatar URL. Present on 11/34 records (2026-06-12). Absent (not null, not empty) when no avatar. |
| `is_full_day` | boolean | Whether this is a full-day event. |
| `start_ts` | ISO 8601 | Game start timestamp (UTC). |
| `end_ts` | ISO 8601 | Game end timestamp (UTC). |
| `timezone` | string | IANA timezone string. |
| `home_away` | string | `"home"` or `"away"`. |
| `score` | object or absent | Final score. **Present on completed games only**; absent on upcoming games. |
| `score.team` | int | This team's final score. |
| `score.opponent_team` | int | Opponent's final score. |
| `game_status` | string, null, or **absent** | `"completed"` for finished/scored games. For a game that is NOT finished the field is either **`null`** (observed 2026-06-12) or **entirely absent** (the key is omitted — observed 2026-07-19); treat both identically (`.get("game_status") == "completed"`). A third value **`"new"`** was observed live (2026-07-19): a game-stream stub was created but not yet scored — it carries a `score` object of `{team: 0, opponent_team: 0}`. **Not-final games (absent/null/`"new"`) REMAIN in the schedule array indefinitely** — including past-dated games that were never played/scored (confirmed 2026-07-19: April- and June-dated games with no status and no score still present in July). GC does NOT drop a postponed/cancelled/unplayed game from the array. See the Not-Final vs Removed caveat below. |
| `has_videos_available` | boolean or absent | Whether game video is available. Present on completed games; absent on upcoming games in observed records. |
| `has_live_stream` | boolean | `false` for all observed records. |

### Not-Final vs Removed (schedule reconciliation)

**Confirmed live 2026-07-19 across 17 teams (633 game records):** a game that is not finished — whether upcoming, in a created-but-unscored `"new"` state, or a past-dated game that was never played/scored — **stays in the schedule array**. `game_status` for these is `"completed"`-absent (either the literal string `"new"`, or `null`, or the key omitted) and there is no `score` object (except `"new"`, which carries a 0-0 `score`). Observed status distribution: 615 `"completed"`, 17 with `game_status` absent, 1 `"new"`. No `"postponed"`/`"suspended"`/`"in_progress"`/`"live"` status string was ever observed — GC does not emit a distinct postponed status here; a postponed/cancelled/unplayed game simply lacks the `completed` status and score while remaining in the array (multiple April- and June-dated unplayed games were still present in the July snapshot).

**Consequence for any schedule-diff / reconcile logic:** "present in the schedule array but not `completed`" is a TRANSIENT/not-yet-final state, NOT a removal. Only a game **fully absent from the full schedule array** indicates a genuine removal/void. Therefore a reconcile MUST diff prior-loaded games against the **full** `/games` array (all `game_status` values), NOT a `completed`-only filtered subset — a `completed`-only subset would misclassify every legitimately-present not-final game (and every past unplayed game) as "removed."

### Status Stability: `completed` is Terminal (longitudinal, 2026-07-20)

The 2026-07-19 probe recorded a **snapshot** of statuses. A follow-up **longitudinal** probe (2026-07-20) tested whether a status ever moves BACKWARD, using our own database as the prior snapshot: every stored game row was ingested from a boxscore, so GC reported it `"completed"` at load time (load timestamps spanning 2026-06-30 to 2026-07-14, i.e. a 6-to-20-day elapsed window). Re-fetching the same 17 teams' full schedules (636 live records) and diffing against **583 games GC had previously reported as `completed`**:

- **0 reversions.** Not one prior-`completed` game came back with `game_status` absent, `null`, `"new"`, or any other non-`completed` value. `"completed"` behaved as a **terminal** state over the observed window.
- **0 genuine removals.** 22 stored `game_id`s were absent from the queried team's array, but **all 22** are explained by the perspective-specific `id` (see the caveat above): each is a cross-perspective twin whose surviving `game_id` is the OTHER perspective team's `event_id`, and each was confirmed PRESENT and `completed` in that other team's live array. After controlling for perspective, the genuine-removal count is zero.
- Live status distribution held steady at 621 `"completed"`, 14 key-ABSENT, 1 `"new"`.

**Do not read this as proof that reversion is impossible** — a scorekeeper un-finalizing a game is a UI action we have not exercised, and no probe can prove a negative. It establishes that reversion is **not observed** across 583 games over a multi-week window, so it is rare at most, not routine.

### Zero-Completed Arrays and Long-Lived Team-Seasons (2026-07-20)

Probed 15 additional team-seasons whose `public_id`s were captured in earlier sessions, spanning seasons from **spring 2019 through summer 2026** (602 records):

- **No team returned zero completed games.** Every team that had played returned its **full** completed history — including team-seasons finished up to **7 years** ago (a spring-2019 team still returns all 50 of its completed games in 2026).
- **A season rollover does NOT empty an old array.** GC team-seasons are separate entities with separate `public_id`s (the same club's 8U/9U/10U/11U/12U/13U/14U squads each carry a distinct `public_id`). A rollover mints a NEW `public_id`; it does not drain the prior one. So "season rollover" is not a mechanism that can produce a zero-completed array for a team that has played.
- **A team that does not exist returns 404, not an empty array.** `GET /public/teams/{unknown_slug}/games` → **404 `Not Found`**; a malformed (too-short) slug → **400 `Bad Request`**. A removed/re-registered team therefore surfaces as an HTTP error, not as a silently-empty success payload.

**Consequence for schedule-diff / reconcile logic:** the "fresh schedule contains zero completed games while the team has prior completed games" shape has **no observed mechanism** — not season rollover, not team removal (404), not archival, not status reversion. Treat it as a defensive edge case, not an expected one. Its benign sibling — a genuinely new team early in a season with only scheduled games — is a real shape, but by construction has no prior-loaded games to reconcile against.

### Opponent Identity

**The opponent in this payload is identified by a free-text `name` string only.** Verified 2026-06-12 across all 34 records for team `WThfCgtHecNF`: no record carries `public_id`, `root_team_id`, `progenitor_team_id`, or any slug under `opponent_team` (or anywhere else). This is true for both completed and upcoming games, and is independent of how the coach entered the opponent.

This matters for any feature that needs to **machine-resolve** the opponent (e.g., a scheduler that auto-ingests opponent rosters/schedules):

- The own-team public schedule does **NOT** distinguish the two GC opponent entry modes (manual typing vs. team lookup). The dual-entry signal (`progenitor_team_id` present = team lookup; absent = manual entry) lives only in the **authenticated** opponent endpoints (`GET /teams/{team_id}/opponents`, `GET /teams/{team_id}/opponent/{opponent_id}`), and even there it is a UUID, not a `public_id` slug.
- To get an opponent's `public_id` starting from this endpoint, resolve by `name` via `POST /search` (the gc_uuid bridge, `.claude/rules/gc-uuid-bridge.md`), accepting the name-match ambiguity and punctuation quirks; or fall back to operator input.
- The authenticated `GET /teams/{team_id}/game-summaries` is no better for this purpose: its `game_stream.opponent_id` is the opponent's team **UUID** (root_team_id namespace), not a `public_id`.

## Example Response Items

**Completed game** (has `score`, `game_status: "completed"`):

```json
{
  "id": "48c79654-REDACTED",
  "opponent_team": {
    "name": "Anytown Eagles 12U",
    "avatar_url": "https://media-service.gc.com/example-avatar-url"
  },
  "is_full_day": false,
  "start_ts": "2025-05-24T16:00:00.000Z",
  "end_ts": "2025-05-24T18:00:00.000Z",
  "timezone": "America/Chicago",
  "home_away": "away",
  "score": {"team": 4, "opponent_team": 8},
  "game_status": "completed",
  "has_videos_available": false,
  "has_live_stream": false
}
```

**Upcoming game** (verified 2026-06-12 -- no `score`, `game_status: null`, no `has_videos_available`; `opponent_team` carries `name` only, no identity ID):

```json
{
  "id": "e234cf54-REDACTED",
  "opponent_team": {
    "name": "Example Team 14U"
  },
  "is_full_day": false,
  "start_ts": "2026-06-12T20:00:00.000Z",
  "end_ts": "2026-06-12T22:00:00.000Z",
  "timezone": "America/Chicago",
  "home_away": "home",
  "game_status": null,
  "has_live_stream": false
}
```

## Comparison to /games/preview

| Dimension | `/games` | `/games/preview` |
|-----------|----------|-----------------|
| Game UUID field | `id` | `event_id` |
| `has_videos_available` | Present | Absent |
| All other fields | Identical | Identical |
| Preferred for | General use | When `has_videos_available` not needed |

**Recommendation:** Use `/games` (this endpoint) in all cases. The UUID field name difference (`id` vs `event_id`) is important if you need to join to other endpoints.

## Known Limitations

- **No opponent identity ID.** `opponent_team` carries `name` + optional `avatar_url` only -- see the Opponent Identity section. Machine-resolving an opponent requires a name-based `POST /search` or operator input.
- `opponent_team.avatar_url` is absent (not null, not empty) when no avatar exists. Use `.get("avatar_url")` to handle this.
- No pagination observed (32 games on team QTiLIb2Lui3b; 34 on WThfCgtHecNF). Behavior for teams with very large game histories unknown.
- **Both completed AND upcoming games appear** (verified 2026-06-12). Upcoming games have `game_status: null`, a future `start_ts`, and omit `score`/`has_videos_available`. (Earlier observation of "completed only" was incomplete -- likely a team with no upcoming games at capture time.) For richer in-progress / live data, the authenticated `GET /teams/{team_id}/game-summaries` may still be preferred, but it returns completed games only.
- `has_live_stream` is `false` for all observed records.
- **`"completed"` is terminal (not observed to revert).** Longitudinal probe 2026-07-20: 583 prior-`completed` games re-fetched after a 6-to-20-day window produced 0 reversions and 0 genuine removals. See "Status Stability" above.
- **Unknown `public_id` → 404, malformed → 400.** A missing team is an HTTP error, never an empty-array 200. No probed team ever returned zero completed games while having played; finished team-seasons retain their full history for years (2019 seasons still complete in 2026).
- The `id` field is the `event_id` parameter for the boxscore endpoint (confirmed 2026-03-12, terminology corrected 2026-03-19). This is the public-endpoint equivalent of `event_id` in the authenticated flow (game-summaries). `/games/preview` uses `event_id` as the field name for the same value; `/games` uses `id`.
- **Perspective-specific `id` (do not cross-team dedupe on it).** The `id` is specific to the queried team's public schedule: the same real-world game returns a DIFFERENT `id` when fetched from the opponent's schedule. This is unlike the authenticated `game-summaries`, which returns a stable `event_id`/`game_stream_id` per game. The `id` still works as the boxscore/plays `event_id` for the perspective it came from -- but two teams' schedules cannot be deduped to one game by matching `id`.

**Discovered:** 2026-03-04. **Confirmed no-auth:** 2026-03-04. **Opponent-identity + upcoming-games behavior verified:** 2026-06-12.
