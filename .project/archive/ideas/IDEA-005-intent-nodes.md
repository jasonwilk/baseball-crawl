# IDEA-005: Directory-Scoped Intent Nodes at src/ Module Boundaries

## Status
`CANDIDATE`

## Summary
Write directory-scoped CLAUDE.md files ("intent nodes") at semantic module boundaries in `src/` and project directories. When an agent opens a file in `src/gamechanger/`, Claude Code loads `src/gamechanger/CLAUDE.md` automatically, providing localized context without requiring the root CLAUDE.md to enumerate all module invariants. This was Phase 2 of E-010 (Intent/Context Layer Implementation), which delivered Phase 1 (skill files) and was abandoned because the blockers for Phase 2 were not close to clearing and the epic text had gone stale.

## Why It Matters
Story authors currently repeat module invariants (credential handling rules, rate limiting, idempotency contracts, session factory usage, PII safety rules) in every Technical Approach section. Intent nodes would capture these invariants once, close to where agents actually work, reducing story boilerplate and making it harder for implementing agents to miss critical contracts.

The filesystem-context skill (`.claude/skills/filesystem-context/SKILL.md`) already teaches agents to load context on demand from files. Intent nodes are the natural next step: placing that context at the directory level where the code lives.

### Additional Dimensions (from intent-systems.com/blog/intent-layer, reviewed 2026-03-06)

The article "The Intent Layer" adds several dimensions beyond our original E-010 Phase 2 design:

- **LCA (Least Common Ancestor) placement**: Shared knowledge lives once at the shallowest node where it's always relevant. Prevents duplication and drift. We should apply this discipline when deciding what goes in `src/CLAUDE.md` vs. leaf nodes.
- **Fractal compression**: Leaf nodes compress raw code; parent nodes compress child intent nodes (not raw code). A parent node summarizes its children's intent nodes, creating a compression hierarchy. Our E-010 design already specified leaf-first construction, but didn't articulate the "parent summarizes children, not code" principle explicitly.
- **Maintenance flywheel**: On every merge, detect changed files, identify affected intent nodes, re-summarize leaf-first if behavior changed, human reviews. Our documentation.md rule triggers on epic completion (coarse-grained). Intent nodes at the code level would need finer-grained sync — either manual per-PR review or automated detection.
- **Rule scoping opportunity**: Some rules in `.claude/rules/` (e.g., `crawling.md`, `devcontainer.md`) load into every agent session but are only relevant to specific work. Intent nodes could absorb directory-specific rules, reducing ambient load for agents working in unrelated areas. Claude Code currently doesn't support agent-scoped rules, but directory-scoped CLAUDE.md files are already supported.
- **Anti-pattern and pitfall capture**: Each node should include negative examples ("don't do X because Y") alongside positive patterns. Our current context layer captures some anti-patterns in CLAUDE.md (HTTP discipline, security rules) but not at the module level.
- **Chunking strategy**: Target 20k-64k token chunks for optimal compression ratio. Similar code compresses better together. This informs how we draw semantic boundaries for intent nodes.

## Rough Timing
After E-002 (Data Ingestion Pipeline) and E-003 (Data Model and Storage Schema) are both DONE. Intent nodes should be written against a substantially populated codebase, not against directories with only a few files. Writing intent nodes prematurely produces stale, misleading documents.

## Dependencies & Blockers
- [ ] E-002 (Data Ingestion Pipeline) must be DONE -- `src/gamechanger/` needs to have crawl and parse modules in place
- [ ] E-003 (Data Model and Storage Schema) must be DONE -- the database module path (`src/db/` or equivalent) must be settled

## Open Questions
- What is the exact path for the database module as delivered by E-003? E-010 tentatively used `src/db/` but E-003 may deliver a different path.
- Should `tests/CLAUDE.md` and `epics/CLAUDE.md` be included? E-010 planned 7 target directories; assess whether all 7 still make sense given the current project structure.
- The integration aspect (wiring skills + intent nodes into agent definitions, adding intent node maintenance to the Definition of Done) should be scoped at promotion time. E-028 already established documentation maintenance rules (`.claude/rules/documentation.md`), and skills are already wired into the PM definition. Assess what incremental integration work remains.
- E-010 originally targeted "orchestrator, software-engineer, and data-engineer" for skill references. The orchestrator is deleted (E-030). At promotion time, decide which agents need explicit intent node references in their definitions.
- **Maintenance granularity**: Should intent node sync be per-PR (as the article recommends) or per-epic (as our current documentation.md rule works)? Per-PR is more accurate but adds friction. Could start manual and automate later.
- **Rule migration**: Which `.claude/rules/` files could be absorbed into directory-scoped intent nodes to reduce ambient load? `crawling.md` (20 lines) is an obvious candidate for `src/gamechanger/CLAUDE.md`. `devcontainer.md` (131 lines) is heavy but cross-cutting.
- **Ambient load reduction**: Currently ~1,100-1,270 lines of ambient context per session. Could intent nodes + rule migration bring this under 1,000 lines, freeing budget for task-specific content?

## Notes
- **Origin**: Phase 2 of E-010 (Intent/Context Layer Implementation). E-010 was abandoned 2026-03-03 with Phase 1 DONE and Phase 2 BLOCKED/stale. See `/.project/archive/E-010-intent-context-layer-implementation/epic.md` for full history.
- **Design reference**: E-010's Technical Notes contain the intent node design (construction order, node content template, target directories, maintenance protocol). These should be consulted when promoting this idea, but verified against the then-current architecture.
- **Research reference**: E-008 decision log at `/.project/research/E-008-decision-log.md` (approved 2026-02-28) is the original recommendation.
- **Construction order from E-010**: Leaf-first. Write `src/gamechanger/CLAUDE.md` and `src/http/CLAUDE.md` before `src/CLAUDE.md`. Parent nodes summarize children. This aligns with the article's "fractal compression" principle.
- **Target directories from E-010** (to be reassessed): `src/`, `src/gamechanger/`, `src/http/`, `src/safety/`, `src/db/`, `epics/`, `tests/`.
- **External reference**: https://intent-systems.com/blog/intent-layer -- "The Intent Layer" article covering hierarchical intent nodes, LCA placement, fractal compression, maintenance flywheel, and chunking strategy. Reviewed 2026-03-06 and findings integrated into this idea.

---
Created: 2026-03-03
Last reviewed: 2026-03-06
Review by: 2026-06-01
