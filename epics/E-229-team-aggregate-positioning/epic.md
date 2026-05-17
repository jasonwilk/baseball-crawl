# E-229: Team-Aggregate Defensive Positioning

## Status
`READY`

## Overview
E-228's user dev validation surfaced that textbook `BASE_POSITIONS` produces "STRAIGHT UP" defaults that are essentially never right against a real opponent, the per-position responsibility-sector re-evaluation creates a tautology (LF always SHADE LEFT, RF always SHADE RIGHT, CF/2B permanently TRUE), and the categorical text vocabulary (SHADE LEFT, MIXED, per-position glyphs) fails to communicate spatial information to fielders. E-229 reframes positioning recommendations around team-aggregate optimal positions computed from each opponent's batted-ball distribution, and delivers them as visual per-position field diagrams with named compass zones (A–H) for outlier batters.

## Background & Context

**Where E-228 stands.** E-228 (Defensive Positioning Pocket Cards) shipped to user dev validation on commit `2d6be06` of `epic/E-228-defensive-positioning-cards`. Per E-228's TN-9 mandatory-branch-implementation gate, the branch is held for dev validation before merging to main. That validation surfaced three model failures that together require an architectural rework rather than a clean merge:

1. **Reference-frame bug.** E-228 used textbook `BASE_POSITIONS` (where a HS fielder learns to stand in practice) as the deviation origin. Result: every card defaults to "STRAIGHT UP" — the very position the categorical vocabulary describes as "no shift." For a pull-side opponent (which most HS lineups are to some degree), LF actually plays shaded left as a *default*, with individual batters as exceptions to THAT default, not exceptions to the textbook.
2. **Per-position responsibility-sector tautology.** E-228-02 Round 2 added per-position filtering: each position re-evaluates direction/depth from its own subset of BIPs. LF's subset is "left-outfield events" by construction — every event in that subset is "left," so the dominant direction is trivially "left," so LF always shades left if the thin gate passes. RF symmetrically over-calls. CF and 2B were permanently TRUE because their subsets were too small or too symmetric.
3. **Categorical text vocabulary doesn't communicate spatial info.** "SHADE LEFT" / "L Sh" / "MIXED" doesn't tell a fielder where to actually stand. The fielder has to translate a category into a physical position in their head. User validated mid-E-228 that this fails the dugout-glance test.

**The reframe.**
- **Reference frame**: team-aggregate optimal position per (opponent, position), computed from each opponent's whole-spray centroid projected onto each fielder's textbook base, scaled by position range (TN-8). The "star" on each card moves per opponent.
- **Per-batter direction**: a single deviation `(direction_deviation, depth_deviation)` against the team-aggregate star — NOT a per-position-subset re-evaluation. The R2 tautology is structurally avoided.
- **Delivery**: visual per-position field diagrams with the star at team aggregate, a faint textbook reference dot for variance context, and named compass zones (A=in+left, B=left, C=deep+left, D=in, E=deep, F=in+right, G=right, H=deep+right) where individual outlier batters cluster.

**Handedness.** Batter handedness is not in the GameChanger scouting data E-229 can obtain for opponents (TN-9). The team-aggregate star averages BIPs across all batters regardless of handedness; per-batter polarization (LHB pull tendencies, RHB oppo-field hitters) surfaces through outlier zone markers placed at each batter's spatial centroid. Real-time recognition of who is at the plate lives with the fielder, not the card. This is a structural design choice driven by data availability, NOT a v1 scope deferral.

**Phase 1 discovery provenance.**
- Planning seed: `.project/research/E-229-planning-seed.md`
- Consultations completed 2026-05-16 with baseball-coach, ux-designer, data-engineer (three rounds via main-session relay). Locks summarized in History.
- User proactively answered three of DE's open questions during planning (storage shape with single-source provenance, migration approach with branch-stack chain, wiring approach with fresh re-implementation) and locked two more independently (handedness as structural choice; print layout as quarter-letter 4-up).

**Ideas absorbed/promoted.**
- `IDEA-073` (Team-Wide Base Defensive Alignment) — promoted into E-229's core scope (the team-aggregate star). Marked PROMOTED → E-229.

## Goals
- Replace E-228's textbook reference frame with team-aggregate optimal positions computed from each opponent's BIP distribution (TN-3, TN-8).
- Replace E-228's categorical text vocabulary with visual per-position field diagrams + A–H compass zones for outlier batters (TN-3).
- Ship three coach artifacts in a single 4-page mixed-orientation PDF: a coach in-game call sheet (jersey × position → zone-letter matrix, landscape), a coach pre-game prep page (full-field overlay of all 6 positions and all outliers, landscape), and per-position player pocket cards (quarter-letter 4-up cut from letter portrait sheets) (TN-12).
- Preserve E-228's pipeline machinery shape (standalone path, scouting auto-bundle, dashboard link card) with fresh re-implemented code per user lock ("let's do it right").
- Retire categorical-model code wholesale: `call_state`, `team_state_call`, `direction_shade`, `depth_shade`, `zone_concentration` columns; the vocabulary block; the R2 per-position-subset re-evaluation logic; the TN-4a MIXED rule (TN-13).

