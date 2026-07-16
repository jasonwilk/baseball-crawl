# E-265-04: docs-writer coaching how-to for the Outings Breakdown

## Epic
[E-265: Pitcher Outings Breakdown](epic.md)

## Status
`DONE`

## Description
After this story is complete, `docs/coaching/` carries a short how-to that explains the Outings Breakdown section to coaching staff: how the section is organized (a season summary line per pitcher heading a game-by-game outing log), what each column means, how to read the green highlighting, and which values are computed from play-by-play rather than official GameChanger boxscore stats.

## Context
The Outings Breakdown introduces per-outing columns, a season rate line (K/BF, BB/INN, K/BB, H/BF — not the K/9 shown elsewhere on the report), a plays-derived-vs-GC distinction, and green highlighting coaches need explained. This how-to is the coach-facing documentation for the shipped section, written against what E-265-02 actually rendered.

## Acceptance Criteria
- [ ] **AC-1**: A new `docs/coaching/` how-to explains each per-outing column (`Date | Opp | IP | BF | H | HR | BB | K | R | FPS% | ERA(game)`) and the per-pitcher season summary line (the full context set — IP, G, GS, ERA, WHIP, FPS% — plus the rates K/BF, BB/INN, K/BB, H/BF), including what K/BF, BB/INN, K/BB, and H/BF mean (and that H/BF vs BB/INN separates a hit-hard arm from a walk-prone one, which WHIP alone conflates) and that this section deliberately uses those rates rather than the K/9 shown in the main pitching table (epic TN-2/TN-3).
- [ ] **AC-2**: The how-to explains how to read the GREEN highlighting — that a green outing marks a strong "respect it" performance (the epic TN-4 criteria in plain coach language) and that outings below the sample floor are shown plainly without color (never a signal of weakness).
- [ ] **AC-3**: The how-to states plainly that the plays-derived values (FPS% and HR-allowed) are computed from play-by-play data — not official GameChanger boxscore stats — and includes the directional-read caveat that per-outing plays counts are ~90–95% pitcher-attribution accurate and may not tie exactly to a boxscore (epic TN-6). It also notes the small-sample caveats on the season rate line (under 15 IP, and the K/BB BB-count badge, including how a 0-walk pitcher's K/BB is shown as a command strength rather than a blank).
- [ ] **AC-4**: The doc reflects the SHIPPED section (written after E-265-02 lands) and carries the standard staleness header (Last updated + Source epic/story ID) per `.claude/rules/documentation.md`.

## Technical Approach
Standard docs-writer coaching how-to in `docs/coaching/`, written against the shipped E-265-02 section. Keep it short and coach-facing (no operator/engine internals). Reference the epic TN-2/TN-3/TN-4/TN-6 for the authoritative column set, season rate set (K/BF, BB/INN, K/BB, H/BF), green criteria, and the plays-derived/attribution caveats.

## Dependencies
- **Blocked by**: E-265-02 (document the shipped section)
- **Blocks**: None

## Files to Create or Modify
- `docs/coaching/` (new how-to page — e.g. `pitcher-outings-breakdown.md`; exact filename docs-writer's choice)

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Doc matches the shipped section and carries the staleness header
- [ ] Coach-facing tone (no engine internals)

## Notes
The plays-derived-vs-GC distinction and the pitcher-attribution caveat are the two things a coach most needs framed honestly here — a per-outing FPS% or HR count is a directional read, not a byte-exact official number.
