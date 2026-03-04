# GameChanger Season Stats -- Raw Response Research Artifact

**Endpoint:** `GET /teams/{team_id}/season-stats`
**Team ID:** `72bb77d8-54ca-42d2-8547-9da4880d0cb4`
**Captured:** 2026-03-04
**HTTP Status:** 200 OK
**Credentials:** REDACTED -- token and device-id stripped before storage

---

## Request (redacted)

```
GET https://api.team-manager.gc.com/teams/72bb77d8-54ca-42d2-8547-9da4880d0cb4/season-stats

Accept: application/vnd.gc.com.team_season_stats+json; version=0.2.0
accept-language: en-US,en;q=0.9
cache-control: no-cache
content-type: application/vnd.gc.com.none+json; version=undefined
dnt: 1
gc-app-name: web
gc-device-id: {GC_DEVICE_ID}
gc-token: {GC_TOKEN}
gc-user-action: data_loading:team_stats
gc-user-action-id: bad3656d-11bb-402f-ade4-5a697ba061d8
origin: https://web.gc.com
pragma: no-cache
priority: u=1, i
referer: https://web.gc.com/
sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

---

## Top-Level Response Structure

The response is a single JSON object (not an array) with three top-level keys:

```
{
  "id": "<team_uuid>",
  "team_id": "<team_uuid>",        // same value as id
  "stats_data": {
    "players": { ... },            // per-player stats keyed by player UUID
    "streaks": { ... },            // hot/cold streak data keyed by player UUID
    "stats": { ... }               // team aggregate stats
  }
}
```

---

## Players Section

`stats_data.players` is an object keyed by player UUID. Each value has:

```json
{
  "<player_uuid>": {
    "stats": {
      "offense": { ... },   // batting stats
      "defense": { ... },   // pitching + fielding stats
      "general": {
        "GP": 84            // games played
      }
    }
  }
}
```

### Players observed in this response

10 players were present in this capture:

| Player UUID | GP (general) | Sample offense stats |
|-------------|-------------|----------------------|
| b7790d88-ce4c-4197-92c5-d6086547ce92 | 84 | AVG .255, OBP .423, OPS .709 |
| 77c74470-5d1c-4723-a7e3-348c0ed84e5f | 80 | AVG .177, OBP .443, OPS .643 |
| e9a04fc5-f49d-44b4-bf3a-c8ff04bb5e4a | 68 | AVG .323, OBP .431, OPS .824 |
| c4fca852-ec12-47eb-bf5b-772d1306f0b1 | 73 | AVG .136, OBP .277, OPS .421 |
| e8534cc3-fc54-435f-8878-743499e2f2d4 | 87 | AVG .373, OBP .546, OPS 1.083 |
| 8119312c-45b0-4ddd-b157-2512c3521086 | 88 | AVG .393, OBP .533, OPS 1.100 |
| 3050e40b-dbf3-4f9a-bb71-ce77e546206f | 90 | AVG .354, OBP .449, OPS .899 |
| 879a99fd-ef90-4cce-9794-4ec0f78224bb | 91 | AVG .389, OBP .481, OPS 1.078 |
| 83a7b908-733e-420c-bf82-67f532ccf219 | 90 | AVG .176, OBP .333, OPS .557 |
| 11ceb5ee-52ef-47c9-826a-d780bb285266 | 90 | AVG .365, OBP .548, OPS 1.135 |
| d5645a1b-d92a-4b82-9b5c-e2bfa591908f | 91 | AVG .441, OBP .569, OPS 1.177 |
| 996c48ba-9e0a-45fb-8e6c-77bee46e30f0 | 92 | AVG .330, OBP .438, OPS .933 |

---

## Offense (Batting) Fields

All fields observed in `stats.offense` for a player. Integer unless noted.

| Field | Type | Description |
|-------|------|-------------|
| `BB` | int | Walks (base on balls) |
| `CH%` | float | (always 0 in this sample -- meaning unknown) |
| `AB` | int | At bats |
| `SW%` | float | Swing % |
| `OS%` | float | (always 0 in this sample) |
| `C%` | float | Contact % |
| `LND` | int | (unclear -- possibly lined drives or landing?) |
| `LOBB` | int | (unclear -- possibly left on base by batter?) |
| `LND%` | float | LND as a percentage |
| `PS` | int | Pitches seen |
| `OS` | int | (always 0) |
| `SW` | int | Swings |
| `BA/RISP` | float | Batting average with runners in scoring position |
| `3OUTLOB` | int | Left on base when 3 out |
| `CI` | int | Catcher's interference |
| `DC%` | float | (always 0) |
| `CB%` | float | (always 0) |
| `DB%` | float | (always 0) |
| `H` | int | Hits |
| `ROE` | int | Reached on error |
| `OSSW` | int | (always 0) |
| `GP` | int | Games played (also in general) |
| `FB%` | float | (always 0 in this sample) |
| `FLB%` | float | Fly ball % |
| `2S+3` | int | (count related to 2-strike counts?) |
| `BABIP` | float | Batting average on balls in play |
| `HR` | int | Home runs |
| `GB%` | float | Ground ball % |
| `HARD` | int | Hard contact count |
| `SM%` | float | Swinging miss % |
| `INP` | int | (unclear -- possibly innings/plate appearances related) |
| `SL%` | float | (always 0) |
| `SHB` | int | Sac hits/bunts |
| `KC%` | float | (always 0) |
| `GIDP` | int | Grounded into double play |
| `SLG` | float | Slugging percentage |
| `KB%` | float | (always 0) |
| `TB` | int | Total bases |
| `SB` | int | Stolen bases |
| `3B` | int | Triples |
| `2STRIKES` | int | Plate appearances reaching 2-strike count |
| `FULL` | int | Full count plate appearances |
| `OSS` | int | (always 0) |
| `6+%` | float | % of PAs going 6+ pitches |
| `CS` | int | Caught stealing |
| `SOL` | int | Strikeouts looking |
| `2B` | int | Doubles |
| `SHF` | int | Sac flies |
| `PA` | int | Plate appearances |
| `1B` | int | Singles |
| `QAB` | int | Quality at bats |
| `R` | int | Runs scored |
| `PIK` | int | Picked off |
| `OPS` | float | On-base plus slugging |
| `AVG` | float | Batting average |
| `OB` | int | Times on base |
| `QAB%` | float | Quality at bat % |
| `CT%` | float | (always 0) |
| `ABRISP` | int | At bats with RISP |
| `6+` | int | PA count going 6+ pitches |
| `SC%` | float | (always 0) |
| `RB%` | float | (always 0) |
| `HBP` | int | Hit by pitch |
| `GSHR` | int | Grand slam home runs |
| `SB%` | float | Stolen base % |
| `AB/HR` | float | At bats per home run (only present if HR > 0) |
| `WEAK` | int | Weak contact count |
| `RBI` | int | Runs batted in |
| `SM` | int | Swinging misses |
| `GB` | int | Ground balls |
| `FLB` | int | Fly balls |
| `2S+3%` | float | (percentage form of 2S+3) |
| `BB/K` | float | Walk to strikeout ratio |
| `SO` | int | Strikeouts |
| `HRISP` | int | Hits with RISP |
| `FC` | int | Fielder's choice |
| `2OUTRBI` | int | RBI with 2 outs |
| `OBP` | float | On-base percentage |
| `PS/PA` | float | Pitches per plate appearance |
| `PA/BB` | float | Plate appearances per walk |
| `XBH` | int | Extra base hits |
| `GITP` | int | (always 0 -- grounded into triple play?) |
| `OSSM` | int | (always 0) |
| `TS` | int | Total swings (or total something) |
| `LOB` | int | Left on base |

---

## Defense (Pitching + Fielding) Fields

The `stats.defense` section combines both pitching and fielding statistics for the same player. Fields prefixed with `IP:` appear to be innings played at a specific position (fractional thirds-of-innings).

### Pitching fields

| Field | Type | Description |
|-------|------|-------------|
| `ERA` | float | Earned run average |
| `IP` | float | Innings pitched |
| `ER` | int | Earned runs |
| `H` | int | Hits allowed |
| `BB` | int | Walks allowed |
| `SO` | int | Strikeouts |
| `HR` | int | Home runs allowed |
| `BK` | int | Balks |
| `WP` | int | Wild pitches |
| `HBP` | int | Hit batters |
| `GS` | int | Games started (pitching) |
| `SVO` | int | Save opportunities |
| `WHIP` | float | Walks + hits per inning pitched |
| `FIP` | float | Fielding independent pitching |
| `BAA` | float | Batting average against |
| `K/G` | float | Strikeouts per 9 innings (or per game) |
| `K/BB` | float | Strikeout to walk ratio |
| `K/BF` | float | Strikeouts per batter faced |
| `BB/INN` | float | Walks per inning |
| `BF` | int | Batters faced |
| `GO` | int | Ground outs (pitching) |
| `AO` | int | Air outs (pitching) |
| `GO/AO` | float | Ground out to air out ratio |
| `P/BF` | float | Pitches per batter faced |
| `P/IP` | float | Pitches per inning |
| `#P` | int | Total pitches thrown |
| `TP:P` | int | (total pitches? always 0) |
| `LOO` | int | Left on base by opponent |
| `LOO%` | float | LOO % |
| `LOB%` | float | Opponent left on base % |
| `LOB` | int | (pitcher: opponent LOB) |
| `0BBINN` | int | Innings without a walk |
| `123INN` | int | 1-2-3 innings |
| `123INN%` | float | % of innings that were 1-2-3 |
| `FPS` | int | First pitch strikes |
| `FPS%` | float | First pitch strike % |
| `FPSO` | int | First pitch strike outs |
| `FPSO%` | float | First pitch strike out % |
| `FPSH` | int | First pitch strike hits |
| `FPSH%` | float | First pitch strike hit % |
| `FPSW` | int | First pitch strike walks |
| `FPSW%` | float | First pitch strike walk % |
| `LBFPN` | int | (unclear -- batters facing after first pitch?) |
| `SB` | int | Stolen bases allowed |
| `CS` | int | Caught stealing (pitcher) |
| `SB%` | float | Opponent stolen base % |
| `SBATT:C` | int | Stolen base attempts (catcher) |
| `PIK` | int | Pickoffs |
| `BBS` | int | (walks in some context) |
| `LOBBS` | int | (unclear) |
| `S%` | float | Strike % |
| `SW` | int | Swings against |
| `SM` | int | Swinging misses (pitching) |
| `SM%` | float | Swinging miss % |
| `GB` | int | Ground balls allowed |
| `FLB` | int | Fly balls allowed |
| `FLY` | int | Flies (air balls) |
| `GB%` | float | Ground ball % allowed |
| `FLB%` | float | Fly ball % allowed |
| `FLY%` | float | Fly ball % |
| `HARD` | int | Hard contact allowed |
| `HARD%` | float | Hard contact % |
| `WEAK` | int | Weak contact allowed |
| `WEAK%` | float | Weak contact % |
| `BABIP` | float | BABIP against |
| `BA/RISP` | float | Batting average against with RISP |
| `ABRISP` | int | At bats against with RISP |
| `HRISP` | int | Hits with RISP |
| `2STRIKES` | int | Batters reaching 2-strike count |
| `FULL` | int | Full count at bats |
| `1ST2OUT` | int | 1st and 2nd outs |
| `1ST2OUT%` | float | % of 1st+2nd out situations |
| `LND` | int | (unclear) |
| `LND%` | float | |
| `LOBB` | int | (unclear) |
| `<3` | int | Batters out in under 3 pitches |
| `<3%` | float | % of batters out in under 3 pitches |
| `<13` | int | (unclear pitch count grouping) |
| `<13%` | float | |
| `6+` | int (implied) | -- not seen in defense |
| `DP` | int | Double plays (as pitcher) |
| `DP:P` | int | Double plays turned as pitcher |
| `TB` | int | Total bases allowed |
| `R` | int | Runs allowed |
| `AB` | int | At bats against |
| `2B` | int | Doubles allowed |
| `3B` | int | Triples allowed |
| `1B` | int | Singles allowed |
| `FC` | int | Fielder's choices against |
| `ROE` | int (implied) | -- not seen in this response defense |
| `SHB` | int | Sac hits/bunts against |
| `SHF` | int | Sac flies against |

