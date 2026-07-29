# IDEA-230: The dispatch-log hook can wedge the write guard for every agent, and its output has never once shipped

## Status
`PROMOTED` — to **E-279 (closure machinery)** on 2026-07-28, bundled with [[IDEA-228]]. Defect 1 is story E-279-01 (sequenced FIRST, because dispatching the epic is itself what triggers the wedge). Defect 2 is story E-279-02, **BLOCKED on an operator delete-vs-keep ruling** (E-279 OQ-1) — routed to the operator rather than decided, because E-260 built this mechanism on an explicit operator decision.

**Carried into E-279 rather than retired with this idea:** the `.git/info/exclude:19` residue is **not repo-fixable** — if the operator rules delete, that line survives in every existing clone and no commit removes it, so E-279 must report it as a manual per-clone item rather than imply the deletion was complete.

**Originally: two defects in one mechanism (`.claude/hooks/send-message-counter.sh` + `.dispatch-log/`). Defect 1 is a live session-wide blocker with a proven one-command repro; defect 2 has been silently true since E-260.**

## Defect 1 — a PreToolUse hook creates worktree directories, and `worktree-guard.sh` reads directories as dispatch state

**`send-message-counter.sh` derives the epic worktree path from the COMMAND STRING and then
`mkdir -p`s it** (the Bash branch, `LOG_DIR="$WT/.dispatch-log"; mkdir -p "$LOG_DIR"`). Nothing in it
checks that the worktree exists, or that git knows about it — the header comment states the
command-derived design deliberately, so attribution stays exact with several dispatches live.

**`worktree-guard.sh` detects "dispatch active" by globbing for that exact path**
(`WORKTREE_DIR=$(ls -d /tmp/.worktrees/baseball-crawl-E-* …)`), **not** by `git worktree list`.

**So the telemetry hook can put the write guard into dispatch-active mode with no dispatch running**,
blocking ALL main-checkout Write/Edit for **every agent in the session** — including closure work,
idea capture, and agent-memory writes — until somebody removes a directory that git does not report.

⚠️ **The trigger is the command's TEXT, not its effect.** Proven 2026-07-28 by controlled test: a
bash command whose only content was assigning the string
`cd /tmp/.worktrees/baseball-crawl-E-999 && git add -A` **to a shell variable** — never executing any
git operation — found the directory **already created** by the time the command ran, because
PreToolUse fires first. A fabricated epic number was enough. **Any command that merely mentions a
worktree path near the words `git add` — an audit, a grep, a quoted example in a diagnostic — creates
that path and wedges the guard.**

**Observed for real, not just in the test.** This idea was written into a session that was itself
blocked by it: `/tmp/.worktrees/baseball-crawl-E-278/` existed on disk at 13:16Z containing nothing
but `.dispatch-log/E-278.tsv` (header + one row, `sends` blank, `seq=1` proving a fresh file), twenty
minutes after E-278's closure commit (`b7552a4`, 12:56:27Z) had removed the worktree at Step 9.
`git worktree list` showed main only; Step 12's terminal gate had passed. **Honest attribution: the
most likely creator is claude-architect's own diagnostic command in this session, which contained
exactly the triggering string.** That does not soften the finding — it sharpens it. The agent
investigating the hook wedged the repository by reading about the hook.

**Also note what this does to the Step 12 terminal gate.** The gate reads `git worktree list` and
`git branch --list`, both of which were clean. **A directory recreated after Step 9 is invisible to
every check the closure sequence performs**, and its effect (a global write block) does not surface
until the next agent tries to write.

## Defect 2 — the TSV has never ridden a closure patch, and the committed comment says it does

`.dispatch-log/E-NNN.tsv` **has never been committed for any epic**: absent from `b7552a4`'s tree,
absent from `git log --all -- '.dispatch-log'`, and never added in any branch.

**Root cause is not the hook.** `.git/info/exclude:19` contains `.dispatch-log/` — excluding the whole
directory, so `git add -A` never stages the TSV. Meanwhile the committed `.gitignore` stanza at
**55-58** ignores only `.dispatch-log/sends.count` (the rule itself is line **58**) while its comment
states the TSV *"stays TRACKED so it rides the closure patch"* (line 57), and the hook header repeats
it (*"TRACKED -> rides the closure patch"*).

> ⚰ **Range corrected 2026-07-28 (was `56-58`).** The stanza starts at line **55**, not 56: line 55 is
> `# Dispatch send-counter (transient; see .claude/hooks/send-message-counter.sh).`, which names the
> hook **by path**. Acting on 56-58 would delete the assertion and the ignore rule while leaving line
> 55 standing as a comment pointing at a deleted file — the exact surviving-claim defect this idea is
> about. Found by PM during E-279 planning by reading the file; claude-architect confirmed and noted
> it had relayed the original range without re-deriving it. **This is the idea's own lesson turned on
> the idea: a claim you relay is a claim you author.** E-279 TN-13 and story E-279-02 carry the
> corrected range.

