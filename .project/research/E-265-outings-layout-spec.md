# E-265 Outings Breakdown — Implementable Layout Spec

**Story**: E-265-03 (ux-designer layout spec) | **Consumer**: E-265-02 (SE implementation)
**Grounded against**: `/tmp/.worktrees/baseball-crawl-E-265/src/api/templates/reports/scouting_report.html`, `/tmp/.worktrees/baseball-crawl-E-265/src/reports/pitcher_outings.py`, and `/tmp/.worktrees/baseball-crawl-E-265/src/reports/renderer.py` (line numbers and field names below are from a clean read of those files at spec-authoring time; re-verify if they have moved since). Updated after code-review round 1 (2 MUST FIX + 2 SHOULD FIX, all incorporated below).

This spec resolves AC-1 through AC-5 of E-265-03. It reuses existing classes and idioms only — no new responsive mechanism, no new disclosure primitive, no new heat ramp.

## 1. Section placement and flag gating (Resolved Decision #2: INLINE)

Insert a new `<div class="outings-section">` block **inside the first `.stats-content` wrapper**, directly after the existing Pitching table's `{% endif %}` (end of the `has_pitching` branch, immediately after the `era-basis-footnote` paragraph / `no-data-msg` fallback — the Pitching block currently closes around line 729) and **before** the `<h2 class="section-header batting-section">Batting</h2>` header (line 732). This keeps all pitcher-related content contiguous and rides the existing landscape `stats-page` print context (no new named `@page`).

**The entire section — `<h2>`, the plays-derived note, and every per-pitcher block — is wrapped in one `{% if show_pitcher_outings %}` … `{% endif %}` gate**, mirroring `show_predicted_starter` exactly (`scouting_report.html:534`/`:635`; `show_pitcher_outings = is_pitcher_outings_enabled()`, epic TN-1/TN-7). This is load-bearing, not cosmetic: the epic's Success Criterion requires the flag-unset report to be **byte-identical** to the post-E-264 baseline golden — zero diff, nothing added or removed. **With the flag unset, this section renders NOTHING: no `<h2>`, no annotation, no empty-state markup, no CSS-visible trace.** (The scoped CSS in §10 is inert either way since no matching class appears in the DOM when the flag is off, exactly like the Most Likely Arms section's CSS today.)

```html
{% if show_pitcher_outings %}
<div class="outings-section">
  ...
</div>
{% endif %}
```

Give the wrapper its own forced page break for print, mirroring the existing `.batting-section` rule (line 415):

```css
.outings-section { page-break-before: always; }
```

Sequence on print: Pitching page(s) → Outings Breakdown (own page, may span several via §6 below) → Batting (own page, unchanged).

**Empty state applies ONLY when the flag is ON and no pitcher has outings data** — the non-fatal empty-data path required by epic AC-6 ("the builder produces a suppressed/empty state, not a crash"), distinct from the flag-OFF case above. When `show_pitcher_outings` is `True` but the pitcher-outings list is empty, still render the `<h2>` + plays-derived note (the section is genuinely "on," just data-empty) and drop in the standard empty-state paragraph, matching the idiom already used by both Pitching (line 728) and Batting (line 790):

```html
{% if show_pitcher_outings %}
<div class="outings-section">
<h2 class="section-header">Outings Breakdown</h2>
<div class="sort-annotation">FPS% and HR-allowed below are computed from charted pitch-by-pitch play data, not GameChanger's boxscore totals — see pitch-charting coverage above.</div>
{% if pitcher_outings %}
  {# ... per-pitcher <details> blocks (§4) ... #}
{% else %}
<p class="no-data-msg">No data available</p>
{% endif %}
</div>
{% endif %}
```

Two independent conditions, two different meanings: `show_pitcher_outings` (outer) is the byte-identical feature flag; `pitcher_outings` (inner, truthy/empty list check) is the honest-empty-state data check. Do not collapse them into one condition — collapsing would either reintroduce the golden-diff risk (rendering the h2 when the flag is off) or hide the flag-on-empty-data state behind the wrong branch.

