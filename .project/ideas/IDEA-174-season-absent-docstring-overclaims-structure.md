# IDEA-174: `_fetch_public_team_info`'s docstring makes an API claim in the clothes of a structural one

## Status
`CANDIDATE`

## Summary
The docstring on `_fetch_public_team_info` (`src/reports/generator.py`, ~:1668-1670) asserts:

> *"An isolated `season=None` alongside a usable `team_name` is not a shape this function can currently produce; keep it that way."*

Strictly read, that is false. The five signals are **not** co-located in the payload: `team_name`, `ngb`, and `age_group` are read top-level, but `season` and `season_year` are read one level down behind a defensive `pub_data.get("team_season") or {}`. A 200 whose body omits `team_season` — or carries it as `null` / `{}` — yields exactly `age_group` present with `season` None. That `or {}` is the code's own acknowledgment that the nesting can be missing.

## Why It Matters
What the docstring's deliberate coarseness actually guarantees is that a **fetch failure** is all-or-nothing: one `if resp.status_code == 200:` block, so a timeout/DNS/non-200 nulls every signal together and league detection degrades to `unknown` → card suppressed. That is a real and load-bearing property, and it is the reason the handler must not be split into per-field error handling.

But **payload-shape completeness is a different and weaker claim**, and the sentence conflates them. It is a claim about the **API** wearing the clothes of a claim about the **function**. What makes it true in practice is api-scout's live evidence — `team_season` present and flat across every sampled team, response key set stable across 7 samples — which is genuine evidence and belongs *in the sentence*, rather than being silently substituted by a structural assertion.

The risk is not that the code is wrong today. It is that a future reader cites the sentence as a **structural guarantee** and reasons that some partial-signal shape is unreachable by construction, when it is only unreachable by observation of a vendor payload we do not control. That is the same defect class this project has repeatedly shipped: prose asserting behavior more strongly than the code supports, concentrated in the closing generalization of a safety note — exactly where it gets checked least.

## The correct wording direction (not a spec)
Say what is structural and what is empirical, separately: the fetch-failure path is all-or-nothing **by construction**; an isolated `season=None` requires a 200 whose payload omits `team_season`, which **has not been observed** (cite the sample). Keep the "do not split this into per-field error handling" instruction exactly as forceful as it is now — that part is correct and load-bearing.

## Why It Matters (bounded)
Low severity, and deliberately so. E-274 established that the exposure this sentence covers is bounded and that E-274 adds **no new risk kind** to it: season-absent + `"Varsity"` in the name already resolves `nsaa_varsity` today via the name path, and season-absent + `high_varsity` resolves the same league by the same spring default — identical outcome, identical curve. Only the population changes, and that delta is itself bounded by the unobserved payload shape.

## Rough Timing
Fold into the next deliberate touch of `_fetch_public_team_info` — explicitly not worth a dedicated commit or epic. Promote earlier only if someone is observed **citing** the sentence as a structural guarantee in a design decision, which is the failure mode this captures.

## Dependencies & Blockers
- [ ] None. Pure prose correction.

## Open Questions
- Does the same over-claim appear in [[IDEA-168]]'s own text? That idea's "Second trigger" section makes a closely-related argument ("`_fetch_public_team_info` is **fail-safe by accident of structure**… an isolated `season=None` alongside intact other signals is not a shape that function can produce"). If so, both need the same correction, and IDEA-168's is the more consequential of the two because it drives that idea's priority rating.
- Is there a cheap assertion — a test or an api-scout corpus check — that would make the empirical half of the claim self-monitoring rather than a frozen observation?

## Notes
Surfaced by software-engineer during E-274 discovery (2026-07-25), correcting a reconciliation PM had proposed in the stronger form. PM had argued the shape was structurally unproducible and was about to record that in E-274's Technical Notes; SE read the actual lines and showed the nesting defeats it. **Recorded partly because of who got it wrong** — the over-claim was persuasive enough that PM independently reconstructed it from the docstring rather than catching it.

Explicitly OUT of E-274's scope: the wording is load-bearing against a granular-error-handling refactor, and weakening it casually is worse than leaving it imprecise. Any rewrite must preserve the wholesale-failure instruction at full force.

Related: [[IDEA-168]] (shares the underlying claim and the priority reasoning built on it), E-274 TN-6 (records the correction and the bounded-exposure conclusion).

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
