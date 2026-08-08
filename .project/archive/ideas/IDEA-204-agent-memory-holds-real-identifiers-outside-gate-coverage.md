# IDEA-204: Committed agent-memory holds real team identifiers, in a tree the doc-PII gate never scans

## Status
`CANDIDATE` — **live exposure in committed material. Surfaced to the operator directly during E-275 planning.**

## Summary

Two findings that compound:

1. **Committed agent-memory carries real, denylisted identifiers across the ecosystem.** Discovered by api-scout against its own directory (~6 verbatim team names in one file) and then **measured** by running the existing gate over the whole tree.
2. **The doc-PII byte-gate is invoked only against `docs/api`**, so `.claude/agent-memory/` has never been covered by it. The exposure is not a gate failure — the gate was never pointed at that tree, which is what let it accumulate unnoticed in committed material.

### Measured scope (2026-07-27, `scripts/check_doc_pii.sh` run over `.claude/agent-memory/`)

- **15 distinct files** carry denylisted identifiers
- **33 matching lines** in total
- spread across **six agents' memory directories**: baseball-coach (4 files), api-scout (4), claude-architect (3), software-engineer (2), product-manager (1), data-engineer (1)

**This is not one agent's lapse in one file. It is a systemic property of how agent memory has been written across the whole ecosystem** — and it includes the directories of the agents who would be asked to fix it.

api-scout's original report described roughly six names in one file. **It understated the scope by an order of magnitude, and that is worth recording as evidence of how the finding was made rather than as an error to correct away**: it was found by one agent looking honestly at its own directory, which is exactly the method that cannot see the other five.

> ⚠️ **CAUTION FOR ANYONE REPRODUCING THIS MEASUREMENT.** The gate prints matching **lines**, so re-running it pulls real identifiers into whoever's context runs it. The counts above were aggregated and the raw output deliberately discarded so the strings do not persist. **Cite the numbers; do not re-run it casually to confirm them.**

**No identifier is reproduced in this file, deliberately** — counts, file paths and agent names only. A capture that quotes what it reports widens the exposure it exists to close.

### The half that is easy to miss: the remediation has no verifying check

`scripts/check_doc_pii.sh docs/api` will never see `.claude/agent-memory/`, so **whoever redacts this has nothing that confirms they finished.** Widening the gate's path argument is arguably the more important half of the fix than the redaction — **a redaction with no verifying gate is a one-time cleanup that silently rots**, and the rot is invisible by construction.

⛔ **NO REDACTION IS AUTHORIZED.** Nobody edits those files; the operator decides. api-scout has confirmed it left its own file untouched rather than racing the decision.

## Why It Matters

Agent-memory is the highest-traffic prose in this repository — it is loaded into context on nearly every interaction, by design. So an identifier there is not merely at rest in a file nobody opens; it is actively read into agent contexts and can be echoed into any subsequent artifact.

The coverage gap is the more general finding and the one worth fixing. `CLAUDE.md` describes the byte-gate as the thing that catches literal real identifiers the pattern scanner cannot detect, and a reader would reasonably assume it protects the trees where prose accumulates. It protects one of them. The pre-commit gate covers `docs/`, `epics/` and `.project/` per the `GATE_TREES` configuration; `.claude/agent-memory/` — the tree with the most prose and the most agent-authored content — sits outside it.

**The two halves need each other.** Cleaning the file without widening the gate leaves the same thing free to recur, in a tree where nine agents write continuously. Widening the gate without cleaning the file makes every future commit fail against existing content.

## Rough Timing

**Operator decision, not an agenda item.** History rewriting is an operator call and the sequencing matters — widening `GATE_TREES` first would block commits until the existing content is clean.

The cheap, safe first step is measurement: run the byte-gate against `.claude/agent-memory/` in report-only mode and find out whether this is one file or a pattern. Nobody has done that, and the answer changes what kind of work this is.

## Dependencies & Blockers
- [ ] Operator decision on whether committed history is in scope or only the working tree.

## Open Questions
- **Is it one file or a pattern?** One agent found this in its own directory by looking. Eight other agent-memory directories have not been checked, and there is no reason to think the one that looked is the only one affected.
- **Sequencing**: clean first then widen, or widen with an allowlist for known-existing content and burn it down? The second lets the gate start protecting new writes immediately, which is where most future exposure comes from.
- **Should the gate cover `.claude/` generally**, or agent-memory specifically? Rules and skills are prose too.
- **Does history need rewriting, or is going-forward coverage enough?** Depends on the operator's threat model for a private repository; not an agent call.
- Would broader coverage have caught this at the time it was written, or was the content added before the gate existed? Affects whether this is a gap or a regression.

## Notes

**Credit where it belongs**: api-scout found and reported this **against its own committed directory**, unprompted, while working on something else. Self-audits that surface one's own exposure are the hard kind, and the finding would not otherwise exist.

Filed rather than fixed because agent-memory is edited only by the owning agent under the own-memory carve-out in `.claude/rules/agent-routing.md`, and because the gate configuration is context-layer work belonging to claude-architect. E-275 could do neither and correctly did not try.

Companion: [[IDEA-203]], the other half of "the doc-PII gate does not do what a reader of the rules would expect" — that one is about what it blocks that it should not, this one about what it never sees. **Evaluate together.**

Domain: claude-architect (gate config) + the owning agent (content).

Related: [[IDEA-203]], [[IDEA-170]] (the gate cannot see `src`), [[IDEA-180]] (gate tree scope and history gap — closest prior art; check whether this is the same finding rediscovered before filing work against both).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
