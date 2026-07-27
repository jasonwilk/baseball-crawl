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

A verification of the kind named above -- that a CONCEPT was fully added, removed, or reconciled -- is complete only when all three of the following are done. A localized edit that claims nothing about a concept's reach (a typo fix, a broken link, one reworded sentence) is not one of these and owes no sweep.

1. **Token grep** -- grep the obvious keyword(s) for the concept across the affected tree. This is the starting point, never the whole check.
2. **Synonym expansion** -- before concluding, enumerate the ways the concept is expressed WITHOUT the grepped token (paraphrases, hyphen-free forms, domain synonyms, pronoun/abbreviation references) and grep those too. Ask: "if someone described this idea without using my search term, what words would they use?" Grep each.
3. **Semantic read of the touched sections** -- actually read the prose in and around every changed region (and any section the concept logically belongs in), confirming the concept is coherent after the change -- fully present where intended, fully absent where removed, and not contradicted or half-stated elsewhere. A clean grep is not a substitute for reading the sections.

A verification that ran only step 1 is incomplete: report it as a gap, not a pass.

**And all three steps bound REACH, not correctness -- a prose sweep structurally cannot see code that still PARSES.** A retirement strands executables as readily as sentences: a probe, harness, or fixture that imports cleanly, runs, and reports a plausible number about a configuration that no longer ships. Nothing in it is stale to READ, so no grep of `docs/`, `.claude/` or `epics/` will surface it, and its output is the quiet kind that reports nothing wrong (`.claude/rules/tool-output-integrity.md`, "A check that RAN is not a check that WORKED"). E-276's closure found exactly this in two harness files. **When the retired thing has executable consumers, the sweep needs an import/path scan or a run -- not a read.** And a substring match is not that scan: the first attempt there matched `t_game`, which also hit `first_game`, `next_game` "and forty other files".

## Retired Claims Survive in Forms Carrying None of Their Tokens

A claim you REMOVED is harder to sweep than a concept you added: it survives not as a restatement but as residue that no longer looks like a claim. E-272 retired one sentence ("the season-absent default is the stricter table, so it over-rests") and found five survivals across four structural positions, plus a sixth shape in the same review -- a **title** encoding the retired predicate above a correct body; an **index row** still asserting what its own topic file has retracted; a **rating or priority derived from the claim but sharing none of its words** (an urgency of "no urgency" that rested entirely on the retired safety claim -- no grep will ever find this); a **compressed adjective** carrying the whole claim in one word ("safe", "conservative") inside an otherwise unrelated sentence; and an error **hiding behind a legitimate neighbouring use of the same token** (one wrong "fourth" beside two correct ones, so the grep hit looks accounted for).

**The shape also runs in REVERSE, which is why step 3 can never be dropped: the REFUTATION can be the sentence carrying none of the claim's tokens.** In E-276 a 41-line memory file held both *"a wrong delete self-heals"* and, four paragraphs below, the material that makes it false (*"the protection runs backwards with respect to severity"*) -- sharing not one word, so **no grep for the retired claim can ever surface the sentence that kills it**. A contradiction can sit inside one short file indefinitely and only READING it finds them together. Same trap from the other side: fresh, correct, supporting material landing next to a retired sentence makes the whole hit read as accounted for -- the live half gets harder to lose and the retired half harder to see.

So when the swept concept is a RETIREMENT, step 2 must enumerate the **judgements that DEPENDED on the claim**, not merely rephrasings of it -- every rating, priority, risk adjective, and summary line in the neighbourhood. Ask "what would I have written differently if I had never believed this?" And check each hit individually even when a neighbouring hit is correct.

## A Quoted Tombstone Is Grep-Indistinguishable From the Live Claim It Retired

This repo retires claims as **quoted tombstones rather than silent deletions**, because a silently corrected claim is one a future reader reintroduces. **The practice is right and stays.** But the quotation preserves every token of the retired text, so a searcher greps the stale phrase and gets a hit that looks live: in E-277 a reviewer flagged that a story still read *"THE FOUR-CELL MATRIX HAS NOT BEEN RUN AT ALL"* -- already retired, and the string it found was **inside the dated tombstone marking it retired**. Nobody was careless; the artifact is designed to keep that text findable.

Remedies, cheapest first: **(i) put the retirement marker BEFORE the quotation, on the same line**, so the first token a reader meets is `⚰ RETIRED`; **(ii) read the surrounding line before ruling a stale-looking string live** -- the standing "grep finds candidates, only a Read confirms" rule, which covers this exactly; **(iii) do NOT respond by dropping tombstones.** The cost asymmetry is the whole point: **a re-reported fix costs one message; a silently reintroduced claim costs whatever the claim costs.**

**Why the noise is worth accepting, and exactly what it looks like when it fires.** The practice trades a **silent staleness** for a **noisy false positive**: the retired token survives on purpose, so the grep **over-matches rather than under-matching** -- the right trade by this repo's own principle, since an over-match arrives visibly and must be dispositioned while an under-match is indistinguishable from absence. **But it holds only if the reader RESOLVES each hit instead of counting them.** The trap is that **the count moves in the WRONG DIRECTION after a successful sweep**: E-277's three corrected sites left *more* `_team_orphan_pred` matches than before the repair (10 across 3 files), so **a pass verifying the sweep by counting the retired token reads a false failure -- it reports a regression that is actually the repair.** Three categories share the one token and **only a literal read separates them: tombstone (evidence) · correct use (a live code fact) · live residue (the only one to fix).** The confirmation pass that got this right did so by METHOD rather than luck -- it read and quoted each site individually and never counted the token.

**And a false CREDIT outlives a false claim.** Attribution is swept like any other prose: a TRUE sentence in the WRONG POSITION produces a citation defect that no truth-check reaches, because every sentence in it is correct. In E-277 an unattributed paragraph abutted a block headed *"THREE BOUNDS, all `cr4`'s"*, and unattributed-in-a-PM-verdict reads as PM's -- one skim from being read as a fourth `cr4` bound. **Where an unattributed passage abuts an attributed block, name the boundary in BOTH directions.** The durable mechanism: **crediting someone converts a statement into a fact about a person, and people do not re-open those.** So take the awkwardness of naming yourself in a document you author -- under-crediting to avoid looking self-serving puts a false citation in the durable record to protect the author's modesty, which is the worse trade.

## Relationship to Other Rules

- This is the doc/prose-surface companion to the tool-output-integrity grep prohibition (`.claude/rules/tool-output-integrity.md`, Prohibition 3): a grep hit -- or a grep miss -- is a candidate signal, never a ruling. Confirm with a read.
- The Closure CR Integration Review (`.claude/skills/implement/SKILL.md`, Phase 5) is the unconditional closure pass under which context-layer epics receive their combined-diff review; this rule governs how that review verifies doc/prose concepts.
