# IDEA-123: Step 1d runs `generate` before `reconcile-scoreboard` — ratchet trips vs a pre-generate baseline

## Summary
The Step 1d closure runtime smoke runs `bb report generate <public_id>` BEFORE `bb report reconcile-scoreboard` (deliberately — so the ratchet measures the state the smoke just produced). But `bb report generate` can **ingest net-new plays** (it fetches plays/spray in-memory for the report), which shifts the plays-vs-boxscore reconciliation metrics. If those net-new plays move a ratcheted axis (`dropped_pitch_events` / `no_plays_units`) relative to a baseline captured BEFORE the generate, `reconcile-scoreboard`'s one-way ratchet gate can trip on a **legitimate ingestion delta the smoke itself caused** — a false epic-FAIL. Fix: either **capture/refresh the reconcile-scoreboard baseline AFTER the generate step**, or **ensure the smoke's `generate` target is already fully represented in the committed baseline** (so generate ingests nothing net-new), or run reconcile-scoreboard against a target the generate does not mutate.

## Status
`PROMOTED` (2026-07-12) — folded into E-262 (story E-262-06). **Mechanism SETTLED by operator decision (2026-07-12):** the grounded-frequency read is dissolved — root fix is a terminal static `.smoke-fixture` corpus (completed-season GC team page with high play-by-play coverage, same season year), keep generate→reconcile order, one operator-owned bootstrap re-snapshot. Reorder-only just moves the false-fail to the next closure; re-snapshot-every-closure is a recurring burden; the terminal fixture removes the drift at the root regardless of drift frequency. (The open question "is the fresh-target case rare?" is moot — the fixture is static.)

## Why It Matters
Step 1d's whole point is a trustworthy closure gate; a gate that can false-FAIL on its own side effect erodes trust and triggers needless remediation churn (or, worse, teaches operators to wave it through). The generate→reconcile ordering was chosen so the ratchet sees fresh state, but it didn't account for generate being a WRITER to the plays tables the scoreboard measures. The two goals (measure fresh state / don't trip on self-caused deltas) need reconciling in the procedure.

## Rough Timing
No urgency — in E-256's live-run the operator interpreted the result. Promote when `implement/SKILL.md`'s Step 1d procedure is next touched, ideally together with [IDEA-122] (same live-run, same section). Overlaps the standing operator practice that the reconcile-scoreboard baseline is operator-owned and re-snapshotted after a legitimate fidelity change.

## Dependencies & Blockers
- [ ] None hard. Interacts with E-257's reconcile-scoreboard baseline ownership model (operator owns every snapshot).

## Open Questions
- Is the cleanest fix to reorder (reconcile-scoreboard BEFORE generate) — losing the "measure what the smoke produced" property — or to accept generate's ingestion into the baseline (re-snapshot post-generate)?
- Does the smoke target `public_id` reliably have all its plays already ingested in a normal closure (making this a rare edge), or does a fresh target routinely ingest net-new plays (making it the modal case)? Needs a grounded read before locking the fix — do not assume rarity.

## Notes
Surfaced during the E-256 Step 1d closure runtime smoke live-run, 2026-07-12. **Domain: claude-architect** (`.claude/skills/implement/SKILL.md` Step 1d procedure), coordinating with the E-257 reconcile-scoreboard baseline-ownership convention. Sibling finding from the same live-run: [IDEA-122].

---
Created: 2026-07-12
Last reviewed: 2026-07-12
Review by: 2026-10-10
