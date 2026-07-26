# Agent Design -- Detailed Reference

## Subagent Architecture

### Configuration Format
Subagents are markdown files with YAML frontmatter in `.claude/agents/`:
```yaml
---
name: agent-name
description: When Claude should delegate to this agent
tools: Read, Grep, Glob, Bash
model: sonnet | opus | opus[1m] | fable | haiku | inherit   # aliases in use here: see the register below
effort: low | medium | high | xhigh | max                    # omit to take the model's default
permissionMode: default | acceptEdits | dontAsk | bypassPermissions | plan
maxTurns: 50
skills:
  - skill-name-to-preload
memory: user | project | local
background: false
isolation: worktree
hooks:
  PreToolUse: [...]
---

System prompt in markdown body...
```

### Scope Priority (highest to lowest)
1. `--agents` CLI flag (session only)
2. `.claude/agents/` (project, check into git)
3. `~/.claude/agents/` (user, all projects)
4. Plugin's `agents/` directory

### Built-in Subagents
- **Explore**: Haiku, read-only, fast codebase exploration
- **Plan**: Inherits model, read-only, research for planning
- **general-purpose**: Inherits model, all tools, complex multi-step tasks
- **Bash**: Inherits model, terminal commands in separate context

### Key Design Principles
- Design focused agents: each should excel at one specific task
- Write detailed descriptions: Claude uses these to decide when to delegate
- Limit tool access: grant only necessary permissions
- Check into version control for team sharing
- Subagent nesting WORKS (corrected 2026-07-26, Claude Code 2.1.220 — verified in transcripts: a subagent called the `Agent` tool and produced four `spawnDepth: 1` children carrying its `parentAgentId`). Our named agents cannot spawn because **no agent definition in `.claude/agents/` grants the `Agent` tool** — a configuration choice, changeable, not a platform limit. The old "no nesting" claim was false and had propagated to 7 sites.

### Persistent Memory for Agents
- `memory: user` -- recommended default, learns across all projects
- `memory: project` -- project-specific, shareable via version control
- `memory: local` -- project-specific, not version controlled
- First 200 lines of MEMORY.md loaded into system prompt
- Read/Write/Edit tools auto-enabled when memory is on

### When to Use Subagents vs Main Conversation
**Use main conversation when:**
- Task needs frequent back-and-forth
- Multiple phases share significant context
- Making a quick, targeted change
- Latency matters

**Use subagents when:**
- Task produces verbose output (test results, exploration)
- Want to enforce specific tool restrictions
- Work is self-contained and can return a summary

## Execution-Profile Register (per agent)

Audited 2026-07-26 (D5 of the consolidated layer pass). Alias-to-model resolutions
come from the dated register in `model-behavior-reference.md`; re-verify there
rather than trusting this table's second column, which is a copy.

| Agent | Alias | Resolves to | Effort | Adapter | Tool-surface note |
|---|---|---|---|---|---|
| api-scout | `opus` | claude-opus-5 | `medium` | Opus 5 | + Bash, WebFetch |
| claude-architect | `opus[1m]` | claude-opus-5 | `high` | Opus 5 | + Bash, WebFetch |
| code-reviewer | `opus[1m]` | claude-opus-5 | `high` | Opus 5 | read-only: no Write/Edit, has Bash |
| data-engineer | `opus[1m]` | claude-opus-5 | `high` | Opus 5 | + Bash, WebFetch |
| product-manager | `opus[1m]` | claude-opus-5 | `high` | Opus 5 | **no Bash, no WebFetch** (deliberate) |
| software-engineer | `opus[1m]` | claude-opus-5 | `high` | Opus 5 | + Bash, WebFetch |
| baseball-coach | `sonnet` | claude-sonnet-5 | *unset* | none | no Bash, no WebFetch |
| docs-writer | `sonnet` | claude-sonnet-5 | *unset* | none | no Bash, no WebFetch |
| ux-designer | `sonnet` | claude-sonnet-5 | *unset* | none | no Bash, no WebFetch |

No agent pins `fable` or any 4.8 alias; the Fable path is an ad-hoc spawn-time
override (`.claude/rules/agent-routing.md`), so its coaching lives in the spawn
prompt, not in a definition. No definition sets a `thinking` field, and thinking
is ON by default on both Opus 5 and Sonnet 5 [VENDOR, 2026-07-26] — so the
absence is the intended state, not an omission. No definition grants `Agent`
(see the spawner-only note below).

**Three audit conclusions that are "leave it alone", recorded so the next pass
does not re-open them:**

1. **The three unset Sonnet efforts are correct as unset.** This was carried
   forward as an open item from the Opus review (G2) on the assumption that an
   unset field risked low-effort under-thinking. It does not: *"On Claude Sonnet
   5, effort defaults to `high`, the same as on Claude Sonnet 4.6"* [VENDOR
   "Prompting Claude Sonnet 5", fetched 2026-07-26]. The under-thinking risk the
   same page describes is scoped to `low`, which is not where these agents run.
   Writing `effort: high` would add three lines that change no behavior. If cost
   ever needs trimming on the consultation agents, `medium` is the lever.
