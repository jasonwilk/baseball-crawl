# E-266-05: Codify the browser-render testing instinct (rule + code-reviewer hook)

## Epic
[E-266: Pitcher Outings Breakdown — Expand-in-Place & Print](epic.md)

## Status
`TODO`

## Description
After this story is complete, the context layer carries the browser-render testing discipline: a new `paths:`-scoped rule `.claude/rules/browser-render-testing.md` that auto-loads for report-surface changes, and a code-reviewer discipline hook. Future template / print-CSS / disclosure changes will require a headless-Chromium render+print check, not just a generated-HTML string assertion — closing the exact gap that let the E-265 defects ship.

## Context
Operator directive: "build the instinct to test with playwright into the context layer" (epic Background). The E-265 defects passed every gate because all gates verified generated-HTML-vs-spec and none rendered a browser (epic Background smoking-gun). claude-architect ruled the 3-layer codification (epic TN-8); layer 3 (the SE-owned pytest mechanism) lands in E-266-04, and this story codifies layers 1 and 2. This is a context-layer story owned by claude-architect. The context-growth ratchet (trigger 7) is operator-pre-authorized (epic TN-8).

## Acceptance Criteria
- [ ] **AC-1**: A new `.claude/rules/browser-render-testing.md` is `paths:`-scoped to glob `src/api/templates/**` + `src/api/static/**` + `src/reports/renderer.py`/`generator.py` (auto-loading for the code-reviewer via the Step-2 rule-glob mechanism), and states the discipline (per epic TN-8, **broadened per the claude-architect directive**): a **design/experience-affecting change to ANY user-facing rendered surface** (reports, admin, auth — layout / print / disclosure / responsive / a11y-visual) requires a headless-Chromium render+print check; a generated-HTML string-presence (or DOM-only) assertion does NOT satisfy it. (`src/api/static/**` is forward-insurance per claude-architect F2 — all report print-CSS is inline in the template today, but this closes the gap if CSS is ever extracted to `src/api/static/`.)
- [ ] **AC-2**: The rule states the discipline at the discipline level and does NOT hard-name the committed test path (it MAY cite `tests/…` illustratively) — per epic TN-8, so the rule has no brittle file dependency.
- [ ] **AC-3**: A code-reviewer discipline hook is added to `.claude/agents/code-reviewer.md`: when a diff makes a **design/experience-affecting change to a rendered surface** (layout / print / disclosure / responsive / a11y-visual), a string-presence (or DOM-only) render test is insufficient — the review MUST DEMAND headless-Chromium render+print evidence. The hook carries a `Catches:` citation to E-265 (the disclosure/print defects that passed every string-level gate and shipped broken). It points at the auto-loading rule, not a test path (epic TN-8).
- [ ] **AC-4**: The additions are consistent with the existing rule/agent-doc conventions (front-matter `paths:` shape, code-reviewer discipline-section idiom) — no malformed rule that fails to auto-load.
- [ ] **AC-5** (scope is design-validation-WIDE — claude-architect directive): the rule states its scope explicitly as design-validation across rendered surfaces — **reports print-CSS is the WORKED EXAMPLE, not the boundary** — and includes (a) a **self-limiting test** the reviewer applies ("would a plausible bug here pass a string/DOM assertion but fail in a real browser?" — if yes, a browser render+print check is required), and (b) the **exclusions**: email templates are OUT (different rendering engine) and `src/api/routes/**` is OUT (backend, not a rendered surface). The rule stays named `browser-render-testing.md` and PATH-SCOPED (front-matter `paths:` glob) — it is NOT promoted to `CLAUDE.md` or a `paths: "**"` rule. No new context-ratchet event: this is within TN-8's pre-authorized growth envelope; the closure context-layer assessment records that the rule shipped design-validation-wide.

## Technical Approach
Author `.claude/rules/browser-render-testing.md` following the existing `paths:`-scoped rule conventions (front-matter glob + discipline body), and add the discipline hook to `.claude/agents/code-reviewer.md`. Reference epic TN-8 for the exact 3-layer framing and the discipline statement. The concrete test mechanism this discipline points at already exists (E-266-04) — cite it illustratively only. Do not add the deferred 4th option (Step-1d print-media extension) — claude-architect ruled it redundant with the pytest mechanism (epic TN-8).

## Dependencies
- **Blocked by**: E-266-04 (the real render+print test mechanism exists to codify/cite)
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/browser-render-testing.md` (new — the paths-scoped discipline rule)
- `.claude/agents/code-reviewer.md` (modify — add the browser-render discipline hook)

## Agent Hint
claude-architect

## Definition of Done
- [ ] `.claude/rules/browser-render-testing.md` exists, is `paths:`-scoped to the AC-1 globs, and auto-loads for code-reviewer (well-formed front-matter, AC-4)
- [ ] The rule states the DESIGN-VALIDATION-WIDE discipline (any user-facing rendered surface; reports print-CSS as the worked example), the reviewer self-limiting test, and the exclusions (email OUT, `routes/**` OUT) (AC-1/AC-5); it does NOT hard-name a committed test path (AC-2)
- [ ] The code-reviewer hook in `.claude/agents/code-reviewer.md` DEMANDS headless-Chromium render+print evidence for a design-affecting rendered-surface change and carries the `Catches:` E-265 citation (AC-3)
- [ ] The rule stays PATH-SCOPED (not promoted to CLAUDE.md or `paths:"**"`); no new ratchet event (within the TN-8 pre-authorized envelope)
- [ ] Code follows project style (see CLAUDE.md); no regressions in existing tests

## Notes
Context-layer story — routes to claude-architect. Trigger-7 context-growth is operator-pre-authorized (epic TN-8); record the operator authorization in the closure context-layer assessment rather than performing an offset.
