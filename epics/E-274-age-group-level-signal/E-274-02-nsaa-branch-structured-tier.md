# E-274-02: Structured tier inside the recognized-`nsaa` branch

## Epic
[E-274: Read GameChanger's `age_group` as a structured level signal](epic.md)

## Status
`BLOCKED`
<!-- Blocked on Open Question OQ-1 (prevalence of a recognized ngb on opponent profiles), NOT on a
     sibling story. If OQ-1 shows ~zero opponents carry a recognized nsaa/nfhs ngb, this story is
     ABANDONED and re-filed as an idea. Do NOT dispatch it before OQ-1 is answered. -->

## Description

After this story is complete, a team whose `ngb` is recognized as `nsaa`/`nfhs` has its varsity-vs-sub-varsity **tier** decided by the structured `age_group` value when one is present, instead of by a team-name substring match that defaults to varsity when the name carries no keyword. The governing body still selects the rule system; only the tier within it changes source.

## Context

**This story is BLOCKED and may be abandoned. Read the gate before doing anything else.**

Software-engineer surfaced this while analysing placement and flagged it explicitly rather than letting it ride in as an implication of E-274-01. Inside the recognized-`ngb` branch, `_nsaa_level_from_name(team_name)` (`src/reports/starter_prediction.py:518-526`) returns `nsaa_varsity` when the name carries no level keyword — and that default is the **under-resting** direction (the module's own comment at lines 278-286 states the varsity branch is not conservative). A structured `high_junior_varsity` is strictly better evidence than an absent name keyword. Verified today: `ngb=["nsaa"]`, `team_name="Anytown East"`, `age_group="high_junior_varsity"` resolves `nsaa_varsity`.

**Why it is separated from E-274-01 rather than folded in.** It is a different risk class. E-274-01 activates a field that is provably inert today, so it cannot regress an existing resolution. This story changes a **currently-shipping path**, making it the only part of the epic that can regress a working result. Keeping it on its own diff keeps that blast radius reviewable.

**Why it is BLOCKED.** Its value depends on prevalence nobody has measured. api-scout observed `ngb` as the junk-empty `"[]"` on 5 of 7 opponent profiles and `""` on the other 2 — **zero recognized values in that sample**. If that generalizes, this story fixes a path no opponent traverses, and shipping a regression-capable change for no measured benefit is the wrong trade. **OQ-1 in the epic file must be answered before this story is dispatched.** If prevalence is ~zero, abandon it and re-file as an idea; do not dispatch on the theory that the fix is cheap.

This story does **not** contradict the epic's Technical Notes TN-2 precedence ruling. `ngb` still names the rule **system** and still outranks `age_group`; the structured value supplies only the **tier within** the already-selected NSAA family. Those are orthogonal axes.

## Acceptance Criteria

- [ ] **AC-1**: Given a recognized `ngb` of `nsaa` or `nfhs` and a team name carrying **no** level keyword, when `age_group` is `high_junior_varsity` or `high_freshman`, then the resolved league is `nsaa_subvarsity` — not the `nsaa_varsity` default the name path returns today. A test pins the current behavior being corrected.
- [ ] **AC-2**: Given a recognized `nsaa`/`nfhs` `ngb` and `age_group == "high_varsity"`, then the resolved league is `nsaa_varsity`.
- [ ] **AC-3**: Given a recognized `nsaa`/`nfhs` `ngb` and an `age_group` that is absent, empty, or unrecognized, then the tier is decided by `_nsaa_level_from_name` exactly as it is today — this path is unchanged, so an unrecognized value can never be a regression.
- [ ] **AC-4**: Given a recognized `ngb` that is **not** `nsaa`/`nfhs` (`american_legion`, `usssa`, `perfect_game`), then the result is unchanged by this story — the structured tier applies only within the NSAA family, and a genuine `usssa` team stays `usssa` regardless of its `age_group`.
- [ ] **AC-5**: Given a recognized `nsaa`/`nfhs` `ngb` and one of the four out-of-scope school values (`middle_12U`, `middle_13O`, `elementary`, `college`), then the outcome is consistent with the epic's Technical Notes TN-3 suppression ruling rather than silently taking the varsity default. State the chosen behavior in the test docstring with its reasoning.
- [ ] **AC-6**: The full suite is green and the five `starter_prediction` importer files named in Technical Notes TN-8 pass. Because this story changes a shipping path, any existing assertion that must change is a genuine stale-contract update — identify each one explicitly and state why the old assertion was encoding behavior this story deliberately corrects.

## Technical Approach

Within the branch that has already selected the NSAA family from a recognized `ngb`, decide the varsity-vs-sub-varsity tier from the structured `age_group` value when one is recognized, falling back to the existing name-based helper otherwise. Reuse the school-value → level-class mapping E-274-01 establishes rather than introducing a second mapping — two places deciding what `high_freshman` means is exactly the drift this epic's single-chain design avoids.

Note the epic's Technical Notes TN-5 constraint: do **not** route `age_group` through `_nsaa_level_from_name`. That helper matches with a plain `in` substring rather than a word boundary, so it happens to give the right answer for `high_freshman` by coincidence rather than by contract — and the same looseness makes `"Anytown Preserve"` resolve sub-varsity.

The season axis is not involved here: a recognized `ngb` already fixes the family, so this is a tier decision only.

## Dependencies
- **Blocked by**: E-274-01 (reuses its school-value → level-class mapping); **Open Question OQ-1** (prevalence gate — see Status and Context)
- **Blocks**: None

## Files to Create or Modify
- `src/reports/starter_prediction.py` (modify — the tier decision inside the recognized-NSAA branch only)
- `tests/test_league_detection.py` (modify — coverage for the NSAA-branch tier decision)

Does NOT modify the ngb-empty region E-274-01 owns, `_LEVEL_WORD_PATTERNS`, `_nsaa_level_from_name`'s own behavior for the name path, or any rest-rule table.

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] OQ-1 was answered before dispatch and the answer justified shipping rather than abandoning

## Notes

The prevalence gate is the point of this story's BLOCKED status, and it should not be quietly satisfied by an implementer's judgment that the change looks safe. The relevant question is not "is this correct?" — it is — but "does any opponent reach this path?" A correct fix to an untraversed branch still adds a regression surface and a maintenance obligation for no coaching value.

If OQ-1 comes back positive (opponents do carry recognized `nsaa`/`nfhs` values), this story is worth shipping on its own merits: the current default is the under-resting direction, which is the direction this project treats as unacceptable, and a structured value is strictly better evidence than an absent keyword.
