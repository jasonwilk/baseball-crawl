# IDEA-176: `\bsophomore\b` has no plural, while `\breserves?\b` does

## Status
`CANDIDATE`

## Summary
In `_LEVEL_WORD_PATTERNS` (`src/reports/starter_prediction.py:313`) the sophomore entry is `\bsophomore\b` — no `s?`. Its neighbour two lines up is `\breserves?\b`, which does carry one. Software-engineer verified the divergence live:

```
"Anytown High Sophomore"    -> nsaa_subvarsity   (matches)
"Anytown High Sophomores"   -> unknown           (does NOT match; card suppressed)
"Anytown High Reserves"     -> nsaa_subvarsity   (matches, via reserves?)
```

## Why It Matters
Low severity and **safe-direction** — a missed match falls to `unknown` and suppresses the card, so no coach is handed a wrong rest number. That is why this is an idea and not a defect.

What makes it worth recording is the **inconsistency** rather than the miss. A reader scanning `_LEVEL_WORD_PATTERNS` sees a table where some level words tolerate a plural and one does not, with nothing marking the difference as deliberate. Either the `s?` on `reserves?` is the intended convention and `sophomore` is an oversight, or plurals are handled case-by-case for a reason nobody wrote down. A future editor adding a level word has no way to tell which, and will guess.

Worth pairing with the observation that team names in this domain *are* pluralised routinely ("Reserves", "Sophomores" both read naturally as squad names), so the plural form is not a contrived input.

## Rough Timing
Fold into the next deliberate touch of `_LEVEL_WORD_PATTERNS` — explicitly not worth a dedicated commit. [[IDEA-172]] proposes reordering that same list and is the natural carrier; E-274 deliberately does **not** touch the list at all (its school branch runs before the list is consulted), so it is not the right home.

Do not promote this on its own. Two ideas already queue against this one function; a third single-line fix arriving separately is churn.

## Dependencies & Blockers
- [ ] None.

## Open Questions
- Is the plural divergence deliberate anywhere else in the table? A full pass over all nine entries would settle whether `reserves?` is the exception or `sophomore` is — nobody has checked the other seven.
- Should the fix be per-entry `s?` additions, or a single normalisation step applied before matching? The latter is tidier but is a wider behaviour change to a rest-rule gate, and E-274's Technical Notes TN-5 records why broad normalisation of this matcher is treated with suspicion (it recruits inputs into branches by accident).
- Does the same gap exist for `frosh` / `freshman`? Neither takes a natural plural, so probably moot — but unchecked.

## Notes
Found by software-engineer during E-274 discovery (2026-07-25) while demonstrating why a `high_*` prefix match on the `age_group` value would be a trap — the sophomore pattern was the worked example, and the plural gap surfaced incidentally alongside it. SE flagged it explicitly as "worth an IDEA, not an E-274 story," and that judgment is adopted here.

Related: [[IDEA-172]] (reorders the same list — the natural carrier), [[IDEA-171]] (promoted to E-274; same "level-word matching is weaker than it looks" theme).

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
