---
name: design-pitcher-outings-breakdown
description: Design pattern for per-pitcher game-log sections in the scouting report -- column curation via existing mob-hide classes, native <details> progressive disclosure, and binary outlier highlighting distinct from the percentile heat ramp
metadata:
  type: project
---

Consulted 2026-07-15 on a new "Outings Breakdown" section (per-pitcher game-by-game
log) for the scouting report, gated behind `FEATURE_PITCHER_OUTINGS` (mirrors
`FEATURE_PREDICTED_STARTER`). Full recommendation delivered to PM; not yet built.
Recorded here because it establishes three reusable patterns.

**Why:** `pitcher-outings.md` prototype had 18 columns per outing -- too wide for
375px. The design had to curate columns, add progressive disclosure without JS,
and invent a highlight treatment for "notable outings" that doesn't collide with
the existing 5-tier heat-map ramp (`.heat-0`..`.heat-4`, percentile-across-players).

**How to apply** (reusable beyond this one section):

1. **Column curation reuses `mob-hide` / `mob-hide-extra`, no new breakpoint.**
   Both classes collapse at the same `max-width:640px` query in
   `scouting_report.html` today (functionally identical, just two labels for
   future-proofing) -- any new dense table should tier its columns into
   always-visible / `mob-hide-extra` / `mob-hide` rather than inventing a new
   responsive mechanism.
2. **Native `<details>`/`<summary>` is the progressive-disclosure primitive for
   this stack** (server-rendered HTML, no JS frameworks). Default collapsed on
   screen; force-open for print with a pure-CSS override:
   `@media print { details.X{display:block} details.X>summary{display:none}
   details.X>*:not(summary){display:block!important} }`. This lets print/PDF
   show full detail (room in landscape) while phone defaults to curated. Give
   the `<summary>` a 44px min-height touch target.
3. **A per-row/per-outing "notable" flag is NOT the heat ramp.** The heat-0..4
   green gradient ranks a player against teammates (season aggregate,
   `_compute_batting_heat`/`_compute_pitching_heat` in `renderer.py`). A
   single-outing outlier flag is a different grain (this game vs. this
   pitcher's OWN baseline) and needs a binary accent pair instead, built from
   tokens already meaningful in the template rather than new hues:
   `.outing-strong {border-left:3px solid #16a34a; background:#f0fdf4}` (reuses
   heat-4 green / heat-1 tint) and `.outing-exploit {border-left:3px solid
   #991b1b; background:#fef2f2}` (reuses `.trust-loud`/`.form-chip-l` red).
   Row-level, not cell-level (it's one boolean per row, not a gradient per
   stat). Gate computation on a minimum outing count (3+) per pitcher so it
   isn't computed against an N=1 baseline -- but the row itself always renders
   at full weight regardless (never-suppress still governs the data, only the
   annotation is withheld).
4. **Result (W/L/T) as a reused `.form-chip-w/l/t` pill inside the Date cell**,
   not a separate table column -- same component as the existing Recent Form
   strip, avoids a 19th column.
5. **Combined XBH column** (2B+3B+HR summed) mirrors the existing
   `player._xbh` convention already used in the Batting table -- reuse that
   precedent for any future pitching-allowed extra-base display instead of
   three separate narrow columns.

See [[MEMORY]] Established UI Patterns for the base heat-tier / table
conventions this extends.
