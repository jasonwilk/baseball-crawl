# E-082-04: Document the Codex RTK operating model

## Epic
[E-082: Codex RTK Project-Level Integration](epic.md)

## Status
`TODO`

## Description
After this story is complete, the operator will have a clear explanation of how RTK works in the Codex lane: where the binary lives, why the integration is explicit instead of transparent, how to verify it, and why no host-global setup is required by default.

## Context
The RTK story for Codex is materially different from the Claude story in E-070. Without documentation, future operators will assume the same `rtk init -g` and host-mounted settings pattern applies. This story records the actual Codex operating model so that assumption does not become a recurring footgun.

## Acceptance Criteria
- [ ] **AC-1**: A project document explains the Codex RTK model: project-local binary install, checked-in Codex guidance, and explicit `rtk <command>` usage.
- [ ] **AC-2**: The document explicitly states that the Codex lane does not rely on a Claude-style automatic RTK hook or `rtk init -g` flow.
- [ ] **AC-3**: The document explains that host `~/.codex` mapping is optional and is not required for the default Codex RTK workflow.
- [ ] **AC-4**: The document records the smoke-check command/path from E-082-03 and the expected success/failure signals.
- [ ] **AC-5**: The document explains the fallback rule: when RTK does not support or improve a command, Codex uses the raw command directly.
- [ ] **AC-6**: The document describes the implemented binary location and confirms that it is gitignored local state, not a committed project artifact.
- [ ] **AC-7**: The document explains coexistence with the existing Claude RTK lane: Claude may still use a host/global RTK install and hook-based integration, while the Codex lane uses a project-local binary and explicit invocation.

## Technical Approach
This documentation can extend the Codex operator guide from E-081 or create a clearly linked companion section if that keeps the structure cleaner. The important thing is that the final docs describe implemented reality only and clearly separate the Codex RTK lane from the Claude RTK lane.

## Dependencies
- **Blocked by**: E-081-04, E-082-01, E-082-02, E-082-03
- **Blocks**: None

## Files to Create or Modify
- `docs/admin/codex-guide.md`

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The Codex RTK model is clearly distinguished from the Claude RTK model
- [ ] The document reflects implemented reality only

## Notes
- This story exists to prevent the "RTK for Codex must work exactly like RTK for Claude" assumption from creeping back in later.
