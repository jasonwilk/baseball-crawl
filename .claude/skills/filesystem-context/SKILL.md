# Skill: filesystem-context

**Category**: Architectural
**Adapted for**: baseball-crawl
**Source**: muratcankoylan Agent Skills for Context Engineering (E-008-R-02)

---

## Activation Triggers

Load this skill when you are about to:

- **Start a new task** that requires reading context files before beginning work (story files, epic files, research artifacts, API specs, design docs)
- **Decide what to load at session start** vs. what to defer until a specific sub-task needs it
- **Choose between loading a full document or relying on memory** when a session's context window is partially consumed
- **Write a new context file** (story, epic, research artifact, agent memory entry) and need to decide what belongs in it vs. what should stay ambient
- **Debug an agent completing a task incorrectly** and suspect it was missing key context that was available on the filesystem but never loaded

---

## Key Concepts

### 1. The Filesystem as a Context Store

The filesystem is not just where code lives -- it is an active context delivery system. Any information that an agent needs to perform a task can be placed in a file and loaded on demand. This is more scalable than embedding all possible context in static system prompts, because:

- Static prompts load everything regardless of relevance (expensive, diluting)
- File-based context loads only what is needed for the current task (efficient, focused)

**The core pattern**: Store context in files. Load it on demand. Name files and directories semantically so agents can discover them by path alone.

### 2. Progressive Disclosure

Progressive disclosure is the mechanism that makes file-based context efficient:

1. **First pass**: An agent sees only the name and location of a context file (e.g., the story table in `epic.md` lists story IDs and titles)
2. **Second pass**: When the agent determines it needs the full content, it reads the file

This two-step load means a session can "know about" many context files without paying the token cost of loading all of them. The agent pays full cost only for what it actually uses.

In baseball-crawl, progressive disclosure appears at multiple levels:
- Epic tables list story IDs and titles -- the PM reads individual story files only when dispatching
- Agent definitions name skill files by trigger condition -- the agent reads the full SKILL.md only when the trigger fires
- MEMORY.md contains pointers to deeper topic files -- agents read those only when the topic is active

### 3. Ambient Context vs. Deferred Context

**Ambient context** loads automatically at session start, before any task begins:
- The root `CLAUDE.md`
- All files in `.claude/rules/`
- The agent's own definition from `.claude/agents/<agent>.md`
- The agent's `MEMORY.md` from `.claude/agent-memory/<agent-name>/MEMORY.md`

**Deferred context** is loaded explicitly when a task requires it:
- Story files
- Epic `Technical Notes` sections
- Research artifacts from `/.project/research/`
- API specs from `docs/gamechanger-api.md`
- Raw API responses or log excerpts

The distinction matters: ambient context is available without cost at session start. Deferred context has to be deliberately fetched. Missing deferred context is a common failure mode -- the agent starts work without the full picture.

### 4. The Cost of Over-Loading vs. Under-Loading

**Over-loading** (loading too much context):
- Dilutes attention -- important facts at the beginning and end of a large context window receive less attention than facts in the middle ("lost in the middle" phenomenon)
- Consumes tokens that could be used for actual work
- Can trigger context compaction, which loses conversation history

**Under-loading** (loading too little context):
- Agent works from incomplete information and makes decisions that violate contracts or miss requirements
- Common failure: implementing agent starts a story without reading the epic's Technical Notes, misses a key invariant, and ships non-compliant code
- Produces re-work

**The right balance**: Load the ambient context (it is always present), load the task's story file in full, load the relevant epic Technical Notes, and defer research artifacts unless the task specifically requires them.

### 5. Meta-Note: Skills Are Themselves Filesystem Context

This SKILL.md file is an instance of the filesystem-context pattern. It is not pre-loaded into every session. Instead, agent definitions name this skill by trigger condition (e.g., "when beginning a task that requires reading context files, read `.claude/skills/filesystem-context/SKILL.md`"). You are reading this file because a trigger fired -- that is progressive disclosure working correctly.

---

## Practical Implementation

### How Baseball-Crawl Uses Filesystem Context

Baseball-crawl uses the filesystem-context pattern pervasively. The following named examples are the primary instances:

#### Example 1: Implementing Agents Load Story Files Before Starting Work

When `general-dev` or `data-engineer` receives a task, the standard context block always includes the full story file contents. The agent's first action is to confirm it has read and understood all acceptance criteria before touching any code.

File location: `/Users/jason/Documents/code/baseball-crawl/epics/E-NNN-slug/E-NNN-SS.md`

The story file is not ambient -- it is not loaded at session start. It is loaded per-task, when the PM dispatches the story. This keeps baseline session tokens low across the many stories in a project, while ensuring the implementing agent has full context for the specific story it is executing.

**Pattern in practice**: Before writing a single line of code, read the story file. Check all acceptance criteria. If any AC references an external file (a design doc, an API spec, a data schema), load that file too before beginning work.

#### Example 2: The PM Loads epic.md and All Story Files Before Dispatch

Before the `product-manager` dispatches any story, it reads:
1. The full `epic.md` for the parent epic (especially the Technical Notes section)
2. All story files in the epic directory (to identify which are TODO vs. IN_PROGRESS vs. DONE)
3. The story files for any completed dependencies (to understand what those stories delivered)

File locations:
- Epic: `/Users/jason/Documents/code/baseball-crawl/epics/E-NNN-slug/epic.md`
- Stories: `/Users/jason/Documents/code/baseball-crawl/epics/E-NNN-slug/E-NNN-SS.md`

This is a deliberate load sequence, not an accident. The PM does not rely on memory alone for dependency statuses -- it reads the actual story files to confirm current status. Memory can be stale; the file is the source of truth.

