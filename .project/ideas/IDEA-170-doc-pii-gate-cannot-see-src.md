# IDEA-170: The doc-PII byte-gate structurally cannot see `src/`

## Status
`CANDIDATE`

## Summary
A real team `public_id` is hardcoded in two docstrings in `src/gamechanger/team_resolver.py` (~line 15 and ~line 61) — verified programmatically against a real team row in the dev DB, so it is a live identifier, not a placeholder. The two-line fix matters less than what it reveals: **`scripts/check_doc_pii.sh` only sweeps docs trees, so no automated gate can catch a real identifier in `src/`, `tests/`, or `scripts/`.**

## Why It Matters
The project runs two complementary PII defenses, and this instance falls in the seam between them:

- **`src/safety/pii_scanner.py`** catches credentials, emails, and phone numbers by PATTERN. A GameChanger `public_id` is an opaque slug — it matches no pattern, so the scanner cannot flag it, by design.
- **`scripts/check_doc_pii.sh`** catches exactly this class — real names, UUIDs, and `public_id`s — by matching a denylist of literal known identifiers. But it is invoked against a docs tree (`scripts/check_doc_pii.sh docs/api`), so its coverage stops at the docs boundary.

The result is a structural blind spot rather than a missed run: the only tool that CAN detect a real `public_id` is never pointed at the code. The pre-commit path therefore cannot catch this class in source, and the finding surfaced only because a human agent happened to read the file.

Severity is genuinely low for this instance — a `public_id` is public-by-construction (it is the slug in a shareable GameChanger URL), and these are docstrings in a scouting helper. But the project's standing security rule is that real identifiers do not belong in committed source, and "low severity this time" is a property of what happened to land there, not of the gap. A real athlete name in a docstring would be the same gap with a materially worse instance.

## Rough Timing
Two separable pieces, and they should not be bundled:
- **The two docstring occurrences**: trivial, fold into the next touch of `team_resolver.py`. Not worth a dedicated commit (the IDEA-167 precedent).
- **The coverage gap**: the real item. Promote when someone is next working on the safety tooling, or immediately if a HIGHER-severity identifier (a real athlete name) is ever found in source.

## Dependencies & Blockers
- [ ] None for the docstring fix.
- [ ] The coverage extension needs a decision on noise tolerance before it is worth building (see Open Questions).

## Open Questions
- **Is pointing the existing gate at `src/` actually cheap?** The denylist is literal-match, so running `check_doc_pii.sh src/` may be nearly free — or it may produce false positives wherever a legitimate fixture or test constant intentionally contains a denylisted string. Worth a dry run before committing to it.
- Should the gate run on the whole repo minus an explicit allowlist, rather than on enumerated trees? That inverts the default from opt-in to fail-closed, which matches how the project treats other safety gates.
- Do `tests/` and `scripts/` need the same coverage? `tests/` in particular carries fixtures that may legitimately hold identifier-shaped strings — this is where the noise question bites hardest.
- Is there a cheap sweep to find out whether these two are the only occurrences in `src/`, so the fix is not a whack-a-mole?

## Notes
Found by api-scout during E-272 Phase 4 review, while probing `team_resolver.py` for an unrelated header question. **Unrelated to E-272** — captured here rather than folded into the epic, since fixing it inside E-272 would widen a pitch-rules epic into safety tooling.

Deliberately does NOT record the identifier itself; see the cited file locations. Related: [[IDEA-167]] (PII-fixture comment naming the wrong shape) — both are cases where the PII tooling's real-world behavior diverged from what a reader would assume it covers, which may be the more useful pattern than either instance alone.

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
