# E-249-01: Connected-Components Dedup with Fork Refusal (core fix + fixture suite)

## Epic
[E-249: Player-Dedup Stale-Worklist Fix](epic.md)

## Status
`DONE`

## Description
After this story is complete, same-team player deduplication will group detected prefix pairs into per-roster connected components, collapse every unambiguous component (a single terminal NAME — including equal-named same-human duplicates) to one canonical player, and refuse every fork (≥2 terminals with distinct names) — leaving it unmerged with a WARN log. The stale-worklist `PlayerMergeError` cascade is gone, and the fix introduces no new cross-merge mode — fork-shaped ambiguity is refused rather than guessed (the pre-existing strict-prefix linear-chain limitation, e.g. "Alex"⊂"Alexa", is unchanged and deferred to Tier 2 / IDEA-089). This is the core fix in `src/db/player_dedup.py`, consumed by the load path (`dedup_team_players`); the CLI delegation is E-249-02.

## Context
The current code computes the merge worklist up front and iterates it serially while each merge DELETEs a player, so redundant intra-component edges hit the existence guards in `merge_player_pair` and raise caught `PlayerMergeError`s; branching/fork components leave residual duplicates. Critically, the current code's *failing* redundant edge is the only thing preventing a cross-merge of two distinct humans (see epic Background, "load-bearing-edge reframe"). A naive worklist fix would REMOVE that protection and introduce a silent cross-merge (Mode B), which baseball-coach identified as the must-not-defer trust-killer. This story replaces the accidental protection with the deliberate fork-refusal rule. All existing merge invariants (E-237 provenance handling, per-merge mechanics, perspective scoping, `recompute_aggregates` ownership) must be preserved — see epic Technical Notes TN-5.

## Acceptance Criteria
- [ ] **AC-1**: Given a roster whose detected prefix pairs form a single-terminal component (a total chain such as O⊂Oli⊂Oliver, OR a single-stub pair such as Jo→John), when dedup runs over that `(team_id, season_id)`, then the component fully collapses to one canonical player selected per Technical Notes TN-2, all other members are removed from `players`, and their stats are combined under the canonical id.
- [ ] **AC-2**: Given a roster whose detected pairs form a fork (≥2 terminals with mutually-DISTINCT names — e.g. Jo→John + Jo→Jon, or O→Oliver + O→Owen), when dedup runs, then the entire component is left unmerged (every member survives as a distinct `players` row) per Technical Notes TN-1, and the two distinct terminals (e.g. Oliver and Owen) remain separate rows (no-cross-merge).
- [ ] **AC-3**: Given a component whose maximal members share the SAME first+last name under different UUIDs (an identical-name cross-perspective duplicate, e.g. `{Jon, Jon}` or `{Jon, Jon, Jonathan}`), when dedup runs, then the component COLLAPSES to one canonical (NOT refused as a fork), per the distinct-name test in Technical Notes TN-1. This is the regression guard for Finding 1 — equal-named maximal members must not be misclassified as a fork.
- [ ] **AC-4**: Given any multi-edge component, when dedup runs, then zero `PlayerMergeError`s are raised or caught from redundant edges (the stale-worklist cascade is eliminated).
- [ ] **AC-5**: Given a refused fork, when dedup runs on the load path, then exactly one WARN-level log line is emitted per refused component identifying the team and the conflicting terminal names, per Technical Notes TN-3.
- [ ] **AC-6**: Given a component whose members carry mixed-provenance season rows (a member `full`/`supplemented` row plus `boxscore_only` rows), when the component collapses, then member rows are preserved/re-pointed via the existing `_delete_or_repoint_season_rows` path and never deleted or downgraded, per Technical Notes TN-5.1.
- [ ] **AC-7**: Given a collapsed component over a POPULATED fixture whose stored `player_season_*` deliberately disagrees with the per-game sum, when dedup runs with `recompute_aggregates=True`, then the resulting season aggregate is the correct combined line for the canonical player (the aggregate test has teeth per Technical Notes TN-6 / the E-247 corollary).
- [ ] **AC-8**: The load path (`dedup_team_players`) consumes the new shared component-planning unit (per Technical Notes TN-4), and the `recompute_aggregates` ownership contract is unchanged (load path behavior with `recompute_aggregates=False` still defers to the end-of-load recompute), per Technical Notes TN-5.4.

## Technical Approach
Introduce a shared component-planning unit in `src/db/player_dedup.py` (per Technical Notes TN-4) that takes the detected pairs for a scope, groups their endpoints into connected components, classifies each component as single-terminal (collapse) or fork (refuse) per TN-1, selects the per-component canonical per TN-2, and returns a plan of `(canonical, [duplicates])` collapses plus the list of refused forks. `dedup_team_players` consumes that plan, executing each component's merges through the existing `merge_player_pair` under one transaction/savepoint per component (TN-5.3), and emits the WARN logs for refused forks (TN-3). Reuse all existing per-merge helpers unchanged (TN-5.2). The exact function/dataclass shape is the implementer's decision; the binding constraints are in Technical Notes TN-1 through TN-6. Do not change the detection signal or the existing canonical tiebreak logic beyond making it operate per component.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-249-02

## Files to Create or Modify
- `src/db/player_dedup.py` (the shared planner + `dedup_team_players` orchestration; detection and per-merge helpers reused)
- `tests/test_player_dedup.py` (add the component-shape fixtures per TN-6: chain-collapse, single-stub-collapse, fork-refuse, identical-name-collapse `{Jon, Jon}` and `{Jon, Jon, Jonathan}` regression guards, no-cascade assertion, no-cross-merge assertion, populated stale-disagreeing aggregate fixture)
- Any other `tests/` file that imports `db.player_dedup` (run per the Test Scope Discovery rule in Technical Notes TN-6)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-249-02**: the shared component-planning unit (function + return shape) that the CLI will consume in place of its inline `find_duplicate_players` + merge loop. E-249-02 needs the planner to expose both the collapse plan and the refused-fork list so the CLI can render them in dry-run and execute.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (the TN-6 component shapes incl. identical-name collapse regression guards + no-cascade + no-cross-merge + populated stale-disagreeing aggregate fixture)
- [ ] All `tests/` files importing `db.player_dedup` discovered and run (Test Scope Discovery)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The fork-refusal rule (TN-1) is the central correctness invariant — it is what guarantees no Mode-B cross-merge. Tier 2 (IDEA-089) will later use same-game co-occurrence between terminals to safely auto-collapse genuine same-human forks; this story deliberately refuses all forks. Bake `game_id` co-occurrence into the fork fixtures (per TN-6) so the same-human-vs-two-human distinction is explicit in the test data even though Tier 1 does not act on it.
