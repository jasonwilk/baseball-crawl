# Skill: context-fundamentals

**Category**: Foundational
**Adapted for**: baseball-crawl
**Source**: muratcankoylan Agent Skills for Context Engineering (E-008-R-02)

---

## Activation Triggers

Load this skill when you are about to:

- **Begin a complex multi-file task** where many documents will be loaded into the same session (multiple story files, research artifacts, API specs, design docs)
- **Notice context window usage is above 70%** (the statusline shows yellow or red on the context bar) and you need to decide whether to load another large document
- **Decide whether to load a full research artifact or summarize from memory** before beginning a task
- **Use `/clear` to start a new session** and want to confirm you are doing so for the right reasons
- **Compact context** mid-session and want to understand what is at risk of being lost
- **Debug an agent that missed a key fact** that was present in a file loaded earlier in the session

---

## Key Concepts

### 1. The Four Components of a Context Window

Every agent session's context window contains four types of content:

1. **System prompt / ambient rules**: The project's root CLAUDE.md, all `.claude/rules/*.md` files, and the agent's definition from `.claude/agents/<agent>.md`. This loads automatically at session start. In baseball-crawl, this is approximately 1,000-1,270 lines of text before any task-specific content is added.

2. **Conversation history**: The turn-by-turn exchange between the user and the agent, including all tool calls and tool results. This grows throughout the session. Long sessions with many file reads, bash commands, and edit operations accumulate substantial conversation history.

3. **Tool outputs**: Results from tool calls (file reads, bash command outputs, search results). When you read a 300-line file, those 300 lines enter the context window as tool output and remain there for the rest of the session.

4. **Loaded files (task-specific context)**: Files explicitly loaded for the current task -- story files, epic Technical Notes, research artifacts. These are a subset of tool outputs but worth treating as a distinct category because they are the primary lever agents have for managing context budget.

### 2. Lost in the Middle

The "lost in the middle" phenomenon is a well-documented failure mode in LLM context windows: **information at the very beginning and very end of a context window receives more attention than information in the middle**.

In practice, this means:
- Content loaded at session start (ambient rules, agent definition) is relatively well-attended
- Content loaded just before the current response is relatively well-attended
- Content loaded in the middle of a long session -- a research artifact read three tool calls ago -- may receive less attention than you expect

**Implication for baseball-crawl**: If you need an agent to apply a specific contract or invariant (e.g., the rate limiting rule from the HTTP session story), load the relevant file close to the point of use, not at session start. Do not assume that a file loaded at the beginning of a long session will be correctly applied 50 tool calls later.

### 3. Context Poisoning

Context poisoning occurs when **incorrect or misleading information** enters the context window and distorts subsequent reasoning. Unlike lost-in-the-middle (where information is forgotten), context poisoning is active: the wrong information is applied instead of the right information.

Common sources of context poisoning in baseball-crawl:
- Loading a stale research artifact that describes an architecture that was subsequently revised
- Reading a story file whose Status field has not been updated (reading an IN_PROGRESS story as if its approach is settled when it may have changed)
- Tool output that includes an error message that the agent misinterprets as the expected output

**Mitigation**: Check file modification dates on critical design documents. If a research artifact is more than a few weeks old and the epic it informed has evolved, verify against the current epic file rather than relying solely on the artifact.

### 4. Context Compaction

When a session's context window approaches its limit, Claude Code automatically compacts the conversation history by summarizing older turns. This is a lossy operation -- details from early in the session may be summarized into higher-level statements that lose precision.

**What compaction affects**: Conversation history (turns, tool calls, tool results from earlier in the session). The ambient context (system prompt, CLAUDE.md, rules files) is preserved.

**What compaction does not affect**: Files that are currently loaded in the context remain accessible. The agent's MEMORY.md (ambient) is preserved. The current task's story file (if loaded recently) is likely preserved.

**Implication**: If you are mid-session and context compaction is imminent, any nuanced information from early file reads may be compacted into summaries. If that information is critical, re-read the source file before making a decision that depends on it.

---

## Practical Implementation