## Non-Goals
- **Per-handedness card variants** (two-stars-per-card or 12-cards-per-opponent). Data availability is the constraint, not engineering effort (TN-9). Not captured as fast-follow ideas; the constraint is unlikely to change.
- **Per-position responsibility-sector re-evaluation** (the R2 tautology that broke E-228). Explicitly retired (TN-13).
- **Categorical text vocabulary** ("SHADE LEFT," "MIXED," "L Sh," "R," etc.). Retired in full (TN-13).
- **Coach card-key reference page** (one-page printed reference of the compass on a blank field). Single-card legend covers it (UXD lock); future-story candidate if validation shows fielders struggle to learn the compass.
- **Custom dashboard card view for tracked opponents.** Link card on opponent dashboard still resolves to the standalone report bundle (E-228 CX-2 reuse pattern, unchanged).
- **Runtime / dynamic zone clustering** — see `IDEA-072` (Clustering-Derived Empirical Fielding Zones), gated on E-229 calibration confirming per-batter centroid tightness.
- **Adding handedness to the data pipeline.** Out of scope; the structural design (TN-9) survives without it.

## Success Criteria
- Migration 002 rewritten in place on the `epic/E-228-defensive-positioning-cards` branch with v2 schema: retired columns gone; `zone_id` (CHECK A–H or NULL) added; new `team_position_aggregate` table with PK `(team_id, season_id, perspective_team_id, position)` added; conftest references to retired columns scrubbed.
- Engine produces 6 `team_position_aggregate` rows per opponent (LF/CF/RF/3B/SS/2B) and per-batter `batter_positioning` rows in a single SQLite transaction (TN-6 atomicity).
- Per-batter rows carry `zone_id ∈ {A..H, NULL}` + `is_thin` + (where applicable) `is_low_confidence`; NO categorical columns survive (TN-13).
- Coach AC: visual artifacts produced by E-229 (call sheet + prep page + player cards) represent test-opponent spray data more faithfully than E-228's text artifacts. Coach signs off on the design-review AC during E-229-05.
- Dashboard "Defensive Positioning" link resolves to E-229-generated bundle for tracked opponents (CX-2 reuse pattern preserved).
- User runs `docker compose up` on the combined E-228+E-229 branch HEAD and validates against real opponent data before merge to main (per TN-1 mandatory branch implementation).

## Stories

**Dependency chain** (per CR M1 fix to the Overview narrative):

```
1 → 2 → {2b, 9}
2b → {3, 4, 5, 6, 7}    # locked-constants artifact feeds every visual story (per Codex iter-3 P2.4)
3 → {4, 6}              # 4 extends 3's SVG; 6 reuses 3's field generator
4 → {5, 6}              # 5's template wraps 4's full pill output; 6 inherits 4's collision-jitter
{5, 6, 7, 9} → 8        # bundle needs all three artifacts AND the LLM contract (DE P1.2 fix)
8 → 10                  # pipeline calls bundle generation; no separate Tier 2 stage
```

Stories execute serially per the implement skill; the dependency graph determines a valid linear order. The implement skill picks one (e.g., `01 → 02 → 2b → 03 → 04 → 06 → 05 → 07 → 09 → 08 → 10`); the constraint is only that all `blocked_by` complete before a story starts.

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-229-01 | Migration 002 v2 — schema rewrite in place | TODO | None | data-engineer |
| E-229-02 | Engine rewrite — team-aggregate centroid + per-batter deviation + atomicity | TODO | E-229-01 | software-engineer |
| E-229-2b | Quarter-letter layout feasibility prototype | TODO | E-229-02 | ux-designer |
| E-229-03 | Card field SVG generator — star, textbook dot, compass letter ring, density background | TODO | E-229-02, E-229-2b | software-engineer |
| E-229-04 | Outlier batter pills — jersey lookup + collision jitter | TODO | E-229-03, E-229-2b | software-engineer |
| E-229-05 | Compact card template — quarter-letter 4-up geometry + coach design review | TODO | E-229-04, E-229-2b | software-engineer |
| E-229-06 | Coach prep page — full-field overlay, all 6 positions | TODO | E-229-03, E-229-04, E-229-2b | software-engineer |
| E-229-07 | Coach call sheet — jersey × position matrix, alphabetical sort | TODO | E-229-02, E-229-2b | software-engineer |
| E-229-08 | Bundle generation — 4-page mixed-orientation PDF + coverage-cue snapshot + LLM render-time threading | TODO | E-229-05, E-229-06, E-229-07, E-229-09 | software-engineer |
| E-229-09 | Tier 2 LLM input contract — render-time threading, no DB persistence | TODO | E-229-02 | software-engineer |
| E-229-10 | Pipeline wiring — standalone path + scouting path + dashboard link | TODO | E-229-08, E-229-09 | software-engineer |

## Dispatch Team
- data-engineer
- software-engineer
- ux-designer

## Technical Notes

### TN-1: Mandatory Branch Implementation -- E-228 + E-229 stack, NO AUTO-MERGE AT CLOSURE (forward-port of E-228 TN-9)

