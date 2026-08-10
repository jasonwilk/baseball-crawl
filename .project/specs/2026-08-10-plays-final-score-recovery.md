# Plays final-score recovery — the game-ending run dropped on a skipped final play

**Date**: 2026-08-10 · **Status**: `READY`
**Source**: `.project/research/ingestion-fidelity-seed.md` §2, taken as a chunk by operator ask.
The seed is a CLAIM and was audited against the repo and the live API before this spec; every
number below is re-measured on a **settled** dev DB, not inherited.

## Goal

After this chunk, `PlaysParser.parse_game` returns the game's true plays-derived final score
alongside its plays, and `PlaysLoader` persists it per perspective. Today that score is lost
whenever the game's last play hits a parser skip path — which is how walk-off and run-rule
endings finish. **91 of 2,459 game-perspective units (3.7%), across 88 games, are short a total
of 102 runs** (81 units × 1 + 9 × 2 + 1 × 3). This chunk fixes nothing already stored; a
post-commit backfill does that.

Measured population (settled dev DB, 2,303 games / 143,613 plays):

| Class | Units |
|---|---|
| Reconcile exactly | 2,358 |
| **THE DEFECT — short by 1-3** | **91** |
| Plays EXCEED box (two scorebooks disagreeing — NOT this bug) | 9 |
| Other (abandoned charting — NOT this bug, see Out of scope) | 1 |

## Why it matters (measured, not argued)

- **Youth is hit ~2.5× harder**: 6-inning regulation **7.9%** (18/228) vs 7-inning **3.2%**
  (64/2,022); unfetched 4.3% (9/209). Short games under aggressive run-rules end mid-inning more
  often, and ending mid-inning is exactly when the winning run lands on a skipped play. Bound:
  only 66 of 1,029 teams have `innings_per_game` fetched, so this is directional, not precise.
- **No stat is lost, only the score.** GameChanger's own boxscore does not count the abandoned
  final PA either (33 of 37 sampled games matched its batters-faced exactly). `plays` holds no
  stat columns; RBI (`migrations/001_initial_schema.sql:191`) and runs-allowed (`:215`) are
  boxscore-sourced and already correct. Do not re-litigate this as a pitching/RBI defect.

## Expert consultation

`api-scout` was consulted (the payload-shape claims below are its lane per principle D): 114
games probed across HS, Legion, 10U, 12U, 14U and 18U, 136 live calls, zero errors. Its findings
were then **verified independently against raw payloads by the spec author** rather than
relayed — four payloads opened directly, plus the exhaustive run in Verification 0.

`baseball-coach` was **not** consulted, deliberately: the only domain claim here (an unresolved
plate appearance is not a completed at-bat, so it earns no AB/BF/RBI) was settled empirically
against GameChanger's own boxscore rather than by coaching judgment, which is the stronger
evidence for this question.

## Files

- `migrations/013_game_perspectives_plays_final_score.sql` — created.
- `src/gamechanger/parsers/plays_parser.py` — `parse_game` return type + seeding rule; module
  docstring example at `:19`.
- `src/gamechanger/loaders/plays_loader.py` — sole `src/` caller (`:156`); persist + warn.
- `tests/test_plays_parser.py` — new cases; update the 3 `parse_game` call sites (`:111`,
  `:130`, `:1567`).
- `tests/test_plays_loader.py` — new persistence + warning cases.

## The work

### 1. Migration `013`

Add two nullable INTEGER columns to `game_perspectives`: `plays_final_home_score`,
`plays_final_away_score`. NULL is load-bearing provenance ("not yet derived"), same contract as
`teams.innings_per_game` in `.claude/rules/data-model.md`. No DEFAULT, no NOT NULL, no backfill
in the migration.

**Grain rationale — do not "simplify" this onto `games`.** Two perspectives of one game
genuinely disagree: verified in the live DB where one `play_order` reads `8-7` under one
perspective and `10-7` under the other. A game-level column is last-writer-wins and would
manufacture a false discrepancy. `game_perspectives` is already
PK(`game_id`, `perspective_team_id`) — the grain `recon_scoreboard.py` uses.

### 2. Parser — `parse_game` returns `ParsedGamePlays`

Replace the bare `list[ParsedPlay]` return with a frozen dataclass carrying `plays`,
`final_home_score: int | None`, `final_away_score: int | None`.

