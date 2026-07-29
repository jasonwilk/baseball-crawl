# E-279 — planning-END state (READY 2026-07-28)

**Scope of this file: ONLY what the epic file does not already say.** `epics/E-279-closure-machinery/epic.md` is canonical for scope, stories, ACs, technical notes, the review scorecard and the codification seed — **prefer pointing at it over restating it.** Written at planning end; closure entries belong to dispatch and are deliberately absent.

## The one thing that will be re-litigated if unread

**Story 01 runs FIRST, and this is now an EDGE, not prose.** Until Codex caught it, "story 01 first" was a binding constraint stated only in TN-1 while the Stories table and every Dependencies section said `None` — so under the workflow contract the stories were order-free and the constraint bound nobody. Edges 01→02 and 01→03 were added; **story 01 stays `Blocked by: None`** so its "closes even if everything else slips" property survives. **Do not remove those edges as redundant.** The reason it must run first: dispatching this epic necessarily quotes worktree paths beside `git add`, which manufactures a phantom worktree directory until the guard fix lands.

## Facts a successor cannot derive from the epic file

- **The `ACM`→`ACMR` PII-gate fix is a SEPARATE, already-landed commit**, not part of E-279 — subject *"fix: PII pre-commit gate enumerates renamed files (ACM -> ACMR)"*, 2026-07-28. Operator-ruled standalone so a security change would not reach the operator inside a closure-machinery diff. **A dispatched implementer will find `ACMR` at `.githooks/pre-commit:24` and must not "restore" it.** Story 04 AC-9 says so; this is the second copy on purpose.
- **E-271's epic file is UNEDITED under a re-confirmed declination.** Only `E-271-03-disjoint-file-cluster.md` plus an E-271 History entry were authorized (OQ-2). The eight-item residual list lives in E-279 TN-8c and is reachable from E-271's History, which cites it **by story ID rather than path** so it survives archiving. **Do not "finish the job" on E-271 without a fresh authorization.**
- **The planning commit is cited by SUBJECT, not by hash, deliberately:** *"feat(E-279): plan closure machinery -- write-guard wedge fix + archive-rename restructure (READY)"*, 2026-07-29, 15 files. **An earlier draft of this line cited a hash, and the `--amend` that folded this very file rewrote that hash out of existence** — citing the replacement would only re-arm the trap, since any later amend moves it again. A hash under amend is the same class of volatile anchor as a line number, and this epic's own rule says cite a stable one.

## Process facts worth carrying, not repeating

- **Three PM generations ran this epic.** The seed-handoff pattern worked, and the reason it worked is that each seed said *the epic files are authoritative and this note is a relay*. **A good seed is not a correct seed** — pm2's was excellent and still carried one claim (the `epic.md:16` repro compression) that had to be corrected.
- **Message delivery failed repeatedly between agents this session** (CR→PM twice, CA→PM three times, PM→main at least twice). Every one was delay-or-loss, never corruption. **If a teammate seems silent, assume the leg, not the agent** — and verify delivery by the effect in the artifact, never by a success receipt.
- **I made two count errors in my own text and caught both by RE-DERIVING, neither by re-reading**: "38 acceptance criteria" against an actual 36, and an iteration-2 total of 21 against a composition summing to 22. Neither reached a file in a way a sweep would catch, because **a figure that lives only in a message is unswept by construction.** The generalisation is candidate 4 in the epic's codification seed.

## Open at planning end

- **IDEA-232** (`:8-11` skips the doc-PII gate) — filed, CANDIDATE, owner claude-architect. Promote when someone is already editing `.githooks/pre-commit`.
- **Codex iteration 2 was NOT run** — the operator chose READY over a second round at 5/5 accepted with every fix landed.
- **Freshness: re-confirm or demote by 2026-09-26.**
