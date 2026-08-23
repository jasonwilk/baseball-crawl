# Host-side git hooks bypass — verify fix, audit exposure

**Status: STUB**
**Created**: 2026-08-22, from the exit-sheet concept session's commit work.

## What happened

`core.hooksPath` was set to the absolute devcontainer path `/workspaces/baseball-crawl/.githooks`.
On the macOS host that path does not exist, so git ran **no hooks at all** for host-side
commits — no PII pattern scan, no byte-gate, no `[pii-hook]` receipt. Discovered when the
receipt failed to print on a docs commit (the receipt's absence worked exactly as CLAUDE.md
step 8 intends). The three commits that surfaced it were each hand-scanned clean
(`check_doc_pii.sh` PASS + pattern scanner + name grep, positive controls fired).

**Fix applied 2026-08-22, operator-ruled ("both")**: `git config core.hooksPath .githooks`
(relative; resolves against the repo top-level in both environments). Applied outside a chunk
because every day unfixed = more ungated commits.

## Owed by this chunk

1. **Positive control on the fix, host side**: next host commit must print
   `[pii-hook] PII scan passed.` — confirm it did (the first commit after 2026-08-22 on the
   host is the natural specimen).
2. ✅ **Container-side verification — DONE 2026-08-22** by the in-devcontainer session
   (reply preserved at the concept chunk's `container-session-reply.md`, unversioned):
   git 2.53.0 `git hook run pre-commit` resolves and runs `.githooks/pre-commit` under the
   relative path — full receipt chain printed, RC 0 — and the scanner's positive control
   fired (`[PII BLOCKED]`, RC 1) without touching the index.
3. **Exposure audit**: enumerate commits made host-side during the ungated window and give
   each a retroactive PII pass. ⚠ The window may be LONG: per item 4, the absolute value was
   a STALE config entry predating commit `34f2024` (E-038) — not a recent regression — so the
   audit's start bound is whenever this clone's config last got the absolute write, not a
   recent date. Host-side commits are likely rare (most work runs in-container); the audit
   determines how rare. The three 2026-08-22 docs commits are already cleared.
4. ✅ **Root cause — RESOLVED 2026-08-22, no code fix needed**: the only writer is
   `scripts/install-hooks.sh:11`, which ALREADY writes the relative literal
   (`git config core.hooksPath .githooks`) — fixed in `34f2024` "fix(E-038): use relative
   hooksPath for cross-environment portability". A container rebuild re-runs it and would
   NOT regress today's fix. Today's absolute value was stale config from before E-038
   (an old checkout run or manual `git config`), surviving because nothing re-ran the
   installer on the host.
5. Board entry in `.project/specs/README.md` STANDING RESIDUALS — owed when the README is
   free (another session held it modified when this stub was written).
