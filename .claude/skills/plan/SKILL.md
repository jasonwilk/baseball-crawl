# Skill: plan

**Category**: Workflow Automation
**Adapted for**: baseball-crawl

---

## Activation Triggers

Load this skill when the user says any of:

- "plan E-NNN", "plan an epic for X", "plan epic for X"
- "create an epic for X", "write stories for X"
- "let's plan X", "design an epic for X"
- Any request that implies creating a new epic with stories

**Compound triggers** (plan then dispatch):

- "plan and dispatch X", "plan and execute X"
- "create an epic and start it", "define and execute X"
- "plan and implement X"

If the user used a compound trigger, set `compound_dispatch = true` for Phase 5 handoff.

**Non-triggers** (do NOT load this skill):

- "spec review E-NNN" -> codex-spec-review skill
- "implement E-NNN" / "start E-NNN" / "dispatch E-NNN" -> implement skill
- "clarify E-NNN" / "refine E-NNN" -> PM clarify mode (no skill needed)
- "triage" -> PM triage mode (no skill needed)

---

## Purpose

Codify Jason's planning workflow (plan -> internal review -> codex validation -> READY) as a repeatable, enforceable process. The main session loads this skill on planning triggers, forms a team with PM and domain experts, guides PM through discovery and planning, automatically chains internal review and codex validation, enforces post-refinement consistency sweeps, and gates the epic at READY (or chains into the implement skill for compound triggers).

This skill owns the planning process (phases, gates, transitions). The PM agent definition owns PM capabilities (quality checklist, consultation triggers). Rules stay where they are (`workflow-discipline.md`, `agent-routing.md`, `agent-team-compliance.md`) -- this skill references them, does not duplicate them. This skill does NOT modify the codex-spec-review skill or the implement skill's core phases.

---

## Prerequisites

Before starting the planning workflow, verify:

1. **The user's request describes a problem or feature to plan.** If the request is too vague (e.g., "plan something" with no domain or feature indication), ask the user to describe what they want to build before proceeding.

2. **Check for existing DRAFT epics.** Scan `/epics/` for directories containing an `epic.md` with `Status: DRAFT`. If a potentially overlapping epic exists (similar domain or feature area), present it to the user and ask: "There is an existing DRAFT epic that may overlap: E-NNN ([title]). Is this a new epic or a continuation of that one?" Wait for the user's answer before proceeding.
   - If continuation: load the existing epic and resume at the appropriate phase (Phase 3 if stories exist, Phase 1 if not).
   - If new epic: proceed with Phase 0.

---

## Phase 0: Team Formation

**Entry condition**: Prerequisites pass; user has described a feature or problem to plan.

### Step 1: Check for explicit agent naming

Before parsing domain signals, check whether the user explicitly named agents in their request (e.g., "plan this with SE and DE", "plan with architect", "get coach and PM on this").

**PM is always included on the planning team**, even if the user does not name PM explicitly. PM is infrastructure for planning (just as PM is infrastructure for dispatch). If the user names agents that do not include PM, add PM automatically.

- **If the user names 2+ agents**: This is a Pattern 1 (Explicit Team Request) per `agent-team-compliance.md`. The named agents (plus PM if not named) override the domain suggestion table entirely. Use `TeamCreate` to create the team and spawn all agents (named agents + PM) using the spawn contexts in Step 4. Skip Steps 2-3 (domain parsing and suggestion are not needed since the user named agents explicitly) and Step 4's `TeamCreate` call (team was already created here in Step 1). Proceed directly to Phase 1.

- **If the user names exactly 1 agent**: This is a Pattern 2 (Explicit Consultation Directive) per `agent-team-compliance.md`. The named agent is added to the team alongside PM. The main session may still suggest additional experts based on domain signals (Steps 2-3), but the named agent is guaranteed.

- **If the user names no agents**: Proceed to Step 2 (domain signal parsing).

### Step 2: Parse domain signals

Scan the user's request for domain keywords and match against the suggestion table:

| Domain Signal | Keywords / Patterns | Suggested Team |
|--------------|-------------------|----------------|
| Database / schema / ETL / migration | "schema", "migration", "ETL", "database", "table", "column" | PM + data-engineer |
| Dashboard / UI / display | "dashboard", "page", "column", "display", "UI", "template" | PM + software-engineer + baseball-coach |
| API / endpoints / crawling | "API", "endpoint", "crawl", "fetch", "GameChanger" | PM + api-scout |
| Agent infra / rules / skills | "agent", "rule", "skill", "hook", "CLAUDE.md", "context layer" | PM + claude-architect |
| Coaching / stats / scouting | "coach", "stat", "scouting", "lineup", "report" | PM + baseball-coach |
| Security / auth / credentials | "auth", "credential", "security", "token", "login" | PM + software-engineer |
| Multi-domain or unclear | No clear single domain | PM + ask user which experts to include |

