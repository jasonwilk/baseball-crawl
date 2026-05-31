# E-229-03: Remove RTK Integration section from codex-guide doc

## Status
`DONE`

## Epic
E-229

## Story
Remove the `## RTK Integration (Codex Lane)` section from
`docs/admin/codex-guide.md`. This is the operator-facing documentation of the
RTK Codex lane; with RTK removed, the section is obsolete and would mislead
operators. The adjacent `## Checked-In Layer` list stays -- those files remain in
the repo and their RTK content is removed by their own stories.

## Acceptance Criteria

1. The `## RTK Integration (Codex Lane)` section is removed in full, including all
   its subsections: binary-location, "What This Lane Does NOT Use", "Coexistence",
   and "RTK Smoke Check" (the `python scripts/check_codex_rtk.py` block). The
   implementer should locate the section by heading rather than by line number.
2. The `## Checked-In Layer` list (and all other non-RTK sections) is retained
   and unchanged.
3. The document's heading structure and surrounding sections remain coherent (no
   orphaned subheadings, no broken intra-doc references to the removed section).
4. **Staleness header.** `docs/admin/codex-guide.md` currently has NO staleness
   header. Add one per `.claude/rules/documentation.md`: `Last updated` = the
   current date, `Source` = E-229. (This is an add, not a conditional update --
   the file has no header today.)
5. **No RTK reference remains in the file** -- grep `rtk|rust token killer`
   (case-insensitive) over `docs/admin/codex-guide.md` returns zero hits.

## Files to Create or Modify

- `docs/admin/codex-guide.md` (modify -- remove RTK section, add staleness header)

## Technical Approach

A single contiguous section removal, located by heading. After removing the
section, confirm the `## Checked-In Layer` list survived intact and scan for any
in-doc references that pointed at the removed RTK section, fixing or removing them
so the doc reads cleanly. Add the staleness header (the file has none today).
Verify with a case-insensitive RTK grep over the file.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No RTK reference remains in `docs/admin/codex-guide.md`
- [ ] Staleness header added per `.claude/rules/documentation.md`
- [ ] Document reads coherently with no dangling cross-references

## Non-Goals

- Do not modify any context-layer or provisioning file (those are E-229-01 and
  E-229-02).
- Do not remove or alter the `## Checked-In Layer` list -- the three files it
  names remain; only their RTK content is removed in E-229-02.

## Notes
- The smoke-check script `scripts/check_codex_rtk.py` referenced in the removed
  section is deleted in E-229-01; this story removes its documentation.
