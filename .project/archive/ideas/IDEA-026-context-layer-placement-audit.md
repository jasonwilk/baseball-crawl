# IDEA-026: Context Layer Placement Audit -- Phase 2

## Status
`CANDIDATE`

## Summary
Systematic evaluation of context layer delivery beyond CLAUDE.md: subdirectory intent nodes (CLAUDE.md files in src/ subdirectories), rules directory consolidation, and automated staleness detection. Phase 2 of the placement work started in E-112.

## Why It Matters
E-112 optimizes the top-level context layer (CLAUDE.md, universal rules, agent memory). But two structural gaps remain: (1) agents working in specific src/ subdirectories receive no directory-scoped context (everything comes from the root), and (2) the rules directory has grown to 18 files with no consolidation or staleness enforcement. Addressing these would further improve agent accuracy by delivering relevant context at the right scope level and preventing context rot.

## Rough Timing
After E-112 ships and we have a new ambient baseline to measure from. No urgency -- E-112 delivers the high-value wins. This is the long-tail optimization.

## Dependencies & Blockers
- [ ] E-112 (Context Layer Optimization) must be complete -- establishes the new baseline
- [ ] Sufficient project maturity in src/ modules to justify scoped context (src/gamechanger/ is the most mature candidate)

## Open Questions
- Which src/ subdirectories benefit most from intent nodes? CA suggests src/gamechanger/ as a pilot.
- What threshold justifies consolidating small rule files (e.g., pii-safety 14 lines, crawling 20 lines)?
- Is automated staleness detection worth the hook complexity, or is the manual assessment at epic closure sufficient?
- Should rules consolidation wait until after E-112-05 creates 3 new rules (the directory will be at 20+ files)?

## Notes
Derived from CA's placement audit during E-112 refinement (2026-03-15). Three components:

1. **Subdirectory intent nodes**: Place CLAUDE.md files in src/gamechanger/, src/http/, src/db/, migrations/. These auto-load when agents work in those directories, providing T-shaped context (deep knowledge of the local module, shallow awareness of neighbors). CA recommends src/gamechanger/ as a pilot. Related to IDEA-005 (Directory-Scoped Intent Nodes).

2. **Rules directory consolidation**: 18 rules files, 1,245 lines. Some are tiny (pii-safety 14 lines, crawling 20 lines). Evaluate whether small rules should be consolidated into thematic groups. Low priority.

3. **Automated context staleness detection**: Currently we rely on manual context-layer-assessment at epic closure plus advisory guard rules (`.claude/rules/context-layer-guard.md`, created by E-112-05) that fire when agents edit context-layer files. The recommended escalation path is: manual assessment (have now) → advisory rules (E-112-05) → deterministic hooks (this idea, if advisory proves insufficient). Hook-based enforcement would mechanically check line counts, frontmatter presence, and cross-reference validity. Only pursue if advisory rules show repeated non-compliance.

---
Created: 2026-03-15
Last reviewed: 2026-03-15
Review by: 2026-06-15
