# E-013: Agent Buildout -- Complete All Stubbed Agents

## Status
`COMPLETED`

## Overview
Five of the seven agents in `.claude/agents/` are either severely stubbed or missing critical infrastructure. This epic completes each agent to production quality: full frontmatter, comprehensive system prompts, seeded memory directories, intent layer integration, and context management skill wiring. The result is a fully operational agent ecosystem where every agent can be dispatched confidently without guessing at its capabilities or missing context.

**Absorbed epics**: E-012 (Filesystem-Context Skill Integration) and E-014 (Multi-Agent Patterns Skill Integration) were merged into this epic on 2026-03-01. All three epics modify agent definition files; running them as separate epics would create sequencing nightmares from shared file conflicts. E-013-04 was expanded to cover all skill wiring across all seven agents (absorbing E-012-01, E-012-02, E-014-01 through E-014-05). E-013-06 was created to absorb E-012-03 (PM dispatch procedure and quality checklist updates). E-012 and E-014 are archived as ABANDONED.

## Background & Context
The agent ecosystem was bootstrapped rapidly across E-001 through E-010. Two implementing agents (`general-dev`, `data-engineer`) were created as functional stubs in E-007, just detailed enough to enforce the work authorization gate. Three consultative agents (`orchestrator`, `api-scout`, `baseball-coach`) have solid system prompts but incomplete frontmatter and no memory infrastructure. No agent has skills wired into their definition with named trigger conditions, even though three skill files were delivered by E-010 Phase 1.

The specific gaps, discovered by reading all agent files on 2026-02-28:

**`data-engineer.md`** (42 lines, stub): Missing `description` and `memory` frontmatter fields. No sections covering core responsibilities, how to interact with other agents, memory instructions, or skill references. References Cloudflare D1/Wrangler in the body text -- this contradicts the E-009 decision to use SQLite (D1 dropped). Has no memory directory at all.

**`general-dev.md`** (42 lines, stub): Same structural gaps as data-engineer. Missing `description`, `memory` frontmatter. No memory directory. No skill references. No section on responsibilities beyond work authorization gate and code style.

**`orchestrator.md`** (156 lines, reasonably complete): Has comprehensive routing logic but missing `memory` frontmatter and no memory directory. Does not reference any skills. `agent-blueprints.md` describes data-engineer and general-dev as "to be created when needed" but they already exist as stubs -- claude-architect's memory is stale on this point.

**`api-scout.md`** (168 lines, good content): Has `memory: project` frontmatter but no memory directory has been seeded (no `.claude/agent-memory/api-scout/` exists). Memory instructions section at the bottom is vague.

**`baseball-coach.md`** (134 lines, good content): Same as api-scout -- `memory: project` declared but no seeded directory. Memory instructions are a minimal bullet list.

**Intent layer gap**: E-010-06 (skill integration into agent definitions) remains BLOCKED pending E-002+E-003. However, the integration for orchestrator, api-scout, and baseball-coach can proceed now -- those agents' work is not gated on the data pipeline. The blocking dependency is only relevant for intent nodes in `src/`, not for skill references in agent definitions.

**No expert consultation required** -- this is infrastructure work within the agent ecosystem. All agents and their intended capabilities are already specified in CLAUDE.md, existing agent files, and claude-architect's memory. No domain decisions (baseball-coach) or API questions (api-scout) are needed to complete this epic.