Keyword matching is case-insensitive. If the request matches multiple domains, combine the suggested agents (e.g., "dashboard with new schema columns" matches Dashboard + Database -> PM + software-engineer + baseball-coach + data-engineer). PM is always included.

If no domain signal matches and the request is not multi-domain, this is the "unclear" row -- ask the user which experts to include rather than guessing.

### Step 3: Suggest team composition

Present the suggested team to the user for confirmation:

> Based on your request, I suggest a planning team of: **PM** + **[suggested experts]**.
> Want to adjust this team? You can add or remove experts before we start.

Wait for the user to confirm or modify. The user may:
- Confirm as-is: proceed to Step 4
- Add experts: include them
- Remove experts: exclude them
- Replace the entire suggestion: honor the replacement

### Step 4: Create the team and spawn agents

Use `TeamCreate` to create the planning team. Spawn all confirmed agents with the appropriate mode:

**PM** -- spawned WITHOUT consultation mode (PM produces artifacts as its normal function):

```
You are the product-manager agent on the [team-name] team. Your role during planning is discovery and epic formation. Operate in discover mode first (Phase 1), then plan mode (Phase 2). Consult domain experts on the team for requirements. Write the DRAFT epic and stories. Run your quality checklist before declaring the epic complete. Do not set the epic to READY -- that happens in Phase 5 after spec review and refinement are complete. Wait for direction from the main session via SendMessage.
```

**Primary-capacity domain experts** (api-scout, baseball-coach, claude-architect) -- spawned WITHOUT consultation mode. These agents produce artifacts as their normal function per `workflow-discipline.md` "When to declare consultation mode" guidance. Spawn context:

```
You are a [agent-type] agent on the [team-name] team for planning epic E-NNN. Provide domain expertise when consulted by PM or the main session. Wait for questions via SendMessage.
```

**Implementing-type domain experts** (software-engineer, data-engineer, docs-writer) -- spawned WITH consultation mode per `workflow-discipline.md` Consultation Mode Constraint. Include the exact activation phrase in the spawn context:

```
You are a [agent-type] agent on the [team-name] team for planning epic E-NNN. Consultation mode: do not create or modify implementation files or planning artifacts. Provide domain expertise when consulted by PM or the main session. Wait for questions via SendMessage.
```

**Exit condition**: Team is created, all agents spawned and ready.

---

## Phase 1: Discovery

**Entry condition**: Team is formed and all agents are ready.

### Step 1: Route to PM in discover mode

Send the user's request to PM via `SendMessage`. PM operates in discover mode:

- Consults domain experts on the team for requirements
- Produces problem statement, constraints, and open questions
- May identify that the scope is too unclear for an epic

### Step 2: Evaluate discovery output

If PM determines scope is too unclear for an epic, PM captures the request as an idea file in `/.project/ideas/` and reports back. The planning workflow ends. Report to the user: "Scope is too unclear for an epic. PM has captured this as an idea for future refinement."

If PM produces a problem statement with sufficient clarity, proceed to Phase 2.

**Exit condition**: PM has a clear problem statement and requirements, or the request has been captured as an idea.

---

## Phase 2: Planning

**Entry condition**: PM has a clear problem statement from Phase 1.

### Step 1: Route to PM in plan mode

Direct PM to write the DRAFT epic and stories with expert input. PM:

- Writes the epic file with goals, success criteria, stories table, and Technical Notes
- Writes individual story files with acceptance criteria, technical approach, and dependencies
- Consults domain experts on the team as needed during planning
- Runs the PM quality checklist (from the PM agent definition)
- Epic status is `DRAFT` at the end of this phase

### Step 2: Confirm planning is complete

PM reports when the DRAFT epic and all stories are written. Confirm with PM that the quality checklist has been run.

**Exit condition**: DRAFT epic and all stories exist with acceptance criteria. PM's quality checklist is complete.

---

## Phase 3: Internal Review Cycle

**Entry condition**: Phase 2 is complete (DRAFT epic with stories exists).

The main session automatically chains this phase after PM completes Phase 2. No separate user command is needed -- the internal review cycle is a built-in step of the planning workflow.

Track the current internal review iteration: `internal_review_iteration` (starts at 1, increments on each loop). Track whether CR was spawned: `cr_spawned` (starts false, set true on first CR spawn -- used in Phase 5 compound dispatch handoff).

### Step 1: CR spec audit (Sub-pass A)

If CR is not already spawned (`cr_spawned = false`), spawn a code-reviewer into the planning team. CR spawn context:

```
You are the code-reviewer agent on the [team-name] team. During planning, you perform spec audits on epic and story files -- not code reviews. Wait for review assignments from the main session via SendMessage. Each assignment will include spec-review criteria and the epic directory path.
```

