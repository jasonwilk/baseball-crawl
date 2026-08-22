<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; teams by id/role only. -->

# Migration audit 6 (2026-08-22)

**Covers:** chunks 16 (generate-concurrency cap, `4ee9a52`), 17 (orphan-cleanup FK rollback,
`2217092`), 18 (reaper unlink race, `846e9eb`). Audit 5 (`4911891`+`c6af80e`+`12444f4`,
2026-08-16) closed the window at chunk 15.

**Rulings:** the operator approved all recommendations wholesale, 2026-08-22. Every docket
item below records its ruling and where the promotion landed.

**Method:** built from four trainer-verified post-mortems (chunk-16, chunk-17, chunk-18
analyses, plus the runs-instrument spec-session notes); every NUMBER restated below was
recomputed fresh against git/pytest/the tree at draft time (commands in the corrections file).
The one caller-supplied item not independently recomputable here is marked as such.

## Corrections of record

1. **Chunk 18's summary counts are false; the fix itself is correct.** Recomputed:
   - "18 new tests" → **16** (`git show 846e9eb -- tests/test_report_generator.py |
     grep -c '^+    def test_'` → `16`). Said three times, including the approval prompt.
     Cross-check: board baseline 4,564 + 16 = 4,580, the final full-suite count the log itself
     reports.
   - "`TestCleanupOrphanTeams*` (12 passed)" — printed by no run (trainer-verified against the
     transcript). The number is *derivable* (`-k "CleanupOrphanTeams"` collects `12/199` today),
     but the spec's own verification command names two classes and collects `10`; the claim
     attributes a count to a run that never printed it.
   - The `-k` filter attribution is wrong: the spec's filter
     (`Reap or Ready or NoGames or Race or Completion`) collects **29** today
     (`29/199 tests collected`), not the quoted 41; pre-split it would collect 21, not 33. The
     quoted 33/41 are only reachable by adding the 12 `TestCleanupOrphanTeams*` tests
     (21+12=33, 29+12=41) — a second command's output silently summed into the first's claim.
   - "4572 baseline / ratchet satisfied" — 4,572 is POST-fix (4,564 + the first 8 tests), and
     the log's "no captured pre-chunk baseline exists" is false: the board recorded chunk 17
     ending at **4,564**.
2. **The archived reaper-race spec's writer table is stale** — it still declares three
   unguarded writers; the same commit that moved it to `done/` fixed all three. Fresh sweep:
   `grep -rn "UPDATE reports SET" src/` returns **4** hits (was 6 pre-fix), all guarded or N/A.
   Corrected table drafted in the corrections file.
3. **The trainer's mis-aimed BENIGN finding is conceded** *(caller-supplied concession,
   recorded per the audit-6 dispatch; the underlying chunk-17 facts are trainer-verified)*:
   the catchable moment in chunk 17 was the session writing "losing this race is BENIGN" into
   shipped code (true for interleaving A, false for B) — the counterexample rule fired against
   the OLD code, never against the fix's own new absolute.
4. **Jot re-verification at this audit:** "16 not 18" — confirmed; "29 vs 41 collected" —
   confirmed (29 fresh); "6→4 sweep hits, remaining guarded/N-A" — confirmed (4 fresh, table
   in corrections file); chunk-18 suite delta recomputed as 4,564 → 4,580 (+16).

## Scorecard