## Goals
- `data-engineer.md` and `general-dev.md` are full operational manuals matching the depth of `api-scout.md` and `baseball-coach.md`, with complete frontmatter, all responsibility sections, memory instructions, and skill trigger references.
- All six non-orchestrator agents have seeded memory directories with a `MEMORY.md` that includes initial entries for project context, architectural decisions relevant to that agent, and known patterns.
- ALL seven agents have named skill references with trigger conditions for all applicable skills (`filesystem-context`, `multi-agent-patterns`, `context-fundamentals`) wired into their system prompts. Each agent receives only the skills relevant to their role (see E-013-04 for the mapping).
- The `filesystem-context` skill is wired into `project-manager.md` and `claude-architect.md` with trigger conditions tied to their specific workflows (Dispatch Mode, Refinement Mode, agent design decisions). *(Absorbed from E-012)*
- The `multi-agent-patterns` skill is wired into all seven agents with role-specific trigger conditions: relay agents (orchestrator, PM) get dispatch-time triggers, implementing agents (general-dev, data-engineer) get defensive triggers, consultative agents (baseball-coach, api-scout) get output-discipline triggers, and claude-architect gets design-time triggers. *(Absorbed from E-014)*
- The PM's Dispatch Mode procedure explicitly includes a progressive disclosure step referencing the filesystem-context skill, and the PM's quality checklist includes a verifiable item for deferred context file paths in story Technical Approach sections. *(Absorbed from E-012-03)*
- Claude-architect's own memory (`agent-blueprints.md`) is updated to reflect that stubs exist and remove stale "create when needed" entries.
- The E-009 SQLite-over-D1 decision is correctly reflected in `data-engineer.md` (no Wrangler references, correct migration tooling, correct local DB path).

## Non-Goals
- Writing Phase 2 intent nodes (`src/CLAUDE.md`, etc.) -- those remain BLOCKED on E-002+E-003 as specified in E-010.
- Changing existing agent routing logic or model assignments. Note: adding missing routing entries for data-engineer and general-dev to orchestrator.md is IN scope (E-013-04 AC-9) -- these agents exist but are not yet listed in the orchestrator's routing table.
- Creating new agents not already planned.
- Writing story-specific context documents for individual epics.
- Modifying `CLAUDE.md` or any `.claude/rules/` files.

## Success Criteria
1. `data-engineer.md` is 150+ lines, contains all mandatory sections (Identity, Core Responsibilities, Work Authorization, Database Standards, How You Interact With Other Agents, Skill References, Memory Instructions), and contains no Wrangler/D1/Cloudflare Workers references.
2. `general-dev.md` is 150+ lines, contains all mandatory sections (Identity, Core Responsibilities, Work Authorization, Code Standards, How You Interact With Other Agents, Skill References, Memory Instructions).
3. `.claude/agent-memory/api-scout/MEMORY.md` exists with initial entries covering: API exploration status, auth patterns discovered, credential lifecycle, known GameChanger API quirks.
4. `.claude/agent-memory/baseball-coach/MEMORY.md` exists with initial entries covering: coaching priorities established, stat decisions made, scouting report conventions, LSB team context.
5. `.claude/agent-memory/general-dev/MEMORY.md` exists with initial entries covering: project code conventions, key file paths, known implementation patterns.
6. `.claude/agent-memory/data-engineer/MEMORY.md` exists with initial entries covering: schema conventions (ip_outs, soft refs), migration tooling (apply_migrations.py), local dev DB path.
7. ALL seven agents have skill reference sections with named trigger conditions. Each agent receives only the skills relevant to their role (see E-013-04 for the full mapping).
8. `claude-architect`'s `agent-blueprints.md` has the stale "create when needed" entries for data-engineer and general-dev removed or updated to reflect current state.
9. `project-manager.md` contains a `## Skills` section referencing `filesystem-context` (with Dispatch Mode and Refinement Mode triggers) and `multi-agent-patterns` (with dispatch context block verification trigger). *(From E-012, E-014)*
10. `claude-architect.md` contains a `## Skills` section referencing `filesystem-context` (with ambient vs. deferred context design trigger) and `multi-agent-patterns` (with relay depth evaluation trigger). *(From E-012, E-014)*
11. The PM's Dispatch Mode step 1 in `project-manager.md` explicitly references the filesystem-context skill and names the two-pass progressive disclosure reading sequence. *(From E-012-03)*
12. The PM's quality checklist in `project-manager.md` includes an item requiring story Technical Approach sections to name all referenced context files by absolute path. *(From E-012-03)*

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-013-01 | Complete `data-engineer.md` -- full system prompt + memory seed | DONE | None | architect-01 |
| E-013-02 | Complete `general-dev.md` -- full system prompt + memory seed | DONE | None | architect-02 |
| E-013-03 | Seed memory directories for `api-scout` and `baseball-coach` | DONE | None | architect-03 |
| E-013-04 | Wire ALL skill references into ALL agent definitions | DONE | E-013-01, E-013-02 | architect-01 |
| E-013-05 | Update claude-architect's own memory to reflect current ecosystem state | DONE | E-013-01, E-013-02 | architect-03 |
| E-013-06 | Extend PM dispatch and quality checklist procedures | DONE | E-013-04 | architect-01 |

