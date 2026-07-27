# IDEA-209: `_parse_ngb` lowercases the JSON path but not the pre-parsed-list path

## Status
`CANDIDATE`

## Summary

`_parse_ngb` (`src/reports/starter_prediction.py`) accepts either a JSON-encoded string or an already-parsed list, and **normalizes case on only one of them**. Confirmed by reading the function, not relayed:

- JSON string path: `return [str(v).lower() for v in parsed]` — lowercased.
- Pre-parsed list path: `return ngb` — returned as-is, no lowering.

So `'["AMERICAN_LEGION"]'` resolves `legion` while `["AMERICAN_LEGION"]` resolves `unknown`. The same value, in the two shapes the function exists to accept, gives different answers.

A third path is quieter: a bare non-JSON string (e.g. `"usssa"` rather than `'["usssa"]'`) raises `JSONDecodeError`, is swallowed, and returns `[]` — indistinguishable downstream from "this team declared no governing body."

## Why It Matters

`unknown` is a suppress-or-warn state: the coach is told pitch-count rules cannot be applied. So a casing difference in an upstream caller silently converts a team with a known governing body into one with no pitch guidance — failing toward *less* information rather than a wrong number, which is the milder direction, but for a reason no one would predict from the call site.

The bare-string case is the one to watch: it is silent, and its output is a legitimate value. Nothing distinguishes "parsed to nothing" from "declared nothing."

## Rough Timing

No urgency on its own. **Fold into the next epic touching `detect_league_level` or `_parse_ngb`** — it is a few lines in one function. Do not plan around it.

Worth noting the trigger is real but narrow: the JSON-string shape is what the GC public API returns, so the pre-parsed-list path is exercised mainly by internal callers and tests, which is why this has not bitten.

## Dependencies & Blockers
- [ ] None.

## Open Questions
- Should the bare-string case parse as a single-element list rather than empty? That would be a behaviour change, not just normalization, and it needs a moment's thought about what a caller passing a bare string actually meant.
- Are there other GC enum fields read through a two-shape accessor with the same asymmetry? Nobody has swept for siblings.

## Notes

Out of scope for E-275 by operator ruling (fix-only + tripwire + fixture pack), which named this as one of four adjacent MINORs to capture rather than build.

Originally surfaced by the audit-starter sweep and carried in the E-275 spec seed; **the mechanism above was re-verified against the source during E-275 planning** rather than inherited, because that seed was found to carry five other claims that did not survive checking.

Related: [[IDEA-210]], [[IDEA-201]], [[IDEA-202]] (the other three E-275 MINORs — same function family, captured in the same pass), [[IDEA-207]] (`little_league` dead-ends in the same `ngb` block).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
