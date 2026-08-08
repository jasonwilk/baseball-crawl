# IDEA-144: Deliberate size-driven split of scouting_report.html

## Status
`CANDIDATE`

## Summary
The standalone scouting report template `src/api/templates/reports/scouting_report.html` is ~900+ lines and grows with every new report section. At some point a deliberate, size-driven split into Jinja2 partials (`{% include %}`) is warranted for maintainability — but as its OWN refactor decision with real requirements, not smuggled in via a speculative feature epic.

## Why It Matters
During E-265 (Pitcher Outings Breakdown) refinement, both software-engineer and ux-designer recommended adding the new section INLINE rather than introducing an `{% include %}` section framework, because building reusable template plumbing for one section — especially to match the PARKED E-263 Deep Scout epic's un-built include contract — is speculative complexity ("Simple first. Complexity as needed."). That was the right call for E-265. But SE explicitly flagged that the template's growing size is a legitimate concern that should drive its own refactor when the pain is real, with the partial boundaries chosen from the actual section inventory rather than guessed from a parked epic's needs.

## Rough Timing
When the template's size actively hurts maintainability (merge conflicts across concurrent report-feature epics, hard-to-navigate single file), or when a real consumer (e.g. a revived E-263) needs a shared section-include mechanism. Not urgent while report sections are added infrequently and inline-gated.

## Dependencies & Blockers
- [ ] Real pain: repeated merge friction or navigation cost on `scouting_report.html`, OR a concrete second consumer needing shared includes
- [ ] A section inventory to choose partial boundaries from (Most Likely Arms, Pitching table, Batting table, Spray, Outings Breakdown, header/footer, embedded CSS/JS)

## Open Questions
- Partial boundaries: by report section, or extract the large embedded `<style>`/`<script>` blocks first?
- Does the report's self-contained-single-file serving contract (frozen HTML on disk) constrain how partials are composed at generation time? (Partials compose at RENDER time; the written artifact stays a single self-contained file — confirm no serving-path impact.)
- If E-263 revives and introduces its own `deep_scout` framework, does that subsume this, or are they different scopes (feature framework vs. maintainability split)?

## Notes
Raised by software-engineer during E-265 refinement (2026-07-15) as an explicit "flag as idea, not E-265 scope" note. Related: E-265 (inline decision), E-263 (parked Deep Scout, plans its own `{% include %}` framework).

---
Created: 2026-07-15
Last reviewed: 2026-07-15
Review by: 2026-10-13