If spawn succeeds, set `cr_spawned = true`. If spawn fails, leave `cr_spawned = false` and escalate to the user with options: (a) retry spawn, (b) skip CR sub-pass for this iteration (run holistic team review only), (c) abort internal review and advance to Codex (Phase 4) or READY (Phase 5).

Send the spec audit assignment to CR via `SendMessage`:

```
Spec audit for epic E-NNN (internal review iteration [N] of 3):

Epic directory: [absolute path to epic directory]

Review ALL epic and story files against these spec-review criteria:

1. **AC testability and specificity**: Each acceptance criterion must be verifiable by reading the implementation. Flag vague, unmeasurable, or untestable ACs.
2. **Dependency correctness**: Check for file conflicts between stories (multiple stories modifying the same file without acknowledging each other), missing dependencies (story B uses output of story A but doesn't list A as a blocker), and circular dependencies.
3. **Story sizing**: Flag stories that appear to combine multiple unrelated changes or that are too large for a single implementation pass.
4. **Technical Notes completeness**: Verify that Technical Notes referenced by stories actually exist and contain sufficient detail for implementation.
5. **File ownership conflicts**: If two stories list the same file in "Files to Create or Modify", verify they modify different sections or that the dependency chain is correct.
6. **Interface definitions for inter-story dependencies**: When story B depends on story A's output, verify that the interface (function signatures, file formats, schema changes) is defined clearly enough for story B's implementer.

Report each finding with: location (file + section), criterion violated, description, and suggested fix.
```

### Step 2: Holistic team review (Sub-pass B)

Send the epic to each planning team agent (PM and domain experts spawned in Phase 0) asking each to review from their domain perspective. Send via `SendMessage` to each agent:

```
Holistic review for epic E-NNN (internal review iteration [N] of 3):

Epic directory: [absolute path to epic directory]

Review the epic and all story files from your domain perspective. Look for:
- Requirements that are technically infeasible or incorrectly specified
- Missing considerations from your domain expertise
- Inconsistencies between stories that affect your area
- Anything that would cause implementation problems in your domain

Report your findings to PM for triage.
```

**PM-only planning team** (no domain experts beyond PM): Sub-pass B degrades to PM self-review. Send the same review request to PM only, noting that PM should review from the broadest perspective available. Do not broadcast to non-existent agents.

PM collects feedback from all reviewers (CR findings from Step 1 + domain expert findings from Step 2).

### Step 3: Triage findings

Route the CR spec audit findings to PM for triage. PM already has the holistic team review findings (domain experts reported directly to PM in Step 2). Send via `SendMessage`:

```
Internal review findings for triage (iteration [N] of 3):

CR spec audit findings:
[CR findings from Step 1]

Combine these with the holistic team review findings you already received from domain experts in Step 2. For each finding (from both sources):
1. Assess whether it is correct (a real issue in the epic/stories) or incorrect (false positive, misunderstanding, or targets something outside the epic's scope).
2. Consult domain experts on the team as needed for domain-specific findings.
3. Assign a disposition:
   - ACCEPT: Valid finding. You will incorporate the fix.
   - DISMISS: Finding is incorrect. Record the reason (false positive, misunderstanding, out of scope).

Report back with a triage summary: each finding's description, source (CR or team), disposition, and reason.
```

### Step 4: Present triage summary and decide path

Present PM's triage summary to the user. The summary shows each finding with its source, disposition (ACCEPT/DISMISS), and reason.

- If no findings from either sub-pass: Report "Clean internal review -- no findings from CR spec audit or holistic team review." Skip to Step 7 (user decides).
- If all findings are DISMISSED: Report "All findings dismissed -- no changes needed." Skip to Step 7 (user decides).
- If any findings are ACCEPTED: Collect the accepted findings and proceed to Step 5 (incorporation).

### Step 5: PM incorporates findings

Route to PM to incorporate all accepted findings into the epic and story files. Send accepted findings via `SendMessage`:

```
Incorporate these accepted internal review findings into the epic and story files:

[list of accepted findings with their descriptions and sources]

After incorporating each finding, proceed to the consistency sweep (Step 6).
```

### Step 6: Post-incorporation consistency sweep (REQUIRED GATE)

After PM incorporates findings, the main session MUST route PM through the consistency sweep before presenting user options (Step 7). The workflow does NOT advance past this step until PM confirms the sweep is complete and all drift is resolved.

Route to PM via `SendMessage`:

