# E-112-05: CLAUDE.md Placement Migration

## Epic
[E-112: Context Layer Optimization](./epic.md)

## Status
`DONE`

## Description
After this story is complete, every remaining CLAUDE.md section that has a more appropriate delivery mechanism will have been moved there. Four new scoped rules are created (including a context-layer guard rule to prevent regression), two existing rules are extended, six pure duplicates are removed, one section is relocated, and the context-fundamentals skill is updated with post-E-112 actuals. CLAUDE.md retains only genuinely ambient project identity content (~150 lines).

## Context
E-112-02 trims sections that are already duplicated in existing scoped locations. This story completes the placement work by migrating sections that have no scoped home yet (creating new rules) and removing sections that duplicate content in rules loaded via file-path scoping. The placement framework: CLAUDE.md holds genuinely ambient project identity; everything else goes to the mechanism that delivers it to the right agent at the right time.

## Acceptance Criteria

### New scoped rules
- [ ] **AC-1**: A new rule `.claude/rules/dependency-management.md` exists, scoped to `requirements*`, `pyproject.toml`, `.python-version`, `Dockerfile`, `.devcontainer/devcontainer.json`. Contains the Dependency Management section content (pip-tools workflow, file layout table, common operations) and the Python Version Policy section content (source of truth, sync locations, upgrade criteria, verification steps). The Dockerfile and devcontainer.json paths are included because the Python Version Policy requires all four sync locations to be updated atomically. CLAUDE.md replaces both sections with a ~2-line summary + pointer.
- [ ] **AC-2**: A new rule `.claude/rules/http-discipline.md` exists, scoped to `src/http/**`, `src/gamechanger/**`, `src/pipeline/**`, `scripts/*crawl*`, `scripts/*fetch*`. Contains the HTTP Request Discipline section content (headers & identity, session behavior, rate limiting, pattern hygiene, implementation notes). The existing `crawling.md` rule content is absorbed into this file (merged, not duplicated). The old `crawling.md` is deleted. CLAUDE.md replaces the section with a ~2-line summary + pointer. The expanded paths preserve `crawling.md`'s original coverage of pipeline and script files that make HTTP requests.
- [ ] **AC-3**: A new rule `.claude/rules/app-troubleshooting.md` exists, scoped to `docker-compose.yml`, `Dockerfile`, `requirements.txt`, `migrations/**`. Contains the App Troubleshooting section content (stack management, health check, logs, rebuild, unreachable diagnosis). CLAUDE.md replaces the full section with a ~3-line summary: a 1-line "rebuild after `src/` changes" reminder + pointer to the rule for the full troubleshooting guide. The tighter scope avoids injecting 39 lines on every `src/**` edit while still triggering on the files most likely to break the running app.

### Existing rules extended
- [ ] **AC-4**: `.claude/rules/proxy-boundary.md` is extended with the Bright Data subsection content from CLAUDE.md (~40 lines: env vars, SSL behavior, sticky sessions, diagnostics). CLAUDE.md replaces the Bright Data subsection with a ~2-line summary + pointer to `proxy-boundary.md`. The mitmproxy subsection was already handled by E-112-02.
- [ ] **AC-5**: `.claude/rules/python-style.md` is extended with the Code Style section content from CLAUDE.md (type hints, docstrings, dataclasses, pathlib, logging). CLAUDE.md removes the Code Style section entirely (fully covered by the scoped rule).

### Pure duplicate removals
- [ ] **AC-6**: The Testing section (~4 lines) is removed from CLAUDE.md. Content is already in `.claude/rules/testing.md`.
- [ ] **AC-7**: The Ideas content within the Project Management section (~20 lines: ideas vs. epics distinction, promotion triggers, review cadence, adding an idea) is removed from CLAUDE.md. Content is already in `.claude/rules/ideas-workflow.md` or equivalent.
- [ ] **AC-8**: The Main Session Compliance subsection (~6 lines) is removed from CLAUDE.md. Content is already in `.claude/rules/agent-team-compliance.md`.
- [ ] **AC-9**: The Workflow Contract subsection (~12 lines) is removed from CLAUDE.md. Content is already in `.claude/rules/workflow-discipline.md`.
- [ ] **AC-10**: The Proxy Lifecycle Commands subsection (~17 lines under Proxy Boundary) is removed from CLAUDE.md. Content is already in `.claude/rules/proxy-boundary.md`.

### Relocation
- [ ] **AC-11**: The Statusline section (~10 lines) is moved from CLAUDE.md to `.claude/hooks/README.md`. CLAUDE.md removes the section entirely.

### Existing rule scope refinement
- [ ] **AC-12**: `.claude/rules/ideas-workflow.md` has `epics/**` added to its `paths:` frontmatter (in addition to existing `.project/ideas/**` and `.project/templates/idea-template.md`). This ensures the "ideas vs. epics" guidance fires when agents create or modify epics, not only when they work in the ideas directory.

