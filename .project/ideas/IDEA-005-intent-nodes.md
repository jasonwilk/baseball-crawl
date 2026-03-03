# IDEA-005: Directory-Scoped Intent Nodes at src/ Module Boundaries

## Status
`CANDIDATE`

## Summary
Write directory-scoped CLAUDE.md files ("intent nodes") at semantic module boundaries in `src/` and project directories. When an agent opens a file in `src/gamechanger/`, Claude Code loads `src/gamechanger/CLAUDE.md` automatically, providing localized context without requiring the root CLAUDE.md to enumerate all module invariants. This was Phase 2 of E-010 (Intent/Context Layer Implementation), which delivered Phase 1 (skill files) and was abandoned because the blockers for Phase 2 were not close to clearing and the epic text had gone stale.

## Why It Matters
Story authors currently repeat module invariants (credential handling rules, rate limiting, idempotency contracts, session factory usage, PII safety rules) in every Technical Approach section. Intent nodes would capture these invariants once, close to where agents actually work, reducing story boilerplate and making it harder for implementing agents to miss critical contracts.

The filesystem-context skill (`.claude/skills/filesystem-context/SKILL.md`) already teaches agents to load context on demand from files. Intent nodes are the natural next step: placing that context at the directory level where the code lives.

## Rough Timing
After E-002 (Data Ingestion Pipeline) and E-003 (Data Model and Storage Schema) are both DONE. Intent nodes should be written against a substantially populated codebase, not against directories with only a few files. Writing intent nodes prematurely produces stale, misleading documents.

## Dependencies & Blockers
- [ ] E-002 (Data Ingestion Pipeline) must be DONE -- `src/gamechanger/` needs to have crawl and parse modules in place
- [ ] E-003 (Data Model and Storage Schema) must be DONE -- the database module path (`src/db/` or equivalent) must be settled

## Open Questions
- What is the exact path for the database module as delivered by E-003? E-010 tentatively used `src/db/` but E-003 may deliver a different path.
- Should `tests/CLAUDE.md` and `epics/CLAUDE.md` be included? E-010 planned 7 target directories; assess whether all 7 still make sense given the current project structure.
- The integration aspect (wiring skills + intent nodes into agent definitions, adding intent node maintenance to the Definition of Done) should be scoped at promotion time. E-028 already established documentation maintenance rules (`.claude/rules/documentation.md`), and skills are already wired into the PM definition. Assess what incremental integration work remains.
- E-010 originally targeted "orchestrator, general-dev, and data-engineer" for skill references. The orchestrator is deleted (E-030). At promotion time, decide which agents need explicit intent node references in their definitions.

## Notes
- **Origin**: Phase 2 of E-010 (Intent/Context Layer Implementation). E-010 was abandoned 2026-03-03 with Phase 1 DONE and Phase 2 BLOCKED/stale. See `/.project/archive/E-010-intent-context-layer-implementation/epic.md` for full history.
- **Design reference**: E-010's Technical Notes contain the intent node design (construction order, node content template, target directories, maintenance protocol). These should be consulted when promoting this idea, but verified against the then-current architecture.
- **Research reference**: E-008 decision log at `/.project/research/E-008-decision-log.md` (approved 2026-02-28) is the original recommendation.
- **Construction order from E-010**: Leaf-first. Write `src/gamechanger/CLAUDE.md` and `src/http/CLAUDE.md` before `src/CLAUDE.md`. Parent nodes summarize children.
- **Target directories from E-010** (to be reassessed): `src/`, `src/gamechanger/`, `src/http/`, `src/safety/`, `src/db/`, `epics/`, `tests/`.

---
Created: 2026-03-03
Last reviewed: 2026-03-03
Review by: 2026-06-01
