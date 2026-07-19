---
paths:
  - "src/api/templates/**"
  - "src/api/static/**"
  - "src/reports/renderer.py"
  - "src/reports/generator.py"
---

# Browser-Render Testing Discipline

## The Rule

**A design/experience-affecting change to any user-facing rendered surface requires a headless-Chromium render+print check. A generated-HTML string-presence assertion -- or a DOM-only assertion -- does NOT satisfy this.**

"User-facing rendered surface" is every server-rendered HTML surface a person looks at: reports, admin, auth. "Design/experience-affecting" is the change dimension: **layout, print, disclosure (show/hide), responsive, or a11y-visual** behavior. When a change touches any of those on any of those surfaces, the review requires evidence that the surface was rendered in a real browser and inspected -- including its print rendering where print is in play.

This is **design-validation-wide**. It is not a reports-only rule and not a print-CSS-only rule. Reports print-CSS is the **worked example** below, not the boundary.

## Why (the gap this closes)

The E-265 disclosure/print defects shipped broken because **every gate verified generated-HTML-against-spec and none rendered a browser**. A `<details>` block, a print `@media` rule, and a responsive breakpoint all produce correct HTML *strings* while rendering wrong: an expand-in-place control that does not expand, print CSS that clips a table, a disclosure that stays collapsed. String-presence and DOM-shape assertions are blind to all of it. Only a real browser render exposes it.

## Worked Example: Reports Print-CSS

The report template carries inline print CSS (`@media print`) that controls page breaks, table fit, and what is hidden on paper. A change to that CSS -- or to the disclosure controls the report uses -- passes any "the string `@media print` is present" check while silently breaking the printed page. The discipline requires launching the report in headless Chromium and exercising its print rendering, not asserting on the HTML the generator emitted.

(Today all report print-CSS is inline in the template, which is why this rule's glob includes `src/api/static/**` as forward-insurance: if the CSS is ever extracted to a static asset, the discipline keeps auto-loading instead of silently ceasing to.)

## Reviewer Self-Limiting Test

Apply this test to decide whether a browser render+print check is required for a given change:

> **"Would a plausible bug in this change pass a string-presence / DOM-only assertion but fail in a real browser?"**

If **yes**, a headless-Chromium render+print check is required and a string/DOM-only test does not clear the bar. If **no** (the change cannot manifest as a visual/layout/print/disclosure defect -- e.g., it only alters a value that a DOM-text assertion fully pins), the browser check is not obligated by this rule.

## Exclusions

- **Email templates are OUT.** They render in a different engine (mail clients), not a browser; a headless-Chromium check does not represent how they render.
- **`src/api/routes/**` is OUT.** Route handlers are backend request/response logic, not a rendered surface. Test them at the HTTP/response layer.

## Where the Concrete Mechanism Lives

The "simple first" concrete instance of this discipline is a committed headless-Chromium pytest (Playwright + Chromium; see `.claude/rules/devcontainer.md` for the browser-test infrastructure, the dev/main-checkout-only boundary, and the fail-closed convention + `SKIP_BROWSER_TESTS` opt-out). This rule states the discipline at the discipline level and deliberately does NOT hard-name that test's path -- point at the discipline, not a brittle file dependency. A `tests/...` module may be cited illustratively, but the obligation is "render it in a browser and check," not "one specific file must exist."
