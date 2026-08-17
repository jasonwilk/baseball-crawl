<!-- NO REAL NAMES OR IDENTIFIERS — no person's name, ever; teams by id/role only. -->

# Step 9's `git log --follow` promise fails silently on a rewritten spec

**Date**: 2026-08-17 · **Status**: `STUB` — measured, root-caused, one board line is currently
FALSE. Small docs/board chunk; no `src/` impact, so no codex requirement and PII gates alone.
**Source**: found at the generate-concurrency handoff (`4ee9a52`) by running the very command the
board entry recommends. Not inherited — re-run the measurement below, it takes seconds.

## The defect

CLAUDE.md step 9 says a COMPLETE spec moves to `.project/specs/done/` in its commit and that
**"no hash needed, `git log --follow` supplies it"**. That is CONDITIONAL and it fails silently.

`git mv` plus a heavy same-commit rewrite drops the file below git's DEFAULT 50% rename-similarity
threshold, so git records the move as a delete + add and `--follow` cannot cross it. It does not
error — it returns a plausible one-line history, which is the dangerous part.

**Measured 2026-08-17** on `.project/specs/done/2026-08-10-admin-generate-concurrency.md`
(429 → 790 lines in the moving commit, i.e. the file nearly doubled):

- `git log --follow --oneline -- <path>` → **1 commit** (`4ee9a52`, the move itself).
- `git log --follow --oneline -M20% -- <path>` → **3 commits** (`4ee9a52`, `a607ad0` the spec
  pass, `d1f8fe9` the original stub). The history is intact and recoverable; only the default
  threshold hides it.

**Scope is ONE file, and that is the finding — this is a first occurrence, not historical rot.**
Swept all 15 specs in `done/` comparing `--follow` depth against `--follow -M20%` depth: 14 agree,
1 diverges (the one above). Do NOT write a remediation pass over `done/` — there is nothing else
to remediate.

**Why it will recur rather than being a one-off:** an execution chunk folds its review rounds into
the spec's progress log, so more-than-doubling a spec in the commit that moves it is the NORMAL
shape of a handoff, not an unusual one. This chunk went through four review gates; the next
heavily-reviewed chunk hits the same threshold.

## What is actually wrong right now

**Two of the three board-level items are ALREADY FIXED. Only the CLAUDE.md decision remains open,
and that is what this stub exists for.**

1. ~~The `specs/done/` preamble's blanket `--follow` recommendation.~~ **DONE** — fixed by a peer
   session at `657dc22`, which replaced it with `git log --follow -M20%` and cites the
   429 → 790 measurement inline. Verified present, not inherited.
2. ~~The one false per-entry pointer.~~ **DONE in this stub's own commit** — the generate-concurrency
   LANDED entry now names `-M20%` explicitly instead of promising bare `--follow`.
   ⚠ **It was ONE line, not four, and that is the part worth carrying forward.** Four LANDED
   entries carry a `--follow` pointer; each was checked against its own spec by measurement rather
   than by pattern:

   | entry | `--follow` | `-M20%` | verdict |
   |---|---|---|---|
   | `2026-08-10-admin-generate-concurrency.md` | 1 | 3 | **FALSE — fixed** |
   | `2026-08-13-same-listing-dedup-detection.md` | 4 | 4 | true, left alone |
   | `2026-08-10-opponent-roster-dedup-gap.md` | 5 | 5 | true, left alone |
   | `2026-08-10-pii-scanner-hardening.md` | 2 | 2 | true, left alone |

   A find-and-replace would have hedged three correct sentences into noise and destroyed the
   signal. **Any future sweep of these pointers must re-measure, not pattern-match.**
3. **CLAUDE.md step 9's unconditional promise — STILL OPEN, and it is the whole remaining chunk.**
   See the decision below.

## Open decision the operator owes

**Does step 9's wording change, and does this become a rule?** Principle E says promote to a rule
only after it bites TWICE, at the per-3-chunk audit, never mid-flight. **This has bitten ONCE.**
So the defensible options are:

- **(a) Fix the false board line only**, and let the audit decide about CLAUDE.md. Cheapest, and
  it respects the bites-twice bar. The gap stays live for the next handoff.
