# Removed text snapshot — context-layer-guard.md numeric targets

- **Source:** `.claude/rules/context-layer-guard.md`
- **Story:** E-260-07 (fold the unenforced numeric targets into the ratchet baseline)
- **Date:** 2026-07-11
- **Original line ranges (pre-edit):** 24-26 (CLAUDE.md Target), 28-30 (MEMORY.md Target)

The `~150` CLAUDE.md / `<150` MEMORY.md numeric targets are removed (they were unenforced and never held — the ratchet is now the enforcement mechanism for the four-subtree size). The qualitative placement guidance and the platform truncation fact are retained; the Placement Framework table is kept.

---

## :24-26 — CLAUDE.md Target (numeric target removed)

## CLAUDE.md Target

**~150 lines.** CLAUDE.md holds genuinely ambient project identity only. Before adding content to CLAUDE.md, ask: "Does every agent need this on every interaction?" If the answer is "only when touching certain files" or "only for certain agents," it belongs in a scoped rule or agent definition instead.

---

## :28-30 — MEMORY.md Target (numeric target removed)

## MEMORY.md Target

**Under 150 lines.** MEMORY.md is an index, not a memory store. Content beyond line 200 is silently truncated by the platform. Extract detailed content to topic files in the same directory and link from MEMORY.md.
