---
name: boxscore-stats-and-outcome-vocab
description: Boxscore extra-array holds BF/#P/TS/WP (opponents too); full plays name_template outcome vocab; boxscore BF == completed-PA count
metadata:
  type: reference
---

Confirmed 2026-06-29 against 24 real team-133 (`4RVrRCAcWc0a`) games + the managed test team, for the E-245 reconciliation-gap sizing.

**Boxscore stat structure (`GET /game-stream-processing/{event_id}/boxscore`, accept `application/vnd.gc.com.event_box_score+json; version=0.0.0`):**
- Top-level keys = team identifiers → `{players, groups}`. Each group has `category` (`"lineup"` for batting, `"pitching"`), `team_stats`, `stats` (per-player rows: `player_id`/`player_text`/`stats`), and `extra`.
- **Primary block (`team_stats` + `stats[].stats`) is REDUCED:** pitching = IP/H/R/ER/BB/SO; batting(`lineup`) = AB/R/H/RBI/BB/SO. NO BF/pitches/PA here.
- **The sparse extras live in `group.extra[]`:** each entry is `{stat_name, stats:[{player_id, value}]}`. Pitching extras observed: `WP`, `#P` (pitches), `TS` (total strikes), `BF` (batters faced). These ARE present for scouted OPPONENTS (not member-only) — earlier I wrongly concluded opponent boxscores lacked BF because I looked in `stats[].stats` instead of `extra[]`. (The game-loader's `BF`→`bf` mapping is fed from these extras — the engine comment "sparse extras already loaded".)

**Plays `name_template.template` outcome vocabulary (21 distinct, full season):** Strikeout, Single, Ground Out, Walk, Fly Out, Pop Out, Double, Line Out, Hit By Pitch, Error, Sacrifice Bunt, Fielder's Choice, Double Play, Triple, Home Run, Sacrifice Fly, Dropped 3rd Strike, Intentional Walk, FC Double Play, Batter Out, Infield Fly. No "Strikeout looking/swinging" split at name_template level (that's in `final_details`). The reconcile engine's hardcoded sets (`src/reconciliation/engine.py`) correctly classify all 21: the 10 generic-out/error/FC strings not in any set fall through the catch-all `AB = outcome not in _AB_EXCLUSIONS` and correctly count as AB. No SO/AB/H drift. Re-audit if GC adds outcome strings (a new HIT or PA-not-AB string would need adding).

**BF == completed-PA equality:** total boxscore BF (both teams' pitchers, summed from `extra`) equals the count of plays with non-empty `final_details` EXACTLY, every game (9/9 checked). Incomplete PAs (non-empty `at_plate_details` + empty `final_details`) occur ZERO times in completed games — that case is a live/in-progress-edit artifact only (seen on the test team mid-edit). So the parser's skip-on-empty-`final_details` rule causes no BF undercount. See [[plays-pitch-type-templates]].