- **(b) Fix the board line AND add the verification step to step 9** — after moving a spec, run
  `--follow` and confirm it reaches past the moving commit; if not, cite hashes or `-M20%`. This
  is a step-9 wording change and spends CLAUDE.md bytes, so it is a cap trade the operator rules
  on, not a session.
- **(c) Fix the board line and change the CONVENTION instead** — always cite the hash in a LANDED
  entry, dropping the `--follow` promise entirely. Removes the failure mode rather than detecting
  it, at the cost of a hash in every entry.

Recommendation: **(b)**, because the failure is silent and the check is one command — but it is a
CLAUDE.md byte trade and therefore explicitly the operator's call.

⚠ **The landed README fixes do NOT settle this, and the distinction is the reason this stub
survives them.** They correct the board's own advice — where a reader looks AFTER suspecting a
problem. CLAUDE.md step 9 is what a session reads while CREATING one, and it still promises
`--follow` unconditionally. A session that follows step 9 literally will write another false
pointer, and the board note will only help whoever later doubts it. Different surfaces, different
readers, different moments. **Do not close this chunk on the strength of the README edits.**

## Files

- `.project/specs/README.md` — the false pointer on the generate-concurrency LANDED entry.
- `CLAUDE.md` — step 9 only, and ONLY under option (b) or (c). Byte cap is a tripwire: if the
  edit does not fit, bring the trade, do not compress meaning.

## Out of scope

- Any remediation sweep over `.project/specs/done/` — measured, 14 of 15 are fine.
- `git` configuration (a repo-wide `diff.renames` / `merge.renameLimit` setting). Rejected on
  sight: it would fix the reading of history in THIS checkout while leaving every other clone and
  every web view of the repo unchanged, which is worse than a visible convention.
- The scanner rename gap at step 6. Adjacent and also a rename problem, but a different
  instrument and a different failure.

## Verification

Never trust a piped pytest exit code — but note this chunk touches no code, so the full suite is
not the gate; the gates are the two commands below plus the PII scan.

1. **Reproduce before fixing** (positive control for the instrument itself — prove it can show the
   broken state):
   `git log --follow --oneline -- .project/specs/done/2026-08-10-admin-generate-concurrency.md`
   → expect exactly **1** line. Then the same command with `-M20%` → expect **3**.
2. **Re-run the done/ sweep** and confirm the 14/15 split still holds, rather than inheriting it:
   compare `--follow` depth against `--follow -M20%` depth for every file in
   `.project/specs/done/`.
3. After the fix, the board entry's stated recovery command must actually work when pasted.
   A paraphrase is not enough — paste it and read the output.

## Progress log

- **2026-08-17** — Stubbed at the generate-concurrency handoff. Measured, not inherited: 1 of 15
  `done/` specs affected, history recoverable at `-M20%`, no data lost. No writes made to the
  board; the false pointer is left in place deliberately so this chunk fixes it under approval
  rather than a session patching it post-commit (approval dies with its commit).
- **2026-08-17** — Rescoped on discovering a peer session had STAGED a `specs/done/` preamble fix
  in the shared checkout while this stub was being written. Two corrections folded: item 1 was
  already in flight (confirm, do not redo), and the per-entry sweep was narrowed after measuring —
  only 1 of the 4 `--follow` pointers is false, so a pattern edit would have damaged three correct
  sentences.
- **2026-08-17** — Peer bundle landed at `657dc22`. Re-verified rather than inherited: the `done/`
  sweep re-run still reports **1 broken of 15**, the same file; each of the four board pointers
  re-checked against its own spec's measurement; the peer's preamble fix confirmed present in the
  tree. The one false pointer is fixed in THIS stub's commit. **What remains open is exactly one
  thing: the CLAUDE.md step-9 decision**, which is a byte trade and therefore the operator's, not a
  session's. This chunk is now small enough that it may be folded into another docs chunk rather
  than run standalone — the operator decides that too.
- **2026-08-17 — bitten ONCE, deliberately not promoted.** Principle E requires two bites before a
  lesson becomes a rule, ruled at the per-3-chunk audit and never mid-flight. This is bite one, so
  nothing was written into `.claude/rules/`; the lesson sits in agent memory and this stub. If it
  recurs, that is bite two and audit 6 has its evidence.
