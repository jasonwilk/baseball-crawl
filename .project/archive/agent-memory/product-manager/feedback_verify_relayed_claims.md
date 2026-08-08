---
name: feedback-verify-relayed-claims
description: A relayed compound claim is only verified in the half its source directly observed — check the other half before scoping work on it
metadata:
  type: feedback
---

# Verify the half of a relayed claim the source did not observe

When a claim reaches you second-hand and has two parts — "X is wrong in the docs **and** in the tests," "this is a fabrication that **some docs and tests** describe" — treat only the part inside the source's direct observation as evidence. Check the rest yourself before scoping any work on it.

**Why:** during E-274 discovery, team-lead relayed api-scout's finding that the `team_season.season.year` nesting was "a fabrication that some docs and tests describe," and suggested a story to audit the fixtures. api-scout had genuinely inspected the **docs**; it had never audited the **tests**. PM checked: no test or fixture encodes the nesting, `tests/test_report_generator.py` uses the correct flat shape throughout, and the one live occurrence is `.claude/rules/testing.md`, which carries it **deliberately** as the labelled wrong example in its Test-Validates-Spec section. The rule was working exactly as designed. Acting on the relay would have manufactured a cleanup story out of a correct file.

Team-lead named the mechanism explicitly and asked for it to be recorded: forwarding a specialist's compound statement as a single unit after verifying only the half within that specialist's remit. It happened three times in one session.

**How to apply:**
- Ask what the source actually *looked at*. A specialist who inspected docs has said nothing about tests; an API probe has said nothing about our fixtures; a coach's rest-rule ruling has said nothing about where a label renders.
- Check the unobserved half before writing an AC, a story, or a Technical Note that depends on it. A grep is usually enough.
- If the unobserved half does not reproduce, **say so and drop the scope** rather than keeping a reduced version of the story. Two candidate defects dissolved on inspection in E-274; the right output was no story, not a smaller one.
- This binds your OWN compound claims too. In the same session PM asserted a "closed enum" (api-scout could not certify exhaustiveness) and a structural unreachability (software-engineer showed the payload nesting defeats it). Both were plausible, both were convenient, and neither had been checked. A discovery pass that only logs other agents' errors is not measuring itself.

Related: [[feedback_verify_cited_facts_before_approving]] (the same discipline applied to paths cited in prose), [[feedback_reverify_idea_before_folding]] (the same discipline applied to a backlog idea's premise).
