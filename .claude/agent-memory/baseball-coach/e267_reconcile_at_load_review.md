---
name: e267-reconcile-at-load-review
description: Coaching-value verdict on E-267 reconcile-at-load (game/player-line/roster retire-absent) -- departed-player roster semantics endorsed, W-L/season-line auto-correction endorsed, roster drop-cap tryout-cut nuance flagged
metadata:
  type: project
---

## Context

E-267 "Reconcile-at-Load Against the Fresh Crawl" (2026-07-19) makes the load pipeline
retire stale/duplicate rows on re-scout across three grains: game, player-line, roster.
Coach consult was missing from the original plan (DE + api-scout had already consulted);
provided retroactively before READY re-confirmation. Epic: `epics/E-267-reconcile-against-fresh-crawl/`.

## Verdict 1 -- Departed-player roster semantics (E-267-04 AC-5)

**Endorsed as coaching-correct.** A player cut/removed from the fresh roster crawl
retires from the ROSTER DISPLAY (report roster grid, bench card) while KEEPING their
`player_game_*` stat rows.

**Why:** the roster grid answers "who is on this team right now / who might I face
today" -- a departed player showing up there is actively wrong for lineup construction
(own team) and false scouting alarm (opponent, "watch out for a hitter who already
quit/transferred"). Stat lines are a different question ("what happened this season")
and should survive -- games that were played, were played; a coach reviewing season
totals or a hot-streak history shouldn't have real production erased because the kid
left mid-season. No scenario surfaced where a coach needs the departed player back ON
the live roster grid; "might return" is not a roster-retire risk because GC's roster
crawl only returns `active` players (TN-11) -- a temporarily-inactive/suspended player
was ALREADY invisible to us pre-epic (GC's own status semantics, not something this
epic changes), and a genuine return re-upserts cleanly on a future crawl.

**Flagged nuance (SHOULD HAVE, not a blocker):** confirm season batting/pitching
leaderboards resolve player display name via the `players` table (not gated on
`team_rosters` membership), so a departed player's real in-season contributions
still surface in season stat tables/leaderboards even though they're gone from the
live roster grid. If leaderboards silently join through `team_rosters`, a departed
player's real production could vanish from BOTH surfaces, which would be wrong --
[[coaching-decisions]] establishes stat visibility should never be suppressed for
reasons other than sample size.

## Verdict 2 -- W-L / season-line auto-correction

**No coaching objection -- strongly endorsed.** Retiring stale/duplicate games auto-
corrects W-L, recent form, and every rate stat (OBP/ERA/K-BB/etc.) derived from
`player_game_*` SUMs -- this is exactly the "byte-identical play ingestion" north star
applied to the load path, not just the parser. Bonus: it also fixes false proactive
flags (a duplicated/stale game inflating a "hot streak" or a pitch-count/rest-day
calculation could trip a false safety flag or mask a real one) -- safety-flag accuracy
depends on the same corrected game grain. Reports being disposable/regenerable (forward-
only, no historical repair) is consistent with the reports-first, fresh-start model
already established for this project.

## Verdict 3 -- Other domain concerns on the three retire grains

- **Roster drop-cap calibration (TN-12, DE pre-dispatch decision) -- flagged nuance,
  not a blocker.** The conservative default (refuse >1-player single-run drop) fits
  mid-season single departures well but may be too strict for a real, common HS/youth
  pattern: preseason tryout cuts, where a coach trims a 20-player tryout pool down to
  a 12-15 final roster in ONE roster-page edit (multiple players dropped at once,
  legitimately). Under the conservative default this legitimate multi-cut event would
  refuse-and-warn rather than retire, leaving stale tryout-only names on the roster
  grid until a later single-departure or manual purge. Flagged this to DE for TN-12
  calibration; NOT a blocker because the failure mode is benign (stale grid clutter,
  never wrong STATS -- no coach-facing number corrupts, unlike the other two grains).
- **Scored-but-empty-boxscore-never-retires guard (player-line, E-267-03 AC-1/AC-2) --
  endorsed.** GC boxscores can publish with categories present but per-player stats
  empty while a game is live/in-progress; retiring against that shape would delete real
  historical stat lines. Correctly gated to POPULATED 200 only.
- **Hard-delete uniform (TN-4) -- endorsed, no display-philosophy conflict.** The
  "never suppress, always contextualize" display philosophy governs SAMPLE-SIZE
  sparsity (a real stat with a small N), not entities that no longer exist on the
  team. A departed player isn't a suppressed small sample -- they're gone. Ghost rows
  serve no coaching purpose.

## Full reply delivered to PM via SendMessage, 2026-07-19.
