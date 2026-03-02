# Semantic/Intent Layer Design -- Detailed Reference

## What is the Semantic Layer?

The semantic layer is the meta-architecture that maps user intents to agent capabilities.
It ensures that for any user request, the right agent is activated with the right context.
It encompasses:
- CLAUDE.md files (always-on project context)
- Skills (on-demand knowledge and workflows)
- Subagent descriptions (delegation routing)
- Rules (modular, scoped instructions)
- The relationships between all of these

## Core Architectural Principles

### Five Pillars of Claude Code Design
1. **Model-Driven Autonomy**: The model decides next steps within boundaries
2. **Context as a Resource**: Auto-compaction and careful context management
3. **Layered Memory**: 6 layers load at session start with priority hierarchy
4. **Declarative Extensibility**: Skills and agents defined via markdown/YAML
5. **Composable Permissions**: Tool-level allow/deny/ask

### Intent Routing
- Claude uses subagent descriptions to decide when to delegate
- Claude uses skill descriptions to decide when to load skills
- No algorithmic routing -- Claude's native language understanding matches intent
- Write clear, specific descriptions to improve routing accuracy
- Vague or overlapping descriptions cause mis-routing

## Feature Selection Decision Framework

### Always-On Context (CLAUDE.md)
- Project conventions that apply to every task
- "Always do X" / "Never do Y" rules
- Build commands, test runners, environment setup
- Keep under ~500 lines; move reference material to skills

### On-Demand Knowledge (Skills)
- Reference material Claude needs sometimes (API docs, style guides)
- Workflows triggered with /name (deploy, review, release)
- Domain knowledge that's too large for CLAUDE.md
- Use `disable-model-invocation: true` for side-effect workflows

### Isolated Execution (Subagents)
- Tasks that produce verbose output (test results, exploration)
- Parallel research (multiple subagents explore simultaneously)
- Specialized workers with restricted tool access
- Context preservation (exploration stays out of main context)

### Deterministic Automation (Hooks)
- Actions that must happen every time (formatting, linting)
- Zero context cost (runs externally)
- Cannot be ignored by the model (unlike CLAUDE.md instructions)
- Use for enforcement, not guidance

### External Connections (MCP)
- Database queries, Slack, browser control
- Pair with skills that teach Claude how to use the connection
- Tool definitions load at session start (context cost)

## Layering Strategy

### How Features Layer
- CLAUDE.md: additive (all levels contribute simultaneously)
- Skills/subagents: override by name (higher priority wins)
- MCP servers: override by name (local > project > user)
- Hooks: merge (all matching hooks fire regardless of source)

### Effective Combinations
| Pattern              | How it works                                           |
|---------------------|-------------------------------------------------------|
| Skill + MCP         | MCP provides connection; skill teaches usage patterns |
| Skill + Subagent    | Skill spawns subagents for parallel work              |
| CLAUDE.md + Skills  | Always-on rules + on-demand reference material        |
| Hook + MCP          | Hook triggers external actions through MCP            |

## Designing for a New Project

### Bootstrap Sequence
1. Run `/init` to generate starter CLAUDE.md
2. Refine CLAUDE.md with project-specific conventions
3. Create `.claude/rules/` for modular, topic-specific rules
4. Add skills for domain knowledge and repeatable workflows
5. Define subagents for specialized tasks
6. Add hooks for deterministic automation
7. Connect MCP servers for external services

### Scaling Strategy
- Start simple: just CLAUDE.md
- Add skills as reference material accumulates
- Add subagents when context management becomes an issue
- Add hooks when you find yourself correcting Claude on the same thing
- Agent teams for genuinely parallel work (use sparingly due to token cost)

### Maintenance Principles
- Treat CLAUDE.md like code: review, prune, test changes
- If Claude keeps doing something wrong despite a rule, the file is probably too long
- If Claude asks questions answered in CLAUDE.md, the phrasing might be ambiguous
- Periodically audit skills for relevance and accuracy
- Monitor agent descriptions for overlap