```
Run the post-incorporation consistency sweep. This is a required gate -- you MUST complete all sub-steps before reporting back.

Sub-step A: List every value you changed during incorporation. Include:
- Counts (story counts, AC counts, dependency counts)
- Names (env var names, field names, function names, class names)
- File paths (files to create or modify, referenced paths in ACs or Technical Notes)
- Status categories or enum values
- Any other concrete value that was added, removed, or modified

Sub-step B: For each changed value, grep the epic directory for ALL occurrences:
  grep -rn "<old-value>" <epic-dir>/
  grep -rn "<new-value>" <epic-dir>/

Sub-step C: Verify consistency. For each changed value:
- The OLD value should appear ZERO times (fully replaced).
- The NEW value should appear in every location where it is relevant (epic file, all story files, Technical Notes, Stories table).
- If a value appears in one file but a related reference was not updated in another file, that is drift.

Sub-step D: Fix any drift found. If a fix in one file requires a corresponding update in another (e.g., renaming a file path in a story's "Files to Create or Modify" requires updating the same path in Technical Notes and other stories that reference it), apply BOTH updates before proceeding.

Report back with:
1. List of values changed
2. Grep results for each value (occurrences found)
3. Drift detected? YES/NO
4. If YES: what drift was found and how it was fixed
5. Confirmation: "Consistency sweep complete. All values are consistent across all files."
```

**Gate enforcement**: If PM's report does not include the confirmation phrase or reports unresolved drift, the main session sends PM back to fix the remaining inconsistencies. The main session does NOT present Step 7 options to the user until PM confirms the sweep is clean.

**If PM finds no drift**: Record "Consistency sweep: clean" and proceed to Step 7.

**If PM finds and fixes drift**: Record what was found and fixed, then proceed to Step 7. The fixes are part of the refinement -- no separate review cycle is needed for consistency fixes.

### Step 7: User decides next step

Present the iteration summary to the user (what was reviewed, findings count, triage results, incorporation details if any, consistency sweep results if run). Then present the decision based on iteration count and whether accepted findings existed:

**If `internal_review_iteration < 3`** (circuit breaker not reached):

> Internal review iteration [N] of 3 complete. [Summary of findings/clean status]
> (a) Run another internal review iteration
> (b) Advance to Codex validation (Phase 4)
> (c) Proceed directly to READY (Phase 5) -- skip Codex

- If (a): Increment `internal_review_iteration` and loop back to Step 1.
- If (b): Proceed to Phase 4.
- If (c): Proceed to Phase 5.

**If `internal_review_iteration >= 3` AND accepted findings existed in this iteration** (circuit breaker fires):

> Circuit breaker: 3 internal review iterations completed. Remaining findings from the last iteration:
> [list any unresolved or newly accepted findings]
>
> (a) Fix remaining findings and mark READY (Phase 5)
> (b) Advance to Codex validation (Phase 4)
> (c) Continue refining (resets circuit breaker)
> (d) Leave as DRAFT and stop

- If (a): Route remaining findings to PM for incorporation, run consistency sweep, then proceed to Phase 5.
- If (b): Proceed to Phase 4.
- If (c): Reset `internal_review_iteration = 1` and loop back to Step 1.
- If (d): Report "Epic remains DRAFT. Planning workflow stopped." End the workflow.

**If `internal_review_iteration >= 3` AND no accepted findings** (clean at circuit breaker threshold):

Present the standard options (a/b/c) as above. If the user chooses (a), reset `internal_review_iteration = 1`.

**Exit condition**: User decides to proceed to Phase 4, Phase 5, loop back, or stop.

---

## Phase 4: Codex Validation Pass

**Entry condition**: User chose to advance from Phase 3 (internal review), or loop-back within Phase 4 (user requested re-review after refinement).

Track the current Codex review iteration: `codex_review_iteration` (starts at 1, increments on each loop-back).

### Step 1: Run the codex-spec-review script

Run the spec review script directly via Bash. Do NOT load the codex-spec-review skill -- run the underlying script to avoid skill-nesting complexity:

```
timeout 1200 ./scripts/codex-spec-review.sh <epic-dir>
```

Where `<epic-dir>` is the absolute path to the epic directory (e.g., `/workspaces/baseball-crawl/epics/E-140-planning-skill/`).

Capture the exit code and full output.

### Step 2: Handle the result

- **Exit 0, output contains "No findings"** (or similar clean-review language): Report "Clean Codex review -- no findings." Proceed directly to Phase 5 (READY gate). Skip refinement entirely.

- **Exit 0, output contains findings**: Present the full codex findings to the user. Proceed to Step 3 (triage).

- **Exit 124 (timeout)**: Report to the user: "Codex review timed out after 20 minutes." Ask how to proceed:
  - (a) Generate a spec review prompt for async execution. Assemble the prompt using the prompt-generation format described in `.claude/skills/codex-spec-review/SKILL.md`. Present in a fenced code block. Pause and wait for the user to paste findings back -- if the pasted content contains "No findings" (case-insensitive), skip triage and proceed to Phase 5; otherwise enter Step 3 with the pasted content. The user may also say "skip" (proceed to Phase 5).
  - (b) Skip Codex review and proceed to Phase 5
  - (c) Retry (re-run the script)

