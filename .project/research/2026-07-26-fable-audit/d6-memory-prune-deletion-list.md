# D6 — agent-memory prune: deletion list for operator ruling

Written 2026-07-26 by the successor CA. **Nothing here has been executed.** The
operator rules on this list before any deletion, per the standing gate.

## The scoping recommendation, first, because it changes what you are ruling on

The mandate was a *near-complete* prune: "reset aggressively; selectively
re-bootstrap." Having inventoried the tree, I want to put a narrower proposal in
front of you, and say plainly why.

The tree is 116 files and 1.2 MB, but **only nine of those files cost any
context**. `MEMORY.md` is loaded into an agent's system prompt; every other file
is inert until something reads it. The nine index files total ~92 KB, and an
agent loads only its own, so the real per-agent ambient cost runs 4.8 KB
(docs-writer) to 20.1 KB (claude-architect). The other 107 files cost nothing
until retrieved, and retrieving them is the point of having them.

So the aggressive-reset case rests on hygiene rather than on context cost, and
against it stands a lesson already recorded in claude-architect's own memory:
*"The principle guides FUTURE decisions. It does NOT justify deleting existing
working context, architectural details, or agent configs."* That line exists
because a previous simple-first pass deleted things that were load-bearing. Your
recorded preference is that architectural detail be preserved.

**Recommendation: prune the always-loaded tier hard, and treat the 107 topic
files as a separate question with a much higher bar.** That gets the entire
measurable benefit. If you want the topic files culled anyway, say so and it
becomes its own pass with its own list — but it should not ride in on the
authority of a context-cost argument that does not apply to it.

Everything below is scoped to that recommendation.

## Tier 1 — delete because WRONG (highest confidence; these are actively harmful)

Each verified by reading both the memory line and the current rule text.

**1. `software-engineer/MEMORY.md` line 12: "Store raw API responses before
transforming (raw -> processed pipeline)".** There is no raw tier. Four
committed sources say so: `CLAUDE.md` ("no stored raw-response tier"),
`canonical-seams.md`, `http-discipline.md` (raw bytes persist only on the
out-of-band capture and exploration paths), and `architecture-subsystems.md`,
which deleted the file-reading loader twin in E-256 and warns in terms that fit
this line exactly: following the stale guidance "would rebuild the twin E-256
just removed." This is a stale instruction sitting in the ambient context of the
one agent most likely to act on it.

**2. `data-engineer/MEMORY.md` topic-index line for `etl-patterns.md`, the
phrase "raw-to-processed pipeline".** Same defect, one layer down, and it
survives in a form carrying none of the first one's wording — which is why a
grep for "raw response" alone would have missed it.

**3. `software-engineer/MEMORY.md` line 13: "Use dataclasses or Pydantic models
between functions, not raw dicts".** `python-style.md` is the canonical version
and it has a carve-out this copy dropped: "Prefer dataclasses or Pydantic models
for structured data passed across module boundaries. **Plain dicts are fine for
local or transient use.**" The memory copy reads as an absolute, and it also
runs against CLAUDE.md's core principle ("a dict is better than a class — until
it isn't"). This is duplication that drifted into conflict, which is the
instruction-pair-in-tension class the vendor guidance says degrades output.

## Tier 2 — delete because DUPLICATED, with the durable copy named

**4. `claude-architect/MEMORY.md`, the "Key Architectural Decisions" section —
specifically its one enormous per-epic bullet.** This is the live signal: a
PostToolUse hook fires on this file at 20.1 KB against a 24.4 KB read limit and
asks for compaction under 17.1 KB. The bullet has accreted a codification
summary for every epic from E-077 to E-276, and `epic-codifications.md` in the
same directory carries all 27 of them as proper sections. The index line is
duplicating its own topic file. Proposed replacement is one line pointing at
`epic-codifications.md` plus the handful of live invariants that genuinely
belong in an index. **Estimated saving: 6-7 KB, which alone clears the hook.**
This is my own directory, so it needs no routing — only your ruling.

**5. `code-reviewer/MEMORY.md`, "Mandatory Review Checks" (lines 39-69).** The
SQL Dimension Audit and Multi-Dimension Test Coverage items are present in
`code-reviewer.md`'s own Bug Pattern Checklist, in fuller form and with the
defect citations attached. The agent loads both, so it reads each check twice
with slightly different wording. **Verify before deleting**: the Fallible Call
Chain, Status Write Lifecycle, and Error-Path CLI items may have no counterpart
in the definition — if so they should be PROMOTED into it, not dropped. I have
not yet checked those three, and I am not going to assert they are covered.

**6. `software-engineer/MEMORY.md`, the "Python Style", "Testing Rules" and
"HTTP Request Discipline" headings.** Each is a "See CLAUDE.md and
`.claude/rules/X`" pointer with one or two lines appended. The pointers are fine
and cheap; the appended lines are the question. The conventional-commits line
duplicates CLAUDE.md's Git Conventions verbatim. The `respx`/`responses` line
and the `create_session()` prohibition should be checked against
`testing.md` and `http-discipline.md` before removal — if they are there, delete;
if not, they are the only copy and must stay.

## Not on the list, and why — so nobody re-opens these

- **`ux-designer/MEMORY.md`'s "Superseded (do NOT present as current design
  guidance)" section.** It looks like dead weight and is the opposite: a
  deliberate tombstone that stops an agent presenting removed surfaces as live.
  Deleting it restores the failure it was written against.
- **`data-engineer/MEMORY.md`'s "Do NOT trust any concrete next-migration-number
  claim" line.** Self-aware anti-staleness guidance. Keep.
- **`docs-writer/MEMORY.md` in full.** 4.8 KB, entirely current, structured as an
  index of file locations and conventions that are genuinely not derivable
  without opening a dozen files. It is the model the others should look like.
- **The nine `MEMORY.md` topic-file indexes.** These are what make the deferred
  tier retrievable. Pruning an index to save bytes strands the file it points at.

## Method, for whoever finishes this

The test is the vendor's: *don't save what the repo or chat history already
records.* Applying it needs both halves — find the memory line, then open the
committed file that supposedly supersedes it and read the actual text. Three of
the six findings above changed shape when I did the second half: what looked
like duplication turned out to be a copy that had dropped a carve-out, and one
"stale" line turned out to be describing legacy on-disk trees that really do
still exist (`data/raw/` has `2024-summer`, `2025`, and `2025-spring-hs` in it
right now, exactly as `architecture-subsystems.md` says it should).

Two traps worth naming. A memory line and the rule that supersedes it often
share no vocabulary, so grep finds one and not the other. And a duplicate that
has drifted is more dangerous than a duplicate that has not, while looking less
so — the drifted one reads as an independent confirmation of a rule it actually
contradicts.

## What remains unaudited

The 107 topic files, and the three code-reviewer checks flagged in item 5. The
per-epic consultation records under `baseball-coach/` (nine files, ~78 KB) and
`product-manager/` are the largest untouched block; they are historical records
whose durable copies should be in the archived epics, but "should be" is not
"are", and each needs the second half of the test before it can go on a list.
