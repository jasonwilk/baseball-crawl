<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; teams by id/role only. -->

# Migration audit 5 — 2026-08-16

**Covers:** chunks 13 (plays final-score recovery, `1827a3e`), 14 (opponent-roster dedup,
`9f1f930`+`b126090`), 15 (same-listing detection, `0464f52`..`f60ff13`). Audit 4 (`2dcc8f8`,
2026-08-10) closed the window at chunk 12.

**Method:** every jot on the audit list was re-verified against primary sources (the three
execution/spec transcripts, git, the tree) by a verification subagent, then the load-bearing
claims re-checked by the trainer before ruling. Verified/relayed distinctions were carried
throughout; two jots and one committed board bullet did not survive verification (below).

## Corrections of record — findings that did NOT survive verification

1. **The principle-I "violation" was FALSE.** The chunk-15 session brought the CLAUDE.md cap
   trade as a three-option question at 13:59 on 2026-08-15 and the operator selected "Raise cap
   to 11,392" at 14:00:39 — verified in the raw transcript by the trainer. The accusation was
   published to the board (`537c984`) and drove a redundant "blessing" on 2026-08-16. Cause: an
   auditor scan of typed user text cannot see question-box answers (they arrive as tool_results
   inside user-type records). This is the transcript-auditor trap the chunk-14 jot recorded as a
   near-miss; here it fired fully and was caught only by audit-5 verification. Vacated in
   `4911891`; the trap is now a `tool-discipline.md` bullet (twice-bitten).
2. **The presentation-gate "natural experiment" was overclaimed.** The 5-in-6 pre-gate
   ExitPlanMode rejection rate is real (verified in the §2 spec transcript). The "0-in-2 after,
   rule inserted mid-stream" arm does not exist: `e483124` landed 11 minutes AFTER the session's
   last ExitPlanMode. Downgraded to: strong baseline, no measured effect yet. Watch the next two
   spec sessions with a pre-registered count.
3. Smaller: chunk 14's zero-overlap review count is **9** findings (5+2+2), not 11; the
   same-listing spec was **673** lines at commit, not 674; chunk 14's post-authorization tool
   calls numbered 30 (not 60+) before commit 1, 59 across both.

## Scorecard

| chunk | active | operator prompts | context ceiling | escapes |
|---|---|---|---|---|
| 13 | ~65 min | 4 | 321k | 1 (latent half-pair clobber) |
| 14 | ~106 min | 7 | 439k | 0 code; 1 false quantifier in dialogue+spec (corrected `c73275e`) |
| 15 | ~346 min | ~16 | 564k | 0 code (2 post-approval commits — process, not product) |

- **The zero-escape streak ended at twelve chunks.** Chunk 13 shipped the `_persist_final_score`
  OR-guard clobber past its own full gate stack; codex found it one chunk later only because a
  review happened to include the committed range. Latent until the regenerate; its fix
  (`2026-08-12-plays-final-score-half-pair-clobber.md`) must land first. This is also the
  clinching datapoint for the review-scope ruling.
- **Chunk 15 broke the size trend** (audit-4 band: 30–50 min, 2–6 prompts): 673-line spec →
  5.8h, ~16 prompts, 564k. Spec weight predicted execution weight — opposite of audit 4's
  chunk-11 datapoint. Fed the spec-size ruling (below).
- **"Did you codex review?" fired in two of three chunks** — the operator's most-repeated
  intervention. Fed ruling 4.
- Review stack: five zero-overlap datasets now (audit-4 frozen-diff 8; §2 4-with-1-overlap;
  chunk 14's 9; chunk 15's 16 across four passes). KEEP-BOTH is settled; recorded, closed.
- New positive pattern, template-grade: **a reviewer's remedy is a claim like its finding** —
  four instances in two chunks of a correct finding whose suggested fix was refuted by
  measurement (blanket surname guard, `team_id` signature, name-similarity, schedule-count
  threading). Not promoted (no failure yet — sessions measured every time); watch.

## Rulings (all operator-approved this sitting)

1. **Escalation counter:** the chunk-14 "all 6" false quantifier is NOT the third
   false-claim-in-dialogue — different class (a measured result compressed into one vivid
   example, quantifier welded to it). The compression class had two instances of its own
   ("all 6"; the five-number twin list) = two bites = promoted directly: **numbers quoted to the
   operator are pasted from output, never retyped** (now `operator-comms.md`). The original
   escalation stands at two; pre-registration intact.
2. **Comms register promoted** to always-on `.claude/rules/operator-comms.md` (five bullets:
   lead with the finding; name the operator's decision in their vocabulary; define or drop
   labels; no empty progress bubbles; paste numbers). Evidence: three bites, the measured
   82%-narration baseline, the divergence-question exhibit and its six-line rewrite, and the
   trainer's own same-message reversion (awareness confers no immunity — the fix had to be
   structural). Contract experiment: narration 82%→24% (substance held), volume 4×, legend
   clause ignored — the rule carries what prose alone couldn't.