**Pattern in practice**: The PM's dispatch context block (sent to implementing agents via the Task tool) always includes the full story file text and the full epic Technical Notes section. Never a summary. Summaries drop information.

#### Example 3: Agent Memory Files Are Loaded at Session Start

Each agent has a persistent memory file at:
`/Users/jason/Documents/code/baseball-crawl/.claude/agent-memory/<agent-name>/MEMORY.md`

This file loads automatically when the agent starts a session. It provides:
- Numbering state (next available epic or idea number)
- Project context (key architectural decisions, active epics summary)
- User preferences
- Lessons learned from previous sessions
- Pointers to deeper topic files (e.g., `patterns.md`, `debugging.md`)

The MEMORY.md file is ambient context for that agent -- always present, always current. Deeper topic files (linked from MEMORY.md) are deferred context -- loaded only when the topic is active.

**Pattern in practice**: If MEMORY.md exceeds 200 lines, content should be moved to a named topic file and a link added in MEMORY.md. This keeps the ambient load small and moves detail to deferred status.

#### Example 4: Research Artifacts Are Loaded When Decisions Arise

Research spikes produce artifacts in `/.project/research/`. These files are not loaded automatically -- they are deferred context, available when needed:

- `/.project/research/E-008-R-02-agent-skills-summary.md` -- loaded by claude-architect when evaluating skill adoption decisions
- `/.project/research/E-008-intent-context-layer-recommendation.md` -- loaded by the PM when writing E-010 stories
- `/.project/research/E-006-precommit-design.md` -- loaded by general-dev when implementing the PII scanner

File location pattern: `/.project/research/<E-NNN-slug>-<topic>.md`

**Pattern in practice**: Never load all research artifacts at session start. Load the specific artifact when the decision or implementation it informs is the current focus.

#### Example 5: API Spec Loaded by API-Touching Agents

The GameChanger API spec lives at:
`/Users/jason/Documents/code/baseball-crawl/docs/gamechanger-api.md`

This is deferred context for most agents. `api-scout` loads it when exploring endpoints. `general-dev` loads it when implementing API client code. It is not ambient -- it changes frequently and is not relevant to every task.

**Pattern in practice**: Any story that involves making GameChanger API calls should explicitly reference `docs/gamechanger-api.md` in its Technical Approach section. The implementing agent then loads it at task start.

### Decision Guide: What to Load and When

```
Session start:
  [auto] CLAUDE.md
  [auto] .claude/rules/*.md (all rules files)
  [auto] .claude/agents/<my-agent>.md (my definition)
  [auto] .claude/agent-memory/<my-agent>/MEMORY.md (my memory)

Task start (always load):
  [manual] Story file: /epics/E-NNN-slug/E-NNN-SS.md
  [manual] Epic Technical Notes: /epics/E-NNN-slug/epic.md (Technical Notes section)

Task start (load if story references it):
  [conditional] Dependency story files (for understanding what they delivered)
  [conditional] Research artifacts from /.project/research/
  [conditional] API spec: docs/gamechanger-api.md
  [conditional] Design documents referenced in story Notes section

During task (load on demand):
  [demand] Any file the task requires you to read, modify, or understand
  [demand] Deeper topic files linked from MEMORY.md
  [demand] This SKILL.md if the task involves context management decisions
```

### Writing New Context Files

When creating a new file that will serve as deferred context:

1. **Name it semantically**: The path should convey its purpose (`E-006-precommit-design.md` tells an agent this is about the pre-commit design for E-006).
2. **Put the most important content first**: Agents loading a large file under time or token pressure will read the beginning more carefully than the end.
3. **Include a brief header**: Date, author, and what question this file answers. An agent should know within 5 lines whether this is the right file to load.
4. **Link to it from the right index**: Research artifacts go in `/.project/research/`. Story-specific artifacts go in the epic directory. Agent-specific knowledge goes in `.claude/agent-memory/<agent>/`.

---

## References and Related Skills

### Related Skills in This Project
- **`multi-agent-patterns`** (`.claude/skills/multi-agent-patterns/SKILL.md`): How filesystem-context integrates with multi-agent dispatch. The dispatch context block (story file + epic Technical Notes) is the primary instance of filesystem-context in the user -> PM -> implementing agent chain. Load this skill when coordinating context delivery across multiple agents.
- **`context-fundamentals`** (`.claude/skills/context-fundamentals/SKILL.md`): The foundational framework for understanding context windows, token budgets, and the mechanics of why filesystem-context works. Load this skill before beginning complex multi-file tasks where context budget decisions are critical.

### Source Material
- **E-008-R-02 Research Summary**: `/.project/research/E-008-R-02-agent-skills-summary.md` -- Documents the muratcankoylan Agent Skills for Context Engineering repository, including the SKILL.md format and the progressive disclosure mechanism. The recommendation to adopt `filesystem-context`, `multi-agent-patterns`, and `context-fundamentals` specifically originated in this research.
- **E-008 Recommendation**: `/.project/research/E-008-intent-context-layer-recommendation.md` -- The Phase 1 implementation sketch that specified how each skill should be adapted for baseball-crawl.
- **E-010 Epic**: `/Users/jason/Documents/code/baseball-crawl/epics/E-010-intent-context-layer-implementation/epic.md` -- Parent epic for all three Phase 1 skill files. Technical Notes section contains the canonical SKILL.md format description.

### External Reference
- muratcankoylan Agent Skills for Context Engineering: https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering (12.8k stars as of 2026-02-28). Baseball-crawl adopts 3 of the 13 skills from this repository, adapted to project-specific conventions. The plugin install (`/plugin marketplace add muratcankoylan/...`) is NOT used -- skills are written and maintained directly.
