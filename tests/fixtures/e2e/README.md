# E2E Report-Generation Fixture (E-234-05)

**Purpose.** Drive `src/reports/generator.py::generate_report()` end-to-end against a
transport-only (respx-style) mock. Every HTTP call the report pipeline makes is keyed
to a recorded-payload file here. See `manifest.json` for the exact URL -> file map.

**Provenance.** Real GameChanger payload **shapes**, captured from the cached scouting
crawl of a real HS varsity team (2026 spring season). **Fully anonymized** —
this is committed test data. Used **cache** (`data/raw/2026-spring-hs/scouting/`), except
the public team profile which was re-pulled live (no-auth) for shape fidelity, and the
`POST /search` response which was built from the confirmed endpoint schema
(`docs/api/endpoints/post-search.md`) since per-team search responses are not cached.

## Team / game-set identifiers (use these in the mock)

| Field | Value |
|-------|-------|
| public_id | `ExampleTm001` |
| gc_uuid (from search, used in spray URL) | `00000000-0000-4000-8000-00000000003b` |
| team name (search/profile) | `Example Team Varsity` |
| season | spring 2026 |
| Game 1 id | `00000000-0000-4000-8000-000000000002` — 2026-03-19, **home**, 11-1 **W** |
| Game 2 id | `00000000-0000-4000-8000-000000000004` — 2026-03-27, **away**, 4-14 **L** |

## Call sequence (see manifest.json for URLs + payload files)

1. `GET /public/teams/{public_id}` -> `public_team_profile.json`
2. `GET /public/teams/{public_id}/games` -> `public_team_games.json`
3. `GET /teams/public/{public_id}/players` -> `roster_players.json`  *(inverted path)*
4. `POST /search` -> `search_response.json`  *(gc_uuid resolution; body `{"name": "Example Team Varsity"}`)*
5. `GET /game-stream-processing/{game_id}/boxscore` -> `boxscore_{game_id}.json`  *(x2)*
6. `GET /game-stream-processing/{game_id}/plays` -> `plays_{game_id}.json`  *(x2)*
7. `GET /teams/{gc_uuid}/schedule/events/{game_id}/player-stats` -> `spray_{game_id}.json`  *(x2)*

## ORACLE — hand-computed from the RAW payloads (NOT from generator output)

These were tallied directly from the recorded payloads with a standalone script
(documented formulas below), independent of `generate_report()`. Anonymization preserves
all stat numbers, so they hold against the fixtures verbatim.

### Team W-L (from `public_team_games.json` `score.team` vs `score.opponent_team`)
- Game 1 (home): 11 - 1 -> **W**
- Game 2 (away): 4 - 14 -> **L**
- **Season W-L = 1 - 1**

### Batting season line — player jersey **#7** (`fake_uuid 00000000-0000-4000-8000-00000000000f`)
Per-game (from each boxscore's `lineup` group `stats` + `extra`):
- Game 1: AB 2, R 2, H 1, RBI 1, BB 2, SO 0, 2B 1, TB 2
- Game 2: AB 2, R 0, H 1, RBI 0, BB 0, SO 0, TB 1, HBP 1, SB 1
- **Season total: AB 4, R 2, H 2, RBI 1, BB 2, SO 0, 2B 1, HBP 1, SB 1**
- AVG = H/AB = 2/4 = **.500**; OBP = (H+BB+HBP)/(AB+BB+HBP+SF) = 5/7 = **.714**

Alt clean position player — jersey **#5** (`...00000000000c`): season AB 4, R 1, H 2, RBI 1,
BB 1, SO 2, SB 1 -> AVG **.500**, OBP 3/5 **.600**.

### Pitching season line — pitcher jersey **#4** (`fake_uuid 00000000-0000-4000-8000-000000000011`), the workhorse/starter (G1 "(W)")
Per-game (from each boxscore's `pitching` group `stats` + `extra`):
- Game 1: IP 4.667 (14 outs), H 2, R 1, ER 0, BB 1, SO 7, #P 65, BF 18
- Game 2: IP 1.333 (4 outs), H 6, R 5, ER 5, BB 2, SO 0, #P 41, BF 12
- **Season total: IP 6.0 (18 outs), H 8, R 6, ER 5, BB 3, SO 7, #P 106, BF 30**
- ERA = ER*27/outs = 5*27/18 = **7.50**; WHIP = (BB+H)*3/outs = 11*3/18 = **1.83**;
  K/9 = SO*27/outs = 7*27/18 = **10.50**

### FPS% (plays-derived) — pitcher jersey **#4** (`...000000000011`)
Definition (matches `plays_parser._FPS_STRIKE_RESULTS`): first pitch of each PA is a strike
if its `at_plate_details` template is one of Strike looking/swinging, Foul, Foul tip, In play,
Foul bunt; `Ball N` is not. FPS% = first-pitch-strikes / BF. Pitchers attributed to PAs by
boxscore appearance order + BF budget (the reconciliation engine's method); PA counts match
boxscore BF totals exactly (G1 19=19, G2 33=33).
- Game 1 (#4): 8 first-pitch strikes / 18 BF = 44.4%
- Game 2 (#4): 6 first-pitch strikes / 12 BF = 50.0%
- **Season #4 FPS% = 14 / 30 = 46.7%**

Alternatives:
- Pitcher **#16** (`...00000000000d`, pitched G2 only): 10/18 = **55.6%** (single-game; simplest season value).
- **Team-level** (all scouted pitchers, attribution-independent — just first-pitch strikes
  over all defensive-half PAs): G1 8/19 + G2 17/33 = **25/52 = 48.1%**. Most robust if the
  per-pitcher attribution proves brittle in the assertion.

> Recommendation: assert the **team W-L**, the **#4 pitching counting line** (exact), at least
> one **batting counting line** (exact), and an FPS% (prefer #16's 55.6% single-game or the
> team-level 48.1% for least sensitivity to pitcher attribution; use #4's 46.7% to exercise
> multi-game season aggregation). Counting stats are exact; rate stats depend on the formulas above.

## Sanitization (what was removed — committed test data)

- **Auth/credentials:** none present in response bodies; no `gc-token`/`gc-device-id`/cookies were
  ever in payloads. Confirmed no tokens leaked.
- **Signed media URLs:** every `avatar_url` (CloudFront `Policy`/`Signature`/`Key-Pair-Id` signed
  URL — credential-like) stripped to `""`.
- **UUIDs:** all real UUIDs (players, teams, games, streams, gc_uuid) -> fake
  `00000000-0000-4000-8000-NNNNNNNNNNNN`, consistent across every file (joins preserved).
- **public_id slug:** real slug -> `ExampleTm001` (global).
- **Player names:** all `first_name`/`last_name` -> `Player <Ordinal>` (keyed by player UUID; jersey
  numbers kept — visible on any broadcast, not PII).
- **Team / org / people:** team name, opponent names, staff, city/state genericized
  (`Example Team Varsity`, `Example Opponent One/Two`, `Coach One..`, `Anytown`/`XX`); season record
  genericized to a non-identifying value.
- **Kept as-is (not PII):** all stat numbers, scores, dates, jersey numbers, enums
  (`high_varsity`, `completed`, half/inning, pitch templates), coordinates.
