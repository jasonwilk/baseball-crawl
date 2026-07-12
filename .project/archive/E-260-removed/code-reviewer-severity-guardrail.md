# Removed text snapshot — code-reviewer.md MUST FIX classification guardrail

- **Source:** `.claude/agents/code-reviewer.md`
- **Story:** E-260-03 (Replace the code-reviewer severity test with a two-tier floor)
- **Date:** 2026-07-11
- **Original line range (pre-edit):** 226 (the "MUST FIX classification guardrail" paragraph, under Priority 6: Convention Violations)

Replaced by a single two-tier severity floor (MUST FIX must name a functional consequence; everything else is SHOULD FIX, one message, no round). The adjacent "Scope guardrail" (:228) is orthogonal and retained.

---

## :226 — removed three-condition downgrade guardrail

**MUST FIX classification guardrail**: Any finding that violates a documented convention (CLAUDE.md, `.claude/rules/python-style.md`, `.claude/rules/testing.md`) is MUST FIX by default. A convention violation MAY be downgraded to SHOULD FIX only when ALL THREE conditions are met: (a) the violation has no functional impact (runtime behavior, correctness, security, or test reliability is unaffected), (b) the violation is in code that follows an established pattern already present in the same file or module (the implementer matched existing style, not invented something new), and (c) the violation is NOT in: security rules, credential handling, SQL scope, or test coverage (those are always MUST FIX). SHOULD FIX remains the classification for genuinely optional improvements not mandated by project rules.
