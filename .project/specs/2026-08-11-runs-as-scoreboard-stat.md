<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# Runs as a reconciliation-scoreboard stat — the game-score section

**Date**: 2026-08-11 (rewritten 2026-08-17) · **Status**: `READY`
**Source**: `.project/specs/README.md` NOW — the ruled sequence's fourth item, so the full
regenerate is verifiable. Rewritten from its `STUB` state after the stub's premise was
refuted against the repo. Two neighbouring items fold in on operator rulings of 2026-08-17.

## Goal

After this chunk `bb report reconcile-scoreboard` measures **runs** — the plays-derived
final score against the `games` row, per game-perspective — as a new ungated section beside
the existing per-stat fidelity and axis counters. The instrument that was blind to the
102-run defect can see that class of defect. Two folded items ride along: the plays
loader's half-pair score write can no longer NULL a real score, and the admin generate
page's concurrency cap matches the operator's one-at-a-time ruling.

## What the STUB asked for, and why it is not what gets built

The stub asked for a runs stat beside the per-player stats in `PITCHING_STATS` /
`BATTING_STATS` (`src/reports/recon_scoreboard.py:92-93`). **Not buildable, and it would
not have caught the defect it was written for.**

- Those stats are compared per player-game unit. Plays carry no per-player run
  attribution: `plays` holds a running game score (`home_score`, `away_score`,
  `did_score_change` — `migrations/001_initial_schema.sql:484-486`) and `play_events`
  carries no player id at all (`:497-508`). Per-batter runs scored are not derivable.
- The recovery chunk established that the missing runs never touched a player stat —
  "No stat is lost, only the score", `done/2026-08-10-plays-final-score-recovery.md:32-35`.
  RBI and runs-allowed are boxscore-sourced and were already correct.

