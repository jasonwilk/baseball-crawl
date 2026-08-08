# Skills and Hooks -- Detailed Reference

Last updated: 2026-03-04

## Skills System

### SKILL.md Format
```yaml
---
name: skill-name          # becomes /skill-name slash command
description: When to use   # Claude uses this for auto-invocation
argument-hint: [args]      # shown during autocomplete
disable-model-invocation: true  # manual-only invocation
user-invocable: false      # Claude-only, hidden from / menu
allowed-tools: Read, Grep  # tool restrictions when active
model: sonnet              # model override
context: fork              # run in isolated subagent
agent: Explore             # which subagent type for context: fork
hooks:                     # lifecycle hooks scoped to this skill
---

Markdown instructions here...
```

### Skill Locations (priority order)
1. Enterprise (managed settings)
2. Personal (`~/.claude/skills/<name>/SKILL.md`)
3. Project (`.claude/skills/<name>/SKILL.md`)
4. Plugin (`<plugin>/skills/<name>/SKILL.md`)

### Two Types of Skill Content
1. **Reference content**: Knowledge Claude applies (conventions, patterns, style guides)
   - Runs inline, available alongside conversation context
2. **Task content**: Step-by-step instructions for specific actions
   - Often invoked manually with /skill-name
   - Use `disable-model-invocation: true` for side-effect workflows

### Supporting Files
```
my-skill/
  SKILL.md           # Main instructions (required)
  template.md        # Template for Claude to fill in
  examples/
    sample.md        # Example output
  scripts/
    validate.sh      # Script Claude can execute
```
- Keep SKILL.md under 500 lines
- Move detailed reference to separate files
- Reference supporting files from SKILL.md

### String Substitutions
- `$ARGUMENTS` -- all arguments passed
- `$ARGUMENTS[N]` or `$N` -- specific argument by 0-based index
- `${CLAUDE_SESSION_ID}` -- current session ID
- `!`command`` -- preprocessor: runs shell command, inserts output

### Context Loading
- Descriptions always in context (2% of context window budget)
- Full content loads only when invoked (by you or Claude)
- `disable-model-invocation: true` = zero context cost until you invoke
- In subagents, preloaded skills are fully injected at startup

### Project Skills (Current)
| Skill | Category | Purpose |
|-------|----------|---------|
| context-fundamentals | Foundational | Context window mechanics, budget management |
| filesystem-context | Architectural | File-based context delivery, progressive disclosure |
| multi-agent-patterns | Architectural | Telephone game mitigation, dispatch checklist |
| ingest-endpoint | Workflow | Two-phase GameChanger API endpoint ingestion (api-scout then claude-architect) |

### Workflow Skills Pattern (ingest-endpoint)
- Workflow skills automate multi-agent sequences that the user has done manually 2+ times
- No YAML frontmatter -- the skill is loaded by the team lead when triggered by user intent
- CLAUDE.md Workflows section provides the discovery mechanism (team lead reads CLAUDE.md, sees trigger phrases, loads the SKILL.md)
- Both api-scout and claude-architect are direct-routing exceptions, so no PM intermediation needed
- Phase ordering matters: time-sensitive work (credential-bearing API calls) goes first

### Invocation Control Matrix
| Setting                          | User invoke | Claude invoke | Context cost |
|----------------------------------|------------|---------------|-------------|
| (default)                        | Yes        | Yes           | Description |
| disable-model-invocation: true   | Yes        | No            | Zero        |
| user-invocable: false            | No         | Yes           | Description |

## Hooks System

