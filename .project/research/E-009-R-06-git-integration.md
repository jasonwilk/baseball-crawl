# E-009-R-06: Research Report -- Git and GitHub Integration: gh CLI vs. MCP

**Spike**: E-009-R-06
**Date**: 2026-03-01
**Researcher**: product-manager (PM executing in-session)
**Output path**: `.project/research/E-009-R-06-git-integration.md`

---

## Summary

This report evaluates two approaches for agent access to git history and repository
metadata: (1) the `gh` CLI via Bash, and (2) abhigyanpatwari/GitNexus or github/github-mcp-server
as MCP-based alternatives.

**Key finding**: GitNexus is not a git history tool -- it is a code graph tool (see E-009-R-05
for evaluation). The true MCP alternative to `gh` CLI for GitHub data is **github/github-mcp-server**
(GitHub's official MCP Server, 27,400 stars). This report evaluates both.

**Conclusion**: `gh` CLI via Bash is sufficient for all realistic agent use cases at this
project's scale and current state (no GitHub remote). When a GitHub remote is established,
`github/github-mcp-server` is worth adopting -- it is genuinely superior to `gh` CLI for
structured agent queries. But that decision should be deferred until the remote exists.

---

## Section 1: `gh` CLI Capabilities

### 1.1 What `gh` CLI Exposes That Plain `git` Cannot

Plain `git` is local-only. It knows nothing about GitHub-side concepts: pull requests,
issues, releases, Actions workflows, secrets, project boards, code search across GitHub's
index, or repository metadata (stars, forks, topics). `gh` CLI bridges the local git
repo to the GitHub platform API.

Specifically, `gh` adds:
- Pull request management (create, review, merge, list, checkout)
- Issue tracking (create, edit, close, list, comment)
- GitHub Actions (run, view, enable/disable workflows)
- Release artifacts (create, download, verify)
- Gist management
- Project boards (v2 Projects -- items and fields)
- Repository metadata queries (stars, forks, description, topics, visibility)
- Code search across GitHub's index (`gh search code`)
- Secret and variable management (org + repo level)

What `gh` still cannot do that github/github-mcp-server can: structured, typed tool access
with predictable JSON schemas, integration with multi-step agentic workflows without shell
parsing, and access to GitHub Actions insights and Dependabot security alerts as tool calls.

### 1.2 Representative JSON Output Examples

**Example 1: List commits on a branch with JSON output**
```
gh api repos/{owner}/{repo}/commits \
  --field ref=main \
  --field per_page=5 \
  --jq '[.[] | {sha: .sha[0:7], message: .commit.message, author: .commit.author.name, date: .commit.author.date}]'
```
Output:
```json
[
  {"sha": "a1b2c3d", "message": "feat(E-009-02): add docker-compose.yml", "author": "Jason", "date": "2026-03-01T12:00:00Z"},
  {"sha": "e4f5g6h", "message": "fix(E-006-04): pii scanner regex", "author": "Jason", "date": "2026-02-28T18:00:00Z"}
]
```

**Example 2: Search commits by story ID in message**
```
git log --grep="E-005" --pretty=format:'{"hash":"%h","message":"%s","date":"%ai"}' | jq -s '.'
```
Note: This is `git` (local) not `gh`, but is the reliable method for commit message grep.
`gh` cannot grep commit messages without an API call for each commit.

**Example 3: List pull requests with JSON**
```
gh pr list --state all --json number,title,state,mergedAt,headRefName \
  --jq '[.[] | select(.title | test("E-009"))]'
```
Output:
```json
[
  {"number": 12, "title": "feat(E-009-02): docker compose base environment", "state": "MERGED", "mergedAt": "2026-03-01T..."}
]
```

### 1.3 Output Parseability for Agents

With `--json` and `--jq` flags, `gh` output is reliably machine-readable. The `--json`
flag takes a comma-separated list of fields to include, and `--jq` allows inline jq
expressions to transform the output. This eliminates fragile line-by-line text parsing.

For local git operations (commit log, blame, diff), `git log --pretty=format` with
`%h`, `%s`, `%ai`, `%an` format codes produces structured, easily-parseable output. A
`git log --grep="E-009" --pretty=format:'{"hash":"%h","subject":"%s"}' | jq -s '.'`
pattern works cleanly.

**Verdict on parseability**: The agent can parse both `gh --json` and `git --pretty=format`
output reliably via the Bash tool, especially when piped through `jq`. No fragile string
parsing required.

### 1.4 Authentication and Docker Container Compatibility

`gh` supports three authentication methods:
1. Interactive: `gh auth login` (requires a terminal; not useful for automated agent sessions)
2. Environment variable: `GITHUB_TOKEN` or `GH_TOKEN` (set in `.env`, passed to Docker)
3. Enterprise: `GH_ENTERPRISE_TOKEN`

**Docker container compatibility**: Confirmed compatible. The standard pattern for
Claude Code in Docker is to pass `GH_TOKEN` via environment variable in `.env` or
`docker-compose.yml`. As of late 2025, `gh` was removed from Claude Code's
`disallowed_tools` list (`"disallowed_tools": ["Bash(gh:*)"]` removed from startup.json).
However, `gh` is not installed by default in Docker containers -- it must be explicitly
added to the Dockerfile.

**Current project state**: The project has no GitHub remote yet, so `gh` authentication
is moot until a remote is established.

---

## Section 2: GitNexus and github/github-mcp-server

### 2.1 GitNexus Clarification

The spike named `abhigyanpatwari/GitNexus` as the MCP git server to evaluate. Research
found that GitNexus is a **codebase knowledge graph tool**, not a git history/repository
metadata tool. It indexes symbol dependencies and execution flows. It does not expose:
git log, blame, diff, commit history queries, or GitHub API data.

GitNexus is evaluated in full in E-009-R-05 under "CodeGraphContext representative."
It is not the right tool for git history access.

The correct MCP representative for git/GitHub data access is **github/github-mcp-server**
(GitHub's official MCP Server). This is evaluated below.

### 2.2 github/github-mcp-server: What It Does

GitHub's official MCP Server (github.com/github/github-mcp-server, Apache-2.0). Provides
structured tool access to GitHub's platform API across these toolsets:
- `repos`: browse code, search files, analyze commits, understand project structure
- `issues`: create, update, manage issues and comments
- `pull_requests`: create, review, merge, list
- `actions`: monitor workflow runs, analyze failures, manage releases
- `code_security`: Dependabot alerts, security advisories
- `projects`: GitHub Projects v2 -- items, fields, boards
- `discussions`, `notifications`, `teams`

Key tool types for agent git workflows:
- `get_file_contents` -- read any file from a remote repo without cloning
- `list_commits` -- structured commit list with filtering
- `get_commit` -- detailed single commit (diff, files changed, stats)
- `search_code` -- semantic code search across GitHub's index
- `search_commits` -- search commit messages across a repository
- `create_pull_request`, `list_pull_requests` -- PR workflow automation

### 2.3 Current Status

27,400 stars, 3,700 forks, 755 commits, created 2025-03-04. Actively maintained by GitHub
(the company). Deployed as both local MCP server and a remote HTTP server (generally
available as of 2025-09-04). Supports GitHub Enterprise Server via `GITHUB_HOST` env var.

### 2.4 Setup Cost

- Install: `npm install -g @github/mcp-server` (or use the Docker image)
- Register in `.claude/settings.json` under `mcpServers`
- Authentication: `GITHUB_PERSONAL_ACCESS_TOKEN` in environment (already in `.env`)
- **Requires a GitHub remote**: All tools query GitHub's API. None work against a
  local-only repo with no remote.

### 2.5 Comparison to gh CLI

For each capability relevant to baseball-crawl:

| Query | `gh` CLI via Bash | github/github-mcp-server |
|-------|-------------------|--------------------------|
| Commit search by message | `git log --grep="E-009"` (local, fast) | `search_commits` (remote, requires push) |
| Files changed in a commit | `git show --stat <sha>` | `get_commit` (structured JSON) |
| PR list for a branch | `gh pr list --json ...` | `list_pull_requests` (typed tool) |
| Issue tracking | `gh issue list --json ...` | `list_issues` (typed tool) |
| Code search | Not available locally | `search_code` (GitHub index) |
| Actions status | `gh run list --json ...` | `list_workflow_runs` (typed tool) |
| Epic/story cross-ref | Manual grep + git log | Automated with `search_commits` + grep |

**Where MCP is better**: Structured typed tool calls with defined schemas. The agent does
not parse shell output -- it receives JSON with guaranteed field names. For multi-step
workflows (find commits for a story -> check which files changed -> verify AC) the MCP
server is dramatically cleaner.

**Where `gh` CLI is better**: Local-only queries (works before a remote exists, works
offline). Simpler for one-off bash queries that do not need structured output.

### 2.6 Unique Capabilities of github/github-mcp-server

1. **`search_code`**: GitHub's semantic code search across the entire repository index.
   Not available via `gh` CLI in the same structured form.
2. **Dependabot + security alerts**: `list_dependabot_alerts`, `get_vulnerability_alert`.
   Not available via `gh` CLI without additional flags.
3. **GitHub Projects v2**: Full project board management as tool calls.
4. **Actions workflow intelligence**: `get_job_logs`, workflow run analysis. `gh` CLI
   can access this but output parsing is more fragile.
5. **Remote server mode**: Can be registered as an HTTP MCP server rather than a local
   process -- agents call it without starting a subprocess.

---

## Section 3: Fit Assessment

### 3.1 Agent Workflows That Would Benefit from Richer Git Access

**Workflow 1: Post-story commit verification (PM or general-dev)**
- Task: Verify that story E-009-02 has committed changes to the expected files.
- Query: Find commits with "E-009-02" in message; check files changed.
- With `git`/`gh`: `git log --grep="E-009-02" --pretty=format:"%h %s" && git show --stat <sha>`
- With MCP: `search_commits(query="E-009-02") -> get_commit(sha=...)` -- no parsing needed.
- Frequency: Per-story completion (weekly to monthly).

**Workflow 2: Story-to-commit cross-reference (PM)**
- Task: Identify which stories have DONE status but no corresponding commits (workflow gaps).
- Query: For each DONE story, check git log for story ID in commit messages.
- With `git`/bash: A Python script reading story files + `git log --oneline --grep` calls.
  Already feasible, somewhat fragile to write correctly.
- With MCP: `search_commits` across all stories in batch. Cleaner agent invocation.
- Frequency: Infrequent (audit/review mode only).

**Workflow 3: Impact assessment before a PR (general-dev)**
- Task: Before merging a branch, identify which source files changed and which other
  agents/stories are affected.
- Query: `git diff main...HEAD --name-only` + cross-reference against epic story files.
- With `git`: Already works via Bash today. No gap.
- With MCP: `list_pull_requests` + `get_pull_request_files` -- useful when a PR exists.
- Frequency: Per-PR (none currently -- no GitHub remote).

### 3.2 Does `gh` CLI Handle These Workflows?

- Workflow 1: Yes, with `git` CLI (not `gh`). `git log --grep` is local and works today.
- Workflow 2: Yes, with a Python script + `git log`. More verbose but no MCP needed.
- Workflow 3: Yes, with `git diff`. No GitHub remote needed.

All three workflows work today without a GitHub remote, using local `git` commands.

### 3.3 Frequency of These Workflows

- Workflow 1 (commit verification): Occasional -- per story completion, ~weekly.
- Workflow 2 (cross-reference audit): Rare -- infrequent audits.
- Workflow 3 (impact assessment): Per-PR -- currently zero frequency (no remote).

### 3.4 Offline vs. Remote Requirements

| Approach | Works offline (no GitHub remote) | Requires connected GitHub remote |
|----------|-----------------------------------|----------------------------------|
| `git` CLI via Bash | Yes -- all local operations | No |
| `gh` CLI via Bash | Partial -- local git works; GitHub API features need remote | For API features |
| github/github-mcp-server | No -- all tools call GitHub API | Yes |

**Current project state**: No GitHub remote. All three git workflows above work today
with local `git` commands. `gh` CLI and github/github-mcp-server are both future-state.

---

## Section 4: Trade-off Summary

| Dimension | `gh` CLI via Bash | github/github-mcp-server |
|-----------|-------------------|--------------------------|
| Setup cost | Low (install `gh`, set GH_TOKEN) | Moderate (npm install, settings.json, PAT) |
| Requires GitHub remote | For GitHub features, yes | Yes, always |
| Output parseability | Good with `--json --jq` | Excellent (typed tool schemas) |
| Agent ergonomics | Good (familiar Bash pattern) | Better (typed tool calls, no output parsing) |
| Maintenance burden | Low (GitHub Inc. maintains `gh`) | Low (GitHub Inc. maintains MCP server) |
| Unique capabilities | None vs. raw git | code search, Dependabot, Projects v2, remote mode |
| Works today (no remote) | Local git works; GitHub features blocked | Nothing works |
| Adoption signal | Ubiquitous (part of standard dev tooling) | 27,400 stars, 3,700 forks -- very high |

---

## Section 5: Verdict

**`gh` CLI via Bash**: **Sufficient for current state.** The project has no GitHub remote.
All realistic git queries (commit log, file history, grep-by-story-ID) work today via
local `git` commands in the Bash tool. `gh` adds GitHub platform features, but those
features are blocked until a remote exists.

**github/github-mcp-server**: **Worth adopting when a GitHub remote is established.**

This is a stronger recommendation than "worth a follow-up spike." The server is:
- Maintained by GitHub Inc. (not a solo project)
- Extremely well-adopted (27,400 stars, 3,700 forks)
- Genuinely superior to `gh` CLI for structured agent queries (typed schemas, no
  output parsing, multi-step workflow support)
- Free of runtime dependency issues (can run as remote HTTP server)
- Directly relevant to the PM's primary workflow: story-to-commit cross-referencing

The only reason not to adopt it today is that **the project has no GitHub remote**, and
the server requires one. Once a remote is established (which IDEA-003 tracks), this
should be one of the first infrastructure additions.

**GitNexus**: Not applicable to this spike. Evaluated in E-009-R-05. It is a code graph
tool, not a git history tool.

---

## Recommendation to PM

**No action today.** The project has no GitHub remote. Local `git` CLI via Bash handles
all current git queries.

**When a GitHub remote is established**:
1. Promote IDEA-003 (Work Management as Agent Interface) to an epic.
2. Include a story to add `github/github-mcp-server` to `.claude/settings.json`.
3. Add `GITHUB_PERSONAL_ACCESS_TOKEN` to `.env.example` and project credential docs.
4. The story is small (half a session): install server, register in settings, verify
   that an agent can call `search_commits` and `list_pull_requests` successfully.

**Note for PM**: IDEA-003 currently reads "requires product-manager + claude-architect
collaboration; tool evaluation (GitHub, Plane, Vikunja) is first research spike." Given
the findings here, the tool evaluation spike should include github/github-mcp-server as
the work management infrastructure choice -- it is the clear winner for GitHub-native
work tracking and already available. No additional evaluation of Plane or Vikunja is
likely needed if GitHub is the remote.

---

**Sources:**
- [abhigyanpatwari/GitNexus](https://github.com/abhigyanpatwari/GitNexus)
- [github/github-mcp-server](https://github.com/github/github-mcp-server)
- [GitHub CLI Manual](https://cli.github.com/manual/)
- [GitHub MCP Server Public Preview Announcement](https://github.blog/changelog/2025-04-04-github-mcp-server-public-preview/)
- [Remote GitHub MCP Server Generally Available](https://github.blog/changelog/2025-09-04-remote-github-mcp-server-is-now-generally-available/)
- [GitMCP](https://gitmcp.io/)
- [mcp-server-git on PyPI](https://pypi.org/project/mcp-server-git/)
- [cyanheads/git-mcp-server](https://github.com/cyanheads/git-mcp-server)
