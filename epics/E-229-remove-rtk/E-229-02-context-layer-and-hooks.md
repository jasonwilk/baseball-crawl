# E-229-02: Scrub RTK from context layer + drop pytest machinery (atomic)

## Status
`TODO`

## Epic
E-229

## Story
Remove all RTK references from the context layer (Codex config, AGENTS.md, the
claude-context-bridge skill, agent memory, the implement skill, and the
context-fundamentals skill) and drop the pytest tooling that existed only to
compensate for RTK's output compression. The pytest-hook deregistration in
`.claude/settings.json` and the deletion of the two hook `.sh` files MUST happen
in this single story so the repo is never left in a deleted-but-wired (or
wired-but-deleted) state.

## Acceptance Criteria

1. **`.codex/config.toml`**: the 3-line RTK comment block (lines 7-9) is removed.
   Lines 1-5 (model/effort/header) are unchanged. The file remains valid TOML.
2. **`AGENTS.md`**: the entire `## RTK Usage` section (~lines 17-48), including
   the "Coexistence with Claude RTK" subsection, is removed. Surrounding sections
   are intact and the heading structure remains coherent.
3. **`.agents/skills/claude-context-bridge/SKILL.md`**: the
   `## RTK (Token Optimization)` section (lines 31-33) is removed; surrounding
   content preserved.
4. **`.claude/rules/pytest-verbose.md` is deleted.**
5. **`.claude/hooks/pytest-verbose.sh` is deleted.**
6. **`.claude/hooks/pytest-exitfirst-warn.sh` is deleted.**
7. **`.claude/settings.json`**: in the PreToolUse `"Bash"` matcher hooks array,
   the `pytest-verbose.sh` and `pytest-exitfirst-warn.sh` entries are removed.
   `pii-check.sh` and `epic-archive-check.sh` are retained. The Write/Edit
   `worktree-guard` matchers are untouched. The file is valid JSON. (The Bash
   matcher has four entries in order: pii-check, epic-archive-check,
   pytest-verbose, pytest-exitfirst-warn -- remove only the last two.)
8. **Atomicity**: AC 5, 6, and 7 are all satisfied in this story -- no hook file
   is deleted while still registered, and no registration remains for a deleted
   file.
9. **`.claude/skills/implement/SKILL.md`**: the single `-x`/`--exitfirst`
   worktree-constraint bullet (line ~224, which carries the "RTK compression hides
   suite truncation" wording, the `rtk proxy` reference, and the cross-reference to
   `pytest-verbose.md`) is removed, and the surrounding worktree-constraint list
   reads coherently without it.
10. **`.claude/skills/context-fundamentals/SKILL.md` -- recompute ALL affected
    numbers by measuring.** Remove the `pytest-verbose (56)` entry from the
    context-budget table, then recompute every dependent figure across the file
    (the table total, the worked-example subtotals, and the prose aggregate-target
    figures) per Technical Notes. The implementer MUST re-measure the 7 surviving
    universal rule files with `wc -l` and propagate the measured total -- NOT
    blind-subtract 56 from the existing numbers. After the edit, the table count,
    worked-example block, and prose totals are mutually consistent.
11. **No dangling reference**: a grep for `pytest-verbose` across the entire
    `.claude/` tree (excluding `worktrees`) returns zero hits.
12. **No RTK reference remains** in any file this story owns (grep
    `rtk|rust token killer`, case-insensitive, zero hits in the owned files).
    Note: the agent-memory directories are NOT owned by this story -- the only
    RTK-vs-`rtkn` distinction there is handled at closure, see Notes.

## Files to Create or Modify

- `.codex/config.toml` (modify)
- `AGENTS.md` (modify)
- `.agents/skills/claude-context-bridge/SKILL.md` (modify)
- `.claude/rules/pytest-verbose.md` (delete)
- `.claude/hooks/pytest-verbose.sh` (delete)
- `.claude/hooks/pytest-exitfirst-warn.sh` (delete)
- `.claude/settings.json` (modify -- remove the two pytest-hook registrations)
- `.claude/skills/implement/SKILL.md` (modify -- strip the RTK/pytest bullet + cross-ref)
- `.claude/skills/context-fundamentals/SKILL.md` (modify -- recompute all affected numbers)
- (NOT this story -- no agent-memory edits: api-scout/MEMORY.md and software-engineer/endpoint-parsing-notes.md contain only the `rtkn` JWT field (a false positive, NOT Rust Token Killer); claude-architect's memory has zero RTK hits. The only real RTK memory content is PM's own `product-manager/MEMORY.md` (E-224 archival note), swept by the PM at closure.)

## Technical Approach

This is a multi-file context-layer scrub. The single hard constraint is
atomicity between `settings.json` deregistration and the hook-file deletions:
both must land in this story so dispatch never produces a state where a registered
hook points at a missing file. The context-budget recomputation in
`context-fundamentals/SKILL.md` depends on dropping the `pytest-verbose` rule, so
both edits live here together. This story does NOT touch agent memory (see Notes).

For the context-fundamentals recompute (AC-10), the file carries the
pytest-verbose line count (56) in several places that all change when the rule is
dropped: the universal-rules table total (currently "8 rules / ~394 lines"), the
worked-example subtotals that fold in the rules figure, and the prose
aggregate-target / estimate figures. Do NOT blind-subtract 56 -- re-measure the 7
surviving universal rule files with `wc -l`, recompute the table total from the
measured sum, then propagate the corrected rules figure through the worked-example
and prose numbers so the file is internally consistent. See epic Technical Notes
for the affected line locations.

Verify with JSON/TOML validity checks and `pytest-verbose` / `rtk` greps over the
`.claude/` tree.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass (this story's per-file ACs are self-contained; the tree-wide closing grep is an epic-level gate, not a story AC)
- [ ] No context-layer file references `pytest-verbose`, the deleted hooks, or the deleted smoke-check script
- [ ] settings.json remains valid JSON with the correct two remaining Bash hooks and unchanged Write/Edit hooks
- [ ] Code/context follows project style (see CLAUDE.md)

## Non-Goals

- Do not touch host-level RTK artifacts (the global command-rewrite hook in
  `~/.claude`).
- Do not modify provisioning files (those are E-229-01).
- Do not modify `docs/admin/codex-guide.md` (that is E-229-03).
- Do not modify PM's own agent memory (`.claude/agent-memory/product-manager/`)
  -- that is handled at epic closure.
- Do not introduce any replacement pytest rule, hook, or wrapper. This is a full
  drop.

- Agent memory: NO in-epic sweep. A verified grep showed the only `rtk` hits in
  `api-scout/MEMORY.md` and `software-engineer/endpoint-parsing-notes.md` are the
  `rtkn` JWT access-token field -- a false positive (same `rtkn` as the auth docs),
  not Rust Token Killer; the claude-architect memory dir has zero RTK hits. So
  there is nothing to sweep there, and an in-epic sweep would risk deleting valid
  API-payload notes. The only real RTK memory content is PM's own
  `product-manager/MEMORY.md` (an E-224 archival note), which the PM cleans at
  closure.
- The tree-wide closing grep is an EPIC-LEVEL acceptance gate (in epic.md's
  Acceptance Criteria section), not a story-02 AC. This keeps story-02's per-file
  ACs self-contained and `Blocked by: None` honest.
