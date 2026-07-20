# E-267-04: Roster Grain at Load — Retire Departed Roster Players (H2)

## Epic
[E-267: Reconcile-at-Load Against the Fresh Crawl](epic.md)

## Status
`DONE`

## Description
After this story is complete, a re-scout whose fresh roster OMITS a player present in a prior run retires that player's `team_rosters` row for the team+season — as part of the normal load, forward-only. This closes H2 (departed players rendering on the coach-facing report roster grid indefinitely).

## Context
Roster upserts (`_upsert_roster_player` `scouting_loader.py:406-430`; `_upsert_roster_jersey` `game_loader.py:1526-1565`) update present players but never retire absent ones; `_validate_roster_count` only warns. The report roster grid `_query_roster` (`generator.py:626-641`) reads `team_rosters` directly, so an ex-player renders forever. Uses the E-267-01 primitive scoped to the roster grain.

## Acceptance Criteria
- [ ] **AC-1**: Given a team re-scouted whose fresh roster omits a player present in a prior run, and the absence is corroborated as REMOVED (the existing empty-guard `scouting_loader.py:343-345` passed AND the STRICTER roster-grain drop guard held, per Technical Notes TN-2 + TN-12), when the load runs, then that player's `team_rosters` row for the `(team_id, season_id)` is hard-deleted and no longer renders in `_query_roster`.
  - **AC-1c (boxscore-less loads do NOT reconcile the roster — ACCEPTED limitation, ruled 2026-07-20):** The reconcile is positioned after the boxscore load (per the corrected Technical Approach), and `scouting_loader.py:170-175` early-returns on `if not boxscores`, so a load that produces no boxscores never retires roster departures. This is ACCEPTED, not a gap to close. It is fail-safe in the only direction that matters (a stale grid, never a false delete) and splits into two sub-cases that are BOTH correctly handled:
    1. **True preseason (no completed games at all).** The report never renders. `_no_games_gate` (`src/reports/generator.py:1911-1962`) fires when N == 0 — N being completed games we actually have stat data for — and writes a minimal `no_games` page instead of the full report. A team with no boxscores has N = 0 by construction, so the roster grid is never shown to a coach in this state. The stale row exists but is unreachable.
    2. **Degraded re-scout (games exist, boxscores absent THIS run).** Here skipping is not merely acceptable, it is CORRECT: a boxscore-less re-scout of a team that has games is a degraded crawl, and retiring roster rows on its evidence is exactly the delete-on-a-bad-crawl that bias-to-refuse forbids. Closing this would be a regression, not a fix.
  - Also weighed: the case that motivates closing it — the preseason tryout cut — would be REFUSED anyway. A 20→14 cut is 6 departures against `MAX_ROSTER_DEPARTURES = 2` (TN-12's accepted tryout-cut fallback), so a pre-early-return call would buy only the ≤2-departure preseason case, which sub-case 1 already makes invisible. The coverage is worth less than it appears.
  - **Do NOT close this by adding a second call site in the boxscore-less branch.** A second call site carries its own ordering constraints relative to the dedup sweep, and the existing call site's upper boundary was itself found untested (2026-07-20 code review). Adding an untested call site to fix an invisible gap trades a fail-safe limitation for a live false-delete surface.
- [ ] **AC-2 (roster drop cap — LOCKED, DE-decided)**: The roster grain applies an ABSOLUTE cap `MAX_ROSTER_DEPARTURES = 2` **IN ADDITION TO** the universal FLOOR_RATIO health gate — both run, and either can refuse. The cap exists because the flat ratio ALONE is too loose for a 12-15 roster (a 9-of-14 mid-edit passes 0.5), per Technical Notes TN-12; it narrows the ratio rather than replacing it, via the `extra_guard` seam whose narrowing-only property is structural (E-267-01 AC-2).

  <!-- WORDING CORRECTED 2026-07-20 (PM). This AC originally read "(NOT the flat FLOOR_RATIO, ...)",
       which read literally says the ratio does not apply to this grain — FALSE. The code runs BOTH:
       `crawl_is_authoritative(...)` at `src/db/reconcile_at_load.py:992-996` AND
       `extra_guard=roster_departure_guard` at `:1001`, and the refusal WARN branches between them at
       `:1022-1035` (floor_ratio vs MAX_ROSTER_DEPARTURES). `test_catastrophic_roster_shrink_refuses_
       on_the_floor` proves the floor fires on this grain. I meant "the cap is not DERIVED FROM the
       ratio"; the wording said the ratio is unused. Caught only after E-267-05's docs faithfully
       inherited the error into `docs/admin/operations.md:555` ("rather than a shrink ratio", since
       corrected to "in addition to"). Operationally load-bearing: a roster refusal WARN can name
       `floor_ratio`, so the stale wording would have contradicted the operator's only diagnostic at
       the moment of diagnosis. -->
 Given `absent = {DB roster player_ids for (team_id, season_id)} − {fresh player_id set}`: when `len(absent) > 2` (≥3), then NO roster row is retired (bias-to-refuse) and ONE WARN is logged carrying `team_id`, `season_id`, `roster_db_count`, `fresh_crawl_count`, `absent_count`, and the absent `player_id` list; when `len(absent) <= 2`, the retire proceeds. Only DELETEs are capped — the ADD path (new fresh-crawl players) is NEVER gated. An empty/incomplete payload (empty-guard) is likewise never retired.
  - **AC-2a (the counts are CANDIDATE counts, not raw-roster counts — recorded 2026-07-20):** Since round 3, ids exempted as pending-dedup-collapse members leave the candidate set entirely, so `roster_db_count` and `absent_count` describe the RETIREMENT-CANDIDATE population, not the raw `team_rosters` row count. This is correct and deliberate — the `MAX_ROSTER_DEPARTURES` cap must be evaluated against candidates, since an exempt row was never a departure and counting it would distort the very decision the cap makes. AC-2 is judged to HOLD as worded: it names which fields the WARN must carry, and all six are present; it never defined their population. Recorded here rather than rewritten because the operator-diagnosis risk (a `roster_db_count` that undercounts the visible roster) is already recoverable from the adjacent INFO line, which logs the exempted ids and count for the same run. **No new requirement on the implementer** — if the exemption INFO line is ever removed, this becomes a real gap and the exempt count must move into the WARN itself.
- [ ] **AC-8 (planner failure must FAIL CLOSED — added 2026-07-20, PM ruling)**: The dedup pre-plan that computes collapse exemptions (`_pending_collapse_player_ids`) currently fails OPEN — on a planner exception it logs ERROR, returns no exemptions, and the roster retire proceeds unprotected. That must become FAIL CLOSED: a planner failure SKIPS the roster retire for that run and emits one WARN naming the skip and its cause. Rationale — the error asymmetry is extreme and one-directional:
  - **Skipping costs** a stale roster row for one cycle. Fail-safe, and the next successful crawl retires it.
  - **Proceeding costs** a PERMANENTLY split identity: the roster row under the new id, every stat row under the old, no co-rostered pair left for dedup to detect, and — confirmed by execution during the round-3 consultation — NO self-heal across later crawls, because each crawl re-backfills the old id and the retire removes it again before dedup runs.
  A transient, recoverable failure (the planner erroring) must not be able to cause permanent, unrecoverable corruption. Every other grain in this epic refuses when its corroborating signal is unavailable (TN-2 health gate, populated-200, empty-guard); the exemption plan IS this grain's corroborating signal, and it is the only one currently allowed to go missing without stopping the delete. Note also that the fail-open posture is defended in the code as "restores the prior behavior" — but the prior behavior IS the defect this round exists to fix, so prior-behavior parity is not a safety argument here.
- [ ] **AC-9 (the plan/re-detection relationship is SUBSET, not equality — recorded 2026-07-20)**: The roster retire computes dedup exemptions from a plan (P1) that is NOT executed; the existing `dedup_team_players` call re-detects independently (P2). PM ratified that deviation — executing the captured plan in the loader would open-code plan+execute there, violating CLAUDE.md's one-shared-home rule for `plan_player_dedup`/`execute_collapse`, and would move refused-fork WARN ownership into the loader. The property that makes it safe is **`P1.collapses ⊆ P2.collapses`**, code-reviewer-verified: every member of a P1 collapse is exempt, so the retire deletes none of them; deletions only remove nodes and edges, never add them, so each component survives intact and is re-detected. An exemption therefore can never be stranded — which is the only thing the deviation needs.
  **Set EQUALITY does NOT hold and must not be asserted anywhere.** P2 can contain collapses P1 refused: retiring one member of a refused fork drops that fork to a pair, which the next plan will merge. (That promotion is itself a real concern, captured as IDEA-157 — filed against the planner's non-durable fork refusal, not against this story.) A future reader relying on equality would be relying on something false; the guarantee is one-directional containment.
- [ ] **AC-3**: The DELETE removes ONLY the `team_rosters` row, NEVER the `players` parent (per TN-10 risk 6 — the player may still have stat rows or appear on other teams; roster departure is not player deletion).
- [ ] **AC-4**: The set-difference and DELETE are scoped to the roster natural key `(team_id, season_id)` — `team_rosters` has NO `perspective_team_id` (PK `(team_id, player_id, season_id)`, per TN-10 risk 1, DE-confirmed). Delete the team-season's roster rows whose `player_id` is absent from the fresh crawl set; no other team's roster can be touched (one team-season = one roster source).
- [ ] **AC-5**: Departed-player semantics are explicit (per TN-10 risk 1 caveat): a player absent from the fresh roster crawl but present in stat tables via the `game_loader._upsert_roster` boxscore backfill (e.g. cut mid-season) IS retired from the roster display while KEEPING their `player_game_*` rows (stat tables FK to `players`, not `team_rosters` — no FK break). The roster grid reflects the current roster; season stats retain the departed player's games.
- [ ] **AC-6 (leaderboard-survives-departure guard test — baseball-coach SHOULD-HAVE, TN-13)**: The repo ALREADY resolves season-leaderboard names via the `players` table and left-joins `team_rosters` only for jersey (`src/api/db.py:457` and `:521`), so no fix is needed — this AC LOCKS that behavior with a regression assertion. Add a test that retires a departed player from `team_rosters` and asserts they STILL appear in the season batting/pitching leaderboards with their name and production intact (only the roster-grid disappearance is intended). The test guards against a future change that would regress the leaderboard join to gate on `team_rosters` membership.
- [ ] **AC-7**: Regression test per TN-7: reproduces the stale roster row (fails pre-fix — ex-player renders in `_query_roster`) and asserts the single-departure retire post-fix; plus bias-to-refuse cases for (a) an empty/incomplete roster payload and (b) a ≥3-player single-run drop (a 9-of-14 mid-edit roster must NOT retire the 5 missing, and must emit the AC-2 WARN); an assertion the `players` row survives; an assertion a backfilled-then-cut player's `player_game_*` rows survive the roster retire (AC-5 semantics); **[GAP-4 cross-team scoping]** a two-team-season case — retire team A's roster and assert team B's `(team_id, season_id)` roster is UNTOUCHED (guards the `WHERE team_id=? AND season_id=?` on the NOT-IN delete); and coverage of the AC-6 leaderboard-survives-departure guard.

## Technical Approach
Wire the E-267-01 `classify_absences` health-gate into the scouting load, scoped to `(team_id, season_id)`, positioned AFTER the boxscore load (and still before the dedup sweep) — NOT at roster-load time, reusing the existing empty-guard (`scouting_loader.py:343-345`) plus the LOCKED `MAX_ROSTER_DEPARTURES = 2` absolute drop cap (TN-12) as the corroboration — NOT the flat FLOOR_RATIO. Unify with the jersey-upsert path if that simplifies the set-difference. Hard-delete the `team_rosters` leaf only (risk 6). Lock the already-correct `players`-resolved leaderboard join with a regression assertion (AC-6) — no production change expected there.

<!-- PLACEMENT CORRECTED 2026-07-20 (PM ruling during E-267-04 AC verification). This section
     originally said "the roster-load path". That placement CANNOT satisfy AC-5:
     `_upsert_roster_jersey` (the boxscore backfill) inserts a `team_rosters` row for EVERY player in
     EVERY boxscore, so a retire performed at roster-load time is undone moments later by the backfill
     re-adding a departed player who appears in an EARLIER game — exactly the cut-mid-season case AC-5
     specifies. The constraint is the backfill, not the roster fetch. Confirmed by mutation, not
     argument: moving the call before the boxscore load fails
     `test_cut_mid_season_player_keeps_their_stat_rows`. Corrected rather than left standing because
     the next person wiring a grain into this pipeline reads Technical Approach as the design record,
     and the original would send them at a placement that silently self-undoes.
     AC-6 line-citation note: the `src/api/db.py:457`/`:521` references above are the function
     DEFINITION lines (`get_season_batting` / `get_season_pitching`); the actual joins are at
     `:506-507` and `:574-575`. Same two readers, imprecise line — the AC's premise was never wrong. -->


## Dependencies
- **Blocked by**: E-267-03
- **Blocks**: E-267-05

## Files to Create or Modify
- The roster-load path (`src/gamechanger/loaders/scouting_loader.py`, `src/gamechanger/loaders/game_loader.py`, and/or the E-267-01 module)
- Test file under `tests/` (incl. the AC-6 leaderboard-survives-departure regression assertion — the leaderboard join is already `players`-resolved at `src/api/db.py:457`/`:521`, so no production code change is expected there)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] E-257 reconciliation-scoreboard ratchet not regressed — verified at CLOSURE by the operator (not self-checked from the worktree — dev DB absent there), per TN-5

## Notes
Closes H2 (two-channel CONFIRMED/high). Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.