**This is a hard requirement carried forward from E-228's TN-9 and adapted to the E-228+E-229 branch stack. Whoever runs dispatch MUST NOT miss it.**

E-229's implementation builds directly on top of E-228's branch. The sequence is:

1. Dispatch creates the epic worktree branching from the E-228 branch HEAD, not from main: `git worktree add -b epic/E-229 /tmp/.worktrees/baseball-crawl-E-229 epic/E-228-defensive-positioning-cards`. This is an explicit override of the default branch-from-main pattern in `.claude/skills/implement/SKILL.md`.
2. Stories execute in the epic worktree as normal.
3. The closure step pulls the worktree changes back into the `epic/E-228-defensive-positioning-cards` branch HEAD (not into `main`). After closure, the E-228 branch carries: `c0e4fb8 chore(E-228) plan` → `2d6be06 feat(E-228)` → `<chore(E-229) plan>` → `<feat(E-229) closure>`.
4. The user runs `docker compose up` against the combined branch HEAD, exercises the positioning bundle against real-opponent data, and validates.
5. **Only after the user's explicit sign-off** does the combined E-228+E-229 stack merge to `main` as one atomic merge. E-228 never merges to main on its own.

The user's framing: "I'd rather validate the final state once than ship the broken intermediate state and re-validate the fixed state."

**Operator gotcha (release-step note).** The user's local `data/app.db` currently has E-228's v1 migration 002 applied. When E-229 lands on the branch, the migration runner sees "002 already applied" and skips, leaving the on-disk schema at v1 even though the file is v2. The user must drop the local database and reapply: `rm data/app.db && docker compose up -d --build app`. Single-operator project; no cleanup migration is needed (YAGNI).

### TN-2: Single-source provenance for `team_position_aggregate`

The engine in `src/reports/positioning.py` is the SOLE writer for the `team_position_aggregate` table. Render layer (`src/reports/renderer.py`, templates) and Tier 2 LLM (`src/reports/positioning_llm.py`) READ from this table; they never recompute the centroid in their layer, never shadow-store deviations from a different baseline. Same architectural shape as E-228's TN-6 engine-self-commit invariant: a single writer per data product avoids drift.

### TN-3: Reference frame and zone vocabulary

**Reference frame**: team-aggregate optimal position per `(team_id, season_id, perspective_team_id, position)`. Star = team-aggregate point in SVG space. Per-batter outlier = sign of `(direction_deviation, depth_deviation)` ordinal buckets against the star.

**Zone vocabulary** (8-zone compass around the star). Directional language is canonical; SVG positions follow from the coord convention in TN-15.

| Zone | Direction | Depth |
|------|-----------|-------|
| A    | left      | in    |
| B    | left      | (mid) |
| C    | left      | deep  |
| D    | (center)  | in    |
| E    | (center)  | deep  |
| F    | right     | in    |
| G    | right     | (mid) |
| H    | right     | deep  |

`(0, 0)` deviation = star = NULL zone label. Direction language is **stable across opponents** — the star moves, the language doesn't. Fielder learns the compass once and reuses it all season.

**Deterministic sign rule for zone assignment** (per DE I-4 lock): the zone letter is determined by `(sign(direction_deviation), sign(depth_deviation))`. Magnitude is IGNORED for letter assignment; the field-plot position carries magnitude per TN-5. Sign convention: `direction` negative = `left`, positive = `right`; `depth` negative = `in`, positive = `deep`.

| `sign(direction)` | `sign(depth)` | Zone |
|-------------------|---------------|------|
| neg               | neg           | A    |
| neg               | 0             | B    |
| neg               | pos           | C    |
| 0                 | neg           | D    |
| 0                 | 0             | NULL (star, no zone label) |
| 0                 | pos           | E    |
| pos               | neg           | F    |
| pos               | 0             | G    |
| pos               | pos           | H    |

**Legend wording is sourced from module-level constants** (per UXD M-1) so all surfaces share the same text:
- `COMPASS_LEGEND_SHORT` (per-card): `★ team default · ○ textbook · A–H = outlier zones (see right)`
- `COMPASS_LEGEND_LONG` (call sheet, prep page): `A in-left · B left · C deep-left · D in · E deep · F in-right · G right · H deep-right · · = team default`

**Render-layer compass behavior**: all 8 letters render at fixed angular positions on every card; populated zones at full opacity, empty zones as faint placeholders (~30% opacity). This preserves the stable visual language for the recognition task. Letter placement is at the outer edge of each zone (~75–85% of available radius from star), edge-clamped to the field outline.

**Axis naming**: "in/deep" preferred over "shallow/deep" (coach lock — "in" is shorter and more dugout-natural; coaches say "bring it in" or "play them in" far more often than "play them shallow"). The legend wording on cards and the call sheet uses "in/deep" verbatim.

