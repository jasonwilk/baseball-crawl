# E-068-04: Add Vision Stewardship to PM Agent Definition

## Epic
[E-068: Vision Stewardship](epic.md)

## Status
`DONE`

## Description
After this story is complete, the PM agent definition will include vision stewardship as a core responsibility. The PM becomes the project's vision steward -- responsible for long-horizon product thinking, capturing and curating vision signals, and being curious and opinionated about where the project should go. The "curate the vision" trigger phrase will be documented as a PM workflow.

## Context
The PM currently owns the backlog (epics, stories, ideas) but does not have an explicit mandate to think about where the project is heading long-term. Vision stewardship expands the PM's role to include: (1) recognizing and capturing vision signals during its own work, (2) curating accumulated signals into the polished vision document when triggered, and (3) bringing a proactive, opinionated perspective to product direction rather than passively managing tasks. The "curate the vision" phrase activates a specific workflow where the PM reviews signals with the user and refines `docs/VISION.md`.

## Acceptance Criteria
- [ ] **AC-1**: The PM agent definition (`.claude/agents/product-manager.md`) includes a new section or subsection describing vision stewardship as a PM responsibility. This covers: long-horizon product thinking, recognizing vision signals, curating the vision document.
- [ ] **AC-2**: The "curate the vision" trigger phrase is documented in the PM agent definition, either as a new task type entry or as a workflow within an existing section. The documentation explains what happens when this phrase is used: PM reviews `docs/vision-signals.md` with the user, discusses which signals belong in `docs/VISION.md`, updates the vision document, and clears processed signals from the parking lot.
- [ ] **AC-3**: The PM's "Completing an epic" checklist (Atomic Status Update Protocol section) references the vision signal review that now occurs during dispatch closure, so the PM is aware of it when performing close-mode work.
- [ ] **AC-4**: The vision stewardship additions are additive only -- no existing sections are removed, renamed, or have content deleted. New content is inserted within or after existing sections, not injected mid-paragraph into existing prose.
- [ ] **AC-5**: The additions reference the two vision artifacts by their full paths: `docs/VISION.md` (polished vision) and `docs/vision-signals.md` (parking lot).

## Technical Approach
The PM agent definition at `/.claude/agents/product-manager.md` needs targeted additions in several locations. The specific insertion points and wording are implementation decisions for the architect -- the key constraint is that the additions cover the three responsibilities (long-horizon thinking, signal capture, curation workflow) and the trigger phrase, without disrupting the existing structure. Read the full PM agent definition to understand the current section layout before making changes.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-068-05

## Files to Create or Modify
- `.claude/agents/product-manager.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] PM agent definition remains well-structured and readable
- [ ] No regressions in existing tests

## Notes
The PM agent definition is large (~400 lines). Changes should be surgical -- add vision stewardship content at natural insertion points rather than reorganizing the entire file. The "curate the vision" workflow could be modeled after the existing task types table or as a standalone subsection.
