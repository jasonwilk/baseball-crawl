# IDEA-232: a missing PII scanner skips the doc-PII byte-gate, which does not depend on it

## Status
`CANDIDATE` — **narrow, real, and deliberately NOT bundled with its bigger sibling.** Found during E-279 iteration-2 review; the sibling shipped, this did not.

## Summary

`.githooks/pre-commit:8-11` exits 0 for the WHOLE hook when `src/safety/pii_scanner.py` is absent:

```
if [ ! -f "$REPO_ROOT/src/safety/pii_scanner.py" ]; then
  echo "[pii-hook] Scanner not installed yet. Skipping PII check."
  exit 0
fi
```

The message says "Skipping PII check," and for the pattern scanner that is correct — it cannot run without its own module. **But the exit is above the doc-PII byte-gate at `:67-126`, which runs `scripts/check_doc_pii.sh` — a standalone shell harness with a denylist that has NO dependency on `src/safety/pii_scanner.py` whatsoever.** So a gate that could have run is skipped for the absence of a file it never uses, and the operator-visible line understates what was skipped.

## Why It Matters

Small, and worth stating both sides so nobody over- or under-reads it.

**Against urgency:** this requires the repo to be in a broken state. `src/safety/pii_scanner.py` is committed, so reaching it means someone deleted a tracked file or is committing from a partial checkout. It is not reachable in ordinary operation.

**For fixing it anyway:** `.claude/rules/tool-output-integrity.md` is explicit that **a check that RAN is not a check that WORKED**, and a gate skipped silently is the shape that rule exists to catch. The hook elsewhere holds the opposite posture on purpose — E-279's new archive-reference gate is specified to BLOCK when its own script is missing ("a gate that never ran is INVALID, not a pass"), and `check_doc_pii.sh` exit 2 exists so a gutted harness fails rather than passes. So `:8-11` is the odd one out in its own file, and E-279 story 04 had to add an explicit "do not harmonize these two postures" note to stop a future reader making the NEW gate match this OLD one — which is the wrong direction.

The likely fix is small: move the doc-PII block above the scanner-absent exit, or narrow that exit so it skips only the pattern-scanner stage. Either way the message should name what was actually skipped.

## Why This Was NOT Folded Into E-279 or Its Sibling Commit

Two separate scope decisions, both deliberate.

1. **Not into E-279.** E-279 is a micro-epic under a standing operator steer not to grow. It closes this exposure for its OWN gate — story 04 AC-5 places the archive-reference gate FIRST in the hook, above every early exit — so nothing E-279 ships is affected. The residual is exactly one pre-existing gate.
2. **Not bundled with the rename fail-open** (the sibling, shipped as commit `9b62395`, `ACM`→`ACMR`). That one is reachable in **ordinary operation** — move a file and edit it in the same commit, which is what `git add -A` after a `git mv` does — and it carried a real credential past both gates in a controlled test. Bundling a weaker item with a stronger one invites a single disposition for both and dilutes the urgent one. PM packaging decision; claude-architect raised the severity distinction that decided it and concurred.

## Rough Timing

**Not urgent.** Promote when either fires:

- Anyone is already editing `.githooks/pre-commit` for another reason — the marginal cost is near zero and this is cheap to fold in.
- The scanner-absent path is actually hit (a partial checkout, a fresh-clone-before-install workflow, a CI stage that copies a subset of the tree).

Prefer the first. This is a poor errand and a good passenger.

## Dependencies & Blockers
- [ ] **E-279 should land first if the two would touch the same region.** E-279 inserts its gate at the top of the hook; a fix here moves or narrows an exit near the top. Sequencing them avoids a needless collision, though the scopes are disjoint in principle.
- [ ] **Owner is claude-architect** (`.githooks/**` is context-layer-adjacent hook machinery, and it authored both the E-279 gate and the sibling fix).

## Open Questions

- **Move the doc-PII block above `:8-11`, or narrow the exit?** Moving is smaller but reorders the file; narrowing keeps the order and makes the dependency explicit. The narrowing probably reads better, since it states WHY the scanner's absence matters to one gate and not the other.
- **Are there other consumers of that early exit's blast radius?** Only the two gates were enumerated during E-279 review. If a third gate is ever added below it, it inherits the skip silently — which is an argument for narrowing rather than moving.
- **Should the message change regardless of the fix?** "Skipping PII check" is singular and understates a whole-hook exit. Even with no behavioral change, naming what was skipped is honest and nearly free.

## Notes

Filed 2026-07-28 by product-manager during E-279 iteration-2 triage. Surfaced by `cr-e279` (as the promoted half of its CR-6 finding, once `:26-28` turned out to carry a live bypass) and confirmed by `ca-e279`, which narrowed the scope to what is recorded here: the residual is the doc-PII gate alone, because E-279's first-placement bound already protects the archive gate.

**The measurement that decided the sibling's severity is worth keeping:** a `git mv` plus a same-staging edit classifies as `R` at 57% and 73% similarity in two independent probes, and `--diff-filter=ACM` returns zero entries for it. That is the sibling's ground, not this idea's — recorded here only so a future reader does not conflate the two and re-open a decision that has already shipped.

Related: [[IDEA-228]] and [[IDEA-230]] (E-279's sources); [[IDEA-231]] (the other E-279 scope split). The shipped sibling has no idea file by design — a landed fix needs no parking ticket, and commit `9b62395` is its record.

---
Created: 2026-07-28
Last reviewed: 2026-07-28
Review by: 2026-10-26
