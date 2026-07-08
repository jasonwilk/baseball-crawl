---
name: feedback-verify-cited-facts-before-approving
description: When AC-verifying a doc/prose truth-correction, verify each cited concrete fact (file/module/function path, id/routing token) against ground truth before approving — prose reading correctly is not enough
metadata:
  type: feedback
---

When verifying a doc or prose "truth-correction" (the whole class of E-255-style sweeps), a claim that READS correct is not the same as a claim that IS correct. Before approving, verify every cited *concrete fact* against ground truth:

1. **Cited file/module/function path** → glob/grep that the path actually exists (and, when the claim is "X was renamed to Y" or "X is the caller," that Y/the caller resolves in `src/`). A correction can introduce a *fresh* wrong path while fixing the old error.
2. **Cited id / routing / schema token** (e.g. `game_stream_id` vs `event_id`, a `team_season` shape) → cross-reference it against the canonical source of truth (here: the R-01 verified-facts artifact / the code), not just the story's local ACs. The same token can be correct in one file and stale in another.

**Why:** learned during E-255 dispatch (2026-07-08), recorded as the epic's trigger-8 behavioral-lesson closure gate. Two real slips: (a) I approved E-255-05 AC-2's "plays pipeline is alive" prose but did NOT glob the cited module paths — the correction had written `src/gamechanger/plays_parser.py` when the real path is `src/gamechanger/parsers/plays_parser.py` (CR caught it, MUST FIX). (b) I approved the coach `scouting-pipeline.md` SUPERSEDED banner in E-255-07 AC-3 (it correctly named the 403 finding + real pipeline) but did not cross-check its boxscore param `game_stream_id` against R-01's `event_id` fact — Codex F5 caught it at integration review.

**How to apply:** in any close/AC-verification of a prose correction, treat each cited path/id/token as a checkable claim and verify it against the filesystem or the R-01/canonical artifact before ruling PASS. This is the same discipline as [[feedback-clean-reread-before-defect]] (re-read + quote literal text) extended to cited-facts, and it is what the per-story-AC + integration-review layered defense is for — the integration review is the backstop, but catch what you can at AC time. Proportional: it is a verification habit, not a new rule (the `tool-output-integrity.md` clean-reread disciplines already cover the spirit).
