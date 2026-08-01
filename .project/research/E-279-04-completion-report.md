# E-279-04 — Archive-reference sweep script and its two call sites

**Status: implementation complete; ONE ITEM AWAITING ROUTING (see "Blocking" below).**

> ⚠️ **This report deliberately never spells this epic's pre-archive `epics/` path**, and neither does any quoted tool output reproduced below — the gate this story ships makes that literal unspellable outside `.project/archive/` from the moment it lands, and a completion report is not exempt from the rule it documents. Writing this paragraph is what the standing cost feels like in practice.

## What shipped

| File | Change |
|---|---|
| `scripts/check_archive_refs.sh` | created — the sweep |
| `.githooks/pre-commit` | additive gate, placed FIRST (83 insertions, **0 deletions**) |
| `.claude/skills/implement/SKILL.md` | sub-step 3 (iii) reserved slot filled |
| `src/reports/llm_analysis.py` | AC-8 one-path repoint, comment-only |
| `tests/test_archive_refs_gate.py` | created — 28 tests |

**Exit contract** (the shape `check_doc_pii.sh` established): `0` PASS · `1` BLOCKED · `2` INVALID. `1` and `2` are distinct because a gate that never ran is INVALID, not a pass — zero findings and zero executions are otherwise the same counter state.

## ⚠️ Blocking — this epic currently FAILS its own gate

TN-2 makes "E-279 passes the gate it ships" a property of this story's output. **Measured, not argued:** the tree was copied, the archiving performed, and the real script run against it. **Exit 1, four surviving references across three files.**

Two further references self-clear — they live in the epic file itself, which moves into `.project/archive/` at sub-step 3 (ii) and is inside the excluded tree by the time the gate runs. The instrument confirmed that prediction independently.

| Site | Class | Owner |
|---|---|---|
| `.project/research/E-279-01-completion-report.md` ×2 | **EVIDENCE** — records what `git status` showed at a moment | product-manager |
| `.claude/agent-memory/claude-architect/dispatch-telemetry-design.md:12` | **EVIDENCE** — a statement about design time | claude-architect |
| `.claude/agent-memory/product-manager/e279-planning-state.md:3` | **CRITERION** — a pointer a reader is meant to follow | product-manager |

**Three evidence, one criterion.** TN-3's remedy applies to the evidence sites: **reword so the line does not spell the dead path** — repointing them would falsify the record. The criterion site genuinely wants repointing.

**Not actioned, awaiting routing.** Three of four are PM-owned. The fourth is mine, and I have not touched it either: story 04's Files list does not name it, and I produced one wrong self-authored scope bound already today (below). Correcting an over-narrow bound by inventing an over-wide one is not an improvement.

**The epic anticipated the CLASS (TN-3) but nobody ran the predicate against E-279 itself.** That is why this surfaces now rather than at the closure commit, where AC-6 has deliberately removed every exit but `--no-verify`.

## Verification

**AC-1 both directions** — clean tree exits 0; a planted reference exits 1 naming the file. A clean exit certifies nothing without the second.

**AC-2** — nine malformed arguments each exit 2: empty, `E-*`, `*`, `E-27`, `E-2799`, `epics`, `E-abc`, an id-plus-slug, and a traversal attempt. Anchoring uses a `case` glob rather than a regex, because a case pattern matches the whole word by construction and an unanchored regex is how a wildcard sneaks through a check like this.

**AC-5 trigger, both staged shapes** — fires on rename-shaped (`R100`) and on delete+add-shaped archiving, with the staged shape asserted as a precondition rather than assumed. Nothing conditions on `rename from`.

**AC-5 RED states, all three pass the gate** — modify-only under an already-archived epic; add-only under one; delete-only from a still-live `epics/` directory. Each scratch repo carries a *real* dead reference to an already-archived epic, so a presence-keyed gate would fire on all three. That reference is what makes the RED states meaningful instead of vacuous.

**AC-5 ENUMERATION** — asserted against the source with comment lines stripped, because the block's comments discuss `STAGED_ARR` at length and explaining a trap is the opposite of falling into it. An inert gate is shape-identical to one correctly declining to fire, so this cannot be tested behaviorally.

**AC-5 PLACEMENT — the discriminating probe.** Every scratch repo lacks `src/safety/pii_scanner.py`, so the hook's missing-scanner skip fires. **Every "the gate blocked" assertion is therefore also a demonstration that it ran above that skip.** Made explicit by mutating placement only:

