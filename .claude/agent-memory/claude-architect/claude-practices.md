# Claude Code Best Practices -- Detailed Reference

## CLAUDE.md File Design

### What Belongs in CLAUDE.md
- Bash commands Claude cannot guess (build, test, lint, deploy)
- Code style rules that differ from language defaults
- Testing instructions and preferred test runners
- Repository etiquette (branch naming, PR conventions)
- Architectural decisions specific to the project
- Developer environment quirks (required env vars, local setup)
- Common gotchas or non-obvious behaviors

### What Does NOT Belong in CLAUDE.md
- Anything Claude can figure out by reading code
- Standard language conventions Claude already knows
- Detailed API documentation (link to docs instead)
- Information that changes frequently
- Long explanations or tutorials
- File-by-file descriptions of the codebase
- Self-evident practices like "write clean code"

### Size and Format
- Keep under ~500 lines (ideally under 150 for maximum adherence)
- For each line, ask: "Would removing this cause Claude to make mistakes?" If not, cut it
- No required format, but keep it short and human-readable
- Use emphasis ("IMPORTANT", "YOU MUST") to improve adherence on critical rules
- Use `@path/to/import` syntax to import additional files
- Check into git so team can contribute; the file compounds in value over time

### File Placement Hierarchy
1. **Managed policy**: Organization-wide (IT/DevOps managed)
2. **Project root**: `./CLAUDE.md` or `./.claude/CLAUDE.md` (team-shared)
3. **Project rules**: `./.claude/rules/*.md` (modular, topic-specific)
4. **User memory**: `~/.claude/CLAUDE.md` (personal, all projects)
5. **Project local**: `./CLAUDE.local.md` (personal, this project only, auto-gitignored)
6. **Auto memory**: `~/.claude/projects/<project>/memory/` (Claude's own notes)

### Loading Behavior
- Parent directory CLAUDE.md files load at launch (up to root)
- Child directory CLAUDE.md files load on-demand when Claude works in those dirs
- Rules files (.claude/rules/*.md) load with same high priority as CLAUDE.md
- More specific instructions take precedence over broader ones

## Modular Rules (.claude/rules/)

### Structure
- Place .md files in `.claude/rules/` directory
- All .md files are discovered recursively (subdirectories supported)
- Files can have YAML frontmatter with `paths:` field for scoping
- Rules without paths load unconditionally
- Supports glob patterns: `**/*.ts`, `src/**/*`, `*.{ts,tsx}`
- Symlinks are supported for sharing rules across projects

### Organization Best Practices
- Each file covers one topic (code-style.md, testing.md, security.md)
- Use descriptive filenames
- Use conditional path rules sparingly
- Organize with subdirectories (frontend/, backend/)

## Context Management

### The #1 Constraint: Context Window
- Performance degrades as context fills
- Context window is the most important resource to manage
- Use /clear between unrelated tasks
- Auto-compaction triggers at ~95% capacity
- Use subagents for exploration (keeps main context clean)
- Track context usage with custom status line

### Anti-patterns
- Kitchen sink session: mixing unrelated tasks without /clear
- Correcting over and over: after 2 failed corrections, /clear and rephrase
- Over-specified CLAUDE.md: important rules get lost in noise
- Trust-then-verify gap: always provide verification (tests, scripts)
- Infinite exploration: scope investigations narrowly or use subagents

## Verification is the Highest-Leverage Practice
- Include tests, screenshots, or expected outputs so Claude can check itself
- Without success criteria, Claude might produce plausible but incorrect output
- Invest in making verification rock-solid (test suite, linter, bash checks)

## Workflow Best Practices
1. Explore first (Plan Mode): read files and understand
2. Plan: create detailed implementation plan
3. Implement: switch to Normal Mode, code against the plan
4. Commit: descriptive message and PR
- Skip planning for small, clear changes (typos, renames)
