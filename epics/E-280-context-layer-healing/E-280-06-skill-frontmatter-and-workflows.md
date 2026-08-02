# E-280-06: Skill frontmatter ×10 and CLAUDE.md Workflows compression (DOCTOR c)

## Epic
[E-280: Context-Layer Healing](./epic.md)

## Status
`TODO`

## Description
After this story, all ten `SKILL.md` files carry `name` and `description` frontmatter and are harness-discoverable, the trigger phrases that currently live in three places live in one, and CLAUDE.md's Workflows section is a pointer rather than a restatement. This is net-subtractive despite adding frontmatter.

## Context
**Zero of ten SKILL.md files have YAML frontmatter** — confirmed independently by PM and by the design owner. Every one opens with `# Skill: <name>` / `**Category**` / `**Adapted for**`. No skill is harness-discoverable and all loading routes through CLAUDE.md prose.

The two halves are one restatement, not two chores. CLAUDE.md's `## Workflows` section is **seven bullets covering six skills** — *Curate the vision* is a bullet that invokes the product-manager in curate mode and names no skill — and each skill bullet restates the trigger phrases that belong in that skill's `description` frontmatter. The in-body `## Activation Triggers` sections restate them a third time — **133 body lines plus 10 headings** today. Adding the frontmatter creates the single source; collapsing the other two is what makes it single. Under the epic's design test in TN-7, doing only one half fails.

Arithmetic worth stating so the closure reading is not misread as growth: frontmatter adds 4 lines × 10 = 40 to `.claude/skills`, and the collapsed Activation Triggers sections remove roughly 143, for a net near **−100 lines**. CLAUDE.md is not in the four counted subtrees at all, so its compression scores zero on the line-count diagnostic while removing roughly 700 tokens from every agent's always-on load — which is the actual point, and an instance of the instrument mispricing the change (epic TN-4b). Note the framing: the context-layer size **gate was retired** by operator ruling on 2026-08-02 (epic OQ-1), so these numbers are reported and never judged. No subtree total can fail this story.

The reference format lives in the installed marketplace skills at `~/.claude/plugins/marketplaces/context-engineering-marketplace/skills/*/SKILL.md`: a `name` plus a `description` written in the form "This skill should be used when…".

## Acceptance Criteria

