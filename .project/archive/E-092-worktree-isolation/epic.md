# E-092: Git Worktree Isolation for Agent Teams

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Make the dispatch pattern worktree-native so implementing agents work in isolated git worktrees during epic dispatch. Each agent gets its own working directory and branch, eliminating file conflicts between concurrent agents within a single epic. The main session coordinates merge-back after review approval.

## Background & Context
Today, all implementing agents spawned during dispatch share the main checkout at `/workspaces/baseball-crawl`. This works when stories touch distinct files, but creates risks when agents run concurrently: git index lock contention, accidental file clobber, and test interference. The current dispatch pattern relies on careful file-ownership declarations in stories to prevent conflicts, but this is a convention-based guardrail with no enforcement.

Claude Code's Agent tool supports an `isolation: "worktree"` parameter that creates a temporary git worktree for a spawned agent. The worktree is auto-cleaned if no changes are made; if changes exist, the worktree path and branch are returned for the coordinator to merge. This is a built-in platform feature -- we just need to wire it into our dispatch workflow. **Confirmed by operator**: `isolation: "worktree"` works with both subagents (Task tool) and Agent Teams teammates.

**Expert consultation completed:**
- **software-engineer** (two rounds): Confirmed worktree isolation is safe for tests (`tmp_path`/`:memory:`), Docker stays shared, merge strategy is `--no-ff`, migrations must serialize. Found two concrete code issues: (1) three modules call `dotenv_values()` with no path argument -- in a worktree, this fails to find `.env` because it walks up from cwd. Fix: use `__file__`-relative path fallback, matching the pattern already used in `token_manager.py`. (2) Four files hardcode `./data/app.db` with no env-var override -- low urgency because agents only run pytest, not the pipeline. Issue (1) is addressed by E-092-05. Issue (2) is deferred (not blocking for worktree dispatch).
- **claude-architect**: Identified five context-layer files needing updates. Recommended context-layer stories run WITHOUT worktree isolation (in main checkout). Code-reviewer reads from worktree paths but does not get its own worktree. Per-story merge-back (after review, before cascade) is the correct sequencing. Multi-team concurrent dispatch should be deferred to a future epic.

## Goals
- Implementing agents (SE, DE) work in isolated git worktrees during dispatch, eliminating file conflicts
- Main session handles per-story merge-back after code-reviewer approval
- Context-layer stories (claude-architect) continue to run in the main checkout without worktree isolation
- Code-reviewer reads from worktree paths to verify changes before merge
- Agents understand their worktree environment and its constraints (no Docker, no bb CLI, tests are safe)

## Non-Goals
- Multi-team concurrent dispatch (multiple epics running simultaneously) -- deferred to future work
- Cross-team file reservation or locking mechanisms
- Per-worktree Docker stacks or port management
- Fixing hardcoded `./data/app.db` paths in loaders/crawlers -- not blocking because agents only run pytest (which uses `tmp_path`/`:memory:`), not the pipeline
- Changing the code-reviewer's spawning model (it stays non-isolated, reads worktree paths)

## Success Criteria
- The implement skill spawns implementing agents with `isolation: "worktree"` by default
- Context-layer stories are explicitly exempt from worktree isolation
- A new worktree-isolation rule file documents agent behavior in worktrees
- The dispatch pattern documents merge-back protocol and conflict escalation
- The closure sequence verifies all worktree branches are merged and worktrees removed before archiving

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-092-01 | Create worktree isolation rule | DONE | None | claude-architect |
| E-092-02 | Update dispatch pattern for worktree dispatch | DONE | None | claude-architect |
| E-092-03 | Update implement skill for worktree lifecycle | DONE | E-092-01, E-092-02 | claude-architect |
| E-092-04 | Update code-reviewer for worktree-aware review | DONE | None | claude-architect |
| E-092-05 | Fix dotenv_values() path resolution for worktrees | DONE | None | software-engineer |

## Dispatch Team
- claude-architect
- software-engineer

## Technical Notes

### Worktree Mechanics
Git worktrees (`git worktree add <path> -b <branch>`) create a new working tree sharing the same `.git` object store. A branch can only be checked out in one worktree at a time. Claude Code's `isolation: "worktree"` parameter handles creation, branch naming, and cleanup automatically.

### Isolation Boundary
The `isolation: "worktree"` parameter is passed per-spawn in the Agent tool call -- it is NOT set in agent definition frontmatter. This preserves the ability to spawn agents without worktrees for quick consultations (Task tool) while using worktrees for dispatch.

### Context-Layer Exception
Stories that modify only context-layer files (CLAUDE.md, `.claude/agents/`, `.claude/rules/`, `.claude/skills/`, etc.) must NOT use worktree isolation. These files are shared infrastructure. The existing routing rule (context-layer paths -> claude-architect) is extended with "and spawn without `isolation: worktree`". Context-layer stories run serially in the main checkout.

### Merge-Back Protocol
After code-reviewer approval, the main session runs the merge-back sequence from the main checkout. The full sequence is: APPROVED -> merge -> (if success) remove worktree -> delete branch -> mark DONE -> cascade.

1. Run `git merge --no-ff <worktree-branch>` from the main checkout
2. If merge succeeds: remove worktree (`git worktree remove <path>`; `--force` if needed), delete branch (`git branch -d <branch>`), mark story DONE, proceed to cascade
3. If merge conflicts: story remains IN_PROGRESS, cascade is blocked for dependent stories only (non-dependent stories can proceed). The user resolves the conflict in the main checkout (not the worktree). After resolution, the main session marks DONE, removes the worktree, deletes the branch, and proceeds to cascade.

Merge must happen BEFORE cascade, because cascaded stories may depend on the merged changes. A story is NOT marked DONE until its branch is successfully merged.

