# E-276-02: Game Grain

## Epic
[E-276: Reconcile-at-Load Health Gate — Capture the Prior Set Before the Run's Own Writes](epic.md)

## Status
`TODO`

## Description

After this story is complete, the game-grain reconcile computes its health gate against the games loaded as of the start of the run, so newly-completed games loaded in the same run can no longer relax the floor and authorize retiring stale ones. The prior set is captured above the boxscore load while the reconcile call stays below it, and a game deleted mid-run by the in-pipeline twin merge can no longer be logged as a phantom retire.

## Context

The game grain's pollution is the sharpest illustration of the general mechanism: newly-completed games appear in normal operation — that is what re-scouting is for — and each one relaxes the floor by half a game. Stale absences that correctly refuse on their own start retiring once enough new games load alongside them, bounded only by `MAX_GAME_RETIREMENTS`.

This grain is also the one where the pollution is **not** an artifact of reading inside an open transaction. The payload loader commits per game, so by the time the reconcile runs, this run's new rows are committed. No isolation-level change could fix it — the capture has to move.

The reconcile call itself must stay below the boxscore load: the redirect map is empty until that load runs, and a reconcile hoisted above it would find every redirected game's canonical id missing from the fresh set. Only the *capture* moves up. That creates a second long-span ordering coupling in the same function as the existing roster one.

## Acceptance Criteria

- [ ] **AC-1**: Given prior-loaded games with stale absences that refuse on their own, when a re-scout loads newly-completed games in the same run, then those absences **still refuse** — the newly-completed games inflate neither side of the ratio. Pre-fix the same input retires; this is the story's discriminating case.

- [ ] **AC-2 (wrong-reason trap — binding, per Technical Notes TN-11)**: Every refusal assertion MUST identify **which** mechanism refused. Several produce "0 retired" here — the health gate, the boxscore-completeness signal, and `MAX_GAME_RETIREMENTS` — so a test that does not discriminate passes pre-fix via the completeness signal and proves nothing. Assert on a **structural record carried by the result dataclass, not on refusal-reason prose** (TN-11): a test that greps log text passes when someone rewords the message. **That record is not reachable by default AND does not yet exist — read epic TN-17 first.** `_reconcile_absent_games` logs a summary and discards `GameRetireResult`, and that dataclass carries its refusals as **prose strings** with no gate-outcome field. **Adding the fields is a production change required under either sanctioned means.** Patch target for this grain is `reconcile_at_load` (function-local import) — the player-line grain differs; see TN-17's table. Assert positively that the spy captured a result: it is what detects a wrong patch site.

      Fixture sizing, verified: **2 prior loaded against a fresh schedule of 2 brand-new completed games**, which retires both today while **today's gate and the cap both permit** [EXECUTED, SE]. The run-2 fixture MUST also supply boxscores for every completed game in the fresh array, or the completeness signal refuses first and the health gate is never exercised at all.

      **Assert `refused_by == "gate"`, not merely that something refused.** The enum on this grain is `gate` / `cap` / **`boxscores_incomplete`** / `empty_payload` / `fetch_not_ok`, and `boxscores_incomplete` is a distinct member rather than a flavour of the cap — the existing WARN already separates them *because the remedies differ*. **`refused_by` is UNIT-level; per-id protections (cross-perspective, `not_final`) live in `.refusals[game_id]`. A test asserting "0 retired" must check BOTH** — that is the wrong-reason trap's real closure on this grain, and neither field alone gives it.

- [ ] **AC-3**: The prior-game capture is taken at the anchor specified in TN-2 — inside `_load_team_core`, after the season-id derivation it depends on and above the boxscore load — while the reconcile call remains below the boxscore load. Both positions are load-bearing and neither may move.

- [ ] **AC-4**: The candidate population is the **live prior read, unchanged from today**, with **no intersection against the captured snapshot** — per epic Technical Notes TN-1(b). The snapshot feeds the gate only.

      An earlier draft required such an intersection, motivated by a phantom retire when the in-pipeline twin merge deletes a `games` row mid-run. **That motivation was refuted by DE itself** — the merge is keyed on the source event id captured *before* the canonical-id rebind, so the merged-away id is always in `fresh`, classifies PRESENT, and is never a retire candidate. If a reviewer proposes reinstating an intersection, its comment must never cite the twin merge: shipping a refuted causal claim inside a safety comment is the exact defect class this epic exists to close.

- [ ] **AC-5**: A comment at the capture site names **both** drift directions of the new long-span ordering coupling — a write moved above the capture, and the reconcile hoisted above the boxscore load — in the manner of the existing roster-snapshot comment. Nothing in the signature enforces either position; per TN-4 and the epic's Background both failure directions are silent.

- [ ] **AC-6**: **Both** prose sites assigned to this story in TN-9 are corrected in this same change.

      **(a)** The comment block at the `comparable` assignment in `retire_absent_games`, whose "Two population mismatches were tried and rejected here" paragraph claims newly-completed games "are not in prior either". That claim is false today and is exactly what AC-1 disproves.

      **(b)** The **"WHICH gate refused"** comment above the three-branch `transient_reason`, which enumerates **three** causes named apart *"because the remedies differ"*. **This comment is not wrong today — the change makes it wrong**, which is why it is easy to read past: nothing about it looks stale. The enumeration stops being exhaustive once `refused_by` names the mechanisms explicitly and `boxscores_incomplete` is separated from the cap. It pairs with AC-10, which fixes the message the comment describes.

- [ ] **AC-7 (deletion-neutrality — game grain, STRUCTURAL given a named premise)**: **The fix never permits a DELETION that today's code refuses, on this grain.** This holds **by construction from the premise `W ⊆ fresh`** (epic TN-5), **not** from a conjunction and **not** from a sweep. It is scale-free — it holds at 2 games and at 200.

      **⚠️ Scope the assertion to DELETIONS, never to permits.** The two gates genuinely disagree at `P_pre = ∅` **and** `W = ∅` (32 executed cases), where all have an empty candidate set and nothing is deleted either way. A test phrased as "permits whenever today permits" would fail against a correct design.

      **Port the sweep, with its range attached — its STATUS has changed but the port has not.** The 0-of-2197 result (three parameters over `0..12`) exists only in a session scratchpad. It is now **corroboration rather than sole support**, so it is no longer load-bearing for the claim — but it must still land as a parametrized property test per epic TN-16, and **it must carry its range wherever cited: `0..12` does not reach a 20–30 game season.** Zero failures over a space that stops short of production reads as strong evidence *because* the count is zero, which is exactly why the range is a stated limitation rather than a citation detail.

      `MAX_GAME_RETIREMENTS` and every other cap are unchanged — see the epic's Non-Goals for why touching them would destroy this epic's own before/after evidence.

- [ ] **AC-8 (guard the `W ⊆ fresh` coupling — 4 lines, and it is the check SE already ran)**: `W ⊆ fresh` on this grain — everything the run writes into the delete scope comes from the fresh payload — is what makes the uniform shape degenerate here (epic TN-3). **SE hunted a falsifier and found none**: exactly ONE `INSERT INTO games` exists in `src/`, reached only via `_upsert_game_and_stats` with the id set from `summary.event_id`, so stub-creation and error-recovery paths are covered by construction; a runtime assertion across the full suite gave **179 reconcile invocations, 0 violations, 4207 tests passed** — the space here being "every reconcile the suite exercises", which is why it is weaker evidence than the static enumeration beside it.

      **But the property rests on a single-field coupling that nothing guards.** `_build_games_index_from_data` sets `event_id` from `game["id"]`, and `_reconcile_absent_games` reads that same field to build `fresh_ids` — two modules, no assertion tying them. The same function also sets `game_stream_id` from that field, so a future edit sourcing `event_id` from `game_stream_id`, or reading a different key, **breaks the property silently**: candidates would then include a row the run itself created and absent from fresh, presenting as a mysterious retire rather than a type error.

      Land **both**: a comment at the coupling naming what depends on it, and the runtime assertion as a test. An unguarded cross-module coupling underwriting a load-bearing property is exactly what this epic exists to stop shipping.

      **Evidence tier, recorded honestly**: the static enumeration is what makes the property general; the 179 invocations confirm no suite-exercised path falsifies it but are **not** a proof over production inputs.

- [ ] **AC-9**: `python -m pytest tests/` reports 0 failed, with no existing assertion changed. The pre-implementation baseline is **4207 passed**.

- [ ] **AC-10 (PRESERVE the operator-facing which-refuser discrimination)**: When this grain refuses, the WARN it emits MUST name the refusing mechanism and carry **that mechanism's own counts**, rendered from `refused_by` and the gate-outcome record.

      **This is a preservation requirement, not a new capability, and that is verified rather than assumed** [PM-VERIFIED, clean read of `retire_absent_games`]. The three-branch `transient_reason` in this function already discriminates today, and its own comment says so: *"WHICH gate refused... the three causes are named apart: an operator seeing '8 games vanished' needs to know whether that was a suspected partial crawl (the floor), an incomplete boxscore load..., or a legitimate-looking mass removal above the cap -- the remedies differ."* The property exists and is deliberate.

      **What must not be lost is that discrimination becoming implicit.** The message must distinguish the gate from the cap from `boxscores_incomplete` — the last being a genuinely separate mechanism rather than a flavour of the cap — and **must not fold per-id protections into the unit-level reason**, since those live in `.refusals[game_id]` and folding them loses which ids were held back.

      **This is not a duplicate of AC-2, and the two do not conflict.** AC-2 governs what a *test* asserts on and forbids the WARN as an assertion target. This governs the *message itself*. The gate-outcome record (epic TN-11) is the source and the WARN renders from it, never the reverse — so a test for this AC may assert on the message text, because here the message **is** the deliverable rather than a proxy for behaviour.

      **The generalizable point, worth more than the string**: adding a mechanism to a guarded path silently degrades every message that enumerated the old mechanisms. The comment above will still read as though it holds — an accurate comment made false by a change elsewhere, which is this epic's own subject arriving in its own remediation.

## Technical Approach

The capture anchor, the **no-intersection** rule and its reason, the transaction verdict, and the test design constraints are specified in the epic's Technical Notes — TN-1 (fix shape), TN-2 (anchors), TN-4 (staleness, both directions), TN-5 (deletion-neutrality), TN-6 (transaction verdict, including why this grain's pollution survives a commit), TN-9 (prose sites), TN-11 (the wrong-reason trap), TN-12 (test design), TN-14 (guardrails).

