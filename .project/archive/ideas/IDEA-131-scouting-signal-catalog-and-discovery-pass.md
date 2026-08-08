# IDEA-131: Scouting Signal Catalog + Discovery Pass — Deep Scout inputs

## Status
`CANDIDATE`

<!--
Status definitions:
  CANDIDATE  -- Active idea, worth revisiting. Default status for new ideas.
  PROMOTED   -- Became an epic. Record which one in the Notes section.
  DEFERRED   -- Deliberately set aside. Include a reason and a re-review date.
  DISCARDED  -- Decided against. Include a reason so we don't re-propose it.
-->

## Summary
The durable, growable inventory of opponent-intelligence SIGNALS computable from data already in the dev DB (no new crawling), plus the "discovery pass" METHOD that generates new catalog entries. The catalog (`.project/research/scouting-signal-catalog.md`, 21 `SIG-NNN` entries as of 2026-07-13) is the structured spec input the Deep Scout epic (E-263) consumes; the discovery pass is the standing hypothesis-sweep practice that grows it (`hypothesis` → `computed` → `validated-live`). This idea tracks the catalog + method as a first-class artifact so it is reviewed on every epic completion, independent of any single epic that builds a subset of its signals.

## Why It Matters
Until now every scouting signal was surfaced by the operator spotting it by eye — reactive tooling. The catalog institutionalizes that eyeball as a repeatable reference, and the discovery pass institutionalizes it as a repeatable METHOD (form hypotheses, test cheaply, verify attribution before reporting, keep survivors above the sample floor, record honest nulls). E-263 v1 builds the MUST-tier subset; the remaining SHOULD-tier signals and the AUTOMATED (agent-run) discovery pass are the natural v2+ backlog this idea holds. Keeping it as a tracked idea prevents the catalog from silently freezing at whatever E-263 happens to build.

## Rough Timing
- E-263 (Deep Scout v1) consumes the MUST-tier subset now.
- Revisit at E-263 closure: which `SIG-NNN` entries got `validated-live`, which remain `hypothesis`/`computed`, and whether the AUTOMATED discovery pass (a `.claude/skills/` graduation) has earned its keep.
- Promote a v2 epic when: enough SHOULD-tier signals have validated to justify a second wiring pass, OR the operator hits the pain of running the discovery pass by hand often enough to want it agent-run.

## Dependencies & Blockers
- [x] Design record exists (`.project/research/deep-scout-design-2026-07-12.md`)
- [x] Catalog structure + 21 entries exist (`.project/research/scouting-signal-catalog.md`)
- [ ] E-263 (Deep Scout v1) ships — establishes the fact-sheet spine the catalog feeds and moves its MUST entries to `validated-live`
- [ ] Handedness probes (#1 `/player-attributes/{id}/bats`, #2 raw events for non-managed game) land before any handedness-gated signal (SIG bats/throws family) is buildable

## Open Questions
- When does the catalog graduate from `.project/research/` to `docs/` (product reference)? CA's rec: on v1 ship, not before (Simple First — `docs/` implies committed stability). E-263 may make this a closure-time move.
- Does the discovery pass graduate from a documented practice to a codified `.claude/skills/discovery-pass`? Only when an epic makes it an automated agent-run pass — speculative until then.
- Which SHOULD-tier signals (steal-traffic-light extensions, bench matchup advisor, coach-tendency scouting, productive-out rate, lineup prediction) form the v2 wiring slice?

## Notes
- Companion artifacts: `.project/research/deep-scout-design-2026-07-12.md` (narrative/citation surface — §4 idea inventory, §6 fact-sheet architecture, §7 v1 scope, §8x live-validation logs) and `.project/research/scouting-signal-catalog.md` (structured lookup surface — the `SIG-NNN` entries, field schema, Discovery Pass method).
- Ownership convention (per catalog header): content columns = baseball-coach; structure columns = claude-architect.
- Hard cross-cutting rule the catalog encodes: roll up strictly by `player_id`/UUID, NEVER by name (duplicate-name players across teams silently merge otherwise). Same duplicate-identity family as E-261 (cross-perspective dedup).
- Scouting-adjacent but DISTINCT from IDEA-022/084/106/108 — this is the catalog+method meta-artifact, not a single signal.

---
Created: 2026-07-13
Last reviewed: 2026-07-13
Review by: 2026-10-11
