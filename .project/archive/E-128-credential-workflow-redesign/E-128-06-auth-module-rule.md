# E-128-06: Auth-Module Rule File

## Epic
[E-128: Credential Workflow Redesign](epic.md)

## Status
`DONE`

## Description
After this story is complete, agents editing auth module source files will automatically receive implementation constraints via a glob-triggered rule file. This prevents recurring discovery costs (e.g., using `os.environ` instead of `dotenv_values()`, routing refresh through `create_session()`, misinterpreting HTTP 400 vs 401).

## Context
The auth module source files (`src/gamechanger/{signing,token_manager,client,exceptions}.py`) have no dedicated rule file. The `http-discipline.md` rule covers `src/gamechanger/**` but focuses on request behavior (rate limiting, browser headers), not auth-specific constraints. Implementation constraints are only in CLAUDE.md's "GameChanger API" section -- ambient but not scoped. CA's audit (2026-03-18) identified this as the single most impactful context-layer gap.

## Acceptance Criteria
- [ ] **AC-1**: A rule file `.claude/rules/auth-module.md` exists with paths scoped to `src/gamechanger/signing.py`, `src/gamechanger/token_manager.py`, `src/gamechanger/client.py`, `src/gamechanger/exceptions.py`.
- [ ] **AC-2**: The rule file documents per Technical Notes TN-5: exception hierarchy, httpx client choice, env var access pattern, `.env` write-back mechanism, client pattern (lazy fetch + 401 retry), security constraints.
- [ ] **AC-3**: The rule file is concise (under 60 lines) and actionable -- constraints only, no background narrative.
- [ ] **AC-4**: CLAUDE.md's "GameChanger API" section's Auth bullet is slimmed to a pointer to the rule file (e.g., "Auth module constraints are in `.claude/rules/auth-module.md`"), removing duplicated detail. The Auth bullet is consistent with the rule file content.

## Technical Approach
Create a new rule file per Technical Notes TN-5. Review the existing CLAUDE.md auth-related sections for consistency. The rule file should be self-contained -- an agent reading only the rule file should know all implementation constraints for the auth module.

**Overlapping glob scope**: `http-discipline.md` already fires on `src/gamechanger/**`. The auth-module rule is **additive** -- it covers auth-specific implementation constraints (exception hierarchy, env var access, write-back). It must NOT duplicate rate-limiting, browser headers, or other HTTP-level rules already in `http-discipline.md`.

Key files to study: `.claude/rules/http-discipline.md` (existing rule format and overlapping scope), `src/gamechanger/token_manager.py` (implementation patterns to document), CLAUDE.md (GameChanger API section).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/auth-module.md` -- new rule file
- `CLAUDE.md` -- review and update auth-related sections if needed

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Rule file follows existing rule file conventions
- [ ] No regressions in existing rules
