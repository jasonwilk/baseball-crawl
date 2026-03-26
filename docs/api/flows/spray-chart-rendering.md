# Spray Chart Rendering — End-to-End Reference

This document describes how GameChanger spray chart data works from API response to rendered image. It is the definitive implementation reference for E-158.

**Spike basis:** Research conducted 2026-03-09 through 2026-03-11. Coordinate system calibrated from proxy analysis of 17,700+ defender position events (session `2026-03-11_034739`). Field geometry and rendering logic extracted from `gamechanger-sabertooth-Bfa6tgrf.js` (session `2026-03-11_032625`). Working spike code lives in `.project/research/spray-chart-spike/`.

---

## 1. Data Endpoints

Two endpoints provide spray chart data, serving different access patterns.

### Per-Game: All Players, One Call

```
GET /teams/{team_id}/schedule/events/{event_id}/player-stats
```

| Profile | Accept Header |
|---|---|
| Web | `application/json, text/plain, */*` |
| Mobile | `application/vnd.gc.com.player_game_stats+json; version=0.2.0` |

**Auth required.** Uses `gc-token` + `gc-device-id` headers.

Response structure:

```json
{
  "spray_chart_data": {
    "offense": {
      "<player_uuid>": [ ...spray_entries... ],
      "<player_uuid>": [ ...spray_entries... ]
    },
    "defense": {
      "<player_uuid>": [ ...spray_entries... ]
    }
  }
}
```

`offense` and `defense` are dicts keyed by player UUID. Each value is an array of spray chart entries (see Section 2).

**Works for both own teams and opponents.** Pass the opponent's `progenitor_team_id` as `team_id` — confirmed working 2026-03-09. This is the efficient path: both teams' all players in a single API call.

`event_id` is the boxscore path parameter from game-summaries (not `game_stream_id` — see CLAUDE.md Data Model note on this distinction).

---

### Per-Player Season: One Player, Full Season

```
GET /teams/{team_id}/players/{player_id}/stats
Accept: application/vnd.gc.com.player_stats:list+json; version=0.0.0
```

**Auth required.**

Response is a list of per-game stat records. Each record contains:

| Field | Type | Coverage |
|---|---|---|
| `offensive_spray_charts` | array or null | ~93% present |
| `defensive_spray_charts` | array or null | ~16% present |

The low defensive coverage rate is expected — defensive spray charts are only recorded when a fielder is credited in a play.

This endpoint is what GC's web player profile page uses (confirmed from proxy session `2026-03-11_032625`). Use it when you need a single player's full season view without fetching every game's player-stats.

**Note:** Coordinate scale is assumed identical to the per-game endpoint but has not been cross-verified.

---

## 2. Spray Chart Entry Structure

Each entry in either endpoint follows this shape:

```json
{
  "id": "<uuid>",
  "code": "ball_in_play",
  "compactorAttributes": {"stream": "main"},
  "attributes": {
    "playResult": "single",
    "playType": "hard_ground_ball",
    "hrLocation": null,
    "defenders": [
      {
        "error": false,
        "position": "CF",
        "location": {"x": 129.06, "y": 79.08}
      }
    ]
  },
  "createdAt": 1752607496602
}
```

Key fields:

| Field | Notes |
|---|---|
| `attributes.playResult` | Hit/out classification value (see Section 3) |
| `attributes.playType` | Ball contact description (e.g., `hard_ground_ball`, `line_drive`, `fly_ball`) |
| `attributes.hrLocation` | Zone for non-in-the-park HRs: `"left_field"`, `"center_field"`, `"right_field"`, `"in_the_park"`, or `null` |
| `attributes.defenders[].location` | Raw API coordinates — apply transform (Section 4) before rendering |
| `attributes.defenders[].position` | Fielder position string (e.g., `"CF"`, `"1B"`, `"SS"`) |
| `attributes.defenders[].error` | Whether the play was scored an error |
| `createdAt` | Unix timestamp in milliseconds |

A single at-bat may produce multiple defender entries if multiple fielders were involved in the play.

---

## 3. Play Result Enum

Full set of observed `playResult` values:

**Hits** (render green in GC):
- `single`
- `double`
- `triple`
- `home_run`
- `dropped_third_strike`

**Outs** (render red in GC):
- `batter_out`
- `batter_out_advance_runners`
- `fielders_choice`
- `error`
- `sac_fly`
- `other_out`
- `offensive_interference`
- `sacrifice_bunt_error`
- `sacrifice_fly_error`

GC's classification function (`zre()` in the bundle) treats the five hit values as hits and everything else as outs. This is a binary split — there is no intermediate category.

---

## 4. Coordinate System