### Fielding fields

| Field | Type | Description |
|-------|------|-------------|
| `PO` | int | Putouts |
| `A` | int | Assists |
| `E` | int | Errors |
| `TC` | int | Total chances |
| `FPCT` | float | Fielding percentage |
| `DP` | int | Double plays |
| `IF` | int | (unclear -- infield fly?) |
| `GP:P` | int | Games played as pitcher |
| `GP:F` | int | Games played in field |
| `GP:C` | int | Games played as catcher |
| `outs` | int | Total outs recorded |
| `outs:F` | int | Outs recorded in field |
| `outs:C` | int | Outs recorded as catcher |
| `outs-P` | int | Outs while playing pitcher |
| `outs-1B` | int | Outs while playing 1B |
| `outs-2B` | int | Outs while playing 2B |
| `outs-3B` | int | Outs while playing 3B |
| `outs-SS` | int | Outs while playing SS |
| `outs-LF` | int | Outs while playing LF |
| `outs-CF` | int | Outs while playing CF |
| `outs-RF` | int | Outs while playing RF |
| `outs-C` | int | Outs while playing catcher |
| `IP:P` | float (implied) | Innings played as pitcher |
| `IP:1B` | float | Innings played at 1B |
| `IP:2B` | float | Innings played at 2B |
| `IP:3B` | float | Innings played at 3B |
| `IP:SS` | float | Innings played at SS |
| `IP:LF` | float | Innings played at LF |
| `IP:CF` | float | Innings played at CF |
| `IP:RF` | float | Innings played at RF |
| `IP:SF` | float | Innings played at ? (always 0) |
| `IP:F` | float | Total innings played in field |
| `IC:C` | float | Innings caught as catcher |
| `CI` | int | Catcher's interference |
| `CI:C` | int | Catcher's interference (as catcher) |
| `PB:C` | int | Passed balls (catcher) |
| `SB:C` | int | Stolen bases allowed (catcher) |
| `CS:C` | int | Caught stealing (catcher) |
| `SB:C%` | float | Stolen base allowed % (catcher) |
| `CS:C%` | float | Caught stealing % (catcher) |
| `PIK:C` | int | Pickoffs (catcher) |
| `SBATT:C` | int | Stolen base attempts against catcher |
| `OSMPH` | int | (always 0) |
| `OS#MPH` | int | (always 0) |

