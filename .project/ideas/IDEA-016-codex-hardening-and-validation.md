# IDEA-016: Codex Hardening and Validation Trail Map

## Status
`CANDIDATE`

## Summary
After E-081 and E-082 land the safe, documented Codex baseline, run a focused hardening pass to verify the remaining shaky edges: runtime bootstrap, trust/config shape, RTK path exposure, and any future revisit of experimental Codex features such as spawned agents.

## Why It Matters
The current safe plan is intentionally conservative: project-local `CODEX_HOME`, checked-in Codex guidance, repo skills, and explicit `rtk <command>` usage. That is enough to ship a practical Codex lane, but it is not the same as a bulletproof one. A later hardening pass would reduce upgrade risk, remove undocumented assumptions, and give the project a clean path to revisit stronger Codex features only when the platform surfaces are stable enough.

## Rough Timing
Promote this after E-081 and E-082 are complete and the team has at least one real usage cycle with the Codex lane, or sooner if:
- a Codex CLI upgrade changes feature defaults or config behavior
- operators hit friction around `CODEX_HOME`, trust bootstrap, or RTK path resolution
- the project wants to revisit spawned agents or other currently experimental Codex features

## Dependencies & Blockers
- [ ] E-081 must be complete
- [ ] E-082 must be complete
- [ ] Need real operator usage of the safe Codex lane to identify the highest-value hardening gaps
- [ ] If spawned agents are reconsidered, Codex multi-agent support should be documented and stable enough to rely on

## Open Questions
- Which parts of the Codex runtime bootstrap are stable across CLI upgrades, and which need explicit smoke coverage?
- Is `shell_environment_policy.set` sufficient for durable RTK path exposure, or should the repo standardize on absolute-path guidance instead?
- What exact trust-entry/config shape should the project treat as canonical for a project-local `CODEX_HOME` bootstrap?
- If spawned agents are revisited later, which feature flags would be required and how should the repo guard that path?

## Notes
Light trail map:
- Phase 1: Verify the safe baseline end to end after E-081/E-082 land. Treat `AGENTS.md`, `.codex/config.toml`, `.agents/skills/`, project-local `CODEX_HOME`, and explicit RTK usage as the supported lane.
- Phase 2: Add stronger validation around bootstrap behavior: trust config shape, dual-shell env injection, PATH exposure, smoke checks, and upgrade-safe regression checks.
- Phase 3: Re-evaluate advanced Codex surfaces only if the docs and CLI stabilize: spawned agents, multi-agent workflows, or other higher-automation patterns. Keep this optional rather than assumed.
- This idea exists to preserve a future path to "bulletproof" without bloating E-081/E-082 beyond the safe documented baseline.

---
Created: 2026-03-09
Last reviewed: 2026-03-09
Review by: 2026-06-07