**THE SEEDING RULE — walk the RAW payload backwards from the end, skipping INERT plays, and
take the first non-inert play's `home_score`/`away_score`.** A play is inert when
`final_details` is empty **AND** `did_score_change` is false. Return `(None, None)` when there
are no plays or all are inert.

Read the RAW payload, never the parsed list — that is what makes the fix immune to which of the
three skip paths fired, which is required: 5 of the affected units are away-side and 2 end on 3
outs, i.e. run-rule endings reaching the parser through the `Runner Out` / `Inning Ended` path,
not the abandoned-PA path. A path-(a)-only fix leaves those broken and still looks correct.

Do **not** reuse the existing `.get("home_score", 0)` default when seeding — absent must stay
distinguishable from a real 0.

**Three rules were tried and rejected. Do not reintroduce any of them.**

| Rejected rule | Why it fails |
|---|---|
| "last raw play" / "last non-NULL score" | The trailing phantom carries `0`/`0` as **integer zero, not null** (verified: 68-play payload, zero nulls anywhere). Sets **every game's final to 0-0**. |
| "last raw play with non-empty `final_details`" | **The run-carrier HAS empty `final_details`.** Emptiness cannot separate carrier from phantom; the runs stay lost. |
| `max()` over all raw plays | **Fixes most units but BREAKS 5.** Scorekeeper corrections (a run entered then rescinded) leave a non-monotone running score and max latches onto the retracted run — verified: rule 14-6 vs max 15-6, and rule 6-5 vs max 6-6, against officials 14-6 and 6-5. Disqualified by the CLAUDE.md north star: no stat gets closer at another's expense. |

**Why the survivor is trusted**: every one of the **88** affected games was fetched and tested
against its real payload in one clean pass — **87 recover the official final, 1 cannot
(abandoned charting, below), 0 errors**. Corroborated independently across 114 games at all
levels: zero instances of the rule's fatal case (a run-carrier reporting
`did_score_change: false`), zero non-terminal carriers.

**Stated bound, keep it honest**: the backwards walk never runs more than one step in observed
data (trailing-inert run length was 1 in 107 games, 0 in 7, never ≥2). Keep the loop — it costs
nothing and fails safe — but it is *defensive*, not validated beyond one step.

### 3. Loader — persist and warn

`_load_game` unpacks `.plays`. After a successful insert, UPSERT the two finals onto
`game_perspectives` **inside the existing per-game transaction** (`plays_loader.py:174-183`).
Use `INSERT ... ON CONFLICT DO UPDATE`, not a bare `UPDATE`: the row is normally created by
`GameLoader` (`game_loader.py:1000`, `INSERT OR IGNORE`) earlier in the pipeline, but a bare
UPDATE would silently no-op if it were absent.

Log a **WARNING** when the derived finals disagree with the `games` row's scores. This is the
standing detector for the two legitimate-disagreement classes below and for any payload shape
this population does not contain.

### 4. Tests

