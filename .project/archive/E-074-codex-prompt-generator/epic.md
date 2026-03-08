# E-074: Codex Review Prompt Generator Skill

## Status
`COMPLETED`

## Overview
Add two new workflow skills that generate self-contained review prompts the user can copy-paste into Codex, as an alternative to piping through the existing `codex-review.sh` and `codex-spec-review.sh` scripts. One skill generates code review prompts (diff + rubric), the other generates spec review prompts (epic/story files + rubric). Both include agent team instructions so Codex can recommend collaborative triage.

## Background & Context
The project has two existing codex review workflows:
- **Code review** (`review-epic` skill + `codex-review.sh` script): Runs codex in-process, then spawns a team to triage findings.
- **Spec review** (`spec-review` skill + `codex-spec-review.sh` script): Runs codex in-process, then spawns PM + domain experts to triage.

Both workflows pipe context to codex programmatically. Sometimes the user prefers to interact with Codex directly -- pasting a prompt manually rather than running it through the pipeline. This epic adds that parallel path via two separate skills, following the same split pattern as the existing `review-epic` / `spec-review` skill pair.

**Expert consultation completed:**
- **claude-architect**: Two separate skill directories (not one combined file) -- different inputs, rubrics, triggers, and output structures warrant separation. Two separate CLAUDE.md Workflows entries (one skill = one entry). Rubric files read at execution time. Static agent roster table in the prompt template (not dynamic reads of agent definition files) -- Codex only needs names and one-line roles, and the roster changes rarely. Claude verifies the table against the CLAUDE.md Agent Ecosystem section before assembling.
- **software-engineer**: Git diff commands replicated via Bash (same modes as codex-review.sh). Spec files gathered via Glob + Read. Untracked files gap: the existing script only lists untracked file names without contents -- the skill should read and include full untracked file contents. Three-tier size thresholds: under 5,000 lines proceed normally, 5,000-10,000 lines warn user, over 10,000 lines refuse and suggest mitigations. Size estimated BEFORE assembling. Spec review edge cases: epic dirs may contain scratch/draft files; stories referencing external docs will not be auto-included.

## Goals
- User can say "codex review prompt" and get a complete, copy-pasteable prompt containing the diff, code review rubric, and agent team instructions
- User can say "codex spec review prompt" and get a complete, copy-pasteable prompt containing the epic/story files, spec review rubric, and agent team instructions
- The generated prompts are self-contained -- Codex needs nothing beyond the pasted prompt
- Existing scripts and skills remain unchanged

## Non-Goals
- Modifying the existing `codex-review.sh` or `codex-spec-review.sh` scripts
- Modifying the existing `review-epic` or `spec-review` skills
- Automating the Codex interaction (the whole point is manual copy-paste)
- Building a new script -- these are skills (Claude assembles the prompt using its tools)

## Success Criteria
- A skill file exists at `.claude/skills/codex-prompt-code/SKILL.md` for code review prompt generation
- A skill file exists at `.claude/skills/codex-prompt-spec/SKILL.md` for spec review prompt generation
- CLAUDE.md Workflows section includes two new entries (one per skill)
- The generated code review prompt includes: the relevant diff (with full untracked file contents), the full code review rubric, and instructions for Codex to start an agent team
- The generated spec review prompt includes: the full epic/story markdown content, the full spec review rubric, and instructions for Codex to start an agent team
- Both prompts instruct Codex to begin its response with "This is peer feedback from Codex"
- Both prompts include a static agent roster table (name + role) for team composition
- Code review prompt handles size thresholds (warn at 5,000-10,000 lines, refuse over 10,000 lines)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-074-01 | Code Review Prompt Skill | DONE | None | claude-architect |
| E-074-02 | Spec Review Prompt Skill | DONE | None | claude-architect |
| E-074-03 | CLAUDE.md Workflows Entries | DONE | E-074-01, E-074-02 | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### Skill Architecture
Two separate skill files following the existing `review-epic` / `spec-review` precedent:
1. `.claude/skills/codex-prompt-code/SKILL.md` -- code review prompt generation
2. `.claude/skills/codex-prompt-spec/SKILL.md` -- spec review prompt generation

Rationale: different inputs (git diff vs. epic files), different rubrics, different trigger phrases, different output structure (diff modes vs. epic directory targeting). A combined file would need conditional branching throughout.

