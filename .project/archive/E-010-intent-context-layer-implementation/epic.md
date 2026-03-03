# E-010: Intent/Context Layer Implementation

## Status
`ABANDONED`

## Overview
Implements the hybrid intent/context layer recommended by E-008: three project-adapted skill files in Phase 1 (immediate), followed by directory-scoped intent nodes at `src/` module boundaries in Phase 2 (triggered when E-002 and E-003 are DONE). The goal is to reduce the amount of contextual scaffolding that story authors must repeat in every Technical Approach section by placing invariants closer to where agents actually work.

## Background & Context
E-008 researched and recommended a two-phase hybrid approach (E-008 decision log: `/.project/research/E-008-decision-log.md`, approved 2026-02-28):

- **Phase 1** (2-4 hours, no preconditions): Copy and adapt three specific skill files from the muratcankoylan Agent Skills for Context Engineering repository into `.claude/skills/`. Each file is adapted with baseball-crawl-specific examples and conventions, not a verbatim copy. Skills to adopt: `filesystem-context`, `multi-agent-patterns`, `context-fundamentals`.

- **Phase 2** (4-6 hours, triggered by E-002 + E-003 DONE): Write intent nodes -- directory-scoped CLAUDE.md files -- at semantic module boundaries. Target directories: `src/`, `src/gamechanger/`, `src/http/`, `src/safety/`, `src/db/` (or equivalent), `epics/`, `tests/`. Phase 2 cannot start until those directories are substantially populated by E-002 and E-003. Writing intent nodes against a codebase that does not yet exist produces stale, misleading documents.

- **Integration story** (follows Phase 2): Update agent definitions for orchestrator, general-dev, and data-engineer to explicitly reference relevant skills and intent nodes with named trigger conditions. Update the Definition of Done template to include intent node maintenance responsibility.

**No expert consultation required** -- the E-008 recommendation document (by claude-architect) provides sufficient implementation guidance for all Phase 1 stories. Phase 2 stories may require a brief consultation with claude-architect at the time they are unblocked to confirm the final module structure matches what E-002/E-003 delivered.

## Goals
- Three skill files exist in `.claude/skills/` (one per skill subdirectory), each adapted to baseball-crawl conventions with project-specific examples.
- Agent definitions for orchestrator, general-dev, and data-engineer reference at least one skill by name with a trigger condition.
- Directory-scoped `CLAUDE.md` intent nodes exist at all target `src/` module boundaries after E-002 and E-003 are DONE.
- The Definition of Done template includes a one-line intent node maintenance clause.
- A new story's Technical Approach section no longer needs to repeat module invariants already captured in an intent node.

## Non-Goals
- Installing the full muratcankoylan plugin (13 skills). Only 3 are being adopted.
- Writing intent nodes before `src/` modules exist (Phase 2 is explicitly deferred).
- Adding the `context-degradation`, `memory-systems`, or any other skill beyond the three specified.
- Creating a dedicated context-manager agent (rejected in E-008 as over-engineered).
- Changing the workflow contract established in E-007.
- Headless browser or Playwright tooling.

## Success Criteria
1. `.claude/skills/filesystem-context/SKILL.md` exists and contains a baseball-crawl-specific section describing how story files, epic files, and research artifacts implement the filesystem-context pattern.
2. `.claude/skills/multi-agent-patterns/SKILL.md` exists and contains a section describing baseball-crawl's orchestrator -> PM -> specialist chain and the telephone game risk.
3. `.claude/skills/context-fundamentals/SKILL.md` exists and contains a section describing baseball-crawl's context budget (what loads per session vs. per task).
4. Each skill file follows the muratcankoylan SKILL.md format: activation triggers, key concepts, practical implementation, references.
5. After Phase 2 (when E-002 + E-003 are DONE): intent nodes exist at all 7 target directories, each 100-300 lines covering purpose, entry points, contracts, anti-patterns, and downlinks.
6. After integration story: agent definitions for orchestrator, general-dev, and data-engineer contain a named skill reference with a trigger condition.

## Stories

### Phase 1 -- Skill Files (READY, dispatchable now)

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-010-01 | Write `filesystem-context` skill | DONE | None | claude-architect |
| E-010-02 | Write `multi-agent-patterns` skill | DONE | None | claude-architect |
| E-010-03 | Write `context-fundamentals` skill | DONE | None | claude-architect |

### Phase 2 -- Intent Nodes (DRAFT, blocked until E-002 + E-003 DONE)

Phase 2 stories are listed here for planning purposes but are NOT dispatchable. Story files for Phase 2 will be written when E-002 and E-003 both reach DONE status. The PM will conduct a brief consultation with claude-architect at that time to confirm the final module structure before writing the story files.

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-010-04 | Write intent nodes for `src/` module boundaries | ABANDONED | E-002 DONE, E-003 DONE | claude-architect |
| E-010-05 | Write intent nodes for `epics/` and `tests/` | ABANDONED | E-002 DONE, E-003 DONE | claude-architect |
| E-010-06 | Integration -- agent definitions + DoD template update | ABANDONED | E-010-04, E-010-05 | claude-architect |

## Technical Notes

### Skill File Format (from muratcankoylan pattern)

Each skill lives in its own directory: `.claude/skills/<skill-name>/SKILL.md`

The SKILL.md format uses four sections:
1. **Activation triggers**: When an agent should load this skill (specific task types, keywords, situations)
2. **Key concepts**: Core knowledge the skill provides (concise, scannable)
3. **Practical implementation**: Concrete guidance for applying the skill in this project
4. **References and related skills**: Links to related skills or external material

**Progressive disclosure**: Skills are loaded on demand, not pre-loaded into every session. Agent definitions reference skill names and trigger conditions; the agent reads the full SKILL.md only when the trigger fires. This keeps baseline session tokens low.

