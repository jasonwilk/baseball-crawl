# E-279-02: Dispatch-log telemetry deletion

## Epic
[E-279: Closure machinery](../E-279-closure-machinery/epic.md)

## Status
`TODO`
<!-- OQ-1 RESOLVED 2026-07-28: operator ruled DELETE (verbatim option "Delete entirely"). AC-1 through AC-4 below are the delete criteria; the former KEEP branch is retired in place. No longer blocked. -->
<!-- OQ-2 (E-271-03 reconciliation) was EXECUTED at planning time on 2026-07-28. It is not part of this story; it was briefly scoped here as an AC-5 and that placement was withdrawn. See epic TN-8(c). -->

## Description
After this story is complete, the dispatch-log telemetry mechanism no longer exists, and neither does any committed claim that it works. Today it writes a file that has never once survived a closure while two committed artifacts assert that it does. The operator ruled DELETE on 2026-07-28, so this story removes the mechanism in the **three repo places** it lives and strikes the claims that outlived it. (Epic TN-13 enumerates **four** places; the fourth, software-engineer's memory, is **E-279-05**, not this story.)

## Context
Two coupled facts, both verified. The TSV has never been committed for any epic, and the root cause is not the hook: `.git/info/exclude:19` contains `.dispatch-log/`, excluding the whole directory, so `git add -A` never stages it. Meanwhile `.gitignore:58` ignores only `sends.count` while the comment above it at line 57 states the TSV "stays TRACKED so it rides the closure patch", and the hook header repeats the claim. **A committed claim was falsified by an uncommitted, per-clone override that no repo grep and no code review can see.**

The disposition was the operator's call (epic OQ-1), not claude-architect's and not PM's, because E-260 built this on an explicit operator decision and `c990446` shows the operator makes retirement calls on this hook. **Ruled DELETE on 2026-07-28.** The grounds: never readable in nineteen epics, `rounds` has no producer by construction, `sends` blanks under parallel dispatch, so a repaired file would carry one usable column.

**This story does not fix the wedge on its own, and it is not credited with doing so.** Story 01 makes the guard read authoritative state; this story stops anything manufacturing false state. The class closes on the conjunction (epic Success Criteria), and the two stories remain independent by design.

**Single owner: claude-architect.** Two other-owner items were removed from this story on 2026-07-28. The software-engineer memory reconciliation is now **E-279-05** (blocked-by this story) on claude-architect's own objection — `.claude/rules/context-layer-assessment.md` reserves an agent's memory directory to that agent, and dispatch assigns stories, not criteria. The E-271-03 reconciliation was executed at planning time by PM. See the epic's Dispatch Team section for both.

## Acceptance Criteria

- [ ] **AC-1** (mechanism removed, all three repo places): `.claude/hooks/send-message-counter.sh` is deleted; **both** `.claude/settings.json` registrations are removed **per AC-2's enumeration** (AC-2 governs the mechanics; this criterion does not stand alone, because "the registration is removed" is otherwise satisfiable by deleting the whole Bash block); and the whole `.gitignore` stanza at 55-58 is removed. **RED state:** any one of the three left standing — removing the hook while a registration survives leaves the mechanism half-live and the settings entry dangling.
  - **Verification is scoped to LIVE references, deliberately.** No committed file may still DIRECT a reader to invoke, rely on, register, or maintain the script. **Dated historical framing is EXEMPT and MUST NOT be edited.** The classification was resolved during planning so the implementer inherits verdicts rather than making criterion-versus-evidence calls under time pressure: **evidence, leave alone** — `.claude/skills/implement/SKILL.md:646` (the E-278 phantom-finding narrative, and the anchor for "the merge base binds every diff you take during closure"), `.project/research/E-271-e267-audit-findings.md:31` (the P-6 finding row), `.project/ideas/IDEA-230-*` and `IDEA-116-*`, `.project/ideas/README.md`, and everything under `.project/archive/`. **Removed by this AC itself** — `.gitignore:55`. **Out of scope here** — `.claude/agent-memory/software-engineer/dispatch-git-gotchas.md` (E-279-05). **Needs an authored verdict, not preservation** — see AC-3.
  - An unqualified "no committed file references the script by path" would be **impossible to satisfy correctly**: `SKILL.md:646` must not be edited, so the only way to pass it is to damage a live rule's evidence.
- [ ] **AC-2** (the two settings removals are NOT symmetric, and the asymmetry is deeper on the Bash side): **The Bash matcher block (opens `:8`) contains FOUR hook objects** — `pii-check.sh` (:12), `epic-archive-check.sh` (:18), `secret-read-guard.sh` (:24), and `send-message-counter.sh` (:30). **Only the fourth object (lines 28-33) is removed**; the enclosing block and its three siblings survive, and the file remains valid JSON. **The SendMessage matcher block (:36-46) is sole-occupant and is removed in its entirety.** Verify by grep that `pii-check.sh`, `epic-archive-check.sh` and `secret-read-guard.sh` are all still registered on Bash after the change.
  - **RED state, and it is the reason this AC is worded by enumeration rather than by block:** deleting the Bash *block* rather than the one object would silently unregister a PII gate, a credential-access guard, and the unarchived-epic gate. **No test would fail and the story would report complete.** `epic-archive-check.sh` matters doubly here — E-279-03's own design argues the restructure is safe partly *because* that hook still clears under the new sequence, so removing it would quietly falsify this epic's own premise.
- [ ] **AC-3** (no surviving claim): Given the mechanism is gone, when the repository is swept for `.dispatch-log`, `sends.count`, `rounds`, and the "rides the closure patch" assertion, then **every surfaced line gets a WRITTEN VERDICT — "no change needed" included** — and each verdict is one of: removed, annotated as history, or left untouched with its reason. **The written-verdict form is the criterion, NOT an enumeration of sites, and the difference is load-bearing:** a named-site list is satisfied by fixing the named sites and is silent about the ones nobody listed, whereas a per-line verdict is immune to an incomplete list. This wording replaces an earlier "either removed or annotated as history," which **forced a false disposition on a legitimate hit** — see the worked example below.
  - **Worked example of a hit whose correct verdict is "no change needed":** `.claude/agent-memory/product-manager/archived-epics.md:85` reads "the CA+docs codification **rides the closure patch**" inside the E-264 record. That is a true, live statement about closure patches in general and has nothing to do with the dispatch-log TSV. It must be **neither removed nor annotated as history** — both dispositions would damage a correct sentence. The sweep tokens over-match by design (`.claude/rules/doc-sweep.md`); an over-match arrives visibly and must be dispositioned, which is what this criterion requires. **RED state:** a sweep that reports "all hits removed or annotated" with no verdict recorded for a hit it left alone.
  - **A token grep is the starting point and cannot be the whole sweep.** Two of this epic's own residuals (`E-271/epic.md` TN-11 and TN-12) say **"a bash hook"** and carry NONE of the four sweep tokens; they were found by reading, not grepping. Enumerate the *judgements* that rested on the mechanism, not only rephrasings of the claim.
  - The `.gitignore` stanza is the load-bearing case: line 57 asserts the TSV stays tracked and line 55 names the hook by path, so a partial removal leaves a comment pointing at a deleted file. **The "flag, do not edit" path has NO live instance in this epic, and assuming otherwise will misdirect you.** `context-layer-assessment.md` reserves flagging for owners who are NOT on the dispatch team; all three agent-memory owners here ARE on it. `.claude/agent-memory/software-engineer/dispatch-git-gotchas.md` is **E-279-05**. `.claude/agent-memory/product-manager/archived-epics.md:79` is **PM's, reconciled at closure**. And `.claude/agent-memory/claude-architect/epic-codifications.md:64` and `:171` are **claude-architect's own directory — and claude-architect implements this story**, so those edits ride the closure patch. Do not flag your own hits to yourself.
  - **`:64` is the sharpest site and is NOT merely evidence.** It describes the hook in the present tense with `WARN_AT=15` / `DENY_AT=25` and asserts the log *"rides the closure patch"* — the exact false claim this epic retires, already wrong on the thresholds before deletion touches it. It needs an authored verdict, not preservation. `:171` is the E-276-era defect record and is largely evidence; it still needs a written verdict rather than a silent pass.
- [ ] **AC-4** (the un-fixable residue is reported, not implied fixed): The story's completion report states explicitly that `.git/info/exclude:19` still contains `.dispatch-log/` in every existing clone, that no commit can remove it, and that it is a manual per-clone operator item left alone deliberately (epic TN-11 item 3). A completion report that omits this reads as though the deletion were complete when it is not.

**⚰ Branch B — DEAD. The operator ruled DELETE on 2026-07-28, so the KEEP branch is not implemented.** Its former ACs (an existence check before `mkdir -p`, and reconciling the `.gitignore`/header claims to the per-clone reality) are retired here rather than deleted, so a reader who wonders whether the keep-and-repair option was considered can see that it was, and was decided against. **Do not implement them.**

**Two items that used to be ACs here are no longer this story's** (2026-07-28), recorded so a reader does not think they were dropped: the software-engineer memory reconciliation is **E-279-05**, and the E-271-03 reconciliation was executed at planning time (epic TN-8c). Neither is optional; both moved for ownership reasons, not scope reasons.

## Technical Approach
Read epic TN-13 before starting — it carries the four-place deletion scope with the ranges verified first-hand, including a correction to the `.gitignore` range that circulated as 56-58 and is actually 55-58.

For AC-3's sweep, note that a token grep is the starting point and not the whole check (`.claude/rules/doc-sweep.md`). The retired claim has forms carrying none of its tokens — most importantly any *judgement* that rested on the telemetry being available. Enumerate what would have been written differently had the mechanism never existed, not only rephrasings of the claim.

Do not attempt to fix `.git/info/exclude` from a story. It is not in the working tree, has no history, and differs per clone.

## Dependencies
- **Blocked by**: **E-279-01.** OQ-1 is resolved (2026-07-28) and does not block this story; the edge is the epic's binding sequencing constraint (TN-1) — story 01's guard fix must land before any other story runs, because dispatching this epic quotes worktree paths next to `git add` and, until the guard reads authoritative state, doing so wedges every agent on the machine. **Added 2026-07-28 (Codex P1-2); until then this read `None` while TN-1 asserted the ordering in prose.**
- **Blocks**: E-279-05 (software-engineer reconciles its memory against the deleted state, not an interim one).

## Files to Create or Modify
- `.claude/hooks/send-message-counter.sh` (delete)
- `.claude/settings.json` (modify — remove both PreToolUse registrations, ~:30 Bash and ~:41 SendMessage; the removals are not symmetric, see AC-2)
- `.gitignore` (modify — remove the whole 55-58 stanza: three comment lines plus the `sends.count` ignore rule)

## Agent Hint
claude-architect

<!-- Single owner. The SE-memory work is E-279-05; the E-271-03 reconciliation was executed at planning time. See the epic's Dispatch Team section. -->

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Source: `.project/ideas/IDEA-230-...`, defect 2 and its first open question. The idea's durable lesson is the SHAPE rather than this file: **when a claim concerns what git does with a path, `git check-ignore -v` is the check — reading `.gitignore` is not.**

E-271-03 AC-6 asserted this hook stays registered and keeps logging, which the delete ruling falsified. That is already reconciled — PM executed the bounded E-271-03 edit at planning time on 2026-07-28. See epic TN-8(b) and TN-8(c).
