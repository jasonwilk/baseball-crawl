---
name: boxscore-empty-shape
description: Shape of GET /game-stream-processing/{event_id}/boxscore when a game has a final score but no/partial GC scorebook (scored-but-empty modal scouting case)
metadata:
  type: project
---

# Boxscore "scored-but-empty" shape (sub-case A)

When a game has a public FINAL SCORE but no per-player scorebook charted in
GameChanger (the modal scouting case — opponent's public schedule shows a result
but no one scored the book), `GET /game-stream-processing/{event_id}/boxscore`
returns **sub-case A**: the two **team-key envelope is PRESENT** (own = public_id
slug, opp = UUID), each team has its `players` roster + `groups`
(lineup/pitching categories), but the per-player **`stats` arrays are empty**.

**Why:** the team-key envelope encodes *which two teams played* (scheduling/roster
metadata) and exists regardless of scorekeeping. The `stats` arrays are exactly
what scorekeeping populates. No scorekeeping → empty `stats`, envelope intact.

**Direct partial evidence (2026-06-14):**
`data/raw/2026-spring-hs/scouting/LHIYRnPoo8DC/boxscores/03c21843-1499-4698-895e-214d3b5f1598.json`,
opponent key `e822d38d-...`, pitching group:
`{"category":"pitching","team_stats":{"IP":4,"H":3,...},"extra":[],"stats":[]}`
— category + envelope intact, `stats:[]` and `extra:[]` empty. Note `team_stats`
aggregate can stay POPULATED even when per-player `stats` is empty (team tally
recorded, no per-player breakdown).

**Loader consequence (GameLoader):** team keys detected → NOT the keyless
early-return → writes games row + score, loads zero stat rows,
`LoadResult.errors=0`. Both `groups: []` (categories absent) and
categories-present-with-empty-`stats` are loader-equivalent (errors=0). This is
the basis for E-236 story 09 `load_status="completed"`.

**Contrast — sub-case B is a DIFFERENT event, not a flavor of scored-but-empty:**
`{}` / error body / UUID-only-unmatched keys = genuine processing failure or
nonexistent stream. Crawler usually sees 403/404/500 (raises GameChangerAPIError,
game skipped, NO games row); if it reaches the loader, keyless early-return →
`errors=1`. Carries no final-score games row → NOT scored-but-empty.

**LIVE CONFIRMED 2026-06-14** (two real captures, LSB Varsity `tIPqaBAqhp3y`,
games `08e8658e` vs Elkhorn North, `ab05fce5` vs Omaha Westside). A 200 boxscore
for an un-scorekept game is sub-case A: 2 asymmetric envelope keys (slug + UUID);
EACH team has `groups` = list of length 2 with BOTH `lineup` and `pitching`
categories present, each `{category, team_stats:{zeroed}, extra:[], stats:[]}`.
**`groups` is NEVER `[]`** — categories are always present with empty `stats`/`extra`.
`players` is variable: own team (slug) had `players:[]`; opponent (uuid) had a
FULL roster (21/20 players) even with empty stats. The un-pinned detail is now
pinned: **categories-present-with-empty-`stats`, not `groups:[]`.**

**Secondary critical finding — the "no scorebook" case has TWO API behaviors:**
- **game-stream created but unscored** (`game_status:"new"`, details `score:{team:0,opponent_team:0}`)
  → boxscore returns **200 + sub-case A empty envelope** → loads as scored-but-empty
  games row (errors=0 → completed).
- **no game-stream record at all** → boxscore returns **404** (NOT `{}`, NOT empty
  200). In the scouting crawler a 404 raises GameChangerAPIError → game skipped →
  NO games row. The hypothesized "sub-case B = `{}`/keyless 200 body" does NOT occur
  in the wild; the real failure mode is a 404 status. (Most LSB games on these
  schedules 404'd — public `/games` exposes no scores either; scores come from
  `/public/game-stream-processing/{id}/details?include=line_scores` with
  `Accept: application/json`.)

**Honesty caveat (score pairing):** both empty 200 captures are 0-0 `"new"`-status
games — a game-stream stub, not a game with a real NON-ZERO final score. I did NOT
find on LSB's own schedules a game with a real final score AND an empty boxscore;
that exact combo is the opponent-scouting modal case. But the boxscore SHAPE is
identical regardless of score (score comes from schedule/summary, not the boxscore),
so pairing this real empty-envelope shape with a non-zero score in a fixture is
faithful. Does NOT change sub-case-A → load_status="completed".

## Frequency / `game_status` gating (LIVE 2026-06-14)

**`game_status == "completed"` is GC's "a GC scorebook exists" marker.** Both the
scouting crawler (`scouting.py:173`) and the report generator's M denominator
(`generator.py::_count_completed_games:145`) filter on exactly this. Live sample
across 6 real opponents (dmPyrVfovgt0, LHIYRnPoo8DC, KCRUFIkaHGXI, Zh0aiPCxWIDh,
a30ozUdZAP44, Y4RbMLhdKECw), 72 completed games sampled: **72/72 returned
200-with-data. ZERO 200-empty, ZERO 404, ZERO 403.**

Implication: within the set the pipeline actually fetches, neither 200-empty nor
404 occurs. The 200-empty (game_status "new") and 404 (no game-stream) shapes are
games that are NOT `game_status=="completed"`, excluded BEFORE the boxscore loop.
So an "all-404 completed-games opponent (M>0)" is structurally not the field
reality — a team that never keeps scorebooks surfaces as **M=0** (zero completed
games → no_games path), not all-404-blocked. (LSB Freshman `l3u29sLwAEf7`: 23
games, all boxscores 404, public list has NO `game_status`/`score` fields at all →
filters to M=0.) The realistic "all boxscores blocked, M>0" cause is **401 auth
expiry / transient failure mid-run** (games_crawled==0), NOT structural no-scorebook.

**403 is NOT a boxscore-read outcome.** The boxscore endpoint is authenticated but
NOT ownership-gated (works for opponent games). ~130 live boxscore calls across 8
teams: zero 403s. 403 is an owned-SCOPE thing (e.g., season-stats Forbidden for
non-owned teams), not a per-game public-scouting read outcome. Dominant "can't
read" for the reports-first public-id flow = 404 (no stream) or 401 (auth expiry).

**Public `/games` shape varies:** opponent schedules carry `score` + `game_status`;
LSB's own teams' lists (when none scored) omit both. Real per-game score comes from
`/public/game-stream-processing/{id}/details?include=line_scores` (Accept: application/json).

Related: [[exploration-findings]], data-model.md "scored-but-empty-game trap".
