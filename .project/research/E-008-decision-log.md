# E-008: Intent/Context Layer Design -- Decision Log

Append-only. Each entry is a dated record of a user decision. Do not modify existing entries.

---

## Entry 1: 2026-02-28

**Decision**: APPROVED

**Approved approach**: Option 5 (Hybrid) -- selective skill adoption (Phase 1) + intent node hierarchy at module boundaries (Phase 2)

**Rationale summary**: The current system works, but three specific skills (`filesystem-context`, `multi-agent-patterns`, `context-fundamentals`) describe patterns baseball-crawl already uses without having codified them for agent consumption. Phase 1 closes that gap at low cost (2-4 hours, no conditions required). Phase 2 intent nodes are premature until `src/` has substantial code and are deferred until E-002 and E-003 are DONE.

**Constraints for implementation**:
- Phase 1 only (skill files) proceeds immediately.
- Phase 2 stories (intent nodes at module boundaries) are left in DRAFT in the new epic until after E-002 and E-003 are both DONE.
- All three skills go into `.claude/skills/` (one subdirectory per skill, with a `SKILL.md` file inside each).
- Each skill must be adapted to baseball-crawl's conventions and include project-specific examples -- not a verbatim copy of the muratcankoylan source material.
- Owner for all Phase 1 and Phase 2 stories: claude-architect.

**Follow-on epic authorized**: E-010 (E-009 is occupied by the Tech Stack Redesign epic)

**Epic closed**: E-008 moves to COMPLETED and is archived to `/.project/archive/E-008-intent-context-layer-design/`
