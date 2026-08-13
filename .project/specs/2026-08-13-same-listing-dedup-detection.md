<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; for teams, orgs, ids and UUIDs use the PII-Safe Placeholder Taxonomy in `.claude/rules/api-docs.md`. -->

# Same-listing dedup: DETECTION at load time

**Date**: 2026-08-13 · **Status**: `READY` — written, codex-reviewed (7 rounds, clean), committed;
waiting only for a fresh execution session.
**Source**: `.project/specs/README.md` NOW — the ruled sequence after the dedup fix landed. Supersedes
the detection half of `2026-08-10-same-listing-dedup-window.md` (`STUB`); that stub's REPAIR half is
de-scoped by the Regeneration hazard ruling (2026-08-12) and dies with the full regenerate.

## Goal

After the full regenerate, GameChanger's double-listing of one real game does not produce two `games`
rows — in either of its two shapes — and all genuine doubleheaders remain separate rows. Today the
collapse rule requires the two listings' start instants to fall within **1.0 second**; real
double-listings arrive **minutes** apart, and a second shape evades the rule entirely because the two
rows name different opponent team rows for the same real opponent.

This chunk is DETECTION-FIRST, and that is not the same as non-destructive. ⚠ **Work item 3's
identity-bearing promotion routes through `merge_duplicate_game`, which re-points child rows and
DELETES the losing `games` row.** So a load that encounters an already-stored divergence twin will
opportunistically merge it — the chunk does not go looking for stored duplicates, but it does repair
the ones its own load path walks into. Name that seam alongside the two in `CLAUDE.md`: `bb report
generate` is already destructive on two axes, and this adds a third condition under which it deletes
a `games` row. What remains genuinely out of scope is the SWEEP — no pass hunts for stored twins, and
`bb data merge-duplicate-games` is untouched.

## Files

- `src/gamechanger/loaders/game_loader.py` — edit: widen `_SAME_LISTING_MAX_DELTA_SECONDS`; add the
  opponent-divergence second pass to `_find_duplicate_game`; add the identity-bearing promotion at
  the redirect site in `_load_boxscore_data`.
- `tests/test_loaders/test_game_dedup.py` — edit: RED-first tests per branch, plus the negative
  controls (genuine doubleheader, score disagreement, shared-perspective refusal).
- `.claude/rules/data-model.md` — edit: record the widened rule, its warrant, and the
  same-perspective merge refusal that makes an existing twin un-self-healable.
- **The three `redirect_map` definition sites, all of which say "cross-perspective" and become stale
  the moment work item 3 adds a promotion-merge mapping** — `src/gamechanger/loaders/__init__.py`
  (the `LoadResult.redirect_map` docstring), `.claude/rules/architecture-subsystems.md` (Reports
  Package, "Cross-perspective dedup redirect map"), `.claude/rules/perspective-provenance.md` (Plays
  Pipeline). Edit all three in the SAME commit, or narrow work item 3 so the semantics genuinely do
  not change and say so explicitly. This is the inbound-sweep obligation: what points AT a thing you
  redefine is invisible in your own diff.
- `.project/specs/README.md` — edit at step 9.
- `.project/specs/2026-08-10-same-listing-dedup-window.md` — edit: point its detection half here;
  it stays `STUB` for the residual observations it also carries.

## Established facts (measured 2026-08-13 — re-derive, do not inherit)

Measured against the live `data/app.db` (2,303 `games` rows) plus one live authenticated probe. Every
number below is reproducible from the Verification section's census SQL. Teams are referred to by
role, never by name or id; the census re-derives the rows.

**F1 — the 1.0s branch is REACHED; the stub's addendum ("the tolerance branch is not reached on at
least one path") is REFUTED.** `_is_same_listing_delta` returns `True` on the two real stored start
strings of the 0.96s pair. That twin survives because the step *behind* the redirect —
`_merge_twin_or_rollback` → `merge_duplicate_game` — **structurally refuses when the two rows share a
`perspective_team_id`** (the AC-2 disjointness pre-classification), and both rows carry the same
single perspective. The refusal returns "proceed to the upsert", so the row is never collapsed.
Corroborating: the rows were written two days BEFORE the rule landed (`b7552a4`, 2026-07-28), and the
team was re-loaded from its own perspective after that date without collapsing.
**Consequence: a same-perspective twin can never self-heal in place — only a fresh load avoids
creating it.** That is why the regenerate is the repair and this chunk is detection only.

**F2 — there is no deterministic identity key; the window question does not dissolve.**
⚠ **This is an EXTERNAL PREMISE from a live probe, not a repo-checkable fact, and it CONTRADICTS
current committed doctrine.** Three in-repo sites say the authenticated `game-summaries` `event_id`
is the stable cross-perspective key: `CLAUDE.md`, `.claude/rules/perspective-provenance.md` (the
Stable/Perspective-specific table), and `docs/api/endpoints/get-teams-team_id-game-summaries.md`. A
reviewer cannot replay the probe. **Re-run it before relying on F2** — the method is below; it is
read-only, and it is a PAGINATED fetch per team (`get_paginated` sends `x-pagination: true` and
follows `x-next-page` to exhaustion; the endpoint doc records 50 records per page), not a single
GET. If it comes back the other way, stop: the
divergence branch is the wrong instrument and the chunk needs re-planning, not re-tuning.