2. **api-scout at `medium` on Opus 5 is correct.** *"use `low` and `medium`
   liberally as your primary control for token cost and response time wherever
   quality holds"* [VENDOR "Prompting Claude Opus 5"]. api-scout's work is
   documentation-shaped rather than reasoning-dense. The vendor also says to
   re-run an effort sweep on your own evals after carrying defaults over from a
   prior model; we have no evals, so the standing posture is leave-and-observe,
   not a speculative retune.
3. **The delegation cap does not apply to any agent here.** The Opus 5 page's
   subagent-damping snippet governs an orchestrator, and no definition grants
   `Agent`. Adding it would be coaching against a behavior the tool surface
   already makes impossible — the over-constraint the same vendor guidance warns
   about. Revisit only if the `Agent` grant changes.

**One finding that is NOT fixed here, because fixing it is outside D5's scope
(a rule edit, not an execution profile) — route it deliberately:** the READY
Freshness Gate in `.claude/rules/workflow-discipline.md` assigns PM a fallback
staleness measurement of `git log -1 --format=%cs -- epics/E-NNN-slug/`, and
**PM has no Bash tool**, by deliberate design (its own anti-pattern 1 says so).
So the gate's primary path (read the READY date out of the epic file) is
runnable by PM and its fallback path is not. The fix is one sentence in the rule
— when the epic file carries no READY date, PM asks the main session for the
commit date rather than estimating — not a tool grant.

## Agent Teams (Experimental)

### Architecture
- Team lead: main session that creates team and coordinates
- Teammates: separate Claude Code instances with own context
- Shared task list with claim/complete workflow
- Mailbox for inter-agent messaging

### Best Use Cases
- Research and review (multiple angles simultaneously)
- New modules/features (each teammate owns a piece)
- Debugging with competing hypotheses
- Cross-layer coordination (frontend, backend, tests)

### Best Practices
- Start with 3-5 teammates
- 5-6 tasks per teammate is the sweet spot
- Size tasks as self-contained units with clear deliverables
- Give teammates enough context in spawn prompt
- Avoid file conflicts (each teammate owns different files)
- Monitor and steer; don't let team run unattended too long

### Teams vs Subagents Decision Matrix
| Need                    | Use           |
|------------------------|---------------|
| Quick focused worker   | Subagent      |
| Only result matters    | Subagent      |
| Workers need to talk   | Agent team    |
| Competing hypotheses   | Agent team    |
| Shared coordination    | Agent team    |
| Lower token cost       | Subagent      |

## Agent Ecosystem Design Patterns

### Common Patterns
1. **Writer/Reviewer**: One agent writes, another reviews with fresh context
2. **Research fan-out**: Multiple subagents explore different aspects in parallel
3. **Chain pattern**: Subagents in sequence, each completing a phase
4. **Specialist delegation**: Claude routes to domain-specific agents

### Quality Gates
- Use hooks (TeammateIdle, TaskCompleted) to enforce quality
- PreToolUse hooks for conditional validation
- Stop hooks to verify work before completing

### Context Efficiency
- Subagents run in separate context windows (preserves main context)
- Skills preloaded into subagents are fully injected (not on-demand)
- Subagents don't inherit parent conversation history
- Auto-compaction triggers at ~95% capacity for subagents too

## Team-Communication Tools (Agent Teams)

Every team-participating agent definition MUST list these five tools in `tools:` frontmatter:
- `SendMessage` -- send messages to teammates and main session
- `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet` -- shared task list operations

Without these tools, spawned teammates can do file work but cannot reply to assignments or report completion via SendMessage. The implement skill instructs agents to use SendMessage extensively for assignment and completion reporting -- the tools must be granted at the frontmatter level.

**Discovered 2026-05-15 during E-228 dispatch**: all 5 teammates (PM, DE, SE, UXD, CR) silently failed a "reply ALIVE via SendMessage" diagnostic ping. Audit revealed none of the 9 agent definitions had any team-comms tools — they had never been present in any git revision. Fix: added the 5 tools to all 9 agent definitions.

Team formation is now implicit and teardown automatic (the explicit `TeamCreate`/`TeamDelete` tools were removed in Claude Code v2.1.178). The flag `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` gates the team-coordination surface: without it, both `SendMessage` and the shared `Task*` task list are unavailable and spawned agents are one-shot (consistent with TN-4 and the durable `CLAUDE.md` Agent Ecosystem note).

Spawner-only tool (deliberately NOT granted to teammates):
- `Agent` (Task tool) -- currently held only by the main session. This is our GRANT policy, not a platform capability limit; granting it to an agent would let that agent spawn (see the nesting correction above). Revisit deliberately, not by accident. **Operator ruling 2026-07-26: keep the grants as they are and "decide later with data"** -- the P2/P3 handoff evals will count PM-escalation events, so the revisit happens against a number rather than an intuition.

Any future new agent definition MUST include the 5 team-comms tools unless it is intentionally isolated from team dispatch.
