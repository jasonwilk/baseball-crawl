# Migration Audit 4 — chunks 10–12, and the pivot back to the app

Date: 2026-08-10. Covers: season-year filter (`a9c6f19`), docs sweep (`437f671`),
PII scanner hardening (`26bf605`). Prior: audits 1–3.

## Scorecard

| chunk | active | prompts | ceiling | escapes |
|---|---|---|---|---|
| 10 season-year filter | ~48 min | 6 | 357k | 0 |
| 11 docs sweep | ~27 min | 2 | 196k | 0 |
| 12 scanner hardening | ~38 min | 4 | 243k | 0 |

Twelve chunks into the new system: **zero escaped defects.** Suite 4471→4474.
Execution sessions are converging on ~30–50 active minutes with 2–6 prompts.
The outlier is SPEC weight: chunk 11's spec cost ~12h/278k for a 27-minute
execution — routed below.

## The experiment ruling (pre-registered criterion, resolved)

Five arms, one frozen index (tree `06d77b0`), nothing fixed until all reported.
8 distinct findings; no arm >5; the highest-severity finding (F1, interaction
class) was missed by enriched-headless. **Typed reviews STAY for all src/
chunks** — as pre-registered, we stop wondering.

The unwelcome result, kept deliberately: **enrichment made the reviewer worse**
(3 findings vs bare's 4; missed F1 while tracking the spec's own concerns).
Feeding a reviewer the author's framing ANCHORS it. Bare-headless
`claude -p "/code-review"` is cheap, session-invocable, and caught F1 — worth
running as an extra early arm; it does not replace the typed review.

## Lesson routing

| lesson | route |
|---|---|
| Author-framing anchors reviewers (2nd instance of one pattern: an inventory narrows the sweep, a spec narrows the reviewer) | tool-discipline line — ADDED this audit |
| Spec weight must scale with chunk risk (chunk 11: 495-line spec, 27-min execution); spec sessions leave at boundaries too | spec-template header line — ADDED this audit (no card bytes) |
| Old-workflow residue: fix-on-touch, never a dedicated sweep chunk again | policy, recorded here; the tail stopped finding new files at chunk 11 |
| Half-picture relays (trainer): enumerate every gate reading the same state before presenting a consequence | trainer memory (2 instances, mine) |
| Wrong-diff trap recurred and was caught + logged both times | watching; instrument-side fix unknown; carry |

## Operator defaults set this audit (veto anytime)

1. **Smoke check stays operator-run** — the cap trade (wiring it into the card)
   is declined for now; zero bytes spent, revisit if it is ever missed in need.
2. **F8 (`epics/` entry vs byte-gate)**: entries stay put; the reviewer's
   reframe (gate all staged paths instead of a tree allowlist, mooting the
   instance) is stubbed for a future gate chunk.
3. **F3/F4/F7 (three pre-existing gate holes)**: PARKED as one batched
   gate-hardening stub. None is urgent on a dormant, solo, unpushed-to-prod
   repo — and they do NOT preempt the accuracy chain.

## The pivot (the audit's real ruling)

The harness queue is EMPTY. Step 4 is gated on ~3 more real chunks by its own
terms. The march from here is app-only: seed §2 (game-ending run — whole games
silently skipped), §3, §4, residual-game probe, org-reachability measurement,
PII docs chunk, then morning-of-game reports. Audit 5 fires after three of
those land. Process changes between now and then require a bite, not an idea.