### Context-layer guard rule
- [ ] **AC-13**: A new rule `.claude/rules/context-layer-guard.md` exists, scoped to `CLAUDE.md`, `.claude/rules/*.md`, `.claude/agent-memory/*/MEMORY.md`. Contains: (a) the placement framework (what belongs in CLAUDE.md vs. rules vs. skills vs. agent defs vs. memory), (b) CLAUDE.md line target (~150 lines -- genuinely ambient project identity only; do not add content that belongs in a scoped rule, skill, or agent def), (c) MEMORY.md line target (under 150 lines -- index only, content beyond line 200 is silently truncated; extract detailed content to topic files in the same directory), (d) new rules must have `paths:` frontmatter (universal rules must justify why they need to load on every interaction), (e) before creating a new rule file, consider whether the content fits in an existing thematic rule (extend rather than create); single-purpose rules under 15 lines are candidates for consolidation. This rule is advisory (agents see the constraint and self-correct) not mechanical enforcement.

### Context-fundamentals skill update
- [ ] **AC-14**: `.claude/skills/context-fundamentals/SKILL.md` is updated with post-E-112 actuals: (a) the ambient baseline number (line 28 and Section 1 description) reflects the new total (~380 lines, not ~1,000-1,270), (b) the budget table (lines 74-84) has correct per-source line counts for CLAUDE.md, rules files, agent defs, and MEMORY.md, (c) a new "Triggered rules" row is added to the budget table showing ~0-400 lines variable load depending on files touched (highest for `src/gamechanger/` edits, lowest for context-layer edits), with a brief note explaining the variation, (d) the worked example (lines 147-176) is refreshed with post-E-112 ambient subtotal and total — the implementer must measure actual line counts with `wc -l` after E-112-03/04 land (do not cite estimates), and (e) Decision 1 ("Load a Full Research Artifact or Rely on MEMORY.md?") is updated to account for MEMORY.md topic file indirection -- when MEMORY.md is an index pointing to topic files, the agent should load the topic file (smaller than a research artifact, more current than a summary).

### Invariants
- [ ] **AC-15**: No information is deleted -- every removed line exists in the destination location.
- [ ] **AC-16**: CLAUDE.md is ~150 lines or fewer after all changes.
- [ ] **AC-17**: All existing tests pass after the changes.
- [ ] **AC-18**: All new and extended rule files have correct frontmatter `paths:` scoping.

## Technical Approach
This story follows the same mechanical pattern as E-112-02: for each section, verify the destination contains (or will contain) the content, then replace/remove the CLAUDE.md section. The key difference is that some destinations must be created first (new rules) or extended (existing rules) before the CLAUDE.md section can be removed.

Ordering within the story:
1. Create/extend destination files (AC-1 through AC-5, AC-11, AC-13 guard rule)
2. Remove pure duplicates from CLAUDE.md (AC-6 through AC-10)
3. Replace migrated sections with summary + pointer (AC-1 through AC-4)
4. Refine existing rule scoping (AC-12)
5. Verify line count and test suite (AC-16, AC-17, AC-18)
6. Update context-fundamentals skill with post-E-112 actuals (AC-14 -- must be LAST, after all CLAUDE.md changes are finalized, so line counts are stable)

Reference files to verify for duplicate removal:
- Testing → `.claude/rules/testing.md`
- Ideas → check for `ideas-workflow.md` or equivalent in `.claude/rules/`
- Compliance → `.claude/rules/agent-team-compliance.md`
- Workflow Contract → `.claude/rules/workflow-discipline.md`
- Proxy lifecycle → `.claude/rules/proxy-boundary.md`

When absorbing `crawling.md` into `http-discipline.md` (AC-2), verify no other files reference `crawling.md` and update any that do.

## Dependencies
- **Blocked by**: E-112-02 (both edit CLAUDE.md; E-112-02's trims must land first)
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/dependency-management.md` (create)
- `.claude/rules/http-discipline.md` (create -- absorbs `crawling.md`)
- `.claude/rules/app-troubleshooting.md` (create)
- `.claude/rules/context-layer-guard.md` (create -- regression prevention rule)
- `.claude/rules/crawling.md` (delete -- absorbed into `http-discipline.md`)
- `.claude/rules/proxy-boundary.md` (modify -- extend with Bright Data content)
- `.claude/rules/python-style.md` (modify -- extend with Code Style content)
- `.claude/hooks/README.md` (modify -- add Statusline content)
- `CLAUDE.md` (modify -- remove/replace migrated sections)
- `.claude/skills/context-fundamentals/SKILL.md` (modify -- update budget table, worked example, Decision 1)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing tests
- [ ] CLAUDE.md contains only genuinely ambient project identity content
- [ ] All new rules have correct file-path scoping in frontmatter

## Notes
- This story depends on E-112-02 completing first. E-112-02 handles the first round of trims (Proxy Boundary mitmproxy, Script Aliases, Terminal Modes, Shell Environment, Codex Bootstrap, GameChanger API auth). This story handles everything else.
- The Bright Data subsection is handled here (not in E-112-02) because it requires extending `proxy-boundary.md` with new content, not just pointing to existing content.
- When removing the Ideas content from CLAUDE.md Project Management, verify the destination rule exists. If no `ideas-workflow.md` exists, check if the content is covered by other rules or the PM agent definition before removing.
- Archived files (`.project/archive/`) are frozen historical records -- do NOT update references in archived files.
- After this story, CLAUDE.md should read like a project README: purpose, scope, stack, deployment, security rules, key directories, agent ecosystem, git conventions. Everything else is in scoped delivery.