### Source Material for Phase 1

The muratcankoylan repository was researched in E-008-R-02 (summary at `/.project/research/E-008-R-02-agent-skills-summary.md`). The SKILL.md format is documented there. The three skills to adapt are:

- `filesystem-context` (Architectural category): Dynamic context discovery by storing context in files and loading on demand. Baseball-crawl already uses this pattern implicitly.
- `multi-agent-patterns` (Architectural category): Supervisor, peer-to-peer, and hierarchical agent coordination. The telephone game risk in supervisor architectures is directly applicable.
- `context-fundamentals` (Foundational category): What context is, its components, and why token efficiency matters. Foundational grounding for complex multi-file story work.

**Adaptation requirement**: Each skill must be adapted to include baseball-crawl-specific examples. Generic content copied verbatim from the muratcankoylan source has lower value than content that names specific files, agents, and patterns from this project.

### Phase 2 Intent Node Design

Intent nodes are directory-scoped CLAUDE.md files. When an agent opens a file in `src/gamechanger/`, Claude Code loads `src/gamechanger/CLAUDE.md` automatically (if it exists), providing localized context without requiring the root CLAUDE.md to enumerate all module invariants.

**Construction order**: Leaf-first. Write `src/gamechanger/CLAUDE.md` and `src/http/CLAUDE.md` before `src/CLAUDE.md`. Parent nodes summarize children; they do not re-read raw code.

**Node content template** (100-300 lines each):
- Purpose of this module (1-3 sentences)
- Entry points (which files callers use; what they should never call directly)
- Contracts and invariants (the things that must always be true: rate limiting, idempotency, credential handling, etc.)
- Anti-patterns (common mistakes agents make in this module)
- Downlinks (list of subdirectory CLAUDE.md files that provide deeper context)

**Target directories for Phase 2**:
- `src/CLAUDE.md` -- scope: all of src/; covers module organization, Python conventions, testing requirements
- `src/gamechanger/CLAUDE.md` -- covers credential handling, rate limiting, session factory contract, idempotency
- `src/http/CLAUDE.md` -- covers session factory, browser headers, rate limiting, no-parallel-requests rule
- `src/safety/CLAUDE.md` -- covers PII scanner, pre-commit hook, never-commit rules, synthetic test data marker
- `src/db/CLAUDE.md` (or equivalent path from E-003) -- covers ip_outs convention, soft referential integrity, migration conventions, local vs. prod DB
- `epics/CLAUDE.md` -- covers numbering scheme, status lifecycle, dispatch rules, PM as sole dispatcher
- `tests/CLAUDE.md` -- covers no-real-HTTP rule, pytest conventions, fixture patterns (tmp_path, no committed fixture files)

### Maintenance Protocol (for Phase 2 and integration story)

The integration story (E-010-06) must establish this rule in agent definitions and the Definition of Done template:

> If a story you complete changes a module's contracts, entry points, or file structure, you MUST update the relevant intent node (`CLAUDE.md` in that directory) as part of the story's definition of done. If no intent node exists yet, note in the story's completion comment that one should be created.

This prevents intent node drift -- the primary risk identified in E-008.

### Risk: Skills as Checkbox Noise

The recommendation (E-008) specifically calls out the risk that skill files get installed but never actively used. Mitigation: each agent definition that benefits from a skill must name the skill explicitly and include a trigger condition. This makes loading deliberate rather than ambient. The integration story (E-010-06) implements this for orchestrator, general-dev, and data-engineer.

## Open Questions
- What is the exact path for the database module in E-003's delivered structure? The intent node target is tentatively `src/db/` but E-003 may deliver a different path (e.g., `src/database/`, `src/storage/`). Confirm when E-003 is DONE before writing E-010-04.
- Should `api-scout` also have a skill reference added? The `filesystem-context` skill is relevant to api-scout's pattern of reading/writing docs/gamechanger-api.md. Assess during E-010-06.

## History
- 2026-02-28: Created following E-008-03 APPROVED decision. Authorized by E-008 decision log entry 2026-02-28. Phase 1 stories (E-010-01, 02, 03) are READY and dispatchable immediately. Phase 2 stories (E-010-04, 05, 06) are BLOCKED pending E-002 and E-003 completion.
- 2026-02-28: Phase 1 COMPLETE. E-010-01, E-010-02, E-010-03 all DONE. Three skill files created: `.claude/skills/filesystem-context/SKILL.md` (199 lines), `.claude/skills/multi-agent-patterns/SKILL.md` (211 lines), `.claude/skills/context-fundamentals/SKILL.md` (193 lines). Epic remains ACTIVE pending Phase 2 (blocked on E-002 + E-003).
- 2026-03-03: ABANDONED. Phase 1 (3/3 stories) is fully delivered and the skill files are in active use across agent definitions. Phase 2 (E-010-04/05/06) remains blocked on E-002 + E-003, which are both still ACTIVE with significant remaining work -- the blockers are not close to clearing. Additionally, the epic text is stale: Goals, Success Criteria, story descriptions, and Technical Notes all reference the orchestrator agent, which was deleted in E-030. The integration story (E-010-06) specifically names "orchestrator, general-dev, and data-engineer" as targets. Keeping a stale epic ACTIVE with no dispatchable stories and distant blockers adds confusion. The Phase 2 concept (directory-scoped CLAUDE.md intent nodes at src/ module boundaries) remains valid and has been captured as IDEA-005 for future promotion when E-002 and E-003 complete. At promotion time, the idea should be planned against the current architecture (no orchestrator, 6-agent ecosystem, docs-writer exists, documentation rules from E-028 in place).