## Technical Notes

### Agent File Structure (canonical format)

Every agent file in `.claude/agents/` must follow this structure, derived from the best-in-class examples (`api-scout.md`, `baseball-coach.md`, `claude-architect.md`):

```
---
name: <agent-name>
description: "<routing description with 5 usage examples>"
model: haiku | sonnet | opus
color: <color>
memory: project
---

# <Agent Name> -- <Role Tagline>

## Identity
[2-3 sentences: who this agent is, their core expertise, what they are NOT]

## Core Responsibilities
### 1. [Responsibility Name]
[Specific description of what this means in practice]
...

## Work Authorization (for implementing agents only)
[Story reference requirement, refusal language]

## [Domain-Specific Standards]
[The technical rules and conventions specific to this agent's domain]

## How You Interact With Other Agents
[Which agents produce input for this agent, which agents consume this agent's output]

## Skill References
[Named skills with trigger conditions]

## Memory Instructions
[What to save, update frequency, what NOT to save]

# Persistent Agent Memory
[Standard memory block with path and guidelines]

## MEMORY.md
[Current memory or "Your MEMORY.md is currently empty."]
```

### Skill Reference Format (canonical)

The E-010-06 integration story established this format for skill references in agent definitions. Use this exact pattern in all five agents:

```markdown
## Skill References

Load `.claude/skills/filesystem-context/SKILL.md` when:
- Beginning a task that requires reading multiple context files before starting work
- Deciding whether to load a full document or rely on memory
- Writing a new context file and deciding what belongs in it

Load `.claude/skills/multi-agent-patterns/SKILL.md` when:
- Dispatching a story via the Task tool and verifying context block completeness
- Routing a request through more than one agent
- Debugging an implementing agent whose output does not match user intent

Load `.claude/skills/context-fundamentals/SKILL.md` when:
- Beginning a complex multi-file task where context window budget matters
- Context window usage is above 70% (yellow statusline) and you need to load another large document
- Deciding whether to use /clear before starting a new task
```

Agents should include only the skills relevant to their role. The orchestrator needs all three. Implementing agents need `filesystem-context` and `context-fundamentals` most acutely. Consultative agents (`api-scout`, `baseball-coach`) need `filesystem-context` primarily.

### E-009 Architecture (for data-engineer)

The E-009 decision (finalized 2026-02-28, decision at `/.project/decisions/E-009-decision.md`) replaced Cloudflare D1 with SQLite:

- **Storage**: SQLite in Docker volume (WAL mode + Litestream backup), host-mounted at `./data/app.db`
- **Migrations**: Numbered SQL files (`migrations/001_*.sql`, `migrations/002_*.sql`). No Alembic, no Wrangler, no D1 CLI.
- **Migration runner**: `apply_migrations.py` (runs at app startup, applies any unapplied migrations in order)
- **Local dev**: `./data/app.db` (host-mounted SQLite). `docker compose up`.
- **No Cloudflare Workers, no D1 CLI, no `wrangler` commands** anywhere in data-engineer's domain.
- **ip_outs convention**: Innings pitched stored as integer outs (1 IP = 3 outs). Always. No exceptions.
- **Soft referential integrity**: Orphaned player IDs in stats tables are accepted with a WARNING log, not rejected.
- **Splits**: Home/away and L/R stored as nullable columns in season stats tables (not separate rows).

