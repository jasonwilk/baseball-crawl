---
name: dispatch-git-gotchas
description: git rm stages a deletion, hiding it from code-reviewer's unstaged `git diff` during dispatch; TaskUpdate's owner field sends a real assignment; restore the staging boundary before reporting
metadata:
  type: project
---

# Dispatch git gotchas

## `git rm` silently stages the deletion — CR cannot see it

During dispatch, the staging boundary is: **staged (`git diff --cached main`) = prior
completed stories; unstaged (`git diff`) = the story under review.** Code-reviewer
reviews the *unstaged* diff.

`git rm <path>` deletes the file **and stages the deletion**. The removal therefore
lands in the staged half, mixed in with prior stories' content, and `git diff` shows
**nothing**. A reviewer looking at the current story's diff sees no evidence the file
was ever deleted — the AC "passes" against an invisible change.

Hit in E-256-03: `git rm src/gamechanger/bridge.py` folded a 97-line deletion into
stories 01/02/07's staged content.

**Fix (index-only, worktree deletion preserved):**
```
git restore --staged <path>     # index entry back to HEAD; file stays deleted
git status --porcelain <path>   # expect " D" (unstaged deletion), not "D "
```

**Prefer:** delete files with the `rm` shell builtin or a filesystem delete, not
`git rm`, so the deletion stays unstaged and reviewable. If `git rm` is already run,
unstage it before reporting and *disclose it* — `git restore` is outside the usual
permitted `git status/diff/log` set.

**Also invisible to `git diff`:** a **new untracked file** (e.g. a created `.dockerignore`) never
appears in `git diff` or `git diff --stat`. Use `git status --porcelain` for any completeness claim,
and `md5sum` when asserting a file is *unchanged*.

**Baselines:** mid-epic, the index is the baseline, not `HEAD`. `git show :<file>` reads the staged
tree (prior completed stories); `git show HEAD:<file>` predates every staged story and reports false
deltas.

See [[testing-gotchas]] for the worktree-vs-main import mechanics.

## `TaskUpdate` with `owner` SENDS a real assignment — the task list is not a notepad

Setting a task's `owner` via `TaskUpdate` dispatches a well-formed `task_assignment`
message to that agent, indistinguishable from one the lead composed by hand: it carries
`"assignedBy": "<the setter>"`, a timestamp, and the task's `description` as its body.

Cost the E-277 dispatch a false authorization incident. The sub-lead ran a `TaskUpdate`
batch setting `owner` on three tasks purely to record durable state, believing the list
was passive. Three agents received assignments; one (me) implemented a whole story while
the lead's prose message said HOLD. The lead then chased it as a possible rule breach and
a second undetected coordinator before finding its own `TaskUpdate` batch. Two of the
timestamps were **0.7s apart** — the signature of sequential calls in one batch, and the
detail that identified the cause.

**Implications:**
- **As an implementer**, an assignment arriving as structured JSON is NOT self-evidently
  more authoritative than a prose message from the same agent. When the two conflict,
  say so in one line before writing code. The tie-break is cheap; the silent resolution
  is what turned this into an incident.
- **Never "tidy" the task list** during a dispatch you do not lead — no owner edits, no
  status edits. A cleanup gesture emits a dispatch signal.
- If you must record state, put it in the story Notes or your own memory, not in an
  `owner` field.

### The body it sends is the task's STORED description — frozen at creation, broadcast as current

Second firing, same epic, and this time I was the setter rather than the receiver. I ran
`TaskUpdate(taskId: 3, owner: "se")` on a task I was already working, purely to mark it
mine. It emitted a `task_assignment` stamped `assignedBy: se` whose body was the
description written when the task was CREATED — including *"S03-6 (invariant names wrong
quantity) NOT yet landed"*. That had been true at creation and was false by then: S03-6
was already in the story file as `AC-2.1c` and I had implemented against it.

