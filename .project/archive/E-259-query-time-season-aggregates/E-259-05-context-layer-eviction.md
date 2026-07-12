# E-259-05: Evict context-layer references (context-layer files + owning-agent memory)

## Epic
[E-259: Query-Time Season Aggregates](epic.md)

## Status
`DONE`

## Description
After this story is complete, the context layer no longer references the retired stored tables, `canonical_recompute`, `_compute_season_aggregates`, the parity apparatus, or the `bb report verify-aggregates` command. The Step 1d `verify-aggregates` HARD sub-check E-256 added is **struck** (a plain deletion, not a substitution), and the epic's net context-layer shrinkage is recorded as the trigger-7 counterweight.

## Context
This is the deletion-side eviction pass for the cutover. Technical Notes §5 enumerates the files and §6 states the shrinkage-not-substitution principle. Two care points: (1) `code-reviewer.md`'s Bug Pattern Checklist uses `player_season_batting` as its worked example — **edit inside the `BUG-PATTERN-CHECKLIST` delimiters, never touch the markers**, which the Codex prompt extracts verbatim; (2) the Step 1d sub-check strike is a plain deletion — `reconcile-scoreboard` does not move into the slot (it is already a separate unconditional check), and there is no left-hand side to check post-cutover. Doc-runbook references route to story 06, not here.

## Acceptance Criteria
- [ ] **AC-1**: Given story 05's portion of the Technical Notes §5 eviction set (the context-layer files + CA's own memory — §5 items 1–7 and 11; the OTHER agents' memory, §5 items 8–10, is the closure obligation established by AC-6, not this AC), when this story is complete, then each reference to a retired surface (`player_season_*` as a stored table, `canonical_recompute`, `_compute_season_aggregates`, `aggregate_parity`, `bb report verify-aggregates`) in those files is struck or annotated as history, verified per the doc-sweep discipline (token grep + synonym expansion + semantic read, `.claude/rules/doc-sweep.md`).
- [ ] **AC-2**: Given `.claude/agents/code-reviewer.md`, when this story is complete, then its Bug Pattern Checklist worked example no longer uses the retired stored table, the edit is made **inside** the `BUG-PATTERN-CHECKLIST` delimiters, and the delimiter markers themselves are unchanged.
- [ ] **AC-3**: Given `.claude/skills/implement/SKILL.md` and `.claude/agents/code-reviewer.md` Step 1d, when this story is complete, then the `bb report verify-aggregates` HARD sub-check is **removed** (not replaced) from the Step 1d skill text AND `verify-aggregates` is struck from `code-reviewer.md`'s **Test-Execution-Constraint enumerated command list** (the E-256-11 carve-out authorizes it there; leaving it would keep CR authorized to run a deleted command), and a short note records that no aggregate-integrity gate remains because the aggregate is now the query (`reconcile-scoreboard` remains the surviving live fidelity gate, unchanged).
- [ ] **AC-4**: Given CLAUDE.md, when this story is complete, then all four sites in Technical Notes §5 item 1 are updated: the `verify-aggregates` Commands entry, the `canonical_recompute` Architecture bullet, the `bb data dedup-players` recompute mention, and any `backfill-appearance-order`→`verify-aggregates` footgun (if E-256 has not already removed it).
- [ ] **AC-5**: Given claude-architect's OWN memory dir (`.claude/agent-memory/claude-architect/`, notably `epic-codifications.md`), when this story is complete, then it is grepped for the retiring surfaces (`verify-aggregates`, `canonical_recompute`, `_compute_season_aggregates`, `aggregate_parity`, stored `player_season_*`) and each hit reconciled — strike a stale reference, PRESERVE a still-valid one — per the doc-sweep discipline. The OTHER agents' memory dirs (data-engineer, software-engineer, code-reviewer) are **NOT this story's ACs**: a single-CA-assigned story cannot have other agents editing their own dirs within it (CA's AC-5 ruling), so their reconciliation is a closure Deletion-Side-Eviction obligation the Context-Layer Assessment Gate discharges before archival (see AC-6 and Handoff Context).
- [ ] **AC-6**: Given `.claude/rules/context-layer-assessment.md`'s Deletion-Side Eviction paragraph, when this story is complete, then its grep target is generalized from "the `MEMORY.md` indexes" to also include **each agent's own `.claude/agent-memory/<agent>/` directory (MEMORY.md index AND topic files), reconciled by the OWNING agent** — strike stale references, preserve still-valid guidance (a reference is a candidate, never an automatic strike); for an agent on the dispatch team it reconciles its own dir at closure, and for an agent not on the team whose dir has a hit the main session flags it for a follow-up sweep; claude-architect MAY read any dir to IDENTIFY hits but only the owning agent edits its own content. This is a trigger-8 promotion (the recurring per-agent-memory-undercount lesson → the closure rule as its load target).