---

## Streaks Section

`stats_data.streaks` is keyed by player UUID and contains hot/cold streak data. In this capture only one player had a streak entry:

```json
{
  "<player_uuid>": {
    "streak_H": {              // "H" = hot streak
      "offense": { ... },      // same offense field set as player stats
      "defense": { ... },      // same defense field set
      "general": { "GP": 2 }   // games in the streak
    }
  }
}
```

The streak stats appear to contain the same fields as the regular player stats but reflect only the games within the streak period. The streak key `streak_H` uses "H" to denote a hot streak. Cold streaks would presumably use `streak_C` (not confirmed in this capture).

---

## Team Aggregate Stats

`stats_data.stats` contains team-wide totals with the same offense/defense/general structure:

```json
{
  "offense": { ... },   // team batting aggregates
  "defense": { ... },   // team pitching/fielding aggregates
  "general": {
    "GP": 92            // team games played (max across players)
  }
}
```

Key team aggregate values from this capture:

| Stat | Value | Notes |
|------|-------|-------|
| GP | 92 | Team games played |
| AVG | .326 | Team batting average |
| OBP | .471 | Team on-base % |
| SLG | .453 | Team slugging |
| OPS | .924 | Team OPS |
| R | 645 | Runs scored |
| H | 670 | Hits |
| 2B | 162 | Doubles |
| 3B | 30 | Triples |
| HR | 13 | Home runs |
| SB | 255 | Stolen bases |
| SB% | .917 | Stolen base success rate |
| BB | 445 | Walks |
| SO | 469 | Strikeouts |
| RBI | 535 | RBI |
| ERA | 4.57 | Team ERA |
| WHIP | 1.81 | Team WHIP |
| FIP | 3.90 | Team FIP |
| K/G | 6.50 | Strikeouts per 9 |
| E | 161 | Errors |
| FPCT | .927 | Team fielding % |

