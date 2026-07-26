# Scouting-Load Seams — Three Durable Facts

Found while evaluating candidate mechanisms for E-276's player-line residual (2026-07-26).
**Executed evidence lives in `.project/research/E-276-player-line-residual-mechanism-evaluation.md`** —
figures, output lines and fixtures are there and are NOT duplicated here. This file exists so the
three facts survive in a future epic where that record is not in context.

Anchors below are named symbols and quoted sentence-openings, never line numbers.

---

## 1. `dedup_team_players` is scoped to the SCOUTED team — the opponent block has no closer

`ScoutingLoader._load_team_core`'s post-boxscore sweep calls
`dedup_team_players(self._db, team_id, db_season_id, manage_transaction=False)` with the **scouted**
team's id. But `GameLoader._load_team_stats` writes BOTH boxscore blocks — own and opponent — and the
opponent's `player_game_*` rows and `_upsert_roster_jersey` backfill land under `opp_team_id`.

So **nothing in the load path ever dedups the opponent block.** Any reasoning of the form "duplicate
player ids get merged by the end-of-run sweep" is true of the scouted team only. Verified end-to-end,
not inferred from the own-block result: the same identical-name id re-issue that the sweep closes on
the own block stays unmerged on the opponent block.

Consequence to carry: a claim that dedup closes some id-churn hazard **must name which block**.

## 2. `_upsert_game_and_stats` is the per-game entry point in `GameLoader`

`GameLoader.load_payload` → `_load_boxscore_data` → **`_upsert_game_and_stats`**, which upserts the
`games` row, inserts `game_perspectives`, calls `_load_team_stats` once per block, then calls
`_retire_absent_player_lines`.

Reach for `_upsert_game_and_stats` when you need a hook **before a game's stat writes** (a pre-upsert
snapshot, a capture anchor, an instrumentation point).

**`GameLoader` has no `_load_game`, and the name is a trap rather than merely absent** — two sibling
loaders in the same package carry near-misses: `PlaysLoader._load_game` and
`ScoutingSprayLoader._load_game_data`. So the name is familiar from the package and reads as correct.
A subclass override of a method the parent does not define is **never called and never errors**: in
E-276 the harness then ran with an empty capture, the vacuous-permit rule permitted every gate, and
the result was a clean-looking mass delete. Scope the claim when you carry it — *`GameLoader` has no
`_load_game`*, not *there is no `_load_game`*.

Related trap from the same session: `players`' primary key is **`player_id`**, not `id`.

## 3. On the reconcile paths, a CRASH looks like a REFUSAL **under the row count** — `LoadResult.errors` discriminates, at one of five sites

`GameLoader._retire_absent_player_lines` catches broadly, logs ERROR, and returns `1` into
`result.errors`. `ScoutingLoader`'s game-grain and roster-grain reconcile hooks and its dedup sweep
swallow similarly. So a reconcile or guard that **raises** produces every positive signal of one that
**refused**: nothing retired, prior rows intact, WARNING-level logs clean.

**The surviving-row count is not an admissible witness for either outcome.** It cannot distinguish
"the mechanism ran and declined" from "the mechanism blew up before it could act". Two agents probing
this seam in the same session, in opposite directions, both produced a false PASS the row count could
not tell from success — one on a guard that read as a refusal, one on a reconcile that read as a
closure.

**`LoadResult.errors` is the discriminating witness — with one hole.** Per `IDEA-189`, a failing
`dedup_team_players` collapse is logged and swallowed **without** incrementing it, and the same is
true of the game-grain reconcile, the roster-grain reconcile and the exempt pre-plan. Only the
player-line reconcile counts. So `LoadResult.errors == 0` is the right check *and* does not cover
those four sites; on those, neither the row count nor the error count is sufficient.

Practical rule: **never assert a refusal by counting rows alone.** Pair it with the result object,
and where the result object is blind (the four sites above), assert on the mechanism's own return
value or accept that the test cannot tell the two apart and say so.

See also `.claude/rules/testing.md`, "An absence claim needs proof the mechanism COMPLETED CLEANLY" —
this is that rule arriving on the mechanism rather than on the test.