- **Other non-zero exit** (codex not installed, script error, API outage): Report the specific error to the user. Ask how to proceed:
  - (a) Generate a spec review prompt for async execution (same as timeout option a -- pasted "No findings" skips triage)
  - (b) Skip Codex review and proceed to Phase 5

### Step 3: Triage findings

Route the findings to PM and domain experts on the team for triage. Send the findings to PM via `SendMessage`:

```
Codex spec review findings for triage (Codex iteration [N] of 2):

[full codex findings]

For each finding:
1. Assess whether it is correct (a real issue in the epic/stories) or incorrect (false positive, misunderstanding, or targets something outside the epic's scope).
2. Consult domain experts on the team as needed for domain-specific findings.
3. Assign a disposition:
   - ACCEPT: Valid finding. You will incorporate the fix.
   - DISMISS: Finding is incorrect. Record the reason (false positive, misunderstanding, out of scope).

Report back with a triage summary: each finding's ID/description, disposition, and reason.
```

PM consults domain experts on the team as needed. PM reports the triage summary.

### Step 4: Present triage summary

Present PM's triage summary to the user. The summary shows each finding with its disposition (ACCEPT/DISMISS) and reason.

- If all findings are DISMISSED: Report "All findings dismissed -- no changes needed." Proceed to Phase 5 (READY gate).
- If any findings are ACCEPTED: Collect the accepted findings and proceed to Step 5 (incorporation).

### Step 5: PM incorporates findings

Route to PM to incorporate all accepted findings into the epic and story files. Send accepted findings via `SendMessage`:

```
Incorporate these accepted Codex spec review findings into the epic and story files:

[list of accepted findings with their descriptions]

After incorporating each finding, proceed to the consistency sweep (Step 6).
```

### Step 6: Post-incorporation consistency sweep (REQUIRED GATE)

After PM incorporates findings, the main session MUST route PM through the consistency sweep before offering the user the re-review/proceed choice (Step 7). The workflow does NOT advance past this step until PM confirms the sweep is complete and all drift is resolved.

Route to PM via `SendMessage` with the same consistency sweep instructions as Phase 3 Step 6.

**Gate enforcement**: Same as Phase 3 Step 6 -- PM must confirm the sweep is clean or be sent back to fix remaining inconsistencies.

### Step 7: User decides next step

Present the refinement summary to the user (what was changed, consistency sweep results). Then present the decision:

**If `codex_review_iteration < 2`** (circuit breaker not reached):

> Codex refinement complete. Codex iteration [N] of 2.
> (a) Re-run Codex spec review on the refined artifacts (loop to Step 1)
> (b) Proceed to READY (Phase 5)

- If (a): Increment `codex_review_iteration` and loop back to Step 1.
- If (b): Proceed to Phase 5.

**If `codex_review_iteration >= 2`** (circuit breaker fires):

> Circuit breaker: 2 Codex iterations completed. Remaining findings from the last review:
> [list any unresolved findings from the most recent iteration]
>
> (a) Fix remaining findings and mark READY anyway
> (b) Continue refining (resets circuit breaker)
> (c) Leave as DRAFT and stop

- If (a): Route remaining findings to PM for incorporation, run consistency sweep, then proceed to Phase 5.
- If (b): Reset `codex_review_iteration = 1` and loop back to Step 1.
- If (c): Report "Epic remains DRAFT. Planning workflow stopped." End the workflow.

**Exit condition**: User decides to proceed to Phase 5, loop back, or stop.

---

## Phase 5: READY Gate

**Entry condition**: Internal review is clean or user chose to proceed, Codex review is clean/skipped/user chose to proceed, or circuit breaker resolved.

### Step 1: PM sets READY and records review scorecard

Route to PM via `SendMessage`:

```
Set the epic status to READY and record the review scorecard.

1. Update the epic status to READY.
2. Add a History entry with the date and a review scorecard table in the epic's History section using this format:

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | N | N | N |
| Internal iteration 1 -- Holistic team | N | N | N |
| Internal iteration 2 -- CR spec audit | N | N | N |
| Codex iteration 1 | N | N | N |
| **Total** | **N** | **N** | **N** |

Only include rows for review passes that actually ran. If Codex was skipped, no Codex rows appear. If an internal iteration had two sub-passes, include a row for each. Reconstruct finding counts from the triage summaries produced during each iteration.
```

### Step 2: Present epic summary

PM presents the epic summary to the user:

- Epic ID and title
- Number of stories with brief descriptions
- Key acceptance criteria
- Domain experts consulted
- Internal review outcome (N iterations, N findings fixed, or skipped)
- Codex review outcome (N iterations, N findings fixed, skipped, or not run)

### Step 2a: Atomic planning commit

Commit all session artifacts produced during planning. This step is the main session's responsibility (git operations per dispatch-pattern.md).

**Preflight**: Run `cd /workspaces/baseball-crawl && git status --porcelain` (without `-uall`). If the output is empty, skip this step silently (already committed or resume scenario) and proceed to Step 3.

