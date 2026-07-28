---
method: GET
path: /game-streams/gamestream-recap-story/{event_id}
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      HTTP 200 confirmed for event 3cab6a64-REDACTED (redacted team game) on 2026-03-09.
      Query params game_stream_id and team_id observed in this call. HTTP 404
      for event 1e0f8dfc-REDACTED on 2026-03-07 -- recap not generated for all games.
      Status upgraded from OBSERVED to CONFIRMED.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.game_stream_ns_recap+json; version=0.1.0"
gc_user_action: null
query_params:
  - name: game_stream_id
    required: unknown
    description: >
      The game stream UUID for the event. May be used to resolve the stream
      when the event_id alone is ambiguous.
  - name: team_id
    required: unknown
    description: >
      The team UUID. May scope the recap to a team-specific narrative perspective.
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: "2026-07-28"
tags: [games, events]
caveats:
  - >
    HTTP 404 FOR SOME EVENTS: Returns 404 when a recap has not been generated for the
    event. May require the game to be fully processed and scored. Not available for
    all games. Event 1e0f8dfc-REDACTED returned 404 on 2026-03-07; event 3cab6a64-REDACTED returned
    200 on 2026-03-09.
  - >
    `game_utc_start` IS MISNAMED and does NOT carry the game's start instant. On
    both events captured 2026-07-28 it was byte-identical to
    `recap_generation_date` and equal to the moment of the request, while the
    games had started more than a day earlier. Never source a game start time
    from this field. See the Response section.
  - >
    NO SCOREKEEPER / AUTHOR FIELD: the payload is narrative prose plus two
    timestamps; nothing identifies who scored the game or which of two competing
    scorebooks a recap belongs to. (2026-07-28)
  - >
    PII-BEARING BODY: the narrative embeds real team, player, and venue names.
    Do not commit raw response samples.
  - >
    QUERY PARAMS: game_stream_id and team_id observed as query params (not path params)
    in the 2026-03-09 capture. Whether these are required or optional is not confirmed.
related_schemas: []
see_also:
  - path: /game-streams/insight-story/bats/{event_id}
    reason: Related insight endpoint (also returns 404 for some events)
  - path: /game-stream-processing/{game_stream_id}/plays
    reason: Play-by-play data -- preferred for coaching use
  - path: /events/{event_id}/best-game-stream-id
    reason: Resolves event_id to game_stream_id (needed for game_stream_id query param)
---

# GET /game-streams/gamestream-recap-story/{event_id}

**Status:** CONFIRMED LIVE -- 200 OK (some games). HTTP 404 for events without a generated recap. Last verified: 2026-07-28 (schema captured).

Returns a narrative recap story for a completed game event. Accepts optional `game_stream_id` and `team_id` query params that may scope or resolve the recap.

```
GET https://api.team-manager.gc.com/game-streams/gamestream-recap-story/{event_id}?game_stream_id={game_stream_id}&team_id={team_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | UUID | Schedule event UUID |

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `game_stream_id` | UUID | unknown | Game stream UUID for the event (see `/events/{event_id}/best-game-stream-id`) |
| `team_id` | UUID | unknown | Team UUID -- may scope narrative to team's perspective |

## Response

**Schema captured 2026-07-28** (two events, both 200 OK). Single top-level key `recap`:

| Field | Type | Description |
|-------|------|-------------|
| `recap._id` | UUID | Echoes the `event_id` path parameter. |
| `recap.status` | string | `"active"` observed. |
| `recap.recap_type` | string | `"recap_stories"` observed. |
| `recap.title` | array | Rich-text runs -- objects of `{type, content}`, `type: "text"` observed. 3-4 runs per title. Assemble by concatenating `content`. |
| `recap.paragraphs` | array of arrays | Narrative body. Each paragraph is itself an array of the same `{type, content}` runs. 9-10 paragraphs observed. |
| `recap.recap_generation_date` | ISO 8601 (no zone suffix) | When the recap text was generated. |
| `recap.game_utc_start` | ISO 8601 (no zone suffix) | **MISNAMED -- this is NOT the game's start instant.** See below. |

> **⚠️ `game_utc_start` does not carry the game's start time.** Verified on both events 2026-07-28: `game_utc_start` was byte-identical to `recap_generation_date`, and both equalled the **moment of the request** -- while the games themselves had started **more than a day earlier** (confirmed against `start_ts` from `/public/game-stream-processing/{event_id}/details` for the same events). Two events fetched seconds apart returned the *same* `game_utc_start` as each other, which no pair of real game starts would. **Never read a game's start time from this field** -- use the schedule (`/public/teams/{public_id}/games`) or the details endpoint. The equality with `recap_generation_date` also suggests the recap is generated (or re-stamped) at request time rather than served from a fixed record; that mechanism is inferred, not established.

There is **no structured scorekeeper, author, or stream-owner field** -- the payload carries narrative prose plus the two timestamps above and nothing that identifies who scored the game. A caller trying to distinguish two competing scorebooks of one game will not find the answer here.

The narrative prose embeds real team names, player names, and venue names, so a captured body is PII-bearing -- do not commit raw samples.

**Shape** (content redacted -- the real strings are narrative prose):

```json
{
  "recap": {
    "_id": "00000000-REDACTED",
    "status": "active",
    "recap_type": "recap_stories",
    "title": [
      {"type": "text", "content": "Walk-Off Seals The Deal In "},
      {"type": "text", "content": "Example Park"}
    ],
    "paragraphs": [
      [{"type": "text", "content": "It came down to the wire on Sunday at Example Park, as ..."}]
    ],
    "recap_generation_date": "2026-07-28T00:41:10",
    "game_utc_start": "2026-07-28T00:41:10"
  }
}
```

## Investigation Status

**200 confirmed:** Event `3cab6a64-REDACTED` (redacted team, 2026-03-09 session) returned 200. Re-confirmed 2026-07-28 on two further events with the schema documented above; both calls included `game_stream_id` and `team_id` query params.

**404 confirmed:** Event `1e0f8dfc-REDACTED` returned 404 on 2026-03-07. Recap may not be generated for all games.

**Open:** whether `team_id` actually scopes the narrative to one team's perspective is still untested -- both 2026-07-28 calls passed the same `team_id`, so nothing here discriminates.

**Discovered:** 2026-03-05 (proxy). **Last confirmed (200):** 2026-07-28.