### Baseball-Crawl's Context Budget

Every baseball-crawl agent session starts with approximately **1,000-1,270 lines of ambient context** before any task-specific content is loaded:

| Source | Approximate Size | Notes |
|--------|-----------------|-------|
| Root `CLAUDE.md` | ~297 lines | Project conventions, architecture, security rules, HTTP discipline |
| `.claude/rules/*.md` files (10 files) | ~546 lines total | Workflow discipline, dispatch pattern, documentation, ideas, devcontainer, python-style, testing, crawling, project-management, and other rules |
| Agent definition (`.claude/agents/<agent>.md`) | ~139-327 lines | Varies by agent; PM is largest (327), baseball-coach smallest (139) |
| Agent `MEMORY.md` (`.claude/agent-memory/<agent>/MEMORY.md`) | ~12-97 lines | Varies; PM ~97, architect ~97, docs-writer ~12 |
| **Total ambient** | **~1,000-1,270 lines** | Before any task begins |

These are actuals measured during the 2026-03-03 context-layer review (`/.project/research/context-layer-review-2026-03-03.md`). Check the actual files if precision matters for a specific decision.

### Task-Specific Context (Loaded on Demand)

Beyond the ambient baseline, task-specific context is loaded per task. Approximate size ranges:

| Content Type | Typical Size | When Loaded |
|-------------|-------------|-------------|
| Story file | 50-150 lines | At task start, always |
| Epic Technical Notes section | 50-200 lines | At task start, always |
| Research artifact (`.project/research/`) | 100-400 lines per file | When story references it |
| API endpoint files (`docs/api/endpoints/*.md`) | 50-200 lines each | When story involves API calls (load only relevant endpoints) |
| Raw API responses / log excerpts | Variable (can be large) | On demand during debugging |
| Dependency story files | 50-150 lines each | When implementing agent needs to understand what a dependency delivered |

A typical story dispatch adds **200-400 lines** of task-specific context (story file + epic Technical Notes). A research-heavy session might add another **400-800 lines** across multiple artifacts. In a complex E-002 or E-003 story with multiple dependencies and multiple research artifacts, total context (ambient + task-specific) could easily reach 1,800-2,500 lines before any code is written.

### The Three Context Management Decisions

#### Decision 1: Load a Full Research Artifact or Rely on MEMORY.md?

**Load the artifact when**:
- The task requires a specific technical decision that the artifact informs
- The artifact contains acceptance criteria or contracts the task must satisfy
- The artifact is recent (same epic, same week) and unlikely to be stale
- The relevant section of MEMORY.md says "see [artifact file] for details"

**Rely on MEMORY.md when**:
- MEMORY.md contains the key fact in usable form (not just "see the artifact")
- The session is already above 70% context usage (yellow statusline)
- The artifact is older and the epic it informed has evolved significantly
- The task only needs a high-level decision, not the artifact's detailed constraints

**Rule of thumb**: If MEMORY.md has a self-contained entry for the pattern or decision, use MEMORY.md. If MEMORY.md says "see [artifact]" and the task depends on the details, load the artifact.

#### Decision 2: When to Use `/clear` Between Tasks

The CLAUDE.md "Workflow" section explicitly recommends `/clear` between unrelated tasks. This is a context management instruction, not just a hygiene preference.

