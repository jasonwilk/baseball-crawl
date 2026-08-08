# E-271-02: code-reviewer hardening — finding classification, annotation + fail-open mechanical checks, independent-review mode

## Epic
[E-271: Workflow / Process Redesign](../E-271-workflow-process-redesign/epic.md)

## Status
`TODO`

## Description
After this story is complete, `.claude/agents/code-reviewer.md` will classify each finding valid/invalid with a code-grounded reason, mechanically grep destructive-path diffs for annotation-as-coverage tokens and for default-valued safety signals, and carry an independent no-continuity destructive-path review mode plus an unmarked-destructive backstop. This is the code-reviewer-side half of items 3, 4, 7, and 8; the skill-side halves land in E-271-01.

## Context
This story owns the ONLY edits to `.claude/agents/code-reviewer.md` for this epic (file-ownership clustering, epic TN-1). It is blocked-by E-271-01 because its finding-classification format (item 3) and independent-review mode (item 7) must reconcile to the orchestration E-271-01 finalizes. See epic Technical Notes TN-4 (item 3 CR side), TN-5 (item 4), TN-8 (item 7 CR side + backstop), TN-9 (item 8 fold).

## Acceptance Criteria
- [ ] **AC-1** (item 3, TN-4): The code-reviewer adjudicates each EXTERNAL (Codex) finding as valid or invalid — with the one-line code-grounded reason — and emits it with an explicit inline `[valid]` / `[invalid]` tag in the existing Structured Findings Format (NOT a separate subsection), per the emitted-format pin in TN-4. The main session ROUTES exactly that token without adjudicating validity itself, so producer (CR) and consumer (the E-271-01 AC-2 router) cannot drift. Per TN-4(a), per-story CR findings are valid by construction (routed, not re-adjudicated); the adjudication tag is for external findings. Cites P-7.
- [ ] **AC-2** (item 4, TN-5): The existing judgment-based Priority-3 "Annotations are defect markers" item (~:149) is sharpened into a MECHANICAL step: grep the review diff for annotation tokens (`unreachable`, `cannot happen`/`can't happen`, `by construction`/`by-construction`, `impossible here`, `safe here`) on destructive-path lines (DELETE/retire/purge/drop context); each hit REQUIRES a discriminating test OR a PM-recorded exception (recorded in the distinct **Annotation Exceptions** History sub-block whose format the epic template defines — E-271-03 AC-3b — naming the annotation location + why a discriminating test is infeasible + PM sign-off, per TN-5; never a bare comment and never a buried scorecard row), else MUST FIX. Cites P-2.
- [ ] **AC-3** (item 7, TN-8): The code-reviewer's operating instructions carry an "independent no-continuity destructive-path review" mode (invoked as the fresh `code-reviewer-independent` instance per E-271-01 AC-4): it operates from the withheld-rationale payload (raw diff + Goals + Success Criteria + data-model/API facts, NOT the Technical-Notes safety prose / story why-correct manifest / accumulated finding lists) and executes the adversarial-falsification charge per TN-8(b). Per TN-8(c) it SUBSUMES both of Step 1c's conditional obligations BY NAME — the doc-sweep auto-load for context-layer epics and the surface-removal repo-wide grep for route/symbol deletions — plus the cross-story naming/import sweep; and this mode is the Step 1c judgment pass ONLY (Steps 1a/1b/1d remain the dispatch reviewer's). Cites P-1.
- [ ] **AC-4** (item 7 backstop, TN-8(a)): The code-reviewer runs a destructive-diff read during its closure review — grep the closure diff for `DELETE FROM`, `DROP TABLE`/`DROP COLUMN`, and the named destructive seams (`reconcile_at_load.py`, `purge_scouting.py`, `game_merge.py` delete-last, `lifecycle.py`/`generator.py` cascade helpers, `player_dedup.py`) — and if destructive statements are present but the epic's `Destructive-Path` field is `no`, that is flagged as a MUST-FIX planning gap. Cites P-1.
- [ ] **AC-5** (item 8, TN-9): ONE sentence is folded into the existing CR fail-open trigger (Priority-4, ~:158): when reviewing a destructive/safety-gated path, grep the changed module GRAPH for default-valued safety signals (default-True booleans, `getattr(..., True)`, `| None = None` evidence params) and verify each defaults to the REFUSING value, citing `.claude/rules/python-style.md`. No new standalone detector (excluded per TN-9). Cites P-3.
- [ ] **AC-6** (observable form, Codex P2-3): the code-reviewer's rubric structure, per-story review role, and Test Execution Constraint are UNCHANGED outside the items-3/4/7/8 edits — verify by diffing: only the intended items-3/4/7/8 changes appear, and the additions are rubric-line-scale (a handful of lines, per the net-deletion goal, epic TN-10), not new sections.

## Technical Approach
Edit `.claude/agents/code-reviewer.md` only, per epic Technical Notes TN-4 (CR side), TN-5, TN-8 (CR side + backstop), TN-9. AC-1 and AC-3 must reconcile to E-271-01's finalized routing contract and Step-1c independent-review orchestration (this story is blocked-by E-271-01 for exactly that reason) — the classification format the reviewer emits is the one the orchestrator routes, and the independent-review mode's assignment shape matches what the skill spawns. AC-2/AC-4/AC-5 are the mechanical grep steps (reviewer actions, permitted). Keep additions to rubric-line scale. This is a context-layer file → claude-architect per the Routing Precedence rule.

## Dependencies
- **Blocked by**: E-271-01 (finding-routing contract + Step-1c independent-review orchestration)
- **Blocks**: None

## Files to Create or Modify
- `.claude/agents/code-reviewer.md` (modify — items 3-CR, 4, 7-CR + backstop, 8-fold)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Context-layer story (claude-architect). Every AC cites its P-finding (meta-freeze). The 01↔02 coherence (items 3, 7) is carried by the blocked-by edge and verified at closure.
