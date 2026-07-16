# E-265: Pitcher Outings Breakdown

## Status
`COMPLETED`
<!-- READY set 2026-07-16 (operator-approved; freshness clock starts here — re-confirm by 2026-09-14 if not yet dispatched). Hardened through internal review iter 1 (19 findings) + Codex spec review iter 1 (2 findings), all accepted. -->
<!-- Dispatch BLOCKED on E-264 completing (hard blocker) and requires SEPARATE operator authorization — READY marks planning-complete, not dispatch. -->
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- READY freshness gate: re-confirm against docs/ROADMAP.md or demote to DRAFT if READY > 60 days (by 2026-09-14). -->

## Overview
Add a new per-pitcher, game-by-game **Outings Breakdown** section to the standalone scouting report — a log of each opponent pitcher's individual outings (one row per appearance) plus a per-pitcher season summary line, so a coach preparing to FACE this staff can see how each arm has actually performed outing to outing, not just in season aggregate. The per-outing row shows raw boxscore counts plus FPS% and per-outing ERA; the season line adds four rate stats (K/BF, BB/INN, K/BB, H/BF). Env-flag gated (`FEATURE_PITCHER_OUTINGS`), off by default until proven.

## Background & Context
This epic promotes coaching value identified during E-263 (Deep Scout) formation and the pitcher-outings consultations. Rich prior discovery already exists (see Technical Notes TN-8); this epic was created as a STUB capturing operator-confirmed decisions and refined 2026-07-15 after four expert consultations (baseball-coach, data-engineer, software-engineer, ux-designer), then hardened by internal review iteration 1 (code-reviewer spec audit + the four experts' holistic review — 19 findings incorporated).

The report today shows season-aggregate pitching only. Coaches also want per-outing detail (workload, recent form, how each arm gets outs). Because opponent season-stats is 403, everything is derived from data we already store: per-game boxscores (`player_game_pitching`) plus the plays we ingest (`plays`/`play_events`). No new crawling and no migration are required.

This epic is **blocked by E-264** (League-Aware ERA Basis Fix, READY): the outings log displays a per-outing ERA, which MUST use E-264's corrected per-team-season `innings_per_game` basis. E-265 must not ship a per-outing ERA on the old hardcoded 9-inning basis, and must not re-touch E-264's two ERA computation sites. (E-264 ships no reusable basis accessor — see TN-5 for how E-265 obtains the basis.)

## Goals
- A flag-gated per-pitcher Outings Breakdown section renders in the standalone scouting report: one row per appearance, grouped under a per-pitcher season summary line.
- The per-outing row shows the coach-curated column set (TN-2); the season line shows the coach-curated rate set (TN-3) with small-sample caveats.
- Play-by-play-derived values (FPS%, HR-allowed) are clearly indicated as computed from play-by-play (not official GameChanger boxscore stats), via a section-level note (TN-2 / E-265-03).
- Per-outing and season ERA are computed on E-264's corrected `innings_per_game` basis.
- Stronger outings are highlighted GREEN per the coach thresholds (TN-4), consistent with the report's existing heat/green convention. No red "exploit" flags.

## Non-Goals
- Velocity / pitch-mix stats (0%/~1% data coverage — not computable).
- W/L/SV decisions (unrecorded in our data).
- **Extended Group-C whiff/batted-ball stats — swinging-strike%, K-looking-vs-swinging, GO/AO, GB/FB%.** These were in the aspirational stub TN-2 but were trimmed from v1 by baseball-coach's column curation (TN-2/TN-3) and data-engineer's derivation-risk assessment (GO/AO needs a batted-ball outcome-string classifier; true GB/FB% is unreliable because hit trajectory is frequently absent from `plays.outcome`). Deferred to **IDEA-143**.
- **S% (strike%) per outing** — coach dropped it as redundant with the more actionable FPS%.
- Group-E derived stats (FIP / BABIP / pitcher-LOB) — out of scope.
- Red "exploit"/weakness flags — the operator declined to change the report's current highlight philosophy (GREEN-only).
- Any new crawling or migration for stat data (derive from already-stored boxscore + plays). E-264 provides the `innings_per_game` column; this epic reads it.
- A reusable `{% include %}` report-section framework — the section is added INLINE (Resolved Decision #2). A deliberate size-driven template split is deferred to **IDEA-144**.

## Success Criteria
- With `FEATURE_PITCHER_OUTINGS` set, the report renders the Outings Breakdown; unset, the report is byte-identical to the post-E-264 baseline golden — the flag-off path adds and removes nothing (proven by a flag-unset golden test showing zero diff against the post-E-264 golden, mirroring `FEATURE_PREDICTED_STARTER`).
- Each per-outing row shows the TN-2 columns; each per-pitcher season line shows the TN-3 rate set (K/BF, BB/INN, K/BB, H/BF) with the TN-3 small-sample caveats.
- Per-outing ERA equals `ER × (innings_per_game × 3) / ip_outs` on the scouted team's E-264 basis (fallback 7); every displayed per-outing ERA is read alongside its IP column (never suppressed; the adjacent IP column is the sample context — no separate badge markup).
- An outing is highlighted GREEN iff it meets a TN-4 criterion and clears the TN-4 sample floor.
- `python -m pytest tests/` is green (new derivation + render tests plus the flag-on/flag-off pair).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-265-01 | Per-pitcher per-appearance derivation layer (boxscore + FPS%/HR-allowed from plays; per-outing ERA on E-264 basis; season rate line; green-outing flag) | DONE | E-264 (epic) | software-engineer |
| E-265-02 | Renderer + template: flag-gated inline Outings Breakdown section | DONE | E-264 (epic), E-265-01, E-265-03 | software-engineer |
| E-265-03 | ux-designer layout spec (columns, tiering, disclosure, green treatment, small-sample badges) | DONE | None | ux-designer |
| E-265-04 | docs-writer coaching how-to for the Outings Breakdown | DONE | E-265-02 | docs-writer |

## Dispatch Team
- software-engineer (E-265-01, E-265-02)
- ux-designer (E-265-03)
- docs-writer (E-265-04)
<!-- baseball-coach advisory (stat set + green thresholds — see Resolved Decisions / TN-4). data-engineer NOT required: Non-Goals bar any migration, so there is no schema to design; the derivation is read-only reuse of existing query surface + Python plays-derivation. -->

## Technical Notes

### TN-1: Env-flag gate
`FEATURE_PITCHER_OUTINGS`, mirroring the `FEATURE_PREDICTED_STARTER` pattern exactly. A module-level `is_pitcher_outings_enabled()` (owned by E-265-01) reads the env var with the same `.lower() in ("1","true","yes")` shape as `is_predicted_starter_enabled()` (`src/reports/starter_prediction.py:26`). Off by default. The byte-identical-when-unset contract is delivered by a BOOLEAN-gated template section (`{% if show_pitcher_outings %}` … `{% endif %}`, mirroring `scouting_report.html:528`), not by the builder alone — passing an empty/None structure when the flag is off is fine as long as the section is boolean-gated.

### TN-2: Per-outing row — stat scope (baseball-coach curated)
One row per pitching appearance. Columns (coach-final ~11-col trim):

`Date | Opp | IP | BF | H | HR | BB | K | R | FPS% | ERA(game)`

- Boxscore-direct (from `player_game_pitching`): IP (from `ip_outs`), BF, H, BB, K (`so`), R.
- **Plays-derived (no per-game boxscore column exists — data-engineer confirmed):** HR-allowed (count of PAs vs this pitcher whose `plays.outcome = 'Home Run'` — the single canonical HR value, no grand-slam / inside-the-park variants; mirror the `recon_scoreboard`/`plays_parser` convention with a module-local `_HR_OUTCOMES = frozenset({'Home Run'})`) and FPS% (`is_first_pitch_strike` over the charted-PA denominator `pitch_count > 0`).
- Per-outing ERA(game): see TN-5.
- **Raw counts, not per-outing rates** (coach ruling): a single outing is too small a sample to normalize (2 K in 0.2 IP is a nonsensical rate but a legible count), and counts match how GameChanger's own boxscore shows a single game.
- **Plays-derived indication:** FPS% and HR-allowed are surfaced as computed-from-plays via a SECTION-LEVEL note under the `<h2>` (mirroring the existing `.sort-annotation` idiom), NOT per-column badges — there is no per-column badge precedent on the report and the plays columns are interleaved among boxscore columns (ux resolution, E-265-03).

### TN-3: Per-pitcher season summary line — rate set (baseball-coach curated; IDEA-141 resolution + operator F10 add)
Each pitcher's outing log is headed by a season summary line carrying the standard season context (IP, G, GS, ERA on the E-264 basis, WHIP, FPS%) plus the rate set:

`K/BF | BB/INN | K/BB | H/BF`

- **Drop BOTH the invented K/9 AND GameChanger's K/G on this section.** Rationale (coach): this is a brand-new surface with no legacy number to protect, so the "coaches expect traditional K/9" argument that kept E-264 from touching the *existing* pitching-table K/9 does NOT transfer here. K/BF (miss-bats rate, BF denominator) sidesteps the innings-per-game basis question entirely — no per-team asterisk/footnote machinery like E-264's ERA disclosure — and is more tactically honest for prepping to face an arm (independent of choppy HS relief IP). BB/INN is GameChanger's real per-inning field (not our invented BB/9). K/BB (best single quality number at this level) shares its numerator with K/BF.
- **H/BF (hits-allowed rate) — operator RIDE decision (review finding F10).** WHIP conflates walks and hits into one number, so it cannot tell a coach whether a pitcher's baserunners come from bad control (walk-heavy → sit on strikes) vs. getting hit hard (hit-heavy → attack early). No hits-allowed RATE exists anywhere on the report today (the existing season pitching table shows raw H + WHIP but no BAA/H-rate — verified). H/BF is trivial Group-B arithmetic (we already carry H + BF per outing) and is a distinct contact/hits axis — NOT a fourth competing strikeout-rate view, so it does not violate coach's "three focused strikeout/walk numbers" guidance.
- The existing report pitching-table K/9 (a DIFFERENT surface) is unchanged by this epic.
- **Small-sample caveat (coach; applies to all four rate stats).** Flag the rate stats when the pitcher has fewer than **15 IP** — the exact, testable predicate is `season ip_outs < 45` (15 × 3). (Coach's "~40 BF" was the informal BF-scale equivalent; the single pinned trigger is the IP predicate.) K/BB additionally badges its underlying **BB count when `season bb < 5`** (very few walks make the ratio numerically unstable). Never suppress — badge the IP/BB count inline, consistent with `.claude/rules/display-philosophy.md`.
- **K/BB when BB = 0 (review finding F11):** the derivation MUST return a value that DISTINGUISHES the zero-walk case (a command STRENGTH — never walks anyone) from the genuine no-data case; both otherwise collapse to a blank. **Pinned presentation (coach + ux):** render K/BB as a **"0 BB" strength badge** in place of the ratio — NO fraction (`12/0` reads like a data error) and NO `∞` (jargon this report avoids); style it per the report's existing count-badge convention (the same idiom as the `bb < 5` BB-count badge above), inline in the season line and visually distinct from the genuine no-data "—". The derivation returns the distinguishable zero-BB marker so the renderer can apply this badge.

### TN-4: Green-highlight thresholds (baseball-coach; GREEN-only, respect direction)
The operator fixed GREEN-only highlighting (no red exploit flags). On an opponent report, a green-highlighted outing reads "this arm shut hitters down — respect it, don't get cute." An outing is highlighted GREEN iff it meets **ANY ONE** of these (OR, not AND — one standout signal is meaningful):
1. **Command:** BB = 0 across an outing of IP ≥ 3.
2. **Aggression:** FPS% ≥ 65% across a **charted-PA count ≥ 10** (charted PA = `pitch_count > 0`, the FPS% denominator — NOT raw boxscore BF; a quick-scored outing with BF = 12 but only 4 charted PAs must NOT green off 4 pitches of real data — review finding F8).
3. **Dominance:** K ≥ ⅔ of BF (per-outing K/BF ≥ .667, computed from the boxscore K and BF on `player_game_pitching`, so no charted-PA gap) across BF ≥ 10.
4. **Shutdown:** R = 0 across an outing of IP ≥ 4 — uses R (raw runs, the column actually shown per TN-2), NOT ER, so a coach can see WHY a row is green from the visible columns.

The `.667` bar in criterion 3 is deliberately the same numeric value a coach reads as "dominant K rate" for the season K/BF stat, so a coach doesn't see two different "dominant" cuts in one section (a design-intent consistency note — TN-3's season K/BF carries only a small-sample badge, NOT a literal threshold).

**Sample floor (defensive backstop):** `no highlight when BF < 10 AND IP < 2`. Note this floor is NON-BINDING for the four criteria above — each already gates at or above it (crit 1: IP ≥ 3; crit 2: charted-PA ≥ 10; crit 3: BF ≥ 10; crit 4: IP ≥ 4) — so any criterion-meeting outing has already cleared it. It is retained as an explicit backstop guarding against a future lower-gated criterion; it is not independently testable against a green-qualifying row (review finding F2). Below-floor rows still render their raw counts plainly (never suppress, never dim; just no color).

These thresholds are illustrative-but-ready for testable ACs. baseball-coach offered an OPTIONAL one-pass gut-check of the exact numbers against real outing distributions — a nicety, NOT a blocker.

### TN-5: Per-outing ERA basis (E-264 dependency; no accessor — E-265 reads the column)
Per-outing ERA = `ER × (innings_per_game × 3) / ip_outs`, where `innings_per_game` is the SCOUTED team's `teams.innings_per_game` (E-264's column, fallback 7). `er` is stored PER GAME on `player_game_pitching` and returned by `get_pitching_history`, so per-appearance ER is directly available.

**E-264 exposes NO reusable basis accessor** (its design leaves a shared helper to the implementer and INLINES the fallback at its two season-ERA sites), and it threads `innings_per_game` onto `get_season_pitching` ONLY — NOT onto `get_pitching_history`, E-265's per-outing reader (review finding F1). So E-265 must OBTAIN the basis itself via a seam it owns: either a scalar read of `teams.innings_per_game` for the scouted team, or extend `get_pitching_history` to carry the column (with a regression check on existing consumers). Re-applying the fallback `basis = innings_per_game if innings_per_game is not None else 7` (explicit `is not None` — a bare `if not innings_per_game` would wrongly skip the fallback on a falsy `0`) is REQUIRED and is a per-outing (third) application of the same arithmetic — it is NOT what "do not re-derive the basis" prohibits. "Do not re-derive" means: do NOT re-fetch from the API, do NOT derive the basis from team classification/age, and do NOT use the old hardcoded `× 27`. Do NOT touch E-264's two SEASON-ERA sites (`generator.py:453`, `renderer.py:264`).

ERA at single-outing grain is arithmetically volatile by design (1 ER over 1 IP is high) — the adjacent IP column is the sample context (no separate badge markup needed, per `.claude/rules/display-philosophy.md` and review finding F18); return `None` (renderer shows "—") when `ip_outs = 0`, never a divide-by-zero.

### TN-6: Data source, perspective/role filter, and derivation placement (data-engineer)
All stats derive from already-stored per-game boxscore + plays (opponent season-stats is 403). Grain = one `player_game_pitching` row per appearance (its UNIQUE is `(game_id, player_id, perspective_team_id)`).

**Drive plays off the boxscore outings (review finding F12):** the plays aggregation (FPS%, HR-allowed) MUST be driven OFF the `get_pitching_history` outings — which are `g.status = 'completed'`-scoped and carry the pitching perspective filter — left-joining plays per outing's `game_id`. Do NOT independently enumerate outings from `plays` keyed by `(pitcher_id, game_id)`, which could manufacture a phantom outing from a non-completed or boxscore-less game.

**Perspective/ROLE filter (the double-count trap — mandatory at outing grain too):**
- Pitching rows (`get_pitching_history` / `player_game_pitching`): `team_id = :scouted AND perspective_team_id = :scouted`. `get_pitching_history` already applies exactly this — pass the scouted team id.
- Plays (FPS%, HR-allowed): `plays.perspective_team_id = :scouted` (dedup — neutralizes a two-perspective twin game) **AND** `plays.batting_team_id != :scouted` (ROLE — the scouted team is fielding/pitching, so the OTHER team bats) **AND** `plays.pitcher_id = :pitcher`. The `batting_team_id != :scouted` clause is the load-bearing role discriminator; `perspective = scouted` alone would double-count a two-perspective game, and it also backstops a NULL/misattributed `pitcher_id` from leaking a scouted-team-batting PA into the count.

Reuse the charted-PA `pitch_count > 0` denominator CONVENTION for FPS% (as used by `_query_plays_pitching_stats`, `generator.py:1042`) — NOT that function itself, which lacks the `batting_team_id != scouted` role clause and groups by pitcher only; E-265 writes a NEW per-`(pitcher, game)` query (review finding F7).

**NULL vs 0 is sharper at single-appearance grain:** `pitches`/`bf` and rate-stat inputs are frequently NULL for one appearance where the season SUM was fine. Rate stats (FPS%, K/BF, BB/INN, K/BB, H/BF, per-outing ERA) MUST yield `None` (renderer "—"), never 0 and never a divide-by-zero — do NOT `COALESCE(...,0)` a rate denominator. The K/BB zero-BB case (TN-3, F11) is the one place `None`-from-zero-denominator must be made DISTINGUISHABLE from `None`-from-no-data.

**Pitcher-attribution caveat (state in the docs/how-to):** per-appearance plays aggregation inherits the ~90–95% pitcher-attribution accuracy (`plays.pitcher_id` is nullable, reconciliation-corrected — see `.claude/rules/key-metrics.md`). A NULL/misattributed `pitcher_id` lands a PA in the wrong outing bucket. Fine for a directional scouting read; not a byte-exact count.

**Placement (split along the read-vs-derive seam):**
- Reuse `get_pitching_history` (`src/api/db.py`) for the per-appearance boxscore base. The one gap is the opponent faced (get_pitching_history returns `game_id`/`game_date` but not the opponent) — the implementer chooses whether to extend the shared SELECT (regression-test existing consumers if so) or resolve the opponent in the derivation module. Keep raw SQL reads in `src/api/db.py`.
- Put the plays-derivation (FPS%, HR-allowed at per-outing grain), the per-outing ERA + season rate aggregation (incl. H/BF), the green-outing flag, and the per-outing/season assembly in a NEW module `src/reports/pitcher_outings.py` — the `starter_prediction.py` / `recon_scoreboard.py` precedent (read-and-derive, writes nothing → lives in `src/reports/`, not `src/db/`).

### TN-7: Render wiring + flag placement (software-engineer)
Mirror the live Most Likely Arms wiring exactly:
- Put the `show_pitcher_outings = is_pitcher_outings_enabled()` read + the `if show_pitcher_outings:` builder call INSIDE the query/render stage's DB-connection scope in `generator.py` (the outings builder needs a DB read; it can reuse `get_pitching_history(team_id, season_id, db=conn)`, the same seam predicted-starter uses). Do NOT place the builder after the connection closes.
- Pass BOTH the typed outings structure AND the boolean into the render dict (mirror `starter_prediction` + `show_predicted_starter`); gate the whole template section on the boolean.
- **Non-fatal empty-data path:** the builder must handle "no pitching history" by producing a suppressed/empty state, not crashing — a report for a team with no pitching data must still render (mirror the predicted-starter inner `if pitching_history_rows:` guard).
- E-265 writes NO `report_generation_runs` telemetry column, so the `_RUN_RECORD_COLUMNS` allowlist footgun does not apply.

### TN-8: Prior discovery (reference — do NOT re-consult unless something changed)
- `.claude/agent-memory/baseball-coach/pitcher-outings-scouting-consultation.md` — stat ranking, artifact tiering by consumption mode, ~11-col trim. (Its two-signal red/neutral highlight recommendation is OVERRIDDEN by the operator's GREEN-only decision — see TN-4.)
- `.claude/agent-memory/ux-designer/design_pitcher_outings_breakdown.md` — placement, mob-hide column tiering, native `<details>` disclosure, heat treatment, form-chip Result, combined-XBH. (The `.outing-exploit` red accent is DROPPED — GREEN-only; the Result form-chip and combined-XBH are OUT of v1 — see E-265-03.)
- api-scout feasibility matrix (Groups A–E; derive from per-game boxscore + plays).
- Prototype `pitcher-outings.md` + CSVs (uncommitted in the working tree) — the exact computable columns.

### TN-9: Template + generator collision with E-264 (ordering note)
Both E-264 and E-265 edit `src/api/templates/reports/scouting_report.html` AND `src/reports/generator.py`, but E-265 is sequenced AFTER E-264 (hard blocker), so they run SERIALLY on the post-E-264 tree — no concurrent-edit hazard. In the template, E-264 edits the Pitching-table `<th>ERA` (~line 673) + a footnote + the key-player card inline ERA label; E-265 adds a NEW `<h2>` section block in a DIFFERENT region (e.g. after the Pitching table) and MUST NOT disturb E-264's ERA-basis label at ~line 673. In `generator.py`, E-264 edits `_compute_pitching_rates` (`:453`) and the gc_uuid fetch seam (~1994) while E-265-02 edits the query/render wiring region (~2230) — different regions; E-265-02 MUST NOT disturb E-264's fetch/compute sites (review finding F5).

## Resolved Decisions
<!-- These replace the two stub Open Questions. -->

**RD-1 — Rate stat set (owner: baseball-coach; consumes IDEA-141; H/BF added by operator F10). RULED:** the Outings Breakdown's season line shows **K/BF + BB/INN + K/BB + H/BF** — drop BOTH the invented K/9 AND GameChanger's K/G on this new section. The per-outing row shows RAW K and BB counts, not per-outing rates. H/BF is the hits-allowed rate the operator added on review (a distinct contact axis WHIP conflates; F10). Rationale and small-sample caveats in TN-2/TN-3. IDEA-141 marked PROMOTED (folded into E-265).

**RD-2 — Framework-vs-inline (owners: software-engineer + ux-designer). RULED:** add the section **INLINE** in `scouting_report.html`, mirroring the flag-gated Most Likely Arms block 1:1. Do NOT build a reusable `{% include %}` section framework for E-263 (parked, no committed consumer) — that is speculative complexity against an un-built spec ("Simple first. Complexity as needed."). Inline is the proven live precedent, is trivially reversible, and if E-263 ever revives IT can mechanically extract the self-contained inline section into a partial with real requirements in hand. A deliberate size-driven template split is captured as IDEA-144. Both co-owners (SE and ux) independently landed on inline.

## History
- 2026-07-15: Created as a STUB (DRAFT skeleton) at operator request, capturing operator-confirmed decisions. Blocked by E-264; consumed IDEA-141.
- 2026-07-15: **Refined** (DRAFT → fully specified). Four expert consultations resolved both open questions: baseball-coach ruled the K-rate set (RD-1) + green-highlight thresholds (TN-4); software-engineer + ux-designer both ruled INLINE (RD-2); data-engineer confirmed derivation feasibility and surfaced two scope corrections now folded in — (a) HR/XBH-allowed and FPS% are plays-derived, not boxscore (TN-2/TN-6); (b) the extended Group-C whiff/batted-ball stats deferred to IDEA-143. E-265-01 re-owned to software-engineer alone (no migration → no schema for data-engineer); data-engineer dropped from the Dispatch Team. IDEA-143 + IDEA-144 filed.
- 2026-07-15: **Internal review iteration 1 incorporated** (code-reviewer spec audit + coach/ux/SE/DE holistic — 19 findings, all accepted, 0 dismissed). Notable: F1 replaced the phantom "E-264 accessor" language with the concrete `teams.innings_per_game` read + required fallback re-application (TN-5); F8 gated the Aggression green criterion on charted-PA not raw BF (TN-4); F10 (operator RIDE) added H/BF to the season set (TN-3); F11 made the K/BB zero-BB case a distinguishable strength (TN-3/TN-6); F12 drove plays off the completed-game boxscore outings (TN-6). Consistency sweep clean.
- 2026-07-16: **Codex spec review iteration 1 incorporated** — 2 findings, both accepted, 0 dismissed: P1 (propagation completeness — the full season-line context set IP/G/GS/ERA/WHIP/FPS% propagated into E-265-01/02/03/04 ACs, not just the four rates) and P2 (dependency correctness — pinned the layout-spec artifact to `.project/research/E-265-outings-layout-spec.md` and made E-265-02's consumption explicit via a Handoff Context "Consumes" reference). Consistency sweep clean.
- 2026-07-16: Set **READY** (operator-approved). Both open questions resolved (RD-1 rate set = K/BF + BB/INN + K/BB + H/BF; RD-2 inline); operator decisions F10 (add H/BF) + F11 (0-BB "0 BB" strength badge) incorporated. Freshness clock starts 2026-07-16 (re-confirm by 2026-09-14 if not yet dispatched). **Dispatch remains BLOCKED on E-264 completing (hard blocker) and requires SEPARATE operator authorization** — READY marks planning-complete, not dispatch.
- 2026-07-16: **Dispatched, implemented, and reviewed** (operator-authorized "implement E-265 and review"; E-264 hard blocker cleared same day). All 4 stories shipped: **E-265-01** derivation layer (new `src/reports/pitcher_outings.py` — per-appearance boxscore + plays-derived FPS%/HR-allowed, per-outing ERA on E-264's `teams.innings_per_game` basis via `era_basis_innings`, season rate line K/BF+BB/INN+K/BB+H/BF, green-outing flag); **E-265-03** layout spec (`.project/research/E-265-outings-layout-spec.md`); **E-265-02** renderer + flag-gated INLINE template section (`generator.py` wiring in DB-connection scope, three render-boundary Jinja rate filters `pct`/`rate`/`rate2` in `renderer.py`, inline section + scoped CSS in `scouting_report.html`); **E-265-04** coaching how-to (`docs/coaching/pitcher-outings-breakdown.md`). Each code story passed per-story code-reviewer + PM AC verification serially. **Phase 4 Codex code review → 3 findings, all accepted/remediated:** F1 (gate the outings `<style>` CSS under the same `{% if show_pitcher_outings %}` so a flag-OFF report is truly byte-identical to a pre-feature render — CR refuted it as a code defect on the always-on-CSS precedent, but **PM ruled FIX on AC intent**: epic.md:39's "adds and removes nothing" is the goal, "mirroring FEATURE_PREDICTED_STARTER" only the how-guide, and gating the CSS is the sole reading where both clauses hold + makes the off-by-default kill switch provably inert); F2 (`SeasonSummary.games_started` → `int | None`, rendering "—" not a false "0 GS" for an all-NULL `appearance_order` scope, mirroring `get_season_pitching`'s unknown-vs-zero semantics — a real coach-facing correctness fix); F3 (per-pitcher blocks sorted season-IP-desc, matching the Pitching table / spec §4). All ACs re-verified post-remediation. **Step 1c Closure CR Integration Review APPROVED** (1 SHOULD FIX — a stale code comment — fixed). Full-suite green gate + Step 1d runtime smoke pending at Step 8.

### Dispatch & Closure Review Scorecard
| Review pass | Findings | Accepted | Dismissed |
|-------------|---------:|---------:|----------:|
| Per-story CR — E-265-01 | 1 | 1 | 0 |
| Per-story CR — E-265-03 | 4 | 4 | 0 |
| Per-story CR — E-265-02 | 2 | 2 | 0 |
| Per-story CR — E-265-04 | 3 | 3 | 0 |
| Closure CR Integration Review | 1 | 1 | 0 |
| Codex (code review) | 3 | 3 | 0 |
| **Total** | **14** | **14** | **0** |

Notes: per-story CR — E-265-01 SHOULD FIX (zero_bb distinguishability); E-265-03 2 MUST (flag-off gate, field-name corrections) + 2 SHOULD (throws drop, rate-formatting filters); E-265-02 1 MUST + 1 SHOULD; E-265-04 3 SHOULD (docs polish). Codex F1/F2/F3 (F1 refuted-as-code-defect by CR but **PM ruled FIX on AC intent → counted accepted**; F2/F3 straight accepts). Zero dismissals across the whole dispatch.

### Documentation Assessment (closure)
**FIRES.** (a) The coaching how-to `docs/coaching/pitcher-outings-breakdown.md` shipped as E-265-04 (in-scope story, not a separate dispatch). (b) docs-writer additionally dispatched at closure to add `FEATURE_PITCHER_OUTINGS` to the `docs/admin/operations.md` feature-flags table (parity with `FEATURE_PREDICTED_STARTER`). Both recorded; no other doc surface impacted.

### Context-Layer Assessment (Step 3a) — 8-trigger verdicts
1. **New convention/pattern/constraint? NO** — reused existing patterns (flag-gated section à la predicted-starter, read-and-derive `src/reports/` module, render-boundary Jinja rate filters).
2. **Architectural decision w/ ongoing implications? NO** — reused the `era_basis_innings` + `get_pitching_history` seams; no new tech choice.
3. **Footgun/failure mode discovered? YES** — two review-caught lessons, recorded here (NOT codified this epic — see triggers 7/8): (a) a new derived read-surface must MIRROR the existing surface's unknown-vs-zero (NULL) semantics, not coerce to 0 (Codex F2 — outings `games_started` returned 0 where `get_season_pitching` returns None for an all-NULL `appearance_order` scope); (b) a flag-gated report section's kill switch must gate its CSS too, not just body markup, for a truly byte-identical off state (Codex F1).
4. **Agent behavior/routing/coordination change? NO.**
5. **Domain knowledge for future epics? NO** — pitcher-outings stat defs / green thresholds are epic-specific (live in the epic + baseball-coach memory).
6. **New CLI command/workflow/procedure? NO** — `FEATURE_PITCHER_OUTINGS` is a feature flag (now in operations.md), not a CLI command.
7. **Net context-layer growth ratchet? YES — FAILS, disposed via OPERATOR-SIGNED EXCEPTION (operator approved 2026-07-16).** Ratchet is +304 over the 2026-07-13 baseline: **+275 is pre-existing drift on main** (agent-memory accumulation since the E-262 baseline snapshot, NOT E-265) and **+29 is E-265's own** (UXD's optional design memo `.claude/agent-memory/ux-designer/design_pitcher_outings_breakdown.md`, a legitimate design deliverable). Operator elected a signed exception; baseline cleanup deferred to a separate operator pass. No offset performed.
8. **Reusable behavioral lesson (gated promote)? CANDIDATE but NOT promoted** — the F1/F2 lessons (trigger 3) are defect-cited, but promotion is gated on fitting the ratchet baseline (already over) and no prior-epic recurrence is on record. Recorded in History (zero-growth home) rather than codified. Revisit if it recurs.

**Net disposition:** triggers 3 and 7 fire (8 candidate); all dispositioned by History record + the operator-signed trigger-7 exception. **No new context-layer codification this epic** (respects the E-262 meta-layer freeze + the over-baseline ratchet) → claude-architect NOT spawned. No deletions/renames → no eviction sweep.

### Review Scorecard (planning phase)
| Review pass | Findings | Accepted | Dismissed |
|-------------|---------:|---------:|----------:|
| code-reviewer (spec audit) | 6 | 6 | 0 |
| baseball-coach (holistic) | 3 | 3 | 0 |
| ux-designer (holistic) | 6 | 6 | 0 |
| software-engineer (holistic) | 4 | 4 | 0 |
| data-engineer (holistic) | 2 | 2 | 0 |
| Codex (spec review) | 2 | 2 | 0 |
| **Total** | **23 raw → 21 distinct** | **21** | **0** |

Notes: internal iteration 1 raw counts sum to 21 across five sources; three findings were double-raised — F1 (code-reviewer + software-engineer, the phantom E-264 accessor), F4 (code-reviewer + software-engineer, flag-reader ownership), and F-HR (software-engineer + data-engineer verify, the `'Home Run'` literal) — deduplicating to **19 distinct internal findings**. Codex added **2** (P1, P2). All accepted, none dismissed; both open questions resolved and both operator decisions (F10, F11) incorporated. Two consistency sweeps (post-internal, post-Codex) came back clean.
