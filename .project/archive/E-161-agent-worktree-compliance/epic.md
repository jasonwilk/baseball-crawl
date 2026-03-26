# E-161: Agent Worktree Compliance Audit and Hardening

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview

During E-158 dispatch, docs-writer was spawned with explicit worktree path instructions but wrote documentation files to the main checkout (`/workspaces/baseball-crawl/docs/`) instead of the epic worktree. This forced a manual file sweep and restore operation during closure. This epic audits all nine agents for similar worktree compliance gaps and hardens the enforcement mechanisms so that no agent can silently write to the wrong checkout during dispatch.

## Background & Context

**The incident (E-158):** Docs-writer received spawn context specifying the epic worktree path (`/tmp/.worktrees/baseball-crawl-E-158/`) but produced files under `/workspaces/baseball-crawl/docs/`. The main session's post-story path verification (implement skill Phase 3 Step 5) should have caught this, but the damage was already done -- the files existed in the main checkout and required manual cleanup.

**Current enforcement layers:**

1. **worktree-guard hook** (`.claude/hooks/worktree-guard.sh`): PreToolUse hook that blocks Write/Edit to `src/`, `tests/`, `migrations/`, `scripts/` in the main checkout. Worktree writes pass unconditionally. **Gap: `docs/`, `epics/`, `.claude/`, and other paths are not protected.** The hook was designed for implementation paths only.

2. **Spawn context language** (`.claude/skills/implement/SKILL.md` Phase 2 Step 3): Universal implementer spawn context says "Use absolute paths under this directory for ALL file operations." PM and code-reviewer spawn contexts also include the worktree path. **Gap: The instruction is advisory -- an agent that constructs paths from its own knowledge (e.g., "docs live at `/workspaces/baseball-crawl/docs/`") can bypass it.**

3. **worktree-isolation rule** (`.claude/rules/worktree-isolation.md`): Loaded on every interaction (`paths: "**"`). Says "Use absolute paths" and "Stay in the epic worktree." **Gap: Same advisory nature. No deterministic enforcement for non-implementation paths.**

4. **Post-story path verification** (implement skill Phase 3 Step 5): The main session checks Files Changed paths after completion. **This is detective, not preventive -- the wrong-directory write has already happened.**

**Root cause hypothesis:** The worktree-guard hook protects only four directories (`src/`, `tests/`, `migrations/`, `scripts/`). Any agent writing to `docs/`, `epics/`, `.claude/`, `templates/`, or project root files in the main checkout will not be blocked by the hook. The advisory language in spawn context and rules is insufficient when an agent resolves paths from its own training data or agent definition rather than from the provided worktree path.

**Expert consultation:** Claude-architect consulted (2026-03-26). Key decisions:
- **Allowlist with dispatch detection** (not expanded denylist). When an epic worktree exists, block ALL Write/Edit to main checkout except `.claude/agent-memory/`. When no worktree exists, retain existing always-on denylist for implementation paths only. This fails closed during dispatch and is permissive outside dispatch.
- **Dispatch detection**: Check for `/tmp/.worktrees/baseball-crawl-E-*` directory existence. Stale worktrees safely enforce stricter mode.
- **Agent definitions**: Do NOT overhaul with worktree constraints (those are dispatch-time context, not agent identity). Only fix hardcoded non-memory example paths. Spawn context and rules are the correct places for negative instructions.
- **Two stories** (not three): Audit findings folded into Technical Notes (TN-5) rather than a separate story. Story 1 = hook expansion, Story 2 = spawn context + documentation hardening.
- **Agent audit findings**: See TN-5 for the full agent risk assessment.

## Goals

- Audit all nine agent definitions (`.claude/agents/*.md`) for hardcoded or implied path references that could cause wrong-checkout writes during dispatch
- Identify every file path pattern written during dispatch that is NOT covered by the current worktree-guard hook
- Expand worktree-guard hook coverage to block main-checkout writes for all dispatch-relevant paths (not just implementation paths)
- Ensure spawn context language is unambiguous and deterministic enough that agents cannot silently resolve to the wrong checkout

## Non-Goals

- Changing the hook to block ALL writes to main checkout unconditionally (must be dispatch-aware -- non-dispatch work happens in main checkout)
- Refactoring the dispatch pattern or implement skill beyond the minimum needed to close the gap
- Addressing agent compliance issues unrelated to worktree paths (e.g., consultation compliance, work authorization)
- Changing how the main session's own git operations work (those are already in the main checkout by design)

## Success Criteria

