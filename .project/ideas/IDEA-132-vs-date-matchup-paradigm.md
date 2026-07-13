# IDEA-132: The `--vs`/`--date` matchup paradigm

## Status
`CANDIDATE`

<!--
Status definitions:
  CANDIDATE  -- Active idea, worth revisiting. Default status for new ideas.
  PROMOTED   -- Became an epic. Record which one in the Notes section.
  DEFERRED   -- Deliberately set aside. Include a reason and a re-review date.
  DISCARDED  -- Decided against. Include a reason so we don't re-propose it.
-->

## Summary
Design, deliberately, the paradigm by which a scouting report pairs an opponent with OUR team and a game date — `deep-scout <their_public_id> --vs <our_team> --date <game_date>`, degrading gracefully to opponent-only. This turns pure-opponent facts into matchup pairings and unlocks the highest-leverage sections that are meaningless without knowing who "we" are: the self-scout first-inning callout (our probable starter's control line), the steal-light-vs-OUR-runners green/red pairing, and matchup-conditioned eligibility (their week's schedule × our game date). morning-run already knows the pairing + date, so the scheduled path gets matchup context for free.

## Why It Matters
The 2026-07-13 operator decision made E-263 (Deep Scout v1) opponent-only on purpose — the operator wants to design the matchup paradigm as its own deliberate effort rather than bolt a `--vs`/`--date` flag onto v1. The pairing sections are, per the design doc §5, "the highest-leverage sections" (steal lights = OUR runners × their battery; bench advisor = OUR bench × their pen; kryptonite = their losers' profile × OUR profile). Getting the paradigm right — how the report resolves and represents the pairing, how morning-run passes it, how it degrades — is worth a focused design pass, not an incremental flag.

## Rough Timing
After E-263 (Deep Scout v1) ships the opponent-only deterministic sections and the fact-sheet spine exists (the `vs` block is defined-but-empty in v1, ready to populate). Promote when the operator wants the matchup pairings, or when morning-run's known pairing/date makes the self-scout callout the obvious next value.

## Dependencies & Blockers
- [ ] E-263 (Deep Scout v1) ships the fact-sheet spine + the deterministic opponent-only sections (defines the `vs` block this paradigm populates)
- [ ] A design decision on how `--vs <our_team>` is resolved and represented (team id? our roster's probable starter engine reused on our side?)

## Open Questions
- How does the report entry take `--vs`/`--date` (CLI flags, morning-run auto-pass, admin UI)?
- Which pairing sections come first: self-scout first-inning callout, steal-light-vs-our-runners, matchup-conditioned eligibility, bench matchup advisor (design-doc §3 SHOULD #6)?
- How does it degrade when `--vs` is absent (fall back to the v1 pure-opponent forms)?
- Does the full trended freebie ledger (self-scout, design-doc §3 MUST #3) belong here or in a separate staff-review report surface?

## Notes
- Companion: `.project/research/deep-scout-design-2026-07-12.md` §5 (matchup parameterization) + §8 (the self-scout first-inning callout was the literal live-validation secondary lesson).
- E-263 deferred these WITH the `--vs` context: the scoped self-scout first-inning callout (TN-6) and the steal-light-vs-our-runners pairing overlay (TN-10).
- Related: IDEA-131 (signal catalog — several catalog signals are marked `pairing` in the Matchup column and need this paradigm to light up).

---
Created: 2026-07-13
Last reviewed: 2026-07-13
Review by: 2026-10-11