The defect lived at the **game score**, so the instrument goes there. Migration 013 added
`game_perspectives.plays_final_home_score` / `plays_final_away_score`; `PlaysLoader` writes
it and **no measurement consumes it**. One `src/` site does read it —
`merge_duplicate_game` carries both columns forward through its explicit column list
(`src/db/game_merge.py:358-366`, pinned by `tests/test_game_merge.py:541`, which is the
drift guard the recovery chunk's review added). That is a copy, not a reader; this chunk is
the first consumer.

## Measured before-state (live DB, read-only)

Every number below is from `sqlite3 -readonly "file:data/app.db?mode=ro"`, 2026-08-17,
before any change. The `game_perspectives` census was run in both the bare and the guarded
form and returned identical values, so nothing collected was silently empty (the bare form
returned empty results under concurrent WAL writers once, 2026-08-10).

| Measurement | Value |
|---|---|
| `game_perspectives` rows | 2,623 |
| both scores set / home-only / away-only / neither | 2,620 / **0** / **0** / 3 |
| units (both sides known) | 2,620 |
| exact | 2,609 |
| plays SHORT of the `games` row | 6 |
| plays EXCEED the `games` row | 5 |
| Σ abs delta | 26 |
| legacy last-play detection query | 101 |

Two readings carry meaning beyond their size:

- **The recovery fix is proven on live data.** The old last-play read still says 101; the
  column the recovery chunk added says 6. The board's backfill stub is discharged — the
  71-report restore run re-ingested plays and populated 2,620 rows.
- **The instrument earns its keep on the first run.** One completed game is stored `0-0`
  in `games` while its plays derive `10-5`; that single unit is 15 of the 26 abs delta.
  Only **2** completed games repo-wide sit at `0-0`. That is a `games`-row score defect,
  not a plays defect, and nothing else in the repo reports it.

## Files

- `src/reports/recon_scoreboard.py` — edited: `GameScoreFidelity` dataclass, a
  `game_score` field on `ScoreboardResult`, one SELECT, a `to_json_dict` top-level key.
- `src/cli/report.py` — edited: `_render_scoreboard_table` game-score block; one docstring
  line on `reconcile_scoreboard_cmd`.
- `src/gamechanger/loaders/plays_loader.py` — edited: `_persist_final_score` UPSERT guard
  (`:254-255`), `OR` → `AND`.
- `src/api/routes/reports_admin.py` — edited: `MAX_CONCURRENT_ADMIN_GENERATIONS` 2 → 1,
  its comment block, the refusal banner's plural.
- `docs/admin/operations.md` — edited: the banner text at `:573` and its surrounding prose.
- `tests/test_recon_scoreboard.py`, `tests/test_plays_loader.py`,
  `tests/test_admin_reports.py` — edited: new cases; `TestTheCapValue`'s literal pin.
- `.project/specs/2026-08-12-plays-final-score-half-pair-clobber.md` — moves to `done/`.
- `.project/specs/2026-08-11-plays-final-score-backfill.md` — Status flips (see Work 4).
- `.project/specs/README.md` — edited: NOW/NEXT entries for this chunk, the backfill, and
  the clobber; the new residuals this chunk exits (see Work 4).
- **Inbound pointers at the `done/` move** — the standing residual "a `git mv` into
  `specs/done/` strands pointers" binds here. Swept by file 2026-08-17; **four live files
  plus one research record** name the clobber stub:
  `.project/specs/2026-08-16-restore-run-observations.md`,
  `.project/specs/2026-08-16-plays-parser-unknown-templates.md`,
  `.project/specs/README.md`, `done/2026-08-10-opponent-roster-dedup-gap.md:347`, and
  `.project/research/2026-08-16-migration-audit-5.md`. Apply the criterion-vs-evidence
  rule at execution: repoint path-shaped/navigational references, leave provenance records
  as written. Read each — this list is a LOCATOR, not the ruling.

## The work

### 1. The game-score section — UNGATED

`GameScoreFidelity` (frozen dataclass, beside `StatFidelity`):

| Field | Meaning |
|---|---|
| `units` | game-perspective rows where BOTH the plays-derived pair and the `games` pair are non-NULL |
| `exact_units` | units where both scores match exactly |
| `plays_short_units` | plays total < `games` total — the class the 102-run defect lived in |
| `plays_exceed_units` | plays total > `games` total — the two-scorebook class |
| `abs_delta` | Σ `|plays_home − games_home| + |plays_away − games_away|` over `units` |
| `unmeasurable_units` | rows excluded because either side is NULL |

`compute_scoreboard` gains `game_score`, computed from ONE read-only SELECT joining
`game_perspectives` to `games`. Excluded-and-counted mirrors what `_score_side` already
does with no-plays units — an unmeasurable unit never inflates or deflates a rate.

**The stub's constraint 2 is honoured by reporting DIRECTION, never a blend.** A single
`|plays − boxscore|` sum would score two documented non-defects as error:

- **Two scorebooks kept separately** — plays legitimately exceed the `games` row
  (`.claude/rules/perspective-provenance.md` fn.1; E-261's 12-4 vs 12-5). These land in
  `plays_exceed_units` and the human table labels them as legitimate, never as error.
- **A scorekeeper who entered and then rescinded a run** — a non-monotone running score.
  It lands in whichever direction it falls; `abs_delta` is displayed as context, not as a
  verdict.

⚠ **Neither direction is a pure class, and the table must not claim otherwise.** SHORT is
where the 102-run defect lived, but the recovery chunk's own population also carried an
**abandoned-charting** unit that is legitimately short and is not this bug
(`done/2026-08-10-plays-final-score-recovery.md:24`) — the same residual its backfill
success criterion refused to drive to zero. So SHORT reads "worth investigating", never
"defects"; a trend in it is the signal, not its absolute value.

**`baseball-coach` was NOT consulted, deliberately** — the same call the recovery chunk
made and for the same reason (`done/2026-08-10-plays-final-score-recovery.md:44-47`). The
only domain claims here are the two legitimate-disagreement classes, and both are already
settled EMPIRICALLY in this repo — two scorebooks by E-261's measured 12-4 vs 12-5, and
abandoned charting by the recovery chunk's population — which is stronger evidence than
coaching judgment for this question. No new coaching semantics are introduced: the section
reports counts, and it recommends nothing.

**The stub's constraint 1 — ungated — is structural, not a promise.** `evaluate_gate`,
`_validate_baseline_shape`, `GATED_BATTING_STATS`, `GATED_PITCHING_STATS` and
`RATCHETED_AXIS_COUNTERS` are NOT touched, so the committed baseline — which has no
`game_score` key — still loads, and the gate's verdict is UNCHANGED by this chunk.

⚠ **"Unchanged" is not "passing", and an executing session must not expect green.** The
gate FAILS today, before any edit here. Measured 2026-08-17:

```
RC=1  Reconciliation gate FAILED — regressed:
  batting.AB 75 -> 133 · batting.H 20 -> 48 · batting.SO 14 -> 15
  pitching.H 40 -> 170 · pitching.SO 24 -> 71 · pitching.BB 42 -> 137
  axis.no_plays_units 484 -> 7358
```

That is the STANDING RESIDUAL firing exactly as recorded — `evaluate_gate` ratchets on
ABSOLUTE deltas, so corpus growth alone fails it, and `no_plays_units` 484 → 7,358 is the
growth. The design ruling (rate-based thresholds vs retiring the gate half) is still owed
and is NOT this chunk's to make. What this chunk owes is that the violation LIST does not
move — see Verification 7. Gating anything new on top of an unresolved gate design stays
out of scope.

⚠ **The new JSON key is TOP-LEVEL, not an axis counter.** `to_json_dict`'s `axis_counters`
object is pinned to exactly three keys by `tests/test_recon_scoreboard.py:360` and `:459`
(AC-4). That pin stays; `game_score` sits beside `pitching` / `batting` / `axis_counters`.

### 2. Half-pair clobber — `2026-08-12-plays-final-score-half-pair-clobber.md`

`_persist_final_score`'s UPSERT guard reads
`WHERE excluded.plays_final_home_score IS NOT NULL OR excluded.plays_final_away_score IS
NOT NULL` while BOTH columns are assigned from `excluded`
(`src/gamechanger/loaders/plays_loader.py:251-255`). A half-pair `(5, NULL)` landing on a
stored `(NULL, 7)` passes the guard and NULLs a real score — contradicting the docstring
eighteen lines above, which promises the pair "is written together" and that the write is
one-way (`:230-235`).

**Reachable through the real producer, not only by hand**: `_derive_final_score` returns
`play.get("home_score"), play.get("away_score")` and its docstring states "Either element
is None when that key is absent — deliberately NOT defaulted to 0"
(`src/gamechanger/parsers/plays_parser.py:482-495`). So the RED test drives
`loader.load_payload` with a payload missing ONE score key, mirroring the existing
`test_underivable_final_score_does_not_overwrite_a_stored_one` (`tests/test_plays_loader.py:1345`)
rather than writing the half-pair directly.

**The stub required measuring whether real payloads produce half-pairs before choosing
`OR` → `AND`, because `AND` also discards a half we legitimately derived.** Measured
above: **0 home-only and 0 away-only across all 2,623 rows** after a full re-ingest. `AND`
discards nothing observed, and it makes the code match its own docstring rather than the
reverse. Behaviour changes on the half-pair case ONLY: both-NULL is refused under either
operator, a full pair is admitted under either.

### 3. Admin generation cap 2 → 1 — operator ruling 2026-08-17

Board residual 2. `MAX_CONCURRENT_ADMIN_GENERATIONS = 2`
(`src/api/routes/reports_admin.py:97`) contradicts the 2026-08-16 one-at-a-time ruling:
two clicks can both pass the cross-path DB gate inside the window before either has
written its `generating` row — the shape of the 2026-08-16 incident. **Sweep by FILE, then
read** (line-level term-grep is a locator, not an enumerator); known sites:

- the constant and its comment block, `:90-101` — the comment's claim that the page is
  "effectively ONE-AT-A-TIME and this constant only binds inside the window" is what the
  ruling now makes literal, so re-read it for what goes stale at N=1.
- the refusal banner, `:899` — it interpolates the constant, so at N=1 it renders
  "1 report generations are already running". Needs a singular form.
- `TestTheCapValue::test_is_the_operator_ruled_two`, `tests/test_admin_reports.py:1812-1826`
  — the literal pin, the test name, and the docstring citing the 2026-08-16 ruling. The
  pin exists because every other cap test builds its OWN semaphore and is therefore
  tautological against a change to the constant (2→99 left the whole suite green).
- `docs/admin/operations.md:573`, which hardcodes the banner text, plus the prose around it.

**The semaphore STAYS.** It is what binds inside the click-to-`generating`-row window; it
is not vestigial at N=1.

### 4. Board bookkeeping this chunk owes

- `2026-08-11-plays-final-score-backfill.md` — its premise ("all 2,464 rows are NULL, the
  detection query reads 91") is refuted by the measurement above. Flip it to `COMPLETE` by
  discharge, recording the numbers and that the restore run, not a backfill session, did
  it — or `PARKED` if execution finds any part still owed. Do NOT re-run its plan.
- The board's NOW/NEXT entries for the backfill and the half-pair clobber both change.

## Out of scope

- **Per-pitcher runs-allowed derived from plays.** Derivable in principle from score
  changes during a pitcher's plate appearances, declined 2026-08-17: inherited-runner
  attribution is unverified, so disagreement would read as an ingestion defect when it may
  be a definition mismatch. Revisit only with a measured attribution rule.
- **Per-batter runs scored** — not derivable at all; see the refutation above.
- **Gating any of the new numbers**, now or later, until the absolute-vs-rate gate-design
  ruling is made (STANDING RESIDUALS).
- **Board residuals 1 and 3 on the admin generate path** (containment above Phase 1's
  first DELETE; the semaphore slot leaking when a response send fails). Both stay open.
- **The `games`-row `0-0` defect this instrument surfaces.** Measuring it is this chunk;
  fixing it is not. It exits as a stub or an `IDEAS.md` line at handoff.
- **`reconcile-scoreboard` opening the live DB with a bare `sqlite3.connect`** rather than
  the `mode=ro` URI `.claude/rules/canonical-seams.md` prescribes for a must-not-modify
  reader (`src/cli/report.py:297`). Pre-existing; recorded as a residual, not changed here.

## Verification

Run in order. Redirect pytest to a file and capture `$?` separately — never read a piped
exit code.

1. **Before-state, captured first.** `bb report reconcile-scoreboard --json > before.json
   2> before.err; echo "RC=$?"`. Expect **RC=1** and the seven violations quoted in §1 —
   that is today's state, not a failure of this chunk. No `game_score` key yet.
2. **Full suite, before.** `python -m pytest -q > /tmp/before.txt 2>&1; echo "RC=$?" >>
   /tmp/before.txt`. Expect `RC=0` and the count recorded in the progress log below.
3. **RED first on work item 2.** The half-pair test must FAIL before the `OR` → `AND` edit
   (a stored real score is NULLed) and pass after. Show the failure.
4. **Full suite, after.** `RC=0`, and the count must END ≥ where it started (suite only
   ratchets up).
5. **The new section reads the pinned numbers.** `bb report reconcile-scoreboard --json`:
   `game_score` = `units 2620 · exact 2609 · plays_short 6 · plays_exceed 5 ·
   abs_delta 26 · unmeasurable 3`. ⚠ These are pinned to a DB that must not move under the
   chunk — re-run step 1's census if any generation ran, and treat a changed number as a
   cross-check trigger, not a finding.
6. **The old numbers did not move.** Diff `before.json` against the fresh output: the three
   axis counters and every per-stat block must be byte-identical, and the ONLY structural
   difference is the added top-level `game_score` key. A new section that perturbs an
   existing one is a defect.
7. **The gate's verdict is unchanged by the new key.** Diff `before.err` against the fresh
   stderr: the same seven violations, same numbers, and **RC=1 both times**. Do NOT expect
   0 — see §1. This is what proves a baseline lacking `game_score` still loads and is still
   judged identically.

   **Positive control, and it cannot go through the CLI**: `reconcile_scoreboard_cmd`
   exposes only `--json` and `--update-baseline` (`src/cli/report.py:245-256`), so there is
   no flag to point it at a copied baseline. Run the control in-process instead — call
   `load_baseline()` on a `tmp_path` copy with a GATED key deleted (e.g.
   `batting.H.abs_delta`) and assert it raises `BaselineError`; the CLI's own mapping of
   that exception to exit 4 is already covered by `TestGateCli`. A clean result counts only
   with a control proving the instrument can fail.
8. **Work item 3.** The cap tests pass with the literal pin at 1, and the refusal banner's
   rendered text is re-read at N=1 for the singular form.

## Progress log

- **2026-08-11** — Stubbed at the recovery chunk's handoff. No code.
- **2026-08-17** — Rewritten from the stub after auditing it against the repo. The stub's
  per-player shape was REFUTED (plays carry no per-player run attribution; the 102-run
  defect never touched a player stat). Live before-state measured read-only. Two items
  folded in on operator rulings: the half-pair clobber (its open measurement question
  answered — zero half-pairs in 2,623 rows) and the admin cap 2 → 1. Full suite run at
  spec time: **4,564 passed, RC=0** (109s) — the floor Verification 4 ratchets from. No code.
- **2026-08-17, codex-spec-review** — five findings, all verified against the repo and all
  folded. Two P1s were one root: `bb report reconcile-scoreboard` already exits **RC=1**
  with seven gate violations, so the spec's "still passes" was false and its Verification 7
  was unsatisfiable; both now read "verdict UNCHANGED", and the positive control moved
  in-process because the CLI has no baseline-path flag. P2s: `merge_duplicate_game` DOES
  read the two columns (the "nothing reads it" claim was wrong — it is a copy, not a
  consumer); `README.md` and the stranded `done/`-move pointers were missing from Files (the
  re-run sweep found four live files, not the one cited); and the `baseball-coach`
  consultation decision is now recorded — declined, with its reason — which surfaced a real
  accuracy fix: SHORT is not a pure defect class, since abandoned charting is legitimately
  short. Disputed and moved on: none. The rubric's usual pre-commit `Status` complaint did
  not fire this round.