Each of the three skip paths as the FINAL play with a changed score → **no extra `plays` row AND
a correct final** (the seed's explicit requirement). Plus:

- `test_inert_phantom_does_not_zero_final_score` — the 0-0 phantom must NOT zero the final;
- the run-carrying empty-`final_details` phantom → recovered;
- `test_non_monotone_payload_does_not_overshoot_final_score` — the `max` regression test.
  Without it, a future author re-derives `max` and the suite stays green;
- final play missing score keys → falls back, does not write 0;
- empty payload / all-inert payload → `(None, None)`;
- loader persistence and the disagreement WARNING.

## Out of scope

- **The post-commit backfill** — its own small session: back up (`python3 scripts/backup_db.py`)
  → reset → re-scout, per seed §5. `bb report generate` is DESTRUCTIVE (reconcile-at-load and
  orphan reclamation both hard-delete). Plain regeneration cannot repair these games —
  whole-game idempotency at `plays_loader.py:143-152` skips any game that already has plays.
  **Success criterion is 91 → the abandoned-charting residual (≥1), NOT → 0.** Measured
  expectation: 87 of the 88 affected games recover.
- **Runs as a reconciliation-scoreboard stat** — chunk 2, routed as a stub. Add it **ungated**
  first: gating it immediately raises `BaselineError` (exit 4) against a baseline lacking the
  key. It must treat the 9 two-scorebook and the non-monotone units as legitimate disagreement.
- Seed §1, §3, §4. §5 sequences §2 after §1/§3, but §2 is mechanically independent.

### Two classes that are NOT this defect — do not chase them

1. **Abandoned charting (unrecoverable).** One affected game's play-by-play is complete and
   internally consistent, ending at inning 4 bottom / 3 outs / `8-12`, with only the inert
   phantom after it, while the official is `8-13`. The phantom sits at inning **5** top, so the
   game continued and the scorekeeper stopped charting. The run is absent from the payload; no
   seeding rule can recover it. This is why the backfill will not reach 0.
2. **Two scorebooks disagreeing (9 units).** Plays EXCEED the boxscore. Documented behavior —
   `.claude/rules/perspective-provenance.md` fn.1, E-261's 12-4 vs 12-5.

## Verification

Run in order. Redirect pytest to a file and capture `$?` separately — never pipe it.

0. **Confirm the inputs THIS chunk depends on are stable — do not gate on unrelated churn.**
   Two traps, both hit while writing this spec. (a) Row counts do NOT detect an UPDATE: `games`
   and `plays` counts held identical while `games.home_score` changed underneath, moving the
   population from 92 units to 91. (b) `player_game_batting` / `player_game_pitching` drift on
   their own and are **irrelevant here** — gating on them chases a number this chunk never uses.

   Sample these twice, a minute apart; they must agree with each other, and the first two must
   match the values below:

   ```sql
   SELECT (SELECT SUM(home_score+away_score) FROM games) AS score_sum,      -- 28677 at spec time
          (SELECT SUM(home_score+away_score) FROM plays) AS plays_score_sum,-- 877775 at spec time
          (SELECT COUNT(*) FROM games) AS games;                            -- 2303 at spec time
   ```

   Then run Verification 6 — it must return **91**. If `score_sum` or the step-6 count differs,
   the population moved: re-measure steps 5 and 6 and record the new baseline in the progress
   log before comparing anything. A differing `player_game_*` count is NOT a reason to stop.
1. **Migration applies cleanly**, then `PRAGMA table_info(game_perspectives)` shows both new
   columns as nullable INTEGER. Expected: 2 new columns, no error.
2. **Full suite** (chunk touches `src/`, `tests/`, `migrations/`):
   `python3 -m pytest > /tmp/out.txt 2>&1; echo "RC=$?" >> /tmp/out.txt`, then read the file for
   the RC and the pass/fail line. Expected: RC=0, all pass.
3. **Positive control — prove the two guard tests can fail before trusting their pass**
   (principle G). Name them exactly so this is runnable:
   `test_inert_phantom_does_not_zero_final_score` and
   `test_non_monotone_payload_does_not_overshoot_final_score`.

   Write both tests FIRST, before touching the seeding rule, and run:

   ```bash
   find . -name __pycache__ -type d -prune -exec rm -rf {} +
   python3 -m pytest tests/test_plays_parser.py \
     -k "inert_phantom_does_not_zero or non_monotone_payload_does_not_overshoot" \
     > /tmp/pc.txt 2>&1; echo "RC=$?" >> /tmp/pc.txt
   ```

   Expected BEFORE the fix: **RC=1, 2 failed** (`parse_game` returns a bare list, so they fail on
   the missing attribute — that is a legitimate red). Expected AFTER: **RC=0, 2 passed**.

   To re-demonstrate once the fix exists, mutate the seeding rule to the two rejected forms and
   confirm each test catches its own case — clearing `__pycache__` before each run and each
   restore, per `.claude/rules/testing.md` (a size-preserving edit may not invalidate the cache):
   - seed from `plays[-1]` → `inert_phantom_does_not_zero` must FAIL (returns 0-0);
   - seed from `max()` → `non_monotone_payload_does_not_overshoot` must FAIL (overshoots by 1).

   Report per-test outcomes, never an aggregate count.
4. **Test-scope discovery**:
   `grep -rl --include="*.py" "plays_parser\|plays_loader" tests/` — the `--include` is required
   or the result contains `__pycache__/*.pyc` and a fixture README and is not a runnable
   selector. Run every `.py` it returns, not just the two files in §Files.
5. **`bb report reconcile-scoreboard` BEFORE and AFTER, both readings in the progress log.**
   Reference on the settled DB:

   | Side | Stat: exact% / abs-Δ |
   |---|---|
   | pitching | BF 98.5/473 · SO 99.6/61 · BB 98.9/139 · H 99.2/151 · HBP 99.9/16 |
   | batting | AB 99.7/191 · H 99.9/57 · BB 100.0/15 · SO 100.0/30 · HBP 100.0/5 |

   `dropped_pitch_events 0`, `no_plays_units 2252`, `self_games 0`, **gate FAILED, RC=1**.

   **Two things you must know or you will misread this.** The scoreboard measures **no runs
   stat** (`PITCHING_STATS` / `BATTING_STATS`, `recon_scoreboard.py:92-93`, carry no R), so
   **byte-identical numbers are the PASSING result** — they prove no other stat moved. And the
   gate fails against a stale Jul-21 baseline regardless of this change (DB growth, not
   regression). **Never `--update-baseline`** — that is the operator's review point.
6. **Perspective-scoped detection query before/after — expected to stay 91.** This chunk changes
   no stored data without a re-ingest; the columns are proven by test, not by the dev DB. Saying
   so up front stops "unchanged" being read as "didn't work."

   ```sql
   WITH last AS (
     SELECT p.game_id, p.perspective_team_id, p.home_score fhs, p.away_score fas
     FROM plays p
     WHERE p.play_order = (SELECT MAX(p2.play_order) FROM plays p2
        WHERE p2.game_id=p.game_id AND p2.perspective_team_id=p.perspective_team_id))
   SELECT COUNT(*) FROM games g JOIN last l ON l.game_id=g.game_id
   WHERE (g.home_score-l.fhs)+(g.away_score-l.fas) BETWEEN 1 AND 3;
   ```

   ⚠️ The seed's own version of this query is **perspective-blind** and wrong — many games carry
   two perspectives. Use the form above.
7. **Review**: `/code-review` is owed (operator-typed). **`/security-review` is NOT needed** —
   this chunk touches no auth, serving, PII, or deletion surface: a parser return type, a loader
   write, and an additive nullable-column migration. Stated explicitly rather than assumed.

## Progress log

- **2026-08-10** — Spec written. Seed audited: anchors held by symbol, but its measurement did
  not (6 → 91 units) and its "none by more" claim is REFUTED (9 at 2 runs, 1 at 3). Its
  detection query is perspective-blind and was corrected. Three of the spec author's own claims
  at n=37 were refuted at the full population (all-home-side, all-bottom-half, never-3-outs) —
  the tails are the run-rule cases that require generalizing across all three skip paths. Three
  seeding rules were tried and rejected on evidence before the survivor was accepted; the
  survivor was validated against **all 88 affected games** (87 recover, 1 unrecoverable, 0
  errors).
- **2026-08-10 (codex spec review)** — Three real defects found and fixed. (1) `44 runs` was an
  arithmetic carry-over from the n=37 population; the correct figure is **102** (81+18+3). (2)
  Population figures were stale: **91 units / 88 games**, not 92/90. (3) The scoreboard reference
  table was captured while the DB was still settling. **Root cause of (2) and (3): stability was
  checked by ROW COUNTS, which cannot see an UPDATE** — `games`/`plays` counts were identical
  across the whole window while `games.home_score` and the `player_game_*` tables were still
  changing. Verification 0 now exists so the next session does not repeat it. The rule
  re-validated cleanly on the settled population. Also fixed: the §4 grep selector returned
  `__pycache__` and was not runnable; expert consultation is now documented.
- **2026-08-10 (codex spec review, round 2)** — Two P2s, both fixed, no other findings. (1) The
  step-0 settle probe pinned `player_game_*` row counts, which drift on their own and are
  irrelevant to this chunk — rewritten to gate on the signals this work actually depends on
  (`games`/`plays` score sums and the step-6 count), with the drifting tables called out as
  explicitly NOT a stop condition. (2) The positive control named its tests by nickname;
  it now carries exact test names, a runnable `pytest -k` invocation, expected RC before and
  after, and the two mutations that re-demonstrate each guard. Pinned values re-verified after
  the edits: `28677 / 877775 / 2303`, step 6 = `91`.
