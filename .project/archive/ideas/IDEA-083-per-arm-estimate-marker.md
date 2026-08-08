# IDEA-083: Per-arm estimate marker for IP-proxied arms in non-estimate sections

## Status
`CANDIDATE`

## Summary
On the probable-starter card (reports), give an individual arm its own per-line "estimated rest" cue when that arm's most-recent rest was derived from the IP proxy (null pitch count) — but only in a section that is NOT already flagged as a section-level estimate. Today the card carries only a section-level estimate badge/banner (for youth/travel), which contextually covers every arm in that section but says nothing about a single IP-proxied arm appearing in an otherwise full-confidence (e.g. NSAA-varsity) section.

## Why It Matters
E-243's M1 ruling applies an IP proxy (innings → pitch-count bucket) when an arm's most-recent pitch count is null, and treats the proxied arm as DISCOUNTED when the bucket maps to a non-zero preferred rest. That is a per-arm estimate condition finer-grained than the section-level `is_estimate` treatment. In a non-estimate section, the rest chip would read fully confident even though that one arm's rest was proxied. Surfacing it per-arm would make the card fully honest at the arm level. The decision weight is small: the IP proxy still discounts the arm correctly in the ranking, so the gap is cosmetic (a missing visual cue), not a ranking error.

## Rough Timing
Someday / nice-to-have — no urgency. Promote only if IP-proxied arms in non-estimate sections turn out to be more common than expected (NSAA varsity mandates pitch-count tracking, so a null there should be rare) OR a coach reports being misled by a confident-looking chip on a proxied arm.

## Dependencies & Blockers
- [ ] E-243 (probable-starter usefulness) shipped — establishes the IP proxy and the section-level estimate treatment this refines.

## Open Questions
- How often does a null pitch count actually occur in a non-estimate (NSAA-varsity) section? (Frequency was assumed rare from the tracking mandate, not measured — worth grounding before promoting. See E-243 anti-assumption discipline.)
- What is the lightest per-arm cue that does not clutter the chip (a small dot/asterisk + tooltip vs. a chip variant)?

## Notes
Deferred from E-243 by ux-designer's card-design ruling (their domain): "no per-arm marker — the section-level estimate treatment is sufficient; Simple first." Recorded in E-243 epic.md TN-5 ("No per-arm estimate marker"). Parent epic: E-243. Related: the M1 IP-proxy ruling (E-243-01 AC-4), the section-level estimate treatment (E-243-03 AC-5).

---
Created: 2026-06-27
Last reviewed: 2026-06-27
Review by: 2026-09-25
