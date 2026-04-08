# E-219-04: Cross-Perspective Safety Context Layer

## Epic
[E-219: Own-Side-Only Boxscore Loading](epic.md)

## Status
`TODO`

## Description
After this story is complete, the own-side-only principle will be codified in the project's context layer, ensuring all future loader development and code reviews enforce the cross-perspective safety invariant.

## Context
The cross-perspective UUID behavior is a permanent GameChanger API property. Without a context-layer rule, future loaders or loader modifications could re-introduce the same bug. The `data-model.md` rule already documents the UUID behavior (under "Cross-perspective player UUIDs"), but it describes the API behavior without prescribing the loader-side invariant. A dedicated rule or expansion codifies the mandatory guard. See TN-2 and TN-4 in the epic for the risk assessment per endpoint.

## Acceptance Criteria
- [ ] **AC-1**: A context-layer artifact (new rule file or expansion of existing rule) codifies the own-side-only principle: loaders inserting `player_id` data MUST only insert for the team whose perspective the data was fetched from.
- [ ] **AC-2**: The rule identifies the three HIGH-risk endpoint categories (boxscore, plays, spray charts) and documents the risk level and mitigation status for each, per TN-2 in the epic.
- [ ] **AC-3**: The rule includes a mandatory guard: any new loader that inserts `player_id`-keyed data must filter to own-side only. The guard is phrased as an invariant (MUST constraint), not a suggestion.
- [ ] **AC-4**: The rule includes a code review checklist item: reviewers must verify no cross-perspective player insertion in loader code touching files matched by the rule's `paths:` scope.
- [ ] **AC-5**: The plays loader's whole-game idempotency exemption is documented (no code change needed because whole-game idempotency prevents double-loading; see TN-4).
- [ ] **AC-6**: CLAUDE.md is updated if needed to reference the new rule. The update should be minimal (one-liner or addition to existing Architecture bullet) since `data-model.md` already documents the UUID behavior.
- [ ] **AC-7**: The "Player dedup merge-every-run cycle" note in `.claude/rules/data-model.md` is updated to reflect that cross-perspective re-introduction no longer occurs after E-219-01's root cause fix. Name-variant dedup may still trigger occasional merges.

## Technical Approach
CA should determine the best delivery mechanism: new rule file (`.claude/rules/cross-perspective-safety.md`) vs. expanding the existing `data-model.md` rule. The `paths:` frontmatter should scope to loader files. CLAUDE.md update should be minimal. See the CA consultation in the epic for recommended scope.

## Dependencies
- **Blocked by**: E-219-01
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/cross-perspective-safety.md` (new) OR `.claude/rules/data-model.md` (expand with new section)
- `.claude/rules/data-model.md` (update "Player dedup merge-every-run cycle" note per AC-7)
- `CLAUDE.md` (minimal update if needed)

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-219-05**: The "Player dedup merge-every-run cycle" note in `data-model.md` is updated by this story (AC-7). E-219-05 does not need to modify `data-model.md`.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- CA has final authority on delivery mechanism (new file vs. expand existing) and `paths:` scoping.
- The rule should be prescriptive (MUST constraints) not descriptive (how the API works) -- the descriptive part already exists in `data-model.md`.
