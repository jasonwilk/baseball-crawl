# E-230: Positioning Section Refactor (Scouting Reports)

## Status
`READY`

## Overview

Replace the scouting report's embedded positioning section with purpose-built matplotlib PNG charts that mirror the spray chart pattern. HTML owns all headers; charts are pure pixels. Two sections paired in the report: Spray Charts first (offense observation), Defensive Positioning second (defense prescription).

## Background & Context

E-228 shipped the standalone quarter-letter positioning bundle. E-229 rewrote the engine for team-aggregate centroids and re-rendered the bundle. Both shipped clean. The same SVG card renderer (`src/reports/positioning_card.py::render_field_svg`) was also wired INTO the scouting report at `src/api/templates/reports/positioning_cards.html` (included from `scouting_report.html:799`) so the same `Defensive Positioning` data appears inside the primary coaching surface.

User dev validation on the combined E-228 + E-229 branch surfaced two real bugs in that embedded path:

1. **Duplicate-header**: `render_field_svg()` bakes opponent name + coverage cue + position label INSIDE the SVG (designed for the standalone print card). The scouting report template ALSO renders an outer `<div class="positioning-card-header">` with the same three fields. Visible duplication.
2. **Pill collision**: The SVG is dimensioned for 4.25"×5.5" quarter-letter print geometry. Embedded smaller in the report HTML, outlier pills overlap and clip.

Root cause: one renderer trying to serve two surfaces with incompatible geometry. The standalone bundle path is shipped and validated; the embedded path needs its own purpose-built rendering surface.

The scouting report is the user's primary coaching tool (load-bearing user quote: *"I have ONLY been using the standalone reports. I've used no other system features because the reports serve all of my needs."*). Fixing the embedded section IS the deliverable.

This epic lands on top of `epic/E-228-defensive-positioning-cards` (which already contains E-229 + bundle/scouting-report fixes); merge to main is a separate later decision the user makes after dev-validating the combined E-228 + E-229 + E-230 stack. See TN-1.

**No expert consultation gap.** SE consulted on chart-module feasibility (PNG-bytes contract, seam, data shape, image transport, test seams). UXD consulted on layout parity, sizing, headers, coverage-cue symmetry, zero-coverage state. Both consultations converged in one round with explicit pushback discipline. No data-engineer consultation needed — schema and queries are LOCKED untouched. No baseball-coach consultation needed — vocabulary, thresholds, and tier definitions are LOCKED from E-228/E-229.

## Goals

- Eliminate the duplicate-header and pill-collision bugs in the embedded positioning section by making the chart structurally incapable of carrying headers.
- Pair the offense (spray — H2 text `Batter Tendencies` preserved as-is) and defense (positioning — H2 text `Defensive Positioning`) sections in the scouting report so the coaching narrative reads `observation → prescription`, with symmetric coverage cues.
- Establish `src/charts/positioning.py` as a sibling to `src/charts/spray.py`: PNG-bytes contract, render-layer-only, no engine or schema touch.

## Non-Goals

- Bundle deprecation. `src/reports/positioning_card.py` + `src/reports/positioning_bundle.py` + the quarter-letter card output preserve content-level parity (per Story 2 AC-9). The bundle path remains the standalone print artifact.
- New positioning data, schema changes, query changes. The four existing query helpers in `src/reports/positioning_card.py` cover all reads.
- Dashboard changes. This is reports-flow only.
- Pre-existing 40 test failures in `test_report_renderer.py`. Separate planning prompt; out of scope.
- Restructuring perspective-resolution logic. Use existing `_choose_perspective_team_id`.
- New vocabulary, new compass zones, new tier thresholds. TN-3 / TN-15 from E-229 are LOCKED.
- New presentation surfaces (per-card BIP chip, per-position contact mix, "Batter Tendencies" rename — UXD §11 deferrals respected).

## Success Criteria

- A scouting report regenerated on the E-230 branch shows the Defensive Positioning section with a section-level coverage cue and seven non-duplicate-header charts (1 team-level + 6 per-position), no pill collisions, no overlapping text inside chart pixels.
- The report's section order is `Spray Charts → Defensive Positioning`; both sections carry a `Through {date} · {N} games · {M} BIP` annotation beneath their `<h2>` (per TN-2).
- The standalone positioning bundle at `data/reports/{slug}/index.html` preserves content-level parity with its pre-E-230 output (regression test in Story 2 AC-9 — content-level slot-fill, robust to timestamp drift).
- New chart module's unit tests pass, asserting PNG byte signature + decoded length ≥ 1 KB for both public functions, plus viewport math for all 6 positions.

