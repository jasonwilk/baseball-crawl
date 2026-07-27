# IDEA-203: `api-docs.md` prescribes a sentinel taxonomy the doc-PII gate has blocked

## Status
`CANDIDATE`

## Summary

`.claude/rules/api-docs.md` carries an "approved placeholder values" table instructing authors to use `"Anytown Eagles 12U"`, `"Example Team 14U"`, `"Springfield"`, `"Anytown Field"` and similar when writing example JSON.

Per the E-275 spec seed, the **doc-PII byte-gate has already blocked a round of sentinels of exactly that class**, forcing them to be rebuilt from invented tokens.

If both are true, the context layer instructs authors to write values that the commit gate then rejects — and the author has no way to see why, because the real denylist is the uncommitted, gitignored `secrets/pii-denylist.txt`. The failure presents as an unexplained block on text the rules told you to write.

## Why It Matters

This is a **contradiction between two parts of the safety system**, and it outlives any one epic. The cost is not just friction: an author who cannot reconcile a rule with a gate is being trained to route around one of them, and the one that gives way will be the gate, because the gate is the thing standing between them and a commit.

It also degrades the gate's signal. A block that fires on a prescribed placeholder is indistinguishable, from the author's side, from a block that caught a real identifier — so the response to both becomes "change the string until it passes" rather than "find out what I leaked."

During E-275 planning this was handled by building sentinels from scratch and binding the constraint as an epic Technical Note. That works per-epic and does not scale.

## Rough Timing

Promote when anything next touches `.claude/rules/api-docs.md`, the doc-PII gate, or a doc tree the gate covers. No urgency otherwise — the workaround is cheap once you know about it, and knowing about it is what this capture provides.

## Dependencies & Blockers
- [ ] **Confirm the premise.** The seed is a relay and was found to carry five other claims that did not survive checking. Nobody has reproduced the block against the prescribed taxonomy specifically.

## Open Questions
- **Which token actually collided?** Unknown and deliberately not investigated — reading `secrets/pii-denylist.txt` to find out would pull real identifiers into an agent's context to avoid writing them, which is the wrong trade. The right diagnostic is to run `scripts/check_doc_pii.sh` against a file containing the prescribed placeholders and read the exit code and path, not the token.
- **Which side should give?** Plausibly the rule — a placeholder vocabulary of genuinely invented tokens has no collision surface at all, whereas `Anytown`/`Springfield`/`Eagles` are real English place and mascot words that any denylist drawn from real data may legitimately contain. But that is a claude-architect call.
- Does the same contradiction exist for other prescribed values — person names, venue names, the `example.com` domain?
- Is there a way for the gate to say "this is a prescribed placeholder, allow it" without weakening it? Probably an allowlist, and probably worth less than just changing the taxonomy.

## Notes

Surfaced during E-275 planning as a conflict between two context-layer files, neither of which is wrong on its own terms.

Companion finding from the same pass: [[IDEA-204]], the gate's tree coverage. Together they are the two halves of "the doc-PII gate does not do what a reader of the rules would expect" — one about what it blocks that it should not, one about what it does not see at all. **Evaluate them together; they will almost certainly be one piece of work.**

Domain: claude-architect.

Related: [[IDEA-204]], [[IDEA-170]] (the doc-PII gate cannot see `src`), [[IDEA-180]] (gate tree scope and history gap).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