Raw API coordinates (`location.x`, `location.y`) must be transformed before rendering. GC uses an SVG with a 320×480 viewBox where y=0 is at the top (center field) and y increases toward home plate.

### Two-Anchor Linear Transform

Extracted verbatim from the GC JS bundle:

```
svgX = 49.189 + rawX × 0.6926
svgY = 104.158 + rawY × 0.6447
```

In code:

```python
X_SCALE  = (160 - 211.25) / (160 - 234)   # 0.6926
Y_SCALE  = (295 - 246)    / (296 - 220)    # 0.6447
X_OFFSET = 160 - 160 * X_SCALE             # 49.189
Y_OFFSET = 295 - 296 * Y_SCALE             # 104.158

def raw_to_svg(x: float, y: float) -> tuple[float, float]:
    return X_OFFSET + x * X_SCALE, Y_OFFSET + y * Y_SCALE
```

### Derivation

Two anchor points tie raw coords to known SVG positions:

| Anchor | Raw (x, y) | SVG (x, y) |
|---|---|---|
| Home plate | (160, 296) | (160.0, 295.0) |
| First base area | (234, 220) | (211.25, 246.0) |

From these:
- x scale = (160 − 211.25) / (160 − 234) = **0.6926**
- y scale = (295 − 246) / (296 − 220) = **0.6447**
- x offset = 160 − 160 × 0.6926 = **49.189**
- y offset = 295 − 296 × 0.6447 = **104.158**

### Field Landmark Reference

| Landmark | Raw (x, y) | SVG (x, y) |
|---|---|---|
| Home plate | (160, 296) | (160, 295) |
| Pitcher's mound | (160, 214) | (160, 242) |
| 2nd base | (160, 150) | (160, 201) |
| 1st base area | (234, 220) | (211, 246) |
| 3rd base area | (86, 220) | (109, 246) |
| Deep center field | (160, 0) | (160, 104) |

**Out-of-bounds default:** Raw (-200, 200) renders off-field. GC uses this as a sentinel for plays with no meaningful field location.

**Scale:** ~1.9 raw units per foot, derived from pitcher-to-catcher distance (115.6 raw units / 60.5 ft).

---

## 5. GC Rendering Approach

Reverse-engineered from the gamechanger-sabertooth JS bundle (session `2026-03-11_032625`).

### Rendering Method

SVG, not canvas. React component `_pe` returns a 320×480 SVG element.

### Hit/Out Classification

GC's `zre()` function:

```python
HIT_RESULTS = {"single", "double", "triple", "home_run", "dropped_third_strike"}

def classify(play_result: str | None) -> str:
    return "hit" if play_result in HIT_RESULTS else "out"
```

### Colors (Exact Hex from Bundle)

| Type | Fill | Stroke |
|---|---|---|
| Hit | `#00D682` | `#009B4D` |
| Out | `#B90018` | `#61000D` |
| Field lines | `#667C8C` | — |
| Bases | `#9DB2C4` | — |

### Dot Specifications

- `<circle r="4">`, `strokeWidth=1.143`
- Rendering order: **outs drawn first, hits drawn second** → hits appear on top when dots overlap

### Home Run Bubbles

Non-in-the-park home runs are excluded from the dot layer. Instead, GC counts HRs by zone (left/center/right field) and renders a bubble at fixed SVG positions:

| Zone | SVG (x, y) |
|---|---|
| Left | (30, 70) |
| Center | (160, 25) |
| Right | (290, 70) |

Bubble: green circle, `r=12`, `ec=#009B4D`, white count text. Only shown when count > 0.

In-the-park HRs (`hrLocation = "in_the_park"` or `null`) fall through to the dot layer and are rendered as normal hit dots.

---

## 6. Field Geometry

SVG path data extracted verbatim from the GC bundle. Already in final SVG coordinate space — no additional transform needed.

### Field Boundary Path

Outfield arc + foul lines + home plate approach:

```
M237.609577,229.299862 C228.432604,194.989366 197.163117,169.724719 160,169.724719
C122.803685,169.724719 91.5115345,195.034524 82.3658827,229.391832
C82.3652227,229.394311 55.2432618,202.321081 1,148.172141
C27.3762229,86.5315996 88.6341713,43 159.999502,43
C231.365829,43 292.622781,86.5315996 319,148.172141
L182.03012,284.895924
C183.325172,287.8707 184.40625,290.533196 184.40625,293.984533
C184.40625,307.446637 173.479,318.359787 159.999502,318.359787
C146.520004,318.359787 135.592754,307.446637 135.592754,293.984533
C135.592754,290.533196 136.675824,287.8707 137.96988,284.895924
L82.3714674,229.397407
```

