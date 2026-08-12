<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# Roster dedup runs only for the generated team; opponent rosters re-split

**Date**: 2026-08-10 · **Status**: `COMPLETE` — built at `9f1f930`, reviewed three ways
(`/code-review`, codex, `/security-review`), full suite green at 4,513, and the live acceptance
pass RUN AND PASSED (see the 2026-08-12 acceptance entry: excess == the Unknown-name pair only,
zero content destroyed, verified against a backup). **Source**: stubbed from the 13-team serial
regeneration repair
(2026-08-10; pre-repair state in backup `app-2026-08-10T145722.db`, per-team before/after table
in that repair's report). The stub's mechanism was INFERENCE FROM LOGS; it is verified against
the code below, and every figure is re-measured on `data/app.db` on 2026-08-11 — none inherited.

## Goal

After this chunk, a report generation deduplicates every team whose `team_rosters` rows the load
wrote — not just the scouted one — so an opponent-side write can no longer re-split an identity a
previous run collapsed. Two safety guards ship with it, because the existing planner will
otherwise merge players it should refuse.

## The defect, verified in code

- `dedup_team_players` has exactly ONE call site in `src/`: `scouting_loader.py:366-371`, scoped
  to the scouted team's `team_id`.
- `GameLoader._load_team_stats` runs for BOTH sides (`game_loader.py:1014` own, `:1019`
  opponent). Each side's batting/pitching loop calls `_upsert_roster_jersey` (`:1362`, `:1452`),
  whose two INSERTs (`:2187`, `:2197`) write a `team_rosters` row bound to the SCOUTED team's
  `self._season_id` (`:552-554`).
- Those two INSERTs plus `scouting_loader.py:976` (the scouted team's own roster load) are the
  only sites in `src/` that CREATE a `team_rosters` row. The spray loader only SELECTs; the plays
  loader never touches the table. **Say "create", not "write"** — three other sites write the
  table destructively (`player_dedup.py:810` DELETE / `:816` UPDATE, `reconcile_at_load.py:2373`
  DELETE, `lifecycle.py:680` DELETE), and one of them is this chunk's own edit surface, which is
  why Verification 2 owes a `/security-review`.
- So generating team A writes roster rows for A's opponents and deduplicates only A. League play
  is cyclic, so **no generation order converges**.

**Root cause upstream**: GameChanger mints a distinct player UUID per PERSPECTIVE **and per
GAME**. One player on team 47 holds five roster rows — a canonical id (45 stat rows across nine
perspectives) plus three single-game ids from one opponent's perspective, one per meeting, plus
one from another. Provenance is INTACT throughout (`perspective_team_id` names the producer of
every row); the missing step is identity collapse, not provenance.

**Measured stock:**

| Population | Rows | Distinct names | Excess |
|---|---|---|---|
| The 13 repaired teams | 383 | 279 | 104 |
| Repo-wide (2026) | 13,934 | — | **7,083 across 274 of 502 rostered teams** |

The 104 sit on five teams — ids 47 (+44), 61 (+29), 293 (+12), 49 (+10), 43 (+9). Team set
confirmed two independent ways (the `reports.generated_at` window and `scouting_runs`).

## Coach-visible manifestation — the roster block, NOT split stats

The stub said a split identity "divides one player's stats across two roster rows in that team's
report." **That is refuted.** `get_season_batting` / `get_season_pitching` filter
`perspective_team_id = team_id` (`src/api/db.py`), and split ids carry only FOREIGN-perspective
rows, so they contribute nothing to a report's stat tables.

What breaks is `_query_roster` (`generator.py:730`), which selects every `team_rosters` row with
no grouping: team 47's pre-repair report on disk renders **123 roster entries over 27 distinct
rendered names** — one player printed nine times.

Two bounds on the "no reader" half, both load-bearing:

- The zero-own-perspective-split check holds for `player_game_batting`, `player_game_pitching`
  and `spray_charts`, and FAILS on `plays` batter-side (2 groups, Unknown stubs).
- The foreign-perspective duplicates (653 batting groups, 182 pitching groups) ARE read by a live
  writer: `generator.py:1080-83` calls `reconcile_game(..., dry_run=False)` in the report path,
  and the engine reads `WHERE game_id=? AND team_id=? AND perspective_team_id=?`
  (`engine.py:386-392`, `:455-460`) — scoped to the REPORT's perspective, not to each row's own
  team. Do not restate "nothing reads them."

## ⚠ Why two guards ship with the fix

`find_duplicate_players` guards only `LENGTH(folded first_name) > 0`. Two `Unknown Unknown`
placeholder ids fold to identical names, so they form a single-terminal-name component and
COLLAPSE. **Fork refusal cannot catch this — it fires on DISTINCT names. "Zero refused forks" is
what this hazard looks like, not evidence of safety.**

Executed against team 47's current plan: two `Unknown Unknown` ids in the SAME game under the
SAME perspective are two different pitchers — 4 outs / 40 pitches / 3 ER / 10 BF versus 6 outs /
26 pitches / 0 ER / 8 BF. `_delete_or_update_game_stats` (`player_dedup.py:720-733`) ranks
completeness, ties, and DELETES the duplicate. A real appearance is destroyed.

**Scale, with the measurement definition stated** — over the full 2026 plan (2,746 collapses /
7,073 merges), comparing every non-key column of `player_game_batting` (19) and
`player_game_pitching` (14): **488 conflict-deletions whose deleted row differs from the
survivor, 33 of them on NAMED players**; 61 `Unknown Unknown` collapses merge away 443 ids;
season 2025 contributes zero. (A narrower hand-picked column subset yields 476; counting
`team_rosters` jersey/position differences as content yields 1,280. Use the 488 definition.)

**Scoping fact that makes the acceptance pass safe**: on the five residual teams, post-guard,
all 112 stat-row conflicts are **byte-identical — zero differing-content deletions**. The
content-aware refusal protects the other 269 teams the fix reaches over time, not this pass.

## Files

- `src/gamechanger/loaders/game_loader.py` — new `rostered_team_ids` set; record in
  `_upsert_roster_jersey`.
- `src/gamechanger/loaders/scouting_loader.py` — Hook-1 becomes a loop.
- `src/db/player_dedup.py` — Unknown-name detection guard; plan-time content-aware refusal.
- `src/cli/data.py` — display the new refusal class (6 `refused_forks` read sites to mirror).
- `tests/test_scouting_loader.py`, `tests/test_player_dedup.py`, `tests/test_cli_data.py`,
  `tests/test_player_line_reconcile.py`.

## The work

### 1. Touched-team set (`game_loader.py`)

Add `self.rostered_team_ids: set[int]` beside `redirect_map` / `processed_event_ids`
(`:555-571`) — the same per-run side-effect-set pattern, naturally scoped because `GameLoader` is
constructed fresh per report run. Record `team_id` inside `_upsert_roster_jersey` (`:2165`):
both INSERT branches live there, so it is the single choke point for boxscore-sourced roster rows
on both sides.

### 2. Dedup loop (`scouting_loader.py`)

Replace the single Hook-1 call with a loop over `[team_id] + sorted(rostered_team_ids -
{team_id})`, each with `db_season_id` and `manage_transaction=False`, each in its own
`try/except` so one opponent's failure does not skip the rest.

- **Scouted team FIRST is load-bearing, not cosmetic.** Opponent merges delete `players` rows and
  re-point roster rows globally; running them first weakens the `P1 ⊆ P2` argument
  `_pending_collapse_player_ids` rests on.
- **Position UNCHANGED** — after `_reconcile_departed_roster` (which needs RAW pre-dedup ids),
  before the commit. Both documented long-span ordering couplings in `_load_team_core` terminate
  above this hook; do not move either capture.
- **Season id**: opponents dedup under the SCOUTED team's `db_season_id` — the season the rows
  were actually written under, not the opponent's own derived one.

### 3. Unknown-name guard (`player_dedup.py`)

Exclude placeholder names from detection, mirroring the existing `LENGTH > 0` guard. Scope it to
the exact stub value the loaders write (`ensure_player_row` receives `"Unknown"` from
`game_loader.py:1359-1360` when the boxscore omits a name) — do not invent a broader heuristic.

### 4. Content-aware refusal (`player_dedup.py`, `cli/data.py`)

Refuse at PLAN time, never mid-merge: skipping one conflicting delete leaves the blanket
`UPDATE {table} SET player_id = ?` to hit the UNIQUE and abort the component anyway. Add a
predicate that compares conflicting `(game_id, perspective_team_id)` rows for each candidate
duplicate and refuses the component when any pair DIFFERS, with a WARN — structurally the same
shape as the existing fork refusal. One new `DedupPlan` field beside `refused_forks`; mirror its
handling at the 10 read sites (6 `cli/data.py`, 3 `player_dedup.py`, 1 `scouting_loader.py`).

Refused members correctly LOSE their `_pending_collapse_player_ids` exemption — a component that
will never merge must stay retirable, which that docstring already requires.

## Acceptance

**The criterion moves with the Unknown guard, and bare `rows == names` is now WRONG.** Measured:
with the guard, team 47 legitimately retains ONE excess row (its two `Unknown Unknown` ids);
teams 49, 61, 43, 293 have zero Unknown-bearing duplicate groups. The gate is:

> all 13 repaired teams at **excess == Unknown-name duplicates only**, zero re-bloat, measured
> simultaneously in one query after a serial pass over the five residual teams.

## Verification

1. Full suite: `python -m pytest > /tmp/out.txt 2>&1; echo "RC=$?" >> /tmp/out.txt`, then READ
   the file for RC and the pass/fail line. Never a piped exit code.
2. `/code-review` **and `/security-review`**, both operator-typed as SEPARATE messages (a session
   cannot invoke either). The security pass is owed, and an earlier draft of this spec wrongly
   waived it: the chunk edits DELETE behavior in `player_dedup.py` (the refusal changes what is
   deleted; the loop changes WHOSE rows are), and its acceptance pass drives destructive
   `bb report generate` runs. Offer the codex second opinion too — this is a shared merge seam
   consumed by both the load path and the CLI. ⚠ Check `/security-review`'s scope before trusting
   its verdict: on uncommitted work it has been handed the COMMITTED range (standing residual).
3. `python3 src/safety/pii_scanner.py --staged`; reconcile scanned-count, staged-count AND
   renamed-count. Then give **every skipped staged file a manual pass with a positive control**
   (CLAUDE.md step 6) — counts alone are not the gate. A `done/` move is a rename, and `.claude/`
   is invisible to the scanner even when passed explicitly, so a silent RC=0 there is vacuous.
4. **Post-commit acceptance pass, its own results commit.** `bb db backup` FIRST — load-bearing,
   not ceremony, because the pass deletes rows.
   **`bb report generate` takes a GameChanger URL or `public_id` slug, NOT a DB `team_id`**
   (`src/cli/report.py:64-68`), so the five targets must be resolved first — the slugs are
   deliberately not written here (identifier hygiene):

   ```sql
   SELECT id, public_id FROM teams WHERE id IN (47, 49, 61, 43, 293);
   ```

   Then run `bb report generate <public_id>` serially, one per team, in that id order (47 first —
   it is the only one carrying an Unknown-name pair, so a guard regression shows up on run 1).
   Name the destructive seam up front (`bb report generate` hard-deletes
   `games` and their child surface via reconcile-at-load, and unreachable
   `teams`/`players`/`team_rosters` via orphan reclamation). Predicted deletions on those five:
   92 batting, 20 pitching, 104 roster, 758 `reconciliation_discrepancies` — all byte-identical
   post-guard. A differing-content deletion, or a count divergence, is a finding.
   **Reach**: those five teams' games span 98 distinct other opponents, which the pass also
   repairs. Of the other 8 repaired teams only three are touched; the other five stay converged
   by inertia — report that, do not claim the pass proved them.

## Out of scope

- **The repo-wide 7,083-row backlog.** Healing is opportunistic — a team converges only when some
  report touches it. `bb data dedup-players --execute` already drives the identical planner, so
  backlog repair has an audited operator path that keeps 61 Unknown collapses and 488
  differing-content deletions out of the implicit report path, where per-team failures are
  swallowed at ERROR with no operator surface. Stub at handoff; recommend that split.
- **Deciding WHICH row is right** when two conflicting rows differ. This chunk refuses; it does
  not adjudicate.
- **Scorekeeper spelling variants.** By my own rule (folded edit distance ≤ 2 across first+last,
  Unknown excluded, restricted to pairs the prefix rule can never join): 8 pairs across the 13
  teams, 6 of them jersey-corroborated. Shape: one-letter surname variants (`Doe`/`Doo`) and
  non-prefix first-name variants (`Jane`/`Jayne`). Unreachable by prefix matching and invisible
  to the rows-vs-names measure — so a passing gate is NOT "one row per human."
- **Season rollover.** Opponent dedup keyed to the scouted team's season is safe today only
  because no team holds roster rows in more than one season and no 2025-roster team appears in a
  2026 game (both measured). At rollover an opponent accrues a second `season_id` that
  season-scoped dedup can never merge across — permanent `rows > names`. Known limit, with its
  trigger.
- **Transaction scale.** A first run touching ~100 opponents executes hundreds of merges, each
  ~12 full-table `UPDATE … WHERE player_id = ?` statements across 6 tables, in ONE write
  transaction on the WAL file shared with the admin UI and cron. Unmeasured — measure it during
  the pass rather than guessing.
- The plays-stage dedup gap (`.claude/rules/data-model.md`): plays stubs enter `players` only,
  never `team_rosters`, so detection cannot see them. Untouched, still true.

## Test notes

- **RED first, three of them**: (a) an opponent block carrying a same-name/different-uuid pair →
  the opponent's roster converges; (b) two `Unknown Unknown` ids in one game/perspective must NOT
  merge and both stat rows survive (reproduce the shape above); (c) two same-named ids whose
  conflicting rows DIFFER are refused, component intact, WARN emitted.
- **Invert, do not delete**, `tests/test_player_line_reconcile.py::
  test_regime_B_on_the_OPPONENT_block_has_no_closer_in_any_shape`. It asserts precisely the
  property this chunk removes ("the opponent block has no closer in ANY shape") and pins
  `rows_per_run == [9, 18, 9, 9]` on identical-name churn. Rewrite it to assert the closer fires,
  keep the regime-B coverage, and re-derive the pinned sequence from an EXECUTED run.
- **16** test files reference `GameLoader`/`ScoutingLoader` (re-counted 2026-08-11; an earlier
  draft said 14, from a narrower grep). `src/` is touched, so the FULL suite gates regardless —
  the count is context, not the selector. Include `tests/test_cli_data.py`: both guards change
  what `bb data dedup-players` plans and prints.

## Progress log

- **2026-08-10** — Stubbed from the controlled serial repair. No code, no second pass.
- **2026-08-11** — Stub → executable. Mechanism verified in code (it was log inference).
  Stub figures re-measured and exact. Two stub claims CORRECTED: the coach-visible damage is the
  roster block, not split stats; and the repo-wide scale is 51% of roster stock, not 104 rows.
  An adversarial review of the investigation found the Unknown-name collapse class — a merge of
  two different pitchers that destroys a real line — which added both guards and moved the
  acceptance criterion off bare `rows == names`. Operator rulings: dedup every touched team; live
  pass after the commit; backlog as a stub.
- **2026-08-12, EXECUTE** — audited the spec against the repo BEFORE writing code. **Every
  load-bearing citation held**: `dedup_team_players`'s single `src/` call site (`scouting_loader.py
  :366-371`; `cli/data.py:236` is a comment, not a call), `_load_team_stats` at `:1014`/`:1019`,
  `_upsert_roster_jersey` at `:1362`/`:1452` with both INSERTs at `:2187`/`:2197`, `_season_id` at
  `:552-554`, `scouting_loader.py:976`, and the three destructive writers. The
  `_pending_collapse_player_ids` ordering argument is CONFIRMED with its mechanism named:
  `merge_player_pair` re-points `team_rosters` GLOBALLY (`:816`, unscoped `WHERE player_id = ?`)
  and deletes `players` rows (`:663`), so an opponent merge run first can ADD a node to the
  scouted team's component and turn a P1 collapse into a refused fork — stranding exactly the ids
  the exemption protected. Scouted-team-first preserves today's behavior byte for byte.
  **One spec miscount, not load-bearing**: the `refused_forks` read sites are 8 in `cli/data.py`
  (162, 169, 174, 197, 199, 230, 237, 279), not 6 — 12 reads total, not 10. All mirrored.
  Three RED tests written first, each failing for the right reason; the byte-identical-conflict
  control passed from the start, so the refusal is content-aware and not conflict-aware.
  **Suite: 4,507 passed, RC=0** (baseline 4,495 + 12 new). Ruff clean.
  Positive controls, per the mutation protocol (`__pycache__` cleared each way, no-mutation
  control first, per-test outcomes): opponents-first → only the ordering test fails; try/except
  hoisted out of the loop → only the isolation test fails; placeholder guard removed from the
  reconcile diagnostic → it named `stub-1` where detection returns nothing.
  **Two additions beyond the spec's Files list, both forced by the change and invisible in its
  diff.** (1) `src/db/reconcile_at_load.py` — `_dedup_candidate_victims` documents that it mirrors
  detection's name guards precisely so it never names a pair `bb data dedup-players` cannot act
  on; the new placeholder exclusion had to be mirrored there or that claim became false (proven by
  the mutation above). Its jersey half is a deliberate over-name and was left alone. Its import
  comment's cycle claim ("`player_dedup` imports nothing from `src`") also stopped being true and
  was restated as measured. (2) `src/db/players.py` — `PLACEHOLDER_NAME` added as the canonical
  name for the stub value, imported by detection; the SQL literals in that module and in
  `game_loader` still spell it out, which the constant's comment states rather than hides.
  Docs swept by file → read → ruled: `docs/admin/operations.md:579` said the command "only merges
  within the *scouted* team (an opponent block has no closer at all)" — now false, corrected; the
  `bb data dedup-players` section gained both refusal classes and the placeholder note;
  `.claude/rules/data-model.md` gained the four durable invariants. The 579 hit is the one a token
  grep for "dedup" would have found but a grep for "opponent roster" would not.
- **2026-08-12, `/code-review`** — 5 findings, each VERIFIED against the repo before triage; 4
  folded in, 1 routed out as another chunk's code. Two were caught only because the reviewer read
  the interaction rather than the diff.
  1. **(medium) The content refusal re-opens regime B on a differing opponent line.** REAL,
     reproduced: with a scorekeeper edit between generations the sequence is
     `[9, 18, 9, 9]` — character for character the pre-chunk pin. **Unimproved subset, not a
     regression**, and the mechanism is worth stating: the refusal stops the DEDUP path deleting a
     differing row, then the player-line retire deletes it on run 3 anyway, after which the
     component is conflict-free and merges. So the guard DEFERS that deletion to the grain the
     operator already ruled on (IDEA-185), rather than preventing it. Now pinned by
     `test_the_content_refusal_leaves_regime_B_open_on_a_DIFFERING_opponent_line`; docs qualified.
  2. **(low) The operator-doc closer claim was unqualified** on placeholder-named ids. Correct —
     detection excludes the stub, so that shape has no closer at all. Both open shapes now
     enumerated at `operations.md`. (The reviewer's "disproportionately opponent-side" frequency
     claim is NOT restated: unmeasured.)
  3. **(low) `plays_loader._persist_final_score` uses `OR`, so a half-derived pair nulls a stored
     counterpart.** VERIFIED as real: the parser returns two independent `.get`s, and the
     docstring three lines up promises an all-or-nothing write. **NOT this chunk's code** — it
     landed with the plays final-score recovery — and all 2,464 rows are NULL today, so it is
     LATENT and would first fire during the planned full regenerate. Routed to the operator, not
     bundled.
  4. **(low) My `PLACEHOLDER_NAME` comment's producer list was incomplete** — it named the two
     `GameLoader` sites and missed `PlaysLoader` (×2) and `ScoutingSprayChartLoader`. My own prose,
     my own defect; corrected, and the correction now records the distinction that matters (only
     the `GameLoader` path writes `team_rosters`, so only it is visible to detection).
  5. **(low) `team_id` was excluded from the content comparison but is NOT in
     `UNIQUE(game_id, player_id, perspective_team_id)`** — the one column an exclusion-based
     definition gets wrong. FIXED by including it, after measuring that this is FREE: component-
     member collisions differing ONLY in `team_id` number **zero** across both seasons and all
     16,230 detected pairs, so no refusal is added and the fleet-wide 488 figure is unchanged. (The
     raw corpus has 1,575 such batting pairs — every one two unrelated players sharing a game and
     perspective, never co-rostered. Counting those would have been the wrong number.) The spec's
     "19 and 14 non-key columns" therefore reads 20 and 15.
  Suite after the fixes: **4,508 passed, RC=0**; ruff clean.
- **2026-08-12, codex review** (`scripts/codex-review.sh uncommitted`, `RESULT_FILE` read whole) —
  2 findings, **ZERO overlap with `/code-review`'s 5**, which is now the strongest single-diff
  evidence yet for the standing "keep both" verdict. Both verified and fixed; both were forward
  hazards with zero live instances, and in both cases the MEASUREMENT changed the fix.
  1. **(high) The placeholder guard covered `first_name` only, while the loaders write the stub
     into `last_name` too.** Correct, and it is my scoping error: detection requires equal
     surnames AND a first-name prefix, so when both surnames are the stub the equality is
     satisfied by two ABSENCES and a prefix pair rests on nothing — the vacuous-match shape one
     dimension over from the blank-name case codex's own predecessor found. **But the obvious fix
     was wrong.** Measured before writing it: all 6 placeholder-surname pairs in the 2026 corpus
     are `('Riley Vance','Unknown')` twice over — GC writing the WHOLE name into `first_name` — so a
     blanket surname guard would have destroyed 6 real merges to close a hazard with 0 live
     instances. Shipped the narrow rule instead: a stub surname voids only a STRICT-PREFIX pair,
     never an equal-first-name one. Post-fix detection is byte-identical to pre-fix (35 / 16,195),
     with all 6 still detected.
  2. **(medium) `_delete_or_update_rosters` deletes the duplicate's roster row without preserving
     `jersey_number` / `position`.** Reproduced (`canonical=(NULL,NULL)` + `('23','CF')` →
     survivor still `(NULL,NULL)`). Coach-visible: the report roster block renders both. Codex's
     real contribution was the EXPOSURE argument — this chunk multiplies traffic through that
     helper from one team to hundreds. Fixed by BACKFILLING before the delete, never overwriting,
     mirroring `_upsert_roster_jersey`'s own NULL-only semantics. Note this also VINDICATES the
     spec's decision to keep `team_rosters` out of the content-refusal definition: the right
     remedy was to stop losing the data, not to refuse the merge over it. Zero live instances (no
     detected pair has a jersey on the duplicate and none on the canonical); `position` is NULL on
     all 13,934 rows.
  Suite: **4,512 passed, RC=0**; ruff clean.
  **Routed OUT, on the operator's ruling**: the `plays_loader._persist_final_score` `OR`-guard
  defect became `.project/specs/2026-08-12-plays-final-score-half-pair-clobber.md` (`STUB`). It
  must land BEFORE the full regenerate — that regenerate is what would first write the damage.
- **2026-08-12, LIVE ACCEPTANCE PASS — RUN, AND IT PASSES.** Operator ruled: run it. Code at
  `9f1f930`; backup `data/backups/app-2026-08-12T022220.db` taken FIRST. Three generations, not
  five: after team 47, teams 49 and 61 had ALREADY converged as its opponents, so only 43 and 293
  still needed a run of their own. That is the fix's whole thesis demonstrating itself.

  **The gate: all 13 repaired teams at 280 rows / 279 names / excess 1, and that 1 IS the
  Unknown-name pair** (`stub_excess == 1`, `collapses == 0` on every one of the 13 — nothing left
  the planner can merge). Zero re-bloat: 49 and 61 stayed converged through runs 2 and 3.

  **Reach, measured**: run 1 alone swept 20 teams and performed 1,227 merges. Repo-wide excess
  **7,048 → 4,347** across **271 → 224** affected teams — 38% of the backlog cleared by three
  reports, which is the opportunistic healing this spec predicted rather than a repair pass.

  **No content was destroyed, verified against the backup rather than trusted from the refusal
  counter.** 274 batting and 57 pitching rows were deleted, yet the set of DISTINCT content
  signatures (every column but `id`/`player_id`) is IDENTICAL before and after — 48,009 and 11,723
  — with ZERO signatures vanishing. Every deleted row was a byte-identical duplicate. `games`
  unchanged at 2,303; no sweep failure, no savepoint rollback, zero ERROR lines.

  **The predictions land within one row each, and every shortfall has the SAME cause — the guard**:
  batting 91 (predicted 92), pitching 19 (predicted 20), roster 103 (predicted 104). All three
  predictions were measured PRE-guard; team 47's retained `Unknown` pair is exactly one unmerged
  pair, hence exactly one surviving row in each table. Not a divergence — the difference IS the
  guard.

  **The content-aware refusal FIRED IN PRODUCTION, on its first real outing**: a 7-member component
  on team 301 refused because merging would have DELETED a `player_game_batting` row differing in
  `rbi`. Pre-fix that RBI was gone. This is the guard's reason for existing, observed on live data.

  **Coach-visible, the thing this was all for**: team 47's report went from **123 roster entries
  over 27 names to 25 entries over 24 names**, the single exact duplicate being the deliberately
  retained stub pair. ⚠️ Still visible to a coach, and correctly OUT OF SCOPE: a few
  jersey-corroborated scorekeeper spelling variants (one-letter surname and non-prefix first-name
  differences) render as separate entries. This spec named that class and excluded it — a passing
  gate is NOT "one row per human", exactly as written.
- **2026-08-12, the deferral this supersedes — recorded because the reasoning still binds.**
  Verification 4 below predates the "Regeneration hazard — RULED 2026-08-12" entry in
  `.project/specs/README.md`, which de-scopes REPAIR halves in favor of one full regenerate. Read
  as written, this chunk's five-team pass IS a repair pass, so the ruling reaches it and it must be
  adjudicated rather than run by default. **Not run in this commit.** The argument each way, for
  the operator: the pass is no longer needed to FIX those five teams (the regenerate supersedes
  it), but it is the only evidence that the fix behaves correctly against real data BEFORE the
  regenerate depends on it — and the regenerate is a much larger destructive action to take on
  test-only confidence. The cheap middle exists and is what I would recommend: run team 47 ALONE
  (it is the only one carrying an `Unknown Unknown` pair, so a guard regression shows on run 1),
  after `bb db backup`, and treat the other four as superseded. Every figure Verification 4
  predicts was measured pre-guard and needs re-measuring against the shipped code either way,
  since the guards changed what merges.
- **2026-08-12, `/security-review`** — **the diff-scope residual FIRED, and the review as handed
  over was VACUOUS.** Its `DIFF CONTENT` was the COMMITTED range: the file list contained none of
  the six `src/` files this chunk touches, so **500 lines of uncommitted `src/` changes were
  invisible to it**, and the only three hits for this chunk's identifiers sat inside committed
  spec MARKDOWN — an excluded category, so they could yield nothing. A clean verdict over that
  input would have certified nothing. Re-run against `git diff HEAD -- src/` (762 lines).
  **Result on the correct diff: no finding at confidence ≥ 7**, and the clean result carries a
  POSITIVE CONTROL — detection was shown FIRING (`Jo`/`John`, and the `Riley Vance` stub-surname
  pair) before its exclusions were trusted. Cleared with evidence, not by inspection: every
  interpolated value in the new dynamic SQL traced to ground (module-literal table names;
  column names from `PRAGMA table_info`, with **no runtime DDL anywhere in `src/`**, so columns can
  only originate in `migrations/`; count-derived placeholders) while the attacker-influenced
  values — player UUIDs from the third-party payload — are BOUND; parameter alignment executed
  live in both scoped and unscoped forms; the new `team_rosters` COALESCE executed against decoy
  rows on another team AND another season, crossing neither; deletion authorization intact (every
  path into `generate_report` is admin-gated); no new PII class in the logs.
- **2026-08-12, the one fix the security pass produced** (raised as a non-security observation):
  the per-team `except` did not roll back before continuing, and the loop shares ONE transaction
  committed at the end — the shared-connection partial-commit footgun. **The prescribed remedy was
  wrong for this seam**: that rule addresses a loop with a per-item COMMIT, and a bare
  `rollback()` here would discard the whole transaction — both reconcile grains' pending retires
  AND every opponent already merged this run — to contain one team's failure. Fixed with a per-team
  SAVEPOINT instead, the same shape `execute_collapse` uses per component. The test rejects BOTH
  wrong remedies and each mutation fails on its own assertion: no savepoint → "the failing team's
  partial write rode the commit"; bare rollback → "a rollback discarded work that a savepoint would
  have kept". Final suite: **4,513 passed, RC=0**; ruff clean.
- **2026-08-11, codex-spec-review** (`scripts/codex-spec-review.sh`) — 5 findings, each verified
  against the repo before folding in, all folded: acceptance pass was NOT EXECUTABLE (`bb report
  generate` takes a `public_id`, not a `team_id` — lookup step added); `/security-review` was
  wrongly waived (this edits DELETE behavior); the PII step omitted the manual pass on skipped
  staged files; "the ONLY `team_rosters` writers" was false as written (three destructive writers
  exist — narrowed to "create"); test-file count 14 → 16. The sixth flag, `READY` as an invalid
  Status, is the KNOWN STALE RUBRIC — `.project/codex-spec-review.md:48` still lists four
  statuses; `CLAUDE.md` added `READY` on 2026-08-09. Standing residual, not a defect here;
  Status stays `READY`.
