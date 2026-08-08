# IDEA-024: Refactor postCreateCommand into Bootstrap Script

## Status
`CANDIDATE`

## Summary
Extract the monolithic `postCreateCommand` one-liner in `devcontainer.json` (~13 chained steps) into a dedicated `./scripts/devcontainer-setup.sh` orchestrator script. Individual steps become functions with explicit error messages, making failures debuggable and steps individually re-runnable.

## Why It Matters
The infrastructure review (PM, SE, CA -- 2026-03-13) identified the postCreateCommand as being at its complexity limit. It currently chains ~13 steps with `&&`, including external URL downloads (Claude Code, Codex, RTK, ZSH plugins), pip installs, shell config patching, and hook setup. Failure diagnosis requires reading a wall of concatenated output to find which step failed. Only RTK has a `|| echo` fallback; other external downloads cascade-fail everything downstream. Claude Code and Codex installs are unpinned -- a breaking upstream release surfaces at container rebuild time with no graceful fallback.

## Rough Timing
Not urgent today -- the chain works and is mostly idempotent. Trigger: the next time a new tool or setup step needs to be added to the devcontainer bootstrap.

## Dependencies & Blockers
- [ ] None -- can be done at any time

## Open Questions
- Should tool versions be pinned? Claude Code (`curl | bash` -- no version pin), Codex (`npm i -g @openai/codex` -- no version pin). RTK is already pinned in `post-create-env.sh`.
- Should the script support re-running individual steps? (e.g., `./scripts/devcontainer-setup.sh --step rtk`)
- Should `post-create-env.sh` (env injection, Codex trust, RTK install) be absorbed into the new script, or remain separate?

## Notes
- The current chain is: chsh -> zsh plugins (x2) -> sed zshrc -> Claude Code install -> Codex install -> pip-tools -> pip install dev deps -> install-hooks -> post-create-env -> tmux.conf -> pip install -e . -> RTK install
- `post-create-env.sh` is already extracted and has good idempotency (managed blocks). It's a model for what the rest could look like.
- SE noted: the `sed` zshrc patch could double-apply on partial rebuild retry. A function-based script could check before patching.
- Version pinning is a separate concern but naturally fits into this refactor.

---
Created: 2026-03-13
Last reviewed: 2026-03-13
Review by: 2026-06-13
