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

Generate a lean spec review prompt that the user can copy-paste into Codex. The prompt contains file paths (not file contents), an inlined agent roster table, and review instructions. Codex reads the files itself using its repository access.

This is a **parallel** path to the existing `spec-review` skill (which runs codex in-process via `codex-spec-review.sh`). This skill generates a prompt; that skill executes the review. Both remain available -- the user chooses based on preference.

---

## Prerequisites

Before executing this workflow, verify:

1. **Identify the target epic directory.** If the user specifies an epic ID (e.g., "spec review prompt for E-074"), resolve it to the epic directory under `epics/` (e.g., `epics/E-074-codex-prompt-generator/`). If no epic is specified, ask the user which epic to generate a prompt for.
2. **The epic directory exists and contains `epic.md`.** Check `epics/` first, then `/.project/archive/` if not found. If neither location has it, report the error and stop.
3. **The rubric file exists.** Verify `/workspaces/baseball-crawl/.project/codex-spec-review.md` is present. If missing, report the error and stop.

---

## Workflow

### Step 1: Resolve the epic directory path

Resolve the epic directory to an absolute path (e.g., `/workspaces/baseball-crawl/epics/E-080-lean-codex-spec-prompt/`). Confirm the directory exists and contains `epic.md`.

Do NOT Glob or Read individual files in the directory. The prompt will give Codex the directory path and let it read the files itself.

### Step 2: Confirm the rubric file exists

Confirm that `/workspaces/baseball-crawl/.project/codex-spec-review.md` exists.

Do NOT Read its contents. The prompt will give Codex the rubric path and let it read the file itself.

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

Build the complete prompt by combining paths, the roster, and instructions:

```
======================================================================
SPEC REVIEW REQUEST
======================================================================

Review the planning artifacts in the epic directory below against the
spec-review rubric. Read both locations yourself -- do not ask for
their contents.

Rubric: {absolute rubric path}
Epic directory: {absolute epic directory path}

Read all .md files in the epic directory (top level only, no
subdirectories). Evaluate them against the rubric.

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
Step 1: Resolve epic directory to absolute path (no file reads)
  |
  v
Step 2: Confirm rubric file exists (no file reads)
  |
  v
Step 3: Verify agent roster against CLAUDE.md Agent Ecosystem
  |
  v
Step 4: Assemble prompt (paths + roster + instructions)
  |
  v
Step 5: Present in fenced code block for copy-paste
```

---

## Edge Cases

### Epic directory not found
If the epic ID does not match any directory under `epics/` or `/.project/archive/`, report the error with the paths checked and stop. Do not guess or create a directory.

### No `.md` files in the epic directory
If the directory exists but contains no `.md` files (verified by a quick Glob check), report this to the user and stop. An epic directory with no `.md` files has nothing to review.

### Scratch or draft files in the directory
Epic directories may contain scratch files, draft notes, or work-in-progress artifacts alongside the canonical epic and story files. Note to the user that the PM should clean up the directory before review if non-canonical files are present -- Codex will read all `.md` files in the directory.

### Stories referencing external documents
The generated prompt scopes Codex to the epic directory and the rubric file. Stories may reference external documents (stat glossary, API specs, architecture docs) that are outside the epic directory. If the user knows that referenced external documents are critical for a thorough review, they may need to add those paths to the prompt manually before pasting into Codex.

### Epic is archived
If the epic is found in `/.project/archive/` rather than `epics/`, proceed normally. Note to the user that the epic is archived -- the review may surface learnings but cannot change completed work.

---

## Anti-Patterns

1. **Do not execute the prompt.** This skill generates a prompt for the user to copy-paste into Codex manually. Do not run it through codex, do not spawn agents to review it, do not pipe it to any tool.
2. **Do not modify the rubric file.** The rubric at `.project/codex-spec-review.md` is a shared project artifact. Read it; never edit it as part of this workflow.
3. **Do not embed rubric content or planning artifact content in this skill file.** The skill resolves paths and confirms existence; it does not read or cache file contents. Embedding would create stale copies that diverge from the source files.
4. **Do not expand the prompt's file-read scope.** Keep the prompt scoped to the epic directory and rubric path. Do not add extra paths for externally referenced documents -- if the user needs those included, they add the paths manually.
5. **Do not dynamically read agent definition files.** The roster table is static and verified against CLAUDE.md (ambient context). Reading 9 agent files at execution time wastes context for information that rarely changes.