| chunk | suite delta | review gates run | escapes / record defects |
|---|---|---|---|
| 16 | 4,536 → 4,551 (+15, board) | codex (13 findings), `/code-review`, `/security-review`, mutation harness (13 mutants) | ESCAPE: resurrection path — moved the guarded UPDATE as a unit under a comment restating the false premise; `/security-review` asserted that premise and it was relayed unchallenged; `/code-review` named the exact symptom, ruled document-as-residual. Became chunk 18's subject. RECORD: four false summary headers over honest bodies ("13 mutants every one matching", "four gates 25 findings" over an enumeration summing 21 and a codex 13-not-12, "all 6 fixed" over 5+1 residual, stale "A3 NOT reproducible"). Mutant letters in 16 operator-facing messages; F1–F5 namespace silently rebound to `/code-review` numbers; operator approved a superseded diff after a post-presentation edit. |
| 17 | 4,551 → 4,564 (+13, board) | `/simplify`, codex (unfixed tree, never re-run), `/code-review`, `/security-review` | ESCAPE: the half-fix — scope set entirely by codex's counterexample (interleaving A); NO gate probed direction B; `/security-review` CREDITED the fix as narrowing. "Losing this race is BENIGN" shipped in code, false for B, answer one grep away. RECORD/COMMS: "all four spec-named tests failing by name" stated twice over output reading `9 failed, 2 passed` (compression through the WORD channel); narration 31/46 = 67%. Zero operator corrections; campaign-best positives (below). |
| 18 | 4,564 → 4,580 (+16, recomputed) | codex (`codex-review.sh uncommitted`: 1 P1 + 1 P2, both folded), `/code-review` fork (2, folded), `/security-review` (none), mutation run | Fix verified CORRECT independently (all three writers through the shared guard; sweep 6→4). ESCAPE-of-deliverable: **Ordering 2 never built** — convergence argued in a test docstring citing `TestReaperWhenALateGenerationFinishesFirst`, a class that cannot exercise it. NO RED PHASE at all (first flat skip in the program); writer-sweep gate skipped at review time; archived spec table left stale; reconcile CLI read-write defect found (routing owed); mutation restore via global `str.replace` corrupted an unrelated UPDATE (caught by manual diff); gate RC discarded through a pipe in its own run; false counts (correction 1) reaching the approval prompt; narration 74% AFTER notice; trainer relay's plain rewrite silently dropped; security question re-asked a spec-settled ruling. |

Cross-chunk reads:
- **The compression class is now in its FIFTH consecutive chunk and reached the approval
  prompt itself.** Always in SUMMARY surfaces (headers, wrap-ups, approval prompts); bodies
  stay honest. The audit-5 paste-numbers rule is under-scoped: an aggregate has no single
  output to paste, and chunk 17 showed it escaping through quantifier WORDS, not digits.
- **The centerpiece class, spanning all three chunks:** raised findings got independent
  reproduction every time; CLEARED claims (reconcile "pre-existing", the int-cast safety
  verdict, Ordering-2 "converges anyway", 16's relayed ruled-out premise, 17's "BENIGN") got
  inference, relay, and prose. Two were right by luck; one is the unproven core deliverable;
  two shipped the next chunk's defect.
- Review-stack keep-both: sixth and seventh datasets (16's headless codex P1 in fresh code —
  import above try, permanent slot leak; 18's codex P1 — success-shaped `GenerationResult` on
  the lost-race branch, plus the exact test-gap P2 that let it ship green).

## Docket — rulings (operator, wholesale, 2026-08-22)