**Enumerate session changes**: Use the TN-8 approach to identify all session artifacts:

1. **Recognized artifact paths** (stage these):
   - `epics/E-NNN-slug/` (epic and story files) -- wholly-owned directory, `git add epics/E-NNN-slug/`
   - `.claude/agent-memory/` (agent memory updates) -- mixed directory, enumerate with:
     ```
     git diff --name-only -- .claude/agent-memory/
     git ls-files --others --exclude-standard -- .claude/agent-memory/
     ```
     Stage each matching file individually with `git add <file>`.
   - `docs/vision-signals.md` (if modified) -- single file, `git add docs/vision-signals.md`
   - `.project/research/E-NNN-*` (research artifacts, if any) -- wholly-owned by epic, `git add .project/research/E-NNN-*/`
   - `.project/ideas/` (if any ideas captured) -- mixed directory, enumerate with:
     ```
     git diff --name-only -- .project/ideas/
     git ls-files --others --exclude-standard -- .project/ideas/
     ```
     Stage each matching file individually with `git add <file>`.

2. **Classification**: Files matching recognized patterns above are staged. Files NOT matching any recognized pattern are **unrecognized** -- report them to the user and wait for instructions before proceeding. Do not stage unrecognized files automatically.

**Present staged changes**: After staging recognized files, run `git diff --cached --stat` and present the summary to the user.

**User approval**: Require explicit approval before committing. Only "yes", "commit", "approve", "go ahead" proceed.

**Commit**: `git commit -m "feat(E-NNN): plan <epic title> (READY)"`

**User rejects the commit**: Pause and wait for instructions. The user can:
- (a) Adjust staged files and retry (e.g., unstage something, add something)
- (b) Inspect staged changes (`git diff --cached`)
- (c) Skip the commit entirely

**Compound trigger skip behavior**: If the user chose (c) skip AND `compound_dispatch = true`, downgrade to non-compound behavior: set `compound_dispatch = false`, stop at READY, and report "Epic E-NNN is READY. To dispatch, say 'implement E-NNN'." Do not create the worktree from uncommitted state.

**Ordering with compound dispatch**: For compound triggers, this commit step runs BEFORE Step 3b (worktree creation), ensuring the epic worktree branches from committed state. The step's position between Step 2 and Step 3 naturally satisfies this -- Step 3b is inside the handoff sequence.

### Step 3: Dispatch decision

- **If `compound_dispatch = false`** (standard planning trigger): **STOP.** Report to the user: "Epic E-NNN is READY. To dispatch, say 'implement E-NNN'." The dispatch authorization gate per `workflow-discipline.md` is preserved -- planning and dispatch are separate actions.

- **If `compound_dispatch = true`** (compound trigger like "plan and dispatch"): The compound trigger serves as the user's explicit dispatch authorization per `workflow-discipline.md` Dispatch Authorization Gate. No additional confirmation is needed. Chain into the implement skill via the handoff sequence below.

#### Handoff to implement skill (compound trigger only)

The planning team is already active. The main session transitions it to a dispatch team rather than tearing down and creating fresh. This is the unified team lifecycle.

**Step 3a: Team transition**

Evaluate each agent currently on the planning team:

1. **PM**: Stays on the team. PM transitions from planning role (discover/plan mode) to dispatch role (status management + AC verification). Send PM a role-transition message:

```
Planning is complete. Transitioning to dispatch mode. Your role is now:
- Story status file updates (TODO -> IN_PROGRESS -> DONE)
- Epic Stories table updates
- Epic status transitions (READY -> ACTIVE -> COMPLETED)
- AC verification ("did they build what was specified")
Wait for routing from the main session via SendMessage.
Epic worktree path: [epic-worktree-path]
```

2. **Domain experts who are also implementers** (e.g., software-engineer consulted during planning, software-engineer implements during dispatch): Stay on the team. Transition from consultation mode to implementation mode. Send a mode-transition message:

```
Planning is complete. You are transitioning from consultation to implementation mode. You will receive story assignments from the main session. The consultation mode constraint is lifted -- you may now create and modify implementation files.
```

3. **Domain experts who are NOT implementers** (e.g., baseball-coach consulted but does not implement code): Offer to shut down via `shutdown_request`. These agents have served their planning purpose. If the user prefers to keep them for advisory during dispatch, honor that preference.

4. **Code-reviewer**: If CR was spawned during Phase 3 (`cr_spawned = true`), reuse it -- send a role-transition message transitioning from spec audit to code review:

```
Planning is complete. Transitioning to dispatch mode. Your role is now per-story code review during implementation (not spec audit). Wait for review assignments from the main session via SendMessage. Each review assignment will include a story ID, the full story file text, epic Technical Notes, and the implementer's Files Changed list.
Epic worktree path: [epic-worktree-path]
Review the current story's changes via `cd [epic-worktree-path] && git diff` (unstaged changes = current story).
Review all accumulated changes via `cd [epic-worktree-path] && git diff --cached main` (staged = prior stories).
```

