# E-229 Planning Seed

**Status**: Phase 1 (discovery + consultation) nearly complete. One open user decision (print layout) before Phase 2 (epic + stories).
**Created**: 2026-05-16. Last updated: 2026-05-16 during planning.
**Authoritative for**: locked decisions, in-flight decisions, open questions, scope hints, team state. Designed so a fresh session can resume planning cleanly.

---

## How to resume (read this first if you're a fresh session)

1. **Where we are**: E-228 is committed on `epic/E-228-defensive-positioning-cards` (commit `2d6be06`), NOT merged to main. Dev validation surfaced architectural problems → E-229 plans a rework.
2. **Plan skill is loaded**. Phase 1 (discovery + consultation) is running. One open user decision (print layout) remains before Phase 2 (epic + stories).
3. **Active team** (all alive on `e228-positioning` team): PM, baseball-coach, ux-designer, data-engineer. SE/CR/docs/arch are shut down until dispatch.
4. **Working tree state**: checked out on `epic/E-228-defensive-positioning-cards` branch. Untracked files in `.claude/agent-memory/*` and elsewhere (agent state). The Docker stack runs E-228's code currently (not E-229).
5. **Communication protocol**: peer DMs between PM and experts have been UNRELIABLE — drop silently. All E-229 consultations went through the main session as relay. PM has been instructed to peer-DM + carbon-copy team-lead with `summary: "[to <agent>] <topic>"` going forward.
6. **First action a fresh session should take**: surface the one remaining open user decision (print layout), wait for DE round-2 response, then route PM into Phase 2.

---

## Why E-229 exists

E-228 ran through TN-9 user dev validation. Validation surfaced three problems requiring a model rework, not a clean merge:

### 1. Reference-frame bug
E-228 used textbook `BASE_POSITIONS` as the deviation origin. Every card defaults to "STRAIGHT UP" — essentially never correct for a real opponent.

### 2. Per-position re-evaluation tautology
E-228-02 R2's responsibility-sector filtering: LF's subset is `(left, outfield)` events by construction → dominant direction is always left → LF always shades left. RF symmetric. CF permanently TRUE.

### 3. Categorical text vocabulary is wrong delivery format
SHADE LEFT / per-position glyphs / MIXED don't communicate spatial truth. Fielder has to translate categories into physical positions in their head.

---

## Locked decisions (consensus from coach + UXD + DE + user)