### Docker and CLI Constraints
Agent worktrees do not interact with Docker or the `bb` CLI. The Docker stack reads from the main checkout's `data/` volume mount. Tests run fine in worktrees because they use in-process ASGI clients and temporary databases.

### Migration Serialization
Migration stories (data-engineer) must never run concurrently to avoid numbering conflicts. This is already implicit in current practice but should be documented explicitly in the dispatch pattern.

### dotenv_values() Path Resolution Bug
Three modules call `dotenv_values()` with no path argument, which searches from cwd upward. In a worktree, cwd is the worktree root (e.g., `/tmp/.worktrees/baseball-crawl-abc123/`), and `.env` is not there -- it is gitignored and only exists in the main checkout. Affected modules: `src/gamechanger/client.py`, `src/gamechanger/credentials.py`, `src/http/proxy_check.py`. The fix is to use `__file__`-relative path resolution, matching the pattern already established in `src/gamechanger/token_manager.py` (`Path(__file__).resolve().parents[N] / ".env"`). This is a code fix (E-092-05) independent of the context-layer stories.

### Worktree Cleanup Lifecycle
Per-story cleanup happens immediately after successful merge (not deferred to closure):

1. Main session spawns agent with `isolation: "worktree"` -- Claude Code creates worktree + branch
2. Agent works in worktree, reports completion with `## Files Changed`
3. Code-reviewer reviews from worktree path
4. If NOT APPROVED: implementer fixes in same worktree (review rounds continue)
5. If APPROVED: main session merges branch (`git merge --no-ff <branch>`)
6. Main session removes worktree (`git worktree remove <path>`; if that fails due to untracked files, retry with `--force`)
7. Main session deletes branch (`git branch -d <branch>` -- safe because branch is fully merged)

Closure includes a sweep: `git worktree list --porcelain` to catch any orphaned worktrees from error paths, `git worktree remove --force` to clean them, `git worktree prune` as a last resort for stale registrations.

### Error Paths

| Error | When | Handling |
|-------|------|----------|
| Agent crashes mid-work | During implementation | Claude Code auto-cleans worktrees for agents that exit without changes. If partial changes exist, worktree persists. Main session runs `git worktree list --porcelain` to identify orphan, `git worktree remove --force <path>` to clean it, `git branch -D <branch>` to delete the unmerged branch, then escalates to user. |
| Merge conflict | After review approval | Escalate to user with conflict details. Worktree stays active for inspection. User resolves or abandons. Main session cleans up after resolution. |
| Review rejects (max rounds) | Circuit breaker | Existing escalation to user. Worktree stays active until user decides. If story abandoned, main session cleans up worktree without merging. |
| Worktree cleanup fails | After merge | `git worktree remove` can fail if directory is in use or has untracked files. Retry with `--force`. If even `--force` fails, log warning and continue -- worktree is inert after branch is merged. Closure sweep with `git worktree prune` catches stale registrations. |

### Overlap Prevention
The main session SHOULD NOT assign concurrent stories with overlapping "Files to Create or Modify" sections to parallel worktrees. If overlap is detected during routing, those stories are serialized (assigned sequentially, not concurrently). This is prevention-first: file-ownership declarations in stories prevent conflicts at planning time; the merge conflict escalation is the safety net.

### Merge Serialization Constraint
Single-team dispatch uses a single main session as the sole merge coordinator. Merges are sequential (`git merge` acquires `.git/index.lock`). This is a design constraint, not a limitation -- it ensures merge order matches dependency order. Multi-team concurrent dispatch (two main sessions merging into the same branch simultaneously) would require a future coordination mechanism (merge queue, separate base branches, or operator-queued merges).

### File Paths in Reports
Implementing agents report `## Files Changed` with worktree-absolute paths. The main session and code-reviewer must use these paths for review. After merge, paths map back to the main checkout naturally.

## Open Questions
- How exactly does Claude Code name worktree branches? (e.g., `worktree-<hash>`, `agent-<name>-<timestamp>`) -- affects merge commit messages but not the workflow.
- Where does Claude Code create worktree directories? (e.g., `/tmp/.worktrees/`, sibling to repo) -- affects the rule file's path guidance.

## History
- 2026-03-10: Created. SE and CA consultations completed during planning.
- 2026-03-10: Multi-agent review: SE (2 rounds -- project mechanics + concrete code bugs), CA (2 rounds -- context-layer scope + coordination/cleanup analysis), code-reviewer (spec review -- 5 MUST FIX resolved). Two Codex spec reviews: round 1 (4 findings -- resolved open question, dependency fix, AC language fix, test expectation fix), round 2 (3 findings -- review template gap, monkeypatch signature breakage, test file list). All findings resolved. Set to READY.
- 2026-03-10: Dispatched. Wave 1: E-092-01 (architect-01), E-092-02 (architect-02), E-092-04 (architect-04), E-092-05 (se-05). Wave 2: E-092-03 (architect-04, after 01+02 completed). E-092-05 reviewed by code-reviewer (APPROVED, no findings). All 5 stories DONE.
- 2026-03-10: Documentation assessment: No documentation impact (internal agent dispatch mechanics only).
- 2026-03-10: Context-layer assessment: (1) New convention -- YES, codified by E-092-01 (worktree-isolation.md). (2) Architectural decision -- YES, codified by E-092-02 (dispatch-pattern.md). (3) Footgun/boundary -- YES, codified by E-092-01 (worktree constraints). (4) Agent behavior change -- YES, codified by E-092-02/03/04 (dispatch, skill, reviewer). (5) Domain knowledge -- NO. (6) New CLI/workflow -- NO. All firing triggers already codified by the epic's own stories; no additional context-layer work needed.
- 2026-03-10: COMPLETED.
