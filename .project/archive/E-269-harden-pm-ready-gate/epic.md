# E-269: Harden the PM READY Quality-Checklist Gate

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- READY 2026-07-19; DISPATCHED & COMPLETED 2026-07-19. Context-layer epic: claude-architect owned the
     design (design brief) and implemented the dispatched story; PM framed the ACs + authored the
     epic/story. Codex spec-review round 1 (2 findings, both accepted + fixed) plus Codex code review
     round 2 (2 findings, both accepted + fixed) — see the Review Scorecard in History. -->

## Overview
Harden the PM READY gate so an epic with a phantom story (a Stories-table row with no story file, or a stub full of TBD placeholders) or a silently-skipped required domain consultation CANNOT reach READY. The fix adds two binding items to the PM Quality Checklist in `.claude/agents/product-manager.md` and tightens the existing soft consultation line — the dispatched IMPLEMENTATION touches that one file only. (The retrospective-catch walkthrough that proves the gate works is planning-time documentation captured in the E-269-01 story's Notes — not an implementation deliverable; see Technical Notes TN-5.)

## Background & Context
Earlier this session two epics reached READY in defective form and only a later manual Codex review caught them: **E-268** was READY with a phantom story row (`E-268-01` had no story file on disk), and **E-267** was READY with a schema-impossible AC plus a never-performed api-scout consultation on safety-critical GameChanger-payload ACs.

Root cause (claude-architect diagnosis): the **PM Quality Checklist** (`.claude/agents/product-manager.md`, Quality Checklist section ~L254–269) is the single chokepoint that BOTH the plan-skill path and the ad-hoc-spawn path cross before READY, and it verifies neither:
1. **Story-file existence per Stories-table row** — the checklist iterates over stories the PM can see, not over the epic's Stories-table rows, so a phantom row passes.
2. **Consultation completeness against the Consultation Triggers table** (PM def L80–86) — the current consultation item (L257: "Expert consultation completed (or 'No consultation required' noted)") is a soft self-attestation not bound to the triggers table, so a silently-skipped domain (e.g. api-scout) passes.

The two leaks differ in how the plan skill relates to them, and neither is closed by the plan-skill review criteria:
- **Consultation gap:** the plan skill's Phase 0 domain team-formation would likely have surfaced api-scout on the plan path (a domain team includes it), so this leak is plan-path-mitigated but the ad-hoc-spawn path (PM sets READY via its own checklist, PM def L111) leaves it open.
- **Phantom-story gap:** the Phase-3 CR spec audit reviews existing files against six criteria (`.claude/skills/plan/SKILL.md:200`), NONE of which verify that every Stories-table row has a corresponding story file — so a phantom story would slip the plan skill TOO, not just the ad-hoc path.

Therefore the shared **PM Quality Checklist** — the one gate BOTH paths cross before READY — is the mechanism that closes the leak, and for the phantom-story case it is the ONLY place it can be closed (the plan-skill criteria do not check it). That makes option (a) necessary, not merely convenient.

## Goals
- A phantom story (table row with no file, or a stub with TBD/placeholder sections) CANNOT pass the PM READY gate.
- A silently-skipped required domain consultation CANNOT pass the PM READY gate — every triggered domain gets an explicit consulted-or-waived verdict.
- Fix via **option (a) alone**: two binding Quality-Checklist items + tightening the existing soft consultation line — the dispatched implementation deliverable is one file (`.claude/agents/product-manager.md`).

## Non-Goals
- NOT option (b): do not force a Codex spec review onto every ad-hoc epic (heavy, against simple-first).
- NOT option (c): do not add a hard "all epic creation must route through the plan skill" rule (unenforceable bright line; blocks legitimate quick captures).
- No new rule file, no `workflow-discipline.md` change, no plan-skill change. (The plan skill partially mitigates the consultation gap via Phase-0 team formation but does NOT check story-file-per-row; the fix belongs in the shared Quality Checklist both paths cross, not in the plan skill.)
- Does not attempt to prevent a WRONG waiver (see Technical Notes honest ceiling) — only to make every skip an explicit, visible verdict.

## Success Criteria
- Reading `.claude/agents/product-manager.md` shows the Quality Checklist now binds the two new items (story-file existence; consultation completeness) and the tightened consultation line, with no internal contradiction.
- A written retrospective walkthrough demonstrates that, applied to E-267's and E-268's READY-state inputs, the two new items WOULD have failed the gate (E-268 phantom `E-268-01`; E-267 skipped api-scout on payload-semantics ACs).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-269-01 | Harden the PM READY Quality-Checklist gate (story-file existence + consultation completeness) | DONE | None | claude-architect |

## Dispatch Team
<!-- Context-layer file (`.claude/agents/product-manager.md`) — routes to claude-architect per the
     Routing Precedence in agent-routing.md; claude-architect owns the design and implements. -->
- claude-architect

## Technical Notes

**TN-1 — Edit locus.** `.claude/agents/product-manager.md`, the Quality Checklist section (currently ~L254–269). All changes are confined to this section; no other file changes.

**TN-2 — What the two binding items must verify (design, per claude-architect).**
- *Story-file existence*: every story listed in the epic's Stories table has a real story file on disk carrying acceptance criteria, a Files-to-Create-or-Modify list, and a Definition of Done. A table row with no file, or a stub with TBD/placeholder sections, FAILS the gate — no READY with a phantom story. The check must iterate the Stories-TABLE rows, not the stories the PM happens to have in context.
- *Consultation completeness*: for each domain the epic touches per the Consultation Triggers table (PM def L80–86), record an explicit per-domain verdict — CONSULTED (input captured in Technical Notes) OR WAIVED (one-line reason). A silent omission is not a waiver. State explicitly that GameChanger payload / data-availability ACs trigger api-scout. This mirrors the "explicit per-trigger yes/no verdict" discipline already required at epic closure (context-layer + documentation assessments).

**TN-3 — Reconcile the existing soft line.** The current L257 item ("Expert consultation completed (or 'No consultation required' noted)") must be tightened to point at the new per-domain verdict rather than the soft blanket note; the two must not conflict or duplicate.

**TN-4 — Honest ceiling (state, do not overclaim).** A waiver is only as good as PM judgment — a determined PM could still waive api-scout wrongly. The gate's value is converting a *silent* skip into an *explicit, visible* per-domain verdict the user can see and challenge in the READY summary. It does NOT guarantee every waiver is correct, and a hard "must consult" gate is deliberately out of scope. The change must state this limitation honestly rather than claim the gate prevents all bad consultation decisions.

**TN-5 — This epic hardens the very checklist the PM uses; implementation-deliverable vs planning-doc.** The dispatched story edits the PM's own READY gate; the IMPLEMENTATION DELIVERABLE — the only context-layer file the story ships — is `.claude/agents/product-manager.md` (Quality Checklist section), implemented by claude-architect during dispatch. The AC-5 retrospective-catch walkthrough is a PLANNING-TIME artifact, authored NOW into the E-269-01 story's Notes; it is documentation that verifies the design, NOT an implementation file change. So "the dispatched implementation touches product-manager.md only" and "AC-5's walkthrough lives in the story Notes" are consistent, not contradictory: the story file's Notes is a planning artifact, product-manager.md is the shipped deliverable. Planning writes no context-layer files.

## Open Questions
- None. claude-architect recommends a single story (the retrospective demonstration folds in as an AC, not a separate E-222-style dry-run story — a markdown checklist has no isolatable executable test artifact, so the "dry-run" is a reasoning walkthrough best captured as an AC); PM concurs (simple-first).

## History
- 2026-07-19: **Dispatched & completed (E-269-01 DONE).** E-269-01 shipped two binding Quality-Checklist items to `.claude/agents/product-manager.md` — (1) *story-file existence*, iterating the Stories-TABLE rows (a table row with no file, or a stub with TBD/placeholder sections, FAILS the gate); (2) *consultation completeness*, an explicit per-domain CONSULTED/WAIVED verdict against the Consultation Triggers table (silent omission ≠ waiver; GameChanger payload/data-availability ACs trigger api-scout) with the honest ceiling stated — plus tightening the soft L257 consultation line to point at the per-domain verdict. Codex code-review remediation additionally reconciled the L86 Consultation Triggers row (a second soft-blanket-note location that the new gate would otherwise contradict) — PM ruled the widened locus in-spirit under AC-6 (same file, no new rule/workflow/plan-skill files, completing the same TN-3 anti-contradiction change). Both Success Criteria met.
  - **Review Scorecard:**

    | Review Pass | Findings | Accepted | Dismissed |
    |---|---|---|---|
    | Per-story CR — E-269-01 | — | — | — (skipped: context-layer-only story; PM verified ACs alone) |
    | Closure CR Integration Review | 0 | 0 | 0 |
    | Codex code review | 2 | 2 | 0 |
    | **Total** | **2** | **2** | **0** |

    Footnote: Codex Finding 1 = the L86 Consultation Triggers soft-blanket contradiction, fixed by claude-architect. Codex Finding 2 = stale status mirrors — the epic.md L6 lifecycle comment accepted as a closure to-do (reconciled at the Step 8 COMPLETED flip); the MEMORY.md / epic-status portions were expected mid-dispatch timing (closure-time updates), not defects. Both findings actioned; none dismissed.
  - **Documentation assessment:** No documentation impact — the change is to an agent definition (the PM's internal READY gate); no `docs/admin` or `docs/coaching` surface describes this gate.
  - **Context-layer assessment (eight explicit per-trigger verdicts):**
    1. New convention/constraint — **YES** (two binding READY-gate items); codified in the deliverable itself (`.claude/agents/product-manager.md`); no further action.
    2. Architectural decision — No.
    3. Footgun/boundary — **YES** (the READY-gate leak); addressed by the deliverable; the L86 second-location miss is a doc-sweep instance already covered by `.claude/rules/doc-sweep.md`; no new codification.
    4. Agent behavior change — **YES** (PM READY-gate behavior); codified in the deliverable; no further action.
    5. Domain knowledge — No.
    6. New CLI/workflow — No.
    7. Net context-layer growth ratchet — **FAIL** (+564 total vs baseline), but E-269's own delta is +4 lines (`product-manager.md`); the +560 remainder is pre-existing baseline drift (agent-memory +458, rules +102) from prior epics. **OPERATOR-SIGNED EXCEPTION GRANTED for E-269 (Jason, 2026-07-19):** E-269's +4-line delta is a legitimate reviewed deliverable; the pre-existing drift remains the separate operator re-snapshot follow-up (E-262 item).
    8. Reusable behavioral lesson — No.
  - **Ideas backlog + vision signals (advisory):** No `.project/ideas/README.md` CANDIDATE is unblocked or promoted by E-269 (a process/PM-gate change unblocks no feature idea). `docs/vision-signals.md` carries unprocessed signals (last curated 2026-07-05), but none are E-269-related — no new signal captured.
- 2026-07-19: **DRAFT → READY.** **Review Scorecard** (all findings accepted + fixed; targeted verify clean by a main-session grep of both fixes + the coherent deliverable-vs-planning-doc split):
  - CA-designed context-layer epic (claude-architect design brief; PM framed ACs + authored the epic/story).
  - Codex spec review round 1 (2 findings, both ACCEPT): P1 scope inconsistency (AC-5 walkthrough vs AC-6 "one file" — resolved by distinguishing the implementation deliverable `product-manager.md` from the planning-time walkthrough now authored in the E-269-01 Notes; TN-5 codifies the split); P2 rationale accuracy ("plan workflow would have caught both" corrected — the phantom-story gap slips the plan skill too, so the shared PM Quality Checklist is the sole gate → option (a) necessary).
  - NOT dispatched — awaits explicit user dispatch authorization.
- 2026-07-19: Created (DRAFT) from the READY-gate leak diagnosed this session (E-267/E-268 reached READY malformed). claude-architect design brief; PM framed ACs + authored the epic + story file. Consultation verdict: claude-architect CONSULTED (design brief, context-layer domain owner); no other Consultation-Triggers domain applies (no GameChanger payload/data-availability ACs → api-scout not triggered; no schema/ETL → data-engineer not triggered; no coaching-data/stat definition → baseball-coach not triggered). Held DRAFT for the Codex spec-review pass; not dispatched.