### Memory Seed Content (per agent)

Memory seed entries should reflect what the agent *would have learned* if it had been active throughout E-001 through E-010. Draw from:
- The PM's MEMORY.md (key architectural decisions section)
- The claude-architect's MEMORY.md (agent ecosystem section)
- The relevant epic Technical Notes for each agent's domain

**api-scout seeds** (from project history):
- GameChanger API is undocumented; all knowledge is empirical
- Credentials are short-lived, user provides curl commands, `scripts/refresh_credentials.py` extracts them
- API spec lives at `docs/gamechanger-api.md` -- the single source of truth
- Never log/store actual tokens; redact to `{AUTH_TOKEN}` placeholders

**baseball-coach seeds** (from CLAUDE.md and project scope):
- Target: LSB HS Freshman, JV, Varsity, Reserve (Legion later)
- Roster: 12-15 players per team, ~30 game seasons
- Key batting stats: OBP (most important), K%, BB%, splits by hand and home/away
- Key pitching stats: K/9, BB/9, K/BB ratio, pitch counts
- ALWAYS flag stats with < 20 PA or < 15 IP
- Coaching decisions: lineup construction, pitching matchups, opponent tendencies, player development

**general-dev seeds** (from CLAUDE.md code conventions):
- Type hints on all function signatures
- Docstrings on all public functions and classes
- Prefer dataclasses or Pydantic models for structured data
- Use `pathlib` for file paths (not `os.path`)
- Use `logging` module (not `print`)
- Pytest for tests; mock HTTP at the transport layer (never real network calls)
- Source code: `src/`. Tests: `tests/`. Data: `data/`. Docs: `docs/`.

**data-engineer seeds** (from E-003, E-009 decisions):
- SQLite everywhere (local + prod). No D1. No Wrangler.
- Migration files: `migrations/001_*.sql`, `migrations/002_*.sql`, etc.
- apply_migrations.py runs at startup, applies unapplied migrations in order
- ip_outs convention: 1 IP = 3 outs. Always integer outs.
- Soft referential integrity: log WARNING on orphaned player IDs, do not reject
- Splits: nullable columns (home_obp, away_obp, vs_lhp_obp, vs_rhp_obp), not separate rows
- Local dev DB: `./data/app.db` (host-mounted Docker volume)
- Core entities: Team, Player, PlayerTeamSeason, Game, Lineup, PlateAppearance, PitchingAppearance

### Skill-to-Agent Mapping (for E-013-04)

| Agent | filesystem-context | multi-agent-patterns | context-fundamentals |
|-------|-------------------|---------------------|---------------------|
| orchestrator | Yes | Yes | Yes |
| project-manager | Yes | Yes | No |
| claude-architect | Yes | Yes | No |
| api-scout | Yes | Yes | Yes |
| baseball-coach | Yes | Yes | No |
| general-dev | Yes | Yes | Yes |
| data-engineer | Yes | Yes | Yes |

### Trigger Conditions by Agent (for E-013-04)

**orchestrator** (all three skills):
- filesystem-context: "About to pass a large context block via Task tool or deciding what to include in a dispatch"
- multi-agent-patterns: "Constructing a Task tool dispatch -- before writing the prompt passed to project-manager, to apply verbatim relay and check for telephone game distortion risk" + "Aggregating outputs from multiple specialist agents before relaying to the user -- to quote findings directly rather than summarizing"
- context-fundamentals: "Context window is above 70% and you need to aggregate outputs from multiple agents"

**project-manager** (filesystem-context + multi-agent-patterns):
- filesystem-context: "Entering Dispatch Mode -- before reading the epic directory" + "Entering Refinement Mode -- before reading research artifacts, prior epic files, or dependency story files"
- multi-agent-patterns: "Entering Dispatch Mode -- before constructing the context block for an implementing agent, to verify the block contains the full story file and full epic Technical Notes (not summaries)" + "Receiving a work-initiation request from the orchestrator that appears to be a paraphrase"

