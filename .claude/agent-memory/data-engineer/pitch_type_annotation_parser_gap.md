---
name: pitch-type-annotation-parser-gap
description: GameChanger pitch-type charting mode strands pitch events in play_events as event_type='other'; plays.pitch_count/is_first_pitch_strike collapse to 0
metadata:
  type: project
---

# Pitch-type-annotated play_events strand as event_type='other'

When a GameChanger game is charted with **pitch-type tracking** on, each pitch's
`play_events.raw_template` carries a trailing pitch-type suffix, e.g.
`"Strike 1 looking (Curveball)"`, `"Ball 1 (Fastball)"`, `"In play (Fastball)"`.
The parser's pitch classifier only matches the **un-suffixed** form
(`"Strike 1 looking"`, `"Ball 1"`, `"In play"`, `"Foul"`), so annotated pitch
events fall through to `event_type='other'` with `pitch_result=NULL`. Downstream
aggregation then leaves `plays.pitch_count` and `plays.is_first_pitch_strike` at
their `NOT NULL DEFAULT 0` — so FPS% and P/PA collapse toward 0 on a report.

**Why:** Discovered 2026-06-28 diagnosing physically-impossible stats (3.4% FPS,
0.2 P/PA) on team "Empire Netting & Fence Sr. Legion" (teams.id=133,
public_id `4RVrRCAcWc0a`, season 2026). Of 23 games with `plays`, only 1
(`4181aca7-...`) parsed cleanly; **22 had recoverable pitch text stranded in
`event_type='other'`** (e.g. zero-pitch game `c116d009-...`: 218 play_events, 0
classified as pitch, all pitch text in raw_template). The data is NOT absent —
it is in `play_events.raw_template`, recoverable by a parser fix + re-parse, no
API re-fetch needed.

**How to apply:**
- play_events join: `play_events.play_id` → `plays.id` (plays PK is `id`, NOT `play_id`).
- Triangulation rule: pitch text in `raw_template` of an `event_type='other'`
  row ⇒ parser bug, not source absence. Compare a suspect game against a
  cleanly-parsed control before blaming the API.
- **Default-0 masking** is structural: `pitch_count`/`is_first_pitch_strike`/
  `is_qab` are all `INTEGER NOT NULL DEFAULT 0` — query time cannot distinguish
  "first pitch was a ball" (legit 0) from "no pitch data charted" (default 0).
  Pitch-derived denominators (FPS%, P/PA) must be data-bearing (`pitch_count>0`)
  per [[etl-patterns]] and `.claude/rules/data-model.md` Data-Bearing Coverage,
  plus a coverage badge ("over N of M games charted").
- **QAB is exempt**: `is_qab` is OUTCOME-derived, populated across all games
  regardless of pitch charting (game `1ad9fe47`: sum_pitch_count=1, sum_qab=31).
  Keep QAB%'s all-PA denominator; only the "6+ pitch AB" sub-criterion is
  marginally undercounted in mis-parsed games.
- Diluted queries live in `src/reports/generator.py`: `_query_plays_team_stats`
  (team FPS / P-PA), `_query_plays_pitching_stats`, `_query_plays_batting_stats`
  — all unfiltered `SUM/COUNT` over every plays row.