## Stories

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-230-01 | `src/charts/positioning.py` chart module + unit tests | TODO | None | - |
| E-230-02 | Wire chart module into scouting report; reorder sections; pairing annotation | TODO | E-230-01 | - |

## Dispatch Team

- software-engineer

(No data-engineer — no schema. No claude-architect — no context-layer changes. No ux-designer — visual spec is locked in this DRAFT; UXD-consultation work is complete.)

## Technical Notes

### TN-1: Mandatory Branch Implementation — E-228 + E-229 + E-230 stack, NO AUTO-MERGE AT CLOSURE (forward-port of E-229's TN-1)

**This is a hard requirement carried forward from E-228 TN-9 / E-229 TN-1 and adapted to the three-epic stack. Whoever runs dispatch MUST NOT miss it.**

E-230's implementation builds directly on top of the E-228 branch, which already carries E-229. The sequence is:

1. Dispatch creates the epic worktree branching from the E-228 branch HEAD, not from main: `git worktree add -b epic/E-230 /tmp/.worktrees/baseball-crawl-E-230 epic/E-228-defensive-positioning-cards`. This is an explicit override of the default branch-from-main pattern in `.claude/skills/implement/SKILL.md`.
2. Stories execute in the epic worktree as normal. All `git diff` references during dispatch — including the code-reviewer's diff against base — compare against `epic/E-228-defensive-positioning-cards`, NOT against `main`. Stories' Handoff Context sections must reference the E-228 branch.
3. The closure step pulls the worktree changes back into `epic/E-228-defensive-positioning-cards` (not into `main`). After closure that branch carries: `c0e4fb8 chore(E-228) plan` → `2d6be06 feat(E-228)` → `<E-229 plan>` → `<E-229 closure>` → `<E-230 plan>` → `<E-230 closure>`.
4. The user runs `docker compose up -d --build app` against the combined branch HEAD, exercises the new positioning section against real-opponent data, and validates.
5. **Only after the user's explicit sign-off** does the combined E-228 + E-229 + E-230 stack merge to `main` as one atomic merge. E-228 never merges to main on its own; E-229 never merges to main on its own; E-230 never merges to main on its own.

The user's framing carried forward: *"I'd rather validate the final state once than ship the broken intermediate state and re-validate the fixed state."*

**Operator note for validation.** E-230 has no migration; **do NOT `rm data/app.db`** — it would discard the E-228+E-229 dev-validation state needed to compare the positioning section before/after this change. Validation step: `docker compose up -d --build app` against the combined branch HEAD.

### TN-2: Coverage cue format (symmetric across both sections)

Both Spray Charts and Defensive Positioning sections render a `<div class="sort-annotation">` beneath their `<h2>` with the SAME format:

```
Through {freshness_date_human} · {game_count} games · {team_bip_count} BIP
```

- `{freshness_date_human}` is the existing report freshness date in "Mon Day" form (e.g., `Apr 12`).
- `{game_count}` is the existing report game count.
- `{team_bip_count}` is the canonical opponent BIP count from `team_position_aggregate.bip_count` (the engine writes the SAME value to all 6 position rows per opponent per `.claude/rules/architecture-subsystems.md` "Defensive Positioning Engine"). Read it from any one of the 6 rows for the chosen perspective. **Do NOT compute a fresh `SELECT COUNT(*) FROM spray_charts WHERE ... AND x IS NOT NULL AND y IS NOT NULL` for this annotation** — that would diverge from the bundle's persisted snapshot whenever the opponent has null-coordinate BIPs that the density query filters out. The bundle's per-card BIP caption (`({N} BIP)` from `positioning_card.py::_svg_star` line ~613) already uses `team_position_aggregate.bip_count`; both sections of the scouting report MUST use the same source so a coach holding the printed bundle and the scouting report sees identical BIP numbers for the same opponent.

This format symmetry is the pairing-rationale carrier. Both sections must use this exact format; do not let one drop the BIP or use a different separator.

`freshness_date` and `game_count` are already populated on the `data` dict at `src/reports/generator.py:1404-1405`. `team_bip_count` is extracted from the already-fetched `team_position_aggregate` row (no new query). When `_choose_perspective_team_id` returns `None` (zero-coverage opponent), `team_bip_count` is `0` and the annotation degrades to `Through {date} · 0 games · 0 BIP` per TN-10.