If CR was NOT spawned during Phase 3 (`cr_spawned = false`), spawn fresh using the implement skill's code-reviewer spawn context.

5. **New implementer types**: The implement skill's Phase 2 handoff path is the single owner of spawning any additional agents needed for dispatch that are not already on the team. The plan skill does NOT spawn new implementer types during handoff -- it only transitions existing agents and hands off to the implement skill.

**Step 3b: Create the epic worktree**

Create the epic-level worktree per the implement skill's Phase 2 Step 1:

```bash
git worktree add -b epic/E-NNN /tmp/.worktrees/baseball-crawl-E-NNN
```

**Step 3c: Load the implement skill**

The main session loads the implement skill (`.claude/skills/implement/SKILL.md`). The implement skill detects the handoff (planning team already active) and begins at its Prerequisites check. Since the epic is READY (just set in Step 1), prerequisites pass and dispatch proceeds through the implement skill's phases using the transitioned team.

Set `handoff_from_plan = true` so the implement skill skips team creation (Phase 2 Steps 1-3) and reuses the existing team.

**Exit condition**: Planning workflow is complete (READY and stopped, or handed off to implement skill).

---

## Workflow Summary

```
User says "plan [X]" or "plan and dispatch [X]"
  |
  v
Main session loads this skill
  |
  v
Detect compound trigger? --> set compound_dispatch flag
  |
  v
Prerequisites:
  - User request describes a problem/feature
  - Check /epics/ for existing DRAFT epics (ask if overlap)
  |
  v
Phase 0: Team Formation
  - Parse domain signals from user request
  - Suggest team (PM + domain experts)
  - User confirms or adjusts
  - Create team, spawn agents
  - Implementing-type experts get consultation mode
  - Primary-capacity experts + PM: no consultation mode
  |
  v
Phase 1: Discovery
  - PM in discover mode, consults domain experts
  - Too unclear? --> capture as idea, STOP
  - Clear problem statement? --> proceed
  |
  v
Phase 2: Planning
  - PM in plan mode, writes DRAFT epic + stories
  - Quality checklist run
  - Epic status: DRAFT
  |
  v
Phase 3: Internal Review Cycle  <---------+
  - Spawn CR if not already spawned        |
  - Sub-pass A: CR spec audit              |
  - Sub-pass B: Holistic team review       |
  - PM triages combined findings           |
  - No findings? --> skip to user decides  |
  - Incorporate accepted findings          |
  - Consistency sweep (required gate)      |
  - User decides:                          |
    (a) Another internal iteration --------+
    (b) Advance to Codex --> Phase 4
    (c) Proceed to READY --> Phase 5
    Circuit breaker at 3 iterations:
      adds (d) Leave as DRAFT --> STOP
  |
  v
Phase 4: Codex Validation Pass  <----------+
  - Run: timeout 1200 ./scripts/codex-spec-review.sh
  - Clean? --> skip to Phase 5              |
  - Findings? --> triage (ACCEPT/DISMISS)   |
  - Timeout/error? --> prompt fallback      |
  - Incorporate accepted findings           |
  - Consistency sweep (required gate)       |
  - User decides:                           |
    (a) Re-run Codex ----------loop---------+
    (b) Proceed to READY --> Phase 5
    Circuit breaker at 2 iterations:
      adds (c) Leave as DRAFT --> STOP
  |
  v
Phase 5: READY Gate
  - PM sets epic to READY
  - PM records review scorecard in epic History
  - Present epic summary (internal + Codex outcomes)
  - Atomic planning commit (session artifacts, user approval)
    - Skip silently if no changes
    - Rejection with compound trigger --> downgrade to non-compound
  |
  +---> compound_dispatch = false?
  |       "Epic is READY. Say 'implement E-NNN' to dispatch."
  |       STOP
  |
  +---> compound_dispatch = true?
          Chain into implement skill
          - Team transition (PM stays, experts transition)
          - CR: reuse if spawned in Phase 3, else spawn fresh
          - Implement skill begins at Prerequisites
```

---

## Edge Cases

### User request too vague for an epic
If the user's request lacks sufficient detail to define acceptance criteria, PM captures it as an idea in `/.project/ideas/` rather than forcing an underspecified epic. Report to the user: "This request has been captured as an idea for future refinement. When you have more clarity, we can plan an epic."

### CR spawn failure during Phase 3
If spawning the code-reviewer fails during Phase 3 Step 1, escalate to the user with options:
- (a) Retry spawn
- (b) Skip CR sub-pass for this iteration (run holistic team review only)
- (c) Abort internal review and advance to Codex (Phase 4) or READY (Phase 5)