⚠️ **The durable lesson is the SHAPE, not this file: a committed claim was falsified by an
uncommitted, per-clone override that no repo grep and no code review can see.** `.git/info/exclude`
is not in the working tree, has no history, and differs per clone. Two artifacts asserted the
behavior; the thing that actually decided it was invisible to both. **When a claim concerns what git
does with a path, `git check-ignore -v` is the check — reading `.gitignore` is not.**

**Consequence:** every dispatch since E-260 (`c16de84`) wrote rows into a worktree file that was never
staged and was then destroyed by Step 9's `git worktree remove --force`. **The telemetry this
mechanism exists to produce has not survived a single closure.**

## ⚠️ Corrected relay — do not re-chase the matcher hypothesis

The report that prompted this idea hypothesized that the hook's matcher requires literal adjacent
`git add`, so a `git -C <worktree> add -A` form never fires and no row is written. **The matcher
property is real** — tested directly, `git -C /tmp/.worktrees/baseball-crawl-E-NNN add -A` does NOT
fire — **but it is not the cause and never has been.** Transcript enumeration shows the actual
staging-boundary form used across every dispatch is `cd <worktree> && git add -A` (193+ occurrences
of the dominant variant), which **does** fire; the only `git -C` occurrences in the transcripts are
this session's own test output. Rows were being written all along. **Recorded so the refuted
hypothesis is not re-investigated.** The matcher gap remains a latent second-order defect: legal,
natural, and silently non-firing if anyone adopts that form.

## Why It Matters

Defect 1 is the severe one and it is not a telemetry problem — **a passive, retired-to-silent
telemetry hook holds a write-blocking capability over the entire repository**, acquired by accident
through a shared filesystem convention rather than by design. `c990446` deliberately stripped this
hook's deny/warn authority the same day; **its ability to wedge every agent's writes survived that
retirement, because that ability lives in a different hook's detection logic.**

Defect 2 is mild in isolation but it is the reason nobody noticed defect 1 for nineteen epics: the
artifact that would have shown `.dispatch-log/` behaving oddly never reached a diff, a review, or the
repository.

## Rough Timing

**Defect 1: promote now, or fix it as a one-line change out of band** — it blocks live sessions and
the repro is one command. **Defect 2: bundle with it**, since the disposition question is shared.

## Dependencies & Blockers
- [ ] None. Both files are claude-architect's (`.claude/hooks/**`, `.gitignore` is shared).

## Open Questions

- **Does anyone consume this telemetry?** The honest answer shapes everything else. E-260 built it for
  dispatch cost accounting; the data has never once been available to read, and nobody has missed it
  in nineteen epics. **"Simple first" points at deleting the TSV mechanism outright** rather than
  repairing a pipeline whose output has no established consumer. If it stays, the `rounds` column
  still has no producer (the hook's own header says so) and `sends` is blank under parallel dispatch —
  so a repaired file would carry one usable column.
- **Which layer should fix defect 1?** Three independent fixes, and they are not equivalent:
  **(i)** the hook writes only when the worktree already exists (narrowest, keeps the telemetry);
  **(ii)** `worktree-guard.sh` detects dispatch via `git worktree list` rather than a directory glob
  (**strongest — it makes the guard read authoritative state instead of a filesystem side effect, and
  closes the whole class rather than this one instance**); **(iii)** delete the TSV mechanism, which
  moots defect 2 as well. (ii) and (iii) are complementary; **(ii) should land regardless**, because
  any future hook or agent that creates a path under `/tmp/.worktrees/` re-opens the same hole.
  ⚠️ Weigh (ii) against fail-closed posture: a directory glob fails closed if git state is unreadable,
  and that conservatism is presumably why it was written that way. The fix must not turn a
  fail-closed guard into a fail-open one.
- **Should Step 9 / Step 12 verify the directory is gone?** Step 12 already asserts `git worktree list`
  is clean, which this defect walks straight past. An `ls /tmp/.worktrees/` check would have caught it —
  but only if it runs *after* everything else, and it would still lose to any later-firing hook.
  **Detection is the weaker answer here; (ii) above is the real one.**

## Notes

Filed 2026-07-28 by claude-architect while refining [[IDEA-228]], from an audit relay whose central
mechanism turned out to be wrong (see the corrected-relay section). **All four checkable claims in the
relay were verified against the repo before use; the hypothesized cause was the only one that failed.**

The stale `/tmp/.worktrees/baseball-crawl-E-278/` directory was removed in-session after inspection
(contents: two lines of headerless telemetry, no data), restoring the end state Step 9 and Step 12
already require.

Related: [[IDEA-228]] (the other closure-machinery defect from the same closure; both are procedures
whose failure is invisible to the terminal gate), [[IDEA-227]] (dispatch lessons stranded where nobody
loads them), [[IDEA-204]] (agent-memory outside automated gate coverage).

---
Created: 2026-07-28
Last reviewed: 2026-07-28
Review by: 2026-10-26
