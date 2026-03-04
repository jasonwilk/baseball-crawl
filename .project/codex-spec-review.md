# Spec-Review Rubric for baseball-crawl

## Setup

Before reviewing, read these workflow context files:
1. `/workspaces/baseball-crawl/CLAUDE.md` -- project principles, tech stack, agent ecosystem, workflow conventions
2. `/workspaces/baseball-crawl/.claude/rules/workflow-discipline.md` -- READY gate, work authorization gate, PM task types
3. `/workspaces/baseball-crawl/.claude/rules/dispatch-pattern.md` -- how stories are dispatched, PM responsibilities, agent routing table
4. `/workspaces/baseball-crawl/.claude/agents/product-manager.md` -- PM agent definition, refinement workflow, quality checklist

This is a **planning artifact review**, not a code review. Evaluate the epic and story files provided against the project's workflow contracts and planning quality standards.

## Evaluation Checklist

For every story in the epic, check each item and report findings:

### 1. Acceptance-Criteria Clarity and Testability
- Are all ACs specific enough that an implementing agent could verify them without guessing?
- Can each AC be confirmed with a concrete, observable test (file exists, command exits 0, output contains X)?
- Are any ACs ambiguous, subjective, or dependent on unstated context?

### 2. Dependency Correctness and Sequencing
- Are all `Blocked by` / `Blocks` relationships explicitly stated in each story file?
- Do the dependencies reflect the actual data flow and file modification order?
- Are there hidden dependencies not captured in the dependency fields (e.g., story A must read output from story B)?
- Does the epic's Stories table match the dependency graph in individual story files?

### 3. File-Conflict and Parallel-Execution Risks
- Do any two stories marked as parallel-safe modify the same file?
- If parallel execution is claimed, verify that "Files to Create or Modify" lists do not overlap.
- Are there implicit ordering requirements (e.g., story A creates a file that story B reads) that make them not truly parallel-safe?

### 4. Story Sizing and Vertical Slicing
- Is each story independently deliverable and testable end-to-end?
- Are any stories too large -- spanning multiple domains, producing artifacts that can't be verified until a later story completes?
- Are any stories too small -- trivially contained in a neighboring story with no benefit to splitting?
- Does each story deliver clear, standalone value?

### 5. Agent-Routing Correctness
- Per the routing table in `dispatch-pattern.md`: context-layer files (CLAUDE.md, `.claude/agents/*.md`, `.claude/rules/*.md`, `.claude/skills/**`, `.claude/hooks/**`, `.claude/settings.json`, `.claude/agent-memory/**`) must route to `claude-architect`.
- Python implementation, crawlers, parsers, tests, utility scripts route to `software-engineer`.
- Database schema, SQL migrations, ETL route to a data-engineer-roled agent.
- Are any stories routed to the wrong agent type given their "Files to Create or Modify"?

### 6. Mismatch Between Epic Claims and Current Repo Reality
- Does the epic's Background or Context section describe things that are already done but framed as future?
- Does the epic describe dependencies as "will be created" when they already exist in the repo?
- Are there AC items that are already satisfied by existing code or configuration?

### 7. Missing Expert Consultation
- Per the PM workflow, expert consultation is expected before marking an epic READY when stories touch:
  - Domain statistics or coaching logic (baseball-coach should be consulted)
  - API behavior or GameChanger endpoint patterns (api-scout should be consulted)
  - Database schema or ETL pipeline design (data-engineer should be consulted)
  - Agent infrastructure, CLAUDE.md, rules, or skills (claude-architect should be consulted)
- Does the epic's Background section document that consultation occurred where it was warranted?
- If consultation was skipped, is there a stated reason?

### 8. Definition of Done Clarity
- Does each story have a "Definition of Done" section that an implementing agent could use to self-assess completion?
- Are the DoD items specific and verifiable (not vague like "works correctly" or "looks good")?
- Is the DoD consistent with the ACs (not a weaker or looser restatement)?

### 9. Implemented Reality vs. Planned Future State
- Does the epic clearly distinguish between what currently exists in the repo and what the epic will create?
- Are any claims about existing infrastructure actually accurate (file paths, module names, API behaviors)?
- If the epic references other epics as "completed", have those actually been completed and archived?

## Reporting

- Cite the specific story ID and AC label (e.g., "E-034-03, AC-5") for every finding.
- Group findings by checklist category.
- Rate each finding: **P1** (blocks READY), **P2** (should fix before READY), **P3** (minor, fix if easy).
- If the spec is clean across all nine categories, state explicitly: "No findings. This epic is ready to mark READY."
- Do not report stylistic opinions on prose quality unless they cause genuine ambiguity in a testable AC.
