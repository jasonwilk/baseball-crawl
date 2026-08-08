# IDEA-231: 25 dead `epics/E-NNN-` references are already shipped across four owners

## Status
`CANDIDATE` — **measured, not estimated. Split out of E-279 deliberately; one instance was taken in-scope there, these 24 were not.**

## Summary

Every epic closure renames `epics/E-NNN-slug/` into `.project/archive/`, which breaks any reference to the old path in a file outside the archive. That is IDEA-228's defect, and E-279 closes it going forward. **It has already fired 25 times.**

**Measured during E-279 planning** (claude-architect; method recorded so it can be re-derived rather than trusted): `grep -rhoE "epics/E-[0-9]{3}-[a-z0-9-]+"` across the repo excluding `.git` and `archive`, deduplicated, then a per-path existence test. **Result: 27 distinct epic-directory paths referenced outside `.project/archive/`, 25 of which do not exist**, sitting in 33 files — 15 under `.project/`, 12 under `.claude/`, 2 `tests/`, 2 `docs/`, 1 `src/`, 1 `scripts/`.

**One was fixed in E-279 and is NOT part of this backlog**: `src/reports/llm_analysis.py`'s "Source of truth, reproduced verbatim from `epics/E-243-.../E-243-04-narration-prompt.md`" — shipped code making a source-of-truth claim, one-line fix, taken as the natural companion to E-279's sweep-script story. **This idea covers the remaining 24.**

## Why It Matters

The failure mode is not the broken link. It is an agent that has no reason to doubt the pointer, follows it, finds nothing, and re-derives what the pointer existed to preserve — the same class as [[IDEA-224]] / [[IDEA-225]] / [[IDEA-226]], arriving by a different route.

E-279 stops NEW instances. It does nothing about these, and nothing will: the sweep script it ships is scoped to the single closing epic by design, precisely so it does not collide with the synthetic `epics/E-999-demo/` fixtures in the two PII tests. **A repo-wide variant is not a bigger version of the same tool.**

## Why This Was NOT Folded Into E-279

PM scope decision, with claude-architect's recommendation on record and agreeing. Two reasons:

1. **It is 25 separate criterion-versus-evidence judgements across four owners**, not one sweep. A path citation may be a POINTER a reader is meant to follow (a **criterion** — repoint it) or a RECORD of where something was observed (**evidence** — editing it falsifies the record). `.claude/rules/tool-output-integrity.md` is explicit that a sweep "fixing every stale-looking figure" destroys records. ⚠️ **The reasoning does NOT depend on how many are evidence.** An earlier draft of this file said "much of this backlog is research and archive-adjacent material where the reference is evidence" — **that proportion was never measured.** It was claude-architect's inference (it did not read the 33 files to classify them) and PM restated it unchecked. 25 judgements across four owners is out of scope at ANY ratio. The proportion is this idea's first open question, not one of its findings.
2. **Turning a micro-epic into a 33-file sweep is exactly the late scope growth IDEA-228 itself warns against**, and it collided with the operator's standing steer for E-279 (micro-epic, refine before build, do not overengineer).

## Rough Timing

**Not urgent, and deliberately so** — these have been dead for some time with no observed cost beyond the one E-278 incident that produced IDEA-228. Promote when either trigger fires:

- An agent is actually misled by one of them (the pain arrives), or
- A context-layer or documentation epic is already opening the same files for another reason, making the marginal cost near zero.

Prefer the second. This is cheap to fold into work that is already in the neighbourhood and expensive as its own errand.

## Dependencies & Blockers
- [ ] **E-279 should land first** — its ceiling ("in a closure archive-path repoint, only the path literal may change", landing in `agent-routing.md`) is the rule any batch repoint should operate under, and its owner-routing table is the routing this work needs.
- [ ] **Four owners must be routed separately** — PM for `epics/` and `.project/`; claude-architect for `.claude/**`; software-engineer for `src/`, `tests/`, `scripts/`; docs-writer for `docs/`. An agent editing another agent's memory directory is the thing the own-memory carve-out forbids.

## Open Questions

- **How many of the 24 are evidence rather than criteria?** Unmeasured. This is the question that decides whether this is a small chore or mostly a no-op with a few real fixes. Worth sampling ten before scoping any epic — if most are evidence, the right outcome may be "annotate a handful, leave the rest" rather than a repoint pass.
- **Is a repo-wide script worth building at all?** Probably not as a gate — the fixture collision above is structural, and a gate that must special-case `E-999-demo` is a gate someone will later widen wrongly. A one-off audit command is a different proposition from a hook.
- **Does the same defect exist for renamed non-epic paths?** Not checked. The measurement above was scoped to `epics/E-NNN-` literally.

## Notes

Filed 2026-07-28 by product-manager during E-279 planning, from claude-architect's measurement. The count and method are recorded above rather than the file list, deliberately: the list will drift, the method re-derives it in one command.

Related: [[IDEA-228]] (the mechanism that creates these, closed forward by E-279); [[IDEA-224]], [[IDEA-225]], [[IDEA-226]] (stranded claims, same consequence, different route); [[IDEA-227]] (lessons stranded where nobody loads them).

---
Created: 2026-07-28
Last reviewed: 2026-07-28
Review by: 2026-10-26