---

## Notable Observations

1. **No player names in response** -- players are keyed by UUID only. Names must be cross-referenced from `/teams/{team_id}/players`.

2. **Defense section combines pitching and fielding** -- a player who both pitches and plays the field will have pitcher stats (ERA, IP, K, BB) and fielder stats (PO, A, E, IP:POS) in the same `defense` object. The presence of `GP:P` and `GP:F` fields tracks how many games in each role.

3. **`IP:POS` fields use fractional innings** -- values like `218.67` represent innings played at a position in thirds (3 outs = 1 inning). `218.67` = 218 full innings + 2 outs.

4. **Many fields consistently 0** -- `CH%`, `OS%`, `FB%`, `SL%`, `KC%`, `KB%`, `CB%`, `DC%`, `DB%`, `RB%`, `SC%`, `CT%`, `GITP`, `OSSM`, `OSSW`, `OSS`, `OS`, `TP:P` were all 0 for every player. These may be for future use, sport-specific (football?), or require a different data configuration.

5. **`AB/HR` only present when HR > 0** -- confirmed by comparing players with HR=0 (field absent) vs. HR>0 (field present).

6. **Season scope is unclear** -- no date range or season year is included in the response. It is unknown whether this represents the current season only or all-time. Given GP values of 84-92, this appears to be a full season (or possibly multi-season aggregate).

7. **`gc-user-action` value for this endpoint:** `data_loading:team_stats` -- new value not previously seen.

---

## Open Questions

- What season/date range does this cover? Is there a query parameter to scope by season?
- How does this endpoint behave for opponent teams (does it return their stats)?
- What does `GP` in the `general` sub-object mean vs. `GP` in `offense`? (offense GP seems to match general GP in all cases here)
- What are the fields consistently returning 0 (`CH%`, `OS%`, etc.) actually designed for?
- Is `streak_C` (cold streak) confirmed to exist?
- Does this endpoint paginate? No pagination headers were observed in the request or response.