```
SHIPPED (gate FIRST)  -> BLOCKED
MUTANT  (gate BELOW)  -> ALLOWED   <- inert, exactly AC-5's RED state
```

**AC-8 verified by ABSENCE with a positive control in the same call** — `epics/E-243-` → 0, the old wrapped form → 0, control `Variant A` → 7 (so the pattern ran). Words are byte-identical after path substitution; only the path literal and its line breaks changed. The new path is contiguous on one line: wrapping it mid-token is what made the original citation unverifiable and invisible to a literal sweep.

**AC-9 — purely additive**: `83 insertions, 0 deletions`. All seven pinned behaviors present, checked by phrase anchor rather than line number. **`--diff-filter=ACMR` is untouched**; `9b62395` is the baseline, and reverting it would reintroduce a security hole.

**Mutation probes — 4 built, 4 KILLED**, each asserting the mutation changed the file before running and restoring from a **scratchpad copy** afterwards with the hash re-checked. No index restore was used anywhere: with prior stories staged, the index holds the previous story's state.

| Mutation | Verdict |
|---|---|
| drop `--no-renames` from the `D` half | KILLED (4 failed) |
| AND → OR (either half fires) | KILLED (1 failed) |
| drop the `.project/archive/` exclusion | KILLED (1 failed) |
| loosen the epic-id validation | KILLED (10 failed) |

Suite green before and after: **28 passed** targeted, **4403 passed** full.

## Findings that outlived their own criteria

**TN-3 and TN-14 disagree about the same mechanism, and TN-14's own commit is what falsified TN-3.** TN-3 states as a *measurement* that a pure-rename staged set yields zero entries, so the empty-set exit returns 0 before anything below it runs. That is correct **for `ACM`** — reproduced exactly. But the file reads `ACMR`, landed by `9b62395`, the very commit TN-14 documents; under `ACMR` the same rename yields **one** entry and the early exit never fires.

**The requirement was unaffected, and AC-5 is why**: it instructed re-derivation and noted that placing the gate first satisfies the requirement *without the list being complete*. The hedge absorbed a falsified premise exactly as designed.

**Placement-first survives on the OTHER exit, which is real** — the scanner-absent skip, already named in TN-14 as the residual this bound closes. The shipped comment records that reason and not the falsified one.

Second-order, moving the other way: TN-3's hand-run claim is now **understated** — under `ACMR` a hand-run archive reaches a below-placed gate too. Reporting only the failure would misrepresent a widening as a weakening.

**A scope bound of mine would have dropped AC-8.** My pre-registered DoD said *"I am not repairing any of the 60 dead references."* AC-8 requires repairing exactly one. The bound was drawn from my own enumeration and then applied as though it outranked the spec; unread, it would have shipped the story without AC-8 while reading as principled scoping. **A bound derived from my own measurement is not evidence about scope — only the spec is.** Pre-registration constrains how I work, never what is required. The same instinct recurred inside AC-8 itself: my first repoint added a two-line parenthetical explaining the wrap, which is prose the TN-4 ceiling does not permit. Removed.

**Counts reconciled rather than disputed.** I measured 60 dead literals; TN-6 says 25. Both correct — mine included the archive-internal historical records AC-1 excludes. Restricted to AC-1's scope: **25 dead, exactly matching**. Distinct literals 28 vs 27, the extra being this epic's own *live* path, created after TN-6 was measured. Files 37 vs 33; three of the four are planning artifacts first committed 2026-07-29 that quote existing dead paths as evidence, which is why files rose while dead literals did not. **I cannot account for the fourth and have not invented a mechanism for it**; it does not affect scope.

## Bounds — what this gate does NOT do

1. **Literal paths only.** A clean exit means *no literal `epics/` + id + slug reference survives outside the archive tree*. A line naming the epic by ID without spelling its path is out of reach **by construction**. AC-7 says so and the skill now says so.
2. **Working tree, not the index.** Both call sites need this — the in-window hold runs before `git add -A`, so the state it must see is unstaged by construction. Consequence at the pre-commit site: under `git add -p` or staged-then-edited, tree and index diverge and this gate judges the tree.
3. **One epic per invocation.** Not a convenience — a repo-wide sweep collides immediately with hard-coded epic-path literals in two test files, one synthetic and one that is live dead paths serving as **evidence**. Neither was touched.
