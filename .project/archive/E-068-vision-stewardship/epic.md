# E-068: Vision Stewardship

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Establish a lightweight system for capturing, curating, and refining the project's evolving vision. Vision signals -- statements about what the project will become or how it will be used -- are captured in a parking lot file by any agent in any session, then periodically curated into the polished vision document during epic closure or on user request. The PM's role expands to include long-horizon product thinking as a vision steward.

## Background & Context
The user (Jason) wants AI agents to play a larger role in shaping the project's direction, not just implementing what he tells them. Conversations regularly produce vision signals -- statements about the project's future direction, new capabilities, or user scenarios -- that currently evaporate when the session ends. Example: Jason mentioned wanting an LLM-powered chat agent built into the dashboard where coaches can ask questions about matchups and get strategy insights. That signal already appears in `docs/VISION.md` (Layer 5: Conversational Intelligence) but is not in any lightweight parking lot that agents can append to during normal work.

Two artifacts already exist or are ready to be created:
- `docs/VISION.md` -- the polished guiding light (already created)
- `docs/vision-signals.md` -- an ultra-lightweight parking lot for raw signals (to be created by this epic)

This epic introduces the trigger phrase "curate the vision" to activate the refinement workflow.

**Expert consultation**: The PM Consultation Triggers table flags "Agent infrastructure, CLAUDE.md, rules, skills" epics for claude-architect consultation. This epic touches those files, but a separate pre-story consultation is not warranted because: (1) all architectural decisions (two-artifact model, closure sequence integration, PM ownership) were made collaboratively with Jason before this epic was formed -- these are user-directed design choices, not open questions for the architect; (2) claude-architect is the sole implementing agent for all five stories (Dispatch Team section), so the architect will apply its own structural judgment during implementation; (3) a pre-implementation architectural review was completed (see History entry for 2026-03-07 refinement review), confirming all insertion points, step numbering, and file locations are correct. A separate consultation would be circular.

## Goals
- Any agent in any session can append a vision signal to the parking lot with near-zero friction
- Epic closure includes a vision signal review step that prompts the user about curation
- The trigger phrase "curate the vision" is introduced and activates a refinement workflow
- The PM agent definition includes vision stewardship as a core responsibility
- The first vision signal (LLM-powered coaching chat agent) is backfilled into the parking lot from `docs/VISION.md` as a seed entry

## Non-Goals
- Creating a new agent for vision work (PM owns this)
- Building any automation around vision curation (it is a human-in-the-loop conversation)
- Modifying the polished `docs/VISION.md` itself (that happens during curation, not during this epic)
- Adding a formal template or ceremony to signal capture (the whole point is near-zero friction)

## Success Criteria
- `docs/vision-signals.md` exists with a clear format and at least one seed signal
- A rule file in `.claude/rules/` instructs all agents to recognize and capture vision signals
- The dispatch closure sequence includes a vision signal review step
- The PM agent definition includes vision stewardship responsibilities and the "curate the vision" workflow
- CLAUDE.md references the vision system (Workflows section for "curate the vision", docs reference for vision files)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-068-01 | Create vision signals parking lot and seed first signal | DONE | None | claude-architect |
| E-068-02 | Create vision signal recognition rule | DONE | E-068-01 | claude-architect |
| E-068-03 | Add vision signal review to dispatch closure sequence | DONE | E-068-01 | claude-architect |
| E-068-04 | Add vision stewardship to PM agent definition | DONE | None | claude-architect |
| E-068-05 | Update CLAUDE.md with vision system references | DONE | E-068-01, E-068-02, E-068-03, E-068-04 | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### Two-Artifact Model

The vision system uses two artifacts with distinct purposes:

1. **`docs/VISION.md`** (already exists) -- The polished, curated vision document. Updated only during deliberate curation sessions with the user. This is the guiding light that agents reference for product direction.

2. **`docs/vision-signals.md`** (created by E-068-01) -- The raw parking lot. Ultra-lightweight. Each entry is a date-stamped line or two capturing a signal. No template, no frontmatter, no ceremony. Any agent appends here when they notice a vision signal in conversation.

### Signal Capture Design

The rule file should instruct agents to recognize vision signals -- statements about what the project will become, new capabilities, user scenarios, or strategic direction -- and append them to `docs/vision-signals.md`. The format should be minimal: a date, a brief description, and optionally a source context. The rule should emphasize that capture is low-friction and that agents should err on the side of capturing (signals can be discarded during curation; lost signals cannot be recovered).

### Closure Sequence Integration

The vision signal review step belongs in the closure sequence after the ideas backlog review (current Step 14) and before the summary (current Step 15). The step should:
1. Check whether `docs/vision-signals.md` has any unprocessed signals
2. If signals exist, mention them in the summary and ask the user if they want to "curate the vision"
3. This is advisory, not blocking -- it does not prevent archival like the documentation or context-layer gates

This is lighter than the documentation or context-layer assessment gates. It is a prompt, not a gate.

