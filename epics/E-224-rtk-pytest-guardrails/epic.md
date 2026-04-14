# E-224: RTK/Pytest Interaction Guardrails

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Harden agent pytest usage against three known RTK (Rust Token Killer) interaction issues that have caused incorrect test result reporting. RTK's output compression interacts badly with `-x`/`--exitfirst` (truncated suites reported as passing), reformats output in ways that break text parsing, and lacks a consistently-used bypass path. This epic extends existing context-layer files and adds a warn-only hook to prevent recurrence.

## Background & Context
RTK transparently rewrites `python -m pytest` to `rtk pytest` for token savings. This has caused two categories of incidents:

1. **Silent truncation (E-173, E-220)**: When `-x`/`--exitfirst` is active, pytest stops at the first failure. RTK compresses the output to a summary like "450 passed" with no indication the suite was truncated. Agents report "all tests passed" when hundreds of additional failures never ran. This caused 67 test failures to accumulate silently across E-173.

2. **Output format instability**: RTK reformats pytest output non-deterministically. `grep "^FAILED"` returns reformatted entries instead of standard test paths. Failure lines drop file paths. Summary line format varies based on RTK's compression decisions.

The project already has guardrails for RTK's `-v` interaction (`.claude/rules/pytest-verbose.md` rule + `.claude/hooks/pytest-verbose.sh` hook). This epic extends those guardrails to cover the `-x`/`--exitfirst` and output parsing issues.

**Expert consultations completed:**
- **claude-architect**: Recommends extending existing `pytest-verbose.md` rule (same root cause, stays small), adding summary verification and `rtk proxy` guidance to the rule, one-liner reference in implement skill (no duplication), and extending the existing hook to strip `-x`.
- **software-engineer**: Confirms warn-only hook is technically feasible (`permissionDecision: "allow"` + `permissionDecisionReason`, no `updatedInput`). Recommends separate hook file for independent configurability. Provides regex pattern for `-x`/`--exitfirst` detection including combined short flags.
- **PM synthesis**: Follows CA on placement (extend existing files, no new rule file). Follows user's stated preference + SE on hook behavior (warn, not block — user's original request said "warns, does not block"). Follows SE on separate hook file (different concern: warn vs. rewrite).

**RTK configuration check** (completed by main session): RTK has no config option to preserve original pytest output format. `rtk proxy` is the only bypass mechanism. `~/.config/rtk/filters.toml` exists but has no active filters.

## Goals
- Prevent `-x`/`--exitfirst` from producing misleading "all passed" reports under RTK compression
- Give agents guidance on interpreting RTK-compressed pytest output and verifying summary totals
- Provide a documented bypass path (`rtk proxy`) for when full output fidelity is required
- Catch `-x`/`--exitfirst` usage at runtime via a warn-only hook as a backstop

## Non-Goals
- Modifying RTK itself (no config option exists for output preservation)
- Blocking `-x`/`--exitfirst` entirely (warn-only; agents retain autonomy for targeted single-test debugging)
- Addressing RTK interactions with tools other than pytest
- Changing the existing `-v` injection hook behavior

## Success Criteria
- `.claude/rules/pytest-verbose.md` contains the `-x`/`--exitfirst` prohibition, summary verification guidance, and `rtk proxy` recommendation
- `.claude/skills/implement/SKILL.md` worktree constraints reference the `-x` prohibition
- A PreToolUse hook warns (does not block) when pytest commands include `-x`/`--exitfirst`
- The hook is registered in `.claude/settings.json`

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-224-01 | Extend pytest rule with RTK guardrails | TODO | None | - |
| E-224-02 | Add `-x` prohibition reference to implement skill | TODO | E-224-01 | - |
| E-224-03 | Create warn-only `-x`/`--exitfirst` detection hook | TODO | None | - |

## Dispatch Team
- claude-architect

## Technical Notes

### Placement Strategy
All changes extend existing files except the new hook script (`.claude/hooks/pytest-exitfirst-warn.sh`). No new rule files are created.

- **Rule**: `.claude/rules/pytest-verbose.md` is the single source of truth for all pytest/RTK interaction guidance. It already has `paths: "**"` frontmatter (loads on every interaction). The `-x` prohibition, summary verification, and `rtk proxy` bypass all belong here.
- **Skill**: `.claude/skills/implement/SKILL.md` gets a one-liner added to the "Prohibited" list within the Epic Worktree Constraints section. No duplication of rule content.
- **Hook**: New file `.claude/hooks/pytest-exitfirst-warn.sh` (separate from `pytest-verbose.sh`). Different concern (warn vs. rewrite), independent configurability. Registered in `.claude/settings.json` under the existing `PreToolUse:Bash` matcher array.

### Hook Behavior: Warn, Not Block
The user's original request specified "warns (does not block)." The hook uses `permissionDecision: "allow"` with `permissionDecisionReason` as the warning text and no `updatedInput`. The agent sees the warning message and can proceed. This is proportional to the risk: `-x` is dangerous for full-suite runs under RTK but legitimate for targeted single-test debugging.

### `-x`/`--exitfirst` Detection Regex
Pattern: `(^|\s)--exitfirst(\s|$)|(^|\s)-[a-zA-Z]*x`

This handles:
- `--exitfirst` as a standalone flag
- `-x` as a standalone flag
- `-xvs`, `-vxs`, `-vx` and other combined short flags containing `x`

The hook only fires on commands already identified as pytest invocations (same detection as `pytest-verbose.sh`).

### Warn-Only Hook Output Format
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "WARNING: -x/--exitfirst detected. RTK compression hides suite truncation — summary may show 'N passed' without indicating hundreds of untested files. Remove -x for full suite runs, or use 'rtk proxy python -m pytest tests/ -v --timeout=30' for uncompressed output."
  }
}
```

No `updatedInput` — the command executes as-is. The warning is advisory.

## Open Questions
- None (all resolved during expert consultation)

## History
- 2026-04-14: Created (discovery consultations with CA and SE completed)
- 2026-04-14: Set to READY after Codex validation (2 iterations, 6 findings accepted, 1 dismissed)
