# IDEA-228: The closure sequence has no window in which archive-rename fallout can be fixed

## Status
`CANDIDATE` — **a sequencing gap in `.claude/skills/implement/SKILL.md`, hit for real at E-278 closure.**

## Summary

**Three conditions in the closure sequence are jointly unsatisfiable, and they only collide
when an archive rename leaves references behind — which is the normal case, not an edge one.**

1. **Sub-step 6's archive rename** moves `epics/E-NNN-slug/` to `.project/archive/E-NNN-slug/`,
   which **breaks every reference to the old path in files OUTSIDE the archive** — agent
   memory, ideas, research notes.
2. Those files are **agent-owned**. The orchestrator must not edit them: its only direct file
   operations are git commands (`.claude/rules/dispatch-pattern.md`).
3. **`.claude/hooks/worktree-guard.sh` blocks the owning agent from the main checkout for as
   long as the epic worktree exists** — and worktree removal is **step 9, AFTER the commit**.

**So the window in which those fixes must land does not exist.** The rename happens in the
main checkout; the owning agent is locked out of the main checkout until after the commit;
and the orchestrator cannot make the edits on the agent's behalf.

**Editing the worktree copy does not work either** — by sub-step 6 the patch has already been
applied to main, the worktree is clean, and it still holds the pre-rename layout. Any edit
there is orphaned, because there is no second patch coming to carry it across.

## ⚠️ Why this goes unnoticed

**The Step 12 terminal gate passes cleanly either way. Nothing in it checks for outbound
references to the renamed path.** At E-278 it was caught only because code-reviewer suggested
looking for exactly this class at the approval gate — a judgement call, not a gate. Absent
that suggestion, the epic would have committed with three dead pointers, one of them in a file
whose own next sentence reads *"it is a frozen record to cite and never edit"* — **an
instruction that is correct while its address is dead.**

## What worked at E-278, and the two alternatives that are worse

**The workaround that worked** (operator-visible, ~one turn): **remove the epic worktree
early, keeping BOTH the branch and the generated patch file** — `git worktree remove` at
sub-step 6 rather than step 9, with `git branch -D` still deferred to after the commit. The
guard drops to mode 2, the owning agent fixes its own files in main, then the orchestrator
re-stages once. **The revert path is unaffected**: it is `git apply -R --3way` in the main
checkout, which never needed the worktree, and the retained branch plus patch file hold it
doubly.

**Two alternatives, both rated worse at the time and recorded so they are not re-proposed:**
- **Defer to a follow-up commit** — ships a known-dead pointer, and the epic's own closure
  diff is the artifact the operator approves. A defect knowingly shipped past an approval gate
  is worse than one caught before it.
- **Route the edits to a freshly spawned agent** — adds a spawn at the commit boundary for
  three one-line edits, which is exactly the late scope growth that goes wrong.

## Why It Matters

The fallout is small and the failure mode is not: a broken pointer in agent memory is followed
by an agent that has no reason to doubt it, finds nothing, and re-derives what the pointer was
put there to preserve. That is the same class as [[IDEA-224]]/[[IDEA-225]]/[[IDEA-226]] —
claims stranded in files nobody re-reads — arriving by a different route.

It also has a **structural** quality the others lack: those three are content that *went* stale,
while this one is **created by the closure procedure itself, every time, by design.** A rename
that is otherwise correct manufactures the defect.

## Rough Timing

**Promote when claude-architect is next spawned for any reason.** Same disposition as
[[IDEA-224]] through [[IDEA-227]]. Deliberately not urgent: the workaround is known, cheap and
now recorded, so the cost of the gap is one flagged turn per closure rather than a defect —
**provided somebody looks.** That proviso is the part worth fixing.

## Dependencies & Blockers
- [ ] **Requires claude-architect** — the target is `.claude/skills/implement/SKILL.md` and
      possibly `.claude/rules/dispatch-pattern.md`; PM can write neither.

## Open Questions

- **Sequence change, or a gate?** Two shapes. **(a)** Move worktree removal before the archive
  rename, keeping branch deletion after the commit — cheap, and it is what worked. **(b)** Add
  an outbound-reference check to the closure gate — `grep -rn "epics/E-NNN-" ` outside the
  archive after the rename, with any hit routed to its owning agent. **(b) is the one that
  survives someone not thinking to look**, which is the actual failure. They are not exclusive
  and CA should weigh both.
- **Does anything else break on the rename besides path strings?** E-278 only checked the
  literal old path. **A reference that names the epic without spelling the path would not have
  been found** — the same non-token blind spot `.claude/rules/doc-sweep.md` step 2 exists for.

---

# Operator candidate design — 2026-07-28 (verbatim)

