# IDEA-080: Caller-audit-on-signature-extension rule

## Source
Dev validation finding immediately after E-229 closure (2026-05-18). The
scouting report's embedded positioning cards section shipped with empty
field SVGs, empty compass-key SVG, and empty opponent-context body --
even though the bundle's same content rendered correctly. SE remediation
fix is in the same worktree (`fix/E-229-scouting-positioning`).

## Root cause (real-world example)
`_build_positioning_context()` in `src/reports/renderer.py` gained 6 new
kwargs during E-229 (`per_card_svgs`, `compass_key_svg`,
`opponent_context_coverage_line`, `opponent_context_stats`,
`opponent_context_tier_line`, `positioning_coverage_cue`). One caller
(`positioning_bundle.py::generate_positioning_bundle`) was updated to
populate them; the other caller (`generator.py::generate_report` via
the data dict passed into `render_report`) was not. The renderer reads
via `data.get(...)` with empty defaults, so the missing kwargs silently
fell through to empty strings/dicts -- no error, no warning, just blank
rendered output. Caught by user printing the artifact in dev validation
(exactly the TN-1 mandate's purpose).

## Why each pre-dev gate missed it
- **Codex F2 finding** scoped to the bundle diff; the unchanged-but-now-
  incompatible `generate_report()` data dict didn't appear as a finding
  because the renderer was changed, not the caller.
- **CR's F2 audit** enumerated callers of the sibling render functions
  (`render_field_svg`, etc.) to confirm bundle propagation, not callers
  of `_build_positioning_context` itself.
- **Tests** assert `_build_positioning_context` rendering when passed
  kwargs directly; no end-to-end test ran the full
  `generate_report() -> render_report()` pipeline and asserted the
  embedded positioning SVGs survive.

## Proposal
Codify a CR rubric extension (and/or testing rule):

> **Caller audit on shared-signature extension.** When a PR adds or
> renames parameters on a function in `src/` whose existing callers
> currently rely on default values to silently fall through, CR MUST:
> (a) enumerate every caller via grep, (b) verify each caller was
> updated in the same PR to populate the new parameters where
> applicable, and (c) flag any caller that still passes empty/default
> values as a finding (real or intentional -- the author must
> declare).

Likely codification target: extend `.claude/rules/testing.md` with a
companion rule to "Slot-Fill Content Assertions" (same family of
discipline -- both about render-time wiring being verifiable at the
correct level), and add a CR-checklist line in
`.claude/agents/code-reviewer.md`'s Bug Pattern Checklist.

## Acceptance criteria sketch
- New rule section added (location TBD by claude-architect)
- CR rubric checklist line added (or "Caller audit" promoted to its own
  bullet in the existing checklist)
- A prose example points back to this E-229 dev-validation incident as
  the motivating case
- Optional: a small grep-based helper script or skill snippet that
  enumerates callers of a named symbol for use during CR

## Effort
Small (~2-3 file edits to context-layer files). Not urgent -- the rule
codifies a discipline that's already being followed in spirit; this
just makes it explicit and CR-enforceable.

## Status
IDEA
