# Migration Audit 1 — first three chunks of the single-agent flow

Date: 2026-08-04. Covers chunks landed 2026-08-02 through 2026-08-03.
Cadence: per operator ruling, an audit runs every 3 landed chunks.

## Scorecard

| chunk | commits | session time | operator cost | escaped defects | process violations |
|---|---|---|---|---|---|
| 1. Enabling commits (guard swap + PII specs gate) | fc2bace, cd02916 | ~55 min active | 11 prompts, mostly one-word | 0 | none |
| 2. Envelope pilot (spec → execute → backfill) | 10c32f3, 8c6abde | ~2.4 h active (spec 40 min wall, exec overnight) | 18 prompts | 1 trivial (git add -A swept an unrelated file; self-detected, no functional impact) | exec session ran to 394k context, past the exit rule |
| 3. Doc-mechanism sweep (residual-game investigation) | aac9ee1 | ~10 h wall, unmeasured active | operator-directed throughout | 0 known | **no spec, no review chain, session never cleared, then forked 3× (~500k each)** |

Old-flow baseline for the same class of work (measured, E-279/E-280 archived TNs):
~6-8 active hours per epic, 66% of dispatch time in review ceremony, 47-106
agent sends per story. Value delivered this window: one-sided games 73 → 1,
~2,400 stat lines recovered, a false API mechanism refuted, a forbidden-write
doc instruction caught (verified doc-only, 16/16 404 probe).

Verdict: quality held (1 trivial escape in 5 commits, all self- or gate-caught
pre-push), time roughly halved, operator attention collapsed to short approvals.
The failure concentrated in ONE joint: the session boundary. The handoff was
printed twice and honored zero times; chunk 3 happened because a finished
session kept accepting questions.

## Incidents

1. **Boundary ignored, then forked.** The 394k pilot session ran 10 more hours,
   took a 16-file cross-layer change with no spec and no review chain, and was
   forked into three ~500k sessions. The forks reported the parent's history as
   their own; the operator coordinated "two threads" that were one brain.
2. **Unexplained vocabulary surfaced to the operator** ("tier 1-4"): a session
   relayed a subagent's internal terms in a question without defining them.
   Relay failure — a question to the operator must be self-contained.
3. **git add -A sweep** (second bite; "path-scoped git add" was already a
   learned rule in the retired system): staged an unrelated concurrent edit
   after the diff had been shown.
4. **Scanner blind spots surfaced**: .claude/ is entirely in SKIP_PATHS (6 of
   14 staged files invisible to the commit gate until manually scanned);
   --stdin reads paths, not content (vacuous scan caught only by a positive
   control).

## Lesson routing (hook/test > agreement line > memory > drop)

| lesson | route |
|---|---|
| Chunk needs a visible state machine; sessions must announce their step | AGREEMENT — chunk lifecycle card (added this audit) |
| /clear is the operator's move; handoff must end with it and the exact resume prompt | AGREEMENT — lifecycle step 10 |
| Fork = same brain, never a second worker | AGREEMENT — new item 10 |
| Questions to operator self-contained; subagent terms defined on relay | AGREEMENT — new item 11 |
| Stage by explicit path, re-diff after staging | AGREEMENT — folded into lifecycle step 7 |
| .claude/ SKIP_PATHS blindness → move the count-check into the pre-commit hook | MECHANICAL — follow-up chunk |
| Guard latent bug: CLAUDE_HOME arm not slash-normalized like repo arm | MECHANICAL — 2-line fix chunk |
| Denylist docs still say "names, UUIDs, public_ids"; policy is now person-names only | DOCS — small chunk |
| --stdin vacuous-scan trap | MEMORY — already written by the working session |
| Residual one-sided game (both identifiers present on empty side) | OPEN QUESTION — live API probe, next ingestion chunk |

## Standing next steps

- **Step 1 of the migration is now the unblocker for everything above**: rewrite
  CLAUDE.md to ~6KB of facts with the agreement + lifecycle card embedded, and
  delete the always-on old-workflow rules. Until it lands, fresh sessions load
  the old rules and the operator pastes/points at the agreement by hand.
- Remaining seed-spec chunks (§2 game-ending run, §3 team_players, §4 labeling)
  proceed through the lifecycle card, one spec each.
