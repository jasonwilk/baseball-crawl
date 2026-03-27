# E-166: Enhanced Spray Charts

## Status
`COMPLETED`

## Overview
Enhance the spray chart system with two improvements: (1) differentiate ball-in-play types using marker shapes so coaches can read contact quality (ground ball vs. line drive vs. fly ball vs. popup) at a glance alongside hit/out outcomes, and (2) replace the current "open in new tab" pattern with a mobile-friendly modal overlay for enlarging spray chart images without leaving the page.

## Background & Context
The spray chart renderer (`src/charts/spray.py`) currently draws all BIP events as circles, colored green (hit) or red (out). The `play_type` column exists in the `spray_charts` table with values like `ground_ball`, `line_drive`, `fly_ball`, and `popup`, but the DB queries in `src/api/db.py` only SELECT `x, y, play_result` — the play type data is stored but never surfaced downstream.

On the opponent detail page, per-player "View spray" links open the PNG in a new browser tab (`target="_blank"`), which is a poor mobile experience (new tab, no context, pinch-to-zoom required). Embedded spray chart images (team spray in opponent detail, player spray in player profile) have no enlarge affordance at all.

UX designer delivered a complete design spec covering marker shape assignments, legend layout, modal HTML/Tailwind structure, and mobile/desktop considerations. No expert consultation required beyond UX (this is a pure rendering + frontend epic with no schema changes, no API calls, no coaching domain questions).

## Goals
- Spray chart images differentiate BIP events by play type (4 shapes) while preserving hit/out color coding
- Two-row legend communicates both dimensions: outcome (color) and contact type (shape)
- All embedded and linked spray charts open in a modal overlay instead of a new tab
- Modal works well on mobile (touch dismiss, scroll lock, proper positioning)

## Non-Goals
- Heat map / density visualization (IDEA-050)
- Fielder position labels on spray charts (IDEA-048)
- Pull/center/oppo tendency summaries (IDEA-049)
- Title enhancements with stats (IDEA-051)
- Changes to the print template (`opponent_print.html`) — it has its own layout concerns
- Changes to spray chart data pipeline or schema

## Success Criteria
- Coaches can distinguish ground balls, line drives, fly balls, and popups on any spray chart PNG
- On mobile, tapping any spray chart image opens a full-screen modal overlay that is dismissible without navigating away
- No regression in existing spray chart rendering (coordinate transforms, HR bubbles, hit/out classification)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-166-01 | Play type marker shapes and legend | DONE | None | - |
| E-166-02 | Modal spray chart viewer | DONE | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Play Type Marker Shape Mapping

| `play_type` value | Marker | matplotlib marker code |
|-------------------|--------|----------------------|
| `ground_ball` / `hard_ground_ball` / `bunt` | Circle | `'o'` |
| `line_drive` / `hard_line_drive` | Triangle up | `'^'` |
| `fly_ball` | Diamond | `'D'` |
| `popup` / `pop_fly` / `pop_up` | Square | `'s'` |
| `NULL`, `other`, or unknown | Circle (fallback) | `'o'` |

Ground balls (including `hard_ground_ball`) and `bunt` use circle as the default/most common shape — bunts are ground-level contact. The API uses three spellings for popup-type plays (`popup`, `pop_fly`, `pop_up`) across different endpoints; all map to square. `hard_line_drive` maps to the same triangle as `line_drive`. `other`, `NULL`, and any unrecognized `play_type` value fall back to circle.

**Note**: The `playType` enum is open (API docs across endpoints show: `ground_ball`, `hard_ground_ball`, `line_drive`, `hard_line_drive`, `fly_ball`, `popup`, `pop_fly`, `pop_up`, `bunt`, `other`). The loader stores raw values unchanged. The renderer must handle any value not in this table via the circle fallback.

### TN-2: Color Scheme (Unchanged)

Hit/out color coding is unchanged from the current implementation:
- Hit: fill `#00D682`, stroke `#009B4D`
- Out: fill `#B90018`, stroke `#61000D`

Shape encodes contact type; color encodes outcome. These are orthogonal dimensions.

### TN-3: Two-Row Legend Layout (matplotlib)