**1. The centerpiece rule — "a claim that CLOSES a question needs a pasted tool output".**
Evidence: chunks 16/17/18 pattern above (trainer-verified post-mortems; Ordering-2 docstring
verified this draft at `tests/test_report_generator.py:540-546`).
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — Option B,
`operator-comms.md`. **Landed:** new bullet in `.claude/rules/operator-comms.md` ("A claim
that CLOSES a question needs a pasted tool output…"), citing the three chunk-16–18
near-misses.

**2. Summary-quantifier rule — fifth bite.**
Evidence: correction 1 (fresh recomputation) + 16's four false headers + 17's "all four
failing by name" over `9 failed, 2 passed`.
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — Option C, both
the prose rule and the mechanical step-7 enforcement. **Landed:** aggregates-as-fractions
bullet in `.claude/rules/operator-comms.md` ("11 of 13 first-run; M1 and M6 re-run after
fixes" form), and the step-7 presentation bullet in `.claude/rules/tool-discipline.md`
requiring aggregates stated as fractions at the approval prompt.

**3. RED-first flat skip in chunk 18 — a rule that EXISTS did not fire.**
Evidence: `testing.md` carries RED-first verbatim; chunk 18 implemented before any test
existed (trainer-verified).
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — enforcement at
the presentation gate rather than new CLAUDE.md bytes. **Landed:** the step-7 presentation
bullet in `.claude/rules/tool-discipline.md` requires stating per-test RED status
(behavior-failure vs symbol-absence vs never-shown-failing), so a flat skip is visible at
approval instead of never surfacing.

**4. Mutation technique rule.**
Evidence: chunk 18's restore-by-global-`str.replace` added a bogus
`AND status = 'generating'` to `_ensure_team_row`'s `teams` UPDATE (`teams` has no `status`
column); caught only by a manual re-diff (spec progress log, `846e9eb`).
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — Option A.
**Landed:** new bullet in `.claude/rules/testing.md` mutation protocol: mutate NARROWLY,
verify every restore by `git diff` (EMPTY or exactly the intended state), pasted.

**5. Header-vs-body consistency check at the step-7 Status flip.**
Evidence: all four of 16's false claims were header/summary-vs-body divergences; 18's false
counts rode the approval prompt.
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — always-loading
rule bytes rather than a CLAUDE.md cap trade. **Landed:** new bullet in
`.claude/rules/tool-discipline.md`: before flipping a spec's Status, re-read every summary
sentence against the body it summarizes.

**6. Re-present after post-presentation edits (step 7).**
Evidence: chunk 16 — operator approved a superseded diff (comment-only delta, disclosed in
prose; mechanic wrong). Once-bitten.
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — promoted now
rather than watched, folded into the step-7 presentation mechanics. **Landed:** the step-7
bullet in `.claude/rules/tool-discipline.md`: any staged-tree change after a diff was shown
means the diff is SHOWN AGAIN before approval counts.

**7. Label rules — mutant letters and namespace collisions.**
Evidence: mutant letters in 16 operator-facing messages incl. the handoff; the kickoff's
F1–F5 silently rebound to `/code-review`'s finding numbers mid-chunk. `9cfd942`
(operator-ruled 2026-08-22) already landed plain-gloss and self-contained-question bullets.
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — Option A: treat
as covered by define-or-drop plus the new plain-gloss rule; measure compliance on the next
execution thread before adding more prose. **Landed:** no new text; watch item.

**8. Promote the mode=ro live-DB query rule.**
Evidence: bare `sqlite3 data/app.db` returned silent empties under concurrent WAL writers
(2026-08-10, measured); near-miss repeat in the runs-instrument spec session (2026-08-17).
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — Option A,
`tool-discipline.md` (always loads; the failing form was an ad-hoc session query).
**Landed:** new bullet in `.claude/rules/tool-discipline.md` with the exact
`sqlite3 -readonly "file:data/app.db?mode=ro"` form.

**9. Reaper/reconcile follow-ups — three routings.**
Evidence: all three verified fresh this draft (writer sweep pasted in corrections file;
`src/cli/report.py:262` docstring "Read-only on the database." vs `:297` bare
`sqlite3.connect`; Ordering-2 docstring at `tests/test_report_generator.py:540-546`).
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22):
- (i) Reconcile CLI read-write defect: **fold into the runs-instrument chunk**, which
  already owns `reconcile-scoreboard` surfaces (not a standalone stub, not IDEAS).
- (ii) Ordering-2 test construction: rides with the runs-instrument work; completion is a
  named watch item below.
- (iii) Writer-table staleness in the archived spec: commit as an audit-6 record fix,
  paired with the board correction.

