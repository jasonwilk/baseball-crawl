---
name: auditing-a-moving-target
description: Protocol for auditing files under a concurrent writer — snapshot+pin by hash, because `cp` itself races; and verdict-by-identity, which beats re-grepping when bytes are unchanged.
metadata:
  type: feedback
---

When a "frozen" tree is still being written (E-280 planning audit, 2026-08-02: the freeze
order and pm2's writes crossed, files moved across ~8 batches during one audit), do NOT
chase it with repeated greps. Snapshot, pin, and compare by hash.

**Why:** a finding read from a file that moves under you is unreportable — you cannot say
which state it describes. Chasing also costs unbounded turns; I burned several passes
re-reading text that had already been fixed.

**How to apply:**

1. **`cp` to scratchpad, then verify the copy didn't race.** MEASURED: my first snapshot of
   one story caught it mid-write (15576 → 16138 bytes, the `cp` landing between). Loop
   `stat` before-cp / `stat` after-cp and only trust the copy when the mtime is unchanged
   across it. A snapshot you did not verify is not a snapshot — same shape as
   [[reconcile_whole_file_revert_vs_ancillary]]'s "a restore you did not verify".
2. **Record a manifest** (8-char md5 + mtime per file) and state it in the report. A verdict
   that names the bytes it covers survives the tree moving again; one that doesn't, doesn't.
3. **Settle-check by double hash** (`md5sum *.md | md5sum`, sleep, repeat) rather than by
   asking whether the writer is done. The writer's own answer is a relay; the hash is the
   artifact.
4. **VERDICT BY IDENTITY.** When re-assigned to re-check items against a tree that is
   byte-identical to the state you already verdicted, say so and carry the verdicts over.
   Re-running the greps is theater — identical bytes cannot yield different findings, and
   the identity comparison is one command against N. This was the useful half of the E-280
   re-checks; it went into the periodic-refinement checklist seed.
5. **Re-verify findings against LIVE bytes, not the snapshot,** before reporting. The
   snapshot is for reading coherently; the report must describe what is on disk now.
6. **State the coverage boundary explicitly** — which generation you audited full-depth vs.
   verified at finding-level only. Then, when later passes DO cover the rest, go back and
   correct the boundary: in E-280 my pass-1 caveat was copied into a durable TN and left
   standing after passes 2-3 had covered the material, telling future readers the epic was
   less verified than it was. A stale caveat that UNDERSTATES coverage still costs — it buys
   a redundant audit. See [[review_depth_labeling]] for the labeling half.

Companion: [[regenerate_the_population_not_the_pair]] — under a moving target the temptation
to spot-check the named item is strongest, and that is exactly when regenerating the
population pays (two floor gaps in E-280 were found that way, both invisible to a
spot-check).