> We could restructure closure so the archive rename happens in the epic worktree before patch
> generation, not in the main checkout after apply. Add a mandatory literal old-path sweep for
> `epics/E-NNN-slug/` outside the archived epic immediately after the worktree-local rename, and
> require that sweep to be clean before the patch is generated. Keep all fallout fixes in the
> worktree so they ride the closure patch. Explicitly classify archive-path/citation repoints in
> `.claude/agent-memory/**` as structure-only edits that claude-architect may perform across any
> agent directory; do not use this change to rewrite stale claims/content outside the owning agent.
> Remove the separate main-side archive rename step, and simplify red-suite / abort rollback so
> reverse-applying the saved patch restores both the content and the path layout. Update
> `.claude/skills/implement/SKILL.md`, `.claude/rules/dispatch-pattern.md`, and any ownership/rule
> text needed in `.claude/rules/context-layer-assessment.md` and `.claude/rules/agent-routing.md`.

The operator flagged their own doubt with it: the proposal adds mandatory prose procedure to a skill
executed by 5-generation models, against the vendor doctrine that prompting is not a control plane
and that new policy should ask "can a hook or script enforce this?" before becoming prose
(`.claude/agent-memory/claude-architect/model-behavior-reference.md`, "Prompting is not a control
plane").

# claude-architect refinement — 2026-07-28

## Verdict: adopt the restructure, and add one script at two call sites. The instrument doubt cuts FOR the proposal, not against it.

**The restructure is net prose REMOVAL.** It deletes four pieces of existing procedure that exist
only to manage a rename living in the wrong tree: sub-step 6 itself; sub-step 5's red-suite warning
(*"Do NOT run the archive-undo `git mv` from sub-step 9 reject path (c)"*); sub-step 9 (c)'s
`git mv`-back line **and** its ordering constraint (*"The `git mv` back MUST precede the
reverse-apply"*); and sub-step 9's half-closed framing. The only NEW mandatory prose is one line
invoking a script and one line stating that a non-zero exit holds the closure. **A change that
removes four conditional rename-ordering rules and adds one script invocation is the
doctrine-compliant direction**, so the over-constraint concern argues for this design rather than
against it.

## Why the sequence change is REQUIRED and detection alone is not sufficient

**The restructure's real product is not a tidier patch — it is a repair window.** Fallout fixes land
in the worktree, where `worktree-guard.sh` already lets the owning agent write unconditionally, and
they ride the patch. That dissolves condition (3) of the deadlock outright.

**Proposal (b) — a check — is worthless until that window exists**, and its stated placement is
wrong twice over. At the Step 12 terminal gate it fires *after the commit*, detecting a defect that
has already shipped past the operator's approval gate — the outcome this idea itself rates as the
worse one. Moved earlier, to the commit boundary, it fires while the worktree still stands and the
owning agent is still locked out of main: **it would detect the deadlock rather than resolve it.**
So (b) is not an alternative to the restructure; it is the second half of it, relocated. **Order
matters: the restructure must land first, or the gate is a dead end.**

**Proposal (a) is superseded — do not re-propose it.** Early worktree removal fixes the same
deadlock but forfeits the remediation path: both remediation loops (red suite at sub-step 5,
epic-FAIL at 5b) re-run the closure sequence *from sub-step 3, in the worktree*. It worked at E-278
only because no remediation round fired. It trades a guaranteed capability for a situational one.

## Mechanics, checked against the sequence — three residuals a planning team must handle

- **The patch.** `git diff --binary --cached $(git merge-base …)` after a worktree `git mv` emits
  either rename headers (`diff.renames` defaults on) or delete+add if similarity drops below
  threshold — plausible here, since `epic.md` is rewritten during the epic. **The design must not
  depend on which**: `git apply --3way` and `git apply -R --3way` handle both. Do not build any
  check on `rename from` appearing in the patch.
- **Rollback genuinely simplifies** — the operator's claim holds. Both paths collapse to
  `git reset HEAD` + `git apply -R --3way`, one command, no ordering constraint, restoring content
  and layout together.
- **`epic-archive-check.sh` still clears.** It is a PreToolUse hook scanning `$CLAUDE_PROJECT_DIR/epics`
  at `git commit` time; under the restructure main loses `epics/E-NNN-slug/` at sub-step 4 (patch
  apply) instead of sub-step 6 — *earlier*, so sub-step 6's stated rationale survives unchanged.
- ⚠ **Residual 1 — re-entry collides with the rename.** Both remediation paths say "re-run the
  closure sequence from sub-step 3." A re-run would `git mv` an already-moved directory and fail.
  Give the rename its own guarded sub-step (3a) and define re-entry below it. **This must be
  specified, not left to judgement.**
- ⚠ **Residual 2 — the archived layout goes live in main earlier.** The full-suite gate (5) and the
  runtime smoke (5b) now run against a tree where the epic is already archived. Nothing in either is
  known to read `epics/`, **but that is an assumption to check, not to inherit.**
- ⚠ **Residual 3 — the worktree's own epic files move mid-dispatch.** After the rename, PM editing
  `epic.md` in a remediation round must use the archive path. Keep the rename as the last action
  before `git add -A`, which the operator's proposal already implies.

## Who runs the sweep — a script makes the litmus test resolve cleanly

Running a deterministic script and reading an exit code is the same shape as sub-step 2's clean-tree
preflight: repository state, not content judgement. So the **main session may run it**. It **must
not rule on the hits**: a non-zero exit is a HOLD, and each hit routes to its owner (PM for `epics/`
and `.project/`; claude-architect for `.claude/**`). Adjudication is domain work because every hit
is a criterion-vs-evidence call — an old-path citation may be a pointer to repoint (**criterion**)
or a record of where something was observed (**evidence**, which editing would falsify). That cut is
governed by `.claude/rules/tool-output-integrity.md`, and a sweep that "fixes every stale-looking
path" destroys records.

## The instrument: one script, two call sites

`scripts/check_archive_refs.sh E-NNN` — grep the literal `epics/E-NNN-` outside `.project/archive/`,
non-zero exit on hits.

1. **In-window hold** — new sub-step 3a, after the worktree rename, before `git add -A`. Repair is
   cheap here: fix in the worktree, it rides the patch.
2. **Fail-closed backstop** — `.githooks/pre-commit`, conditioned on the staged diff containing an
   `epics/` → `.project/archive/` rename. **This is the half that survives nobody looking, which is
   this idea's actual complaint** ("provided somebody looks"). Repair from here is expensive and it
   should never fire; that is what a backstop is. Give it an override consistent with the existing
   PII gate's convention — do not invent a new bypass.

**This is the one place the design exceeds the operator's proposal, and it is where their own doubt
points.** Prose saying "run the script" is precisely the instruction a model skips under load; the
pre-commit gate is the difference between a check and a gate. Same script, two call sites, ~15 lines
of hook.

## The agent-memory carve-out is already granted — what is missing is the CEILING

`.claude/rules/agent-routing.md`'s own-memory carve-out reserves an agent's **own** directory to that
agent and states that a story touching a **different** agent's memory "still routes to
claude-architect." **So claude-architect already holds the authority the operator wants to classify.**
Writing a fresh grant would restate existing authority in looser words — and a looser restatement of
an ownership rule is exactly how the ownership erodes.

Add a **bound** instead, as one sentence beside the existing carve-out: in a closure archive-path
repoint, **the only bytes that may change are the path literal**. Rewording, retiring a claim,
updating a verdict, or adjusting a rating remains the owning agent's; **if the repoint cannot be made
without touching more, it is not a repoint** — route it to the owner or capture it as an idea (the
[[IDEA-224]]/[[IDEA-225]]/[[IDEA-226]] disposition). `.claude/rules/context-layer-assessment.md`
needs no change.

## Accepted residual: non-path references stay out of scope

Open question 2 stays open **by design**. A mechanical sweep sees literals; a reference naming the
epic without spelling the path is a `.claude/rules/doc-sweep.md` step-2 semantic problem and cannot
be mechanized. **Do not grow the script toward it.** State the bound in the skill so a clean exit is
never read as "no stranded references."

## Recommendation — 2026-07-28

Smallest-first; R1 and R2 are the pair that closes the defect:

- **R1 — restructure** (required): rename in the worktree at a guarded sub-step, delete main-side
  sub-step 6 and the three rename-ordering passages it forces. Handles residuals 1-3 above.
- **R2 — one script, two call sites** (required): the in-window hold makes repair cheap; the
  pre-commit backstop makes it non-optional.
- **R3 — bound the repoint** (required): one sentence in `agent-routing.md`. A tightening, not a grant.
- **R4 — record the bound**: one sentence in the skill that the gate is literal-only.

**Not recommended:** proposal (a); a new agent-memory grant; growing the sweep toward semantic
references; siting any check at Step 12.

**Files:** `.claude/skills/implement/SKILL.md`, `.claude/rules/agent-routing.md`,
`scripts/check_archive_refs.sh` (new), `.githooks/pre-commit`. `.claude/rules/dispatch-pattern.md`
takes one line in its permitted-orchestration list (run the check script, route the hits) and
nothing else. Roughly one epic of 3-4 stories; the script and the skill restructure are separable.

## Notes

Hit at E-278 closure, 2026-07-28, between the archive rename and the operator approval gate.
Not a mistake by any participant — the orchestrator sequenced correctly, PM owned the files
correctly, and the hook did exactly what it is for. **All three behaved correctly and the
outcome was still a deadlock**, which is the signature of a procedural gap rather than an
error.

Related: [[IDEA-224]], [[IDEA-225]], [[IDEA-226]] (stranded claims, different route);
[[IDEA-227]] (lessons stranded in completion reports, filed the same day).

---
Created: 2026-07-28
Last reviewed: 2026-07-28
Review by: 2026-10-26
