# Skill: review-epic

**Category**: Workflow Automation
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when the user says any of:

- "review epic", "review epic E-NNN"
- "codex review epic", "codex review epic E-NNN"
- "post-dev review", "post-dev review E-NNN"
- "code review epic", "code review epic E-NNN"
- "review the epic", "run a review on E-NNN"
- Any request that implies running a codex code review on an epic's implementation changes

---

## Purpose

Run a codex code review on an epic's implementation changes, then spawn the implementing team to review findings together. Fixes are applied by the appropriate implementing agent. The PM tracks which findings are addressed, dismissed, or deferred and documents deferred findings in the epic.

This is a **post-dev** review -- it reviews code that has been written. It is distinct from "spec review" (pre-implementation review of epic/story specifications).

---

## Prerequisites

Before executing this workflow, verify:

1. **Identify the target epic.** If the user specifies an epic ID (e.g., "review epic E-042"), use it. If no epic ID is specified, ask the user which epic to review.
2. **The epic exists.** Check `/epics/E-NNN-slug/` first, then `/.project/archive/E-NNN-slug/` if not found. If the epic does not exist in either location, report the error and stop.
3. **Implementation is meaningfully complete.** All stories should be DONE, or the user has explicitly requested a mid-implementation review (incremental reviews are valid -- a few stories DONE is sufficient if the user asks for it). If no stories are DONE, warn the user that there is nothing meaningful to review and ask whether to proceed.

---

## Phase 1: Team Lead -- Run Codex Code Review

**Agent**: Team lead (you -- the agent executing this skill)
**Time-sensitive**: No

### Determine the review mode

The default mode is `uncommitted` -- this reviews all staged, unstaged, and untracked changes in the working tree. This is the right choice when the epic's changes have not yet been committed.

If the user specifies a different mode, use it:
- "review epic E-042 against main" or "review epic E-042 base main" -> `base main`
- "review epic E-042 commit abc1234" -> `commit abc1234`

If the epic's changes have already been committed but not merged, `base main` is typically more appropriate than `uncommitted`.

### Execute the review

Run the codex review script via Bash:

```
./scripts/codex-review.sh <mode> [args]
```

Examples:
- `./scripts/codex-review.sh uncommitted`
- `./scripts/codex-review.sh base main`
- `./scripts/codex-review.sh commit abc1234`

Capture the full output. This is the codex findings report that the team will review in Phase 2.

### Evaluate the output

- If the script reports **"No uncommitted changes to review"** or **"No diff against..."**: Report this to the user and stop. There is nothing to review.
- If the script reports **"No findings."**: Report "Codex review completed with no findings" to the user. No team review is needed -- stop the workflow.
- If the script reports findings: Proceed to Phase 2.

---

## Phase 2: Team Review of Codex Findings

**Agents**: Team lead (spawner) + PM (coordinator) + implementing agents
**Time-sensitive**: No

### Step 1: Determine team composition

Read the epic's `## Dispatch Team` section. If present and non-empty, note the listed agents. If absent or empty, determine agents from the epic's stories using the Agent Selection table in `/.claude/rules/dispatch-pattern.md`.

### Step 2: Create team and spawn all agents

Create the team (`TeamCreate`) and spawn PM + all implementing agents.

**Context block for PM:**

```
POST-DEV REVIEW: The user requested a codex code review of epic E-NNN.

EPIC ID: E-NNN
EPIC DIRECTORY: /epics/E-NNN-slug/ (or /.project/archive/E-NNN-slug/ if archived)

Teammates spawned: [list of agent types spawned alongside PM]

CODEX FINDINGS:
[Paste the full codex output here]

INSTRUCTIONS:
1. The team lead has spawned implementing agents alongside you. Assign review tasks
   to them via SendMessage.

2. Provide each implementing agent with:
   - The full codex findings
   - The epic ID and directory path
   - Their role: review findings relevant to their domain, propose fixes or
     dismissals with rationale for each finding

3. Coordinate the review:
   - Each implementing agent reviews findings in their domain and either:
     (a) Applies a fix (code change)
     (b) Recommends dismissal with rationale (false positive, acceptable tradeoff, etc.)
     (c) Recommends deferral with rationale (valid finding but out of scope for this epic)
   - You (PM) track the disposition of every finding: fixed, dismissed, or deferred.
   - Implementing agents apply code fixes. PM does NOT implement fixes.

4. After all findings are reviewed:
   - Document deferred findings in the epic's Technical Notes or History section
     (include the finding description, rationale for deferral, and any follow-up
     epic/idea reference if applicable).
   - Report the summary back: how many findings were fixed, dismissed, and deferred.
```

