# E-255-07: baseball-coach own-memory truth sweep

## Epic
[E-255: Truth Sweep — Context Layer, API Docs, Runbooks](epic.md)

## Status
`DONE`

## Description
After this story is complete, baseball-coach's own memory (`.claude/agent-memory/baseball-coach/`) describes the reports-first, single-season reality: the cross-team/multi-season "from day one" section is replaced with a one-line non-goal note, the ghost entity list in `coaching-decisions.md` names only real tables, and the dated 403 season-stats recipes carry a SUPERSEDED banner.

## Context
Own-memory edit routed to baseball-coach under the own-memory carve-out. Scoped from the coach's own docket recon (relayed via main) plus a PM clean re-read (2026-07-07):
- **MEMORY.md lines 65-72** ("Multi-Team, Multi-Season Tracking") — CONFIRMED STALE.
- **coaching-decisions.md** — the season-over-season *framing* is CONFIRMED already clean (coach re-read; PM verified) → that sub-item is DROPPED. BUT L19's "Key entities" list STILL names the ghost `Lineup`/`PlateAppearance`/`PitchingAppearance` (PM verified 2026-07-07) → that stays in scope. See epic TN-7 (same ghost list appears in DE memory + DE charter; keep all three consistent).
- **scouting-pipeline.md** — five dated 403 season-stats recipes; a SUPERSEDED banner, not a rewrite of dated research entries.
The `PlayerTeamSeason` token was already scrubbed in E-250 — do NOT redo.

## Acceptance Criteria
- [ ] **AC-1**: Given `MEMORY.md` lines 65-72 ("Multi-Team, Multi-Season Tracking": "tracked across teams and seasons… from day one" + "Longitudinal tracking enables…"), when replaced with a one-line non-goal note + a pointer to the E-239 removal history, then a grep of that MEMORY.md for `from day one` and `Longitudinal tracking enables` returns zero hits, and a single non-goal line stands in place of the section.
- [ ] **AC-2**: Given `coaching-decisions.md` L19's "Key entities" list naming `Lineup`, `PlateAppearance`, `PitchingAppearance`, when corrected by REPLACING those ghost names with the real tables `player_game_batting`/`player_game_pitching`/`plays`/`play_events` (commit to replacement, not conceptual-relabeling — a relabel keeps the token and fails the check), then a grep of `coaching-decisions.md` for `PlateAppearance|PitchingAppearance|Lineup` returns zero hits — consistent with DE memory (E-255-08) and the DE charter pointer (E-255-03) per TN-7. The season-over-season framing is left untouched (already clean).
- [ ] **AC-3**: Given `scouting-pipeline.md`'s five 2026-03-04 discovery-note recipes that assume `/teams/{id}/season-stats` works for opponents (now Forbidden/403 for non-owned teams), when a SUPERSEDED banner is added near the top, then the banner names the 403 finding and points to the real pipeline (opponent public_id → public schedule/roster → authenticated per-game boxscore → client-side aggregate), and the five dated entries are covered by the banner (not deleted — they are dated research history).
- [ ] **AC-4**: Given the re-verify mandate, when any cited item is found already-fixed, the story notes record it as discharged and the prose is left unchanged.

## Technical Approach
Read each memory file in full. AC-1 replaces a section; AC-2 fixes one entity list on L19; AC-3 adds a banner rather than editing dated history. Keep corrections lightweight (aligns with the §3 context-growth counterweight in E-255-03).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/agent-memory/baseball-coach/MEMORY.md`
- `.claude/agent-memory/baseball-coach/coaching-decisions.md`
- `.claude/agent-memory/baseball-coach/scouting-pipeline.md`

## Agent Hint
baseball-coach

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The grep checks (AC-1, AC-2) return zero hits
- [ ] Ghost-entity list consistent with DE memory + DE charter (TN-7)
- [ ] `PlayerTeamSeason` NOT re-touched (already done in E-250)

## Notes
Coach's initial recon recommended dropping `coaching-decisions.md` entirely as "already clean" — a PM clean re-read caught that L19 still carries the ghost entities, so the file stays in scope with a narrowed AC (entity list only; season-over-season framing confirmed clean).