### PM Vision Stewardship

The PM agent definition needs three additions:
1. A new responsibility area: vision stewardship (long-horizon product thinking, being curious and opinionated about project direction)
2. Recognition of the "curate the vision" trigger phrase as a PM task type or workflow
3. A description of the curation process: review accumulated signals with the user, discuss which belong in the vision document, update `docs/VISION.md`, and clear processed signals from the parking lot

### CLAUDE.md Updates

Two sections of CLAUDE.md need updates:
1. **Workflows section**: Add "curate the vision" as a workflow trigger phrase that invokes the PM for vision curation
2. **Key Directories or docs references**: Ensure `docs/VISION.md` and `docs/vision-signals.md` are discoverable

### Files Changed Per Story

| Story | Files |
|-------|-------|
| E-068-01 | `docs/vision-signals.md` (new) |
| E-068-02 | `.claude/rules/vision-signals.md` (new) |
| E-068-03 | `.claude/rules/dispatch-pattern.md`, `.claude/skills/implement/SKILL.md` |
| E-068-04 | `.claude/agents/product-manager.md` |
| E-068-05 | `CLAUDE.md` |

No file conflicts between stories 01-04 (all touch different files). Stories 02 and 03 depend on 01 (the parking lot file must exist before rules or closure steps reference it). Story 04 is independent. Story 05 depends on all others being complete so CLAUDE.md references are accurate. Dispatch waves: wave 1 = E-068-01, E-068-04 (parallel, no file conflicts); wave 2 = E-068-02, E-068-03 (parallel, unblocked by 01); wave 3 = E-068-05.

## Open Questions
- None

## History
- 2026-03-07: Created as DRAFT. No expert consultation required -- pure process/workflow epic with architectural decisions pre-made by the user.
- 2026-03-07: Codex spec review triaged. 5 findings: 2 REFINED (dependency gaps for 02/03 on 01, subjective ACs tightened), 1 partially REFINED (unprocessed signals definition, trigger phrase wording), 1 DISMISSED (consultation -- architect is the implementer), 1 partially REFINED (future-state language corrected).
- 2026-03-07: Architectural refinement review. Verified: (1) rule file frontmatter pattern matches existing rules (paths key with `**` glob, same as dispatch-pattern.md), (2) dispatch-pattern.md closure step numbering confirmed (Step 14 = ideas, Step 15 = summary -- story correctly targets insertion between them), (3) implement/SKILL.md uses Phase 5 internal numbering (Steps 1-9) with Step 6 = ideas and Step 7 = summary -- story Notes already warn about different numbering conventions, (4) PM agent def sections confirmed (Atomic Status Update Protocol > Completing an epic checklist at 6 steps, vision review would be Step 7 after ideas review), (5) CLAUDE.md Key Directories section at line 329 and Workflows section at line 175 confirmed as correct insertion targets. No corrections needed. Epic set to READY.
- 2026-03-09: Epic COMPLETED. All 5 stories implemented by claude-architect agents and verified by main session (all context-layer-only). Artifacts: `docs/vision-signals.md` (parking lot with seed signal), `.claude/rules/vision-signals.md` (capture rule), closure sequence updated in `dispatch-pattern.md` and `implement/SKILL.md`, PM agent definition updated with vision stewardship, CLAUDE.md updated with workflow trigger and Key Directories entries. Documentation assessment: No documentation impact (no CLI commands, API endpoints, or coaching-facing features). Context-layer assessment: (1) New convention — no; (2) Architectural decision — no; (3) Footgun/boundary — no; (4) Agent behavior change — yes, self-codified by E-068-02 (rule), E-068-03 (closure sequence), E-068-04 (PM definition); (5) Domain knowledge — no; (6) New workflow — yes, self-codified by E-068-04 and E-068-05 (CLAUDE.md). No additional codification needed.
- 2026-03-07: Second codex spec review triaged. 7 findings: (1) P1 ACCEPTED -- hardened 01 AC-4 to require exact `## Signals` heading (downstream 03 AC-1 keys off it); (2) P2 ACCEPTED -- corrected epic background and story 01 context to acknowledge LLM chat signal already exists in VISION.md Layer 5, parking lot entry is a backfill not first capture; (3) P2 ACCEPTED -- pinned 05 AC-2 to Key Directories section (was vague "somewhere agents would look"); (4) P2 ACCEPTED -- fixed 03 DoD from "consistent across both files" to "correct within each file" since the two files use different numbering conventions; (5) P2 PARTIALLY ACCEPTED -- strengthened consultation justification to explicitly acknowledge Consultation Triggers table flag and cite the architectural refinement review as evidence, but maintained "no separate consultation" conclusion since architect is the sole implementer and all design decisions were user-directed; (6) P3 ACCEPTED -- added E-068-02 and E-068-03 to story 01 Blocks field (were missing despite epic table showing the dependency); (7) P3 ACCEPTED -- moved E-068-04 to wave 1 (no dependencies, no file conflicts with 01).
