---
name: new-gate-inherits-hook-enumeration
description: MEASURED — a new gate bolted into an existing hook silently inherits that hook's early exits and its staged-path --diff-filter; ACM excludes renames, so a rename-shaped archive move is invisible.
metadata:
  type: feedback
---

When a spec adds a gate to an EXISTING hook (`.githooks/pre-commit`, etc.), the gate
inherits two things nobody writes down: the hook's **early `exit 0` paths** and its
**staged-path enumeration filter**. Check both before accepting the gate as fail-closed.

**Why:** E-279-04 AC-5 specified a fail-closed archive-reference backstop keyed on "the
staged path list". `.githooks/pre-commit:22-24` builds that list with
`git diff --cached --name-only -z --diff-filter=ACM`. **`ACM` excludes renames (`R`).**
Measured in a scratch repo, not reasoned:

| staging shape | `--diff-filter=ACM` | `--diff-filter=ACMR` |
|---|---|---|
| rename (`git mv`, the DEFAULT — `diff.renames` is true) | **0 entries** | archive path ✓ |
| delete+add (`--no-renames`) | archive path ✓ | archive path ✓ |

So the gate would never fire on the normal archive move. The AC made this worse: it warned
against conditioning on `rename from` and told the implementer to "verify the trigger fires
on a **delete+add**-shaped staging" — **the case that works.** The spec's own verification
step pointed away from the failure, so a green test would have certified a dead gate.
Same hook also `exit 0`s at `:8-11` (scanner file absent) and `:26-28` (empty ACM list),
either of which a gate placed below inherits silently.

**The sharper, SECURITY-relevant form — `R` is excluded at ANY similarity score.** A rename
is not content-neutral: `git mv` PLUS an edit in the same staging still classifies as `R`
(measured at 73% and, by claude-architect, at 57%), and `--diff-filter=ACM` drops it either
way. So `git mv` a file, add a credential to it, stage, commit — and `.githooks/pre-commit`
enumerates NOTHING, `:26-28` exits 0, and **neither the PII scanner nor the doc-PII byte-gate
runs**. Verified end-to-end in E-279 planning with a real-shaped token. This is a live
fail-open in the repo's own credential gate, independent of any epic. Fix is one token:
`--diff-filter=ACMR`, whose `--name-only` yields the DESTINATION path (confirmed to exist on
disk and contain the added line, so it is scannable). **The reasoning that deferred it was
"renames are content-neutral" — a rename-with-edit falsifies that, which is why executing the
case reversed the disposition.** Escalated to the operator 2026-07-28.

**How to apply:** for any story adding a gate to an existing hook or script, (1) read the
host's enumeration command and check its `--diff-filter` against the shapes the gate must
catch, (2) enumerate the host's early exits and ask which the new gate sits below, and
(3) when an AC names ONE shape to verify, treat the UNNAMED shape as the likely defect —
build it and run it. Relates to [[tool_gotchas]] (git commands that answer a narrower
question than asked) and the checklist's safety-absolutes rule: build the counterexample,
do not reason about it.