The stale sentence then circulated as a live fact. Within minutes the lead relayed a
STOP-WORK order built on it — *"the spec you are implementing against is missing the
finding written to stop exactly the failure this story exists to prevent"* — and a
reviewer's independent "never landed" report appeared to corroborate it. One `grep -n
"S03-6"` on the story file returned three hits and settled it; the lead's retraction
called it its own defect, *"a negative search result is a candidate, never a witness."*

**What makes this worse than the first firing:** the first was a spurious *authorization*
(an assignment nobody meant to send). This is a spurious *fact* — the payload asserts
spec state, wears a current timestamp and a real sender, and carries no marker that its
body is older than its envelope. Nothing in it looks stale.

**Implications:**
- **ANY `TaskUpdate` can broadcast the description — the trigger is NOT "setting `owner`".**
  A call passing only `status` (and `activeForm`) returned `Updated task #5 activeForm,
  owner, status` and emitted a `task_assignment`: the harness populates `owner` implicitly
  on a status transition. **My first version of this rule was scoped to `owner` and failed
  against me within the hour, on a task I was updating for accuracy.** Treat every
  `TaskUpdate` as publishing the description **as it currently stands** — re-read it first,
  or update it in the same call. A claim-bearing description is a message you are
  scheduling to send later, at a moment you will not choose.
  - **The generalization, which is the reusable half:** this is the third remedy in one
    dispatch to name the SALIENT cause instead of the SUFFICIENT one (`"discriminate by
    symbol"` when the symbol is identical on both classes; `\.refusals` when the docstring
    writes it bare; `owner` when the harness sets it for you). **When you write a rule,
    ask what the SUFFICIENT condition is, not what you happened to be doing when it
    bit you.**
  - **A test for whether a correction is the right one, and it held 4 for 4 in E-277: the
    corrected rule is NARROWER in what it names and WIDER in what it catches.** The fourth
    instance was the dispatch lead's — *"announce before writing"* (salient act) corrected
    to *"quote the literal bytes to a reader who will check them"* (sufficient condition).
    A correction that is wider in what it NAMES is usually just a bigger net, not a better
    rule. **Each of the four was written by someone looking straight at the failure**, so
    proximity to the incident is no protection at all.
- **As a receiver: treat a `task_assignment` body as a RELAY, never as a witness.** Its
  timestamp attests when it was SENT, never when its content was true. Check the story
  file before acting — `.claude/rules/dispatch-pattern.md`'s "the durable artifact wins"
  applies to structured payloads exactly as it does to prose, and the JSON shape is what
  makes it feel exempt.
- **Prefer prose to the task list for anything spec-shaped.** Statuses and ownership are
  fine; findings, gaps and "not yet landed" claims rot in place and get rebroadcast.
- **Author side, from the reviewer who wrote that description: durable state you write is
  a state claim, and it needs a measured-at timestamp MORE than a message does — because
  it gets re-emitted by someone else long after you are gone.** The description was
  written deliberately as a second durable location so the finding would outlive its
  author. Had it read *"unlanded as measured 04:11:54"* rather than *"NOT yet landed"*,
  my rebroadcast would have been self-defusing on sight. This is the same rule as
  `.claude/rules/tool-output-integrity.md`'s handoff-artifact clause, arriving through a
  channel that does not look like a handoff. **Applies to anything I write to outlive me
  — story Notes, provenance marks, memory files: date the measurement, not just the
  claim.** One defect, two authors: a stale claim and a mechanism that rebroadcasts it.

Related: [[testing-gotchas]] on never trusting a channel's success receipt. A `SendMessage`
returning `success: true` with a msg_id is not evidence of delivery — in this same epic,
four acknowledged sends reached an empty inbox while two others arrived batched an hour
late, so both false-negative and false-positive delivery reads occurred in one session.

## Stale `.pyc` outlives its source, even mid-dispatch

Deleting `foo.py` does not remove `__pycache__/foo.cpython-*.pyc`, and any later
`pytest` run leaves more bytecode behind. A directory holding **only** `__pycache__`
and no `.py` is untracked (`__pycache__/` is gitignored), so it exists in the operator's
main checkout but **not** in the epic worktree, and no commit can delete it.

Import semantics of such a directory (verified E-256-03):
- `import pkg` **succeeds** — an implicit namespace package resolves on the directory alone.
- `import pkg.submodule` **fails** — `__pycache__` bytecode is not importable without source.

So they are inert, but a bare package name still resolves. Never report "removed the
ghost directories" as a satisfied AC: it produces no diff, CR cannot verify it, and a
`rm` in the main checkout violates worktree isolation.
