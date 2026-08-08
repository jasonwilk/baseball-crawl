# IDEA-214: fold E-275's instrument-failure catalogue into `tool-output-integrity.md`

## Status
`CANDIDATE` — **material already written and verified; this is a relocation into the rule file that owns the class, not new research.**

## Summary

E-275's planning and trim produced **ten catalogued instrument failures**, currently held in `.project/research/E-275-planning-record.md` §2. `.claude/rules/tool-output-integrity.md` already owns this exact material — "A claim you RELAY is a claim you AUTHOR", the producibility check, the criterion-versus-evidence cut. **The E-275 instances are worked examples of rules that file already states, plus two shapes it does not yet name.**

**PM cannot write to `.claude/rules/**` — claude-architect's domain — which is why this is an idea and not an edit.**

## Why It Matters

**The catalogue is the most transferable thing E-275 produced and it is currently filed under a classifier epic**, where nobody reasoning about tool output will find it. Left there, it is archived with the epic.

**Two shapes the rule file does not currently name**, both earned rather than theorised:

1. **A figure needs its DEFINING SETS attached, not just its value.** A bare number travels into a context that redefines its terms and is wrong on arrival with nothing to signal it. **A matching count is NOT evidence that two figures are the same quantity** — E-275 produced two 14s and two 22s, each pair genuinely different quantities that collided in size by arithmetic accident, and one near-substitution across a definitional boundary was caught only because someone refused to restate a figure they could not re-derive. This is adjacent to the existing producibility check but distinct: producibility asks *could this number have been made*; defining-sets asks *of what population*.

2. **The excision that loses things is the one attached to a STRUCTURE rather than to CONTENT.** During E-275's trim, a protected analysis was nearly dropped because it sat in a *section header* above the ACs being cut rather than inside a note or an AC. Sweeps that enumerate notes, ACs and figures do not enumerate headers, preambles and transitions. This generalises the existing doc-sweep guidance to a case it does not cover.

3. **The TWO-ARTIFACT CONTRADICTION, which no single-file read can catch — and this is the one the rule file most lacks.** An idea file classified a defect's severity as mild; the epic's own Technical Note already stated the table relation proving it harmful. **Both files were internally consistent and individually correct** — they were reasoning about different scenarios that shared an underlying relation, and neither pointed at the other. Six review passes, two audits and three agents read both without connecting them; it was found by *executing* the claim across its full input domain rather than by re-reading either file. **Single-file review cannot catch this by construction**, and the existing rules all address defects visible within one artifact. Sharpest form: *an artifact's severity claim was refuted by a fact its own epic already stated.* Full write-up: `.project/research/E-275-planning-record.md` §2b.

**And the strongest single finding, which belongs wherever the rule file states its own limits:** across the whole catalogue, **awareness of the class conferred no immunity.** Two of the ten instances were committed by the authors of the rule against them, hours after writing it — one by a reviewer applying the criterion-versus-evidence discipline, in the audit commissioned to prevent exactly that error. **Every corrected figure was caught by re-deriving; not one by careful re-reading.**

## Rough Timing

**Promote when claude-architect is next in the context layer for any reason** — this is a fold-in, not a project. It should not wait for a dedicated pass.

**Do not let it ride on E-275's closure.** E-275 is parked at DRAFT and may sit; if it is ever archived without this landing, the catalogue archives with it. That is the failure mode this idea exists to prevent.

## Dependencies & Blockers
- [ ] None. The material is written, verified, and needs no further research.

## Open Questions

- **How much belongs in the rule file versus staying as a cited artifact?** The rule file is loaded on every interaction and is already long. The two named shapes above are probably worth stating inline; the ten worked instances are probably worth a citation to the research file rather than a transcription. **CA's call** — this idea is not prescribing the form.
- **Does the "defining sets" shape merge with the existing producibility check or sit beside it?** They are related and not identical; conflating them may lose the distinction, and stating both may be redundant. Again CA's call.

## Notes

Source material: `.project/research/E-275-planning-record.md` §2 (items 3-6 relocated from E-275 TN-8, plus items 7-10 produced by the trim pass itself). Item numbering is preserved there so existing citations to "TN-8 item 4" resolve.

E-275's TN-8 retains the two rules its ACs depend on and points at the research file for the rest. **Nothing was deleted in that relocation** — the governing constraint on the trim was *relocate, do not delete; leave a pointer at every excision.*

Related: [[IDEA-211]] (a stale rule file that produced a false audit finding — the same family of "the context layer asserts a behaviour it no longer has"), [[IDEA-203]] and [[IDEA-204]] (also claude-architect, also arising from E-275, and plausibly one piece of work with this).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
