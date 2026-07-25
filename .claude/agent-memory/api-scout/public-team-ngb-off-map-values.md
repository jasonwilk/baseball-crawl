---
name: public-team-ngb-off-map-values
description: /public/teams ngb carries governing bodies outside _NGB_MAP (babe_ruth_cal_ripken, pony); an unrecognized ngb SHORT-CIRCUITS detect_league_level to "unknown" and skips the age-bracket ladder entirely
metadata:
  type: project
---

`GET /public/teams/{public_id}` returns `ngb` values that are NOT in
`_NGB_MAP` (`src/reports/starter_prediction.py`). Observed live 2026-07-25 on a
185-team partition (E-274 probe partition 1, 163 resolved profiles):

- `["american_legion"]` ×65, `"[]"` ×49, `["usssa"]` ×38, `""` ×6,
  `["perfect_game"]` ×3, **`["babe_ruth_cal_ripken"]` ×1**, **`["pony"]` ×1**.

The two off-map values are the finding. `_NGB_MAP` knows only
`nsaa`/`nfhs`/`american_legion`/`usssa`/`perfect_game`, so the enum is
demonstrably NOT closed — Babe Ruth/Cal Ripken and PONY are both real national
governing bodies GC indexes.

**Why it matters:** the Priority-2 branch of `detect_league_level` returns
`"unknown"` the moment `ngb` is non-empty but contains no recognized value —
`# ngb has values but none recognized -> unknown`. That RETURN is a
short-circuit: it never reaches the age-bracket ladder below it. So a team
whose `age_group` is a perfectly usable structured bracket (both observed cases
were `"14U"`) is suppressed, while the SAME team with `ngb: "[]"` would have
resolved to `youth_travel` off the bracket. A *more* informative `ngb` produces
a *less* informative answer.

**How to apply:** when a report shows `unknown`/SUPPRESSED for a team that
plainly has an age bracket, check `ngb` for an off-map governing body before
suspecting the bracket ladder. Do not assume the `ngb` vocabulary is closed —
expect more values as the crawl reaches new regions. Related:
[[public-team-age-group-level-field]] (the `age_group` enum, whose vocabulary
DID hold at 185 teams — 163/163 populated, zero off-vocabulary).
