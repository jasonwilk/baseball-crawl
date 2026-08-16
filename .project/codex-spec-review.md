# Spec-Review Rubric for baseball-crawl

## Setup

Before reviewing, read this workflow context file:
1. `/workspaces/baseball-crawl/CLAUDE.md` -- project principles, tech stack, chunk lifecycle, workflow conventions

This is a **planning artifact review**, not a code review. Evaluate the one-page chunk spec provided against the project's workflow contracts and planning quality standards.

**A spec is a CLAIM, not a fact.** The single most valuable thing this review does is resolve the spec's assertions against the actual repository -- file paths, line numbers, counts, command behavior, what a gate does today. Check them; do not take them on the spec's word.

## Evaluation Checklist

Check each item and report findings:

### 1. Verification Commands: Concrete and Observable
- Does the spec carry a Verification section of numbered commands with expected results?
- Can each one be confirmed by observation (file exists, command exits 0, count equals N, output contains X) rather than by judgment?
- Are any verification steps ambiguous, subjective, or dependent on unstated context?
- Does any step claim a clean result without a **positive control** -- a demonstration that the instrument can fail? A sweep, scan, or gate never shown failing proves nothing.
- Is any step *unsatisfiable as written* -- does the work described elsewhere in the spec guarantee a hit the step says will not be there?

### 2. Scope Correctness
- Does every file the work names actually belong to the change being described, and is anything it will inevitably touch missing from the Files list?
- Are the destructive seams named where the work reaches them (`bb report generate`, `bb db purge-scouting`)?
- Does the work strand anything: a pointer to a file being deleted or moved, a cross-reference in surviving prose, a rule whose `paths:` frontmatter names a tree being frozen?

### 3. Claims vs. Repo Reality
- Are the spec's claims about existing infrastructure accurate -- file paths, line numbers, module names, counts, command and gate behavior? Open the files and check.
- Does the spec describe as future something that is already done, or as "will be created" something that already exists?
- Are measurements (byte counts, file counts, line ranges) still true today, and does the spec say when they were taken?
- Does the spec clearly distinguish what exists now from what this chunk will create?

### 4. Missing Expert Consultation
- Consultation is expected before the work is called ready when it touches:
  - Domain statistics or coaching logic (`baseball-coach` should be consulted)
  - API behavior or GameChanger endpoint patterns (`api-scout` should be consulted)
- Does the spec document that consultation occurred where it was warranted? If it was skipped, is there a stated reason?

### 5. Safety Absolutes Without an Attempted Counterexample
- Does the spec make an **absolute claim about deletion, destruction, or a safety guarantee** -- "cannot delete", "always refuses", "never retires more than", "aborts on"? For each one, try to BUILD the counterexample: construct the input, ordering, or FK action under which the claim fails. A surviving absolute is shippable; a falsified one is a blocking finding.
- **Reasoning to an absolute is not evidence for it.** In E-270 the claim "a KEEP-to-PURGE foreign key aborts the purge" was true only for a default-action FK; an `ON DELETE CASCADE` edge raises nothing, commits, and destroys the preserved row. That epic shipped 7 prose defects of this class, E-272 shipped the NRBL over-rest claim, and E-276's planning produced 4-5 wrong gate absolutes -- **every one of them killed by construction, none by review.**

### 6. Spec Hygiene
- Does the spec name its **out of scope** -- what a reader would reasonably expect here and will not find, and where it lives instead?
- Does it carry a **progress log**?
- Does it name a **person**? No spec may. Real team/org identifiers belong to the placeholder taxonomy in `.claude/rules/api-docs.md`; a person's name is never acceptable.
- Does its **Status** read one of the five values in CLAUDE.md step 9 -- `COMPLETE (this commit)`, `READY`, `PARKED + why`, `STUB`, `OPEN + what decision is owed` -- or explicitly claim a chunk in flight? A sixth status is a finding.
- A `COMPLETE` Status names its acceptance state: `acceptance: run` or `acceptance: owed at <chunk>` (audit-5 ruling -- a landed chunk whose proof never ran must be distinguishable from a proven one). And no Status hides behind a bare verdict word: "clean" is a finding; the severity breakdown ("0 P1/P2, 3 P3 folded") is the claim.

## Re-Review Protocol

**Review rounds are a tripwire, not a treadmill** (operator ruling 2026-08-15, from a measured
7-round loop where rounds 5 and 6 were largely reviewing defects earlier fold-ins introduced).
After round 2, continue only if the latest round found a P1/P2 that is NOT an artifact of a prior
fold-in. A spec still generating fresh blockers at round 3+ is usually too big to hold its own
consistency — stop reviewing, bring the operator the split-or-shrink trade, and let the next
round review a smaller thing.

Round 2+ reviews (after the findings are incorporated) follow a scoped process:

1. Read the change summary identifying what was modified.
2. Verify each claimed fix was actually applied in the updated spec.
3. Check that fixes did not introduce new inconsistencies in adjacent text -- a corrected count often appears in more than one place.
4. Do NOT re-review unchanged sections. Prior-round findings on untouched sections are closed. Only re-evaluate what was touched or is adjacent to a change.

**A review claim covers the reviewed TEXT, not the file** (audit-5 ruling: a 19-line section was authored 68 minutes after the Status already said "codex-reviewed"). Edits made after the final round get a re-round OR an explicit unreviewed-edits note in the progress log, naming each edit. A Status asserting review coverage over post-review text is a finding.

## Reporting

- Cite the spec's section heading (e.g. "§4 Templates", "Verification step 2") for every finding.
- Group findings by checklist category.
- Rate each finding: **P1** (blocks execution), **P2** (should fix before executing), **P3** (minor, fix if easy).
- If the spec is clean across all categories, state explicitly: "No findings. This spec is ready to execute."
- Do not report stylistic opinions on prose quality unless they cause genuine ambiguity in a verification step.