**Zone ordering note.** A–H follows a skip pattern around the star — NOT clockwise, NOT grid-mapped. Under TN-15's SVG coord convention (`y=0 at deep CF`), the letters project as: A (in+left) lower-left of star, B (left) left of star, C (deep+left) upper-left, D (in) below, E (deep) above, F (in+right) lower-right, G (right) right, H (deep+right) upper-right. The lettering is optimized for the **recognition task** (fielder looks at the card and finds the zone), not the **memory task** (fielder recalling what Zone F means without the card). The visual card is doing the heavy lifting; the letter ordering is a label, not a mnemonic.

### TN-4: Confidence tiers and visual states

Sample-size thresholds, computed at engine time and persisted to `team_position_aggregate.is_low_confidence` and `bip_count`:

| Tier | BIP count (opponent) | Visual state | `is_low_confidence` |
|------|---------------------|--------------|---------------------|
| Zero-coverage | 0–14 | NO star rendered; dominant card message "Not enough spray data — play your standard alignment"; per-batter outliers NOT rendered; spray-density background hidden | 1 |
| Thin-data | 15–49 | Star rendered with thin-data badge (dashed ring or "(~N BIP)" caption); outliers rendered normally; spray-density background hidden | 1 |
| Full | 50+ | Star rendered solid **with small BIP-count caption** (e.g., "(N BIP)" at ~6–7pt per coach BC-3 "always contextualize, never suppress" — the BIP count contextualizes the star at every confidence tier, not only the thin-data tier); outliers normal; spray-density background rendered (15% opacity dot layer) | 0 |

The 0/15/50 BIP boundaries are coach-calibrated (15 BIPs ≈ 1 full HS game; 50 BIPs ≈ 3–4 games). Zero-coverage state does NOT fall back to textbook `BASE_POSITIONS` for the star — that would re-introduce the E-228 reference-frame bug for first-time opponents.

### TN-5: Outlier threshold

A batter earns an outlier zone marker on the per-position card when ALL of these hold:
- `BIP ≥ 10` (existing thin gate: `is_thin = 0`)
- AND (`|direction_deviation| ≥ 1` OR `|depth_deviation| ≥ 1`) — at least one axis is in a non-zero ordinal bucket

Render: each batter is a numbered pill at their specific `(x, y)` in field SVG space relative to the star. Magnitude is communicated by the pill's position on the field — no sub-letters (A1/A2), no sidebar magnitude tags. The field plot IS the magnitude. The labeled jersey pill IS the disambiguator.

A batter with `BIP < 10` (`is_thin = 1`) gets NO individual outlier marker. Their BIPs DO contribute to the team-aggregate centroid (they shape the star without earning a per-batter shift).

E-228's previous outlier gate (4 BIP / 35% concentration) is retired with the rest of the categorical model.

### TN-6: Atomicity invariant

In a single SQLite transaction, the engine MUST refresh both `team_position_aggregate` rows (6 per opponent) and the corresponding `batter_positioning` rows for that opponent. A partial state where the aggregate is updated but per-batter rows are not (or vice-versa) breaks the render invariants — outlier markers would be measured against a stale star. Either both update or neither updates.

The engine's commit is its own per E-228 TN-6 (engine self-commit; callers do not wrap in an outer transaction).

### TN-7: Render-layer JOIN patterns

Jersey number on outlier pills:
```sql
batter_positioning JOIN team_rosters USING (team_id, player_id, season_id)
```
Roster is authoritative; jersey is NOT denormalized to `batter_positioning`. Renderer fallback if `jersey_number` is NULL: last initial of player name (so the call sheet can still yell something).

