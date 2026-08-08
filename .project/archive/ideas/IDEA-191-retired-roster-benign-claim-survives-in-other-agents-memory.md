# IDEA-191: The retired "roster failures are benign" claim survives in two other agents' memory files

## Status
`CANDIDATE`

## Summary

E-276 retired the claim that the roster grain's failure mode is harmless — *"grid clutter, never a corrupted stat"* / *"a wrong delete self-heals."* The epic scoped every copy it could reach. **Two live copies sit in agent-memory files that E-276 could not edit, because each belongs to an agent that was not on the dispatch team:**

1. **`.claude/agent-memory/baseball-coach/e267_reconcile_at_load_review.md`, Verdict 3** — *"the failure mode is benign (stale grid clutter, never wrong STATS…)"*. **This is the coach-side twin of the sentence TN-9 required scoped, in entirely different words.**
2. **`.claude/agent-memory/data-engineer/` — "DE FLAG 2"**, which [[IDEA-187]] does **not** cover; that idea's surviving scope after two deflations is structural.

## Why It Matters

**These are the sentences that made bias-to-refuse feel *safe* on the roster grain**, which is the reasoning E-276 overturned on the operator's ruling. An agent recalling either one would reason from a premise the shipped code contradicts — and agent-memory is loaded as context, so it reaches decisions directly rather than waiting to be looked up.

**⚠️ The retrieval property is the transferable part.** Copy (1) was found **only by the judgement-expansion step** of a retirement sweep — it shares **no tokens** with the retired sentence. It is `.claude/rules/doc-sweep.md`'s *"retired claims survive in forms carrying none of their tokens"* landing exactly as that rule describes. **A token grep for the retired wording finds neither copy.**

## Rough Timing

**Promote when either agent is next dispatched or consulted on reconcile, roster, or data-loss questions** — that is when the stale premise would be acted on, and when its owner is available to edit its own file.

No urgency otherwise: neither file drives production behaviour, and both agents are idle.

## Dependencies & Blockers

- [ ] **Ownership is the blocker, and it is not a technicality.** Per `.claude/rules/agent-routing.md` each agent owns its own `.claude/agent-memory/<name>/` directory. **Only baseball-coach may fix (1); only data-engineer may fix (2).** E-276 correctly reported rather than edited — the same boundary that made [[IDEA-187]] an idea rather than a one-line change.

## Open Questions

- **Should both be corrected, or scoped?** The E-276 precedent is **SCOPE-IT, DO-NOT-DELETE**: the benign claim is true *outside* the band régime, and it is the sentence the operator's prefer-delete ruling rests on, so a reader must not be left believing it holds unconditionally.
- **Is there a third copy?** Two were found by two different sweeps with different methods. **Nobody has swept the remaining agent-memory directories for the judgement rather than the wording**, and a token grep will not do it.
- **Does this recur structurally?** Every epic that retires a claim can strand copies in the memory of agents not on its dispatch team, and **the retiring epic is exactly the party that cannot fix them.** Whether that wants a standing mechanism is a bigger question than this idea.

## Notes

**Filed because both flags were category (iii) — no idea file and no durable record.** They surfaced during E-276-05's residue sweep, which is the last story of the epic; without capture they would have been archived with it. **The pattern this project has already named applies: an item raised while closing something else is the least likely to be written down.** That is the third such capture from this dispatch ([[IDEA-189]], [[IDEA-190]], this).

**Credit**: claude-architect found copy (1) via the judgement-expansion step and reported both rather than editing another agent's directory.

Related: [[IDEA-187]] (the same invariant stated in a superseded form in DE's memory — **distinct scope**, does not cover FLAG 2), [[IDEA-188]] (the band-régime mechanism that falsifies the benign claim), [[IDEA-186]].

---
Created: 2026-07-26
Last reviewed: 2026-07-26
Review by: 2026-10-24
