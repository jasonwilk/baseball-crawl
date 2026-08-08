---
name: spec-audit-sibling-producer
description: When an epic claims a "canonical/sole" producer of a value, grep for sibling producers that bypass it before trusting the scope.
metadata:
  type: feedback
---

When a removal/refactor epic asserts that a single function is THE producer (or canonical entry point) of some value — a season_id, a status, a slug, an ID — do NOT trust the claim from the epic text. Grep the whole `src/` tree for the value's literal forms and for independent derivation helpers BEFORE accepting the epic's enumerated reference set.

**Why:** E-241 (remove-season-machinery) was scoped around `derive_season_id_for_team` in `loaders/__init__.py` as the sole season_id producer. But `src/gamechanger/crawlers/scouting.py` had its OWN `_derive_season_id()` (+ `season_suffix="spring-hs"` default + a duplicate `_ensure_season_row`), LIVE in the sole reports path (`generator.py:1626` calls `scout_team` with no season_id). This second producer falsified the epic's Success Criterion ("no code path produces a YYYY-suffix slug") and made the migration's anti-fragmentation guarantee non-durable (next crawl re-emits the compound slug after the migration normalizes it). PM called it "the headline catch — exactly the root-vs-leaf miss this epic exists to prevent."

**How to apply:** For any spec-audit or invariant-audit of an epic claiming a canonical/sole producer or guarded writer:
1. Grep `src/` for the value's literal output forms (e.g. the compound-slug strings `spring-hs`/`summer-legion`), not just the named function.
2. Grep for sibling derivation helpers (`_derive_*`, duplicate `_ensure_*`, default-arg producers).
3. For each sibling found, trace whether it's in a LIVE path (e.g. invoked by the sole serving surface) and what tables/columns it writes.
4. A second producer that writes to tracking/side tables (not the protected partition) can still falsify a "no code path produces X" success criterion AND defeat a migration's durability guarantee even when stat correctness is unaffected — flag it as MUST FIX (scope completeness), separate from any FK-ordering/mechanism finding.

Related: [[invariant_audit_sibling_writer]] (DELETE+rederive defeating a provenance guard — same root-vs-leaf family, audit-mode variant).
