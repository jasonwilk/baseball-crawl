# E-082-02: Expose project-local RTK to Codex and add explicit usage guidance

## Epic
[E-082: Codex RTK Project-Level Integration](epic.md)

## Status
`DONE`

## Description
After this story is complete, Codex will be able to resolve the project-local RTK binary and will have explicit repo guidance for when to use `rtk <command>`. The Codex lane will gain intentional RTK usage without pretending there is a transparent Claude-style hook layer.

## Context
Codex's documented surfaces are project config, instructions, and skills. That is enough to make RTK available and teach Codex when to use it, but not enough to justify hidden command-rewrite assumptions. The repo should therefore encode explicit RTK guidance in checked-in Codex files and make the project-local RTK binary available to Codex through a deterministic checked-in path strategy.

This story depends on E-081's Codex bootstrap because it extends the checked-in `.codex/config.toml`, `AGENTS.md`, and repo skill pattern established there.

## Acceptance Criteria
- [ ] **AC-1**: The checked-in Codex layer provides a deterministic way for Codex to resolve the project-local RTK binary without relying on user shell dotfiles. Acceptable implementations are: (a) checked-in Codex config exposes the repo-local RTK directory to Codex shell commands, or (b) checked-in Codex guidance uses the absolute repo-local RTK binary path.
- [ ] **AC-2**: Repo Codex guidance documents when Codex should prefer `rtk <command>`, naming at minimum `git status`, `git diff`, and `git log` as high-token commands where RTK is preferred.
- [ ] **AC-3**: The guidance explicitly states that Codex does not use a transparent Claude-style RTK hook in this repo, so RTK usage is intentional and explicit.
- [ ] **AC-4**: The guidance explicitly defines the fallback path: if RTK does not support or clarify a command, Codex uses the raw command directly.
- [ ] **AC-5**: No command-shadowing aliases, wrapper binaries, or PATH shims are introduced for core commands such as `git`, `ls`, or `cat`.
- [ ] **AC-6**: The RTK guidance is contained in checked-in Codex project files only; no host-global Codex skill directories or home config edits are required.

## Technical Approach
This story should extend the Codex layer built in E-081 rather than inventing a separate RTK subsystem. The likely touch points are the checked-in `.codex/config.toml`, the repo `AGENTS.md`, and the repo-scoped bridge skill from E-081-03.

The guidance should stay narrow and practical. It only needs to cover the RTK usage pattern we actually want Codex to follow in this repo.

If checked-in Codex config cannot safely inject the RTK path for shell commands, fall back to absolute-path guidance in checked-in Codex files rather than adding user-shell setup or hidden PATH tricks.

## Dependencies
- **Blocked by**: E-081-01, E-081-03, E-082-01
- **Blocks**: E-082-04

## Files to Create or Modify
- `.codex/config.toml`
- `AGENTS.md`
- `.agents/skills/claude-context-bridge/SKILL.md`

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-082-04**: The actual RTK usage model, path exposure pattern, and fallback rules that the operator doc must explain.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Codex RTK guidance is explicit rather than magical
- [ ] No command-shadowing pattern is introduced

## Notes
- "Project-level as much as possible" means checked-in guidance plus repo-local binary path, not hidden shell tricks.