### Hook Events (Lifecycle Order)
| Event              | When                                      | Matcher           |
|--------------------|-------------------------------------------|--------------------|
| SessionStart       | Session begins/resumes/clears/compacts    | startup/resume/clear/compact |
| UserPromptSubmit   | User submits prompt                       | (none)             |
| PreToolUse         | Before tool executes                      | Tool name          |
| PermissionRequest  | Permission dialog appears                 | Tool name          |
| PostToolUse        | After tool succeeds                       | Tool name          |
| PostToolUseFailure | After tool fails                          | Tool name          |
| Notification       | Claude sends notification                 | Notification type  |
| SubagentStart      | Subagent spawned                          | Agent type         |
| SubagentStop       | Subagent finishes                         | Agent type         |
| Stop               | Claude finishes responding                | (none)             |
| TeammateIdle       | Agent team teammate about to idle         | (none)             |
| TaskCompleted      | Task being marked complete                | (none)             |
| ConfigChange       | Config file changes during session        | Config source      |
| PreCompact         | Before context compaction                 | manual/auto        |
| SessionEnd         | Session terminates                        | Reason             |

### Hook Types
1. **command**: Shell script (most common)
2. **prompt**: Single-turn LLM evaluation (yes/no decision)
3. **agent**: Multi-turn subagent with tool access for verification

### Exit Codes
- **0**: Action proceeds (stdout added to context for SessionStart/UserPromptSubmit)
- **2**: Action blocked (stderr fed back to Claude as feedback)
- **Other**: Action proceeds (stderr logged but not shown to Claude)

### Hook Configuration Locations
- `~/.claude/settings.json` -- all projects
- `.claude/settings.json` -- single project (committable)
- `.claude/settings.local.json` -- single project (gitignored)
- Managed policy settings -- organization-wide
- Plugin hooks.json -- when plugin enabled
- Skill/agent frontmatter -- while active

### Common Hook Patterns
1. **Auto-format after edits**: PostToolUse + Edit|Write matcher -> prettier
2. **Block protected files**: PreToolUse + Edit|Write -> check against patterns
3. **Re-inject context after compaction**: SessionStart + compact matcher
4. **Desktop notifications**: Notification event
5. **Audit logging**: PostToolUse + Bash -> log commands
6. **Quality gates**: Stop hook -> verify tests pass before allowing completion

### Key Principle
- CLAUDE.md instructions are advisory (Claude may ignore under pressure)
- Hooks are deterministic and guaranteed to execute
- Use hooks for things that MUST happen every time

### PreToolUse Hook for Git Commit Interception (Researched 2026-02-28)
- Matcher `"Bash"` fires on all Bash tool calls; filter by parsing `tool_input.command` in the script
- To block a tool call: output JSON with `permissionDecision: "deny"` on stdout and exit 0
- Exit code 2 also blocks, but JSON output gives better feedback to Claude (reason displayed)
- `$CLAUDE_PROJECT_DIR` env var available for referencing project-relative scripts
- There is NO native PreCommit/PostCommit hook event in Claude Code (feature request #4834 was closed as "not planned")
- Workaround: PreToolUse + Bash matcher + grep for "git commit" in the command
- Hook scripts receive full JSON on stdin; use `jq` to extract fields
- Multiple hooks on same matcher run in parallel; identical handlers are deduplicated

### Hook Types Added Since Initial Research
- **HTTP hooks** (`type: "http"`): POST to a URL, response body controls decision
- **Agent hooks** (`type: "agent"`): Multi-turn subagent with Read/Grep/Glob for verification
- **Prompt hooks** (`type: "prompt"`): Single-turn LLM yes/no decision
- `once: true` field: hook runs only once per session then removed (skills only)
- `async: true` field: hook runs in background without blocking (command hooks only)
- `statusMessage` field: custom spinner text while hook runs

### Git Hook Strategy for This Project (Decided 2026-02-28)
- Use `.githooks/` directory with `git config core.hooksPath .githooks`
- Rejected `pre-commit` Python framework: too heavy for one custom hook, adds dependencies
- Rejected raw `.git/hooks/`: not version-controlled
- One-time setup via `scripts/install-hooks.sh`
- Scanner at `src/safety/pii_scanner.py` -- stdlib only, no pip deps
- Pattern config in Python module (not YAML) to avoid PyYAML dependency
- Design doc: `/.project/research/E-006-precommit-design.md`