1. **Hook allowlist mode**: When an epic worktree exists at `/tmp/.worktrees/baseball-crawl-E-*/`, the hook blocks ALL Write/Edit to `/workspaces/baseball-crawl/` except paths matching `.claude/agent-memory/*`. This covers the full risk surface: `docs/`, `epics/`, `.claude/agents/`, `.claude/rules/`, `.claude/skills/`, `.claude/hooks/`, root files (`CLAUDE.md`, `pyproject.toml`), and any future paths -- not just the named examples.
2. **Hook denylist mode**: When NO epic worktree exists, the hook retains the existing always-on denylist for `src/`, `tests/`, `migrations/`, `scripts/` and allows everything else. Non-dispatch work (e.g., claude-architect writing to `.claude/rules/`) is unaffected.
3. **Agent memory allowlist**: Write/Edit to `.claude/agent-memory/<agent-name>/` in the main checkout is allowed regardless of dispatch state. (Agent memory intentionally stays in main checkout during dispatch. Note: the main session's memory is at `/home/vscode/.claude/projects/*/memory/` -- outside the repo entirely and unaffected by this hook.)
4. **Worktree writes pass**: Write/Edit to `/tmp/.worktrees/baseball-crawl-E-NNN/` paths always pass regardless of dispatch state.
5. **Spawn context hardened**: The implement skill's spawn contexts include an explicit negative instruction prohibiting Write/Edit to `/workspaces/baseball-crawl/` paths during dispatch.
6. **Documentation updated**: `worktree-isolation.md` and CLAUDE.md accurately describe the expanded hook behavior (both modes).

## Stories

| ID | Title | Status | Agent | Deps |
|----|-------|--------|-------|------|
| E-161-01 | Expand worktree-guard hook to allowlist mode with dispatch detection | DONE | claude-architect | None |
| E-161-02 | Harden spawn context and update context-layer references | DONE | claude-architect | E-161-01 |

## Dispatch Team

- claude-architect

## Technical Notes

### TN-1: Hook Scope Analysis

Current protected paths in `worktree-guard.sh`:
- `src/*`
- `tests/*`
- `migrations/*`
- `scripts/*`

Paths written during dispatch that are NOT protected:
- `docs/` (docs-writer output -- the E-158 failure)
- `epics/` (PM status updates, story files)
- `.claude/agent-memory/` (agents writing to their own memory -- but this is intentional in main checkout)
- `.claude/agents/`, `.claude/rules/`, `.claude/skills/`, `.claude/hooks/` (claude-architect context-layer work)
- Root files (`CLAUDE.md`, `pyproject.toml`, etc.)

Note: `templates/` was originally listed here but Jinja2 templates live under `src/api/templates/` which is already covered by the `src/` denylist. Removed as not a real gap.

### TN-2: Design Decision -- Allowlist with Dispatch Detection (Resolved)

**Decision**: Allowlist with dispatch detection (CA consultation, 2026-03-26).

**Mechanism**: The hook checks for the existence of `/tmp/.worktrees/baseball-crawl-E-*` directories. Two modes:
- **Dispatch active** (worktree exists): Block ALL Write/Edit to `/workspaces/baseball-crawl/` except `.claude/agent-memory/*`. Fails closed -- new paths are automatically protected.
- **No dispatch** (no worktree): Retain existing always-on denylist for `src/`, `tests/`, `migrations/`, `scripts/`. All other main-checkout writes allowed (agents like CA legitimately write to `.claude/rules/`, etc. outside dispatch).

**Why not always-on allowlist**: Outside dispatch, agents like claude-architect legitimately Write/Edit to `.claude/rules/`, `.claude/agents/`, `.claude/skills/`, `CLAUDE.md`, `epics/`, etc. in the main checkout. An always-on allowlist would break non-dispatch workflows.

**Why not expanded denylist**: New paths added in the future would not be protected until someone updates the hook. The allowlist approach is maintenance-free for new paths.

### TN-3: Agent Definition Audit Checklist

For each of the nine agents, check:
1. Does the agent definition reference any absolute path under `/workspaces/baseball-crawl/`?
2. Does the agent definition describe output locations (e.g., "writes to `docs/admin/`") that could be resolved to the main checkout?
3. Does the agent's tool set include Write/Edit? (Read-only agents like baseball-coach cannot cause this issue.)
4. Is the agent ever spawned during dispatch? (Agents only used in consultation mode are lower risk.)

### TN-4: Main Session Legitimate Main-Checkout Operations

The main session performs these Write/Edit-equivalent operations in the main checkout:
- `git mv` for archive operations
- Writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`)
- None of these use Write/Edit tools -- they use Bash/git commands

The hook only intercepts Write and Edit tool calls, not Bash commands. This means the allowlist approach would NOT block the main session's legitimate operations.

### TN-5: Agent Audit Findings (CA Consultation, 2026-03-26)

| Agent | Write/Edit? | Dispatch Role | Unprotected Risk Paths | Risk |
|-------|------------|---------------|------------------------|------|
| docs-writer | Yes | Implementer | `docs/admin/`, `docs/coaching/` | **HIGH** (E-158 incident) |
| product-manager | Yes | Infrastructure | `epics/`, `.claude/agent-memory/pm/` | MEDIUM |
| claude-architect | Yes | Implementer (context-layer) | `.claude/rules/`, `.claude/agents/`, `.claude/skills/`, `CLAUDE.md` | MEDIUM |
| ux-designer | Yes | Implementer | `docs/` (design specs) | MEDIUM (never dispatched yet) |
| api-scout | Yes | Implementer | `docs/api/` | MEDIUM |
| software-engineer | Yes | Implementer | `src/`, `tests/`, `scripts/` | LOW (already hook-protected) |
| data-engineer | Yes | Implementer | `migrations/`, `src/` | LOW (already hook-protected) |
| baseball-coach | Yes | Consultation only | `.claude/agent-memory/` only | LOW |
| code-reviewer | No | Infrastructure | N/A | NONE |

**Key findings**:
- No agent definition mentions the worktree-guard hook or its limitations
- docs-writer Work Authorization section has a hardcoded main-checkout example path (only non-memory example path found)
- Spawn context says what TO do but not what NOT to do -- needs explicit negative instruction
- Agent memory paths in definitions correctly reference main checkout (intentional, do not change)

## Open Questions

All resolved. See TN-2 for the allowlist/dispatch-detection decision, TN-5 for the agent audit.

## History

- 2026-03-26: Created (DRAFT). Prompted by docs-writer writing to main checkout during E-158 dispatch.
- 2026-03-26: CA consultation completed. Allowlist with dispatch detection chosen. Agent audit findings added to TN-5. Two stories written. P2/P3 findings from Codex spec review addressed (templates/ removed from TN-1, SC agent-memory misattribution fixed, Success Criteria broadened to full risk surface). Set to READY.
- 2026-03-26: COMPLETED. Both stories delivered by claude-architect. Worktree-guard hook expanded to allowlist mode with dispatch detection (E-161-01). Spawn context hardened with explicit main-checkout Write/Edit prohibition; worktree-isolation.md and CLAUDE.md updated to document both modes; docs-writer hardcoded example path fixed (E-161-02). One integration review finding (comment glob pattern) and one Codex finding (missing AC-1 prohibition in universal spawn context) accepted and remediated. Phantom `git diff main` bug captured as IDEA-047.

### Review Scorecard

| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-161-01 | 0 | 0 | 0 |
| Per-story CR -- E-161-02 | 0 | 0 | 0 |
| CR integration review | 1 | 1 | 0 |
| Codex code review | 2 | 1 | 1 |
| **Total** | **3** | **2** | **1** |

Notes: Per-story CR skipped (context-layer-only). CR integration: 1 SHOULD FIX (comment glob pattern, accepted+fixed). Codex: P1 branch divergence (dismissed — phantom diff bug, IDEA-047), P5 missing AC-1 prohibition in universal spawn context (accepted+fixed).

### Documentation Assessment

No documentation impact. All changes are context-layer (hook, rules, spawn context, CLAUDE.md). No new features, endpoints, schema changes, or user-facing behavior.

### Context-Layer Assessment

| Trigger | Fires? | Verdict |
|---------|--------|---------|
| T1: New convention/pattern | Yes | Dispatch-active allowlist mode is a new enforcement pattern — codified by this epic itself (hook, worktree-isolation.md, CLAUDE.md, spawn context) |
| T2: Architectural decision | No | Refinement of existing hook infrastructure, not a new architecture choice |
| T3: Footgun/failure mode | Yes | E-158 wrong-checkout write incident now documented and enforced — codified by this epic itself |
| T4: Agent behavior change | Yes | Agents are now blocked from main-checkout Write/Edit during dispatch — codified by this epic itself |
| T5: Domain knowledge | No | No domain knowledge changes |
| T6: New CLI/workflow | No | No new CLI commands or workflows |

T1, T3, T4 all fire but are already codified by the epic's own deliverables (hook changes, rule updates, CLAUDE.md updates, spawn context hardening). No additional claude-architect dispatch needed.
