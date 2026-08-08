# IDEA-220: One game carries two perspectives' plays — probably by design; the open question is whether every consumer scopes

## Status
`CLOSED — CHECK DONE, PROMOTION CRITERION NOT MET` (2026-07-28, by E-278 TN-8). **Recorded so the consumer check is not re-run.** The original status line is preserved below because its caution was justified and the check vindicated it.

> *(Original status: `CANDIDATE` — ⚠ Filed with its own premise contested. Read the first section before treating this as a defect.)*
>
> ## ✅ The consumer check was RUN. Result: no unscoped coach-facing consumer.
>
> Every `plays` / `play_events` reader in `src/` was enumerated — **11 files by SQL grep, cross-checked against 27 by name, with all extras hand-cleared.** Result: **every coach-facing plays-derived stat is perspective-filtered.** The five report-section queries in `generator.py` (FPS%, P-BF, QAB%, P-PA, team aggregates), `pitcher_outings.py`, and the reconciliation engine's chosen-perspective filter all scope correctly. `recon_scoreboard.py`'s aggregates carry no `WHERE` filter but `GROUP BY game_id, perspective_team_id, pitcher_id`, so **each perspective is its own group — structurally immune rather than accidentally correct.**
>
> **This capture's stated promotion criterion — *"promote only if the check finds an unscoped consumer"* — is therefore NOT MET, and the idea closes without becoming a defect.**
>
> **One operator-only counter behaves as this capture feared, and the characterization matters.** `recon_scoreboard.py`'s `dropped_pitch_events` counts a two-perspective game's stranded events twice. **It is NOT an omitted `WHERE`**: `play_events` **has no `perspective_team_id` column at all**, so it cannot be filtered without joining through `plays` — calling it "unfiltered" implies a one-line fix that does not exist. Settled position: **the COUNT is right and the DOCSTRING is what should change** — each stranded row is separately repairable, so counting both perspectives' rows is correct for a repair-surface measure, while the docstring describes it pitch-level. It never reaches a coach. Idea-sized wording fix, not a defect.
>
> **Also refuted and not carried forward:** an adjacent `team_rosters` fan-out hazard. `PRIMARY KEY (team_id, player_id, season_id)` means the join cannot fan out.
>
> **What survives and still binds:** this capture's warning against deleting either perspective's rows. And carry into any reconciliation work — **the engine reconciles a two-perspective game under ONE perspective only**, so the other perspective's plays are never corrected.

## Summary

The report audit flagged one 2026-season game whose `plays` rows are **loaded twice under two different `perspective_team_id` values** — 71 + 71 = 142 rows against a 47-77 per-game norm — and whose `games` row stores the **opponent's** perspective event id.

**Both observations are consistent with documented, intended behaviour**, which is why this is filed as a question rather than a bug:

- `.claude/rules/perspective-provenance.md` (Plays Pipeline) states it outright: whole-game idempotency is keyed `WHERE game_id = ? AND perspective_team_id = ?`, so the second load of the *same* perspective is skipped, and **"different perspectives of the same game each get their own plays rows."** Two perspectives × ~71 PAs = ~142 rows is exactly what that design produces.
- The opponent-perspective event id on the `games` row is what cross-perspective dedup produces when the opponent's row was the one loaded first: `GameLoader._find_duplicate_game()` collapses the twin to a single canonical `game_id`, and which perspective's id becomes canonical is an artifact of load order, not a correctness property.

So the honest reading is: **this game was correctly deduped and correctly loaded from both perspectives.** Note that it is therefore the *opposite* case from [[IDEA-218]], where a twin was NOT collapsed — almost certainly a different game, and worth confirming they are not being conflated.

## The one thing that would make it a real defect

Doubled rows are safe only while **every consumer filters on `perspective_team_id`.** That filter is a per-query discipline, not a structural guarantee — `.claude/rules/perspective-provenance.md` makes it MUST-constraint 3 precisely because omitting it silently doubles a line with nothing crashing, and `.claude/rules/data-model.md` records it as the #1 hazard of the E-259 query-time cutover.

**Nobody has checked whether any displayed stat on this report doubles for this game.** That is the whole question, and it is answerable: compare this game's contribution to the plays-derived rate stats (FPS%, P-PA, P-BF, QAB%) and to the reconciliation scoreboard against a single-perspective game, or simply run `bb report reconcile-scoreboard` and look at whether this game is an outlier.

**Two reasons to think it is probably clean**, recorded so the check is scoped rather than open-ended: the audit's calc evaluation verified ~314 facts per environment as computationally correct and found identical computation behaviour across prod and dev ([[IDEA-196]] carries that result), and no doubled stat was observed on the report. **That is evidence, not proof** — it bounds how alarmed to be, not whether to look.

## Why It Matters

Modest, and stating it honestly matters more than stating it urgently.

If the consumers all scope, this is not a defect and the value of the capture is **preventing it from being "fixed"** — someone deleting one perspective's plays to make a row count look tidy would destroy real, deliberately-collected data and break the very isolation the perspective design exists to provide.

If some consumer does not scope, it is a silent double-count on a coach-facing rate stat, which is the failure mode `perspective-provenance.md` was written to prevent, and it would be worth finding.

Either way the answer is cheap and the capture stops the question being re-asked from scratch by the next person who notices a 142-row game.

## Rough Timing

**Run the consumer check whenever anything next touches the plays pipeline or the reconciliation scoreboard** — it is a comparison, not a project. Do not plan around it.

Promote only if the check finds an unscoped consumer, in which case it stops being this idea and becomes a defect with a known fix.

## Dependencies & Blockers
- [ ] None. The check needs only the dev database.

## Open Questions

- **Does any plays-derived stat double for this game?** The question this idea exists to answer.
- **Is this the same game as [[IDEA-218]]'s uncollapsed twin, or a different one?** They are opposite outcomes of the same dedup path — one collapsed, one did not — so establishing they are distinct games is the first thing to do, and it prevents a confused fix aimed at both.
- **Why is this game's PA count 71 per perspective against a 47-77 norm?** Within the stated norm, so probably nothing. Recorded only because the audit cited the range and a future reader may otherwise re-derive it.
- **Is load order the only thing deciding which perspective's event id becomes canonical?** If so, that is worth knowing explicitly rather than by inference — it means the stored event id carries no information about which perspective the data came from, and `perspective_team_id` on the child rows is the only provenance.

## Notes

Found in the four-agent live-vs-dev report evaluation on 2026-07-26/27, alongside [[IDEA-217]] / [[IDEA-218]] / [[IDEA-219]]. Relayed to PM as *"may belong inside the record-header finding or standalone."* Filed standalone **and demoted from anomaly to question**, because reading the perspective-provenance rule shows the observation is what the design predicts.

**The durable point, and the reason this file is worth its length: a row count that looks wrong against a per-game norm is not evidence of a defect when the schema deliberately stores one row set per perspective.** The `perspective_team_id` column exists so that doubling is legible rather than corrupting. Check the consumers, not the count.

**⛔ Do NOT delete either perspective's plays rows.** Both are real data from real API calls, and E-244's redirect-map footgun plus the whole-game idempotency rule mean a hand-deletion would not re-load cleanly.

Related: [[IDEA-218]] (the uncollapsed twin — confirm it is a different game), [[IDEA-217]], [[IDEA-196]] (the calc-evaluation result that bounds this), [[IDEA-106]], [[IDEA-124]].

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