One judgment call belongs to the implementer and is deliberately not specified here: the game-grain retire helper needs both the captured set and a live read — **the captured set for the gate, the live read for the candidate population** — so the required-parameter change **adds** an input rather than removing the helper's own query. How to expose that without spreading schema knowledge into the loader is yours; the constraint from TN-1(a) is that the caller owns *when* the capture is taken and the seam continues to own the SQL.

**⚠️ Two superseded shapes, recorded rather than silently fixed, because a prohibited shape surviving in a story's *implementation guidance* is worse than one surviving in its prose — it is the sentence an implementer reads while deciding what to build.**

- An earlier version said the helper needs both sets *"to compute the intersection"*. **There is no intersection.** `prior_at_start ∩ prior_now` is removed entirely and must not appear in any form; AC-4 states the rule correctly two sections above.
- An earlier version said the live read feeds *"the legacy gate"*. **There is no legacy gate.** Under TN-1(b) this grain runs **one gate** — the corrected gate over the pre-upsert snapshot — and the live read serves the candidate population only.

Reference material, read-only and in an ephemeral session scratchpad — reproduce what it demonstrates rather than depending on the path:
- `/tmp/claude-1000/-workspaces-baseball-crawl/4aca143d-2d11-40ae-ae02-d8924803b063/scratchpad/recon_audit/t_game_prior.py` — spies the game-grain prior read during a real two-run load and shows brand-new ids present in "prior".
- `/tmp/claude-1000/-workspaces-baseball-crawl/2728098f-4677-4ff3-a474-cda6aed92b4c/scratchpad/divergence_game.py` — the read-only probe that recomputes the game gate both ways at every reconcile call.

