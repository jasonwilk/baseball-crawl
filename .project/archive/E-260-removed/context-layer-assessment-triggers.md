# Removed/rewritten text snapshot — context-layer-assessment.md triggers 7/8 + Cadence

- **Source:** `.claude/rules/context-layer-assessment.md`
- **Story:** E-260-07 (context-layer ratchet + wire triggers 7/8)
- **Date:** 2026-07-11
- **Original line ranges (pre-edit):** 23 (trigger 7), 24 (trigger 8), 59-61 (Cadence, Not Caps)

Trigger 7 is rewritten from a soft prompt into a ratchet pointer (the "review prompt, NOT a hard line-count or KB cap" disclaimer removed). Trigger 8 is GATED (not deleted) — cite the defect + fit the baseline; the Learning-Loop hygiene (Load-Target Classification, Deletion-Side Eviction, Memory Retirement) is kept. The "Cadence, Not Caps" section is reconciled so it no longer contradicts the ratchet.

---

## :23 — trigger 7 (rewritten)

7. **Net context-layer growth offset (counterweight).** Did this epic grow the context layer net-positive (more lines/files added than removed across CLAUDE.md, rules, agents, skills, hooks)? If so, what was compressed, consolidated, or retired to offset it -- or, if nothing, why is the net growth load-bearing? Record the offset (or an explicit "nothing retired, and here is why the growth is load-bearing"). This is a review prompt, NOT a hard line-count or KB cap -- a line budget is density-gameable; the goal is that accretion is a conscious, accounted-for decision rather than the default.

---

## :24 — trigger 8 (gated)

8. **Reusable behavioral lesson surfaced (promote-to-load-target).** Did a reusable behavioral lesson surface this epic that RECURRED (it also appeared in a prior epic) OR GENERALIZES beyond one agent? If yes, promote it to its correct load target NOW per the Learning-Loop Lifecycle below -- do not leave it stranded in a non-auto-loading topic file. This always-firing closure gate REPLACES the old uncountable "cited across 2+ epics" criterion (which had no counter).

---

## :59-61 — Cadence, Not Caps (reconciled with the ratchet)

### Cadence, Not Caps

This is a per-epic review cadence, NOT a hard KB or line-count ceiling. The point is that the loop prunes and re-homes as deliberately as it records.
