# IDEA-167: The PII-fixture comment in test_report_generator.py names the wrong dangerous shape

## Status
`CANDIDATE`

## Summary
The comment added alongside E-270's PII-scanner fix (`tests/test_report_generator.py`, the `TestGenerateReportDestructiveReconcile` fixture UUIDs, commit `4b0d17d`) describes the shape that tripped the scanner as **"two hex letters."** The old segments were one hex letter followed by a digit — `…0000000000c1`, `…0000000000d1`, `…0000000000f1`. The scanner's `us_phone` regex matched because those isolate exactly ten zeros between a `-` and a NON-DIGIT; whether the non-digit is followed by a letter or a digit is irrelevant.

The comment's operative instruction — keep that segment all-numeric — is correct and unambiguous, so anyone who simply follows it is safe. The risk is inferential: a reader could conclude a *two-letter* suffix is the dangerous shape and that `…0000000000a2` is therefore fine, when that is precisely the tripping shape.

Fix: replace "two hex letters" with an accurate description (a non-digit terminating a run of exactly ten digits), or drop the shape description and keep only the instruction.

## Why It Matters
Low severity by itself — one word, in a comment whose instruction is already right, on a test fixture. It is captured because of what it is an instance of, not its size: this is the **seventh** occurrence of E-270's recurring defect class (prose asserting something reasoned-to but not verified), and it was introduced **in the fix to the sixth**. The preceding one is sharper still: `se`'s first attempt at this same fix added a comment that QUOTED the offending literal, and the scanner blocked again on the comment — caught only by re-running rather than assuming the fix worked. A rule now exists for exactly this (`.claude/rules/tool-output-integrity.md`, "Prose you AUTHOR is a claim too"); leaving a known-inaccurate claim in place immediately after codifying that rule is the kind of thing that quietly erodes it.

## Rough Timing
No urgency, and explicitly NOT worth a dedicated commit — `cr` recommended not holding the E-270 commit for it and PM agreed. Fold into the next touch of `tests/test_report_generator.py`, which is a frequently-edited file.

## Dependencies & Blockers
- [ ] None. One-line comment change.

## Open Questions
- Is a shape description worth keeping at all, or is the bare instruction ("keep this segment all-numeric") strictly safer? A description invites a reader to reason from it; an instruction does not.
- Does `src/safety/pii_scanner.py`'s `us_phone` pattern warrant a skip entry for synthetic UUID fixtures, as `requirements*.txt` already has for SHA256 hashes? That would remove the class rather than document it — but it also widens a scanner exclusion, which is the direction that needs care.

## Notes
Found by `cr` during the E-270 commit sequence, after the pre-commit PII scan blocked the first attempt on three `us_phone` matches. `se` established the false positive with evidence and separately scanned the whole committed `tests/fixtures/` tree with the same regex (0 matches), closing the escalation branch that something had entered via E-270-03's `data/raw/`-unavailable fixture substitution. Related: E-270 (archived), [[IDEA-166]].

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23 (90 days)
