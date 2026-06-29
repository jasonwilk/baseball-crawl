# Skill: codex-spec-review

**Category**: Workflow Automation
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when the user says any of:

- "spec review", "spec review E-NNN", "review the spec"
- "codex spec review", "codex spec review E-NNN"
- "spec review prompt", "codex spec review prompt", "codex spec review prompt for E-NNN"
- "generate spec review prompt", "generate spec review prompt for E-NNN"
- "review E-NNN spec", "check the spec for E-NNN", "run spec review on E-NNN"
- Any request that implies reviewing an epic's planning artifacts against the spec-review rubric

The word **"spec"** is the mode discriminator. If the user says "codex review" or "code review" without "spec", that is the `codex-review` skill, not this one.

---

## Execution Path Detection

This skill supports two execution paths, detected from the user's trigger phrase:

- **Headless (default)**: The user's phrase does NOT contain "prompt". Claude runs the review via the script, captures output, presents findings, and offers advisory triage.
- **Prompt generation**: The user's phrase CONTAINS "prompt" (e.g., "spec review prompt", "codex spec review prompt for E-NNN"). Claude assembles a lean prompt and presents it in a fenced code block for copy-paste. No execution, no triage.

---

## Prerequisites

Before executing either path, verify:

1. **Identify the target epic.** The user may specify an epic ID (e.g., "E-080") or an epic directory path. If neither is provided, ask the user which epic to review.
2. **Resolve the epic directory.** Check `epics/` first for a matching `E-NNN-*` directory. If not found, check `/.project/archive/`. If found in the archive, note to the user that the epic is archived -- the review may surface learnings but cannot change completed work. Proceed normally.
3. **The epic directory exists and contains `epic.md`.** If the directory does not exist or `epic.md` is missing, report the error and stop.
4. **Check for `.md` files.** If the directory contains no `.md` files, warn the user and stop -- there is nothing to review.
5. **The rubric file exists.** Verify `/workspaces/baseball-crawl/.project/codex-spec-review.md` is present. Do NOT read its contents. If missing, report the error and stop.

---

## Headless Path

### Step 1: Run the script

Run the spec review script via Bash in the foreground:

```
timeout 1200 ./scripts/codex-spec-review.sh <epic-dir>
```

If the user provided additional context, pass it via `--note`:

```
timeout 1200 ./scripts/codex-spec-review.sh <epic-dir> --note "Focus on AC testability"
```

Codex typically takes 1-2 minutes for a standard epic (3-7 story files). Larger epics may take up to 5 minutes.

### Step 2: Handle errors

- **Exit code 124 (timeout)**: Codex timed out after 20 minutes. Report the timeout to the user and ask how to proceed. Do not retry automatically.
- **Other non-zero exit codes**: The script itself failed (codex not installed, invalid directory, missing rubric). Report the specific error message to the user and stop.

### Step 3: Evaluate output

- If the output states "No findings. This epic is ready to mark READY." or similar clean result: report "Clean review -- no findings" to the user. Skip triage. Workflow ends.
- If the output contains findings: present the full Codex findings to the user. Proceed to Step 4.

### Step 4: Offer advisory triage

**Read-receipt gate — REQUIRED. Triage MUST NOT proceed until this is satisfied.**

The headless script streams Codex's output to the Bash tool result, which is truncated to a *preview* when the result is large. Triaging off that preview is the motivating failure mode: in the E-230 dispatch a triage question was fired off a ~2KB preview of a ~373KB persisted Codex result, mischaracterizing four valid findings as "2 LOW already-adjudicated." Before ANY triage tool or action runs against the review result you MUST:

1. **Persist** the full review output to a file (re-run the script redirecting stdout to e.g. `/tmp/codex-spec-review-<epic>.txt`, or save the captured result there). Do NOT rely on the inline Bash preview.
2. **Read the file to completion** and produce a complete digest of every finding (story ID/AC label/the actual claim). Completeness of findings is the objective — account for EVERY finding, not a head/tail sample. You need not hold the raw bytes in context (a very large result would blow the red-zone budget — see `.claude/skills/context-fundamentals/SKILL.md`), but you must process every finding.
3. **Emit a read-receipt derived from the actual file** — its line count (`wc -l <file>`) and its last line (`tail -n 1 <file>`) — before triage begins.

The receipt is a deliberate speed-bump / discipline aid, NOT a cryptographic guarantee (it can in principle be produced without reading the middle), so the binding obligation is the complete finding digest in step 2; the receipt is the forcing function. This gate structurally enforces the always-loaded output-integrity rule (`.claude/rules/tool-output-integrity.md` — never assert or triage content not seen cleanly) and the clean-reread-before-defect discipline (`.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md`); it is the structural form of the read-findings-before-triage lesson.

After the receipt and complete digest are satisfied, offer the user an advisory triage session:

1. Read the Codex findings and identify which domains they touch (schema, implementation, API, coaching, documentation, agent infrastructure, UX).
2. Map those domains to agents from CLAUDE.md's Agent Ecosystem table (ambient context at runtime -- do NOT use a hardcoded roster).
3. The triage team always includes the **product-manager** (PM owns spec work). Other agents are consultative based on the findings' domains.
4. Offer to spawn the triage team. If the user accepts, spawn the relevant agents as named subagents via the `Agent` tool (the triage team forms implicitly on the first spawn). If the user declines, the workflow ends.

**Triage is advisory.** The team assesses findings and recommends action (refine, fix, defer, dismiss) but does NOT implement changes directly. PM owns all epic/story file updates during triage.

---

## Prompt-Generation Path

### Step 1: Resolve the epic directory

Resolve to an absolute path (e.g., `/workspaces/baseball-crawl/epics/E-080-lean-codex-spec-prompt/`). Do NOT read files in the directory -- the prompt gives Codex the directory path.

### Step 2: Assemble the lean prompt

Build the prompt matching the format used by `scripts/codex-spec-review.sh`:

```
SPEC-REVIEW REQUEST

Rubric: /workspaces/baseball-crawl/.project/codex-spec-review.md
Planning artifacts: {absolute epic dir}/ (all *.md files)

Instructions:
1. Read the rubric at the path above.
2. Read all .md files in the planning artifacts directory above.
3. Review the planning artifacts against the rubric. Follow its Evaluation Checklist exactly.
4. Cite story ID and AC label for each finding.
5. If the spec is clean, state: "No findings. This epic is ready to mark READY."
```

If the user provided a runtime note (via `--note` or inline context), include it between the paths and instructions:

```
SPEC-REVIEW REQUEST

Rubric: /workspaces/baseball-crawl/.project/codex-spec-review.md
Planning artifacts: {absolute epic dir}/ (all *.md files)

RUNTIME CONTEXT NOTE FROM PM
{note text}

Instructions:
1. Read the rubric at the path above.
2. Read all .md files in the planning artifacts directory above.
3. Review the planning artifacts against the rubric. Follow its Evaluation Checklist exactly.
4. Cite story ID and AC label for each finding.
5. If the spec is clean, state: "No findings. This epic is ready to mark READY."
```

### Step 3: Present to the user

Present the assembled prompt inside a fenced code block (triple backticks) so the user can copy-paste it directly into Codex.

Do NOT execute the prompt. Do NOT offer triage. Prompt-generation path ends here.

---

## Workflow Summary

```
User says "spec review E-NNN" (or variant)
  |
  v
Load this skill
  |
  v
Detect execution path: "prompt" in phrase? -> prompt-gen, else headless
  |
  v
Resolve epic directory (ask user if ambiguous)
  |
  v
Verify prerequisites (directory exists, epic.md present, .md files exist, rubric exists)
  |
  +---> HEADLESS PATH:
  |       Run codex-spec-review.sh <epic-dir> [--note]
  |       Capture and present findings
  |       No findings? -> Report clean review, stop
  |       Findings? -> Offer advisory triage (PM + domain experts from CLAUDE.md)
  |       User accepts? -> Spawn triage team
  |       User declines? -> Stop
  |
  +---> PROMPT-GEN PATH:
          Assemble lean prompt (request header, rubric path, epic path, optional note, instructions)
          Present in fenced code block
          Stop (no execution, no triage)
```

---

## Edge Cases

### Epic not found
Check `epics/` first, then `/.project/archive/`. If neither location has a matching directory, report the error with the paths checked and stop.

### No `.md` files in the epic directory
If the directory exists but contains no `.md` files, warn the user and stop. There is nothing to review.

### Epic is archived
If found in `/.project/archive/`, note to the user that the epic is archived. Proceed normally -- the review may surface learnings.

### Codex not installed (headless only)
The script checks for `codex` in PATH and exits with an error including install instructions. Report this error to the user and stop.

### Codex returns no findings (headless only)
Report "Clean review -- no findings" to the user. Do not offer triage. There is nothing to triage.

### Rubric file missing
Report the error and stop. Do not attempt to generate a prompt or run the script without the rubric.

---

## Anti-Patterns

1. **Do not hardcode an agent roster in this skill file.** Agent selection for triage uses CLAUDE.md's Agent Ecosystem table at runtime (ambient context). This keeps the roster current without manual sync.
2. **Do not offer triage in the prompt-generation path.** Triage is headless-only. The prompt-gen path assembles and presents -- nothing more.
3. **Do not embed rubric content or planning artifact content.** The skill resolves paths and confirms existence; it does not read or cache file contents.
4. **Do not auto-apply Codex suggestions without team review.** In headless mode, Codex findings are presented for human judgment. Even in triage, the team recommends actions -- they do not implement directly.
5. **Do not add separator walls, "Begin your response with" instructions, or team recommendation blocks to prompts.** The lean format has no ceremony.