## 2. Section header + plays-derived note (AC-4)

Shown fully assembled in §1 above. `.sort-annotation` (defined line 133-138: 8pt italic `#6b7280`) is the existing section-level caveat idiom, already used for "Sorted by innings pitched" (line 671) and the suppressed-starter copy (line 542). One note, once, for the whole section — **not** a per-column badge on FPS%/HR-allowed, since (a) no per-column-badge precedent exists anywhere in this template, and (b) the plays-derived columns interleave with boxscore columns in the fixed TN-2 order, so a per-column marker would fragment the row visually for no added clarity over one section-level line. This directly satisfies AC-4.

## 3. Per-outing table: columns, order, tiers, truncation, field names (AC-1)

Column set and order are fixed by TN-2 and MUST NOT be reordered by tiering — hiding a column via CSS `display:none` does not reorder the remaining visible ones, so the left-to-right reading order at 375px is a subsequence of the full order below.

**Field-name reconciliation against E-265-01's shipped `Outing` dataclass** (`src/reports/pitcher_outings.py:81-103` — the report's Jinja environment uses the default `Undefined`, not `StrictUndefined`, so a wrong attribute name renders a SILENT BLANK rather than an error; every attribute below has been checked against the actual dataclass, not inferred from the display label):

| # | Column | Header text | `Outing` attribute | Tier | Class |
|---|--------|-------------|---------------------|------|-------|
| 1 | Date | `Date` | `game_date` | always-visible | — |
| 2 | Opp | `Opp` | `opponent` **(not `opponent_name`)** | always-visible (truncated, see below) | `outing-opp` |
| 3 | IP | `IP` | `ip_outs` (via `\| ip_display`) | always-visible | — |
| 4 | BF | `BF` | `bf` | secondary detail | `mob-hide-extra` |
| 5 | H | `H` | `h` | supporting count | `mob-hide` |
| 6 | HR | `HR` | `hr_allowed` **(not `hr`)** | secondary detail | `mob-hide-extra` |
| 7 | BB | `BB` | `bb` | supporting count | `mob-hide` |
| 8 | K | `K` | `so` **(not `k`)** | always-visible | — |
| 9 | R | `R` | `r` | always-visible | — |
| 10 | FPS% | `FPS%` | `fps_pct` (via `\| pct`, §9) | supporting/plays-derived detail | `mob-hide` |
| 11 | ERA(game) | `ERA ({{ era_basis.basis }}-inn){% if era_basis.assumed %}*{% endif %}` | `era` (via `\| rate2`, §9) | always-visible | — |

