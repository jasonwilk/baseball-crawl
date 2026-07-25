---
paths:
  - "**"
---

# Tool-Output Integrity

The harness transport layer can drop or corrupt tool output in bursts -- even on zero-IO commands like a bare `echo` -- and recover on retry. This corruption is not always empty: a nonempty result can be wrong. No tool can detect a garbled-but-nonempty read; only an agent applying this discipline can.

## Failure taxonomy

Treat any of these as a tool-output FAILURE, not as truth:

- **Empty** -- a read/command returns nothing for a target you know or expect to be non-empty.
- **Truncated** -- output is cut off (tail missing, a partial edit that did not fully land).
- **Garbled** -- output is nonempty but wrong. Examples: line numbers that disagree with an independent count (e.g., a Read reporting 17-19 lines while `cat -n` shows a clean 1-31 on the same file), a different file's bytes, or a command echoed back instead of executed. First-hand evidence for this mode lives in `.project/research/E-231-harness-repro/harness-output-reliability-report.md` -- including corruption of a bare `echo`, which has no file to change and so cannot be explained away by the differential below. Content that merely disagrees with a LATER read is not yet in this class: run the differential below before you name it.

**Silent-empty from a tool quirk, not from absence:** the environment's `grep` is ugrep, which returns EMPTY (no error) for `grep -rn "a\|b" <path…>` -- recursive BRE alternation over multiple path args. Use `grep -rnE "a|b"` (ERE), or a single pattern / single path. Treat an unexpected empty grep as an **Empty** FAILURE to cross-check (re-run with `-E` or per-file), never as proof of absence -- in E-256-15 this exact quirk returned "no matches" for symbols that were present, and driving a deletion-eviction sweep off it would have shipped a false-clean no-op.

## A read that disagrees has TWO causes -- run the differential before naming one

A read that disagrees with what you remember has two very different causes: **the transport garbled it**, or **the file moved under you** (an accurate read of a state that no longer exists). Their symptoms are evidentially identical -- a second read disagreeing, and a grep for the remembered text returning zero matches, are produced by BOTH, and both are exactly what the response protocol below tells you to gather. Neither discriminates. So name the cause from evidence that does:

1. **A harness note that the file "has been modified on disk since you last read it" -- including an Edit rejected on that ground -- is PRIMARY EVIDENCE that the file moved.** It is the answer, not a symptom to investigate. In the 2026-07-25 incident under "A handoff artifact is a claim with a timestamp" below, it was the one accurate sentence in the whole diagnostic chain, and it was read as a puzzle rather than as the finding.
2. **`stat -c '%y' <file>`** against the time of your read. An mtime later than your read settles it.
3. **Enumerate who else can write this tree** -- a predecessor or concurrent session, a live teammate, an implementer mid-mutation in a dispatch worktree, a background task, a hook. "Nobody else is writing" is an assumption until you have checked it.
4. **grep the other writer's transcript for the text you remember.** `~/.claude/projects/<cwd-slug>/<session-id>.jsonl` plus that session's `<session-id>/subagents/*.jsonl` carry every Write/Edit/Bash payload with timestamps. If your remembered text appears in one, your read was ACCURATE and the diagnosis is settled.

The two causes demand OPPOSITE actions, which is what makes the misfile expensive. "Garbled" says discard what you read. "Moved" says what you read was REAL -- so a defect you saw may genuinely be in the tree, and a later clean read is evidence about a different state, not a refutation of the first.

**Concrete case -- the read was accurate and the file moved (E-267 story 03 round 2; re-adjudicated 2026-07-25 from transcripts).** A PM Read of `src/db/reconcile_at_load.py` returned nonempty, well-formed Python showing precisely the defect the round was hunting: a restored global OR'd flag (`_pop = any(b.populated for b in blocks)`, a `frozenset().union(...)` of the id sets) and a `team_id` accepted by `_prior_line_player_ids` but dropped from its SQL. PM was one step from reporting that the implementer had shipped a cosmetic fix with its verification mutation left in; a second Read disagreed and a grep for those tokens returned no matches, so PM concluded the first read had been garbled, and this file recorded it as the sharpest known garble. **It was not a garble.** SE wrote exactly those lines into the worktree file at 21:35:44Z as a mutation-testing mutant, PM's Read landed at 21:36:02Z and rendered them at lines 694-697, SE restored from its scratchpad backup at 21:36:12Z, and PM's second Read (21:36:20Z) and grep (21:36:28Z) then correctly found nothing. Both reads were accurate; the file was oscillating on a ~30-second cycle under a concurrent writer. The cross-check produced the right ACTION (do not report it) for the wrong REASON -- and had SE not restored, that same reasoning would have dismissed a mutation that was really there. Two things to carry: **a read that hands you exactly the defect you were looking for is a cross-check trigger, not a finding** -- and in a dispatch worktree, an implementer proving a test discriminates IS a writer of the file you are reviewing (`.claude/rules/worktree-isolation.md` records that same practice destroying that same file).

## Response protocol (cross-check, retry, escalate)

When a target known or expected to be non-empty returns empty, truncated, or garbled output:

