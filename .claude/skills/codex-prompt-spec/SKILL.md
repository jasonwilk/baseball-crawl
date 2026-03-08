# Skill: codex-prompt-spec

**Category**: Workflow Automation
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when the user says any of:

- "codex spec review prompt", "codex spec review prompt for E-NNN"
- "generate codex spec review prompt", "generate codex spec review prompt for E-NNN"
- "spec review prompt for E-NNN"
- "build me a spec review prompt", "build me a spec review prompt for E-NNN"
- Any request to generate a copy-paste spec review prompt for Codex

The keyword "spec" is the discriminator. If the user says "codex review prompt" (no "spec"), that is the code review prompt skill (`codex-prompt-code`), not this one.

---

## Purpose

Generate a self-contained spec review prompt that the user can copy-paste into Codex. The prompt includes the full content of all epic/story markdown files, the spec review rubric, a static agent roster table, and instructions for Codex to recommend a collaborative triage team.

This is a **parallel** path to the existing `spec-review` skill (which runs codex in-process via `codex-spec-review.sh`). This skill generates a prompt; that skill executes the review. Both remain available -- the user chooses based on preference.

---

## Prerequisites

Before executing this workflow, verify:

1. **Identify the target epic directory.** If the user specifies an epic ID (e.g., "spec review prompt for E-074"), resolve it to the epic directory under `epics/` (e.g., `epics/E-074-codex-prompt-generator/`). If no epic is specified, ask the user which epic to generate a prompt for.
2. **The epic directory exists and contains `epic.md`.** Check `epics/` first, then `/.project/archive/` if not found. If neither location has it, report the error and stop.
3. **The rubric file exists.** Verify `/workspaces/baseball-crawl/.project/codex-spec-review.md` is present. If missing, report the error and stop.

---

## Workflow

### Step 1: Gather epic/story file contents

Use Glob to find all `*.md` files in the epic directory (top level only -- no recursive descent into subdirectories).

Use Read to gather the full content of each file. Preserve the filename in the assembled output using `--- FILE: {filename} ---` headers.

### Step 2: Read the rubric

Use Read to load the full content of `/workspaces/baseball-crawl/.project/codex-spec-review.md`. This is the spec review rubric that Codex will evaluate the planning artifacts against.

Do NOT embed the rubric content in this skill file. Always read it fresh at execution time so the prompt reflects the current rubric.

### Step 3: Verify the agent roster

Before assembling, compare the static roster table below against the CLAUDE.md Agent Ecosystem section (already in your ambient context). If agents have been added, removed, or renamed since this skill was written, update the table in the assembled prompt to match current reality.

**Static agent roster table (current as of skill creation):**

| Agent | Role |
|-------|------|
| claude-architect | Designs and manages agents, CLAUDE.md, rules, skills |
| product-manager (PM) | Owns what to build, why, and in what order |
| baseball-coach (coach) | Domain expert -- translates coaching needs into technical requirements |
| api-scout | Explores GameChanger API, maintains API spec, manages credential patterns |
| data-engineer (DE) | Database schema design, ETL pipelines, SQLite architecture |
| software-engineer (SE) | Python implementation, testing, general coding work |
| docs-writer | Documentation specialist for admin/developer and coaching staff audiences |
| ux-designer | UX/interface designer for coaching dashboard and UI work |
| code-reviewer | Adversarial code reviewer -- verifies ACs and code quality before stories are marked DONE |

### Step 4: Assemble the prompt

Build the complete prompt by combining the gathered content in the following order:

```
======================================================================
SPEC-REVIEW RUBRIC
======================================================================
{Full rubric content from .project/codex-spec-review.md}

======================================================================
PLANNING ARTIFACTS TO REVIEW (epic directory: {epic-dir})
======================================================================

--- FILE: {filename1} ---
{Full content of file 1}

--- FILE: {filename2} ---
{Full content of file 2}

... (all .md files in the epic directory)

======================================================================
AGENT ROSTER (for team composition recommendations)
======================================================================
| Agent | Role |
|-------|------|
{Verified roster table rows}

======================================================================
REVIEW INSTRUCTIONS
======================================================================
Begin your response with "This is peer feedback from Codex".

Review the planning artifacts above against the spec-review rubric.
Follow the rubric's Evaluation Checklist exactly.
Cite story ID and AC label for each finding.
If the spec is clean, state: "No findings. This epic is ready to mark READY."

After presenting your findings, recommend starting a team of agents
to triage them. The team should include the product-manager (PM)
and relevant domain experts from the agent roster above -- choose
experts whose domain overlaps with the epic's subject matter.

The subject matter experts and PM should decide together which
feedback to refine into the epic, which to fix, and which to defer.
```

### Step 5: Present to the user

Present the assembled prompt inside a fenced code block (triple backticks) so the user can copy-paste it directly into Codex.

Do NOT execute the prompt. Do NOT send it to Codex. The entire purpose of this skill is to generate and present the prompt for the user to use manually.

---

## Workflow Summary

```
User says "codex spec review prompt for E-NNN"
  |
  v
Load this skill
  |
  v
Resolve epic directory (ask user if ambiguous)
  |
  v
Verify prerequisites (directory exists, epic.md present, rubric exists)
  |
  v
Step 1: Glob *.md in epic dir, Read each file
  |
  v
Step 2: Read rubric from .project/codex-spec-review.md
  |
  v
Step 3: Verify agent roster against CLAUDE.md Agent Ecosystem
  |
  v
Step 4: Assemble prompt (rubric + files + roster + instructions)
  |
  v
Step 5: Present in fenced code block for copy-paste
```

---

## Edge Cases

### Epic directory not found
If the epic ID does not match any directory under `epics/` or `/.project/archive/`, report the error with the paths checked and stop. Do not guess or create a directory.

### No `.md` files in the epic directory
If Glob returns no markdown files, report this to the user and stop. An epic directory with no `.md` files has nothing to review.

### Scratch or draft files in the directory
Epic directories may contain scratch files, draft notes, or work-in-progress artifacts alongside the canonical epic and story files. Note to the user that the PM should clean up the directory before review if non-canonical files are present -- all `.md` files in the directory will be included in the prompt.

### Stories referencing external documents
Stories may reference external documents (stat glossary, API specs, architecture docs) that are outside the epic directory. These will NOT be auto-included in the generated prompt. Note to the user that they may need to manually append referenced external documents to the prompt if Codex needs that context for a thorough review.

### Epic is archived
If the epic is found in `/.project/archive/` rather than `epics/`, proceed normally. Note to the user that the epic is archived -- the review may surface learnings but cannot change completed work.

---

## Anti-Patterns

1. **Do not execute the prompt.** This skill generates a prompt for the user to copy-paste into Codex manually. Do not run it through codex, do not spawn agents to review it, do not pipe it to any tool.
2. **Do not modify the rubric file.** The rubric at `.project/codex-spec-review.md` is a shared project artifact. Read it; never edit it as part of this workflow.
3. **Do not embed rubric content in this skill file.** The rubric is read fresh at execution time so the generated prompt always reflects the current rubric. Embedding would create a stale copy.
4. **Do not auto-include external referenced documents.** Keep scope to the epic directory's `.md` files. If stories reference external docs, note this to the user rather than crawling the repo for referenced files.