The two silent-blank traps to watch: the display label "HR" maps to the attribute `hr_allowed`, and the display label "K" maps to the attribute `so` — both are boxscore-column-name holdovers (GameChanger's own boxscore calls strikeouts `so`), not typos to "fix" to `hr`/`k`.

**Rationale for the tier split** (mirrors the existing Pitching table's own ratio of ~6 always-visible out of 19 total, lines 676-697): Date + Opp are row identity (same role as `#` + `Player` in the main table); IP/K/R/ERA(game) are the headline "how'd it go" read (workload, dominance, damage, rate) — the same four-metric always-visible pattern the Pitching table already uses for ERA/K9/GP/IP. BF, H, HR, BB, FPS% are supporting detail, tiered `mob-hide-extra` (HR, BF — game context) vs `mob-hide` (H, BB, FPS% — counting/plays detail), reusing the identical 640px breakpoint (lines 459, 468-470) — both classes currently collapse together; the two labels exist only for future-proofing per the established convention, not a second breakpoint.

Both `.mob-hide` and `.mob-hide-extra` are pre-existing (lines 468, 470) — do not add a new query.

**ERA(game) header reuses the existing E-264 basis-disclosure idiom** verbatim (compare line 681): `ERA ({{ era_basis.basis }}-inn){% if era_basis.assumed %}*{% endif %}`. Do **not** add a second `.era-basis-footnote` paragraph for this table — the single sitewide footnote (line 726) already explains the `*`, and it explains the same basis used here.

**Opp-column truncation** (AC-1 / finding F16) — reuses the `.spray-card-identity` ellipsis pattern (lines 225-229) plus a bounded `max-width` and a `title` attribute for hover disclosure, since a table `<td>` (unlike the spray card's block-level div) needs an explicit width to make `text-overflow:ellipsis` engage:

```css
.outing-opp {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}
@media screen and (max-width: 640px) {
  .outing-opp { max-width: 60px; }
}
```

**Full `<tbody>` row, all 11 columns, correct attribute names, and None-handling.** Per the `Outing` dataclass docstring, every boxscore-direct field (`ip_outs`, `bf`, `h`, `hr_allowed`, `bb`, `so`, `r`) "may be `None` when the boxscore omitted them" — a real per-appearance possibility, not just a rate-stat edge case. `ip_outs` is covered by the existing `\| ip_display` filter (already returns `"-"` for `None`, line 158-159 in `helpers.py`); the six other raw counts and `opponent` have no such filter, so each needs an explicit inline None-guard rather than being left to print an empty cell:

```html
<tr class="{{ 'outing-strong' if o.is_strong else '' }}">
  <td>{{ o.game_date | format_date }}</td>
  <td class="outing-opp" title="{{ o.opponent | e if o.opponent else '' }}">{{ o.opponent | e if o.opponent else "&mdash;" }}</td>
  <td>{{ o.ip_outs | ip_display }}</td>
  <td class="mob-hide-extra">{{ o.bf if o.bf is not none else "&mdash;" }}</td>
  <td class="mob-hide">{{ o.h if o.h is not none else "&mdash;" }}</td>
  <td class="mob-hide-extra">{{ o.hr_allowed if o.hr_allowed is not none else "&mdash;" }}</td>
  <td class="mob-hide">{{ o.bb if o.bb is not none else "&mdash;" }}</td>
  <td>{{ o.so if o.so is not none else "&mdash;" }}</td>
  <td>{{ o.r if o.r is not none else "&mdash;" }}</td>
  <td class="mob-hide">{{ o.fps_pct | pct }}</td>
  <td>{{ o.era | rate2 }}</td>
</tr>
```

(`hr_allowed` is typed `int` non-`None` per the dataclass signature — the guard above is defensive/harmless if so; `so`/`bf`/`h`/`bb`/`r`/`ip_outs`/`opponent` are all typed `... | None` and need it.) `\| pct` and `\| rate2` already return `"—"` internally on `None` — see §9 for exact behavior, so no extra ternary is needed around those two cells.

This prevents both the field-name silent-blank trap (MUST FIX 2) and a silent-blank on a `None` boxscore field within an otherwise-populated row.

## 4. Per-pitcher grouping: `<details>` structure + green summary indicator (AC-3)

One `<details class="outing-log">` per pitcher with outings data (`PitcherOutings.outings`), in the same sort order as the Pitching table (by IP descending) for visual continuity between the two sections. Default-collapsed on screen; force-open for print via the pure-CSS override already established in prior ux discovery (`.claude/agent-memory/ux-designer/design_pitcher_outings_breakdown.md`), renamed to the concrete class used here:

```css
.outing-log { margin: 6px 0; }
.outing-log-summary {
  min-height: 44px;           /* touch target */
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  font-weight: bold;
  font-size: 9pt;
  padding: 4px 2px;
}
.outing-log-flag { color: #16a34a; margin-left: 2px; }

@media print {
  details.outing-log { display: block; }
  details.outing-log > summary { display: none; }
  details.outing-log > *:not(summary) { display: block !important; }
  .outing-season-line { page-break-after: avoid; }  /* keep header glued to its first row, mirrors .section-header line 414 */
}
```

```html
<details class="outing-log">
  <summary class="outing-log-summary">
    {{ pitcher.name | e }}
    {% if pitcher.outings | selectattr("is_strong") | list %}<span class="outing-log-flag" title="Includes a standout outing">&#9679;</span>{% endif %}
  </summary>
  {# ... season line (§7), table (§3/§6) ... #}
</details>
```

**`pitcher.throws` was in an earlier draft of this spec and has been removed** (SHOULD FIX 1): `PitcherOutings` (`player_id`, `name`, `jersey_number`, `season`, `outings`) carries no `throws` field — that attribute exists only on the main Pitching table's row structure, a different data path. Requiring E-265-02 to plumb a new field through the DONE E-265-01 derivation layer for a v1 spec would be a residual decision this spec exists to close out (AC-5), so the pitcher identity in the `<summary>` is name-only for v1. (`jersey_number` IS a real `PitcherOutings` field if a future pass wants to prefix it the way `.spray-card-jersey` does elsewhere — optional, not required by any AC here.)

**Green summary-line indicator** (finding F13): a single filled dot (`&#9679;`, green `#16a34a`) appended after the pitcher's name in the `<summary>`, rendered whenever at least one outing inside is flagged. This directly mirrors the existing `.spray-indicator` idiom (line 197, 765: a small colored glyph — blue diamond `&#9670;` — appended after a player name to signal "more data available below" without expanding). Same mechanism, green instead of blue, different meaning ("respect this arm" vs. "spray chart available"). The `any()` check is expressed inline in Jinja (`selectattr("is_strong")` above) against `Outing.is_strong` (confirmed field name, not `is_green`/`strong`) — no new backend aggregate field is required.

**Do not** add a custom disclosure-triangle marker or suppress the native `<summary>` marker — the native browser marker plus the 44px `min-height` flex row is sufficient and keeps the primitive truly native (no JS), consistent with prior ux discovery point 2.

## 5. GREEN outing-strong row treatment, no red/exploit accent (AC-3, TN-4)

```css
tr.outing-strong td { background: #f0fdf4; }
tr.outing-strong td:first-child { border-left: 3px solid #16a34a; }
```

Applied as `<tr class="{{ 'outing-strong' if o.is_strong else '' }}">` (shown fully in §3's row markup). Reuses heat-4 green / heat-1 tint tokens already in the stylesheet (`.heat-1` background `#f0fdf4` line 24, `.heat-4` fill `#16a34a` line 27) — no new hue introduced. Border-left is placed on `td:first-child` rather than the `<tr>` itself: `border` on `<tr>` is unreliable across browsers/print engines even under `border-collapse:collapse`, whereas `td:first-child` renders consistently (this is a spec-level implementation note for SE, not a new visual language). **No `.outing-exploit` / red accent class exists in this design** — v1 is GREEN-only per the operator's epic TN-4 decision; the row simply renders unflagged (full weight, no accent) when not green. This satisfies "never suppress" — an unflagged row is not dimmed or altered, it just lacks the extra accent.

## 6. Print-pagination override for the outings table (AC-3, finding F14)

The sitewide rule `table { page-break-inside: avoid; }` (line 412) plus `tr { page-break-inside: avoid; }` (line 413) forces a 15-20-row outing log to jump wholesale to the next page if it doesn't fit the remainder of the current one, leaving a large blank gap. Override scoped to this table only:

```css
@media print {
  table.outing-log-table { page-break-inside: auto; }
  table.outing-log-table tr { page-break-inside: avoid; }
}
```

`page-break-inside: auto` on the table permits the table to split across a page boundary; the `tr` rule (re-asserted, since it would otherwise be overridden by the more specific selector cascade only for the table itself) keeps individual rows intact — a single outing's row never splits mid-row, only the boundary between rows can fall on a page break.

Do **not** apply `page-break-inside`/`break-inside: avoid` to the outer `.outing-log` `<details>` wrapper or to `.outing-log-summary` as a whole-block avoid — that would re-force the entire per-pitcher block (summary + season line + full table) onto one page and reintroduce the exact blank-gap problem this override exists to fix. The narrower `page-break-after: avoid` on `.outing-season-line` (§4) is sufficient to keep the header glued to at least its first row.

Wrap the table in a horizontally-scrollable div for the (rare) case a wide desktop viewport still needs it, matching the mobile-first "tables scroll horizontally as a last resort" fallback:

```html
<div style="overflow-x:auto;">
  <table class="outing-log-table">...</table>
</div>
```

## 7. Season summary line — inline text, not a table row (AC-2, finding F17)

Rendered as a `<div class="outing-season-line">`, middot-separated prose, matching the `.exec-summary` (lines 64-70) / `.key-player-stats` (lines 118-121) idiom — **not** a rigid `<table>` row, since the field count and badge presence vary per pitcher and a table row would force fixed-width cells for what is fundamentally a sentence.

```css
.outing-season-line {
  font-size: 8pt;
  color: #374151;
  margin: 2px 0 6px;
  padding-left: 2px;
}
```

Field order per epic TN-3, using the E-265-01 `SeasonSummary` fields verbatim (`src/reports/pitcher_outings.py:107-135`), with display formatting resolved per §9:

```html
<div class="outing-season-line">
  {% if season.small_sample %}<span class="depth-badge">{{ season.ip_outs | ip_display }} IP</span>{% else %}{{ season.ip_outs | ip_display }} IP{% endif %}
  &middot; {{ season.games }} G ({{ season.games_started }} GS)
  &middot; {{ season.era | rate2 }} ERA ({{ era_basis.basis }}-inn){% if era_basis.assumed %}*{% endif %}
  &middot; {{ season.whip | rate2 }} WHIP
  &middot; {{ season.fps_pct | pct }} FPS%
  &middot; {{ season.k_per_bf | pct }} K/BF
  &middot; {{ season.bb_per_inn | rate }} BB/INN
  &middot; {% if season.zero_bb %}<span class="depth-badge depth-badge-strong">0 BB</span> K/BB{% elif season.k_per_bb is not none %}{{ season.k_per_bb | rate }} K/BB{% if season.low_bb %} <span class="depth-badge">{{ season.bb }} BB</span>{% endif %}{% else %}&mdash; K/BB{% endif %}
  &middot; {{ season.h_per_bf | pct }} H/BF
</div>
```

Notes:
- `K/BB` keeps its label anchored regardless of which of the three states renders (ratio / strength badge / no-data dash), so the line always reads "... K/BB ..." at the same textual position. The genuine-no-data branch renders a literal `&mdash;` directly rather than `season.k_per_bb | rate` — `season.k_per_bb` is `None` in that branch and `\| rate` would produce the identical em-dash, but the literal is kept for readability since the branch already tests `is not none` explicitly.
- Reuses the sitewide E-264 ERA-basis idiom exactly as the main Pitching table does (line 681) — the existing single `.era-basis-footnote` (line 726) covers the `*` for both tables; do not duplicate the footnote paragraph here.
- All field names above (`ip_outs`, `games`, `games_started`, `era`, `whip`, `fps_pct`, `k_per_bf`, `bb_per_inn`, `k_per_bb`, `zero_bb`, `low_bb`, `bb`, `h_per_bf`, `small_sample`) are checked verbatim against `SeasonSummary` — none renamed.

## 8. Small-sample and BB-count badges (AC-2), and the F11 zero-BB ruling

All three badges reuse the **existing `.depth-badge` component** (line 194: 7pt, 600-weight, `#6b7280` on `#f3f4f6`, 3px radius) — this is literally "the report's existing count-badge convention" the F11 note asks for, applied without modification for two of the three cases:

| Condition (from `SeasonSummary`) | Rendering |
|---|---|
| `small_sample` (`ip_outs < 45`) | Wrap the IP figure in `.depth-badge`: `<span class="depth-badge">{{ ip }} IP</span>` instead of plain text. Shows the actual IP total — a fact, not a warning label — consistent with `.claude/rules/display-philosophy.md`'s "badge IS the context" rule; never dim, never a "small sample" text warning. |
| `low_bb` (`bb < 5`, and not `zero_bb`) | K/BB renders as the normal ratio (`\| rate`, §9), **plus** an adjacent `.depth-badge` showing the raw BB count: `{{ k_per_bb\|rate }} K/BB <span class="depth-badge">{{ bb }} BB</span>`. |
| `zero_bb` (`bf > 0 and bb == 0`) | K/BB ratio is **replaced** (not badged alongside) by a distinct strength badge reading `0 BB` — no fraction (`12/0`), no `∞`. |
| Genuine no-data K/BB (`k_per_bb is None` and `zero_bb` is `False`, i.e. no BF this season) | Plain `&mdash;` — no badge at all. |

**The `zero_bb` badge needs its own variant, not the plain `.depth-badge` gray**, per the AC-2/F11 requirement that it read as a command-*strength* signal, distinct from the neutral "here's a count" badges above and from the bare no-data dash. New modifier class, reusing the report's existing win-green tokens (`.form-chip-w`, lines 92-93 — a palette already meaningful in this exact report, not a new hue):

```css
.depth-badge-strong { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
```

```html
<span class="depth-badge depth-badge-strong">0 BB</span>
```

This satisfies "Zero open display decisions remain" from the story Notes: every one of `small_sample` / `low_bb` / `zero_bb` / genuine-no-data has a pinned, concrete rendering.

## 9. Rate-stat and ERA display formatting (SHOULD FIX 2)

`SeasonSummary`/`Outing` ship **raw, unrounded floats** (e.g. `fps_pct=0.75`, `k_per_bf=0.3333...`, per-outing `era` as an unrounded float) — no percent conversion, no rounding. The report's registered Jinja filters today are only `ip_display`, `format_avg`, `format_date` (`renderer.py:84-86`) — none of them fit a bare `{{ season.fps_pct }}` (would print `0.75`, not `75%`) or a bare `{{ season.era }}` (would print an unrounded float, not `3.15`).

**Pinned approach: register three new Jinja filters in `renderer.py`, at the render boundary, alongside the existing three** (do **not** push formatting back into the DONE `pitcher_outings.py` derivation layer — that module correctly returns raw floats so its output stays testable/composable; formatting is a display concern and belongs where `ip_display`/`format_avg`/`format_date` already live):

```python
# alongside env.filters["ip_display"] = ip_display, etc. (renderer.py:84-86)
env.filters["pct"] = _format_pct     # already defined, renderer.py:467-471 -- register as a filter too
env.filters["rate"] = _format_rate   # already defined, renderer.py:474-478 -- register as a filter too
env.filters["rate2"] = _format_era   # NEW -- same shape as the two above, added alongside them
```

```python
def _format_era(value: float | None) -> str:
    """Format an ERA/WHIP-grain rate to two decimals, e.g. 3.5 -> '3.50'."""
    if value is None:
        return "—"
    return f"{value:.2f}"
```

`_format_pct` and `_format_rate` already exist in `renderer.py` (used procedurally today to build `team_fps_pct`/`_fps_pct`/`_pitches_per_bf` dict values before templating, e.g. line 754, line 484-485) — this is an ADDITIVE registration (also expose them as filters) so the Outings section's raw dataclass fields can be formatted directly in the template, exactly like `ip_display` formats a raw `ip_outs` int today. No existing call site or filter is modified or removed.

**Exact mapping (every rate/ERA field the spec references, one row each):**

| Field | Filter | Example | Why |
|---|---|---|---|
| `fps_pct` (per-outing AND season) | `\| pct` | `0.75` → `75.0%` | Fraction-of-charted-PA; percent reads naturally, matches the existing team-level FPS% treatment (`_format_pct`, already percent). |
| `k_per_bf` | `\| pct` | `0.3333` → `33.3%` | Fraction of batters faced ending in K — same "rate as percent of PA" shape as FPS%. |
| `h_per_bf` | `\| pct` | `0.25` → `25.0%` | Fraction of batters faced who got a hit — same shape. |
| `bb_per_inn` | `\| rate` | `0.45` → `0.5` | Walks-per-inning can exceed 1 (a wild reliever might run 2+ BB/inning) and is conceptually a per-inning counting rate like WHIP, not a fraction-of-PA — NOT percent-formatted. 1-decimal via `\| rate` matches K/9's existing 1-decimal convention without implying the false ceiling-of-1 that percent formatting would. |
| `k_per_bb` | `\| rate` | `3.5` → `3.5` | A ratio, not a fraction-of-PA — can exceed 1 (unlike the three `pct` fields above), so it is NOT percent-formatted. Reuses the existing 1-decimal `_format_rate` shape already used for K/9 and P/BF elsewhere in this report. |
| `era` (per-outing AND season) | `\| rate2` | `3.5` → `3.50` | Matches the sitewide 2-decimal ERA convention (`generator.py:479`, `f"{...:.2f}"`) used by the main Pitching table — same stat, same precision, different data path. |
| `whip` | `\| rate2` | `1.2` → `1.20` | Matches the sitewide 2-decimal WHIP convention (`generator.py:481`). |

Every filter above returns `"—"` (em-dash, matching the report's most common None-signal, e.g. lines 524, 715, 858) when the input is `None` — this is already built into `_format_pct`/`_format_rate` today and is replicated in the new `_format_era`, so no template-side `is not none` ternary is needed around any of these seven fields (the `k_per_bb` genuine-no-data branch in §7 is the one exception, and it is handled by the surrounding `{% if/elif/else %}` rather than the filter, since that branch also has to choose between three different renderings, not just fill in a dash).

## 10. AC traceability

- **AC-1**: §3 (column table with confirmed `Outing` attribute names, tiers, order, full row markup, None-handling) + Opp truncation (§3). Cites real `mob-hide`/`mob-hide-extra` (lines 468, 470) and `.spray-card-identity` (lines 225-229).
- **AC-2**: §7 (inline season line, not a table row, all `SeasonSummary` fields confirmed) + §8 (small-sample / low-bb / zero-bb badge matrix) + §9 (rate-stat display formatting). Cites `.exec-summary`/`.key-player-stats` (lines 64-70, 118-121) and `.depth-badge` (line 194); complies with `.claude/rules/display-philosophy.md`.
- **AC-3**: §4 (`<details>`/`<summary>`, 44px target, green summary indicator, no `throws` residual) + §5 (`.outing-strong` green-only row) + §6 (print-pagination override).
- **AC-4**: §1/§2 (section-level `.sort-annotation` note, not per-column badges, correctly nested inside the `show_pitcher_outings` gate).
- **AC-5**: This spec maps only the fixed TN-2/TN-3 field set (as delivered by E-265-01's `Outing`/`SeasonSummary`/`PitcherOutings`, field names confirmed against the shipped dataclass source) to concrete markup, CSS, and — per §9 — the exact display formatting for every rate/ERA field. No additional stats, columns, or display states are introduced; combined-XBH, Result/form-chip, and `throws` all remain explicitly out of v1. Byte-identical flag-off behavior (§1) and the flag-on-empty-data path (§1, AC-6) are both pinned so E-265-02 has no residual gating decision either.

## 11. Full CSS block (for direct reference / copy-paste by E-265-02)

```css
/* ---- Outings Breakdown (E-265) ---- */
.outings-section { page-break-before: always; }

.outing-log { margin: 6px 0; }
.outing-log-summary {
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  font-weight: bold;
  font-size: 9pt;
  padding: 4px 2px;
}
.outing-log-flag { color: #16a34a; margin-left: 2px; }

.outing-season-line {
  font-size: 8pt;
  color: #374151;
  margin: 2px 0 6px;
  padding-left: 2px;
}

.outing-opp {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}

tr.outing-strong td { background: #f0fdf4; }
tr.outing-strong td:first-child { border-left: 3px solid #16a34a; }

.depth-badge-strong { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }

@media print {
  details.outing-log { display: block; }
  details.outing-log > summary { display: none; }
  details.outing-log > *:not(summary) { display: block !important; }
  .outing-season-line { page-break-after: avoid; }
  table.outing-log-table { page-break-inside: auto; }
  table.outing-log-table tr { page-break-inside: avoid; }
}

@media screen and (max-width: 640px) {
  .outing-opp { max-width: 60px; }
}
```

(`.mob-hide` / `.mob-hide-extra` are reused unchanged from lines 468/470 — not repeated here. The three new Jinja filters — `pct`, `rate`, `rate2` — are Python registrations in `renderer.py`, not CSS; see §9.)