**10. Narration enforcement — prose has now lost four rounds.**
Evidence trail: 82% (chunk 15 baseline) → 24% (contract experiment) → 67% (chunk 17, 31/46)
→ **74% (chunk 18, AFTER explicit mid-chunk notice)**; the trainer relay's plain rewrite was
silently dropped in 18.
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — Option A:
promote the structural line and have the reader count it per chunk. **Landed:** new bullet in
`.claude/rules/operator-comms.md` ("Between two tool calls, send NO text unless it carries a
number the operator has not seen or a decision being made"), citing the 74% relapse.
Comms round-3 measurement is a carried watch item.

**11. Review-scope definition for docs-only staging (the fourth wrong-diff surprise).**
Evidence: 2026-08-17 — `/code-review` defaulted to HEAD~1 when staged work was docs-only,
reviewing an already-committed chunk; caught only by a scope-check before relay.
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — define the scope
in the review rubric, no CLAUDE.md bytes. **Landed:** scope paragraph in
`.project/codex-spec-review.md` Re-Review Protocol: docs-only staged work is reviewed as the
staged files ONLY, and that scope must be stated to the reviewer.

**12. The cleared-danger asymmetry as a codex-review checklist line.**
Evidence: chunk 16 — every RAISED reviewer finding verified first-hand; the one ruled-OUT
premise relayed unchallenged, and it was the false one.
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — Option B:
covered by docket 1's rule (cleared findings get the same pasted-output reproduction as
raised ones); skip the rubric copy. **Landed:** no separate rubric line; carried by the
docket-1 bullet in `operator-comms.md`.

**13. Rubric false-fire on pre-commit Status (recurred every chunk until fixed).**
Evidence: step 7 flips Status BEFORE staging, so "READY … committed" is definitionally false
at review time; codex flags it every round.
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — Option A.
**Landed:** checklist line in `.project/codex-spec-review.md` §6: a pre-commit Status
legitimately reads READY/committed BY DESIGN; flag only a Status false AFTER commit.

