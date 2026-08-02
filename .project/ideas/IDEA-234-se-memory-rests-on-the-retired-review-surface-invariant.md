# IDEA-234: software-engineer's memory rests on the review-surface invariant E-280 retired

## Status
`CANDIDATE` — **⚠️ TWO FILES, and naming only the topic file leaves the index asserting the
retired claim. Both are listed below for that reason.**

## Summary

E-280 retired the invariant **"unstaged = the current story's changes"** as the definition of
the per-story review surface, replacing it with a frozen tree: the completion report triggers
`git add -A && git write-tree`, and the reviewer reads a diff between two tree SHAs. Under
that mechanism nothing is left unstaged at review time, so *"unstaged is what you are
reviewing"* is now false.

**`.claude/agent-memory/software-engineer/` rests on that invariant in two places, and E-280
could not fix either** — an agent's memory is reconciled only by its owning agent, and
software-engineer was not on E-280's dispatch team.

**1. `dispatch-git-gotchas.md` — built on it end to end, premise and procedure both.**

> `:12-14` — *"During dispatch, the staging boundary is: **staged (`git diff --cached main`) =
> prior completed stories; unstaged (`git diff`) = the story under review.** Code-reviewer
> reviews the *unstaged* diff."*

Everything downstream inherits it: the `git rm` gotcha at `:16-18` (*"A reviewer looking at
the current story's diff sees no evidence the file..."*), the verification recipe at `:27`
(`git status --porcelain <path>` expecting `" D"` unstaged rather than `"D "` staged), and
the remedy at `:31` (*"the deletion stays unstaged and reviewable"*).

**⚠️ Including its frontmatter `description` at `:3`** — *"git rm stages a deletion, hiding it
from code-reviewer's unstaged `git diff` during dispatch… restore the staging boundary before
reporting."* **That is the text surfaced during recall**, so the retired claim reaches a
reader who never opens the body.

**2. `MEMORY.md:41` — the index row independently RESTATES it rather than pointing at it.**

> *"`git rm` stages the deletion, hiding it from CR's unstaged `git diff` (hid 97 lines in
> E-256-03); new untracked files are invisible to `git diff --stat`; mid-epic the baseline is
> `git show :<file>`, never `HEAD:<file>`…"*

Reconciling the topic file alone would leave this standing. That is the exact failure
`.claude/rules/context-layer-assessment.md`'s eviction rule names — *"the `MEMORY.md` index
AND its topic files, not just the index"* — here in mirror image to E-259's recorded
instance, which ran index-first.

## Why It Matters

**The underlying gotchas are still real; only their stated MECHANISM is stale.** `git rm`
still hides a deletion from a reviewer, untracked files are still invisible to
`git diff --stat`, and both still matter under the freeze. So this is **reconcile, not
strike** — the eviction rule's own instruction. A blanket delete would destroy live guidance
that has already caught a 97-line omission.

The risk is specific and directional: an SE spawned into a future dispatch reads
*"unstaged = the story under review"*, arranges its work to keep changes unstaged, and is
reasoning about a mechanism that no longer exists. A stale premise under still-correct advice
is the hardest kind to notice, because every check asking *"is this gotcha real?"* passes.

## Rough Timing

**Resolution trigger: the next time software-engineer is spawned for any reason.** Not worth
a dedicated spawn — nothing is broken today, and the cost of the stale premise is bounded by
SE reading `implement/SKILL.md`, which is authoritative and now correct. Hand this file to SE
at the start of that spawn and let it reconcile its own directory.

Deliberately **not** an E-280 story: E-280 is closed on this point by design, since
`.claude/agent-memory/**` was out of every story's scope and an agent's own dir is reconciled
only by its owner.

## Dependencies & Blockers
- [ ] **Requires software-engineer.** Nobody else may edit `.claude/agent-memory/software-engineer/`
      — flagged, never edited, per the deletion-side eviction ownership rule.
- [ ] E-280 must be merged, so SE reconciles against the landed `implement/SKILL.md` rather
      than a description of it.

## Open Questions

- **Does `git show :<file>` survive?** The index-vs-`HEAD` baseline advice in the same index
  row is about mid-epic staging. Under the freeze the index holds *everything through the
  current story*, not *everything through the previous one*, so the advice may be right for a
  changed reason — which is this repo's reason-rot shape and worth SE checking rather than
  assuming.
- **Does the frontmatter `description` need rewriting or just the mechanism clause?** SE's
  call; the recall-surface consequence is the reason it is called out separately.

## Notes

Filed at E-280 closure from its TN-15 closure obligation (4). **The obligation as written said
this and code-reviewer's memory both needed ideas "because their agents are NOT on this
dispatch team." That premise held for software-engineer and NOT for code-reviewer**, which was
live on the team as `cr-e280` and therefore reconciles its own directory at the closure
authoring window. Only one idea was filed, not two.

The retired invariant's fuller story, including the population no token sweep reaches, is in
E-280's TN-20 items 58 and 59.

Related: [[IDEA-227]] (lessons stranded where their owning agent cannot see them — same
shape, same remedy of a resolution trigger rather than a re-spawn), [[IDEA-228]].

---
Created: 2026-08-02
Last reviewed: 2026-08-02
Review by: 2026-10-31