- [ ] **AC-1**: All ten `SKILL.md` files carry a YAML frontmatter block beginning at line 1 with both `name` and `description`. **RED**: fewer than ten, or a block not starting at line 1.
- [ ] **AC-2**: Each `description` is written in the harness-discoverable form and carries that skill's trigger conditions. **RED**: a description that states what the skill *is* without stating when it should be used.
- [ ] **AC-3**: Every trigger phrase present in CLAUDE.md's `## Workflows` section before the change appears in **exactly one** location after it, and a worklist names the location per phrase. **RED**: a phrase in zero locations, or a phrase in two. (This goes red on a lost phrase and on a surviving duplicate — both failure directions.)
- [ ] **AC-4**: Every SKILL.md gets a **written verdict** on its in-body `## Activation Triggers` section — removed, retained with a stated reason, or absent to begin with. **RED**: a SKILL.md with no verdict, or a file carrying both a frontmatter `description` and an in-body triggers section with no reason recorded for the duplication.
- [ ] **AC-5**: The `.claude/skills` subtree line count is strictly lower after the change than before, both figures recorded. **RED**: not lower. (This is a property of this story's own edit, not a baseline check — the size gate is retired, nothing is offset, no exception exists or is needed. Its RED is the one that matters: if the count is not lower, the Activation Triggers collapse did not happen and only the additive half landed.)
- [ ] **AC-6**: CLAUDE.md's byte size is strictly lower after the change, and both figures are recorded. **RED**: after ≥ before.
- [ ] **AC-7**: No skill becomes unreachable. Every trigger phrase present before the change resolves, after it, to **either** a frontmatter `description` on the skill it triggers **or** the CLAUDE.md Workflows pointer. **RED**: a phrase whose post-change location is neither. (Reworded 2026-08-02: the previous RED was *"a file the harness does not consult for that phrase"*, which **no reviewer in this repo can evaluate** — harness skill-discovery behavior is documented nowhere here, so the criterion rested on knowledge nobody has. The two named locations are checkable by reading.)
- [ ] **AC-8**: **Countable at 10 and 0**: all ten skills have a non-empty frontmatter `description`, and zero skills retain an in-body `## Activation Triggers` section. **RED**: fewer than ten descriptions, or any surviving triggers section. (This exists because AC-3 is **silently vacuous for four of ten skills** — agent-standards, context-fundamentals, filesystem-context and multi-agent-patterns are not user-triggered and have no CLAUDE.md bullet to enumerate against. Their descriptions derive from their in-body triggers instead, and without this AC an implementer could satisfy AC-3 completely while leaving those four untouched.)
- [ ] **AC-9**: **Review-surface invariant, in the two skills this story owns that carry it.** `.claude/skills/plan/SKILL.md` and `.claude/skills/codex-review/SKILL.md` no longer define the review surface as unstaged working-directory state. Every site is enumerated with a **written verdict**, `no change needed` included. **RED**: any surviving sentence equating unstaged content with the current story's changes, or an enumerated site with no verdict. Known sites, a **floor not the list**: `plan/SKILL.md`'s *"Review the current story's changes via … (unstaged changes = current story)"* — a verbatim instance of the exact retired phrase — and `codex-review/SKILL.md`'s staged/unstaged diff-assembly template plus its *"standalone (non-WORKDIR) staged/unstaged path"* reference in the large-refactor guidance. (⚠️ **Same reason as E-280-04 AC-15**: E-280-07 AC-1c verifies this layer-wide and cannot edit these files. Note this is a **body** edit, unlike the rest of this story — it does not conflict with the line-1 frontmatter work, and both files are already in the Files list.)

## Technical Approach
Enumerate the trigger phrases from CLAUDE.md's Workflows section before editing anything — AC-3 is checkable only against a pre-change enumeration, and reconstructing it from the diff afterwards is the failure mode the repo's 8-of-8 author-detection record predicts.

**FOUR skills are not user-triggered and have no CLAUDE.md Workflows bullet** — `agent-standards`, `context-fundamentals`, `filesystem-context`, `multi-agent-patterns`. They still need frontmatter under AC-1; their `description` states the load condition their consuming agent uses rather than a user phrase, and AC-8 is what keeps them from being silently skipped.

**Do not read "seven bullets" as "seven skills."** CLAUDE.md's Workflows section has seven bullets, but one of them — *Curate the vision* — invokes the product-manager in curate mode and names no skill. So the section covers **six** of the ten skills, not seven. (An earlier draft of this story said three-and-seven; it was wrong in both halves, and the arithmetic is worth re-checking against the file rather than trusting either version.)

Verify the marketplace reference format by reading one of those files rather than taking the shape from this story.

## Dependencies
- **Blocked by**: E-280-02 (both modify `.claude/skills/implement/SKILL.md`; the line-1 frontmatter insert is the safest edit to land last, and the trigger-body removal must see E-280-02's final text)
- **Blocks**: **E-280-07** — its AC-1c verifies layer-wide that the "unstaged = current story" invariant is gone, and AC-9 here removes this story's instances in `plan/SKILL.md` and `codex-review/SKILL.md`. **E-280-08** — its AC-13 requires the five `ratchet` sites in `implement/SKILL.md` to be byte-identical across the finished epic diff, and this story edits that file.

## Files to Create or Modify
- `CLAUDE.md` (modify — the `## Workflows` section)
- `.claude/skills/plan/SKILL.md` (modify)
- `.claude/skills/implement/SKILL.md` (modify)
- `.claude/skills/ingest-endpoint/SKILL.md` (modify)
- `.claude/skills/codex-review/SKILL.md` (modify)
- `.claude/skills/codex-spec-review/SKILL.md` (modify)
- `.claude/skills/workflow-help/SKILL.md` (modify)
- `.claude/skills/agent-standards/SKILL.md` (modify)
- `.claude/skills/filesystem-context/SKILL.md` (modify)
- `.claude/skills/context-fundamentals/SKILL.md` (modify)
- `.claude/skills/multi-agent-patterns/SKILL.md` (modify)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The AC-3 trigger-phrase worklist is committed as an artifact
- [ ] `/workflow-help` cheat sheet checked for consistency with the new single source
- [ ] No regressions in existing tests
