# E-228-04: Positioning Cards Design Spec

**Story**: E-228-04 — Positioning cards design spec (wireframes + print-CSS spec)
**Reference mockup**: `.project/research/E-228-positioning-cards-mockup.html`
**Implements for**: E-228-05 (template + report bundle integration), E-228-07 (opponent-dashboard link)

---

## 1. Decision summary (locked)

These decisions are this story's to lock per the epic Technical Notes and the story ACs. They are not open for re-litigation in E-228-05 / E-228-07.

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | Shallow-variant display word (TN-5, AC-1e) | **"SHADE LEFT SHALLOW" / "SHADE RIGHT SHALLOW"** | "IN" is ambiguous with "infield shift" (an actual HS-level baseball play). "SHALLOW" is unambiguous; column widths and card headings accept the extra characters without crowding. Coach-friendly = unambiguous beats short. |
| D2 | Per-position column order (AC-1) | **LF · CF · RF · 3B · SS · 2B** | Coach's recommended starting order. Groups OF together and IF together so a coach scanning a TRUE row stays in one mental frame, and a coach scanning a MIXED row sees the OF/IF split immediately. L→R-from-dugout sub-order inside each group matches how a coach standing in the dugout sees the field. |
| D3 | Cards per portrait sheet (AC-2, AC-3) | **6 cards, 2 columns × 3 rows, one sheet** | 6 covered positions = exact fit. At 8.5"×11" portrait with 0.3" margins, each card is ~3.95"×3.47" — pocket-card form factor (cuts cleanly to back-pocket size). The brainstorm's "8-up" was never reconciled against the actual card count; 8-up would force two empty slots or duplicate cards, both worse than 6-up. |
| D4 | Deviation-magnitude display in confidence column (AC-1d) | **Do NOT surface in v1.** Persisted `direction_deviation` / `depth_deviation` are read-available but the call sheet does not render them. | (1) The confidence column is the recognition-task trust cue (BIP + HR + thin). Adding a fourth axis increases scan cost against display-philosophy. (2) The deviation buckets are deliberately coarse (`0`/`±1`/`±2` per TN-3 Stage A); they don't carry honest precision beyond what `call_state` already encodes categorically. (3) Persistence is preserved so a future calibration pass can pull this surface forward without a schema change. **E-228-05 AC-9 binds the build to this decision: no deviation-magnitude affordance in v1.** |
| D5 | Call-sheet row sort (AC-1, AC-9) | **Non-TRUE `team_state_call` first, then jersey number ascending within each group** | Pre-game prep is the primary use — flagged batters at top. Jersey-ascending secondary sort keeps the call sheet usable as a mid-game cross-reference (a coach who reads jersey # off the scoreboard finds the row in O(1) scan). Flagged-first ordering subverts the "13-row scan to find 3 calls" footgun. |
| D6 | Per-position cell vocabulary (AC-4) | **Short-form codes**: TRUE→`·` · LEFT→`L` · LEFT_SHALLOW→`L Sh` · LEFT_DEEP→`L Dp` · RIGHT→`R` · RIGHT_SHALLOW→`R Sh` · RIGHT_DEEP→`R Dp` | The CALL column uses the full lexical vocabulary (D1). The per-position cells need a compact form so a 6-column matrix fits on landscape without column squeeze. `·` for TRUE makes the silent-default cells visually quiet — they are not 0s or blanks, they are intentional non-calls. |
| D7 | AC-7 dashboard link placement | **A standalone "Defensive Positioning" card on the opponent dashboard, placed immediately before the Team Spray Chart card.** Card contains the link + freshness cue + empty-state. | Positioning is the downstream actionable artifact of the spray data. Adjacency to the Team Spray Chart card reads naturally as "here's where they hit → here are your positioning cards." |

---

## 2. Locked vocabulary table (AC-1e — single source of truth)

The render-layer constants block in E-228-05 implements this table **verbatim**. No "or" / no alternatives. If E-228-05 needs to diverge, escalate — this table wins.

| Stored `call_state` / `team_state_call` enum key | Display call-word (full form) | Per-position cell short form (D6) |
|---|---|---|
| `TRUE` | `STRAIGHT UP` | `·` |
| `LEFT` | `SHADE LEFT` | `L` |
| `LEFT_SHALLOW` | `SHADE LEFT SHALLOW` | `L Sh` |
| `LEFT_DEEP` | `SHADE LEFT DEEP` | `L Dp` |
| `RIGHT` | `SHADE RIGHT` | `R` |
| `RIGHT_SHALLOW` | `SHADE RIGHT SHALLOW` | `R Sh` |
| `RIGHT_DEEP` | `SHADE RIGHT DEEP` | `R Dp` |
| `MIXED` | `MIXED` | (n/a — `MIXED` is only ever a `team_state_call`, never a per-position `call_state`; the engine's Stage B/C never returns `MIXED` per `_compute_position_row` in `src/reports/positioning.py`) |

**Render-layer responsibility (E-228-05 AC-8)**: the constants block is a Python dict mapping each stored enum key to the full display word above. The short-form column may be a second constants block, or derived algorithmically from the full form (e.g., a function that returns the short form for cell rendering). Either is acceptable as long as the full-form mapping is verbatim.

**Provenance**: TN-5's recommended defaults are taken as-is except for the shallow word — D1 picks "SHALLOW" over the TN-5 default "IN" per the locked rationale above.

---

## 3. Call sheet — landscape (AC-1, AC-4, AC-5)

### 3.1 ASCII wireframe (single page, landscape)

```
+----+-----------+----------------------+-----+-----+-----+-----+-----+-----+-----------------+-----------------------------+
| #  | NAME      | CALL                 | LF  | CF  | RF  | 3B  | SS  | 2B  | CONFIDENCE      | NOTE                        |
+----+-----------+----------------------+-----+-----+-----+-----+-----+-----+-----------------+-----------------------------+
| 7  | RAMIREZ   | SHADE LEFT           | L   | L   | ·   | L   | ·   | ·   | 38 BIP · 2 HR   | Pulls grounders early count |
| 23 | THOMPSON  | MIXED                | ·   | ·   | R Dp| L Dp| L   | ·   | 41 BIP · 4 HR   | Goes oppo on offspeed       |
| 4  | WRIGHT    | SHADE RIGHT SHALLOW  | ·   | ·   | R Sh| ·   | ·   | R Sh| 33 BIP · 1 HR   | Slap hitter, beats out IF   |
| 11 | DAVIS     | SHADE LEFT           | L   | ·   | ·   | L   | ·   | ·   | 18 BIP · 0 HR   | Direction only (light data) |
+----+-----------+----------------------+-----+-----+-----+-----+-----+-----+-----------------+-----------------------------+
| 9  | NGUYEN    | STRAIGHT UP          | ·   | ·   | ·   | ·   | ·   | ·   | 27 BIP · 0 HR   |                             |
| 12 | JOHNSON   | STRAIGHT UP          | ·   | ·   | ·   | ·   | ·   | ·   | 22 BIP · 0 HR   |                             |
| 15 | KIM       | STRAIGHT UP          | ·   | ·   | ·   | ·   | ·   | ·   | 14 BIP · 0 HR   |                             |
| 3  | LOPEZ     | STRAIGHT UP          | ·   | ·   | ·   | ·   | ·   | ·   |  6 BIP · 0 HR · thin                              |
+----+-----------+----------------------+-----+-----+-----+-----+-----+-----+-----------------+-----------------------------+
                                                                  ^                            ^                            ^
                                                                  |                            |                            |
                                                            per-position cells          confidence column              LLM rationale slot
                                                              (D6 short form)         (BIP · HR · thin if is_thin=1) (empty when LLM off)
```

### 3.2 Column set (locked per AC-1)

In order, left to right:

| Col | Field | Width hint | Source |
|---|---|---|---|
| 1 | Jersey # (`#`) | ~0.5" | `players.jersey_number` (may be NULL — render `—`) |
| 2 | Name | ~1.5" | `players.first_name + last_name` (may be unresolved — render in `text-gray-500 italic` like existing scouting tables) |
| 3 | CALL (team-state) | ~1.6" | `batter_positioning.team_state_call` → display word from §2 |
| 4-9 | Per-position cells (LF · CF · RF · 3B · SS · 2B) | ~0.5" each | 6 of the 6 `batter_positioning` rows for the batter (one per `position`) → short form from §2 (`call_state`) |
| 10 | Confidence | ~1.3" | `{bip_count} BIP · {hr_count} HR` plus `· thin` when `is_thin=1` |
| 11 | Note (LLM rationale slot) | ~2.4" | E-228-07 fills this; empty when LLM off (AC-4 requirement: call sheet must be fully usable without it) |

**No "lineup slot" column.** Dropped per CX-1.2 (batting order is game-scoped; stale heuristic worse than nothing).

**No "bats L/R" column.** Handedness is unavailable on every E-228 data path (epic Non-Goal); NULL-in-every-row would damage trust.

### 3.3 Column order rationale (D2)

Coach's recommended starting order: **LF · CF · RF · 3B · SS · 2B**. Two groupings:

- **OF first, IF second** — most defensive shifts involve coordinated OF moves; clustering them adjacent makes a coach's eye stay in one frame when scanning a single row.
- **L→R-from-dugout within each group** — matches the coach's physical view from the dugout. LF visually leftmost; 3B visually leftmost on the infield.

**Alternative considered and rejected (for documentation, not for v1)**: a pull-side-vs-oppo-side grouping (3B/LF · SS · CF · 2B/RF) would help on MIXED rows but conflates handedness reasoning with the engine's absolute LEFT/RIGHT vocabulary. Rejected — the data is absolute, the column order should follow the absolute field, not handedness analytics.

### 3.4 Row sort (D5)

1. Rows with `team_state_call != 'TRUE'` first (flagged batters).
2. Rows with `team_state_call == 'TRUE'` second (silent-default batters).
3. Within each group, ascending by jersey number (NULLs last).
4. A visible 1px-gray horizontal separator between the two groups (see mockup) makes the boundary read as intentional.

This is one row per batter — the call sheet collapses the 6 per-position rows in `batter_positioning` into a single row by `player_id` per batter.

### 3.5 Per-position cell rendering (D6, AC-4)

Short-form codes per §2. Visual treatment:

- `·` for TRUE — single mid-gray dot, centered, smaller font (this is the silent-default cell; visually quiet so the eye skips it). Concretely: `color: #9ca3af; font-size: 0.85em` relative to the row.
- `L` / `R` / `L Sh` / `L Dp` / `R Sh` / `R Dp` — at full visual weight, bold, no color highlight (this print is black-and-white-printer fidelity per AC-3). The CELL itself is the call.

**No background-color tint** on flagged cells. Print-fidelity rule: every visual signal must read identically on a dugout B&W printer. Bold + text is sufficient differentiation against the silent `·` rows.

### 3.6 Confidence column (AC-4, AC-6 in E-228-05)

Always rendered at full visual weight per `.claude/rules/display-philosophy.md`. Format:

```
{bip_count} BIP · {hr_count} HR[ · thin]
```

- `{bip_count} BIP` — always present.
- `· {hr_count} HR` — always present, even when 0 (consistent visual weight per HR over-the-fence undercount note in TN-4).
- `· thin` — appended when `is_thin = 1` (per-batter `bip_count < 10` from the engine). The tag is plain text at the same font weight as the BIP / HR text — no dimming, no color flag.

**No "LIGHT DATA" tag for the 10-24 BIP partial-data band.** The BIP count itself is the context; coaches see "18 BIP" and know what that is. The CALL word (e.g., "SHADE LEFT" without depth) is itself the partial-data signal. Adding a tag would over-instrument and arguably contradict the philosophy ("the badge IS the context").

### 3.7 LLM rationale slot (AC-4, E-228-07 fills it)

A `<td>` rendered as a single line of italic gray text, max ~30 chars. When empty (LLM off, LLM unavailable, or LLM-failure-skipped per E-228-07 AC-2/AC-2a): the cell renders blank — no placeholder, no em-dash, nothing. Quiet absence.

**Critical**: the call sheet MUST be fully usable with this slot empty across every row. The CALL column and per-position cells together carry the actionable instruction; the rationale is enrichment.

---

## 4. Player card — portrait, multi-up sheet (AC-2)

### 4.1 ASCII wireframe (one card, ~3.95"×3.47")

```
+----------------------------------+
|  CENTERFIELD                     |
|  ----------------------------    |
|                                  |
|         STRAIGHT UP              |   <-- the default, big, ~36pt
|                                  |
|  ----------------------------    |
|  EXCEPTIONS                      |   <-- subhead, ~9pt
|                                  |
|  #7   RAMIREZ    SHADE LEFT      |
|  #23  THOMPSON   R Dp (MIXED)    |   <-- MIXED: per-position cell + (MIXED) tag
|  #4   WRIGHT     SHADE RIGHT Sh  |
|                                  |
|  (no further exceptions)         |   <-- only if 0 exceptions, see 4.4
|                                  |
+----------------------------------+
```

### 4.2 Card anatomy

- **Position name (header)**: full word, bold, ~14pt. `CENTERFIELD` / `LEFT FIELD` / `RIGHT FIELD` / `SHORTSTOP` / `SECOND BASE` / `THIRD BASE`. Full words (not "CF") so a glove-on player reading at arm's length is never decoding an abbreviation.
- **Default block**: `STRAIGHT UP` in **~36pt bold** centered. This is the only call most players will follow — it must dominate the card visually. (Baseball-coach review locked ~36pt: legible at a greater distance and in shadowed dugout conditions than a smaller value.)
- **Exceptions subhead**: `EXCEPTIONS` in ~9pt small-caps, gray.
- **Exception rows**: one per opposing batter whose `call_state` for *this* position is not `TRUE`. Format:

  ```
  #{jersey_number}   {LAST_NAME}        {DISPLAY_CALL}
  ```

  - **Jersey number column**: ~3 chars, left-aligned, bold, **11pt**.
  - **Name column**: ~10 chars, uppercase last name, ellipsis-truncated, **10pt**.
  - **Call column**: right-aligned, the full display word for the row's `call_state` (NOT short form — this is the actionable instruction the player reads), bold, **11pt**.

  **Font hierarchy rationale (baseball-coach review)**: the call word is the field the fielder acts on, so it ties the jersey number for the largest type in the row at 11pt bold. The name is secondary context (the verbal call may use either jersey or name) and sits at 10pt regular. This puts the actionable field at the top of the row's visual hierarchy, not the bottom.
- **MIXED handling**: when the batter's `team_state_call = 'MIXED'` AND this position's `call_state` is not `TRUE`, the exception row shows the position's own short-form cell value followed by `(MIXED)` in small caps. Coaches who yelled "#23 MIXED" can find the row; the per-position cell tells the fielder what THIS position does. Coaches who yelled "#23 SHADE LEFT" find the row by jersey too.

### 4.3 Exceptions list length

Baseball-coach's known failure mode: "more than 5-6 exception rows per card." With a typical HS scouted lineup of ~13 batters and only 2-4 flagged in a game, a single position's exception list rarely exceeds 4. Spec the card to comfortably hold **6 exception rows** (4 typical + 2 headroom). If a card would exceed 6 exceptions:

- Render the top 6 by `bip_count` descending (most-evidenced batters first).
- Footer row: `+N more — see call sheet` in 7pt gray italic, centered.

This is a soft constraint — E-228-05 should render all exceptions if they fit, and only truncate at the 6-row safety bound. Realistic data should rarely trigger truncation.

### 4.4 Empty exception list (AC-5 all-TRUE)

When a position has 0 exceptions (e.g., the engine flagged no batters in this column), the card shows the position name + `STRAIGHT UP` default block + EXCEPTIONS subhead, then a single italic gray line: `No exceptions for this opponent.`

This must read as intentional — the position card carries a real instruction ("play straight up against everyone") even when there are no exceptions. The card is not "empty" — it is a complete instruction.

### 4.5 Card jersey-keying (AC-9)

Each card is keyed by **fielding position** (CF, LF, RF, 3B, SS, 2B), and the exception rows are keyed by **batter jersey number**. So a coach who yells "#23 SHADE LEFT" routes the call to:

- The CF player (looks at their CF card) finds row `#23` → reads `SHADE LEFT`.
- The 3B player (looks at their 3B card) finds row `#23` → reads `SHADE LEFT DEEP`.
- The 2B player (looks at their 2B card) sees no `#23` row → silent default `STRAIGHT UP`.

The single jersey key (`#23`) decodes to a per-position instruction on each fielder's card. This is the design's core mechanic — AC-9 satisfied.

### 4.6 Utility-player card (AC-2 — design only, v1 does NOT render)

Two-position card for a utility player who plays e.g. SS and 3B in the same game:

```
+----------------------------------+
|  SHORTSTOP  |  THIRD BASE        |
|  -----------+-----------------   |
|                                  |
|  DEFAULT FOR BOTH:               |
|         STRAIGHT UP              |
|                                  |
|  -----------+-----------------   |
|  EXCEPTIONS (SS)                 |
|  #7   RAMIREZ    SHADE LEFT      |
|  #23  THOMPSON   L (MIXED)       |
|                                  |
|  EXCEPTIONS (3B)                 |
|  #7   RAMIREZ    SHADE LEFT      |
|  #23  THOMPSON   L Dp (MIXED)    |
|                                  |
+----------------------------------+
```

Two side-by-side sub-cards sharing the `STRAIGHT UP` default but split exception lists. Spec only — v1 always renders 6 single-position cards per E-228-05 AC-2.

**Future-use note for the operator**: when the utility variant is built, it likely replaces 1-2 single-position cards in the 6-up grid (e.g., a 3-card sheet with one utility card + 4 single cards). The grid geometry (2×3 portrait) accommodates the utility card at the same outer dimensions — utility cards are not a different size.

### 4.7 Cards-per-sheet geometry (D3)

- **6 cards per sheet**, arranged **2 columns × 3 rows**, on a **portrait** page.
- 8.5"×11" minus 0.3" margins = 7.9"×10.4" usable area.
- 0.15" inter-card gutter.
- Each card outer dimensions: ~3.875" × ~3.37" (roughly index-card sized; cuts to ~3.75"×3.25" if the player trims the gutter).
- Cut guidelines: 0.5pt gray lines on the gutters so a coach with scissors cuts cleanly (see print CSS in §6).

---

## 5. Sample mockup row coverage (AC-5)

The reference mockup (`E-228-positioning-cards-mockup.html`) demonstrates all five edge/render states from AC-5:

| AC-5 state | Mockup demonstration |
|---|---|
| Zero scouted batters | Bottom of the mockup — empty-state block shown in a labeled "Zero-batter case" demo card. The call-sheet renders with a single info row: "No scouted batters yet. Cards will appear after the first scouting pull." Player cards render with `STRAIGHT UP` defaults and the empty-exceptions line. |
| All-TRUE lineup (no exceptions) | Demonstrated by rows 5-8 in the call sheet (every batter `STRAIGHT UP`). Player cards in this case all show `STRAIGHT UP` + "No exceptions for this opponent." |
| Batter with MIXED call | Row 2 (Thompson) — MIXED in the CALL column, per-position cells show the differing per-position calls. |
| Partial-data batter (10-24 BIP, direction lean, NULL depth) | Row 4 (Davis, 18 BIP) — direction-only call ("SHADE LEFT"), per-position cells use direction-only codes (`L` rather than `L Sh` / `L Dp`), confidence column shows the BIP count as its own context. **Reads as intentional** — the SHADE LEFT call without depth is a complete instruction. |
| Thin-data batter (< 10 BIP, is_thin=1) | Row 8 (Lopez, 6 BIP) — `STRAIGHT UP` call (the engine writes TRUE for all 6 positions when `is_thin=1`), confidence column appends `· thin`. The row is shown not because it's flagged but because the call sheet shows every batter; thin batters cluster at the bottom of the TRUE group. |

---

## 6. Print CSS spec (AC-3)

Following the existing mixed-orientation pattern in `src/api/templates/reports/scouting_report.html` (named `@page` blocks around lines 307-314; multi-up portrait grid with `break-inside: avoid` around lines 395-407). The positioning section is appended to the report bundle after the existing spray section.

### 6.1 Named `@page` blocks

```css
@page call-sheet {
  size: landscape;
  margin: 0.4in;
}

@page positioning-cards {
  size: portrait;
  margin: 0.3in;
}
```

### 6.2 Print rules

```css
@media print {
  /* Call sheet — landscape page */
  .positioning-call-sheet {
    page: call-sheet;
    break-before: page;          /* new page after the existing spray section */
  }

  /* Player cards — portrait page, multi-up grid */
  .positioning-cards-sheet {
    page: positioning-cards;
    break-before: page;
  }

  .positioning-cards-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    grid-template-rows: repeat(3, 1fr);
    gap: 0.15in;
    height: 100%;
  }

  .positioning-card {
    border: 0.5pt solid #ccc;     /* cut guideline */
    padding: 0.15in;
    break-inside: avoid;
    page-break-inside: avoid;
    display: flex;
    flex-direction: column;
  }

  .positioning-call-sheet table { page-break-inside: avoid; }
  .positioning-call-sheet tr { page-break-inside: avoid; }
}
```

### 6.3 Black-and-white dugout-printer fidelity

Every visual signal must be readable on a B&W laser printer. Concrete constraints:

- **No background-color tint** for cells or rows (no green/red/yellow heat-map tints). All differentiation is via text weight, size, and character choice (`·` vs. text).
- **No grayscale dimming** to convey sample size. Display-philosophy: never suppress. Sample size displays as a BIP number, full weight.
- **Borders are 0.5pt solid #ccc** — light enough not to dominate, dark enough to print as a visible cut line.
- **All fonts**: Arial/Helvetica (already in `scouting_report.html`); no custom web fonts (they won't print reliably).

### 6.4 Cards-per-sheet cut geometry (D3, AC-3)

Each card's outer border is the cut line. The 0.15" gutter between cards means a coach with scissors can cut along either the gutter midline (gets all 6 cards with rough edges) or straight along each card border (gets all 6 cards with clean edges). The card content uses an 0.15" internal padding so trimming up to the border doesn't clip text.

---

## 7. Component inventory (AC-4)

For E-228-05's implementation. Each component is a named, reusable rendering unit:

| Component | Used on | Source data | Notes |
|---|---|---|---|
| **`call-cell`** (named-state cell) | Call sheet, per-position cells (cols 4-9) | `batter_positioning.call_state` for one (batter, position) | Renders the short-form code from §2 D6. `·` for TRUE in light gray; named codes in bold black. No background. |
| **`call-word`** (full display word) | Call sheet CALL column; player card default block; player card exception rows | `batter_positioning.team_state_call` (call sheet); `batter_positioning.call_state` (player card) | Renders the full display word from §2. The render-layer constants block (E-228-05 AC-8) is the single source. |
| **`confidence-cell`** | Call sheet confidence column | `bip_count`, `hr_count`, `is_thin` (denormalized, identical across the batter's 6 rows) | Format: `{bip_count} BIP · {hr_count} HR[ · thin]`. Full visual weight per display-philosophy. No deviation magnitude (D4). |
| **`straight-up-block`** | Player card default block | constant string `"STRAIGHT UP"` | ~36pt bold centered. Dominates the card. |
| **`exception-row`** | Player card exceptions list | `(jersey_number, last_name, call_state)` for one batter at this position | `#NN   LASTNAME   FULL_CALL_WORD`. Sorted by jersey number ascending. |
| **`mixed-tag`** | Player card exception row when batter's `team_state_call='MIXED'` | constant `(MIXED)` in small caps | Suffix to the `call-word` in the same row. Tells the fielder this row came from the MIXED-call batter — coach may have yelled "MIXED" or yelled the jersey. |
| **`thin-tag`** | Call sheet confidence column | derived from `is_thin=1` | The `· thin` suffix; same font weight as BIP/HR (per display-philosophy). |
| **`partial-data row`** | (No special component — see notes) | `bip_count >= 10 AND bip_count < 25` (effectively: every `call_state` is `TRUE` or direction-only) | **Renders identically to a full-data row**. The CALL word (e.g., `SHADE LEFT`) and the BIP count are the context. No dimming, no tag. |
| **`positioning-card-default-line`** | Player card when 0 exceptions | constant string `"No exceptions for this opponent."` | Italic gray, ~9pt. Reads as intentional. |
| **`positioning-empty-state`** | Call sheet when zero scouted batters | (no data) | A single info row: "No scouted batters yet. Cards will appear after the first scouting pull." Player cards render `STRAIGHT UP` defaults across all 6 positions, with the empty-exceptions line. |
| **`llm-rationale-cell`** | Call sheet note column | Tier 2 output (E-228-07) | Empty when LLM off / unavailable / failed. Plain italic gray text, max ~30 chars; longer text truncated by `text-overflow: ellipsis` (with title attribute for full text on hover in screen view). |

**Excluded by D4**: there is NO `deviation-magnitude` component in v1. E-228-05 AC-9 binds the build to this exclusion.

---

## 8. Opponent dashboard link treatment (AC-7, for E-228-07)

### 8.1 Placement (D7)

Add a new card to `src/api/templates/dashboard/opponent_detail.html`, placed in the "State C: Full stats" block, immediately **before** the existing `Team Spray Chart` card (around line 466 in the current template).

Rationale: positioning is the downstream actionable artifact of the spray data. Adjacency reads naturally as "here's where they hit (spray) → here are your positioning cards." Both cards share the same visual treatment (`bg-white rounded shadow border border-gray-200 p-4`).

### 8.2 Card markup (HTML/Tailwind reference)

```html
<!-- Defensive Positioning card — placed before Team Spray Chart -->
<div class="mb-4 bg-white rounded shadow border border-gray-200 p-4">
  <div class="flex items-baseline justify-between mb-2">
    <h2 class="text-base font-bold text-blue-900">Defensive Positioning</h2>
    {% if positioning_report and positioning_report.coverage_text %}
    <span class="text-xs text-gray-500">{{ positioning_report.coverage_text }}</span>
    {% endif %}
  </div>

  {% if positioning_report and positioning_report.slug %}
  <!-- READY state: real link to the standalone report -->
  <a href="/reports/{{ positioning_report.slug }}"
     class="inline-block bg-blue-900 text-white px-4 py-2 rounded text-sm hover:bg-blue-800">
    Open positioning cards &rarr;
  </a>
  <p class="text-xs text-gray-500 mt-2">Print-ready: landscape call sheet + 6 player cards.</p>

  {% elif empty_state_reason == "not_yet_scouted" %}
  <!-- Transitional state: tracked opponent, no scout has run yet -->
  <p class="text-sm text-gray-700">Positioning cards generate automatically with each scouting update.</p>
  <p class="text-xs text-gray-500 mt-1">Cards will appear after the first scouting pull.</p>

  {% elif empty_state_reason == "generation_failed" %}
  <!-- Transitional state: scout ran but report generation failed -->
  <p class="text-sm text-gray-700">Card generation didn't complete on the last update.</p>
  <p class="text-xs text-gray-500 mt-1">The next scouting update will retry automatically.</p>

  {% else %}
  <!-- Fallback empty state -->
  <p class="text-sm text-gray-700">No positioning cards yet.</p>
  <p class="text-xs text-gray-500 mt-1">Cards will appear after the next scouting update.</p>
  {% endif %}
</div>
```

### 8.3 Behavioral contract

- **(a)** The link is a **real link** to an existing `ready` report at `/reports/{slug}` (per epic TN-7 and E-228-07 AC-4) — NOT an on-click generate-with-spinner. The link target comes from `reports WHERE team_id=? AND status='ready' ORDER BY generated_at DESC LIMIT 1` in the route handler.
- **(b)** The freshness cue is a **game-coverage string** (`Through {date} ({N} games)`) using the existing `_format_coverage_text()` helper in `src/api/routes/dashboard.py:976`. Critically, this string reflects when the **displayed report** was generated — NOT when the most recent scout ran. If the latest scout failed mid-pipeline and the displayed report is older, the coverage cue must reflect the older report's coverage. E-228-07's route handler reads the report's `generated_at` and the underlying coverage at that time. **NOT** a system sync date.
- **(c)** The empty state is the **transitional / failure-recovery state** under (B) Pre-generate (epic TN-7). It surfaces when (i) the tracked opponent has not yet been scouted, or (ii) `generate_report()` failed during a scout (E-228-06 AC-6a non-fatal path). It must read as intentional, not broken — coaches see "cards will appear after the next scouting update," not a stack-trace or a generic "report not found."

### 8.4 What this design does NOT include

- **No inline positioning view** on the opponent dashboard. Epic Non-Goal: "an inline positioning view on the opponent dashboard." v1 ships a link to the bundle only.
- **No "Generate now" button**. Per epic TN-7 (B) Pre-generate, generation is the scout pipeline's job; the dashboard is read-only with respect to report state.
- **No separate dashboard card view of the cards themselves**. Per epic TN-7 / CX-2, the tracked-opponent rendering surface IS the standalone report bundle, reached by reuse. The dashboard surface is just the link.

---

## 9. Jersey-number keying (AC-9)

Summary of how jersey numbers thread through the design:

| Surface | Keyed by |
|---|---|
| Call sheet — leftmost column | Batter's jersey number |
| Player card — exception row leftmost field | Batter's jersey number |
| Coach's verbal call | Jersey number ("#23") or name ("#23 SHADE LEFT" / "MIXED" / "RAMIREZ SHADE LEFT") |
| Player decode path | Jersey number on the verbal call → jersey row on the player's own position card → call word in the same row |

The single key (#NN) resolves to a per-position instruction on each fielder's card. AC-9 satisfied.

**Missing jersey numbers**: when a batter's `players.jersey_number` is NULL (rare — usually a roster gap), render `—` in the # column. The row still appears (the call sheet shows every scouted batter). On the player card exception list, the row is sorted to the bottom with `—` in the # cell and the name as the primary key. The coach can still match by name.

---

## 10. Reference mockup (AC-6)

A standalone HTML/Tailwind mockup at `.project/research/E-228-positioning-cards-mockup.html` renders:

1. The landscape call sheet with all five AC-5 edge states demonstrated.
2. The portrait player cards sheet (2×3 grid, 6 cards) — one card per covered position, each demonstrating exception rows and the MIXED tag.
3. The utility-player card variant (design-only).
4. The opponent dashboard link card (READY state + the two transitional states).
5. Print CSS following the existing `scouting_report.html` precedent.

The mockup is **concrete enough to serve as E-228-05's implementation target**. E-228-05 adapts it into a Jinja2 template (`src/api/templates/reports/positioning_cards.html`) consuming the data dict produced by the new query function in `src/reports/generator.py`. The mockup uses inline static data; E-228-05 swaps inline data for `{{ … }}` expressions and `{% for %}` loops.

---

## 11. baseball-coach review record (AC-8)

This section is a **deterministic deliverable per AC-8** — the AC is satisfied by the *presence* of a complete review record, not by a PASS verdict. PM relays this spec to baseball-coach after the initial draft is ready (per the team-lead message at story assignment); the verdict, date, and findings/confirmations are filled in below upon return.

**Review prompt to baseball-coach**:

> Do the wireframes in this spec support a glove-on, ~20-seconds-before-a-pitch lookup — as a recognition task, not an analysis task? Specifically:
>
> - Can a 15-year-old fielder go from "coach yelled #23" to "I know where to stand" in under 5 seconds using only this position's player card?
> - Is the call sheet usable by a coach who needs to call shifts mid-inning from the dugout, without reading more than one row?
> - Are the known failure modes absent? (small font; dense tables; >5-6 exception rows per card; anything requiring a two-column read to decode one call.)
>
> If FAIL: itemize the specific failure points, name the affected wireframe element, and identify the cause.
> If PASS: confirm explicitly that none of the known failure modes are present.

### Baseball-coach review (AC-8)
- **Verdict**: PASS
- **Date**: 2026-05-15
- **Reviewer**: baseball-coach

- **Known failure modes checked**: small font (none — see stylistic note), dense tables (none — coach primary flow unblocked), >5-6 exception rows per card (none — max 3 in mockup, 6-row cap with truncation in spec), two-column read to decode one call (none — full call phrase in single column throughout), recognition-to-analysis push (none — both artifacts are structured for one-key/one-call lookup).

- **Confirmation**: None of the known failure modes are present in the wireframes. Both the player card and the call sheet support the intended glove-on recognition task.

  - **Player card**: The fielder flow is: (1) locate jersey number in the left column of the exceptions list, (2) read the full call word from the right column in the same row. One scan, one call. The dominant `STRAIGHT UP` default block visually fills the card for the common case; exceptions are a short, jersey-keyed list beneath it. The MIXED-batter rows carry the full position-specific call word plus a `(MIXED)` suffix — still a single-column read. The six-row cap and sort-by-BIP truncation rule prevent the exception list from ever overloading a fielder's 20-second scan window.

  - **Call sheet**: The coach flow is: (1) locate the row by jersey number or name (bold leftmost columns), (2) read the CALL column (col 3, bold, left-aligned) for the single verbal instruction. The per-position cells (cols 4–9) and the confidence column are supplementary reference — they come after the CALL column and do not need to be read to make the verbal call. The flagged-first row sort (D5) ensures the batters that need a call are in the first visible rows, not buried.

- **Optional commentary**:

  1. **Spec vs. mockup CSS discrepancy — default block font size (stylistic, not a FAIL)**: The spec (§4.2) specifies `~36pt` bold for the `STRAIGHT UP` default block. The mockup CSS implements it at `28pt`. Neither size fails the readability test on a ~3.95" card, but the larger size makes the default call legible at a greater distance and in shadowed dugout conditions. E-228-05 should implement at ~36pt per the spec, not the 28pt in the mockup CSS.

  2. **Exception call word font is the smallest type on the card (stylistic, not a FAIL)**: The `card-exception-call` is `9.5pt` bold, which is smaller than the jersey number (`11pt`) and name (`10pt`) in the same row. For a 15-year-old in good lighting holding the card at 12–18 inches, 9.5pt bold is readable — it's not squinting territory. But the call word is the most important field in the exception row, and font hierarchy usually puts the most important field at the largest or equivalent size, not the smallest. UXD may want to bump `card-exception-call` to `10–11pt` to reduce risk in low-light afternoon shadows or at-arm's-length distance. This is a calibration-pass item, not a FAIL.

  3. **SECOND BASE card inconsistency between mockup sections (informational)**: In Section 3 (the 6-card grid), the SECOND BASE card shows two exception rows (#4 WRIGHT, #19). In Section 4 (the all-TRUE edge-state demo), the same SECOND BASE card shows "No exceptions for this opponent." Both are valid edge states and both are explicitly labeled as separate AC-5 demonstrations. Not a design flaw — flagging it so E-228-05 doesn't treat the Section 3 card as the canonical all-TRUE rendering.

### Post-review reconciliation (UXD)

The PASS verdict closes AC-8. The three optional-commentary items above were addressed as follows:

- **(A) §4.2 / mockup default-block size**: The mockup CSS for `.card-default-block` was bumped from `28pt` to `36pt` to match the spec. Spec and mockup now agree at ~36pt.
- **(B) Exception call-word font hierarchy**: `.card-exception-call` in the mockup CSS was bumped from `9.5pt` to `11pt` bold so the call word ties with the jersey number (`11pt`) as the largest type in the row — the call word now sits at the top of the row hierarchy instead of the bottom. §4.2 of this spec was updated to reflect the locked `11pt` value with rationale.
- **(C) SECOND BASE mockup labeling**: Both Section 3's SECOND BASE card (normal/exceptions-present demo) and Section 4's all-TRUE edge-state card now carry an HTML comment naming the AC-5 state being demonstrated. E-228-05 won't read Section 3's SECOND BASE rendering as the canonical all-TRUE template.

---

## 12. Annotated decisions reference (open questions for calibration, not for v1)

These are NOT blockers for E-228-05/-07. They are documented for the first-real-opponent calibration pass (epic Rollout, operator activity):

- **Row sort** (D5): "flagged-first, then jersey-ascending" is the recommended default. If the first real opponent's call sheet shows that mid-game cross-reference (jersey-first) is more important than pre-game prep, the sort can flip to pure jersey-ascending without a schema change.
- **Per-position column order** (D2): "LF · CF · RF · 3B · SS · 2B" is the recommended default. The pull-side-vs-oppo-side alternative is documented in §3.3 for future consideration.
- **Cards-per-sheet** (D3): 2×3 portrait = 6 cards = 1 sheet is locked for v1. A utility-variant rollout (§4.6) may rework the grid to mix card sizes, but that's a future iteration.
- **Deviation magnitude** (D4): explicitly NOT in v1 per the locked decision. A calibration pass that identifies a real need surfaces this as a future iteration with its own AC contract.
