# E-256-15: Evict context-layer references to deleted surfaces

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`TODO`

## Description
After this story is complete, the context layer no longer references the surfaces this epic deleted. The E-237 "payload core + thin file-reading wrapper" convention (now actively misleading — it would instruct future loaders to rebuild the twin just deleted), the `backfill-appearance-order` command prose, the two `_utcnow_iso` implementations, `bridge.py`, `discover_opponents`, and the ghost package dirs are struck or annotated as history across `.claude/rules/`, `.claude/agents/`, and `CLAUDE.md`.

## Context
This is the deletion-side eviction pass for stories 01–04 (context-layer-assessment Learning-Loop Lifecycle). It runs after those deletions land so it evicts the real, final symbol set. Two lines in `architecture-subsystems.md` need care: **:72** (Payload-first loaders — its closing guidance "New loaders that must serve both a cached-file path and an in-memory path SHOULD follow this split" becomes actively harmful, instructing future loaders to build the twin we deleted) and **:74** (the E-244 cross-perspective dedup redirect map note, which names `_load_team_from_disk` as a surfacing site). This is a doc/prose surface, so the doc-sweep discipline applies: token grep + synonym expansion + semantic read (`.claude/rules/doc-sweep.md`), not grep alone.

## Acceptance Criteria
- [ ] **AC-1**: Given `.claude/rules/architecture-subsystems.md`, when this story is complete, then the Payload-first loaders guidance at ~:72 no longer instructs future loaders to build a disk/in-memory twin (the deleted pattern), and the E-244 redirect-map note at ~:74 no longer names `_load_team_from_disk` (deleted in story 01) as a live surfacing site.
- [ ] **AC-2**: Given the deleted symbols from stories 01–03 (`load_all`/`load_dir`/`load_file`/`_load_team_from_disk`, `bridge`, `discover_opponents`, `src.pipeline.*`, the duplicate `_utcnow_iso`), when this story is complete, then no `.claude/rules/`, `.claude/agents/`, or `CLAUDE.md` prose references them as live; each is struck or annotated as history.
- [ ] **AC-3**: Given the `backfill-appearance-order` command deleted in story 02, when this story is complete, then **this story removes** (story 02 does NOT touch CLAUDE.md, per Q1 routing — story 15 solely owns the CLAUDE.md prose edit) CLAUDE.md's Commands-section `bb data backfill-appearance-order` sentence AND its "**Footgun**: after backfill, recompute…" note, AND `.claude/rules/data-model.md`'s reference to it (the `bb data backfill-appearance-order` mention and the "confirm with `bb report verify-aggregates`" footgun) is struck or annotated. **This story is the single owner of the `data-model.md` edit relative to story 12** (see Dependencies — blockedBy E-256-12, which adds its dead-table note to the same file first). The context-layer backfill surfaces come from story 02's authoritative repo-wide grep (epic Technical Notes §15) — verify by grep-and-reconcile over `.claude/rules/` + `.claude/agents/` + `CLAUDE.md`, not the enumerated CLAUDE.md/data-model.md pair alone (a hand-list has proven incomplete this cycle; IDEA-115).
- [ ] **AC-4**: Given the eviction, when it is verified, then the doc-sweep discipline was applied per `.claude/rules/doc-sweep.md` — token grep PLUS synonym expansion PLUS a semantic read of the touched sections — not a keyword grep alone.

## Technical Approach
claude-architect owns all these files. Consume the deleted-symbol sets handed off by stories 01/02/03/04. The `utcnow_iso` rename (story 03) may also need a context-layer reference update if any rule/agent names `_utcnow_iso`. Apply the doc-sweep discipline: enumerate how each deleted concept is phrased WITHOUT its obvious keyword before concluding the sweep is complete (the E-250 "across games and seasons" miss is the standing lesson).

## Dependencies
- **Blocked by**: E-256-01, E-256-02, E-256-04 (evicts references to what they delete/restructure); **E-256-12** (same-file collision on `.claude/rules/data-model.md` — story 12 adds its dead-table note first, then this story strikes the `backfill-appearance-order` reference; ordering prevents a merge conflict on that file).
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/architecture-subsystems.md` (~:72, ~:74)
- `.claude/rules/data-model.md` (`backfill-appearance-order` reference)
- `CLAUDE.md` (Commands section, if story 02 left any residue; the `_utcnow_iso`/`utcnow_iso` naming if referenced)
- Any `.claude/agents/*.md` referencing the deleted surfaces (sweep to confirm)

## Agent Hint
claude-architect

## Handoff Context
None.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Doc-sweep discipline applied (AC-4)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This story is the deletion-side half of the epic's Learning-Loop Lifecycle obligation (context-layer-assessment triggers 7/8). It coordinates with, but is distinct from, story 12's dead-table note (which adds new prose rather than evicting old prose) and story 02's inline CLAUDE.md edit (which this story backstops).
