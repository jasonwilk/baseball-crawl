# E-141: Single Epic Worktree Model and Hook Enforcement

## Status
`COMPLETED`

## Overview
Replace the two-tier worktree model (story worktrees + epic worktree) with a single epic worktree where all agents work, and enforce implementation isolation via PreToolUse hooks instead of instruction-based rules. This eliminates story worktree lifecycle, per-story patch-apply, the context-layer exception, and worktree tier collapse -- while enabling safe parallel epic dispatch.

## Background & Context
E-137 built worktree isolation (story-level and epic-level worktrees). E-138 built the full dispatch pipeline with patch-apply merge-back. The first concurrent dispatch (E-134 + E-140) revealed six leak/collapse pathways that all stem from architectural complexity in the two-tier model:

1. **PM on main**: PM modifies `epics/` files directly on main during dispatch, interleaving with other dispatches.
2. **Context-layer exception**: CA agents work on main per the exception, creating split-brain with the epic worktree.
3. **Incomplete closure merge**: Staged impl files mix with other dispatches' changes on main.
4. **`git add -A` contamination**: Unscoped `git add -A` sweeps up all changes from all dispatches.
5. **Story worktree tier collapse**: Implementer lands in the epic worktree instead of a story worktree.
6. **All-context-layer epic breaks closure**: Epic worktree accumulates zero patches, closure merge fails.

Rather than patching each pathway individually, this epic adopts a simpler architecture that eliminates the root causes:

- **One worktree per epic**: No story worktrees. All agents (implementers, CR, PM) work in the single epic worktree. Stories execute serially within an epic.
- **PM in the epic worktree**: Status updates stay in the worktree and merge at closure.
- **Parallel epics**: Multiple epic worktrees can coexist safely (naturally scoped to different file areas).
- **Hook enforcement**: A PreToolUse hook blocks implementation file writes (`src/`, `tests/`, `migrations/`, `scripts/`) to main, providing deterministic enforcement. Context-layer isolation during dispatch is enforced by the implement skill (all stories get worktrees), not the hook — preserving direct-routing exceptions for CA and docs-writer outside dispatch.

Expert consultation: claude-architect (hook design, implement skill simplification scope, PM worktree mechanics, rule file changes, risk assessment).

## Goals
- Implementation file writes to main are blocked by hook (`src/`, `tests/`, `migrations/`, `scripts/`)
- Story worktree lifecycle and per-story patch-apply are eliminated
- The context-layer exception is removed from the implement skill -- all dispatched stories flow through worktrees uniformly
- PM works in the epic worktree during dispatch, not main
- Closure produces a single commit from one epic worktree
- The implement skill is ~30% shorter than today (~880 lines -> ~620 lines)
- `git add -A` contamination is resolved structurally (nothing stray on main during dispatch)

