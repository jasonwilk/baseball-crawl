# E-265-03: ux-designer layout spec for the Outings Breakdown

## Epic
[E-265: Pitcher Outings Breakdown](epic.md)

## Status
`TODO`

## Description
After this story is complete, there is a concrete, implementable layout spec for the Outings Breakdown section that E-265-02 builds against: the per-pitcher grouping (season summary line heading a per-appearance outing log), the per-outing column set/order and mobile column tiering (`mob-hide`/`mob-hide-extra`), the native `<details>` disclosure structure with a `<summary>`-line green indicator, the GREEN strong-outing treatment, the small-sample caveat badges, the season-line inline-text shape, the Opp-column truncation, the print-pagination override, and how plays-derived values (FPS%, HR-allowed) are indicated as computed-from-plays.

## Context
Prior ux discovery exists at `.claude/agent-memory/ux-designer/design_pitcher_outings_breakdown.md` (epic TN-8) and is the implementable basis — with three v1 reconciliations forced by the resolved stat set and the operator's highlight decision (below), plus the internal-review refinements folded into the ACs. The final column set is fixed by baseball-coach (epic TN-2 per-outing row, TN-3 season line); this story maps those to layout, it does not re-pick stats. Both co-owners (ux + SE) ruled INLINE (Resolved Decision #2), so the spec targets an inline section, not a partial.

Three reconciliations vs. the prior ux memory (v1):
1. **GREEN-only** — drop the memory's `.outing-exploit` red accent; only the `.outing-strong` green treatment remains (operator decision, epic TN-4).
2. **No Result (W/L/T) form-chip** — baseball-coach dropped the Result column (team result ≠ pitcher performance, can mislead), so the memory's Date-cell form-chip is OUT of v1.
3. **HR distinct, no combined-XBH** — coach's per-outing row shows HR (home runs allowed) as its own column; the memory's combined-XBH column is OUT of v1 (XBH deferred with the extended stats, IDEA-143).

## Acceptance Criteria
- [ ] **AC-1**: The spec defines the per-outing row column set and order exactly matching epic TN-2 (`Date | Opp | IP | BF | H | HR | BB | K | R | FPS% | ERA(game)`), assigns each column a tier (always-visible vs `mob-hide-extra` vs `mob-hide`, reusing the existing 640px breakpoint classes — no new responsive mechanism), and specifies the Opp column's ellipsis truncation (`overflow:hidden; text-overflow:ellipsis; white-space:nowrap` + `title` for hover, matching the `.spray-card-identity` pattern) so a long opponent name does not blow up column width at 375px (finding F16).
- [ ] **AC-2**: The spec defines the per-pitcher season summary line as wrapping INLINE text (middot-separated, matching the `.key-player-stats`/`.exec-summary` pattern — NOT a rigid table row; finding F17), carrying the full season context per epic TN-3 (IP, G, GS, ERA, WHIP, FPS%) plus the rate set K/BF | BB/INN | K/BB | H/BF, the small-sample caveat badge treatment (flagged when season `ip_outs < 45`; K/BB shows its BB count when season `bb < 5`), and the zero-BB K/BB treatment that reads as a command STRENGTH distinct from a genuine no-data "—" (per the coach+ux F11 ruling — see Notes) — consistent with `.claude/rules/display-philosophy.md` (badge, never suppress/dim), epic TN-3.
- [ ] **AC-3**: The spec defines the native `<details>`/`<summary>` disclosure structure (default-collapsed on screen, force-open for print via the pure-CSS override, 44px `<summary>` touch target) WITH a lightweight green indicator on the `<summary>` line when ≥1 outing inside is green-flagged (so the "respect this arm" signal reads without expanding — finding F13); the GREEN `.outing-strong` row treatment for a flagged outing with NO red/exploit accent anywhere (epic TN-4); and a print-pagination override for the outings table (`page-break-inside: auto` on the table, keeping `tr` avoid) so a 15-20-row log does not force a large blank gap under the sitewide `table{page-break-inside:avoid}` rule (finding F14).
- [ ] **AC-4**: The spec resolves the plays-derived indication (FPS%, HR-allowed) to a SECTION-LEVEL note under the `<h2>` (mirroring the existing `.sort-annotation` idiom — NOT per-column badges, since no per-column badge precedent exists and the plays columns interleave with boxscore columns; finding F15), and records that the section is INLINE per Resolved Decision #2.
- [ ] **AC-5**: The spec is implementable by E-265-02 with no further stat/column/display decisions required (it maps the fixed TN-2/TN-3 stat set to concrete markup/classes and pins the zero-BB treatment; it does not introduce stats beyond that set — extended Group-C stays deferred to IDEA-143).

## Technical Approach
Build on the existing ux memory (epic TN-8), applying the three v1 reconciliations above, the season-summary-line inline layout (new vs the memory, which covered only the per-outing table), and the internal-review refinements (F13 summary indicator, F14 print override, F15 section-level note, F16 Opp ellipsis, F17 inline season line, F11 zero-BB treatment). Produce the spec as `.project/research/E-265-outings-layout-spec.md` — the single pinned artifact path E-265-02 consumes, referenced by absolute path in the handoff. (ux may also update its own `.claude/agent-memory/ux-designer/design_pitcher_outings_breakdown.md` as working notes, but the implementable spec E-265-02 builds against is the `.project/research/` artifact.) Design deliverable — no implementation.

## Dependencies
- **Blocked by**: None (the rate set is resolved — epic TN-3 / Resolved Decision #1 — so the column set is final)
- **Blocks**: E-265-02

## Files to Create or Modify
- `.project/research/E-265-outings-layout-spec.md` (new — the single pinned layout spec artifact E-265-02 consumes)
- `.claude/agent-memory/ux-designer/design_pitcher_outings_breakdown.md` (optional — ux's own working notes; NOT the E-265-02 consumer artifact)

## Agent Hint
ux-designer

## Handoff Context
- **Produces for E-265-02**: the implementable layout spec at `.project/research/E-265-outings-layout-spec.md` (column tiers + Opp ellipsis, `<details>` structure + `<summary>` green indicator, `.outing-strong` green treatment, print-pagination override, small-sample badges, inline season-line placement + zero-BB treatment, section-level plays-derived note) — E-265-02 loads this path as deferred context.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Spec is implementable by E-265-02 with no residual stat/column/display decisions
- [ ] Spec artifact is written to `.project/research/E-265-outings-layout-spec.md` and referenced by that path in the Handoff Context for E-265-02

## Notes
This is a design deliverable, not implementation. The stat set is fixed upstream (coach, epic TN-2/TN-3); the spec's job is layout, tiering, disclosure, and the green/badge treatments. **F11 zero-BB K/BB treatment (pinned during refinement):** when season BB = 0, render K/BB as a **"0 BB" strength badge** in place of the ratio — NO fraction (`12/0` reads like a data error) and NO `∞` (jargon this report avoids) [baseball-coach]; style it per the report's existing count-badge convention (the same idiom as the K/BB `bb < 5` BB-count badge), placed inline in the middot season line and visually distinct from the genuine no-data "—" [ux]. Zero open display decisions remain.
