# IDEA-123: Step 1d runs `generate` before `reconcile-scoreboard` — ratchet trips vs a pre-generate baseline

## Summary
The Step 1d closure runtime smoke runs `bb report generate <public_id>` BEFORE `bb report reconcile-scoreboard` (deliberately — so the ratchet measures the state the smoke just produced). But `bb report generate` can **ingest net-new plays** (it fetches plays/spray in-memory for the report), which shifts the plays-vs-boxscore reconciliation metrics. If those net-new plays move a ratcheted axis (`dropped_pitch_events` / `no_plays_units`) relative to a baseline captured BEFORE the generate, `reconcile-scoreboard`'s one-way ratchet gate can trip on a **legitimate ingestion delta the smoke itself caused** — a false epic-FAIL. Fix: either **capture/refresh the reconcile-scoreboard baseline AFTER the generate step**, or **ensure the smoke's `generate` target is already fully represented in the committed baseline** (so generate ingests nothing net-new), or run reconcile-scoreboard against a target the generate does not mutate.

## Status
`PROMOTED` (2026-07-12) — folded into E-262 (story E-262-06). **⛔ FAILURE MODE NOW MOOT (2026-07-26) — but read the next paragraph before acting on that, because "moot" here does not mean "revert the fix."**

**What went moot and why.** This idea's entire failure mode is a *false-FAIL of the reconcile-scoreboard one-way ratchet gate* — the summary's words: "`reconcile-scoreboard`'s one-way ratchet gate can trip on a legitimate ingestion delta the smoke itself caused." **That gate was retired on 2026-07-26** (the D2 decision, commit `877413e`); the scoreboard is now a pure diagnostic that computes and reports without passing or failing anything. A diagnostic has no verdict to trip, so the generate→reconcile ordering can no longer produce the false epic-FAIL described here, regardless of how many net-new plays a `generate` ingests. Both Open Questions are dissolved with it: Q1 (reorder vs. re-snapshot post-generate) is a choice between two ways to protect a gate that no longer exists, and Q2 (is the fresh-target case rare?) was **already** moot per this idea's own promotion note, which dissolved the grounded-frequency read by making the fixture static.

**What did NOT go moot — three things, so nobody over-reads this.** (1) **The fix already SHIPPED** in E-262-06 and is in production: a terminal static `.smoke-fixture` corpus, generate→reconcile order kept, one operator-owned bootstrap re-snapshot. This idea was never a pending candidate awaiting the retirement; it was closed work. (2) **Whether the static fixture retains independent value now that its ratchet-specific justification is gone is an open question for claude-architect, not something this annotation rules.** A deterministic smoke target plausibly has worth beyond protecting a gate — do not treat "the gate is retired" as an argument to unpin the fixture. (3) The **measurement** survives: CLAUDE.md's Operating Principle still directs running `bb report reconcile-scoreboard` before and after an ingestion change and comparing the readings. Retiring the gate retired the *enforcement*, not the *discipline*.

**Recorded here rather than by flipping the status**, because the status is accurate as it stands — this idea *was* promoted and *was* delivered, and rewriting it to DISCARDED would erase that. See [[IDEA-195]] for the deletion of the now-vestigial gate code this retirement left standing. **Mechanism SETTLED by operator decision (2026-07-12):** the grounded-frequency read is dissolved — root fix is a terminal static `.smoke-fixture` corpus (completed-season GC team page with high play-by-play coverage, same season year), keep generate→reconcile order, one operator-owned bootstrap re-snapshot. Reorder-only just moves the false-fail to the next closure; re-snapshot-every-closure is a recurring burden; the terminal fixture removes the drift at the root regardless of drift frequency. (The open question "is the fresh-target case rare?" is moot — the fixture is static.)

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
