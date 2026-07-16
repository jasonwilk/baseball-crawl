# E-265-02: Renderer + template — flag-gated inline Outings Breakdown section

## Epic
[E-265: Pitcher Outings Breakdown](epic.md)

## Status
`DONE`

## Description
After this story is complete, the standalone scouting report renders a per-pitcher Outings Breakdown section INLINE in `scouting_report.html` behind the `FEATURE_PITCHER_OUTINGS` flag, consuming the E-265-01 derivation and following the E-265-03 layout spec: per-pitcher season summary line + a per-appearance outing log, green highlighting on strong outings, mobile column tiering, and a native `<details>` disclosure. With the flag unset the report is byte-identical to the post-E-264 baseline.

## Context
This is the coach-facing surface. Per Resolved Decision #2 (epic), the section is added INLINE mirroring the live Most Likely Arms block (`{% if show_predicted_starter %}` at `scouting_report.html:528`) — NOT via a new `{% include %}` framework. The flag reader (defined in E-265-01) and wiring mirror `FEATURE_PREDICTED_STARTER` (epic TN-1/TN-7). The green highlight follows the coach thresholds computed in E-265-01 (epic TN-4); plays-derived values (FPS%, HR-allowed) are indicated as computed-from-plays via a section-level note per the E-265-03 treatment (epic Goals / TN-2). Follow `.claude/rules/jinja-safety.md`. See epic TN-9 for the E-264 template + generator collision ordering note. The E-265-03 layout spec this story implements against is the artifact at `.project/research/E-265-outings-layout-spec.md`.

## Acceptance Criteria
- [ ] **AC-1**: With `FEATURE_PITCHER_OUTINGS` set, the Outings Breakdown renders per the E-265-03 layout spec; with the flag UNSET the report is byte-identical to the **post-E-264 baseline golden** (E-264, a hard blocker, regenerates the golden with corrected ERA — the flag-off reference is that post-E-264 golden, NOT a pre-E-264 one; the flag-unset golden test produces zero diff against it and no section markup is present) (finding F6). The section is gated on the boolean passed into the render dict, mirroring `show_predicted_starter` (epic TN-1/TN-7).
- [ ] **AC-2**: The section is added INLINE in `scouting_report.html` (Resolved Decision #2) — no `{% include %}` section-framework is introduced — and does NOT disturb E-264's ERA-basis `<th>` label at ~line 673 or E-264's `generator.py` fetch/compute sites (epic TN-9).
- [ ] **AC-3**: Plays-derived values (FPS%, HR-allowed) are indicated as computed from play-by-play (not official GameChanger boxscore stats) via a SECTION-LEVEL note under the `<h2>` (the resolved treatment — NOT per-column badges), per the E-265-03 spec (epic Goals / TN-2, finding F15).
- [ ] **AC-4**: An outing carrying E-265-01's green "strong-outing" flag renders with the GREEN `.outing-strong` treatment from E-265-03; no outing renders a red/exploit flag (epic TN-4, GREEN-only). Because outings sit inside a default-collapsed `<details>`, the `<summary>` line carries a lightweight green indicator when ≥1 outing inside is flagged, so the "respect this arm" signal reads without expanding (E-265-03, finding F13). Per-outing ERA displays E-265-01's basis-corrected value read alongside its adjacent IP column (no separate badge markup — finding F18); a `None` ERA or `None` rate renders as "—", not 0 (epic TN-5/TN-6).
- [ ] **AC-5**: The season summary line renders as wrapping inline text (middot-separated, NOT a rigid table row — E-265-03, finding F17) carrying the full season context per epic TN-3 (IP, G, GS, ERA, WHIP, FPS%) PLUS the rate set K/BF | BB/INN | K/BB | H/BF, with the small-sample caveat treatment from E-265-03 (flagged when season `ip_outs < 45`; K/BB shows its BB count when season `bb < 5`; a 0-walk pitcher's K/BB renders as a "0 BB" strength badge per the E-265-03 F11 treatment (not a `12/0` or `∞` ratio), visually distinct from a genuine no-data "—"); no stat is suppressed or dimmed (epic TN-3, display-philosophy).
- [ ] **AC-6**: A report for a team with NO pitching data still renders successfully with the flag set (non-fatal empty-data path — the builder produces a suppressed/empty state, not a crash) (epic TN-7).
- [ ] **AC-7**: The outings table overrides the sitewide `table { page-break-inside: avoid }` print rule (`scouting_report.html:406`) — `page-break-inside: auto` on the outings table specifically, keeping `tr { page-break-inside: avoid }` so rows don't split mid-row — so a 15-20-row log paginates without a large blank gap (E-265-03, finding F14).

## Technical Approach
Wire the flag reader `is_pitcher_outings_enabled()` (DEFINED in E-265-01 — this story only wires it, finding F4): read `show_pitcher_outings = is_pitcher_outings_enabled()` + call the builder INSIDE the generator's query/render DB-connection scope (epic TN-7), passing both the typed structure and the boolean into the render dict. Add the inline `{% if show_pitcher_outings %}…{% endif %}` section block to `scouting_report.html` in a region that does not overlap E-264's edits, implementing the E-265-03 layout (column tiering via existing `mob-hide`/`mob-hide-extra`, native `<details>` disclosure with the `<summary>` green indicator, `.outing-strong` green treatment, section-level plays-derived note, Opp-column ellipsis, inline season line, print-pagination override). Do NOT touch E-264's ERA sites. No `report_generation_runs` telemetry column is written (so `_RUN_RECORD_COLUMNS` is not involved).

## Dependencies
- **Blocked by**: E-264 (epic), E-265-01 (derivation + flag reader), E-265-03 (layout spec)
- **Blocks**: E-265-04

## Files to Create or Modify
- `src/reports/generator.py` (flag read + builder call in the DB-connection scope; pass structure + boolean into the render dict)
- `src/api/templates/reports/scouting_report.html` (inline flag-gated section + its scoped CSS incl. the print-pagination override and the `<summary>` indicator)
- `tests/` (flag-ON renders section; flag-OFF golden byte-identical to the post-E-264 golden; green-treatment applied on a flagged outing + the `<summary>` indicator when one is inside; None-renders-as-"—"; zero-BB K/BB renders as a strength not "—"; empty-data non-crash)

## Agent Hint
software-engineer

## Handoff Context
- **Consumes from E-265-03**: the layout spec at `.project/research/E-265-outings-layout-spec.md` (column tiers + Opp ellipsis, `<details>`/`<summary>` structure + green indicator, `.outing-strong` treatment, print-pagination override, small-sample badges, inline season-line placement + zero-BB "0 BB" badge, section-level plays-derived note) — loaded as deferred context by absolute path.
- **Consumes from E-265-01**: the typed per-pitcher outings structure + the `is_pitcher_outings_enabled()` flag reader.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (flag-on/flag-off pair is the AC-1 proof)
- [ ] Code follows project style (see CLAUDE.md) and `.claude/rules/jinja-safety.md`
- [ ] No regressions in existing tests (golden unchanged with the flag unset)

## Notes
Inline is the Resolved Decision #2 ruling (SE + ux both landed there). A future E-263 can extract this self-contained inline section into a partial if it ever ships its framework (IDEA-144 tracks the deliberate template split).
