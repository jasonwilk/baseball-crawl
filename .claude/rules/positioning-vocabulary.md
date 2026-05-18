---
paths:
  - "src/reports/positioning*.py"
  - "src/reports/renderer.py"
  - "src/charts/spray.py"
  - "src/api/routes/dashboard.py"
  - "src/api/routes/reports.py"
  - "tests/test_positioning*.py"
  - "tests/test_report_*.py"
  - "migrations/*positioning*.sql"
---

# Positioning Vocabulary and Coord Conventions

Bounded domain knowledge for the defensive positioning subsystem (E-228 + E-229). Loads only when an agent touches positioning code or its render surfaces. The canonical render-layout source of truth is `.project/research/E-229-locked-layout-constants.md` (LOCKED v1.2); this rule covers the vocabulary, coord conventions, and tier semantics that need to be in head before opening any positioning file.

## 8-Zone Compass (A-H)

The team-aggregate star is the per-opponent default per fielder (one star per `(team_id, season_id, perspective_team_id, position)` row in `team_position_aggregate`). Per-batter outliers carry a zone letter A-H or NULL (NULL = batter sits AT the star, no zone label).

Zone letters are determined by `(sign(direction_deviation), sign(depth_deviation))` only — magnitudes are IGNORED for letter assignment (magnitude is communicated by the pill's spatial position on the field).

**Sign convention**: `direction_dev < 0` = left (toward LF); `direction_dev > 0` = right (toward RF). `depth_dev < 0` = in (toward home plate); `depth_dev > 0` = deep (toward CF wall).

| `sign(direction)` | `sign(depth)` | Zone | Plain English          |
|-------------------|---------------|------|------------------------|
| neg               | neg           | A    | in + left              |
| neg               | 0             | B    | left                   |
| neg               | pos           | C    | deep + left            |
| 0                 | neg           | D    | in (centered)          |
| 0                 | 0             | NULL | star (no zone label)   |
| 0                 | pos           | E    | deep (centered)        |
| pos               | neg           | F    | in + right             |
| pos               | 0             | G    | right                  |
| pos               | pos           | H    | deep + right           |

**The letter ordering is a label, not a mnemonic.** It is NOT clockwise, NOT grid-mapped. Optimized for the recognition task (fielder sees a card with zone letters at fixed angular positions; the card is doing the heavy lifting). A coach memorizing the compass without the card in front of them is not the intended workflow.

Source: `src/reports/positioning.py::_ZONE_SIGN_TABLE`.

## Axis Vocabulary

Coach-locked: "in / deep" — not "shallow / deep". "In" is shorter and more dugout-natural ("bring it in", "play them in"). All legends, all rendered surfaces, all template strings use "in / deep" verbatim. Do NOT substitute "shallow" anywhere a fielder or coach will read it.

## SVG Coord Convention (CRITICAL — inverted from typical screen coords)

The field SVG uses **GameChanger canonical** coord space: **y=0 is at deep CF (top of canvas); y increases toward home plate (bottom).** x=0 is at the left foul line; x increases toward the right foul line.

This is INVERTED from typical screen coords (which have y=0 at top of viewport and y increases downward — coincidentally the same direction here but anchored to a different field landmark). It is also inverted from typical math/plot coords (where positive y is up).

Reference: `src/charts/spray.py:47` (anchor-point comment) and `src/charts/spray.py:480` (ylim inversion in renderer).

**Engine output → SVG offset projection** (relative to star):
```
x_offset =  direction_dev * scale_x
y_offset = -depth_dev * scale_y     # the negation is the y-axis convention adjustment
```

The `-` on `depth_dev` is the canonical y-axis convention adjustment. **It is NOT a bug; do not "fix" it.** A pill with `depth_dev > 0` (deep — toward CF wall) gets `y_offset < 0` (smaller SVG y — toward deep CF at top of canvas). The negation reconciles "depth grows toward CF" (positive in engine semantics) with "y grows toward home plate" (positive in canvas semantics).

**Coord-space rescaling** (engine 320×480 → per-card viewBox 200×320) is FIELD-ANCHORED, not pure-scalar. The field outline does NOT fill the per-card viewBox edge-to-edge (top 80 card-y units are header space; bottom 15 are legend space). Mapping:

```
card_x = 10 + (x_engine / 320) * 180
card_y = 80 + (y_engine / 295) * 225
```

Engine LF foul corner (0, 0) → card (10, 80); engine home plate (160, 295) → card (100, 305); engine RF foul corner (320, 0) → card (190, 80). The pure-scalar mapping (v1.1 of the locked-constants artifact) was geometrically wrong and was caught by SE during E-229-03 — see `src/reports/positioning_card.py::_engine_to_card_xy` for the canonical implementation.

## Coverage Tiers

Sample-size thresholds drive what the render layer shows. Computed at engine time and persisted to `team_position_aggregate.is_low_confidence` and `bip_count`. The engine writes the SAME `bip_count` to all 6 position rows per atomic write — opponent-level coverage, not per-position coverage.

| Tier | BIP count | `is_low_confidence` | Visual state                                                                   |
|------|-----------|---------------------|--------------------------------------------------------------------------------|
| Zero | 0–14      | 1                   | NO star rendered; "Not enough spray data — play your standard alignment" msg   |
| Thin | 15–49     | 1                   | Star with thin-data badge (dashed ring + `(~N BIP)` caption); no density bg    |
| Full | 50+       | 0                   | Star solid with `(N BIP)` caption; outliers + 12%-opacity density bg rendered  |

The 15 / 50 BIP boundaries are coach-calibrated (15 ≈ 1 full HS game; 50 ≈ 3–4 games). Zero-coverage state does NOT fall back to textbook `BASE_POSITIONS` for the star — that would re-introduce the E-228 reference-frame bug for first-time opponents.

## Vocabulary Constants (Render-Layer-Owned)

Legend strings and tier copy live in render-layer module constants, never inlined by templates and never owned by the engine module:

- `COMPASS_LEGEND_SHORT` (per-card): `★ default · ○ textbook · A-H outliers`
- `COMPASS_LEGEND_LONG` (call sheet, prep page): `A in-left · B left · C deep-left · D in · E deep · F in-right · G right · H deep-right · · = team default`
- `format_coverage_cue(through_date, game_count) -> str` returns the locked `Through {Mon Day} ({N} games)` format string.

Source modules: `src/reports/positioning_card.py` (and shared imports from sibling positioning modules). Per the Vocabulary Ownership Split rule in `architecture-subsystems.md`: engine carries no display words.

## What NOT to Look For

The categorical positioning vocabulary from E-228 (SHADE LEFT / MIXED / LEFT_SHALLOW / per-position glyphs / `call_state` / `team_state_call` / `direction_shade` / `depth_shade` / `zone_concentration` / `POSITIONING_CALL_WORDS`) was retired wholesale in E-229. If a search hits one of these in a comment, it is historical; in code, it is a regression. Reference the epic E-229 TN-13 "What E-228's engine retires (inventory)" if in doubt.