**Use `/clear` when**:
- You are switching from one epic's story to a completely different epic's story (carry-over context from the first epic is noise for the second)
- The session's conversation history has become dominated by a debugging session that is now resolved
- You are about to begin a task that requires loading several large documents (the statusline shows >50% context usage and you have not yet loaded the task's files)
- A previous task involved large API response payloads or log files that are no longer relevant

**Do NOT use `/clear` when**:
- You are continuing in the same epic (the ambient context about the epic carries forward usefully)
- The previous task produced a result you need to reference in the next task
- You are in the middle of a multi-step PM dispatch sequence (clearing between dispatches loses track of which stories are IN_PROGRESS)

#### Decision 3: Context Usage Threshold for Loading Large Documents

The statusline at `.claude/hooks/statusline.sh` displays a color-coded context window usage bar:
- **Green** (< 70%): Safe to load additional context. Proceed normally.
- **Yellow** (70-89%): Caution zone. Load only what the current task strictly requires. Defer optional research artifacts.
- **Red** (90%+): Critical zone. Do not load large documents. If you need a large artifact, use `/clear` first and reload only the essentials (ambient context will reload automatically; manually re-load the story file and Technical Notes).

**Practical threshold**: If the statusline shows yellow or red and you need to load a research artifact that is 200+ lines, use `/clear` first. The cost of starting a fresh session is lower than the cost of context compaction losing your story file mid-task.

**Exception**: If you are very close to completing a task and only need to make one or two more file edits, it is usually better to finish the task than to `/clear` and reload everything. The threshold applies to the beginning of a task, not the end.

### Context Budget for a Typical Story

Here is a worked example for a software-engineer story in E-006:

```
Session start (ambient):
  CLAUDE.md:                     ~297 lines
  workflow-discipline.md:         ~40 lines
  other rules files (9):         ~506 lines
  software-engineer.md agent def: ~150 lines
  software-engineer MEMORY.md:    ~87 lines
  ----------------------------------------
  Ambient subtotal:             ~1,080 lines

Task start (story dispatch):
  E-006-04.md (story file):      ~120 lines
  E-006 epic Technical Notes:    ~150 lines
  E-006-02.md (dependency):       ~80 lines  [loaded to understand PII taxonomy delivered]
  ----------------------------------------
  Task subtotal:                 ~350 lines

During task (demand-loaded):
  /.project/research/E-006-precommit-design.md:  ~200 lines
  ----------------------------------------
  Demand subtotal:               ~200 lines

Total:                         ~1,630 lines (~25-30% of a 128k context window)
```

This is a healthy context load. There is ample room for tool outputs (bash commands, file reads of code files) and conversation history before approaching yellow territory.

A session becomes risky when demand-loaded files are large (full API response dumps, multiple research artifacts) or when conversation history grows from many debugging cycles. Watch the statusline.

---

## References and Related Skills

### Related Skills in This Project
- **`filesystem-context`** (`.claude/skills/filesystem-context/SKILL.md`): The mechanism for loading context from files. `context-fundamentals` explains the why (context windows, token budgets, lost-in-the-middle); `filesystem-context` explains the how (which files to load, when, and in what order). These two skills are complementary.
- **`multi-agent-patterns`** (`.claude/skills/multi-agent-patterns/SKILL.md`): In multi-agent dispatch chains, the context budget concern applies to the dispatch context block (story file + epic Technical Notes). Understanding the budget helps explain why verbatim relay is the right choice even when summarizing would save tokens -- the savings are modest and the loss is real.

### Source Material
- **E-008-R-02 Research Summary**: `/.project/research/E-008-R-02-agent-skills-summary.md` -- Q7 identifies `context-fundamentals` as one of the three most applicable skills. The "Key Tensions" section (tension #2: progressive disclosure requires discipline) is directly relevant to the load-vs.-summarize decision in Decision 1.
- **E-008 Recommendation**: `/.project/research/E-008-intent-context-layer-recommendation.md` -- Phase 1 implementation sketch specifies the `context-fundamentals` adaptation: add a section on baseball-crawl's context budget with approximate line counts.
- **Statusline Documentation**: `.claude/hooks/README.md` -- Documents the context window usage bar thresholds (green/yellow/red) shown in the statusline. The color thresholds used in Decision 3 come from this documentation.
- **CLAUDE.md Workflow Section**: `CLAUDE.md` (the "Workflow" section) -- Contains the `/clear` between unrelated tasks guidance that this skill formalizes.

### External Reference
- muratcankoylan Agent Skills for Context Engineering: https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering -- The `context-fundamentals` skill in the Foundational category is the source for the four context component taxonomy, the lost-in-the-middle framing, and the context poisoning concept. Baseball-crawl's adaptation adds the specific ambient budget numbers, the task-specific size ranges, and the three decision guides with baseball-crawl-specific thresholds.
