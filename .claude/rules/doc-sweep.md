---
paths:
  - "docs/**"
  - ".claude/**"
  - "epics/**"
  - ".project/**"
---

# Doc-Sweep Discipline

## Purpose

When a change touches documentation or context-layer prose (`docs/`, `.claude/`, `epics/`, `.project/`), verifying it by keyword grep alone is not sufficient. Prose expresses a concept many ways; a token-grep for the obvious keyword misses the same idea stated in different words. This rule requires a **semantic** review paired with the grep, not a grep in isolation.

**Why:** E-250's de-scope sweep grepped for hyphenated season tokens and missed the prose "across games and seasons" -- the concept survived the keyword-only sweep because it was phrased without the searched token. A grep confirms the tokens you thought of; it says nothing about the ones you did not.

## When This Applies

Whenever a review (the Closure CR Integration Review, a per-story CR of a context-layer/doc story, or any deliberate doc-consistency sweep) verifies that a concept was fully added, removed, or reconciled across the doc/context layer. It auto-loads for the code-reviewer via the Step-2 rule-glob mechanism (`.claude/agents/code-reviewer.md` Step 2 item 6) whenever the reviewed diff touches files matching the `paths:` globs above.

## The Discipline

A doc/context-layer verification is complete only when all three of the following are done:

1. **Token grep** -- grep the obvious keyword(s) for the concept across the affected tree. This is the starting point, never the whole check.
2. **Synonym expansion** -- before concluding, enumerate the ways the concept is expressed WITHOUT the grepped token (paraphrases, hyphen-free forms, domain synonyms, pronoun/abbreviation references) and grep those too. Ask: "if someone described this idea without using my search term, what words would they use?" Grep each.
3. **Semantic read of the touched sections** -- actually read the prose in and around every changed region (and any section the concept logically belongs in), confirming the concept is coherent after the change -- fully present where intended, fully absent where removed, and not contradicted or half-stated elsewhere. A clean grep is not a substitute for reading the sections.

A verification that ran only step 1 is incomplete: report it as a gap, not a pass.

## Retired Claims Survive in Forms Carrying None of Their Tokens

A claim you REMOVED is harder to sweep than a concept you added: it survives not as a restatement but as residue that no longer looks like a claim. E-272 retired one sentence ("the season-absent default is the stricter table, so it over-rests") and found five survivals across four structural positions, plus a sixth shape in the same review -- a **title** encoding the retired predicate above a correct body; an **index row** still asserting what its own topic file has retracted; a **rating or priority derived from the claim but sharing none of its words** (an urgency of "no urgency" that rested entirely on the retired safety claim -- no grep will ever find this); a **compressed adjective** carrying the whole claim in one word ("safe", "conservative") inside an otherwise unrelated sentence; and an error **hiding behind a legitimate neighbouring use of the same token** (one wrong "fourth" beside two correct ones, so the grep hit looks accounted for).

So when the swept concept is a RETIREMENT, step 2 must enumerate the **judgements that DEPENDED on the claim**, not merely rephrasings of it -- every rating, priority, risk adjective, and summary line in the neighbourhood. Ask "what would I have written differently if I had never believed this?" And check each hit individually even when a neighbouring hit is correct.

## Relationship to Other Rules

- This is the doc/prose-surface companion to the tool-output-integrity grep prohibition (`.claude/rules/tool-output-integrity.md`, Prohibition 3): a grep hit -- or a grep miss -- is a candidate signal, never a ruling. Confirm with a read.
- The Closure CR Integration Review (`.claude/skills/implement/SKILL.md`, Phase 5) is the unconditional closure pass under which context-layer epics receive their combined-diff review; this rule governs how that review verifies doc/prose concepts.
