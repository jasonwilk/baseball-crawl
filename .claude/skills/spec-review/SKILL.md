# Skill: spec-review

**Category**: Workflow Automation
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when the user says any of:

- "spec review", "spec review E-NNN", "review the spec"
- "review the spec for E-NNN", "run spec review on E-NNN"
- "codex spec review", "codex review the epic"
- "review E-NNN spec", "check the spec for E-NNN"
- Any request that implies running a spec review on an epic's planning artifacts

---

## Purpose

Automate the two-phase workflow for reviewing an epic's planning artifacts against the project's spec-review rubric. Phase 1 runs the codex spec review script to generate findings. Phase 2 spawns a PM-led review team with relevant domain experts to triage the findings -- deciding which to refine into the epic, which to dismiss, and which to defer.

This formalizes a previously manual process where the PM would optionally request a spec review and then incorporate feedback alone.

---

## Prerequisites

Before executing this workflow, verify:

1. **Identify the target epic.** The user may specify an epic ID (e.g., "E-044") or an epic directory path. If neither is provided, ask the user which epic to review.
2. **The epic directory exists and contains `epic.md`.** Resolve the epic directory:
   - If the user provides an ID like `E-044`, look for a matching directory under `epics/` (e.g., `epics/E-044-workflow-triggers/`).
   - If the user provides a path, use it directly.
   - If no matching directory is found, report the error and stop.
3. **The `epic.md` file exists in the directory.** If missing, this is not a valid epic directory -- report and stop.

---

## Phase 1: Team Lead -- Run Codex Spec Review

**Agent**: Team lead (runs directly -- no delegation needed)
**Time-sensitive**: No

The team lead runs the spec review script and captures its output.

### Steps

1. **Run the script** via Bash. Run this command in the foreground (not as a background task) so output is captured directly:
   ```
   timeout 300 ./scripts/codex-spec-review.sh <epic-dir>
   ```
   Where `<epic-dir>` is the resolved path to the epic directory (e.g., `epics/E-044-workflow-triggers`).

   Codex typically takes 1-2 minutes for a standard epic (3-7 story files). Larger epics may take up to 3 minutes.

2. **Optional `--note` flag**: If the user provided additional context about what to focus on, pass it via `--note "text"`:
   ```
   timeout 300 ./scripts/codex-spec-review.sh <epic-dir> --note "Focus on AC testability"
   ```

3. **Capture the full output.** The script pipes the epic's planning artifacts and rubric into codex and returns findings. Save the complete output for Phase 2.

4. **Check for errors.** If the command exits with a non-zero code, do not proceed to Phase 2:
   - **Exit code 124 (timeout)**: Codex timed out after 5 minutes. Report the timeout to the user and ask how to proceed. Do not retry automatically.
   - **Other non-zero exit codes (script error)**: The script itself failed (codex not installed, invalid directory, missing rubric). Report the specific error message to the user and stop.

---

## Phase 2: PM-Led Review Team -- Triage Findings

**Agent**: product-manager (spawned as a teammate by the team lead)
**Time-sensitive**: No

The team lead spawns the PM as a teammate, providing the codex output and the epic directory path. The PM leads the review from there.

### Instructions for the team lead

Spawn PM with the following context:

```
A codex spec review has been run on epic <EPIC-ID> (directory: <epic-dir>).

The codex findings are below. Your job is to lead a review of these findings:

1. Read the epic and its stories to understand the domain and scope.
2. Determine which domain experts are relevant to this epic (e.g., baseball-coach
   for coaching domain, data-engineer for schema stories, software-engineer for
   implementation stories, api-scout for API-related stories).
3. Spawn the relevant domain experts as teammates.
4. Share the codex findings with the team and lead a triage:
   - REFINE: Finding is valid -- update the affected epic/story files.
   - DISMISS: Finding is not applicable or incorrect -- note why.
   - DEFER: Finding is valid but out of scope -- capture as a note or idea.
5. Update the affected epic and story files with any refinements.
6. Report back with a summary of decisions made.

IMPORTANT: You (PM) own all epic and story file updates. Domain experts provide
input and recommendations but do not modify epic/story files directly.

--- CODEX FINDINGS ---
[Include the full codex output here]
```

### What to do with PM results

When PM completes the review, present the summary to the user:
- Number of findings triaged (refined / dismissed / deferred)
- Key changes made to the epic or stories
- Any deferred items that may need future attention

---

## Workflow Summary

```
User says "spec review E-NNN"
  |
  v
Team lead loads this skill
  |
  v
Resolve epic directory (ask user if ambiguous)
  |
  v
Phase 1: Team lead runs codex-spec-review.sh
  - Passes epic-dir (and optional --note)
  - Captures codex output
  |
  v
[If script error: report to user, stop]
  |
  v
Phase 2: Team lead spawns PM
  - PM reads epic to identify relevant domains
  - PM spawns domain experts as teammates
  - PM leads triage of codex findings
  - PM updates epic/story files as needed
  - PM reports summary of decisions
  |
  v
Team lead presents triage summary to user
```

---

## Edge Cases

### Codex Not Installed
The script checks for `codex` in PATH and exits with a clear error message including install instructions (`npm i -g @openai/codex`). Report this error to the user and stop. Do not attempt to install codex automatically.

### Codex Returns No Findings
If the codex output states "No findings. This epic is ready to mark READY." or similar, report this to the user. Phase 2 is not needed -- there is nothing to triage. The team lead can skip spawning the PM and simply relay the clean result.

### Epic Is Already ACTIVE
An ACTIVE epic may have stories that are IN_PROGRESS or DONE. Review findings may require updates to story files (not just the epic file). The PM should:
- Check each finding against the affected story's status.
- For DONE stories: findings are deferred or captured as follow-up work (do not reopen completed stories without user approval).
- For IN_PROGRESS stories: coordinate with the implementing agent if changes to acceptance criteria are needed.
- For TODO stories: update directly as part of the refinement.

### Epic Is COMPLETED or Archived
If the user requests a spec review on a completed or archived epic, inform them that the epic is no longer active. Ask if they want to proceed anyway (the review may surface learnings but cannot change completed work).

---

## Anti-Patterns

1. **Do not skip Phase 2.** Codex findings are machine-generated and need human judgment. Raw codex output should never be applied directly to epic/story files without PM-led review. Even seemingly obvious suggestions may miss project context.
2. **Do not auto-apply codex suggestions without team review.** The PM and domain experts exist precisely to filter, validate, and contextualize findings. Applying suggestions blindly can introduce errors or misaligned requirements.
3. **Do not let domain experts modify epic/story files directly.** PM owns all file updates during the review. Experts provide input; PM decides and executes changes.
4. **Do not run Phase 2 if Phase 1 produced no findings.** A clean codex result means the spec is ready -- spawning a review team for nothing wastes context and time.
5. **Do not re-run the script repeatedly hoping for different results.** Codex output is deterministic for the same input. If findings seem wrong, bring them to the PM review for triage rather than re-running.