The stored-data form of this test is VACUOUS: `idx_games_stream_id_unique` makes a shared
`game_stream_id` impossible by construction, so any zero it returns proves nothing. The live form was
run against `GET /teams/{team_id}/game-summaries` (auth required, and NOT ownership-gated — the
endpoint doc records it working against an opponent's `progenitor_team_id`). **Reproduce it** by
picking any pair from census bucket (c) at delta 0s, resolving each row's perspective team to its
`gc_uuid`, calling `client.get_paginated(f"/teams/{gc_uuid}/game-summaries", accept=<the endpoint
doc's Accept header>)` for each, and comparing the two `event_id` sets. Results 2026-08-13:

- **Cross-perspective**: two teams that played each other carry **DISJOINT** `event_id` sets — 0
  shared across 26 and 54 records. *Positive control*: each team's own stored `game_id` IS found in
  its own set, so the matcher demonstrably fires; the zero is a finding, not an empty instrument.
- **Same-perspective**: one team's own summaries return **both** listings as distinct `event_id`s,
  with distinct `game_stream.id` and distinct `opponent_id`. GameChanger genuinely holds two events.

The alternative reading — that these are two genuinely different games — is ruled out by the rows
themselves: same date, same start instant, and mirrored per-team scores, with each team reporting the
other's total. So the three doctrine sites above are **wrong for unmanaged teams**, or at least
narrower than they read. Correcting them is explicitly out of scope and routed as a residual; that
correction is an API-doc change and therefore owes an `api-scout` pass, which this chunk does not
make on its behalf.

## Consultation

Neither `api-scout` nor `baseball-coach` was consulted, and the rubric expects a stated reason:

- **`baseball-coach`** — after two review rounds the coaching-domain claim carries no weight in this
  spec: the 1,800s bound is justified entirely from the census (work item 1), and the game-duration
  remark is labelled non-load-bearing corroboration that could be deleted without changing the bound.
  A consult is therefore not required to execute. **It IS the right request if the operator wants
  the bound defended by domain reasoning rather than by this corpus** — a `baseball-coach` pass on
  minimum real-game duration across youth / HS / Legion would change work item 1 only.
- **`api-scout`** — F2 is framed as an external premise with a reproducible method, and this chunk
  changes no API doc. Because the divergence branch is nonetheless CONDITIONED on that premise, the
  consult is replaced by a hard precondition: **Verification step 0 re-probes F2 and STOPS the chunk
  if it comes back the other way.** The doctrine reconciliation itself is out of scope and carries
  the `api-scout` obligation with it.
- Both agents were left unspawned deliberately: this session is configured not to delegate to
  subagents without an explicit operator request. Say the word and either consult can be run.

**F3 — two classes, one predicate.** Both reduce to *the shared team appears twice on one date, close
in time, with an agreeing scoreline*.

- **Class 1 — same-perspective double-listing** (same unordered team pair). Four same-pair candidate
  pairs sit under 1,800s. The window owns **two of them** (deltas 300s and 600s, both filed AFTER the
  fix landed, so both recur on the regenerate). One is the 0.96s pre-fix artifact of F1. One has
  delta 0 with two DIFFERENT single perspectives created in the same second — a concurrent-generation
  race, owned by `2026-08-10-admin-generate-concurrency.md`, **not** a window failure.
- **Class 2 — opponent-identity divergence**: same date, same start instant, agreeing scores, the
  shared team on the same side, but two different opponent team rows for one real opponent. The
  natural key `{home, away}` structurally cannot match them. **31** score-agreeing, shared-team,
  same-side pairs, pre-classified:

  ⚠ **These readings are JUDGEMENTS, not proofs, and the 0s row especially.** "One team cannot start
  two games at one instant" is a statement about play, and the rule reads a RECORDED `start_time` —
  the same counterexample that downgrades the 30-minute argument in work item 1 applies here with
  equal force, and it would be incoherent to accept it there and lean on it here. What actually
  justifies collapsing the 0s pairs is weaker and worth stating plainly: identical recorded instants
  PLUS pairwise score agreement PLUS same-side orientation PLUS mixed opponent identity (work item
  2), and the fact that the byte-equality tiebreaker already in `_find_duplicate_game` collapses
  identical-instant pairs **with no score check at all** — so this is narrower than behavior the
  repo already ships, not a new licence.

  | delta | n | reading | basis |
  |---|---|---|---|
  | 0s | 27 | twin | identical recorded instant + score + side + mixed identity (see above) |
  | 1,800s | 1 | probable twin | batting stat-tuple overlap 9 of 13 |
  | 3,600s | 1 | **UNKNOWN** | overlap 8 of 12 — twin band, but unadjudicated |
  | 9,000s | 1 | genuine doubleheader | overlap **0** of 24, two different opponents |
  | 62,400s | 1 | different games | 17.3 hours apart |

  A 32nd shared-team pair sits at delta 0 with DISAGREEING scores and is excluded by the score gate.

- **Genuine same-pair doubleheaders: 92 pairs, floor 5,400s.** Exactly one carries an identical
  scoreline, 7,200s apart. All 92 must remain separate rows.

**F4 — line-set equality is not a gate** (confirms the E-278-02 AC-8 rejection). The batting
stat-tuple overlap instrument scores 0 on both doubleheader controls and 2–11 on known twins, so a
HIGH overlap is informative and a LOW one is not: cross-perspective boxscores list different player
subsets. It is corroboration for adjudicating a pair by hand, never a runtime discriminator.

**F5 — the promotion can reuse the canonical merge seam.** `merge_duplicate_game` re-points
`game_id` only; it never rewrites `team_id`. Its disjoint-perspective pre-classification is what
makes every re-point collision-free — including `reconciliation_discrepancies`, whose UNIQUE is
`(run_id, game_id, perspective_team_id, team_id, player_id, signal_name)` and therefore DOES contain
`team_id`. A hand-written `team_id` re-point would have to defend that UNIQUE itself; routing through
the seam does not.

## The work

1. **Widen the same-listing window to 1,800 seconds** (`_SAME_LISTING_MAX_DELTA_SECONDS`). Rewrite
   the constant's comment. The current comment claims the bound is "physical, not fitted" and
   explicitly forbids putting the observed doubleheader floor into a criterion; the new bound must
   record BOTH halves of its warrant honestly:
   - **It is FITTED.** The corpus leaves the interval (600s, 5,400s) entirely empty and nothing
     physical selects a point inside it. Margins: 3× above the largest twin the window must catch,
     3× below the smallest observed doubleheader. A fitted bound inherits the risk the old comment
     names — the observed floor can shift.
   - **The minimum-game-duration argument is a CEILING, not a floor guarantee — its counterexample
     was constructed and it SURVIVES.** The argument is: two genuine games sharing a team cannot both
     START within 30 minutes, because the first must finish first. *Counterexample*: the rule keys on
     `start_time`, which is a RECORDED value, not an observed one — the loader's own comment already
     says so. A scorekeeper entering both halves of a doubleheader at nominal times, a suspended game
     resumed and re-stamped, or a forfeit, all produce two genuine games whose RECORDED starts sit
     inside any window. The corpus proves the rest of the shape is real: it already holds a genuine
     doubleheader with an IDENTICAL per-team scoreline, and that pair would be collapsed if its
     recorded gap were small. So the duration argument bounds real PLAY and the rule reads recorded
     TIMESTAMPS; it is **not** a safety guarantee and must not be written into the comment as one.
     What it does support is the CEILING — see the next bullet.
   - **Exposure, stated rather than argued away.** This widens an EXISTING exposure by a factor; it
     does not create a new class. The current 1.0s rule carries the identical residual risk in its
     own comment, and the byte-equality tiebreaker BELOW it collapses same-instant pairs with **no
     score check at all**. The new rule is still narrower than that tiebreaker: it requires pairwise
     score agreement, same-side orientation, and a bounded delta. Mitigation to implement, not just
     note: every collapse MUST log a WARNING naming both start instants and the delta, so a wrong
     merge is auditable after the fact rather than silent.
   - **Why 1,800s and not 3,600s — the LOAD-BEARING justification is the corpus, and it is entirely
     repo-checkable.** From census bucket (c), the score-agreeing shared-team deltas are
     `0, 1800, 3600, 9000, 62400`; from bucket (b), the same-pair doubleheader floor is `5400`.
     1,800s is therefore **the largest bound that admits every delta this corpus classifies as a twin
     while excluding every delta it classifies as not-a-twin or unknown.** 3,600s admits the
     UNADJUDICATED pair (F3) and halves the margin to the doubleheader floor. No domain judgment is
     needed to reach 1,800s; step 1's census re-derives all of it.
   - *Secondary and explicitly NOT load-bearing*: a run-ruled youth game can end inside an hour, and
     this product serves any team at any level, which independently argues against 60 minutes. This
     is coaching-domain judgment, **not measured here** — game duration is not derivable from our
     data (`end_ts` is not exposed and was already rejected as a discriminator by E-278-02). It is
     recorded as corroboration only; if it were deleted the bound would be unchanged. See
     Consultation below.
   - The TRIGGER is unchanged and must not be inverted: pairwise score agreement triggers, the window
     only narrows. A delta-only rule stays unsafe.

2. **Add the opponent-divergence second pass to `_find_duplicate_game`.** It runs ONLY when the
   existing team-pair pass returns no match.
   - **Do not touch the existing team-pair candidate query or the
     `incoming_schedule_count == 1 and len(rows) == 1` tolerant guard.** That guard's meaning depends
     on `len(rows)` counting team-pair candidates; widening the first query would silently change it.
     The second pass is a separate query.
   - Candidates: same `game_date`, `status = 'completed'`, different `game_id`, sharing the
     perspective team **on the same side** (home-with-home or away-with-away), different opponent.
   - Gate, all required: pairwise score agreement (mandatory — operator ruling) AND start delta
     ≤ 1,800s AND **MIXED opponent identity** (below). Absent or unparseable instants fail CLOSED, as
     `_is_same_listing_delta` already does.
   - ⚠ **MIXED IDENTITY IS A TRIGGER CONDITION, not just a tie-break for who survives.** The two
     rows' opponents must be exactly one identity-bearing team (non-NULL `gc_uuid` or `public_id`)
     and one bare-name stub. Both identity-bearing → REFUSE; both stubs → REFUSE. Measured over all
     31 score-agreeing shared-team pairs (query in Verification 1c):

     | delta | pairs | both identity-bearing | both stub | mixed |
     |---|---|---|---|---|
     | 0s | 27 | 0 | 1 | **26** |
     | 1,800s | 1 | 0 | 0 | **1** |
     | 3,600s | 1 | 0 | 0 | 1 |
     | 9,000s (genuine doubleheader) | 1 | **1** | 0 | 0 |
     | 62,400s (different games) | 1 | **1** | 0 | 0 |

     **Both known NON-twins are the only both-identity-bearing pairs**, and every in-window twin is
     mixed. The reasoning matches the measurement: this class exists because one side is a name-only
     stub standing in for a real opponent, so two rows that BOTH carry a GC identity are more likely
     two genuinely different opponents — which would mean two genuinely different games. Refusing
     there costs nothing measurable (0 in-window pairs) and removes a destructive branch the corpus
     cannot evidence. Refusing on both-stub costs exactly **1** delta-0 pair; take the loss.
     ⚠ Honest bound: `n=2` on the both-identity side. This is a fail-closed narrowing justified by a
     mechanism, not a validated discriminator — do not later re-read it as "both-identity proves a
     doubleheader."
   - Orientation-flipped pairs are NOT candidates. All 27 corpus twins keep the shared team on the
     same side. **State the flipped-pair claim at its true width** — an earlier draft said "every
     flipped pair in the corpus disagrees on score" and that is FALSE. Measured 2026-08-13: within
     the window there are **6** flipped shared-team pairs and **0** agree on score under either
     comparison (mirrored — the shared team's own score against its own — or raw home-to-home).
     Corpus-wide across ANY delta there is exactly **1** flipped pair whose MIRRORED scores agree,
     at 14,400s — four hours out, so it is nowhere near the window. Note the comparison choice is
     itself a trap: on a flipped pair, raw home-to-home compares the shared team's score against its
     opponent's, so a "match" there can be an artifact. Fail-closed; recorded as a residual rather
     than handled.

3. **Identity-bearing promotion at the redirect site.** Operator ruling: on a divergence collapse the
   surviving row must name the opponent that carries a `public_id` or `gc_uuid`, never a bare-name
   stub. Which row is canonical is otherwise decided by load order, which the regenerate does not
   control, so this must be order-independent.
   Work item 2's mixed-identity trigger means this step only ever sees one shape: exactly one side
   identity-bearing. There is no both-identity or both-stub case to handle here — those never reach
   the redirect, because they never collapse.
   - Canonical's opponent is already the identity-bearing one → plain redirect, unchanged behavior.
   - Canonical's opponent is the stub AND the incoming's is identity-bearing → do NOT redirect into
     the stub row. Upsert under the incoming event id, then call
     `merge_duplicate_game(source=<stub-headed row>, canonical=<new row>)` per F5.
   - **Fail-closed fallback**: if that merge REFUSES (the two rows share a perspective), leave both
     rows and log — the same posture as today's `_merge_twin_or_rollback`. A refusal costs a
     duplicate row; a wrong merge destroys a game.
   - ⚠ **ORDERING MAKES THAT FALLBACK REAL OR VACUOUS, and this is the sharpest hazard in the chunk.**
     `merge_duplicate_game` refuses only when the two perspective sets INTERSECT; an EMPTY set on
     either side yields no intersection and the merge PROCEEDS. So if the promotion merge runs before
     the incoming upsert has written the new row's `game_perspectives` row, the new row's set is
     empty, a same-perspective pair does NOT refuse, and the guard is vacuous — the
     "absence of refusal is not safety" shape this repo has already been bitten by. **The merge MUST
     run after the incoming perspective row is recorded.** Pin it with a test that asserts a
     same-perspective divergence pair leaves BOTH rows (the corpus contains one such pair, so the
     shape is real, not hypothetical).
   - ⚠ **`redirect_map` MUST gain an entry for the DELETED row's event id** →
     the surviving id. The generator's plays and spray stages remap every source event id through it
     before filing, so an unmapped deleted id strands those stages on a `games` row that no longer
     exists. Analysis at spec time: the deleted row usually belongs to a DIFFERENT perspective's
     earlier run, so its id is normally absent from this run's crawl set and the entry is harmless
     insurance — but "usually" is not a guarantee worth relying on at a seam whose failure mode is a
     silent skip, and the entry costs one line. Add it unconditionally; do not reason about whether
     this run could have produced it. Verify at execution that adding it cannot collide with an
     existing key.
   - `preserve_scores` must be reasoned about explicitly rather than inherited — the gate already
     forces the scores to agree, but the ORIENTATION tuple E-268 protects is exactly what this step
     changes.

4. **Tests, RED first, in `tests/test_loaders/test_game_dedup.py`.** Each new branch needs a test that
   FAILS before the change. Minimum set: Class 1 at a minutes-apart delta collapses; Class 1 beyond
   the window does not; Class 2 same-side score-agreeing collapses; Class 2 with disagreeing scores
   does not; Class 2 orientation-flipped does not; a genuine doubleheader at the corpus floor stays
   split; an identical-scoreline doubleheader 7,200s apart stays split; the promotion keeps the
   identity-bearing opponent regardless of which row loaded first (BOTH orders); both-identity and
   both-stub pairs are REFUSED and leave two rows; a same-perspective divergence pair leaves two rows
   (the ordering pin from item 3); the promotion's
   merge refusal leaves both rows. Note the standing hazard recorded in
   `.project/specs/README.md`: **several test files hand-build a partial schema rather than routing
   through `conftest.load_real_schema`**, so a test-scope grep names none of them. Do not pin a count
   here — the residual says four and a review sweep found at least five, and reconciling that is not
   this chunk's job. The operative instruction is unchanged and does not depend on the number: run
   the FULL suite, not a targeted selection, and run it once per round.

5. **Document** in `.claude/rules/data-model.md`: the widened rule with both halves of its warrant,
   the divergence branch and its same-side/score-agreement gate, and F1 (a same-perspective twin
   cannot self-heal because the merge refuses) — that last one is why an operator seeing a stale twin
   should not read it as this rule failing.

## Out of scope

- **Repair of the twin groups already stored.** De-scoped by the Regeneration hazard ruling
  (2026-08-12); the full regenerate replaces it. `bb data merge-duplicate-games` is not touched.
- **The concurrent-generation race** (the delta-0 same-second pair in F3) — owned by
  `2026-08-10-admin-generate-concurrency.md`.
- **Team-grain dedup of duplicate `teams` rows.** The divergence class exists because one real
  opponent has two team rows, but some of those rows are legitimately distinct GC entities (a
  tournament-event name, a `TBD-<date>` placeholder), so merging teams is not the instrument. See
  residuals.
- **Changing `merge_duplicate_game`'s same-perspective refusal.** F1 explains why an existing
  same-perspective twin is stuck; unsticking it is a separate decision on a destructive seam.
- **Reconciling the three `event_id`-stability doctrine sites** (F2): `CLAUDE.md`,
  `.claude/rules/perspective-provenance.md`, `docs/api/endpoints/get-teams-team_id-game-summaries.md`.
  Its own chunk, and it owes an `api-scout` pass because it edits an API doc.

## Verification

Run in order. Redirect pytest to a file and capture `$?` separately — a piped pytest exit code
reports the PIPE.

0. **PRECONDITION GATE — re-probe F2 before writing any code.** The divergence branch exists only
   because no deterministic key does, and that premise is external to the repo and contradicts three
   committed doctrine sites (F2).

   **The probe pair must be CROSS-perspective.** Not every bucket-(c) delta-0 pair qualifies:
   measured 2026-08-13, of the **27** such pairs, **26** are cross-perspective (and all 26 have a
   `gc_uuid` on both perspectives, so all 26 are probe-eligible) and **1** carries the SAME single
   perspective on both rows. On that one, "compare the two teams' `event_id` sets" degenerates to
   comparing one team's set with itself and the expected result is false — it is not a
   counterexample to F2, it is an ineligible input. Select with:

   ```sql
   -- eligible probe pairs: bucket (c), delta 0, two DIFFERENT perspectives, both with a gc_uuid
   WITH g AS (SELECT * FROM games WHERE start_time IS NOT NULL),
   p AS (SELECT a.game_id ga, b.game_id gb,
           (SELECT GROUP_CONCAT(perspective_team_id) FROM game_perspectives x WHERE x.game_id=a.game_id) pa,
           (SELECT GROUP_CONCAT(perspective_team_id) FROM game_perspectives x WHERE x.game_id=b.game_id) pb
         FROM g a JOIN g b ON a.game_date=b.game_date AND a.game_id<b.game_id
         WHERE ((a.home_team_id=b.home_team_id AND a.away_team_id<>b.away_team_id)
             OR (a.away_team_id=b.away_team_id AND a.home_team_id<>b.home_team_id))
           AND a.home_score IS b.home_score AND a.away_score IS b.away_score
           AND a.start_time = b.start_time)
   SELECT ga, gb, pa, pb FROM p
   WHERE pa <> pb
     AND (SELECT gc_uuid FROM teams WHERE id=CAST(pa AS INT)) IS NOT NULL
     AND (SELECT gc_uuid FROM teams WHERE id=CAST(pb AS INT)) IS NOT NULL;
   ```

   Expected: **26 rows**. Probe any one of them with the script below.

   ⚠ **Credential precondition — check it FIRST, or a broken instrument reads as a refuted premise.**
   `GameChangerClient()` resolves auth from local config/env and can fail before any comparison runs.
   Run `bb creds check` and confirm the **web** profile reports `[OK] 200 OK` on `GET /me/user`
   before probing. An auth failure, an expired token, or a `CredentialExpiredError` is **NOT**
   evidence against F2 — it is no evidence at all. Only a successful paginated fetch for BOTH teams,
   with both positive-control lines printing `True`, produces a readable result.

   Runnable as written from the repo root (note the `src.`-prefixed import: `src/http/` shadows the
   stdlib `http` package if `src` is put on `sys.path` directly, which breaks `httpx`):

   ```python
   # /tmp/probe_f2.py -- read-only; two authenticated GETs. Fill in the two ids from the SQL above.
   import sqlite3
   from src.gamechanger.client import GameChangerClient
   ACCEPT = "application/vnd.gc.com.game_summary:list+json; version=0.1.0"
   GA, GB = "<ga>", "<gb>"                       # the two game_id values
   conn = sqlite3.connect("file:data/app.db?mode=ro", uri=True)
   client = GameChangerClient()
   sets = {}
   for gid in (GA, GB):
       (persp,) = conn.execute(
           "SELECT perspective_team_id FROM game_perspectives WHERE game_id=?", (gid,)).fetchone()
       (uuid,) = conn.execute("SELECT gc_uuid FROM teams WHERE id=?", (persp,)).fetchone()
       recs = client.get_paginated(f"/teams/{uuid}/game-summaries", accept=ACCEPT)
       sets[gid] = {r.get("event_id") for r in recs}
       print(f"{gid}: perspective {persp}, {len(recs)} summaries, "
             f"own id present = {gid in sets[gid]}")   # <- POSITIVE CONTROL, must be True
   print("shared event_ids =", len(sets[GA] & sets[GB]))
   ```

   ```sh
   python3 /tmp/probe_f2.py
   ```

   Expected: both "own id present" lines print `True` (the positive control — without it a zero is a
   broken matcher, not a finding), and `shared event_ids = 0`.
   **If the sets INTERSECT, STOP** — do not implement. The divergence branch is then the wrong
   instrument, and the chunk returns to spec with `api-scout` consulted on what the stable key is.
   Record the observed set sizes and the shared count in the progress log either way.
   *(This gate is the reviewer-offered substitute for an `api-scout` consultation; see Consultation.)*

1. **Baseline census, BEFORE any change.** Run the SQL below against `data/app.db` opened read-only.
   It was executed 2026-08-13 and every expected value here is its actual output.

   Save the block below verbatim to `/tmp/census.sql` (it is not a repo file — it exists only here,
   so that step 6 re-runs byte-identical SQL), then:

   ```sh
   sqlite3 "file:data/app.db?mode=ro" -readonly < /tmp/census.sql
   ```

   ```sql
   -- (a)+(b) same-pair; (c)+(d) shared-team same-side.
   .mode list
   WITH k AS (SELECT *, MIN(home_team_id,away_team_id) t1, MAX(home_team_id,away_team_id) t2
              FROM games WHERE start_time IS NOT NULL),
   d AS (SELECT (julianday(replace(replace(b.start_time,'T',' '),'Z',''))
                -julianday(replace(replace(a.start_time,'T',' '),'Z','')))*86400 AS s,
                (a.home_team_id=b.home_team_id AND a.away_team_id=b.away_team_id
                 AND a.home_score IS b.home_score AND a.away_score IS b.away_score) sos
         FROM k a JOIN k b ON a.game_date=b.game_date AND a.t1=b.t1 AND a.t2=b.t2
                          AND a.game_id<b.game_id)
   SELECT '(a) same-pair pairs delta < 1800s', COUNT(*) FROM d WHERE abs(s) < 1800
   UNION ALL SELECT '(b) same-pair pairs delta >= 1800s', COUNT(*) FROM d WHERE abs(s) >= 1800
   UNION ALL SELECT '(b) min delta among those (s)', CAST(MIN(abs(s))+0.5 AS INT)
                    FROM d WHERE abs(s) >= 1800
   UNION ALL SELECT '(b) of those, identical orientation+scoreline', COUNT(*)
                    FROM d WHERE abs(s) >= 1800 AND sos;

   WITH g AS (SELECT * FROM games WHERE start_time IS NOT NULL),
   p AS (SELECT (julianday(replace(replace(b.start_time,'T',' '),'Z',''))
                -julianday(replace(replace(a.start_time,'T',' '),'Z','')))*86400 AS s,
                (a.home_score IS b.home_score AND a.away_score IS b.away_score) sos
         FROM g a JOIN g b ON a.game_date=b.game_date AND a.game_id<b.game_id
         WHERE (a.home_team_id=b.home_team_id AND a.away_team_id<>b.away_team_id)
            OR (a.away_team_id=b.away_team_id AND a.home_team_id<>b.home_team_id))
   SELECT '(c) shared-team same-side, scores agree', COUNT(*) FROM p WHERE sos
   UNION ALL SELECT '(c) ... at delta 0s', COUNT(*) FROM p WHERE sos AND abs(s) < 1
   UNION ALL SELECT '(c) ... 0 < delta <= 1800s', COUNT(*)
                    FROM p WHERE sos AND abs(s) >= 1 AND abs(s) <= 1800
   UNION ALL SELECT '(c) ... delta > 1800s', COUNT(*) FROM p WHERE sos AND abs(s) > 1800
   UNION ALL SELECT '(c) distinct deltas above 0 (s)', GROUP_CONCAT(CAST(x+0.5 AS INT))
                    FROM (SELECT DISTINCT abs(s) x FROM p WHERE sos AND abs(s) >= 1 ORDER BY 1)
   UNION ALL SELECT '(d) shared-team same-side delta 0, scores DISAGREE', COUNT(*)
                    FROM p WHERE NOT sos AND abs(s) < 1;
   ```

   Expected, and pinned as the before-baseline:
   (a) same-pair pairs with start delta < 1,800s = **4**;
   (b) same-pair pairs with delta ≥ 1,800s = **92**, minimum delta **5,400s**, of which exactly
   **1** carries an identical orientation-and-scoreline (at 7,200s);
   (c) shared-team same-side score-agreeing pairs = **31**, distributed 27/1/1/1/1 across deltas
   0 / 1,800 / 3,600 / 9,000 / 62,400s;
   (d) shared-team same-side pairs at delta 0 with DISAGREEING scores = **1**.
   **Positive control**: the non-zero counts in (a) and (c) ARE the demonstration that the census can
   find twins; a census that returned 0 everywhere would be indistinguishable from a broken query.
   The SQL is pinned above verbatim so step 6's post-regenerate run is byte-identical to this one.

1b. **Re-derive the CLASSIFICATION, not just the buckets.** Step 1 reproduces raw deltas; it does not
   reproduce the twin / unknown / doubleheader labels in F3 that make 3,600s the thing to exclude.
   This query does (F4's instrument):

   ```sql
   -- Batting stat-tuple overlap for the SHARED team, per score-agreeing pair with delta > 0.
   WITH g AS (SELECT * FROM games WHERE start_time IS NOT NULL),
   p AS (SELECT a.game_id ga, b.game_id gb,
           CAST(abs((julianday(replace(replace(b.start_time,'T',' '),'Z',''))
                    -julianday(replace(replace(a.start_time,'T',' '),'Z','')))*86400)+0.5 AS INT) delta_s,
           CASE WHEN a.home_team_id=b.home_team_id THEN a.home_team_id ELSE a.away_team_id END shared
         FROM g a JOIN g b ON a.game_date=b.game_date AND a.game_id<b.game_id
         WHERE ((a.home_team_id=b.home_team_id AND a.away_team_id<>b.away_team_id)
             OR (a.away_team_id=b.away_team_id AND a.home_team_id<>b.home_team_id))
           AND a.home_score IS b.home_score AND a.away_score IS b.away_score
           AND a.start_time <> b.start_time),
   v AS (SELECT game_id, team_id, ab||','||r||','||h||','||rbi||','||bb||','||so t
         FROM player_game_batting)
   SELECT p.delta_s,
     (SELECT COUNT(*) FROM (SELECT t FROM v WHERE game_id=p.ga AND team_id=p.shared
                            INTERSECT SELECT t FROM v WHERE game_id=p.gb AND team_id=p.shared)) shared_t,
     (SELECT COUNT(*) FROM (SELECT DISTINCT t FROM v WHERE game_id=p.ga AND team_id=p.shared
                            UNION SELECT DISTINCT t FROM v WHERE game_id=p.gb AND team_id=p.shared)) union_t
   FROM p ORDER BY p.delta_s;
   ```

   Expected (actual output, 2026-08-13): `1800 → 9/13`, `3600 → 8/12`, `9000 → 0/24`,
   `62400 → 2/23`. **Read it in one direction only** (F4): a HIGH overlap corroborates a twin; a LOW
   one is uninformative, because cross-perspective boxscores list different player subsets. The
   1,800s and 3,600s pairs sit in the same band, which is exactly why 3,600s is UNKNOWN rather than
   ruled a non-twin — and why excluding it is the fail-closed choice, not a confident one.
   *This query classifies; it does not decide. It never runs at load time.*

1c. **Re-derive the identity split** that work item 2 turns into a trigger condition:

   ```sql
   WITH g AS (SELECT * FROM games WHERE start_time IS NOT NULL),
   p AS (SELECT
           CAST(abs((julianday(replace(replace(b.start_time,'T',' '),'Z',''))
                    -julianday(replace(replace(a.start_time,'T',' '),'Z','')))*86400)+0.5 AS INT) delta_s,
           CASE WHEN a.home_team_id=b.home_team_id THEN a.away_team_id ELSE a.home_team_id END opp_a,
           CASE WHEN a.home_team_id=b.home_team_id THEN b.away_team_id ELSE b.home_team_id END opp_b
         FROM g a JOIN g b ON a.game_date=b.game_date AND a.game_id<b.game_id
         WHERE ((a.home_team_id=b.home_team_id AND a.away_team_id<>b.away_team_id)
             OR (a.away_team_id=b.away_team_id AND a.home_team_id<>b.home_team_id))
           AND a.home_score IS b.home_score AND a.away_score IS b.away_score),
   q AS (SELECT delta_s,
           (SELECT (gc_uuid IS NOT NULL OR public_id IS NOT NULL) FROM teams WHERE id=opp_a) ia,
           (SELECT (gc_uuid IS NOT NULL OR public_id IS NOT NULL) FROM teams WHERE id=opp_b) ib
         FROM p)
   SELECT delta_s, COUNT(*) n, SUM(ia AND ib) both_identity,
          SUM(NOT ia AND NOT ib) both_stub,
          SUM((ia AND NOT ib) OR (ib AND NOT ia)) mixed
   FROM q GROUP BY delta_s ORDER BY delta_s;
   ```

   Expected (actual output, 2026-08-13): `0 → 27, 0, 1, 26`; `1800 → 1, 0, 0, 1`;
   `3600 → 1, 0, 0, 1`; `9000 → 1, 1, 0, 0`; `62400 → 1, 1, 0, 0`. The gate rests on this split, so
   a change here changes the rule's reach — re-measure, do not inherit.

2. **RED proof.** Every new test in step 4 of The work MUST be named with one of three prefixes —
   `test_same_listing_`, `test_divergence_`, `test_promotion_` — so this selector is exact and every
   executor runs the same set:

   ```sh
   python3 -m pytest tests/test_loaders/test_game_dedup.py \
     -k "same_listing or divergence or promotion" > /tmp/red.txt 2>&1; echo "RC=$?" >> /tmp/red.txt
   ```

   Run it against UNCHANGED source. Expected: `RC=1`, and the failure count equals the number of new
   tests written (state that number in the progress log when you write them). A new test that PASSES
   pre-change is not testing the change and must be rewritten, not kept.
   Measured 2026-08-13 by running that exact command: **`RC=5`**, with the summary line
   `collected 37 items / 37 deselected / 0 selected`. Pin BOTH — the RC alone is ambiguous, and the
   `37 deselected` half is what proves the file is populated and the selector discriminates, so the
   zero is not an empty-file artifact. (`RC=5` is pytest's "no tests ran"; a reviewer reported `RC=0`
   here and a re-run did not reproduce it, so trust the deselected line over the code if they ever
   disagree.) The baseline is therefore 0 and the RED count is the total, not a delta. Re-confirm
   before writing tests; if it has moved, the prefixes collided with other work and must be renamed.

3. **Full suite green.** `python3 -m pytest > /tmp/suite.txt 2>&1; echo "RC=$?" >> /tmp/suite.txt`
   Expected: `RC=0`, and the passed count ≥ the pre-change count (4,513 at `9f1f930`; re-measure, do
   not inherit). Read the file for the RC and the pass/fail line.

4. **Mutation check — pin the BOUNDARY, not just the direction.** Two of the tests in step 4 of The
   work must sit exactly on the edge: one pair at a delta of **exactly 1,800s** that MUST collapse
   (the comparison is `<=`, and the corpus's probable twin sits precisely there), and one at
   **1,801s** that MUST NOT. Then run two mutations, clearing `__pycache__` before each mutation AND
   each restore, and asserting the mutation actually applied:

   ```sh
   # after each edit to _SAME_LISTING_MAX_DELTA_SECONDS:
   find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
   python3 -m pytest tests/test_loaders/test_game_dedup.py \
     -k "same_listing or divergence or promotion" > /tmp/mut.txt 2>&1; echo "RC=$?" >> /tmp/mut.txt
   ```

   - Mutate to `1799.0` — the **1,800s boundary test must FAIL**. This is the mutant that matters: it
     is the plausible future edit, and it proves the bound is `<= 1800` rather than merely "bigger
     than a few minutes". A `< 1800` implementation is caught here and nowhere else.
   - Mutate to `1.0` (the pre-change value) — the minutes-apart tests must FAIL.

   Restore and re-run after each. **Report per-test outcomes, never an aggregate count** — an
   aggregate hides which test was load-bearing.

5. **North-star diagnostic.** `bb report reconcile-scoreboard` before and after. It is a DIAGNOSTIC,
   not a gate here — the CLI still calls `evaluate_gate` and exits non-zero on a growing corpus (a
   standing residual). Record the numbers; do not treat a red FAILED as blocking.

6. **AFTER the full regenerate (not in this chunk's commit).** Re-run step 1's census verbatim.
   Acceptance, stated to match the rule this spec actually specifies rather than an ideal:
   - **(a) → 0.** All four same-pair sub-window pairs collapse.
   - **(c) 0s → 1, NOT 0.** Exactly one delta-0 pair MUST survive: the both-stub pair, which work
     item 2's mixed-identity trigger refuses on purpose. Measured 2026-08-13, that pair is also the
     single SAME-perspective pair in the bucket, so it is refused twice over — once by the trigger and
     again by `merge_duplicate_game`'s disjointness pre-classification. A `0` here would mean
     something collapsed that the spec says must not; treat it as a FAILURE, not a bonus.
   - **(c) 1,800s → 0.** The mixed-identity probable twin collapses.
   - **(c) 3,600s → 1, unchanged.** Expected to persist — unadjudicated and out of window.
   - **(b) unchanged at 92, floor still 5,400s.** The doubleheaders must not have moved at all.

## Reviews owed at EXECUTION (step 5) — both operator-typed

The spec commit itself is docs-only and takes the PII gates alone. The execution chunk does not:

- **`/code-review` — REQUIRED.** The chunk edits `src/gamechanger/loaders/game_loader.py` and
  `tests/`.
- **`/security-review` — REQUIRED, and do not skip it as "just a dedup rule".** Step 5's trigger
  list names DELETES, and work item 3 routes through `merge_duplicate_game`, which re-points five
  child tables and hard-deletes a `games` row. The specific things to put in front of it: the
  ordering hazard that decides whether the disjointness refusal is real or vacuous (item 3), the
  mixed-identity trigger as the sole guard against collapsing two real games, and the widened
  `redirect_map` contract.
- **`/simplify` — optional, and if run it goes BEFORE `/code-review`** so its own edits get reviewed.
- **A second-opinion codex review is available on request** and is worth offering here: on a recent
  diff the two reviewers overlapped on 1 of 4 findings, each catching what the other missed.

Neither review can be launched from inside a session — the execution session must STOP and ask.

## Residuals this chunk creates or names

- **The 3,600s divergence pair stays uncollapsed and the regenerate will recreate it.** Accepted,
  fail-closed by design: it is unadjudicated (F3), and reaching it needs a 60-minute window that F3's
  duration argument rules unsafe.
- **Orientation-flipped divergence pairs are not candidates** — a deliberate fail-closed narrowing on
  the branch with the weakest identity anchor.
- **A same-perspective twin already in the DB is un-self-healable in place** (F1).
- **Three doctrine sites claim a cross-perspective-stable `event_id`; the probe contradicts them for
  unmanaged teams** (F2). Unreconciled, and left that way deliberately — this chunk records the
  premise and its method, it does not rewrite API doctrine on one probe.
- **After a promotion merge, child stat rows keep the stub team's `team_id`** — the seam re-points
  `game_id` only (F5). Consequence to state, not to fix here: a stub team referenced by a surviving
  game's child row is NOT an orphan, so `reclaim_orphan_reference_data` will keep it alive.
- **Duplicate `teams` rows with identical names exist** (one confirmed pair, one row carrying
  `public_id` + `gc_uuid` and the other carrying neither) — an `ensure_team_row` cascade question,
  not this chunk.

## Progress log

- **2026-08-13** — Spec written from a live-data and live-API investigation. F1 refutes the source
  stub's addendum; F2 refutes the deterministic-key hypothesis by probe with a positive control; F3
  re-attributes the four same-pair twins (the window owns two, the concurrency race one, F1 one).
  Operator rulings folded in: 1,800s both branches, mandatory scoreline agreement plus
  identity-bearing survivor on the divergence branch, census SQL pinned in the spec rather than a new
  CLI surface. No code written; no merges run.
- **2026-08-13** — `codex-spec-review` round 1: 2 P1, 3 P2, all accepted and folded in.
  The census step now names `/tmp/census.sql` instead of an unnamed file; the RED selector is a
  concrete `-k` expression with a measured baseline of 0 collected tests; the minimum-game-duration
  warrant had its counterexample CONSTRUCTED and it survived, so that argument is downgraded to a
  ceiling-only claim and a WARNING-logging mitigation is now required work; F2 is reframed as an
  external premise with a reproducible method and its three contradicting doctrine sites named; a
  Consultation section states why `api-scout` and `baseball-coach` were not consulted.
- **2026-08-13** — round 2: 1 P1, 2 P2, all accepted. The promotion now REQUIRES a `redirect_map`
  entry for the deleted row's event id (the generator remaps every source id through it, so an
  unmapped id silently strands the plays/spray stages). Round 2's P1 also exposed a hazard neither
  round found directly: `merge_duplicate_game` refuses only on a NON-EMPTY intersection, so running
  the promotion merge before the new row's `game_perspectives` row exists makes the fail-closed
  fallback VACUOUS — ordering is now pinned and owed a test. The 1,800s bound was re-justified from
  the census alone, demoting the coaching rationale to non-load-bearing; and F2's `api-scout`
  obligation became Verification step 0, a hard stop-the-chunk precondition.
- **2026-08-13** — round 3: 1 P1, 2 P2, all accepted. Step 0 was UNSATISFIABLE for one allowed input
  — 1 of the 27 bucket-(c) delta-0 pairs is same-perspective, where the probe degenerates to
  comparing a team's `event_id` set with itself; the gate now carries a selector SQL and an expected
  **26** eligible rows. Step 1b was added so the twin / unknown / doubleheader CLASSIFICATION is
  re-derivable (overlap `1800 → 9/13`, `3600 → 8/12`, `9000 → 0/24`, `62400 → 2/23`) rather than
  asserted. And the three sites that define `redirect_map` as cross-perspective-only joined the Files
  list, since work item 3 widens that contract.
- **2026-08-13** — round 4: 2 P1, 1 P2, all accepted, and the sharpest one changed the RULE. Codex
  measured that the "both opponents identity-bearing" case was unevidenced; re-measuring confirmed it
  and showed more: both known NON-twins are the ONLY both-identity-bearing pairs, and every in-window
  twin is mixed. **Mixed identity is now a TRIGGER CONDITION of the divergence branch**, not just a
  survivor tie-break — both-identity and both-stub now REFUSE, which deletes an unevidenced
  destructive branch at a cost of 1 delta-0 pair. Also: F3's 0s row no longer leans on the
  physical-impossibility claim the spec itself falsifies elsewhere; step 0 carries a runnable probe
  script; step 4 pins the inclusive 1,800/1,801 boundary with a `1799.0` mutant; step 1c re-derives
  the identity split.
- **2026-08-13** — round 5: 1 P1, 1 P2, both accepted. Step 1c cited a query that existed nowhere;
  it is now inlined. And a claim of mine was FALSE as written — "every flipped pair in the corpus
  disagrees on score" — corrected to its true width (0 of 6 within the window; exactly 1 corpus-wide
  at 14,400s), with a note that raw home-to-home comparison on a flipped pair is itself misleading.
- **2026-08-13** — round 6: 1 P1, 2 P2. The P1 was a self-contradiction I introduced in round 4:
  step 6 demanded `(c) 0s → 0` while work item 2's new both-stub refusal GUARANTEES one survivor, so
  the acceptance criterion was unsatisfiable by the spec's own rule. Acceptance is now stated
  per-bucket, and a `0` there is a FAILURE. Also confirmed: the both-stub pair and the lone
  same-perspective pair are the SAME pair, refused twice over. The Goal's "repairs nothing already
  stored" was FALSE — the promotion routes through `merge_duplicate_game`, which deletes a `games`
  row — so the Goal now names that destructive seam and scopes the exclusion to the SWEEP.
  The `RC=5` baseline was re-measured against the exact command and HELD (the review's `RC=0` did not
  reproduce); the expectation now pins the `37 deselected` line as the load-bearing half.
- **2026-08-13** — round 7: **no P1/P2 blockers.** Three P3s folded in rather than carried: the F2
  probe is a PAGINATED fetch per team, not "two GETs"; step 0 now names the credential precondition
  explicitly, so an auth failure cannot be misread as refuting F2; and the hand-built-schema hazard
  no longer pins a count (the residual says four, a review sweep found five, and the instruction —
  run the full suite — does not depend on which). Review rounds: 7.
- **2026-08-13** — operator asked which reviews had run. Answer for the SPEC commit: none owed beyond
  the PII gates (docs-only, step 5). But the spec had NOT recorded the step-5 gates the EXECUTION
  chunk owes, so a fresh session could have missed that `/security-review` is required — the
  promotion path hard-deletes a `games` row. Added the "Reviews owed at EXECUTION" section.
