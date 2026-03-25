# IDEA-043: Fuzzy Duplicate Team Detection

## Status
`CANDIDATE`

## Summary
Extend the duplicate detection in E-155 from exact name matching to fuzzy matching (Levenshtein distance, token overlap, suffix stripping). Would catch "Lincoln East" vs "Lincoln East HS" vs "L. East" as potential duplicates.

## Why It Matters
Exact-name matching misses many real duplicates because GameChanger team names are inconsistently formatted. Coaches lose trust when duplicates persist that the system should have caught. Fuzzy matching significantly increases duplicate detection coverage.

## Rough Timing
After E-155 ships and the admin has used exact-match detection for a few weeks. Promote when the admin reports missed duplicates that fuzzy matching would have caught.

## Dependencies & Blockers
- [ ] E-155 (Combine Duplicate Teams) must be complete -- provides the merge infrastructure

## Open Questions
- What fuzzy matching algorithm? Levenshtein, Jaro-Winkler, token set ratio?
- What similarity threshold to use? Too low = false positives, too high = missed duplicates.
- Should fuzzy matches be shown with lower confidence than exact matches?

## Notes
Coach consultation (E-155 discovery) identified this as important but not MVP. "Lincoln East" vs "Lincoln East HS" vs "L. East" are the typical patterns.

**Primary real-world gap (E-155 review, Coach-2)**: Cross-source name variants are likely the most common duplicate scenario. The schedule loader creates "Lincoln East HS" (from schedule data), the resolver finds "Lincoln East" (the canonical GC name). E-155's exact-name matching won't flag these. This makes fuzzy matching the highest-impact improvement for duplicate detection coverage.

**NULL season_year gap (E-155 review, PM-2)**: E-155 detection also misses teams where one has `season_year=NULL` (stub) and the other has `season_year=2026` (resolved). Fuzzy matching should also consider NULL-vs-non-NULL season_year as a potential match.

---
Created: 2026-03-25
Last reviewed: 2026-03-25
Review by: 2026-06-23