### PM-only planning team
If no domain experts beyond PM are on the planning team, Sub-pass B (holistic team review) degrades to PM self-review. PM reviews from its broadest perspective without broadcasting to non-existent agents. Sub-pass A (CR spec audit) runs normally.

### No findings on internal review
If both sub-passes (CR spec audit and holistic team review) return no findings, skip incorporation and consistency sweep. Still present tier advancement options to the user (another iteration, advance to Codex, proceed to READY) per TN-3 and TN-6.

### Codex not installed
If the codex-spec-review script fails because `codex` is not in PATH, the script exits with an error including install instructions. Report the error to the user and offer:
- (a) Generate a spec review prompt for async execution (copy-paste into Codex externally)
- (b) Skip Codex review and proceed to Phase 5

### Codex timeout
If the script times out (exit 124) after 20 minutes, report the timeout and offer the same options as "codex not installed" above, plus (c) retry.

### No findings on Codex review
If the Codex spec review returns clean ("No findings"), skip refinement and proceed directly to Phase 5 (READY gate). Do not offer triage -- there is nothing to triage.

### Circuit breaker (Phase 3: 3 iterations, Phase 4: 2 iterations)
Phase 3: If the 3rd internal review iteration still has accepted findings, present circuit breaker options: (a) fix+READY, (b) advance to Codex, (c) continue (reset), (d) leave as DRAFT.
Phase 4: If the 2nd Codex iteration still has accepted findings, present circuit breaker options: (a) fix+READY, (b) continue (reset), (c) leave as DRAFT.

### Existing DRAFT epic overlap
If the prerequisites check finds an existing DRAFT epic that may overlap with the user's request, ask the user before proceeding. Never silently create a duplicate epic.

### User pastes findings from async Codex review
When the user ran the Codex review externally (via a generated prompt) and pastes findings back:
- If the pasted content contains "No findings" (case-insensitive), treat it as a clean review -- report "Clean Codex review -- no findings." and proceed directly to Phase 5 (READY gate), skipping triage. This matches the headless clean path.
- Otherwise, treat the pasted findings identically to headless findings -- enter Phase 4 Step 3 (triage) with the pasted content.

---

## Fidelity Recovery

When a planning agent's output drifts from the inputs it received, apply these rules instead of grinding through in-place corrections:

1. **Respawn on content mismatch.** If an agent's output contradicts relay content that exists in the main-session inbox (e.g., PM writes "no expert input" when expert input was relayed, or PM's epic contradicts a constraint stated in the relay), respawn the agent with a fresh brief rather than re-prompting in place. Content mismatch is a structural signal that the original spawn did not load the relay -- it is not a typo to correct.
2. **Circuit breaker: 2 failures, then escalate.** If a respawn or re-prompt fails to produce faithful output a second time, stop and escalate to the user. Do not attempt a third remediation round in the same loop.
3. **Stop-gate on adjacent regressions.** If a fix for a review finding introduces a new regression in adjacent code (the fix breaks something that was not in the original finding), stop grinding and escalate to the user for a scope decision. Do not continue remediation through the regression.

---

## Anti-Patterns

1. **Do not skip expert consultation when the domain warrants it.** If the user's request involves coaching stats, database schema, or API behavior, the corresponding domain expert should be on the planning team. Suggest them in Phase 0 -- do not plan in a domain vacuum.

2. **Do not auto-dispatch without user authorization.** Unless the user used a compound trigger ("plan and dispatch"), the planning workflow STOPS at Phase 5 after marking READY. The dispatch authorization gate in `workflow-discipline.md` is non-negotiable. Do not chain into the implement skill without explicit dispatch language.

3. **Do not duplicate rule content.** This skill references `workflow-discipline.md`, `agent-routing.md`, and `agent-team-compliance.md` by path. It does not copy their content. If a rule changes, only the rule file needs updating.

4. **Do not nest skill loading.** The plan skill runs the codex-spec-review script directly (`./scripts/codex-spec-review.sh`) in Phase 4 rather than loading the codex-spec-review skill. Skill nesting adds complexity and context overhead with no benefit.

5. **Do not skip the consistency sweep.** After PM incorporates findings in either Phase 3 or Phase 4, the post-incorporation consistency sweep is a required gate. PM must confirm consistency before the workflow proceeds. This applies to both internal review refinement (Phase 3 Step 6) and Codex refinement (Phase 4 Step 6).

6. **Do not implement during planning.** The planning team produces a READY epic with stories. Implementation happens during dispatch (implement skill). Domain experts on the planning team are consultants (implementing-type experts are in consultation mode) -- they advise, they do not build.

7. **Do not tear down the team between planning and dispatch.** When the user uses a compound trigger, the planning team transitions to a dispatch team. PM stays, consultation-mode agents transition, code-reviewer is reused (if spawned during Phase 3) or spawned fresh. The unified team lifecycle preserves expert context across phases.