### Agent Roster in Generated Prompts
The prompts include a **static roster table** (agent name + one-line role description) rather than dynamically reading `.claude/agents/*.md` files at execution time. Rationale: Codex only needs names and roles to recommend a team -- full agent definitions are unnecessary context. The roster changes rarely (currently 8 agents).

The skill instructions tell Claude to verify the embedded roster table against the CLAUDE.md Agent Ecosystem section (which is already ambient context) before assembling, and update the table if agents have been added or removed. This is one lightweight check vs. 8 file reads.

### Diff Modes (Code Review Skill)
Support the same modes as `codex-review.sh`:
- `uncommitted` (default): staged + unstaged + untracked changes
- `base <branch>`: diff against a specified base branch
- `commit <sha>`: diff of a specific commit

**Untracked file content**: The existing `codex-review.sh` only lists untracked file names (`git ls-files --others`). The skill closes this gap by instructing Claude to detect untracked files and use Read to include their full contents with `--- FILE: path ---` headers.

### Size Thresholds (Code Review Skill)
Three tiers, computed BEFORE assembling the full prompt:
- Under 5,000 lines: proceed normally
- 5,000-10,000 lines (inclusive): warn the user in a preamble, include a size estimate, but still assemble the prompt
- Over 10,000 lines: refuse to assemble. Suggest mitigations (narrower scope, specific files, split PRs)

The size estimate is computed first (count diff lines + untracked file lines) so Claude avoids building a huge string only to discard it.

### Content Gathering (Spec Review Skill)
- Use Glob to find `*.md` files in the epic directory
- Use Read to gather each file's content
- Include all files in the prompt output

**Edge cases**: Epic directories may contain scratch or draft files -- the skill should note that PM should clean up the directory before review. Stories that reference external docs (stat glossary, API specs) will not be auto-included -- the skill should note the user may need to append those manually.

### Rubric Files (referenced, not embedded)
- Code review: `/workspaces/baseball-crawl/.project/codex-review.md`
- Spec review: `/workspaces/baseball-crawl/.project/codex-spec-review.md`

### Prompt Structure (both variants)
The generated prompt that the user copy-pastes into Codex must include:
1. The review content (diff or spec files)
2. The full rubric text (read from the rubric file at execution time)
3. A static agent roster table (agent name + one-line role)
4. Instructions telling Codex to:
   - Begin its response with "This is peer feedback from Codex"
   - Recommend starting a team of agents including PM and relevant domain experts (using the embedded static roster table to identify relevant experts)
   - Have the subject matter experts and PM decide together which feedback to refine into the epic, which code to fix, and which to defer

### Relationship to Existing Workflows
This is a **parallel** path, not a replacement. The existing skills (`review-epic`, `spec-review`) and scripts (`codex-review.sh`, `codex-spec-review.sh`) remain unchanged. These skills output a prompt; those skills execute the review.

## Open Questions
None -- all questions resolved via expert consultation.

## History
- 2026-03-08: Created with incorrect consultation answers (fabricated by the relay, not from actual agents). Initial version had single combined skill file, single CLAUDE.md entry, dynamic agent roster reads, no size thresholds, no untracked file content inclusion.
- 2026-03-08: Corrected after real expert consultation. Split to two skill directories (architect recommendation), two CLAUDE.md entries, static roster table, three-tier size thresholds, untracked file content gap closure, spec review edge cases. Story count changed from 2 to 3.
- 2026-03-08: Codex spec review triage. 6 findings: 4 REFINE (trigger phrases enumerated, size boundary exact, format reference concrete, skill-to-Workflows claim narrowed), 1 DEFER (stale spec-review skill -- caveat added to story 02), 1 DISMISS (standard DoD items). Follow-up noted: spec-review SKILL.md needs update to current dispatch model (pre-E-065 team-spawning language) -- not E-074 scope.
- 2026-03-08: COMPLETED. All 3 stories implemented by claude-architect. Two new skill files created (codex-prompt-code, codex-prompt-spec) and two CLAUDE.md Workflows entries added. All stories context-layer-only, verified directly by main session. Documentation assessment: no documentation impact (internal workflow skills only). Context-layer assessment: (1) New convention: no. (2) Architectural decision: no. (3) Footgun/boundary: no. (4) Agent behavior change: no. (5) Domain knowledge: no. (6) New skill/workflow: yes -- already codified by E-074-03 (CLAUDE.md Workflows entries added). No additional codification needed.
