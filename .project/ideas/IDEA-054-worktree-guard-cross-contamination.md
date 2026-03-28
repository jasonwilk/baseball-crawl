# IDEA-054: Worktree Guard Should Prevent Cross-Epic Contamination

## Status
`CANDIDATE`

## Summary
The worktree guard hook should include intent-layer awareness that prevents agents from writing one epic's files into another epic's worktree. Currently the hook only distinguishes "main checkout vs. worktree" -- it has no concept of epic ownership. An agent blocked from writing to main can be directed (by the main session or itself) to write into an unrelated epic's worktree, contaminating that worktree's git state.

## Why It Matters
During E-176 planning, the main session suggested writing E-176 epic files into the E-173 worktree because E-173's worktree was blocking writes to main. This would have contaminated E-173's worktree with unrelated files. The worktree guard's denial message says "use the epic worktree path instead" without specifying *which* worktree -- it implicitly assumes there's only one. When multiple worktrees coexist (parallel epics, stale worktrees), this guidance is ambiguous and leads to cross-contamination.

Possible fixes at the intent layer:
- The hook's denial message could include the detected worktree path AND warn "do not write to worktrees belonging to other epics"
- The planning skill could automatically create the current epic's worktree before spawning PM, eliminating the ambiguity
- The hook could parse the epic ID from the file path being written and compare it to the worktree's epic ID, blocking mismatches

## Rough Timing
Next context-layer epic. This is a low-cost fix with high value for multi-epic scenarios.

## Dependencies & Blockers
- [ ] None -- this is a hook/skill change, not a code change

## Open Questions
- Should the fix be in the hook (structural enforcement), the planning skill (process), or both?
- Should the hook detect the "target epic" from the file path (e.g., `epics/E-176-*/` → epic E-176) and compare to the worktree's branch name?
- How should the hook handle non-epic files (e.g., `CLAUDE.md` updates) written to a worktree?

## Notes
- Root cause: main session suggested E-173 worktree for E-176 files because the hook's denial message is ambiguous about which worktree to use
- The planning skill currently doesn't create a worktree -- it expects to write to main. When main is blocked, there's no automatic fallback.
- Related: IDEA-045 (worktree divergence detection), IDEA-047 (phantom deletions)

---
Created: 2026-03-28
Last reviewed: 2026-03-28
Review by: 2026-06-26
