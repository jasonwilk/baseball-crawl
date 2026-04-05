# Agent Design -- Detailed Reference

Last updated: 2026-03-02

## Subagent Architecture

### Configuration Format
Subagents are markdown files with YAML frontmatter in `.claude/agents/`:
```yaml
---
name: agent-name
description: When Claude should delegate to this agent
tools: Read, Grep, Glob, Bash
model: sonnet | opus | haiku | inherit
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
- Subagents CANNOT spawn other subagents (no nesting)

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
