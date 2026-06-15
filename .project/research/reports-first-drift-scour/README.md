# Reports-First Drift Scour (held — run AFTER E-236 closes)

**Purpose**: systematically find code, schema, and doc/config artifacts that **stray from the
reports-first tightened direction** — i.e., remnants of the abandoned multi-season / cross-team /
multi-surface vision that survived the 2026-06-12 reframe. The archetype is `season_fallback`: a
feature-level non-goal that was never traced down to its machinery. This scour finds its siblings.

**This is NOT the bug hunt.** The earlier sweep asked "is this reports code buggy / does it lie about
itself?" This one asks "does this artifact *belong* under reports-first, or is it a remnant?" The
yardstick is `docs/ROADMAP.md` §7 (Explicit Non-Goals) + §4 (Cruft Inventory & Verdicts) + §3
(Protected Core), not correctness.

**Dual-modality** (per the proven cross-check pattern): run BOTH
- `scour-workflow.js` (Claude Workflow — find → adversarially-verify → synthesize), and
- `codex-prompt.md` (Codex 5.5-xhigh, run by the operator or via codex script),
then reconcile: overlap = high-confidence remnant; single-source = trace before trusting.

**Where findings go**: NOT a new epic by default. They feed `docs/ROADMAP.md` §4/§7, new IDEA files,
Epic D2 scope, and the next "curate the vision" session.

**Timing**: hold until E-236 (report integrity hardening) closes — it touches the `season_fallback`
area, so running after gives cleaner signal (won't re-flag the just-fixed coach line; can confirm the
deferred-machinery boundary E-236 documents).

**To run the workflow**: `Workflow({scriptPath: ".project/research/reports-first-drift-scour/scour-workflow.js"})`