### TN-3: PNG-bytes contract for `src/charts/positioning.py` (mirror `src/charts/spray.py`)

The new chart module returns PNG bytes. The duplicate-header bug is structurally impossible with this contract because the chart returns pure chart pixels; opponent name / position label / coverage cue all live in surrounding HTML.

Public API:
```python
def render_team_position_chart(
    conn: sqlite3.Connection,
    public_id: str,
    season_id: str,
    *,
    perspective_team_id: int,
    title: str | None = None,
    figsize: tuple[float, float] = (6, 4),
) -> bytes:
    ...

def render_position_chart(
    conn: sqlite3.Connection,
    public_id: str,
    season_id: str,
    position: str,
    *,
    perspective_team_id: int,
    title: str | None = None,
    figsize: tuple[float, float] = (2.5, 2),
) -> bytes:
    ...
```

Implementation conventions copied verbatim from `src/charts/spray.py`:
- Module-level `matplotlib.use("Agg")` before pyplot import.
- `title: str | None = None` default; chart adds no title when None (caller decides heading ownership — HTML owns it for E-230's use).
- `dpi=150` PNG via `fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")`.
- Operate entirely in engine 320×480 GC SVG space; no rescale.

Reuses the four existing query helpers in `src/reports/positioning_card.py` (`_query_team_aggregate`, `_query_populated_zones`, `_query_density_points`, `_query_outlier_batters`). No new queries.

### TN-4: Perspective threading (correctness pin)

`perspective_team_id` MUST be derived ONCE at the top of `_build_scouting_report_positioning_payload` via the existing `_choose_perspective_team_id` (already in use at `src/reports/generator.py:1626`) and threaded as the SAME value into all 7 chart calls (1 team-level + 6 per-position).

**Note on `_query_team_aggregate`'s internal chooser**: `_query_team_aggregate(conn, team_id, season_id, position)` does NOT take `perspective_team_id` as a parameter — it applies the same standalone-perspective-preferred rule internally and returns the chosen `perspective_team_id` in its result dict. By construction, the value returned by `_query_team_aggregate` for the same `(team_id, season_id)` equals what `_choose_perspective_team_id` returns. Both are valid sources for the canonical perspective. Whichever source the caller uses, the SAME value MUST thread into `_query_populated_zones`, `_query_density_points`, and `_query_outlier_batters` (those three DO take `perspective_team_id` as a parameter).

Mixing perspectives across the section was finding F3 from E-229's pre-closure review. The render layer must NOT re-derive perspective per-chart.

### TN-5: Per-position viewport constants

Module-level constant in `src/charts/positioning.py`:
```python
POSITION_VIEWPORTS: dict[str, tuple[float, float, float, float]] = {
    "LF": (..., ..., ..., ...),
    "CF": (..., ..., ..., ...),
    "RF": (..., ..., ..., ...),
    "3B": (..., ..., ..., ...),
    "SS": (..., ..., ..., ...),
    "2B": (..., ..., ..., ...),
}
```

Each tuple is `(xmin, xmax, ymin_bottom, ymax_top)` in engine 320×480 SVG space. The viewport is a ±60-px box around each position's `BASE_POSITIONS[position]` anchor (already imported from `src.reports.positioning`).

Y-axis inversion convention follows `src/charts/spray.py`: SVG `y=0` is at deep CF; `ax.set_ylim(ymin_bottom, ymax_top)` with `ymin_bottom > ymax_top` flips the y-axis correctly. Viewport unit tests assert: `xmin < xmax`, `ymin_bottom > ymax_top` (inversion preserved), and `BASE_POSITIONS[position]` falls inside the viewport rectangle.

The same `_FIELD_PATH_D` boundary path used by `src/charts/spray.py` is drawn on each chart; matplotlib's axis limits clip the path automatically — no per-position re-derivation of field geometry.

### TN-6: `chart_mode` flag on `positioning_cards.html` partial

The same partial serves two callers with different rendering needs:

| Caller | `chart_mode` value | Per-card slot renders |
|--------|-------------------|----------------------|
| `src/reports/positioning_bundle.py::generate_positioning_bundle` (standalone print artifact) | `'svg'` | `{{ card.svg \| safe }}` — inline SVG from `render_field_svg()` (unchanged from E-229) |
| `src/reports/generator.py::_build_scouting_report_positioning_payload` (embedded section) | `'image'` | `<img src="{{ card.image_uri }}">` — base64 PNG data URI |

In the `chart_mode='image'` branch, the per-card HTML header (opponent name + coverage cue + position label currently at `positioning_cards.html:330-334, 386-390, 454-458`) is REMOVED — because the section-level HTML header (per TN-2) already carries opponent context and the chart pixels carry no text. Per-card label is the position name only (no categorical call text — option (i) from the UXD vocabulary decision).

The `chart_mode='svg'` branch preserves content-level parity with the current partial structure (verified by Story 2 AC-9). The bundle path receives no behavioral change.

**Plumbing — `chart_mode` lives INSIDE the `positioning` context object that the partial already receives.** Verified shape in current repo: `positioning_bundle.py:820` renders the bundle template with `template.render(positioning=cards_ctx, ...)`; `renderer.py:877` builds a nested `positioning` object that `render_report()` threads in; both parent templates (`positioning_bundle.html:68` and `scouting_report.html:799`) include `positioning_cards.html` with NO arguments. The partial therefore reads context as `positioning.X`, NOT top-level `X`.

To avoid divergent plumbing surfaces:
- **Bundle path**: `cards_ctx["chart_mode"] = "svg"` set inside `_render_cards_template_html` (or wherever `cards_ctx` is assembled before `template.render(positioning=cards_ctx, ...)`).
- **Scouting-report path**: `_build_positioning_context` adds `"chart_mode": "image"` to its returned positioning dict before that dict is threaded into `render_report()`.
- **Partial read**: `{% if positioning.chart_mode | default('svg') == 'image' %}` — reads from the nested `positioning` object with a defensive default. The default keeps the bundle path safe if a future caller forgets to set the flag.

**Do NOT** set `chart_mode` as a top-level template var. **Do NOT** use `{% include "..." with chart_mode='image' %}` from either parent. Both forms break the nested-context contract the partial reads from; the bundle parity test (AC-9) will catch divergence after the fact, but the contract should fail-fast.

### TN-7: Image transport (base64 data URI)

The scouting report is a self-contained HTML file on disk (per `.claude/rules/scouting-data-flows.md`). PNG bytes are base64-encoded and inlined as `data:image/png;base64,...` URIs, mirroring the existing spray-chart pattern at `src/reports/renderer.py:89-99` (used today for both player spray charts at line 817 and team spray chart at line 398).

Do NOT add a `/dashboard/charts/positioning/...` HTTP route. Reports have no serving runtime for image routes; the dashboard does, but the dashboard is out of scope for E-230.

A single encoding helper in `src/reports/renderer.py` is preferred — either a new `_encode_position_chart(bytes) -> str` or a generalized `_encode_png(bytes) -> str` that the existing spray callers also adopt. Implementation choice is SE's call at story time.

### TN-8: Section reorder (page-break verification)

The current scouting report renders positioning at `scouting_report.html:799` and spray at `:802`. Both `{% include %}` lines sit OUTSIDE the `.stats-content` wrapper boundary (which closes at line 793 and reopens at line 836). Swapping the two `{% include %}` blocks reorders the sections without disturbing sibling layout.

The CSS interaction worth verifying once: `.positioning-cards-sheet` has `page-break-after: always`. With positioning now LAST before `.stats-content` reopens for roster (landscape `@page stats-page`), there is a small chance the browser/weasyprint emits a blank landscape page between positioning sheet 2 and roster. If a blank page appears in print preview, the fix is either:

- Remove `page-break-after: always` from the last positioning sheet, OR
- Drop the wrapping `.stats-content` div around roster (roster has no special page styling).

Print-preview verification is a sub-AC of Story 2 (E-230-02 AC-8).

### TN-9: Density background

The density layer behind each chart is `ax.scatter(xs, ys, s=4, c="#000", alpha=0.12)` — same shape as `src/charts/spray.py::_draw_events` with smaller markers and uniform alpha. Source points come from the existing `_query_density_points(conn, team_id, season_id, perspective_team_id)` helper. No new query. Do NOT use `imshow` (rasterizes blurry) or `hexbin` (visually different from what coaches signed off on for the E-229 bundle).

### TN-10: Zero-coverage degradation

When no perspective is available for the opponent (`_choose_perspective_team_id` returns `None`), the entire Defensive Positioning section renders a single whole-section banner: *"Not enough spray data — play your standard alignment."* No charts render; the section-level coverage cue still renders with `0 games · 0 BIP` so the data-depth fact is visible. This matches the UXD-locked zero-coverage state and the Display Philosophy rule of "never suppress, always contextualize."

## Open Questions

None blocking. One implementation-time judgment call flagged for SE during dispatch (not a new decision):

1. `_encode_position_chart` vs generalized `_encode_png(bytes)` in `src/reports/renderer.py` — both work; SE picks at story time.

(Originally OQ-2 was `chart_mode` plumbing as "SE's call." SE's Phase 3 review (F3) revealed the two callers use different invocation surfaces — `{% include %}` vs context-dict — and mixing them creates a parity-test failure mode. TN-6 now mandates context-dict-only for both callers; no longer an open question.)

## History

- 2026-05-19: Created (DRAFT). Phase 1 discovery: SE consulted on chart-module feasibility + section-reorder mechanics; UXD consulted on visual spec + pairing chrome. UXD spec drift on retired E-228 categorical vocabulary corrected to option (i): per-card label = position name only. Two-story decomposition locked.
- 2026-05-19: Phase 3 review incorporation. CR (1 finding), UXD (4 findings), SE (6 findings) reviewed DRAFT in parallel. 9 accepted as spec-defects, 2 dismissed (1 UXD self-acknowledged polish, 1 incorporation-defect that would have added preempt-CR-bloat TN). Edits: CR F1 (TN-8 AC-7→AC-8); UXD F-2 (Team alignment caption restored in story 2 AC-6+AC-11); UXD F-4 (epic Goals naming parenthetical); SE F1 (`_query_team_aggregate` signature correction in story 1 + TN-4 amendment); SE F2 (TN-2 BIP-count source = `team_position_aggregate.bip_count` for bundle/section consistency, no new COUNT query); SE F3 (TN-6 mandates context-dict-only for chart_mode); SE F4 (AC-9 reframed as content-level slot-fill, not byte-equality); SE F5 (story 1 steers import-from-spray for field-drawing primitives); SE F6 (TN-1 operator note trimmed). OQ-2 closed.
- 2026-05-19: Phase 4 Codex spec review incorporation. Codex returned 4 findings (2 P1, 2 P2); all 4 accepted as spec-defects, 0 dismissed, 0 incorporation-defects. Edits: CX1 (story 2 AC-11 slot-fill extended to verify all 6 position-name labels); CX2 (story 2 AC-1 qualified with explicit zero-coverage short-circuit before threading); CX3 (TN-6 + AC-4 + Technical Approach steps 1+2 specify `chart_mode` lives INSIDE the nested `positioning` context object — `positioning.chart_mode` in partial, `cards_ctx["chart_mode"]` on bundle, `_build_positioning_context` adds it on scouting-report path); CX4 (consistency-sweep miss — all 4 instances of `byte-identical` / `byte-for-byte` wording replaced with content-level parity language across epic.md:35, :47, :174 and story 2:11, :61). Broader consistency sweep run with wider regex (`byte.identical|byte.for.byte|byte.equality|chart_mode|positioning\.chart_mode|AC-7|AC-8|AC-9|AC-10|AC-11|...`); clean.
- 2026-05-19: **Status → READY.** Quality checklist passed: testable ACs, vertical-slice stories, file dependencies declared, expert consultations complete, scope ceiling held. Awaiting user authorization before dispatch per `.claude/rules/workflow-discipline.md` Dispatch Authorization Gate — planning and dispatch are separate actions; user reviews the READY epic before any worktree creation. Closure target per TN-1 is `epic/E-228-defensive-positioning-cards`, NOT main.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 1 | 1 | 0 |
| Internal iteration 1 — Holistic team review (SE + UXD) | 10 | 8 | 2 |
| Codex iteration 1 | 4 | 4 | 0 |
| **Total** | **15** | **13** | **2** |

Both dismissals are from UXD's holistic review and were sound per triage discipline: UXD F-1 was self-acknowledged optional polish ("no fix needed"); UXD F-3 was an incorporation-defect that would have added a preempt-CR-bloat TN already covered by existing AC chain (E-230-01 AC-4 + AC-5 + AC-8). Zero incorporation-defects accepted across all 3 review passes. No Codex iter-2 run per user brief ("spec review when done. And then codex spec review" — singular one Codex pass).