## Dependencies
- **Blocked by**: E-276-01 (the shared prior-set parameter shape and the amended authority check)
- **Blocks**: E-276-03, E-276-05

**Why this story blocks 03 rather than running beside it**: both modify `src/db/reconcile_at_load.py`, so an ordering is required. The direction is deliberate — this grain is the plain application of the settled shape, and landing it first means the roster story edits a file where the uniform shape is already visible in two grains, so its candidate-population divergence reads as a divergence rather than as the only pattern present. See the epic's Stories section.

## Files to Create or Modify
- `src/db/reconcile_at_load.py`
- `src/gamechanger/loaders/scouting_loader.py`
- `tests/test_game_grain_reconcile.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-276-05**: the corrected game-grain population claim, which the CLAUDE.md replacement paragraph must not contradict.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing. **The DISCRIMINATING tests — AC-1's stale-absences-plus-newly-completed case and AC-2's fixture — demonstrably FAIL against pre-fix code and PASS after.** Scoped deliberately: AC-5 is a comment, AC-6 is prose, and AC-7's ported sweep asserts a property that holds under BOTH regimes (it is a no-op guard on this grain, which is the whole point of porting it). A blanket fail-before/pass-after line would make this story's own Definition of Done unsatisfiable.
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] `data/app.db` untouched; no network; synthetic DBs from `migrations/` only

## Notes

`tests/test_game_grain_reconcile.py` already contains `test_truncated_array_padded_with_upcoming_games_retires_nothing`, which pads with **upcoming** games. Those genuinely never enter the prior set, which is why that test passes today and why it does not cover this defect. The reachable padding shape — newly-completed games — is what AC-1 adds. Worth reading that test first: it is the near-miss, and the new test is its sibling.
