# MCP Research Findings (E-009-R-05, E-009-R-06)

Date: 2026-03-01

## Key Decisions

### MCP Ecosystem (R-05)
- **None of the four evaluated MCP servers are recommended today.**
- docker/mcp: Bash + docker compose sufficient. GPL + Docker socket risk not worth it.
- chrome-devtools-mcp: WebFetch sufficient for server-rendered Jinja2 dashboard. Revisit
  only if JS-rendered charts added to E-004.
- GitNexus (CodeGraphContext representative): Excellent tool but codebase too small (<20
  files). Promote-trigger: ~100 Python files. Potential skills conflict in .claude/skills/.
- SDL-MCP: Solo project, 0 forks. Not recommended at any stage vs. GitNexus.

### Git/GitHub Integration (R-06)
- **GitNexus is a code graph tool, NOT a git history tool.** R-06's named tool was wrong.
- **`git` CLI via Bash is sufficient today** (no GitHub remote exists).
- **github/github-mcp-server is worth adopting when a GitHub remote is established.**
  - 27,400 stars, 3,700 forks, maintained by GitHub Inc.
  - Genuinely superior to `gh` CLI for structured agent queries (typed schemas, no parsing)
  - Requires: GitHub PAT in .env, GitHub remote
  - Story estimate: half a session to register in settings.json + verify

## Promote Triggers
1. GitHub remote established --> add story: register github/github-mcp-server in settings.json;
   update IDEA-003 to fold this in as the work-management infrastructure choice.
2. E-004 adds JS-rendered charts --> revisit chrome-devtools-mcp.
3. src/ exceeds ~100 Python files --> run GitNexus follow-up spike.

## Pattern: MCP Worth It vs. Not
Worth it: typed schemas that eliminate bash output parsing; high-adoption servers (thousands
of stars); servers the project CANNOT replicate with bash + --format json.
Not worth it: duplicate of bash + json flags; scale problems not yet present; solo projects
with 0 forks; Node.js runtime in a Python-first project.