**claude-architect** (filesystem-context + multi-agent-patterns):
- filesystem-context: "Designing or reviewing an agent definition -- when deciding what context belongs in system prompt (ambient) vs. skill file or memory topic file (deferred)" + "Structuring MEMORY.md files to determine what stays in the 200-line ambient section vs. what moves to a linked topic file"
- multi-agent-patterns: "Designing a new agent that adds a relay step to the orchestrator -> PM -> implementing agent chain" + "Reviewing or modifying routing logic in any existing agent definition"

**api-scout** (all three skills):
- filesystem-context: "Writing a new discovery to `docs/gamechanger-api.md`" + "Loading multiple research artifacts to cross-reference findings"
- multi-agent-patterns: "Completing an API exploration session and about to communicate findings -- to verify all discoveries are written to `docs/gamechanger-api.md`"
- context-fundamentals: "The API spec file is very large and the session context window is above 70%"

**baseball-coach** (filesystem-context + multi-agent-patterns):
- filesystem-context: "Consulted by PM and reading story files or epic Technical Notes" + "Writing a requirements artifact and deciding what belongs in the file vs. in memory"
- multi-agent-patterns: "Completing a consultation and about to communicate findings -- to verify outputs are written to a durable file"

**general-dev** (all three skills):
- filesystem-context: "Beginning a task that requires reading multiple context files including story file, epic Technical Notes, and referenced design docs"
- multi-agent-patterns: "The Task tool dispatch context appears to contain a summary -- request the full story file before writing any code"
- context-fundamentals: "About to load a large research artifact and context window is above 70%"

**data-engineer** (all three skills):
- filesystem-context: "Beginning a task that requires reading multiple context files including schema docs and migration files"
- multi-agent-patterns: "The Task tool dispatch context appears to contain a summary -- request the full story file before writing any SQL or ETL code"
- context-fundamentals: "About to load a large research artifact or multiple migration files and context window is above 70%"

### PM Skill Reference Format (from E-012)

For PM and architect, the `## Skills` section uses a more detailed format with `###` sub-headings:

```
## Skills

### <skill-name>
**File**: `.claude/skills/<skill-name>/SKILL.md`
**Load when**: [specific trigger conditions for this agent]

[One to two sentences describing why this skill is relevant to this agent's work.]
```

The trigger condition must be specific to the agent's named workflow steps, not a paraphrase of the generic activation triggers in the SKILL.md. This specificity is what makes the reference actionable rather than decorative.

### Implementing Agent Trigger Framing (from E-014)

For general-dev and data-engineer, the multi-agent-patterns trigger is defensive -- it fires when the dispatch context looks wrong, not proactively at every dispatch start. These agents receive many dispatches; loading the skill on every task start would be noisy. The right trigger is when something looks off -- a context block that reads like a summary, a missing acceptance criterion section, or a story file excerpt rather than a full file.

### File Conflict Analysis (from E-012, E-014)

The original E-012 and E-014 epics both modified agent definition files that E-013-04 also modifies. Consolidation eliminates the sequencing nightmares:

| File | Previously touched by | Now covered by |
|------|----------------------|---------------|
| `project-manager.md` | E-012-01, E-012-03, E-014-02 | E-013-04, E-013-06 |
| `claude-architect.md` | E-012-02, E-014-05 | E-013-04 |
| `orchestrator.md` | E-014-01 | E-013-04 |
| `api-scout.md` | E-014-04 | E-013-04 |
| `baseball-coach.md` | E-014-04 | E-013-04 |
| `general-dev.md` | E-014-03 | E-013-04 (verify) |
| `data-engineer.md` | E-014-03 | E-013-04 (verify) |

### Files Each Story Touches

