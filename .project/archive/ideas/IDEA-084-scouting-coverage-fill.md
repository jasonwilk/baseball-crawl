# IDEA-084: Scouting-coverage fill to lift probable-starter accuracy

## Status
`CANDIDATE`

## Summary
Fetch more of each opponent's *completed* season schedule before computing the probable-starter prediction, so the engine has fuller game history to rank from. "Lever A" in the coverage memo: at report-generation time, read the opponent's public completed-game schedule (`/public/teams/{public_id}/games`, no auth) and crawl/boxscore any completed games we are missing for the season via the existing opponent-scouting pipeline, before the prediction runs.

## Why It Matters
The E-243 backtest showed the probable-starter engine's ranking is sound but absolute accuracy is modest (top-1 ~20%, top-2 ~40%). The data-engineer coverage memo (`.project/research/scout-coverage-lever.md`, 2026-06-28) establishes that **coverage, not algorithm, is the binding accuracy lever**: 21.6% of scored games have a starter the engine never saw (automatic misses), and our fully-charted own team (LSB Varsity) sits at a 7.7% novel-starter rate while scouted opponents run 15-50% — same engine, the only difference is history completeness. Lever A directly attacks that gap by reusing existing no-auth pipeline machinery. Realistic payoff is a top-2 lift from ~40% toward ~50-55%, **bounded by structural committee entropy** (pitch-count caps make a dominant ace impossible at this level) — an honest improvement to the ranked "most likely arms" shortlist E-243 ships, not a single-name oracle.

## Rough Timing
After E-243 ships (the presentation/ranking fixes this compounds with). Promote when there's appetite to raise scouting accuracy and a planning session can resolve the two open decisions below.

## Dependencies & Blockers
- [ ] E-243 (probable-starter usefulness) shipped — this compounds with its ranked-shortlist surface.
- [ ] Existing opponent-scouting boxscore pipeline and the public-schedule endpoint remain available (they are today).

## Open Questions
- **Report-time fill vs. scheduled backfill** (the latency trade-off): fetch missing games inline at report generation (lever A — simplest, adds per-report latency), or a periodic backfill job that pre-warms coverage decoupled from report latency (lever B — overlaps the existing morning-run cron). The memo recommends A first, B as a fast-follow if per-report latency proves unacceptable.
- **Per-report fetch budget / latency ceiling**: an explicit bound on how many missing games to crawl per report and the acceptable added generation time (~30 games/opponent is the natural cap).

## Notes
- **Project non-goal — do NOT pursue cross-/prior-season history (lever C).** Cross-season is an explicit CLAUDE.md / ROADMAP non-goal, and rotations turn over year-to-year so prior-season arms rarely predict the current starter — low payoff.
- Source: `.project/research/scout-coverage-lever.md` (data-engineer, 2026-06-28) — full per-team coverage table, the novel-starter-rate methodology, the fully-charted-control argument, and the disposition recommendation (bounded follow-on epic scoped to lever A).
- Split out of E-243 (was E-243-06) per user decision 2026-06-28; the analysis ran against the main checkout because it needs the dev DB. Parent: E-243.

---
Created: 2026-06-28
Last reviewed: 2026-06-28
Review by: 2026-09-26