**Context block for each implementing agent:**

```
You are [agent-type] on a review team for epic E-NNN.
Epic directory: /epics/E-NNN-slug/ (or /.project/archive/E-NNN-slug/ if archived)

CODEX FINDINGS:
[Paste the full codex output here]

The PM (product-manager) will assign your review tasks via messaging. Wait for the PM's instructions before starting work.
```

### Step 3: Remain available

After spawning all agents, the team lead remains available for additional spawn requests from PM (e.g., if PM identifies findings that need a different agent type).

### What to do with review results

When PM reports the review summary, present it to the user:
- Number of findings fixed, dismissed, and deferred
- Brief description of any deferred findings
- Any follow-up work identified

---

## Workflow Summary

```
User says "review epic E-NNN"
  |
  v
Team lead loads this skill
  |
  v
Verify prerequisites (epic exists, stories DONE or user override)
  |
  v
Phase 1: Team lead runs codex-review.sh
  - Determine mode (default: uncommitted)
  - Execute script, capture output
  |
  +---> No changes to review? -> Report and stop.
  +---> No findings? -> Report "clean review" and stop.
  |
  v
Phase 2: Team lead spawns PM + implementing agents
  - PM coordinates review via messaging
  - Team reviews each finding: fix, dismiss, or defer
  - Implementing agents apply fixes
  - PM tracks dispositions
  - PM documents deferred findings in epic
  - Team lead remains available for additional spawn requests
  |
  v
Team lead presents review summary to user
```

---

## Edge Cases

### Codex not installed
The script checks for `codex` in PATH and exits with an error message if not found. Relay the error to the user: "codex is not installed. Install with: `npm i -g @openai/codex`".

### Codex returns no findings
"No findings" is a valid and good result. Report it to the user and end the workflow. Do not spawn a review team when there is nothing to review.

### No uncommitted changes
The script exits cleanly with "No uncommitted changes to review." Report this to the user. Suggest using `base main` mode if the epic's changes were already committed.

### Epic is already archived
Read the epic from `/.project/archive/E-NNN-slug/` instead of `/epics/E-NNN-slug/`. The workflow proceeds identically -- the archive location does not change how the review works.

### Mid-implementation review
The user may request a review before all stories are DONE. This is valid -- incremental reviews catch issues early. Proceed normally but note in the PM context block that this is a partial review.

### Very large codex output
If the codex output is extremely long (exceeding reasonable context limits), summarize the finding categories and counts for the PM context block, but provide the full output in a file (e.g., write to a temporary location) and reference it.

---

## Anti-Patterns

1. **Do not auto-apply codex suggestions without team review.** Codex findings are recommendations, not commands. Every finding must be reviewed by the implementing team before any code change is made. The team decides fix, dismiss, or defer.
2. **Do not run review before implementation is meaningfully complete.** A few stories DONE is fine for an incremental review, but the primary use case is post-epic. Do not trigger this workflow on an epic where no implementation work has started.
3. **Do not conflate "review epic" with "spec review."** They serve different purposes. "Review epic" is a post-dev code review (reviews implementation). "Spec review" is a pre-dev specification review (reviews epic/story design). If the user says "spec review", load the spec-review skill instead.
4. **Do not run both phases in parallel.** Phase 2 depends on Phase 1's output. Wait for the codex review to complete before spawning the review team.
5. **Do not skip documenting deferred findings.** If a finding is valid but deferred, it must be recorded in the epic's Technical Notes or History so it is not lost.
