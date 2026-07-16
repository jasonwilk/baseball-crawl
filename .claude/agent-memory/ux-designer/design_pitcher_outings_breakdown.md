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

## v2 reconciliation (E-265-03, implementable spec)

The v1 discovery above was superseded on three points by the resolved TN-2/TN-3
stat set and the operator's GREEN-only decision (epic TN-4), and extended with
five internal-review refinements (F11, F13-F17). The implementable spec lives
at `.project/research/E-265-outings-layout-spec.md` (the E-265-02 consumer
artifact) — this memory file is working notes only, not the pinned spec.

Reconciliations vs. v1:
1. **GREEN-only** — the `.outing-exploit` red accent above is OUT; only
   `.outing-strong` ships.
2. **No Result form-chip** — the Date-cell `.form-chip-w/l/t` idea above is
   OUT (coach dropped the Result column from TN-2).
3. **No combined-XBH** — HR is its own column per TN-2; the XBH-combining idea
   above is deferred (IDEA-143), not v1.

New in v2 (not covered by v1, which only addressed the per-outing table): the
per-pitcher season summary line as inline middot-separated prose (reusing
`.exec-summary`/`.key-player-stats`, NOT a table row), a `.depth-badge`/
`.depth-badge-strong` badge matrix for small-sample/BB-count/zero-BB display
(zero-BB reads as a command-*strength* signal via the win-green token, distinct
from a neutral count badge or a genuine no-data dash), a green summary-line
indicator on the collapsed `<details>` (reusing the `.spray-indicator` glyph
idiom, green instead of blue), a section-level plays-derived note (reusing
`.sort-annotation`, not per-column badges), and a scoped print-pagination
override (`page-break-inside:auto` on the outings table only) so a long log
doesn't blow a blank gap under the sitewide `table{page-break-inside:avoid}`
rule.