All field element stroke: `#667C8C`, `strokeWidth: 0.751`.

### Base Polygons (SVG Coordinate Points)

**Home plate:**
```
155.367018 291.902403  155.367018 296.46134  159.897659 301.020277
164.428299 296.46134   164.478766 291.902403
```

**3rd base:**
```
112.383633 246.011583  108.738565 249.658733
105.094234 246.011583  108.738565 242.364434
```

**2nd base:**
```
163.642157 194.690046  159.99709 198.337195
156.352759 194.690046  159.99709 191.042896
```

**1st base:**
```
214.900682 246.011583  211.256351 249.658733
207.611283 246.011583  211.256351 242.364434
```

---

## 7. Python/Matplotlib Replication

The working spike implementation is in `.project/research/spray-chart-spike/render.py`. Key choices:

### Figure Setup

```python
fig, ax = plt.subplots(figsize=(4, 6))  # 4:6 inches = 320:480 SVG proportion
ax.set_facecolor("#FFFFFF")
fig.patch.set_facecolor("#FFFFFF")
ax.set_xlim(0, 320)
ax.set_ylim(480, 0)   # Inverted: SVG y=0 is top (CF), y=480 is bottom
ax.set_aspect("equal")
ax.axis("off")
```

Output: `fig.savefig(path, dpi=150, bbox_inches="tight")`

### SVG Path Parsing

The field boundary path is tokenized and converted to a matplotlib `Path`:

```python
import re
from matplotlib.path import Path as MplPath

def _svg_path(d: str) -> MplPath:
    tokens = re.findall(
        r'[MmCcLlZz]|[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?', d
    )
    verts, codes = [], []
    # M → MOVETO, L → LINETO, C → CURVE4 (×3 per segment), Z → CLOSEPOLY
    ...
    return MplPath(verts, codes)
```

The path supports `M`, `L`, `C`, and `Z` commands. Cubic bezier (`C`) consumes three coordinate pairs per segment and maps to three `CURVE4` codes — this is what renders the outfield arc smoothly.

### Rendering Order

```python
outs = [e for e in events if classify(e.get("play_result")) == "out"]
hits  = [e for e in events if classify(e.get("play_result")) == "hit"]

for ev_list in [outs, hits]:   # outs first, hits on top
    for ev in ev_list:
        sx, sy = raw_to_svg(ev["x"], ev["y"])
        circle = plt.Circle((sx, sy), 4, color=fill, ec=stroke, lw=1.14, zorder=4)
        ax.add_patch(circle)
```

### Dependencies

```
matplotlib
numpy
```

Both are standard data-stack packages. No additional GC-specific dependencies.

---

## 8. What Was Validated in the Spike

| Claim | Evidence |
|---|---|
| Per-game endpoint returns spray data for both teams | Fetched 150 BIP events from 4 Freshman Grizzlies games (own team); opponent data present in same response |
| Opponent access via `progenitor_team_id` | Confirmed 2026-03-09 |
| Coordinate transform matches GC rendering | Fetched 92 BIP events for Reid Wilkinson (#28, Lincoln Rebels 14U, UUID prefix `77c74470`); Python-rendered chart matched GC's player profile chart visually |
| Mobile Accept header works | 206 calls in session `2026-03-11_034739`, all 200 OK |
| Coordinate calibration source | api-scout analysis of 17,700+ defender position events in session `2026-03-11_034739` |
| Field geometry source | Extracted from `gamechanger-sabertooth-Bfa6tgrf.js` (session `2026-03-11_032625`) |

Fetched data (`spray_events.json`) was deleted after the spike per data hygiene. Raw game files were also deleted.

---

## 9. Open Questions / Known Gaps

| Gap | Status |
|---|---|
| Coordinate scale: per-player `stats` endpoint vs. per-game `player-stats` endpoint | Assumed identical, not cross-verified |
| Defensive spray chart coordinates: same transform? | Assumed yes, not explicitly tested |
| Opponent data via per-player `stats` endpoint | Untested; per-game endpoint confirmed working for opponents |
| `hrLocation` full enum | Known values: `null`, `"in_the_park"`, `"left_field"`, `"center_field"`, `"right_field"`. Others may exist. |
| `playType` full enum | Observed values include `hard_ground_ball`, `line_drive`, `fly_ball`, `popup`; not exhaustive |
| Defensive coverage rate variability | ~16% defensive coverage observed for this team/season; may vary by team or recording behavior |

---

*Last verified: 2026-03-11. Spike sessions: `2026-03-11_032625` (JS bundle extraction), `2026-03-11_034739` (coordinate calibration).*