3. **Approval dies with its commit** (CLAUDE.md step 7): a finding after an approved commit
   produces a fix brought to the operator, never another commit. Root cause was a lifecycle
   vacuum (no rule for post-commit findings), which sessions filled by manufacturing
   authorization — two chunks running. Kickoff-omission hypothesis refined by verification:
   the discriminator is not *named vs unnamed* but **stop-and-ask vs self-executable** — every
   skipped step required stopping; every unnamed-but-held step was self-executable. And a
   stop-and-ask gate holds when the session pre-schedules it to a named moment (the cap trade
   proved it). Trainer-side: a standing kickoff template names every stop-and-ask gate.
4. **Codex review REQUIRED at step 5 for `src/`-touching chunks** (was: on request). Two chunks,
   4 zero-overlap findings each, both times skipped until the operator asked; offering was
   proven insufficient (chunk 15 offered twice and still deferred it out of existence).
5. **Review scope defined** (step 5): a review covers every change since the chunk's base,
   committed or not — name the range, verify the reviewer received it. Covers the twice-bitten
   security-review wrong-diff trap AND the three-reviews-three-diffs shape, AND the escape at
   chunk 13 (found only because a scope accidentally included it).
6. **Step 9 reworded:** name every discovered thing and where it went (stub / IDEAS / vision
   signal / board residual); a residual parked in a spec moving to `done/` must also land on the
   board; "nothing discovered" is a claim to defend. Trigger: "no new stubs created" read as
   complete while a discovery sat homeless, and IDEAS.md was found EMPTY after three audits.
7. **`COMPLETE` names its acceptance state** — `acceptance: run` or `acceptance: owed at
   <chunk>` — in the Status line, rubric-checked. A fixture-proven chunk must be distinguishable
   from an acceptance-proven one. Bare verdict words ("clean") in a Status are a finding; the
   severity breakdown is the claim.
8. **Cap made mechanical.** The false violation was vacated (above); the real residual was that
   no instrument enforced the cap. Now `.githooks/pre-commit` blocks an over-cap staged
   CLAUDE.md (`CLAUDE_CAP=12032`, number operator-delegated; raise = edit the hook in the same
   commit, an operator ruling). Positive control: blocked at cap=10 before its pass was trusted.
   Cap history: 11,264 → 11,392 (op-ruled 08-15) → 11,520 (op-ruled 08-16) → 12,032 (delegated,
   audit-5 batch 2/3 content).
9. **Mutation protocol:** state the expected catching tests before the run; a mismatch in either
   direction is a finding (`testing.md`). Two same-chunk instances of reported-but-not-
   interrogated per-test output.
10. **Spec-size norm re-ruled as a quality bar:** "as short as truth allows, trim rationale
    before executables" replaces "one page" (step 1). Enforcement is the already-ruled
    review-rounds tripwire (`0b2fa43`): fresh blockers at round 3+ = too big, bring the
    split-or-shrink trade.
11. **A review claim covers the reviewed TEXT** (`codex-spec-review.md`): post-final-round edits
    get a re-round or an explicit unreviewed-edits log note. Trigger: a 19-line section authored
    68 minutes after the Status already said "codex-reviewed (7 rounds, clean)".
12. **The four orphaned stubs, routed:** root-team-id namespace collision — CLOSED at this audit
    (both rule sites endpoint-scoped; spec → `done/`); harvest-web-bundle and
    public-organizations-surface — PARKED onto the API-doc corrections chunk; name-year probe —
    routed into that same chunk. The chunk itself is a NEW bundled NEXT entry (one api-scout
    pass, after the regenerate) also carrying the three `event_id` doctrine sites and the
    one-sided-game probe. Also: generate-concurrency — the actual next chunk — gained the NEXT
    entry nothing had given it.

## Housekeeping

All 13 live specs legal; `done/` discipline holding; IDEAS.md received its first entry (the
jersey-variant class, previously routed nowhere). Board falsehoods corrected in `4911891`
(vacated accusation, closed-but-listed rubric residual, stale byte count). Trainer-side actions:
kickoff template written to trainer memory (names every stop-and-ask gate + reader start-ping);
jot list cleared into this file; trainer commit discipline (edit → stage → present → WAIT)
recorded in trainer memory after an operator correction 2026-08-15.

## Carried forward / watch

- Presentation gate: needs a real "after" arm — pre-registered count over the next two spec
  sessions.
- Comms rule round 2: measure the next execution thread against `operator-comms.md` (bubble
  count and legend compliance are the unproven halves).
- "A reviewer's remedy is a claim" — promote only if a session ever adopts one unmeasured.
- The half-pair clobber fix and the concurrency cap both precede the regenerate; the runs
  instrument precedes it for verifiability. The regenerate closes the ingestion campaign per the
  operator's finish-line ruling; features (morning-of-game scheduled reports; exit-meeting
  one-pagers signal) resume behind it.
- Audit 6 fires after chunk 18.