**14. Re-round termination rule for the rubric.**
Evidence: the concurrency spec session articulated the non-termination ("logging round N
creates new text, so re-round-every-fold never terminates") and its stopping shape worked.
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — Option A, adopt
as written. **Landed:** Re-Review Protocol paragraph in `.project/codex-spec-review.md`:
verification-narrowing folds ship under an UNREVIEWED-EDITS log note; claim- or
mechanism-adding folds get a scoped re-round; the log note itself never triggers another
round — the terminating rule.

**15. git-mv-strands-edits — second bite, promotion due.**
Evidence: 2026-08-09 first bite; 2026-08-16 second bite by the trainer's own audit commit,
operator-caught.
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — Option A: the
existing `tool-discipline.md` git-mv bullet IS the promotion; close the jot. **Landed:** no
new text.

**16. CLAUDE.md step 9's `--follow` promise.**
Evidence: the board's `done/` preamble already says `-M20%` (fixed `657dc22`); CLAUDE.md
step 9 still promised bare `--follow`, conditional-false on move-plus-heavy-rewrite; stub
`2026-08-17-spec-move-follow-gap.md` held the options.
Recommendation: ACCEPTED as recommended (operator, wholesale, 2026-08-22) — take the fix
into step 9; the bite-two bar is met by chunk 16's 790-line case plus the audit-5 near-miss.
**Landed:** CLAUDE.md step 9 now reads "`git log --follow -M20%` supplies it". The one-byte
cap trade landed as an operator-delegated cap raise: `CLAUDE_CAP` in `.githooks/pre-commit`
raised 12032 → 12160 (audit-5 precedent — a cap raise is an operator ruling recorded by
editing the constant; delegated wholesale with these rulings, 2026-08-22). CLAUDE.md is
12,033 bytes after the edit. The stub closes with this landing.

## Template positives (exemplars named by the post-mortems)

- **Chunk 16:** the three-time seeded PII positive-control ritual; the self-verifying mutant
  harness (clean/backup/restore/verify); chasing M6's divergence differentially and fixing
  the hygiene rather than the expectation; the amendment question box (consequence stated
  plainly BEFORE the ruling); three peer-authority refusals — including REFUSING a trainer
  message claiming an operator ruling until the operator confirmed in-terminal; re-deriving
  the trainer's sweep evidence from primaries and catching a mis-sourced cite AND a latent
  test trap (conn=None default → tests hit the real DB); approval-dies honored under
  temptation; stopping on a shared index; re-measuring a peer's claim and shrinking scope
  4→1. The amendment path end-to-end (ruling → spec amendment → scoped codex round →
  implementation → mutation-proven regression) is the template for mid-chunk scope changes
  (~1h, one extra codex round).
- **Chunk 17:** live PII positive control (gate genuinely fired on an epoch-in-path; fixed
  the CONTENT not the pattern; reconciled 8=8); measured-not-inferred baseline via stash;
  refusing a reviewer's reasoning while accepting its fix WITH the disproof measured and
  written into the comment; the rename trap dodged by procedure; the -M20% stub scoped down
  in passing; zero operator corrections all chunk.
- **Chunk 18:** full spec audit before code (every cited line range reproduced against the
  repo, sweep re-run and matched); honest self-disclosure of the str.replace corruption and
  of the missing BEFORE-instrument run; codex P1 + the paired test-gap P2 both folded with
  re-runs pasted.

## Housekeeping (principle F)

- **All 14 live specs legal**: 6 PARKED (+why), 7 STUB, 1 READY
  (`2026-08-11-runs-as-scoreboard-stat.md`) — verbatim Status lines checked 2026-08-22; no
  sixth vocabulary word.
- **Stub adjudications (this sitting):**
  - `restore-run-observations`: its items ride the rebuild spec.
  - `parser-templates`: queued post-rebuild.
  - reconcile read-write stub: NOT created standalone — folded into the runs-instrument
    chunk per docket 9.i.
  - `2026-08-17-spec-move-follow-gap.md`: closed by docket 16's landing.
- **Board is STALE on chunk 18** — `.project/specs/README.md` NOW and STANDING RESIDUALS
  both still carry the reaper race as `READY` / "No code yet — next session executes from
  this spec", while `846e9eb` landed 2026-08-22 with the spec moved to `done/`. Chunk 18's
  step-9 board update never happened. Correction drafted (corrections file).
- **IDEAS.md**: 2 entries (jersey-variant class; `_TEAM_STAT_EXISTS` index trade), both
  healthy someday-work; the reconcile-CLI routing correctly does NOT land here (ruled
  broken-not-someday, docket 9.i).
- **`done/` discipline**: chunk 18's spec moved in its own commit with Status
  `COMPLETE (this commit) — acceptance: run` ✓; its record defects are the audit's
  corrections, not status violations.
- Git-vs-board reality check (`git log --oneline a7ef590..HEAD`): 29 commits; every landed
  chunk except 18 is reflected on the board; `9cfd942` (comms rules) and `cfb342e`/`d6198a4`
  (spec/routing) are consistent with the march.

## Carried forward / watch

- **Audit 7 fires after chunk 21** (3 more chunks), or earlier on a third compression bite
  post-ruling.
- Comms rule round 3: measure bubble count + legend + plain-gloss compliance (`9cfd942` plus
  this audit's narration bullet) on the next execution thread.
- Presentation-gate after-arm: STILL unmeasured (pre-registered count, next two spec
  sessions) — carried from audit 5.
- Ordering-2 completion: the test that actually exercises the second interleaving, riding
  with the runs-instrument work (docket 9.ii).
- "A reviewer's remedy is a claim": no unmeasured adoption observed in 16–18; keep watching.
- Devcontainer pip (will break when the image floats to pip 26.2).
- Residual one-sided game (rides the API-doc bundle chunk).
- The regenerate still owes its own CLI-vs-CLI concurrency discipline in its own spec
  (standing residual, unchanged by chunks 16–18).