## Non-Goals
- Concurrent story execution within an epic (serial is sufficient for this project's scale)
- Changing agent routing (CA is still the agent for context-layer stories)
- Changing code-reviewer skip for context-layer-only stories (review routing is orthogonal)
- Modifying the codex-spec-review skill
- Application code changes (this is entirely context-layer + hooks)

## Success Criteria
- PreToolUse hook blocks writes to `src/`, `tests/`, `migrations/`, `scripts/` when the file path is in the main checkout
- The implement skill has no references to story worktrees, per-story patch-apply, or the context-layer exception
- The implement skill describes serial story execution with a staging boundary protocol for CR diff isolation
- `worktree-isolation.md` describes a single-tier model (epic worktree only)
- `dispatch-pattern.md` and `workflow-discipline.md` are consistent with the single-tier model
- Total context-layer line count is lower than today

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-141-01 | Worktree guard hooks | DONE | None | claude-architect |
| E-141-02 | Implement skill rewrite for single-tier model | DONE | E-141-01 | claude-architect |
| E-141-03 | Rule file updates for single-tier model | DONE | E-141-02 | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: Hook Design — Write/Edit Path Guard

A PreToolUse hook on `Write` and `Edit` that blocks writes to implementation paths when the agent's working directory is the main checkout.

**Protected paths** (blocked in main checkout):
- `src/`
- `tests/`
- `migrations/`
- `scripts/`

**NOT protected** (writable from main):
- `.claude/agent-memory/`, `.claude/hooks/` — agents write memory from main; hooks are context-layer files
- `epics/`, `.project/` — PM creates epics during planning (before dispatch)
- `.claude/settings.json`, `.claude/settings.local.json` — config changes
- `docs/` — docs-writer and other agents may be invoked outside dispatch
- `.claude/skills/`, `.claude/rules/`, `.claude/agents/`, `CLAUDE.md` — CA is a direct-routing exception; blocking these from main breaks non-dispatch architect work

**Detection logic**: Extract `file_path` from `tool_input`. Check if it starts with `/workspaces/baseball-crawl/` (main checkout prefix) AND matches a protected prefix (`src/`, `tests/`, `migrations/`, `scripts/`). Both conditions must be true to deny. Worktree paths (`/tmp/.worktrees/...`) never match the main checkout prefix, so worktree writes pass unconditionally.

**Hook script**: `.claude/hooks/worktree-guard.sh`. Uses the same stdin JSON protocol as the existing `pii-check.sh` hook.

**Error message**: `"Implementation files (src/, tests/, migrations/, scripts/) must be modified in a worktree, not the main checkout. Check your working directory."`

### TN-2: git add -A Contamination — Resolved by Architecture

The original `git add -A` contamination problem (sweeping up changes from multiple concurrent dispatches on main) is resolved structurally by the single-tier worktree model:
- All implementation work happens in epic worktrees (enforced by the Write/Edit hook)
- PM status updates happen in epic worktrees (new model)
- Context-layer stories happen in epic worktrees (exception removed from implement skill)
- Main checkout stays clean during dispatch — there's nothing stray to sweep up
- Closure applies one patch and stages it — `git add -A` stages exactly the right files

No `git add -A` blocker hook is needed. The three legitimate uses of `git add -A` on main (closure merge, archive, planning) are all safe under this model.

**Epic worktree uniqueness**: Not worth a hook. `git worktree add` already fails if the path exists. The implement skill handles reuse for interrupted dispatches.

### TN-3: Implement Skill Rewrite Scope

The implement skill (~880 lines) is rewritten for the single-tier model. Target: ~620 lines (~30% reduction).

**Removed entirely:**
- Story worktree lifecycle (creation, constraints block, cleanup)
- Per-story patch-apply merge-back flow
- Context-layer exception (isolation-depends-on-file-mix, merge-back skip, separate commit)
- Multi-wave parallel assignment logic
- Story worktree orphan sweep
- Anti-patterns specific to story worktrees (#9 context-layer isolation, #10 worktree commits, #11 merge method)

**Simplified:**
- Agent spawn context: one universal template (all agents get epic worktree path, use absolute paths, no `isolation: "worktree"`)
- Story routing: Agent Hint → routing table, no isolation decision branch
- Cascade: serial — pick next eligible story, no wave management
- Phase 4 remediation: no "epic worktree exception" framing (it's just how everything works)
- Closure merge: no targeted staging caveats, no separate context-layer commit. Stage → patch → dry-run → apply → commit → cleanup.

**Added:**
- Epic worktree constraints block (shorter than story worktree constraints — no worktree lifecycle prohibitions). Includes an explicit Bash write prohibition for protected paths (`echo >`, `sed -i`, `cat >`, `cp`, `mv` to `src/`, `tests/`, `migrations/`, `scripts/`) as backup for the Write/Edit hook bypass gap.
- Per-story staging boundary protocol: after each story passes review, `git add -A` in the epic worktree stages that story's changes. Next story's changes are the unstaged diff. CR reviews `git diff` (unstaged only) for per-story isolation. This replaces per-story patch-apply.
- Post-story path verification: check reported file paths match epic worktree pattern.

**Kept unchanged:**
- Phase 0 (tmux rename)
- Phase 1 `handoff_from_plan` path (adapted: plan skill handoff still skips Steps 1-3 when the planning team is already active and the epic worktree already exists; agent spawning adapts to the new model — no `isolation: "worktree"`, universal spawn context instead)
- Phase 2 Steps 1-2 (epic worktree creation, team creation)
- Phase 3 Steps 1, 3 (eligible stories, status updates)
- Phase 3 Step 5 review/triage/circuit-breaker logic (core quality gate)
- Phase 4a/4b (codex review + integration review)
- Phase 5 Steps 2-6, 9-12 (assessments, summary, archive, cleanup)

### TN-4: PM in Epic Worktree

`isolation: "worktree"` creates a NEW worktree — it cannot point at an existing one. PM (and all agents) are spawned WITHOUT `isolation: "worktree"` and given the epic worktree path in spawn context.

**Spawn approach**: All agents receive a universal spawn context that includes:
- The epic worktree path (e.g., `/tmp/.worktrees/baseball-crawl-E-134/`)
- Instruction to use absolute paths under that path for all file operations
- Epic/story file locations relative to the worktree

**Planning vs. dispatch**: During planning (before dispatch), PM works on main — epic files created at `/workspaces/baseball-crawl/epics/`. When the epic worktree is created (Phase 2), it branches from main and includes these files. PM during dispatch modifies the worktree copy. At closure, changes merge back.

### TN-5: Staging Boundary Protocol for CR Diff Isolation

With all stories sharing one worktree, `git diff` shows everything. The staging boundary solves this:

1. After a story passes review (CR + PM approve), the main session runs `git add -A` in the epic worktree.
2. That story's changes are now staged. The next story starts with a clean unstaged diff.
3. CR reviews `git diff` (unstaged only) for just the current story's changes.
4. `git diff --cached main` shows the cumulative view (all completed stories).

This requires strict serial execution — stories MUST NOT overlap. The staging boundary is the inter-story isolation mechanism.

### TN-6: Risk Assessment

**Serial stories = slower wall-clock dispatch**: Independent stories that could run in parallel now run serially. Acceptable at this project's scale. If it becomes painful, the path back to parallelism is re-adding story worktrees for code stories only.

**Parallel epic merge conflicts**: Two concurrent epics modifying the same file will conflict at closure. This is the right outcome — the user resolves it. Acceptable tradeoff for the flexibility of parallel epics.

**Accumulated changes in epic worktree**: Story N sees stories 1..N-1's staged changes. The staging protocol mitigates this (staged = prior stories, unstaged = current work). Agents must understand this convention (documented in epic worktree constraints).

### TN-8: Pytest from Epic Worktree Limitation

The project uses an editable install (`pip install -e .`) whose meta path finder hardcodes the main checkout's `src/` path and intercepts all `import src.*` before `sys.path` is consulted. `PYTHONPATH=src` has no effect. This means `pytest` run from the epic worktree tests main's code, not the worktree's modified code.

This limitation already exists today for story worktrees. The code-reviewer agent doc (`.claude/agents/code-reviewer.md` lines 260-264) documents it and specifies the workaround: implementers run tests during implementation and report results; CR verifies AC compliance through file inspection rather than running pytest.

Under the single-tier model, this limitation still applies. The epic worktree constraints must preserve the existing guidance: "pytest tests the main checkout's code, not this worktree's changes. Run tests for verification, but understand the limitation. Report test results in your completion message."

**Scope decision**: Investigating or fixing the editable install issue is out of scope for E-141. The current workaround (implementer-reported test results + CR file inspection) is functional. A fix would require changing the install method for worktrees — that's a separate epic if the limitation becomes painful.

### TN-7: Files to Modify (Complete Inventory)

| File | Story | Action |
|------|-------|--------|
| `.claude/hooks/worktree-guard.sh` | E-141-01 | Create |
| `.claude/settings.json` | E-141-01 | Modify (add hook entries for Write and Edit) |
| `.claude/skills/implement/SKILL.md` | E-141-02 | Major rewrite |
| `.claude/rules/worktree-isolation.md` | E-141-03 | Rewrite (single-tier model) |
| `.claude/rules/dispatch-pattern.md` | E-141-03 | Simplify |
| `.claude/rules/workflow-discipline.md` | E-141-03 | Simplify |
| `.claude/agents/code-reviewer.md` | E-141-03 | Modify (update worktree/diff references) |
| `.claude/agents/product-manager.md` | E-141-03 | Modify (update dispatch execution + parallel execution rules) |
| `.claude/skills/codex-review/SKILL.md` | E-141-03 | Modify (remove "epic worktree exception" framing) |
| `.claude/skills/workflow-help/SKILL.md` | E-141-03 | Modify (update for single-tier model) |

## Open Questions
None — all design decisions resolved during CA consultation.

## History
- 2026-03-19: Created as two-tier remediation epic (serial gate + targeted staging). CA root-cause analysis confirmed six leak/collapse pathways.
- 2026-03-19: Iterated through spec review, tier collapse incorporation (E-134 postmortem), and context-layer exception removal (E-140 postmortem). Epic evolved from 2-story patching approach to 2-story simplification approach.
- 2026-03-19: Redesigned around single epic worktree model with hook enforcement, per team lead direction. Architecture eliminates story worktrees entirely, moves PM to epic worktree, enables parallel epic dispatch, and replaces instruction-based rules with PreToolUse hooks. CA assessed feasibility, hook design, implement skill scope (~30% reduction), and risks. Epic rewritten: 3 sequential stories (hooks → skill rewrite → rule updates), all CA.
- 2026-03-19: Four spec review iterations (2 resets). Key refinements: (1) hook scoped to implementation paths only — context-layer isolation enforced by implement skill, not hook; (2) git-add-A blocker dropped — resolved structurally by worktree model; (3) code-reviewer.md and codex-review/SKILL.md added to E-141-03 scope; (4) Bash write prohibition as instruction backup for hook bypass gap; (5) post-story path verification AC added; (6) handoff_from_plan path preserved; (7) pytest limitation documented in TN-8. Final: 3 stories, 6+14+10 ACs, 8 TNs.
- 2026-03-19: Set to READY. All review cycles complete.
- 2026-03-19: Dispatch complete. All 3 stories DONE (E-141-01 hooks, E-141-02 implement skill rewrite, E-141-03 rule file updates). Codex review found 3 findings (all remediated): (1) parallel remediation in shared worktree — serialized remediation flow, (2) closure `git add -A` on main unsafe — added clean-tree preflight check, (3) code-reviewer.md stale context-layer guidance — removed main-checkout reference. Integration review round 1 NOT APPROVED (2 fixes needed), round 2 APPROVED. Documentation assessment: No documentation impact. Context-layer assessment: E-141 is self-codifying — the epic's deliverables ARE the context-layer updates (all 6 triggers fire trivially). Epic COMPLETED.
