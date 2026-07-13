# E-263-04: Who's Pitching section (SIG-004/006/016, joined to SIG-001)

## Epic
[E-263: Deep Scout v1 — Opponent-Intelligence Report Sections](epic.md)

## Status
`TODO`

## Description
After this story is complete, the report renders a "Who's Pitching" section (Technical Notes TN-5 Section 2) that surfaces the probable starter's own command profile — innings-weighted control (SIG-004), first-pitch-strike tendency with a charted-games badge (SIG-006), and first-inning wobble (SIG-016) — all conditioned on SIG-001's expected arm, so the coach sees the specific arm's line rather than a staff average.

## Context
Per Technical Notes TN-4, the #1 live-validation miss was computing pitching facts staff-aggregate and never joining them to the probable starter; a staff BB/7 is dominated by low-inning wild relievers and mis-estimates the arm that throws 5+ innings. This section fixes that by innings-weighting every per-arm rate and joining to SIG-001. Per TN-2, FPS% is a charted-only stat that must badge the real denominator. SIG-016 (first-inning wobble) is surfaced here for the OPPONENT's probable starter only — its self-scout reuse on our own starter is a v2 item deferred with the `--vs` matchup context (TN-6), not part of this section. All three signals read `player_game_pitching`/`plays` and are perspective- and role-scoped per TN-3.

## Acceptance Criteria
- [ ] **AC-1**: The report renders a Who's Pitching section per Technical Notes TN-5 (Section 2) as an ADJACENT card sharing visual language + arm identity with the existing Most Likely Arms card (NOT an in-place edit of it — `scouting_report.html` is foundation-owned per Technical Notes TN-9), showing the probable starter's line. It fills the pre-created pitching stub module + the Who's Pitching stub partial from E-263-02a, and renders SIG-001 (from E-263-02b) alongside SIG-004/006/016.
- [ ] **AC-2**: SIG-004 per-arm control (BB/7, SO/7, H/7, strike%, **and swinging-strike/whiff%** per Technical Notes TN-4) is **innings-weighted** and computed per `player_id`, JOINED to SIG-001's probable starter (per Technical Notes TN-4) — the displayed line is the expected arm's own line, not a staff aggregate. Per the reconciled trust-surface idiom (Technical Notes TN-2), the rate ALWAYS renders with its IP badge — below the 15 IP floor it renders `thin` (badge-differentiated), NEVER hidden or replaced by "no rate." Whiff% is derived from `play_events.pitch_result IN ('strike_swinging','foul_tip')` and is the source for the Game Plan's "locates" branch (E-263-07).
- [ ] **AC-3**: SIG-006 first-pitch-strike% is computed per pitcher and ALWAYS renders (never gated) with TWO distinct pieces of context per Technical Notes TN-2: the RATE uses the charted-PA denominator (`is_first_pitch_strike` over `pitch_count>0` PAs, per `.claude/rules/key-metrics.md`), and a separate coverage BADGE discloses how many GAMES were charted (e.g. "3 of 12 games charted"). The coach sees both the rate and its coverage.
- [ ] **AC-4**: SIG-016 first-inning wobble (1st-inning runs/BB/hits per start, averaged across starts) is computed per `pitcher_id` and rendered for the probable starter; below the **≥4-starts floor** (Technical Notes TN-2) it renders as a lean/`thin` (badge-differentiated, value still shown), not a firm pattern.
- [ ] **AC-5**: Every rollup in this section applies BOTH the perspective (dedup) filter AND the role filter `player_game_pitching.team_id = X` per Technical Notes TN-3 (`get_pitching_history` already carries both, db.py:307-308), and keys strictly on `player_id`. A test using the shared twin-game fixture (E-263-02a) proves no double-count.
- [ ] **AC-6**: When SIG-001 resolves to "committee" (Technical Notes TN-4), the section presents the full per-arm two-branch detail for the committee arms (unconstrained by the Game Plan word budget, per Technical Notes TN-5 §2), without forcing a single-arm framing — **capped at 3 arms** (reusing the existing `top_candidates[:3]` cap); when 4+ arms tie, SIG-001's rank selects which 3 display with a "+N other arms also eligible" overflow note.
- [ ] **AC-7**: When `FEATURE_PREDICTED_STARTER` is OFF (SIG-001 absent — per Technical Notes TN-4), this section renders a LOUD, visible degraded/warning state (not a silent empty card), consistent with E-263-02b AC-5 and the report-run honesty mechanism. A test covers the flag-off path.

## Technical Approach
Fill the pre-created pitching stub module under `src/reports/deep_scout/` (from E-263-02a) to compute SIG-004/006/016 into the fact sheet, reusing `get_pitching_history`/`build_pitcher_profiles` (`src/api/db.py`) and the annotated pitch column `plays.is_first_pitch_strike` (populated by `bb data reload-annotated-pitches`; note `is_first_pitch` lives on `play_events`, and FPS% needs only the pre-computed `is_first_pitch_strike` over `pitch_count>0` — do not chase a `plays.is_first_pitch`). Whiff% comes from `play_events.pitch_result`. Innings-weighting and the SIG-001 join are the substance (per TN-4). Fill the Who's Pitching stub partial, reusing the shared trust-surface partial from E-263-02a. Read `.claude/rules/key-metrics.md` for the FPS% charted-PA denominator definition (already codified) — match it, do not re-derive.

## Dependencies
- **Blocked by**: E-263-01 (layout spec), E-263-02a (fact-sheet framework + pitching stub + partial), E-263-02b (SIG-001 fact — the join target)
- **Blocks**: E-263-07 (Game Plan needs SIG-004 incl. whiff% for the two-branch plan)

## Files to Create or Modify
- `src/reports/deep_scout/<pitching module>.py` (modify — fill the SIG-004/006/016 builder stub from E-263-02a)
- `src/api/templates/reports/deep_scout/<whos-pitching partial>.html` (modify — fill the Who's Pitching stub partial from E-263-02a)
- `tests/test_deep_scout_pitching.py` (new — innings-weighting, SIG-001 join, whiff% derivation, FPS% rate + coverage badge, perspective-scoping via the shared twin-game fixture)

Does NOT edit `scouting_report.html` or the assembler — E-263-02a owns those seams per Technical Notes TN-9.

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-263-07**: SIG-004 (per-arm control, for the two-branch plan's "wild" vs "locates" branches). (SIG-016 first-inning wobble is surfaced for the opponent's starter in this section; its self-scout reuse on our own starter is a v2 item — the `--vs` context is out of v1.)

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This is the heaviest deterministic group (innings-weighting + the starter join) but remains a single session per SE. The FPS% definition is already codified in `key-metrics.md` — reuse it.
