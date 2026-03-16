# E-112-02: CLAUDE.md Content Trim

## Epic
[E-112: Context Layer Optimization](./epic.md)

## Status
`TODO`

## Description
After this story is complete, CLAUDE.md will be ~131 lines shorter through deduplication and compression of four sections: Proxy Boundary, Script Aliases/Terminal/Shell/Codex, and GameChanger API auth details. All removed content is already available in scoped rules or docs -- this story eliminates redundancy, not information.

## Context
CLAUDE.md loads on every interaction for every agent. Several sections duplicate content that exists in more targeted locations (scoped rules, skill files, API docs). Trimming these sections reduces ambient context load without losing any information, since agents that need the detail can find it in the scoped location.

## Acceptance Criteria
- [ ] **AC-1**: The Proxy Boundary section in CLAUDE.md is reduced to a ~5-line summary + pointer to `.claude/rules/proxy-boundary.md`. The summary preserves the host-vs-container distinction and the "agents MUST NOT start/stop mitmproxy" rule.
- [ ] **AC-2**: The Script Aliases subsection is replaced with a 1-2 line note that the `bb` CLI is the primary interface (scripts are listed in the bb help output). No individual script entries remain.
- [ ] **AC-3**: The Terminal Modes section is compressed to the 5-line summary table (Mode/Environment/Shell/Agent Teams/When to use) plus the tmux rename convention one-liner. The detailed Heavy mode setup steps and stages table are removed (already in `docs/admin/terminal-guide.md`). The compressed summary points to the terminal guide for setup details.
- [ ] **AC-4**: The Shell Environment section is compressed to ~3 lines covering: ZSH is default interactive, Bash is automation shell (hooks/scripts use bash shebangs by design), dual-injection pattern for env vars.
- [ ] **AC-5**: The Codex Bootstrap section is compressed to ~3 lines covering: checked-in layer (`AGENTS.md`, `.codex/`), local runtime at `CODEX_HOME`, see `docs/admin/codex-guide.md` for details.
- [ ] **AC-6**: The GameChanger API three-token architecture paragraph is replaced with a ~2-line summary + pointer to `docs/api/auth.md`. The credential safety rule ("NEVER log, commit, display, or hardcode credentials") and the authenticated-vs-public endpoint distinction are preserved inline.
- [ ] **AC-7**: No information is deleted -- every trimmed detail exists in the referenced scoped location
- [ ] **AC-8**: All existing tests pass after the changes

## Technical Approach
This is a series of targeted edits to CLAUDE.md. For each section, verify the scoped location contains the detail being removed, then replace with a compact summary + pointer. The Bright Data subsection under Proxy Boundary is NOT part of the trim (it has no scoped duplicate).

Reference locations for verification:
- Proxy Boundary detail → `.claude/rules/proxy-boundary.md`
- Terminal Modes detail → `docs/admin/terminal-guide.md`
- GameChanger API auth detail → `docs/api/auth.md`
- Script Aliases → `bb --help` output (runtime, not a file)

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md` (modify)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] No regressions in existing tests

## Notes
- The Bright Data proxy section stays as-is in this story -- E-112-05 handles its migration to `proxy-boundary.md`
- The GameChanger API section retains the public endpoint documentation, scouting pipeline reference, and credential safety rule -- only the auth architecture paragraph is trimmed
- Net savings: ~131 lines from CLAUDE.md
- The context-fundamentals skill budget update is handled by E-112-05 AC-14 (updating after the final CLAUDE.md story ensures numbers are stable)