The legend is rendered inside the matplotlib PNG (not as HTML) so the legend is embedded in the image file itself and appears wherever the PNG is viewed (download, share, print template, future contexts).

- **Row 1 — Outcome**: Green circle "Hit", Red circle "Out"
- **Row 2 — Play Type**: Gray circle "Ground Ball", Gray triangle "Line Drive", Gray diamond "Fly Ball", Gray square "Popup"

Row 2 uses a neutral gray color (no hit/out coloring) to avoid a confusing color+shape matrix. The legend should be compact and positioned at the bottom of the chart.

**Implementation note**: Two-row legend in matplotlib is non-trivial — it requires either two separate legend objects (one via `ax.legend()`, one via `ax.add_artist()`) or a separator handle approach with `ncols`. This is ~10 lines of work beyond the current single-row `ax.legend()` call.

### TN-4: Renderer Migration from Circle Patches to Scatter

The current renderer uses `plt.Circle()` patches for each event. To support marker shapes, the renderer should migrate to `ax.scatter()` calls grouped by (play_type, play_result) combination. This allows setting `marker=` per group while maintaining the existing z-order (outs rendered before hits).

Marker size should be large enough to distinguish shapes at mobile display widths (~375px). Edge stroke: thin outline for visual separation of overlapping markers.

### TN-5: DB Query Changes

Both `get_player_spray_events()` and `get_team_spray_events()` in `src/api/db.py` must add `play_type` to the SELECT clause. The renderer must handle `play_type=NULL` gracefully (fall back to circle marker).

### TN-6: Modal HTML/JS Structure

One modal instance per page, reused for any chart on that page. Vanilla JS, no external libraries.

**Trigger pattern**: Wrap `<img>` in a `<button type="button">` with `cursor-zoom-in`, `data-src` attribute, and `onclick` handler. Replaces the current `<a target="_blank">View spray</a>` links.

**Modal structure**: `fixed inset-0 z-50` overlay with `bg-black/75` backdrop. Inner container: `max-w-2xl w-full`, white background, rounded corners. Close button (×) in top-right corner.

**Dismiss behaviors**: Click/tap outside chart area, Escape key, explicit close button. The inner container div must call `event.stopPropagation()` via its own `onclick` handler to prevent chart-image clicks from bubbling to the overlay's close handler — without this, clicking the chart image itself would dismiss the modal.

**Scroll lock**: Set `document.body.style.overflow = 'hidden'` on open, restore on close.

**Mobile layout**: `items-start pt-8` (top-aligned with padding for notch/status bar). Desktop: `md:items-center` (vertically centered).

**Accessibility**: `role="dialog"`, `aria-modal="true"`, `aria-label="Close"` on the close button. For image-wrapped trigger buttons (no visible text), use `aria-label="Enlarge spray chart"`. For text trigger buttons (e.g., "View spray"), the visible text serves as the accessible name — do not add `aria-label` (it would override the visible text for screen readers).

**Touch target**: The close button (×) must meet the 44px minimum touch target size for mobile usability.

### TN-7: Modal Placement

The modal HTML and JS should be placed in a `{% block scripts %}` added to `base.html` (just before `</body>`). Templates that need the modal override this block to include the modal markup and JS. This keeps the modal code out of templates that don't need it while avoiding duplication.

Pages requiring modal integration:
- `opponent_detail.html` — "View spray" buttons in batting table + team spray chart image
- `player_profile.html` — embedded player spray chart image

Pages NOT requiring modal integration:
- `opponent_print.html` — print layout, no interactive elements, does not extend base.html

### TN-8: Opponent Detail "View Spray" Link Replacement

The current pattern in `opponent_detail.html`:
```html
<a href="/dashboard/charts/spray/player/{{ player.player_id }}.png?season_id={{ season_id }}"
   class="ml-1 text-xs text-blue-600 underline whitespace-nowrap"
   target="_blank">View spray</a>
```

