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
provided retroactively before READY re-confirmation. Epic: `.project/archive/E-267-reconcile-against-fresh-crawl/`.

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

## Verdict 4 -- Cross-perspective retire-refusal gap (mid-implementation consult, 2026-07-19)

**Context**: implementer's safety guard correctly refuses to retire a game carrying more
than one team's perspective row (whole-game hard delete would destroy the other team's
data). Consequence: a genuinely removed/voided game loaded from BOTH perspectives can
never be retired by this grain -- persists in W-L, season lines, recent form, freshness
count. Team-lead asked for coaching-severity read (not a frequency estimate).

**Split verdict, not a single call:**

- Of the four persisting symptoms, two are real decision corruption (**recent-form
  showing a voided game** -- worst, corrupts the single most game-day-immediate signal
  the system produces; **season batting/pitching lines including a game that didn't
  happen** -- corrupts the OBP/ERA a coach uses for pitch-around/matchup calls) and two
  are cosmetic (W-L off by one, freshness N vs N-1). Don't let the cosmetic half make
  the gap read as minor overall.
- **Sharper edge than the PM's framing**: safety flags (pitch count/rest day/innings
  limit) are about OUR OWN pitchers, not opponents. The real exposure question isn't
  "how often is an opponent's game cross-perspective" -- it's how often one of OUR OWN
  team's games is. My read: likely COMMON, not rare -- any LSB game against an opponent
  we've also scouted (routine workflow: pull that opponent's own boxscores) creates a
  second perspective row for that same game. If confirmed, this stops being a scouting
  nicety and becomes a player-health compliance question -- a stale/duplicate game could
  mask a real rest-day violation (pitcher's last outing looks further back than it is,
  greenlighting a start that should be held). Per my framework, safety flags PUSH
  (compliance) -- they don't get "document and defer" treatment the way scouting-
  accuracy gaps do. **Flagged this as the swing question for DE to confirm technically**:
  does an LSB game vs. a scouted opponent actually pick up both perspectives in practice?
- **Real-world frequency (the actual baseball question, not the software one)**: voided/
  re-entered GC games do happen -- duplicate-entry cleanup, protested/overturned results,
  rainout re-scored as no-contest, wrong-opponent re-scoring. Roughly a small handful of
  times per team per season, program-wide -- real enough that "document and move on"
  needs to survive actually happening a few times a year, not a once-a-decade edge case.
- **Recommendation given**: if own-team cross-perspective exposure is confirmed common
  -> MUST HAVE to close inside the epic (or at minimum mitigate the safety-flag-feeding
  calculations specifically). If confined to opponent-side scouting accuracy only ->
  documentation + follow-on idea acceptable for W-L/freshness, but pushed back on
  lumping recent-form corruption into that same "defer" bucket -- that symptom reaches
  today's game-day decision even on the opponent side, so the follow-on idea should be
  explicitly scoped to prioritize recent-form correctness, not filed as generic backlog.

Full reply delivered to team-lead ("main") via SendMessage, 2026-07-19.

## Verdict 5 -- Correction: masking scenario was wrong, direction is over-caution (2026-07-19)

**DE traced the actual SQL and disproved my masking claim from Verdict 4.** A stale/
duplicate game can only ADD an appearance (accumulate-only, no deletion of real rows) --
it can never remove one. Since `last_outing_date = MAX(game_date)` and rest-day gaps are
computed via `LAG(game_date)`, an extra row can only pull MAX later or shrink a gap,
never the reverse; pitch/appearance totals over a trailing window can only inflate, never
deflate. I tried to break this claim adversarially (stale row before earliest outing,
after latest outing, between two outings) and could not find a counter-case under this
architecture. **My Verdict-4 claim that a persisting stale game could mask a real rest
violation and "greenlight a start that should have been held" is WRONG -- retracting it.**
The actual failure mode is the opposite: over-flagging / false-positive caution.

**Revised severity, safety angle only:**

- Downgraded from MUST-CLOSE-for-health-risk to SHOULD HAVE. Nobody gets hurt from
  over-caution; the cost is competitive (holding a pitcher who was actually fine) and a
  secondary trust-erosion risk IF the discrepancy is visible enough for a coach to notice
  the number is wrong (memory says "he pitched 9 days ago," system says "5 days rest").
- **Important reframe**: the compliance GUARANTEE survives. A real rest/pitch-count
  violation is never masked by this gap, because a true appearance can never be dropped
  by an accumulate-only pipeline -- the bug can only manufacture extra caution, never
  extra permission. "Safety flags push" still holds where it matters: the system will
  never wave through a pitcher who actually needs rest because of this specific gap.
- One remaining unknown flagged to DE/SE, not resolved by me: doubleheader dates (two
  real same-date games are normal in HS ball) interacting with a same-date stale
  duplicate -- confirmed the counting is per-game-row (safe) not per-date (which could
  theoretically collapse/undercount); I could not verify this myself and don't assert a
  break, just flagged it as worth a technical check.

**Verdict 4's other findings are UNCHANGED and independent of this correction**: recent-
form and season-line corruption are about hitting/offensive reads, not pitch-count
math -- both still rated real decision corruption on their own, regardless of how the
safety-flag direction resolved. DE also found dual-perspective creation depends on a
case-insensitive team-name match (not routine when spellings diverge -- each becomes an
independently-retirable single-perspective row and the guard never fires), which lowers
my "likely common" assumption for own-team exposure and further softens urgency.

**Net revised recommendation**: document-and-defer is now defensible for the safety
angle specifically. Follow-on idea should still be explicitly scoped to prioritize
recent-form/season-line correctness (the two decision-corrupting symptoms) ahead of
W-L/freshness cosmetics and ahead of the safety angle, which is now the least urgent of
the three threads in this consult.

Full follow-up reply delivered to team-lead ("main") via SendMessage, 2026-07-19.
