# IDEA-079: Reliably Rich Predicted-Starter & Bullpen Narrative

## Status
`CANDIDATE`

## Summary
Make the LLM-generated "Predicted Starter" and bullpen narrative in scouting reports reliably as rich and specific as the best HEAD output we have seen -- with explicit pitch counts and rest days per arm, event-type detection (USSSA vs NSAA), concrete co-ace framing, and decisive rule-in/rule-out of each pitcher. A side-by-side of the same report (identical deterministic stat inputs) on `prod-stable-2026-05-30` vs current HEAD showed HEAD produced a much richer narrative; we want that richness to be the dependable standard, not a lucky roll.

## Why It Matters
The predicted-starter/bullpen narrative is the highest-value coaching prose in a scouting report -- it is the part a coach reads to decide who they will likely face and how rested those arms are. The richness gap is stark:

- **Terse (prod, undesired):** "This is a committee situation that can't be reliably predicted from the data provided. Two pitchers (Isaacs and Van Horn) have nearly identical starting experience with 8 starts each, and both are rested and available…"
- **Rich (HEAD, desired):** "This appears to be a USSSA (not NSAA) event, and the deterministic model has suppressed its prediction because those pitch rules aren't supported here -- so treat any starter call as a best-guess, not a lock. Brock Isaacs (8 starts, threw 25 pitches two days ago) and Brody Van Horn (8 starts, 33 pitches four days ago) are the two genuine rotation arms and are roughly co-aces; Van Horn is the more rested… Cooper Johnson has zero starts and hasn't pitched since mid-March, so he is not a realistic starter despite being available."

The deterministic inputs (starts, rest, pitch counts) were identical across the two versions -- the facts are stable. What varied was the prose generation. If the richness is reproducible, coaches get consistently actionable pre-game intelligence; if it is just nondeterminism, a coach may get the terse fallback on the day it matters most.

## Rough Timing
Near-term-ish. No hard dependency, but most valuable to lock in before morning-of-game scheduled reports (the roadmap forward feature) become routine -- a scheduled report a coach reads unattended should not degrade to the terse fallback. Trigger to promote: the user wants the richness guaranteed, or a scheduled-reports epic makes narrative reliability a gating concern.

## Dependencies & Blockers
- [ ] None hard. The reports LLM enrichment path (Tier-2 predicted-starter) already exists and was hardened in E-233 (`extract_json_object`, `response_format` baseline).
- [ ] First investigative step (below) must run before scoping any fix.

## Open Questions
- **The central question -- (a) pin vs (b) stabilize:** Did the HEAD richness come from **(a)** a deliberate prompt and/or model change made since the `prod-stable-2026-05-30` tag (in which case the change should be identified, PINNED, and made the reliable standard), OR **(b)** plain LLM run-to-run nondeterminism that happened to produce a great answer this time (in which case we need to *stabilize* prompt/temperature/model so the rich form is the dependable output, not a lucky draw)?
- **First step to answer it:** Diff the starter-narrative prompt and the LLM enrichment module across `prod-stable-2026-05-30..HEAD` (e.g., the reports enrichment prompt and `src/llm/`-area changes). If a substantive prompt/model change exists in that range, the answer leans (a); if not, it leans (b).
- If (a): which exact change drove the richness, and how do we pin it (prompt text, model slug, temperature)?
- If (b): what knobs make the rich form reliable -- lower temperature, a richer/structured prompt that always asks for pitch counts + rest + event-type + per-arm rule-in/out, few-shot exemplar, or a stronger model? How do we verify reliability (relates to IDEA-065 LLM eval harness)?
- Does the event-type detection (USSSA vs NSAA) in the rich output come from real data the model had, or did the model infer/guess it? (Affects whether that line is trustworthy or should be sourced deterministically.)

## Notes
- Prompted by a user-run side-by-side comparison of the same scouting report on `prod-stable-2026-05-30` vs current HEAD (2026-06-16). Structured stat tables were byte-identical; only the LLM narrative differed in richness.
- Related: **IDEA-065** (LLM Starter Prediction Evaluation Harness) -- the natural vehicle for *verifying* narrative reliability once we decide what "rich enough" means. **IDEA-066/E-218** (league/level detection for pitch rules) -- relevant to the USSSA-vs-NSAA event-type line. **E-233** (llm-json-hardening) -- recently touched this enrichment path; its `extract_json_object` + `response_format` work lowers the cost of any prompt/model adjustment here.
- Keep lightweight: this is an idea, not an epic. The deliverable is "decide (a) or (b), then make the rich narrative dependable" -- exact ACs come at promotion time.

---
Created: 2026-06-16
Last reviewed: 2026-06-16
Review by: 2026-09-14 (90 days from created)