- E-013-01: `.claude/agents/data-engineer.md`, `.claude/agent-memory/data-engineer/MEMORY.md` (new dir + file)
- E-013-02: `.claude/agents/general-dev.md`, `.claude/agent-memory/general-dev/MEMORY.md` (new dir + file)
- E-013-03: `.claude/agent-memory/api-scout/MEMORY.md` (new dir + file), `.claude/agent-memory/baseball-coach/MEMORY.md` (new dir + file)
- E-013-04: `.claude/agents/orchestrator.md`, `.claude/agents/project-manager.md`, `.claude/agents/claude-architect.md`, `.claude/agents/api-scout.md`, `.claude/agents/baseball-coach.md`, `.claude/agents/general-dev.md`, `.claude/agents/data-engineer.md`
- E-013-05: `.claude/agent-memory/claude-architect/agent-blueprints.md`, `.claude/agent-memory/claude-architect/MEMORY.md`
- E-013-06: `.claude/agents/project-manager.md`

No story touches the same file as another story running in parallel. E-013-01, E-013-02, and E-013-03 can run simultaneously. E-013-04 and E-013-05 must wait for E-013-01 and E-013-02 to be DONE. E-013-06 must wait for E-013-04 to be DONE.

## Open Questions
- Should `orchestrator` also get a memory directory? It is intentionally stateless (haiku model, no memory frontmatter, no domain knowledge to accumulate). Recommendation: no memory directory for orchestrator -- its routing table is encoded in its system prompt, not accumulated through experience. Revisit only if routing failures become frequent.

## Resolved Questions
- **data-engineer color**: Use `blue`. The current stub incorrectly sets `color: orange` (same as api-scout). The agent-blueprints.md blueprint specifies `blue`. Two different agents sharing the same color creates visual confusion. The E-013-01 rewrite must set `color: blue`.
- **general-dev color**: Use `blue`. The current stub has no `color` field set; blueprints.md says `purple` but the stub's absence of a color implies it was never cached. Use `blue` consistently for both implementing agents.
- **orchestrator routing table**: The orchestrator's "## Available Agents" section must include data-engineer and general-dev routing entries (added to E-013-04 as AC-9). Without these entries the orchestrator cannot route to these agents even after E-013-01 and E-013-02 complete.
- **claude-architect stale tech stack**: The line "Tech stack: Python + Cloudflare D1/Workers/Pages (SQLite locally for dev)" in claude-architect MEMORY.md must be corrected to reflect the E-009 decision (added to E-013-05 as AC-8).

## History
- 2026-02-28: Created. Gap analysis conducted by reading all seven agent files and claude-architect's memory files. Five agents identified as incomplete. No expert consultation required.
- 2026-02-28: Renumbered from E-011 to E-013. The E-011 slot was claimed by E-011-pm-workflow-discipline (also created 2026-02-28) -- a numbering collision caused by the same status-drift problem this project is now addressing via E-011. Story files renamed from E-011-0N to E-013-0N.
- 2026-03-01: Refinement pass by PM. Four gaps identified and fixed: (1) data-engineer color resolved to `blue` (was ambiguous -- corrected in E-013-01 AC-1); (2) migration file naming three-digit convention enforced in E-013-01 AC-5; (3) orchestrator routing table update for data-engineer and general-dev added to E-013-04 as AC-9; (4) stale Cloudflare D1 tech stack line in claude-architect MEMORY.md added to E-013-05 as AC-8. No expert consultation required -- all changes are within PM's infrastructure domain knowledge.
- 2026-03-01: Absorbed E-012 (Filesystem-Context Skill Integration) and E-014 (Multi-Agent Patterns Skill Integration) during triage. E-013-04 expanded to cover all skill wiring. E-013-06 created from E-012-03. E-013-01/02/03 reverted from IN_PROGRESS to TODO. E-012 and E-014 archived.
- 2026-03-02: Executed via agent team (3 claude-architect agents). Wave 1 (01, 02, 03) ran in parallel, Wave 2 (04, 05) ran in parallel after Wave 1, Wave 3 (06) ran after Wave 2. All 6 stories DONE. Epic COMPLETED.