Replace with a button that opens the modal (no `aria-label` needed — visible text "View spray" serves as the accessible name):
```html
<button type="button"
   class="ml-1 text-xs text-blue-600 underline whitespace-nowrap cursor-zoom-in"
   onclick="openChartModal(this.dataset.src)"
   data-src="/dashboard/charts/spray/player/{{ player.player_id }}.png?season_id={{ season_id }}">View spray</button>
```

For embedded `<img>` elements (team spray chart, player profile spray chart), wrap the image in a similar button element with `aria-label="Enlarge spray chart"` (required since there is no visible text).

## Open Questions
None — design spec is complete and implementation path is clear.

## History
- 2026-03-27: Created. UX designer provided full design spec. SE confirmed play_type is in DB but not queried downstream.
- 2026-03-27: READY after 4-round review process.
- 2026-03-27: COMPLETED. Both stories delivered: play type marker shapes with two-row legend (E-166-01) and modal spray chart viewer (E-166-02). All 19 ACs verified. 5 code review findings across 4 review passes (3 accepted, 2 dismissed).

### Spec Review Scorecard

| Round | Source | Findings | Accepted | Dismissed |
|-------|--------|----------|----------|-----------|
| Internal iteration 1 | Holistic team (PM + UX + SE) | 7 | 7 | 0 |
| Internal iteration 1 | CR spec audit | 3 | 2 | 1 |
| Codex iteration 1 | Codex spec review | 3 | 2 | 1 |
| Codex iteration 2 | Codex spec review | 4 | 2 | 2 |
| **Totals** | | **17** | **13** | **4** |

**Dismissed findings (with reasons):**
- CR-1: Prescribing test approach (Jinja2 render assertions) crosses Technical Delegation Boundary; addressed by F7 testing scope note.
- P2: Duplicate of CR-1; already addressed by F7 testing scope note.
- C2-1: Third appearance of same finding (CR-1 → P2 → C2-1); already addressed.
- C2-4: AC-4's four clauses form a cohesive logical group (dismiss behaviors); scroll lock already extracted to AC-11 in iteration 1.

### Code Review Scorecard

| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-166-01 | 2 | 2 | 0 |
| Per-story CR -- E-166-02 | 0 | 0 | 0 |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 3 | 1 | 2 |
| **Total** | **5** | **3** | **2** |

**Per-story CR E-166-01**: 2 SHOULD FIX — dead `mpatches` import removed, test scope confirmed. Both accepted and fixed.
**Per-story CR E-166-02**: APPROVED, no findings.
**CR integration review**: APPROVED, clean.
**Codex code review**: Finding 1 (broken mock tests) accepted and remediated. Finding 2 (missing dashboard tests for modal) dismissed — addressed by F7 planning finding (modal JS is manual verification per story Notes). Finding 3 (XSS in data-src) dismissed — URL assignment via `dataset` property, not JS `eval`; Jinja2 autoescaping sufficient.

### Documentation Assessment
No documentation update triggers fire — no new endpoints, no architecture changes, no schema changes, no new agents, no deployment changes. This is a rendering enhancement and frontend UX improvement within existing surfaces.

### Context-Layer Assessment

1. **New convention, pattern, or constraint established**: No. The `{% block scripts %}` pattern in `base.html` and the modal reuse pattern are standard Jinja2/Tailwind practices, not project-specific conventions requiring codification.
2. **Architectural decision with ongoing implications**: No. Scatter-based rendering and modal overlay are implementation details within existing architecture. No new services, data flows, or integration patterns.
3. **Footgun, failure mode, or boundary discovered**: No. No gotchas or operational boundaries discovered.
4. **Change to agent behavior, routing, or coordination**: No. No agent changes.
5. **Domain knowledge discovered that should influence agent decisions**: No. The play_type enum values were already documented in API endpoint docs; the marker shape mapping is implementation detail in the renderer code.
6. **New CLI command, workflow, or operational procedure introduced**: No. No new commands, scripts, or workflows.

All six triggers: **No**. No context-layer codification required.

### Ideas Backlog Review
Spray chart ideas (IDEA-048 through IDEA-051) remain CANDIDATE — none are unblocked or promoted by E-166. E-166 enhances the existing renderer but does not change the data pipeline or schema, so these ideas' blockers are unchanged.