### Model
- **Reference frame** = team-aggregate optimal position per (opponent, position). Computed from THIS opponent's whole-spray BIP centroid in SVG space.
- **Whole-spray-centroid projection** (NOT per-position-subset). The single centroid is projected onto each position's textbook BASE_POSITION as a position-scaled offset (coach: "outfielders cover more range than infielders, so the same centroid displacement = bigger physical adjustment for LF than for 2B"). This is the engine spec for E-229's Stage A.
- **Per-batter deviation** = signed ordinal buckets (`-2/-1/0/+1/+2`) on `(direction_deviation, depth_deviation)` axes, measured against the star (not textbook).
- **Outlier threshold** = `bip_count >= 10 AND (|direction_deviation| >= 1 OR |depth_deviation| >= 1)`. No feet-based thresholds (we can't honestly convert SVG to feet). No concentration thresholds (designed for the retired categorical model).
- **Zones A–H** = fixed compass directions around the star:
  - A=in+left, B=left, C=deep+left, D=in, E=deep, F=in+right, G=right, H=deep+right
  - (0,0) = star = no zone label
  - Direction-language STABLE across opponents (star moves; language doesn't)
  - "in/deep" vocabulary, NOT "shallow/deep" (coach: more dugout-natural, shorter to yell)
  - Counter-clockwise ordering is non-intuitive spatially; intentional and documented for future readers
- **Thin batters** (BIP < 10): no individual outlier zone; BIPs DO feed team aggregate.
- **MIXED retired entirely.** No team-state call. No categorical labels. The artifact tells the fielder where to stand, period.
- **Handedness: single averaged star (no LHB/RHB split).** Locked as structural design choice (NOT a v1 deferral). User directive 2026-05-16: handedness data is probably unavailable from the GameChanger scouting API for opponent batters — so the engine cannot reliably partition. Statistics still surface the polarization through outlier zones (a LHB pull hitter shows up as a right-field outlier marker regardless of whether their handedness is labeled). Outfielders adjust in real time when they see who's batting. (ii) two stars and (iii) 12 cards are NOT captured as fast-follow ideas — the underlying constraint is data availability, not v1 simplicity.

### Three coverage tiers (coach Q-C, no textbook fallback per PM/DE/coach)
- **0–14 BIPs total**: NO STAR rendered. Card shows "Not enough spray data — play your standard alignment." Card still fully renders (opponent header, position header, coverage cue, legend, message). PM's earlier "dashed textbook star" hybrid was withdrawn — would re-introduce E-228 bug.
- **15–49 BIPs**: Star rendered with thin-data badge (e.g., dashed circle around it or `(~N BIP)` label).
- **50+ BIPs**: Full star, no special indicator.

### Three artifacts (UXD locked)
1. **Per-position player pocket cards** (primary in-game): one per fielding position (LF, CF, RF, 3B, SS, 2B). SVG field diagram. Star at team-aggregate default. Small textbook-reference dot (open outlined circle, no fill, 30–40% grey, 1pt stroke, no label, smaller than star — visually quiet). A–H zone letters at FIXED compass positions on a ring around the star at ~45° increments (NOT at batter centroid). Only render letters for populated zones. Outlier batter markers as numbered jersey pills at exact field positions. Sidebar lookup: zone-grouped (e.g., "Zone A: #7, #22"). Coverage cue, opponent name, position name in header. One-line legend at bottom: `★ team default · ○ textbook · A–H = outlier zones (see right)`.
2. **Visual coach prep page**: full field, all 6 positions overlaid, all outlier markers with position tags. Faint single-channel grey spray-density background (drop below sample threshold). Used pre-game.
3. **Compact text coach in-game call sheet**: jersey × position → zone-letter matrix. Columns: #, name, LF, CF, RF, 3B, SS, 2B. Cell = single zone letter A–H or `·` (team default). **Sort by batting order, fallback alphabetical-by-name if batting order unavailable.** Flagged-batters-first sort with group divider. Legend at top.

### Data model (DE locked)
- **Retire from `batter_positioning`**: `call_state`, `team_state_call`, `direction_shade`, `depth_shade` (categorical buckets — redundant once we have raw deviations and zone identity).
- **Keep**: `direction_deviation`, `depth_deviation` (already present), `is_thin`, `bip_count`, `hr_count`, `zone_concentration` (DROP — categorical artifact).
- **Add to `batter_positioning`**: `zone_id TEXT NULL` (`'A'..'H'` or NULL; NULL = at-star, no marker). Constraint: `CHECK (zone_id IS NULL OR zone_id IN ('A','B','C','D','E','F','G','H'))`.
- **New table**: `team_position_aggregate(team_id, season_id, perspective_team_id, position, star_x, star_y, bip_count, is_low_confidence, computed_at)`. PK = `(team_id, season_id, perspective_team_id, position)`. Six rows per opponent per perspective.
- **Engine is single writer** for `team_position_aggregate` (user-emphasized: single-source provenance). Render and Tier 2 LLM read but never recompute or shadow-store.
- **Atomicity**: `team_position_aggregate` + `batter_positioning` refresh in SAME transaction. Invariant for the epic Technical Notes.
- **Backfill**: lazy via `bb data scout` on first opponent-touch after deploy. One-line epic mention.

### Pipeline / surface reuse from E-228
- `bb report generate <public_id>` (standalone path) — wired to recompute, **re-implemented** for E-229 (user said "let's do it right" — no cherry-pick).
- `run_scouting_sync` + `bb data scout` (scouting path) — auto-generate bundle on every scout run.
- Opponent dashboard "Defensive Positioning" link card — unchanged from E-228. Resolves to most-recent `ready` report.
- **Tier 2 LLM rationale** — survives, optional, non-fatal. Input shape changes (deviation + aggregate context, not categorical). **Tier 2 input contract gets its own dedicated story** (DE recommendation; locks the schema before implementation to prevent post-impl breakage).
- **Bundle structure**: single mixed-orientation PDF. Order: page 1 = call sheet (landscape) → page 2 = prep page (landscape) → pages 3-8 = 6 player cards (portrait, one per page).

### Engineering details (PM-locked, no user input needed)
- **conftest.py scrub**: AC gates that no orphan `call_state` references survive in test fixtures.
- **Marker collision** offset/jitter algorithm: render-layer concern by default. Engine may emit cluster hints if cheap (DE round-2 to confirm).
- **Card-key reference page**: SKIP. The per-card legend + call-sheet legend cover it. Future-story candidate if validation shows fielders struggle.
- **Mobile/web view**: Tailwind `flex-col md:flex-row` responsive. Trivial.
- **Spray-density background on cards**: single-channel grey, ~15% opacity max, dot-only (no convex hull / no heatmap), renders behind everything. Drop below sample threshold.
- **No-outliers state** (sufficient sample but no batter has a zone): render template with star + textbook dot + legend + "No outliers this opponent" note. Same template, fewer elements.

---

## User-decided so far

| Question | User answer | Date |
|---|---|---|
| Q-1 storage shape | New table — with single-source-provenance invariant (engine is only writer) | 2026-05-16 |
| Q-2 migration sequencing | Build E-229 on the existing `epic/E-228-defensive-positioning-cards` branch. E-229 worktree pulls back into the 228 branch for user dev validation. Branch merges to main only after validation. Migration 002 rewritten in place to v2 schema (E-228's v1 002 never reached main). | 2026-05-16 |
| Q-4 wiring carry-over | Re-implement, don't cherry-pick ("let's do it right") | 2026-05-16 |
| Q-5 handedness | Single averaged star. Structural design choice — handedness data isn't reliably available in GC scouting; polarization shows in outlier zones; OF adjusts real time. (ii)/(iii) NOT captured as fast-follow ideas. | 2026-05-16 |
| Q-6 print layout | Quarter-letter cards (4.25"×5.5" portrait), 4-up cut from letter sheets. 6 cards = 2 letter sheets (2 blank slots on sheet 2). One pre-game print → coach cuts on cross-fold lines → distributes 6 cards to fielders. Coach materials (call sheet + prep page) stay full-letter landscape for the dugout. Bundle = 2 standard letter pages + 2 cut sheets. | 2026-05-16 |

### Operator gotcha (DE flag, user-acknowledged via Q-2)
Local `data/app.db` currently has E-228's v1 migration 002 applied. When E-229 lands, must `rm data/app.db && docker compose up -d --build app` for the migration runner to rebuild. One-line release note in the epic; no cleanup migration needed (single-operator project).

---

## Open user decisions

**ALL RESOLVED 2026-05-16.** PM is cleared to enter Phase 2.

### (resolved) Print layout

**Critical correction from user 2026-05-16**: "he will never print them between innings. not sure how we went wrong there. One report pre-game. Let them be a print size that fits in high school baseball back pocket."

This kills the letter-portrait recommendation from UXD round 1. New constraints:
- **Single pre-game print.** Bundle is generated once and distributed in the dugout before the game.
- **Cards must fit in a HS baseball back pocket** (roughly 4–5" wide, 5–6" tall when folded; cards survive in the pocket through a 7-inning game).
- Coach materials (call sheet + prep page) stay standard letter — those live in the dugout/clipboard, not a pocket.

**User answer**: **(a) Quarter-letter cards, 4-up cut**.

Final bundle:
- Page 1 (letter landscape): Call sheet
- Page 2 (letter landscape): Prep page
- Page 3 (letter portrait, 4-up): LF | CF / RF | 3B
- Page 4 (letter portrait, 4-up): SS | 2B / blank | blank

Card geometry: 4.25" × 5.5" portrait. Coach prints once, cuts on midlines, hands out 6 cards.

### Implementation-time considerations (not blocking, surface to UXD/SE during Phase 2)
1. **Cramped real estate**: 4.25" × 5.5" with field SVG + sidebar lookup + header + legend is TIGHT. UXD will need to compress or restructure (e.g., put zone-letter lookup on the back of each card, or fold the sidebar into compact pills under the SVG). Story candidate: "compact card layout for quarter-letter geometry."
2. **Two blank slots on sheet 2**: fill with something useful (mini-legend? team-aggregate density mini? compact opponent stat summary?) or leave blank. Cosmetic, UXD's call.

### (resolved) Handedness for v1
Locked 2026-05-16 as single averaged star — see Locked decisions / User-decided. Permanent design choice based on data availability.

---

## Edge cases / Technical Notes for the epic

1. **First-game-against-new-opponent** (coach flagged): zero prior BIP data → cards still render with "Not enough spray data" message (the 0-14 tier). Named edge case in the epic, not impl-time discovery.
2. **Atomicity invariant**: `team_position_aggregate` + `batter_positioning` refresh in same transaction. Add to TN.
3. **Single-source provenance for star**: engine is only writer; readers don't shadow-store or recompute. Add to TN.
4. **Mandatory branch implementation** (E-229 TN-N, copy E-228's TN-9 forward): no auto-merge at closure; pull worktree back into `epic/E-228-defensive-positioning-cards` branch; user dev validation gates merge to main.
5. **Batting-order data dependency** (coach flagged for DE round-2): DE confirms in round 2 whether batting order is available from the scouting pipeline. If not, call sheet falls back to alphabetical-by-name; batting-order sort becomes a future enhancement.
6. **Tier 2 LLM input contract**: dedicated story to lock the schema (deviation + aggregate context inputs) before implementation.
7. **Marker collision**: render-layer concern by default; engine emits cluster hints only if cheap (DE round-2).

---

## Data-engineer round 2 (RESOLVED 2026-05-16)

DE round-2 came back clean — **zero new schema beyond Q-1**, all five items are render-layer + JOIN tweaks. Summary:

1. **Jersey** → JOIN through `team_rosters` (`team_id, player_id, season_id` → `jersey_number TEXT`). Already populated. No denormalization onto `batter_positioning` (roster is authoritative; mid-season jersey changes would silently disagree). Edge case for renderer: `jersey_number` is nullable — UXD/SE pick fallback (last initial vs "?" vs omit). Locked: **last initial** (so call sheet can still yell something).
2. **Raw BIPs for spray-density background** → direct JOIN to `spray_charts (x, y)` filtered by `chart_type='offensive' AND x IS NOT NULL AND y IS NOT NULL`. All required columns already exist on `spray_charts`. Same `(x, y)` pool fuels all 6 cards (whole team spray projected behind each card — feature, not bug).
3. **`is_low_confidence` at render** → read per-position row from `team_position_aggregate`. No schema change beyond what Q-1 already specifies. Subtlety: under whole-spray-centroid all 6 rows share the same `bip_count`/`is_low_confidence` (redundant but cheap); schema supports either regime if we ever reverse.
4. **Marker-collision offset** → **pure render-layer concern, no engine hint, no schema column.** Engine emits `(zone_id, direction_deviation, depth_deviation)`; renderer does collision detection in canvas space. DE recommends deterministic radial jitter on collision, ε pixels outward from cluster centroid, stable angular order keyed on jersey number. SE picks algorithm at impl time. **Real engineering work — DE flagged this should be a dedicated story** so SE knows jitter is a real ask, not "draw pills at coordinates."
5. **Mixed-orientation bundle** → 2 orientations, not 3 (call sheet + prep page both landscape; cards portrait). E-228 already established the `@page` pattern on the same template. One additional named `@page` (or reuse `@page call-sheet` for prep page). No renderer wrinkle; WeasyPrint handles named pages.

### Render-layer JOIN patterns locked (TN material)
- Jersey: `batter_positioning JOIN team_rosters USING (team_id, player_id, season_id)`
- Spray background: `spray_charts WHERE team_id=? AND season_id=? AND perspective_team_id=? AND chart_type='offensive' AND x IS NOT NULL AND y IS NOT NULL`
- Aggregate star: `team_position_aggregate WHERE team_id=? AND season_id=? AND perspective_team_id=?` (6 rows, one per position)

---

## Agent state (as of 2026-05-16)

| Agent | State | Role for E-229 |
|---|---|---|
| pm | Alive, just respawned with E-229 brief | Discovery + planning + status |
| coach | Alive | Round 1 + round 2 (handedness) DONE |
| uxd | Alive | Round 1 DONE |
| de | Alive | Round 1 DONE, round 2 (5 items) in flight |
| se | Shut down | Respawn at dispatch |
| cr | Shut down | Respawn at dispatch |
| docs | Shut down | Respawn at closure |
| arch | Shut down | Respawn at closure |

**Team name**: `e228-positioning` (still using E-228's team for continuity).

---

## References

### E-228 artifacts (on `epic/E-228-defensive-positioning-cards` branch, NOT yet merged to main)
- Epic: `epics/E-228-defensive-positioning-cards/epic.md`
- Engine: `src/reports/positioning.py`
- Render: `src/reports/renderer.py`, `src/api/templates/reports/positioning_cards.html`
- LLM: `src/reports/positioning_llm.py`
- Migration: `migrations/002_batter_positioning.sql` (will be rewritten in place for E-229)
- Design spec + mockup: `.project/research/E-228-positioning-cards-design-spec.md`, `.project/research/E-228-positioning-cards-mockup.html`
- User's mockup of E-229 visual concept: `Screenshot 2026-05-16 at 8.46.52 AM.png` (repo root)

### Related ideas
- `IDEA-073` (Team-Wide Base Defensive Alignment) — promoted to E-229 core scope.
- `IDEA-072` (Clustering-Derived Empirical Fielding Zones) — future work, gated on calibration.
- `IDEA-074` (Borderline-Case Flag) — likely retire; categorical concept under retired model.
- `IDEA-076` (Coverage-Cue Full-Fidelity Restoration) — unrelated to E-229.
- ~~Handedness-aware positioning (fast-follow)~~ — explicitly NOT captured. Locked as structural choice; underlying constraint is data availability, not v1 simplicity.

### Conversation provenance
- Source: design conversation between user and main session that closed E-228 dispatch and surfaced E-229 framing.
- All three expert consultations (coach, uxd, de) went through main-session relay due to peer-DM drop pattern.

---

## How planning proceeds from here

1. ~~Handedness decision~~ — locked 2026-05-16 (single averaged star, structural).
2. ~~Print layout decision~~ — locked 2026-05-16 (quarter-letter 4-up).
3. ~~DE round 2 response~~ — landed 2026-05-16, zero new schema beyond Q-1.
4. **PM enters Phase 2**: writes DRAFT epic + stories using locked decisions + epic Technical Notes built from the answer trail. **All gates cleared.**
5. PM runs quality checklist.
6. Phase 3 (internal review cycle), Phase 4 (Codex spec review), Phase 5 (READY gate).
7. User dispatches with `implement E-229` (per dispatch authorization gate) or `implement E-229 and review`.