Spray-density background:
```sql
SELECT x, y FROM spray_charts
WHERE team_id = ? AND season_id = ? AND perspective_team_id = ?
  AND chart_type = 'offensive' AND x IS NOT NULL AND y IS NOT NULL
```
Same `(x, y)` pool fuels all 6 cards (whole-team spray projected behind each position's diagram).

Aggregate star position:
```sql
SELECT position, star_x, star_y, bip_count, is_low_confidence FROM team_position_aggregate
WHERE team_id = ? AND season_id = ? AND perspective_team_id = ?
```
Returns 6 rows (one per position).

### TN-8: Position-scaled projection

The whole-spray centroid is a single `(x, y)` point representing the opponent's directional lean. Each position's star = textbook `BASE_POSITION` for that position offset in the direction of the lean, SCALED BY POSITION RANGE: outfielders cover more range than infielders, so the same centroid displacement = bigger physical adjustment for LF than for 2B. The engine in `src/reports/positioning.py` computes this projection; the per-position scaling factors are calibrated constants initially anchored on E-228's `BASE_POSITIONS` reasoning, refined during the first-real-opponent calibration pass (see Rollout below).

This is the position-scaled projection coach surfaced during round-1 consultation — the centroid says "where does this opponent's contact tend to land?" and each fielder's star says "given that lean, where do I shade from MY textbook?" The scaling factor preserves the directional fact while honoring per-position range.

### TN-9: Handedness — structural design choice

Batter handedness is NOT in the GameChanger scouting data E-229 can obtain for opponents. The relevant facts (carried forward from E-228's CX-5 api-scout consultation):
- Public roster endpoint (`/teams/public/{public_id}/players`) has no handedness field
- `players.bats` is unpopulated dead schema (zero read/write paths)
- Handedness-carrying endpoints exist but are off the public-id-based opponent scouting path E-229 uses

The team-aggregate star averages BIPs across all batters regardless of handedness. Per-batter polarization (LHB pull tendencies, RHB oppo-field hitters) surfaces through outlier zone markers placed at each batter's spatial centroid — a LHB pull-hitter shows as a right-field outlier marker regardless of handedness label. Real-time recognition of who is at the plate lives with the fielder, not the card.

This is a **structural design choice driven by data availability**, NOT a v1 scope deferral. The constraint is unlikely to change. Two-stars-per-card and 12-cards-per-opponent (per-handedness) variants are not captured as fast-follow ideas.

### TN-10: Marker collision

When two outlier batter pills land within ε of each other in SVG space, the renderer applies deterministic radial jitter with stable angular order keyed on jersey number (sorted ascending). This is pure render-layer logic — the engine emits raw `(direction_deviation, depth_deviation)` and the render layer projects to SVG coordinates and resolves collisions. No engine hint, no schema column. The collision-resolution function lives in the field SVG generator (E-229-04).

### TN-11: Lazy backfill

The `team_position_aggregate` table is populated lazily on the first scout run or report-generate after the migration applies (via `bb data scout` or `bb report generate <public_id>`). No backfill migration runs at deploy time. Single-operator project; lazy fill is acceptable and avoids deploy-time data work.

### TN-12: Bundle structure

The report bundle is a single 4-page mixed-orientation PDF:
- **Page 1**: Coach in-game call sheet (letter landscape) — full sheet, dugout use
- **Page 2**: Coach pre-game prep page (letter landscape) — full sheet, pre-game analysis
- **Page 3**: 4-up player cards (letter portrait): LF | CF / RF | 3B
- **Page 4**: 4-up player cards (letter portrait): SS | 2B / **compass-key** | **opponent-context-card** (per E-229-05 AC-9 lock; the prior draft's `blank | blank` was retired during Phase 4 iteration 2)

Per-card geometry: 4.25" × 5.5" portrait (quarter-letter). Cut on the midlines after printing; hand 6 cards to fielders (slots 1–6 across the two sheets); the compass-key and opponent-context cards are coach-facing artifacts cut and kept by the coach. Cards survive a 7-inning back-pocket.

The user reframed the print workflow ("he will never print them between innings; one report pre-game; back-pocket size") which overrode UXD's round-1 1-per-page recommendation. E-228's `@page` directive pattern is the precedent for mixed-orientation rendering in one HTML/PDF — only two orientations are needed (landscape + portrait).

### TN-13: What E-228's engine retires (inventory)

Code surface that E-229 retires wholesale:
- `call_state` column on `batter_positioning` (8-key enum: `TRUE`/`LEFT`/`LEFT_SHALLOW`/`LEFT_DEEP`/`RIGHT`/`RIGHT_SHALLOW`/`RIGHT_DEEP`/`MIXED`)
- `team_state_call` column on `batter_positioning` (TN-4a MIXED-rule artifact)
- `direction_shade`, `depth_shade` columns (categorical buckets; redundant once raw deviation magnitudes and zone identity are present)
- `zone_concentration` column (categorical confidence metric for the dominant-zone test)
- `POSITION_RESPONSIBILITY_SECTORS` constant, `bips_for_position()`, `_compute_position_row()` (the R2 per-position-subset re-evaluation logic)
- `_compute_team_state_call()`, `ADJACENCY_LATTICE` (the TN-4a MIXED rule)
- `POSITIONING_CALL_WORDS`, `POSITIONING_CELL_SHORT_FORMS`, `POSITIONING_COLUMN_ORDER`, `POSITIONING_POSITION_LABELS` (the render-layer vocabulary block)

### TN-14: What E-228 keeps (or extends)

- `BASE_POSITIONS` constants survive as render-layer reference dots only — engine no longer uses them as the deviation frame
- `classify_field_zone()` if its output is useful for direction-signal classification (renderer/engine decision during E-229-02 and E-229-03)
- Migration runner mechanics (no change)
- Bundle architecture (`@page` directives, slug-based URLs, `ready`/`expired` lifecycle, `src/reports/generator.py`)
- Dashboard "Defensive Positioning" link card on the opponent dashboard — unchanged scope; resolves to most-recent `ready` report
- Tier 2 LLM rationale slot in `src/reports/positioning_llm.py` — input contract changes (E-229-09); the optional non-fatal contract is preserved; **rationale is ephemeral (rendered inline by E-229-08's bundle assembler; no persistence to any table, no `rationale` column on `batter_positioning`)** per CR B1 + DE P1.2 lock. Bundles are regeneratable on demand; no audit trail in v1. If audit-trail or rationale-caching becomes a real need later → future epic; do not retrofit a column into E-229's migration.

### TN-15: SVG coordinate convention (per DE P1.1 + Codex Phase 4)

The field SVG is 320×480 pixels in the canonical layout. **y=0 is at deep CF (top of canvas); y increases toward home plate (bottom).** x=0 is at the left foul line; x increases toward the right foul line. Reference: `src/charts/spray.py:47` (anchor-point comment) and `src/charts/spray.py:480` (ylim inversion in the renderer).

Engine output: raw signed deviations `(direction_deviation, depth_deviation)` against the team-aggregate star, where:
- `direction_dev < 0` = "left" (toward LF)
- `direction_dev > 0` = "right" (toward RF)
- `depth_dev < 0` = "in" (toward home plate; LARGER SVG y)
- `depth_dev > 0` = "deep" (toward CF wall; SMALLER SVG y)

Render-layer projection from engine output to SVG offset relative to the star:
```
x_offset =  direction_dev * scale_x
y_offset = -depth_dev * scale_y     # the negation is the y-axis convention adjustment
```

The `-` sign on the depth axis is the canonical y-axis convention adjustment; do not "fix" it. Compass-letter ring placement and per-batter pill placement both apply this projection — see E-229-03 AC-4 (compass) and E-229-04 AC-1 + the coord-system regression test AC (pills).

**Consequence for the zone-letter compass on each card**: Zone A (in + left) projects to LOWER-LEFT of the star (negative x_offset, positive y_offset since `-depth_dev * scale_y > 0` when `depth_dev < 0`). Zone H (deep + right) projects to UPPER-RIGHT. Zone D (in, centered) is straight DOWN from the star. Zone E (deep, centered) is straight UP. The renderer computes positions from the zone vocabulary via the projection formula — there is NO hand-mapped angular-degree table in story specs (that pattern was retired during Phase 4 incorporation because it baked in a y-inversion assumption that contradicted the spray.py convention).

### TN-16: Design tokens and coverage cue (per UXD I-1 + I-6 + coach IM-2)

A single source of truth for cross-surface design specifications. Render layer references these tokens; templates do NOT define their own typography or wording.

**Coverage-cue format**: `Through {Mon Day} ({N} games)` rendered at 9pt regular, right-aligned in card/page headers. Snapshot semantics (per coach IM-2 + user-confirmed restore-with-snapshot path): the game count `N` is captured AT bundle-generation time, NOT recomputed when the bundle is viewed (which was the E-228 Phase 4b bug). SE picks the storage shape in E-229-08 (column on `reports`, file metadata, or bundle JSON).

**Color is never load-bearing** (per UXD I-6): all information (zone identity, confidence tier, batter identity) is communicated by shape, position, or text — NEVER by color alone. Color is decorative enhancement only. Test surface: SVG output uses only black, white, and grey-scale fills/strokes by default.

**Typography minimums** (per coach MN-2 + UXD I-3 + UXD I-4):
- Pill jersey + truncated name: 9pt bold (≥7pt absolute minimum at quarter-letter print)
- Compass letters: 10pt bold inside 0.18" diameter 20%-opacity grey circle (≥7pt absolute minimum)
- Card legend: ~7pt
- Coverage cue: 9pt regular
- Call sheet jersey column: 11pt bold (UXD I-7 lock — visually prominent for jersey-lookup workflow)
- Call sheet other columns: 9pt regular
- **Tier 2 LLM rationale (prep page sidebar + call sheet NOTE column ONLY; NOT on cards)**: italic 8pt 50% grey, CSS `-webkit-line-clamp: 2`, overflow hidden, no ellipsis, empty/None renders nothing (per Codex iter-3 P1.2 + UXD lock; full spec in locked-constants artifact §E "Rationale" subsection — this line is a cross-reference; artifact is canonical)

**Module-level constants** (per UXD M-1):
- `COMPASS_LEGEND_SHORT` and `COMPASS_LEGEND_LONG` defined in `src/reports/positioning_card.py` (or a shared renderer module); imported by every template surface (cards, prep page, call sheet) so legend wording cannot drift.
- `format_coverage_cue(through_date, game_count) -> str` helper returns the locked format string.

**Cut-line spec** (per UXD M-3): 0.5pt dashed hairlines (2pt dash, 2pt gap), 50% grey, on horizontal and vertical midlines only. No corner crop marks, no full-card borders.

**Mobile breakpoint** (per UXD I-5): card template collapses to single-column at viewports ≤640px (Tailwind `sm:` breakpoint, NOT `md:`); SVG full-width with aspect ratio preserved, sidebar below at full width.

### Rollout (operator activity -- not a story)

After E-229 lands on the branch, the operator (Jason) runs a first-real-opponent calibration pass: generate the bundle for a real opponent, eyeball the team-aggregate stars against the spray chart, and tweak the position-scaled projection constants (TN-8) and confidence-tier thresholds (TN-4) if needed. The calibration pass has a second job: assess whether the per-batter centroids are tight enough to justify pulling `IDEA-072` (Clustering-Derived Empirical Fielding Zones) forward — this is the empirical decider for the runtime-clustering Non-Goal's gate.

This is a rollout note, not a shippability gate. Constant-comment convention: once a constant has been calibrated, its `# RECALIBRATE after first opponent dataset` annotation becomes `# Calibrated <date> against <opponent>, N games`.

## Open Questions
- **`is_low_confidence` propagation to per-batter rows.** Confidence is naturally per-position on `team_position_aggregate`. Whether to denormalize the flag onto `batter_positioning` rows for render-layer convenience is an engine-implementation choice in E-229-02; either path is acceptable.

(The "two blank slots on print sheet 2" and "zero-coverage state visual treatment" Open Questions from the prior draft were resolved during Phase 3 iteration 1 incorporation: slots locked to visual compass key + opponent context card per UXD I-2; zero-coverage locked to "no star + standard alignment message" per coach + DE no-textbook-fallback principle, user accepted.)

## History
- 2026-05-16: Created (DRAFT). Phase 1 discovery complete:
  - **Round 1** consultations with baseball-coach, ux-designer, data-engineer (all via main-session relay after peer-DM dropouts).
  - **Round 2** consultations forwarding coach's design hints to DE (position-scaled projection, batting-order data dependency) and UXD's engineering items to DE (jersey lookup, raw BIP coords for density bg, marker collision, mixed-orientation bundle).
  - **User direct input** locked Q-1 storage (new table with single-source provenance invariant), Q-2 migration (branch-stack chain on E-228 branch with migration 002 rewritten in place), Q-4 wiring ("let's do it right" — fresh re-implementation), handedness (structural design choice, not v1 deferral), and print layout (quarter-letter 4-up, 4 pages total, back-pocket geometry).
  - **PM-side reconciliations**: zero-coverage state locked as "no star + standard-alignment message" (yielded to coach+DE no-textbook-fallback principle); marker collision locked as render-layer-only with deterministic jitter; spray-density background gated by same sample-size threshold as the star.
  - Absorbs `IDEA-073` (Team-Wide Base Defensive Alignment) — promoted to E-229 core scope.
- 2026-05-17: **Status → READY.** All planning iterations complete; quality checklist passes; strengthened cross-grep sweep clean across all artifacts. User directive at READY transition (verbatim, captured per agent-team-compliance Pattern 3 anti-fabrication discipline): *"let's move to ready but stay in this branch, We're going to work it from here. We're going to test it here. And then...only when it's tested...we MIGHT merge it to main. But after implement we're going to merge it back into this branch."* This reaffirms TN-1 mandatory branch implementation: plan-commit + dispatch worktree + closure all stay on `epic/E-228-defensive-positioning-cards`; merge to main is a separate, gated decision after the user's dev-environment validation on the combined E-228+E-229 branch HEAD. The "MIGHT" is explicit conditionality — merge requires validation to clear, not just dispatch to close.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 13 | 13 | 0 |
| Internal iteration 1 — Holistic team (coach + UXD + DE) | 44 | 43 | 0* |
| Codex iteration 1 (Phase 4 iter-1) | 7 | 7 | 0 |
| Codex iteration 2 (Phase 4 iter-3 from plan-skill POV) | 4 | 4 | 0 |
| **Total** | **68** | **67** | **0** |

\* 1 NO-ACTION on DE M-4 sizing assessment (no action needed; DE confirmed keep-as-one-story for E-229-10).

Note: the "71" cumulative figure cited during reviews counted DE round-2 follow-up (B-5 batting_order scope-out) as a finding; for scorecard purposes that's an extension of Internal iteration 1 (DE B-5) already counted. The 68 / 67 / 0 totals reflect distinct findings reviewed, with the 1 NO-ACTION explicit.

- 2026-05-17: Phase 4 (Codex spec-review validation) iteration 3 incorporated. **4 findings reviewed (3 P1 / 1 P2); 4 ACCEPTED, 0 DISMISSED.** Round-2 consults: coach confirmed P1.1 option (b) — flagged-first partition with alphabetical-by-last-name within each partition (rejected jersey-sort and severity-sort); UXD confirmed P1.2 — rationale renders on prep page sidebar + call sheet NOTE column only, NOT on cards (audience split: rationale → coach surfaces; fielder surfaces skip). Key fixes: E-229-06 AC-4 locked to two-partition alphabetical sort; locked-constants artifact drift A (compass-ring formula missing `scale_x`/`scale_y`) + drift B (`COMPASS_LEGEND_SHORT` missing `(see right)`) fixed in `.project/research/E-229-locked-layout-constants.md`; E-229-06 AC-2/AC-5 + E-229-07 AC-1/AC-5/AC-7 rewritten to cite artifact §B/§E/§F instead of inlining values; dep edges added `blockedBy: E-229-2b` on E-229-04/06/07 (now ALL visual stories 03/04/05/06/07 block on 2b); new ACs for rationale slot: E-229-06 AC-10 (sidebar second-line under each row, CSS line-clamp:2) + E-229-07 AC-1/AC-9 (NOTE column rightmost, restored from E-228 pattern per UXD); locked-constants artifact §E gains "Rationale" subsection (italic 8pt 50% grey 2-line clamp); epic TN-16 typography minimums get a cross-reference line to artifact §E. **Sweep methodology gap** caught: prior iteration's sweep did internal-only artifact-vs-artifact grep but didn't cross-grep artifact-vs-stories; codified extension in `feedback_concept_word_consistency_sweep.md`. PM owns artifact drift A + B (introduced when writing the stub during iter-2; cross-grep methodology would have caught).

- 2026-05-17: Phase 4 (Codex spec-review validation) iteration 2 incorporated. **7 findings reviewed (3 P1 / 4 P2); 7 ACCEPTED, 0 DISMISSED.** Round-2 consults landed: DE confirmed SVG y-axis convention (`y=0 at deep CF` per `src/charts/spray.py:47, 480`); DE locked LLM render-time ephemerality (no DB persistence for rationale; bundle assembler in E-229-08 owns the call); UXD expanded the locked-constants artifact to 7 sections (A–G) + decisions log + YAML versioning frontmatter; CA confirmed E-229-05 routing fix (UXD → SE). Key fixes: epic TN-15 new ("SVG coordinate convention" — y-axis y=0 at deep, projection formulas for compass + pills, `src/charts/spray.py` references); design-tokens TN renumbered TN-15 → TN-16; epic TN-3 zone-list prose stripped of canvas-position modifiers (directional vocabulary canonical, SVG positions follow from coord convention); E-229-03 AC-4 rewritten with sign-offset formula (no hand-mapped degree table) per DE P1.1; E-229-04 AC-1 + new AC-8 coord-system regression test per DE P1.1; E-229-03 AC-1 + E-229-04 AC-3 + E-229-05 AC-1/AC-2 strip hardcoded numeric values (0.6 aspect, 64/36 split, pill dims) and cite the locked-constants artifact instead per Codex P2.5; E-229-06/E-229-07 split into focused modules (`positioning_prep.py` + `positioning_call_sheet.py`) per Codex P2.6; E-229-06 AC-4 batting-order concept-word cleanup (iteration-1 sweep gap) — alphabetical-only sort + flagged-first applies on prep page per coach BC-1; E-229-08 added `blockedBy: E-229-09` + new AC-7/AC-8 LLM render-time threading + ephemerality verification per DE P1.2; E-229-10 removed AC-5 (LLM ownership moved to 08) + `_run_tier2_rationale` function (no separate Tier 2 stage); TN-12 page-4 slot fill propagation `blank | blank` → `compass-key | opponent-context-card` per Codex P2.4; E-229-05 Agent Hint `ux-designer` → `software-engineer` + routing-rationale comment per Codex P2.7 + CA. NEW: `/.project/research/E-229-locked-layout-constants.md` artifact stub (PROVISIONAL v0 with UXD round-1 estimates as initial values; E-229-2b flips to LOCKED v1). Sweep methodology lesson: iteration-1 grep'd code-syntax patterns and missed prose references using the concept word; iteration-2 sweep uses concept-word + code-syntax grep. PM captured the lesson as `feedback_concept_word_consistency_sweep.md` in agent memory.

- 2026-05-16: Phase 3 iteration 1 (CR + holistic team review + DE round-2 followup) incorporated. **57 findings reviewed (coach 8 + CR 13 + UXD 15 + DE 21); 56 ACCEPTED, 0 DISMISSED, 1 NO-ACTION (DE M-4 sizing assessment).** User decisions: (1) coverage-cue path = restore-with-snapshot (game count persisted at bundle-generation time per epic TN-16); (2) new story E-229-2b "Quarter-letter layout feasibility prototype" inserted between E-229-02 and E-229-03 (UXD-owned; locks layout constants); (3) full 56-ACCEPT set proceeds. Key fixes: schema regression in E-229-01 (column types corrected to TEXT; FK REFERENCES added; PK locked to `(player_id, team_id, season_id, perspective_team_id, position)`); thin-gate language drift removed across E-229-02 (triple-confirmed by coach BC-2 + CR I3 + DE B-7); call sheet sort reframed to alphabetical-only with no batting_order conditional (per DE B-5 + UXD I-7; `team_rosters.batting_order` doesn't exist); flagged-first grouping removed from call sheet (per coach BC-1; lineup-card pairing) and retained on prep page only; compass letter rendering unified to "render all 8 always" with faint placeholders for empty zones (per coach MN-1 + UXD B-3/I-4 + CR I1); LLM rationale locked as render-time in-memory threading (per CR B1; no DB persistence); cherry-pick policy tightened to "fresh re-implementation only" (per DE I-8); pipeline file path corrected `src/scouting/run_scouting_sync.py` → `src/pipeline/trigger.py` (per DE B-6); TN-15 design tokens added consolidating coverage cue, typography, color accessibility, cut-lines, mobile breakpoint, module constants (renumbered to TN-16 in iteration 2 when the SVG-coord-convention TN was inserted ahead of it). PM owns three errors I introduced: schema regression (DE B-1/2/3), fabricated DE round-2 confirmation in E-229-07 Notes (DE B-5; captured in `feedback_no_fabricated_expert_confirmation.md`), wrong file path (DE B-6). Captures IDEA-077 "Season-modal batting order from boxscore backfill" with prerequisite "api-scout verifies boxscore JSON carries batting_order"; if promoted, its own epic per DE.