1. **Treat it as a FAILURE** -- do not act on it or report it as the result. If what you have is a *disagreement* rather than an empty or truncated result, run the differential above first: "the tool failed" is one of two candidate causes, not the default.
2. **Cross-check via an independent channel** -- e.g., `wc -l` / `wc -c` / `sed -n` / `cat -n`, or a second tool (Read vs. Glob).
3. **Retry** to obtain a clean result.
4. **Escalate rather than assert** if a clean result still cannot be obtained.
5. **Read persisted review/tool findings to completion BEFORE characterizing, summarizing, or triaging them.** A preview, a `head`/`tail`, or a truncated view is not the content; a large output's first screen is not its findings. Never characterize findings, ask to triage them, or co-batch a triage decision with the command that produced them until you have read the full persisted output in your own context. (The E-230 fabrication failure was exactly this -- findings characterized before they were read; the ad-hoc main-session triage context is the thin spot.)

When two channels disagree, **the clean read wins** over a flaky empty or garbled result -- but only once the differential has ruled out a moved file. Against a file that is being written, the later read is not more TRUE, only more RECENT, and it refutes nothing about the state the first read saw. A "no files found" Glob is NOT proof of absence under a flaky channel -- confirm absence through a second channel before relying on it.

## Prose you AUTHOR is a claim too

The rules above govern what you READ. The same discipline binds what you WRITE: a comment, docstring, spec citation, or CLAUDE.md sentence asserting how the code behaves is an unverified claim until resolved against the repo. Prose is unexecutable, so a green suite says NOTHING about it -- E-270 shipped six such defects across five shapes (a docstring citing a test name that existed in no file, a comment claiming "both callers" when one did not exist, a spec citation pointing at a path that could never exist, and two consequence claims that were exactly backwards).

Before reporting prose complete:

1. **Enumerate every symbol AND path the prose cites** -- test names, functions, flags, files, headings -- not just the ones in your diff, and resolve each against the repo. Where a reference is missing, establish WHY rather than noting it.
2. **EXECUTE behavioral claims rather than reasoning to them.** "This would raise X" is a hypothesis until you make it raise X. In E-270 the claim "a KEEP->PURGE FK aborts the purge" was true only for a default-action FK; running it showed an `ON DELETE CASCADE` edge raises NOTHING and commits.
3. **Cite a stable anchor, not a line range.** Line numbers rot -- twice in E-270, once to the epic's own text between planning and its final story. Cite by test name, symbol, or heading, and the citation survives.

**A claim you RELAY is a claim you AUTHOR.** The heading says "author", but this defect travels by INHERITANCE: a sentence handed to you in an epic spec, a story, or an upstream doc becomes yours the moment you write it down, and a spec that passed internal review plus a Codex pass is not verification -- it is borrowed authority, which is precisely why it gets restated unchecked. In E-272 one false sentence in a Technical Note ("the season-absent default is the stricter table, so an ambiguous season over-rests") reached a shipped code comment, an idea file's urgency rating, and a rule-file draft before anyone did the arithmetic: it was true for the sub-varsity branch and backwards for the varsity one. Check an inherited safety claim at the point you restate it. **A verdict's stated REASON rots independently of the verdict**, and a correct conclusion immunizes its false premise: any check that asks "was the call right?" passes, so only reopening the cited file catches it. This bites hardest in a RETRACTION, where the relief of having caught an error is what stops the reason being read -- on 2026-07-25 a retraction ("that text is not in the file") was wrong about the file, and its own correction ("the rationale applies to a different constant pair") was wrong again, while the verdict -- do not edit the file -- was right all three times. Once such a claim is retired, sweeping out its residue is its own discipline -- see `.claude/rules/doc-sweep.md`, "Retired Claims Survive in Forms Carrying None of Their Tokens".

**A handoff artifact is a claim with a timestamp.** A handoff note, research file, or kickoff prompt written for another session to consume is mutable until it is committed, and correcting it afterwards does not reach a reader who has already read it or a prompt already handed out. On 2026-07-25 a predecessor session wrote a handoff at 06:21:08Z, generated the successor's kickoff prompt from it 45 seconds later, a successor read the file at 06:23:05Z, and at 06:27:20Z the predecessor struck the handoff's central claim -- announcing that correction in its own thread, where the already-launched successor could not see it. So: when you correct material you have already handed off, reissue BOTH the artifact and any prompt built from it; and when you are seeded FROM such an artifact, check its mtime against your own start before treating it as the state.

**The safety-comment sub-class (where this defect concentrates).** Alarming prose is self-protecting: a claim naming the SCARIER outcome feels right for a safety note and is therefore least likely to be challenged. Sharpest form -- **the tidy general rule at the END of a safety note is where this lands, because that is the sentence that sounds most authoritative and gets checked least.** It is also where over-correction lands: E-270 fixed an understatement into a categorically false rule in that exact position. When you write a closing generalization, check it against the codebase's dominant pattern; if that pattern would violate your rule, the rule is wrong.

## Prohibitions

1. **Never assert or relay file content or a tool outcome you have not seen cleanly in your own context.** Report what you observed, not what you expect.
2. **Never co-batch a relay or report with the same-batch command whose output it reports.** A report must describe output already in context from a prior, completed call -- never expected output and never output produced in the same tool batch as the report.
3. **Never rule on a grep / OR-pattern match -- Read and quote the literal line.** A grep hit proves a line matched *something*; it says NOTHING about which alternative of an OR-pattern matched, and an omitted or truncated matching line (`[Omitted long matching line]`) is not evidence of any particular content -- it just means the line was long. grep finds candidates; only a clean Read of the exact line range confirms the current literal text. Never report a defect, rule a claim stale-or-current, or characterize content from a match alone.