## Technical Approach
claude-architect owns the non-memory context-layer files (CLAUDE.md, the four rules, `code-reviewer.md`, `implement/SKILL.md`), CA's OWN memory (`epic-codifications.md`, AC-5), and the Deletion-Side-Eviction rule generalization (AC-6, a CA-owned `.claude/rules/` file) — this is a **single-CA-assigned story**, executed by CA alone. The OTHER agents' memory reconciliation was REMOVED as a story-05 AC (a single-assignee story cannot have DE/SE/code-reviewer each editing their own dir within it — CA's AC-5 ruling); it is now an archival-blocking closure obligation the generalized Deletion-Side-Eviction gate discharges (AC-6, Part 3), which is stronger than the unenforceable cross-agent AC was. Apply the doc-sweep discipline rigorously — the E-250 "across games and seasons" miss is the standing lesson that a keyword grep alone is insufficient. Reconcile-not-strike governs the closure sweep too: `schema_drop_test_blast_radius.md` mentions the tables but is live DROP-test guidance (keep it, and E-259-03 cross-references it); `season_tables_are_a_pure_cache.md` is mostly active E-259 design basis whose line-10 rollback clause must be reconciled against epic §3, not struck wholesale. See Technical Notes §5 for the seed set (now the closure sweep's seed, not story 05's).

## Dependencies
- **Blocked by**: E-259-01, E-259-02, E-259-03, E-259-04 (evicts references to everything they remove); **E-256-11 (CROSS-EPIC, HARD)** — AC-3 strikes the Step 1d `verify-aggregates` sub-check + its `code-reviewer.md` Test-Execution-Constraint entry, which E-256-11 ADDS; that surface does not exist until E-256 is COMPLETED + merged (epic Prerequisite 0).
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md` (four sites)
- `.claude/rules/data-model.md`, `.claude/rules/key-metrics.md`, `.claude/rules/perspective-provenance.md`, `.claude/rules/architecture-subsystems.md`
- `.claude/agents/code-reviewer.md` (Bug Pattern Checklist worked example + Step 1d sub-check)
- `.claude/skills/implement/SKILL.md` (Step 1d sub-check)
- `.claude/agent-memory/claude-architect/epic-codifications.md` (CA's own memory, AC-5)
- `.claude/rules/context-layer-assessment.md` (Deletion-Side-Eviction generalization, AC-6 — no other E-259 story touches this file)
- (NOT the data-engineer / software-engineer / code-reviewer memory dirs — those are the closure Deletion-Side-Eviction obligation per AC-6/Handoff, edited by each owning agent at closure, NOT story-05 ACs. Seed set in Technical Notes §5.)

## Agent Hint
claude-architect

## Handoff Context
- **Produces for closure (trigger-7 accounting)**: story 05 reports its eviction tally to PM — files touched, references struck vs. preserved — as INPUT for the closure Context-Layer Assessment Gate's trigger-7 (net context-layer shrinkage) verdict. Per CA's Q3 ruling, the trigger-7 accounting is the closure gate's job (whole-epic quantity, single authoritative writer), NOT a story AC — a story cannot compute the net context-layer delta mid-epic, and a story-written History entry would risk double-writing the closure verdict. This story supplies the raw tally; the closure gate writes the verdict.
- **Produces for closure (per-agent memory sweep, Part 3)**: the data-engineer, software-engineer, and code-reviewer memory reconciliations (Technical Notes §5 seed — DE's `season_aggregate_writers.md`, `season_tables_are_a_pure_cache.md` line-10, `MEMORY.md`, `fixture_seed_not_rollup_consistent.md`, KEEP `schema_drop_test_blast_radius.md`; SE's `testing-gotchas.md`; code-reviewer's relevant memory) are a Deletion-Side-Eviction closure obligation the Context-Layer Assessment Gate discharges before archival (generalized by AC-6). DE is on the E-259 team, so DE reconciles its four files at closure; SE and code-reviewer memory hits, if those agents are not spawned at closure, are main-session-flagged follow-up sweeps.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Doc-sweep discipline applied (AC-1); BUG-PATTERN-CHECKLIST markers intact (AC-2)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The Step 1d strike (AC-3) is the exact case the PM lesson `feedback_record_shrinkage_dont_substitute.md` was written for: verify the property still exists before proposing a replacement; here it does not, so plain deletion is correct.
