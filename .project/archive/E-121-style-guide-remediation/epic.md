# E-121: Style Guide and Context-Layer Remediation

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Remediate 15 style guide and context-layer inconsistencies identified by a triage audit. These range from fabricated rules in agent memory (CR's non-existent "50-line function limit") to contradictions between CLAUDE.md's core principle and python-style.md, missing CLI escape hatches, and agent definitions that no longer reflect the project's actual patterns. Left unfixed, these inconsistencies cause agents to enforce phantom rules, reject valid code, and waste review cycles on false positives.

## Background & Context
A triage audit of agent definitions, rule files, and agent memory surfaced 28 findings across 4 tiers. This epic covers the 15 highest-priority findings (Tier 1, Tier 2, and Tier 3 items that naturally cluster with the same files). The remaining Tier 3/4 items are lower risk and can be addressed later if needed.

Key drivers:
- **CR memory fabrication**: The code-reviewer's memory contains a "50-line function limit" that does not exist in any rule file. python-style.md explicitly says "long functions are acceptable when they are linear and coherent." This fabrication has caused incorrect MUST FIX findings in reviews.
- **Core principle contradiction**: python-style.md says "not plain dicts" while CLAUDE.md says "A dict is better than a class -- until it isn't." Agents receive conflicting guidance.
- **Missing CLI exception**: The "never print()" rule has no escape hatch for CLI user-facing output via `typer.echo()` or `print()`.
- **Stale DE patterns**: The data-engineer agent definition references patterns (insert-anyway for FK violations, speculative index prohibition) that contradict actual project practice.

Expert consultation: claude-architect (context-layer scoping), software-engineer (**authoritative** on Python style replacement language -- user directive), code-reviewer (proportionality and memory cleanup). No baseball-coach or api-scout consultation required -- this epic is pure process/workflow.

## Goals
- Eliminate all fabricated rules from agent memory
- Resolve contradictions between CLAUDE.md core principles and rule files
- Ensure rule files reflect actual project practice (CLI output, FK handling, index policy, aggregate tables)
- Add proportionality to convention-violation severity classification
- Scope rules appropriately (tests vs production, new-table vs tuning)

## Non-Goals
- Rewriting agent definitions from scratch -- only targeted fixes
- Adding new rules or conventions not identified in the triage
- Changing code behavior -- this epic modifies only context-layer files and agent memory
- Addressing Tier 4 (cosmetic/low-risk) findings

## Success Criteria
- No agent memory contains rules that contradict rule files
- python-style.md aligns with CLAUDE.md core principle on simplicity
- CLI output patterns are explicitly permitted in the style guide
- DE agent definition matches actual FK handling and index policy
- CR agent definition includes proportionality for convention violations
- All modified files pass internal consistency check (no contradictions between files modified in the same story)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-121-01 | CR memory cleanup + python-style.md fixes | DONE | None | - |
| E-121-02 | http-discipline.md + testing.md scoping | DONE | None | - |
| E-121-03 | DE agent definition + DE memory fixes | DONE | None | - |
| E-121-04 | CR agent definition + SE/DE agent definition fixes | DONE | E-121-03 | - |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: Change Taxonomy
Each finding has a specific change type. Stories reference these by finding number.

| # | File | Change | Type |
|---|------|--------|------|
| 1 | `.claude/agent-memory/code-reviewer/MEMORY.md` | Delete fabricated "50-line rule" (lines 42-45, line 64) | DELETE |
| 2 | `.claude/rules/python-style.md` | Soften "not plain dicts" to "Prefer ... for cross-module data; plain dicts fine for local use." Delete duplicate line 21 ("Prefer dataclasses or Pydantic models for structured data"). | SOFTEN + DELETE |
| 3 | `.claude/rules/python-style.md` | Add CLI exception to print() rule: "For CLI user-facing output, `typer.echo()`, `rich.Console.print()`, or `print()` are acceptable." (SE authority) | SOFTEN |
| 4 | `.claude/agents/data-engineer.md` | Replace anti-pattern #5 "insert anyway" with stub-row mechanism per actual FK-safe orphan handling. | REPLACE |
| 5 | `.claude/agents/data-engineer.md` | Distinguish new-table indexing (justify with query pattern) from tuning mode (require EXPLAIN). | DISTINGUISH |
| 6 | `.claude/agents/code-reviewer.md` | Add proportionality qualifier to convention-violation MUST FIX classification. | ADD |
| 7 | `.claude/rules/http-discipline.md` | Scope Rate Limiting section to production/operator sessions; note tests mock HTTP. | SCOPE |
| 8 | `.claude/agents/data-engineer.md` | Update "store events, compute on read" to acknowledge aggregate tables as valid. | UPDATE |
| 9 | `.claude/rules/testing.md` | Narrow `paths:` frontmatter: retain `src/**` (needed for test-scope-discovery), remove redundant `**/*test*.py`, add comment explaining `src/**` inclusion. | NARROW |
| 10 | `.claude/rules/python-style.md` | Scope type hints: require in `src/`, recommend for complex test helpers, not required for simple test functions and `-> None` fixtures. (SE authority) | SCOPE |
| 11 | `.claude/rules/python-style.md` | Soften docstring mandate to "when purpose is not obvious from signature." Priority: side effects, error handling, non-trivial preconditions. (SE authority) | SOFTEN |
| 12 | `.claude/agent-memory/data-engineer/MEMORY.md` | Update timestamp example from `2026-03-01T14:30:00Z` to `2026-03-01 14:30:00` (what SQLite `datetime('now')` actually produces). | UPDATE |
| 13 | `.claude/agents/software-engineer.md`, `.claude/agents/data-engineer.md` | Add consultation-mode exception note to Work Authorization section. | ADD |
| 14 | `.claude/agent-memory/data-engineer/MEMORY.md` | Scope ip_outs "no exceptions" -- acknowledge display formatting is a valid read-time concern. | SCOPE |
| 15 | `.claude/rules/testing.md` | Resolve self-contradiction between targeted discovery and full pytest guidance. | REWORD |

### TN-2: Mechanism Note (from CR consultation)
Agent memory (MEMORY.md) is loaded into the agent's system prompt and treated as documentation of conventions. A fabricated rule in memory automatically becomes a blocking MUST FIX finding because the CR agent def says "any finding that violates a documented convention is MUST FIX." This is why finding #1 (50-line rule in CR memory) is the highest priority fix -- it is an active source of incorrect review findings. The proportionality qualifier (finding #6) provides a second layer of defense for future cases where memory drift occurs.

### TN-3: Consistency Constraints
- After modifying python-style.md, verify no new contradiction with CLAUDE.md core principle.
- After modifying DE agent def, verify Error Handling section #4 stays consistent with Anti-Patterns section.
- After modifying CR agent def Priority 6, verify it does not contradict the MUST FIX classification guardrail text.
- DE agent def section "Core Entities" table references "store events, compute on read" -- finding #8 update must be consistent with both the table and the Schema Design section.

### TN-4: Verification Approach
Since these are context-layer files (no code, no tests), verification is by file inspection:
- Each modified file must be internally consistent (no self-contradictions).
- Cross-file references must align (e.g., CR agent def references python-style.md -- both must agree).
- No deleted content should leave orphaned references.

## Open Questions
- None. All decisions resolved during refinement (testing.md `src/**` retained, proportionality criteria tightened per CR, timestamp format corrected to match SQLite `datetime('now')` output).

## History
- 2026-03-17: Created from triage audit findings. Expert consultation with CA, SE, CR during formation.
- 2026-03-17: Refinement pass. Tightened AC-1 proportionality criteria per CR feedback. Corrected DE memory timestamp finding (SQLite `datetime('now')` produces space-separated format, not T/Z). Resolved testing.md `src/**` decision (retain for test-scope-discovery). Removed ambiguous AC language. Consistency sweep passed. Set READY.
- 2026-03-17: Incorporated SE authoritative decisions on python-style.md replacement language (E-121-01 ACs 4-6). Added `rich.Console.print()` to CLI exception, specific type hint scoping wording, docstring priority anchoring. CA responses confirmed all prior decisions. All three consultations complete.
- 2026-03-17: All 4 stories DONE. COMPLETED. All 15 triage findings remediated across 10 context-layer files: CR memory fabricated 50-line rule deleted, python-style.md aligned with CLAUDE.md core principle (dicts, print, type hints, docstrings), http-discipline.md rate limits scoped to production, testing.md paths narrowed and self-contradiction resolved, DE agent def updated (stub-row FK handling, two-mode indexing, aggregate tables acknowledged), DE memory corrected (timestamp format, ip_outs scoping), CR agent def gained proportionality qualifier for convention violations, SE and DE agent defs gained consultation-mode exception notes. Bonus fixes during review: SE agent def Anti-Pattern #5 "in scripts" restriction removed for cross-file consistency with python-style.md (E-121-01 R2), stale examples in CR/SE/DE agent defs updated (E-121-04 R2).
