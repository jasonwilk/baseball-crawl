# IDEA-168: Season vocabulary drift fails silently (no log; under-rests Varsity arms)

## Status
`CANDIDATE`

## Summary
E-272's season axis keys entirely on the exact token `"summer"` (strip + lowercase). If GameChanger ever emits a variant — `"Summer 2026"`, `"summer_ball"`, `"Summer Legion"` — every summer opponent silently falls back to spring NSAA rules, and in the common case **no log line fires anywhere**. The feature stops working invisibly, with no operator-visible signal that anything changed.

## Why It Matters
The two mechanisms have deliberately different widths, and the gap between them is the blind spot:

- **The gate** (`_is_summer_season`, `src/reports/starter_prediction.py`) is a **2-way** split: `== "summer"` after normalize; everything else takes the spring/NSAA default.
- **The observability log** (`_log_bracket_season_disagreement`) is a **3-way** split: it fires only on membership in `_KNOWN_NON_SUMMER_SEASONS = {spring, fall, winter}` **AND** only when a mapped `\d+U` bracket is present.

So an unrecognized token is invisible to the log by design (we cannot substantiate a conflict with a token we do not know — correct as written), and with no bracket present the log is not consulted at all. A team like "Anytown Reserve" with `season="Summer 2026"` gets `nsaa_subvarsity` instead of `nrbl`, silently.

Two properties keep this off the blocker list:
1. **The failure direction is safe for sub-varsity words — but NOT for Varsity. (CORRECTED 2026-07-25.)** This entry originally read "the failure direction is safe" without qualification. That is false as written, and the correction matters to how urgent this idea is:
   - **Sub-varsity words (JV / Reserve / Freshman / Frosh / Sophomore): safe.** `NSAA_SUBVARSITY` (90 max, 1/2/3/4) demands at least as much rest as `NRBL` at every pitch count up to its cap, so drift over-rests.
   - **Varsity: NOT safe.** Drift routes a summer Varsity team to `nsaa_varsity` instead of `legion`, and those two curves **cross over** — a 50-pitch outing needs 1 rest day under NSAA Varsity but 2 under Legion (also looser at 61-70 and 81-90). So drift on a Varsity-worded summer opponent **under-rests** an arm by a day at three tiers.
   This raises the stakes: the failure is not merely invisible, it is invisible AND under-resting for one of the two level families. It is still not a defect against any AC — the behavior is exactly what TN-4 specifies — but "silent and safe" was the wrong reason to be relaxed about it.
2. **It is fully spec-compliant.** TN-4 designed the default deliberately, and AC-7 deliberately scoped the log to the bracket case.

What makes it worth capturing anyway: the vocabulary is **observed, not specified**. We match on a token GameChanger never contracted to keep stable, so the feature's correctness rests on an empirical sample rather than on a documented enum. Losing the axis returns us to pre-E-272 behavior while the code still looks correct.

**Evidence UPDATED 2026-07-25 (api-scout live probe, n=18) — supersedes this entry's original premise.** As originally written this said `"summer"` was "the *only* token ever observed" (OQ-1, 28 occurrences in the proxy corpus) and framed the risk as a *single*-token dependency with no sibling sample. That is no longer accurate: a live 18-team probe observed **`"summer"` on 17 and `"spring"` on 1** — so a sibling token exists, it is a bare lowercase word like `"summer"`, and it takes the spring/NSAA default correctly. Net effect on this idea, in both directions:
- **Risk DOWN.** Two confirmed tokens both matching the same simple shape (bare, lowercase, single word) is meaningful evidence that the vocabulary is a plain lowercase enum rather than a free-text or composite field. The `"Summer 2026"` / `"summer_ball"` scenarios now look less likely than they did on a one-token sample.
- **Risk NOT eliminated.** api-scout's own framing is that n=18 shows an **OPEN vocabulary, not a closed enum** — two observations do not bound the set, and `"fall"`/`"winter"` remain unsampled. The failure mode is unchanged; only its estimated likelihood moved.
- **One thing improved outright:** `_KNOWN_NON_SUMMER_SEASONS` now has a CONFIRMED live member (`"spring"`), so the disagreement log fires on real data rather than on a token we had only hypothesized.

## Second trigger: the season FIELD is absent (added 2026-07-25)
Drift in the token's WORDING is one way to lose the season signal. **Absence of the field is the other, and it lands in exactly the same place.** Both are recorded here rather than in separate files because they share one landing spot, one consequence, and one fix — split across two ideas, someone fixes one trigger and believes the exposure is closed.

SE measured both routes on real teams:

```
Norfolk Varsity   season=None -> nsaa_varsity    | true summer -> legion   DIVERGES (110 vs 105)
Norfolk Reserve   season=None -> nsaa_subvarsity | true summer -> nrbl     DIVERGES (90 vs 105, OVER-rests, safe)
```

Same asymmetry as the drift trigger: the sub-varsity divergence over-rests (safe), the Varsity divergence under-rests (not safe).

**The two triggers differ sharply in reachability, and that difference should drive priority:**
- **Drift (wording)** becomes reachable the moment GameChanger changes a string. Nothing on our side gates it, and nothing warns us.
- **Absence (missing field)** is currently UNREACHABLE in practice. api-scout found `season` present and non-null on 18/18 teams, and `_fetch_public_team_info` is **fail-safe by accident of structure**: all five signals are set inside one `if resp.status_code == 200:` block from one parsed payload, so a fetch failure nulls EVERY signal together — `detect(None, None, None, None)` → `unknown` → rules `None` → **card suppressed**, not silently mis-classified. An isolated `season=None` alongside intact other signals is not a shape that function can produce. The only route in is a 200 whose payload carries `name` but omits `team_season.season`, which has never been observed.

**Do not "fix" the fail-safe handler on this idea's account.** Its swallow-everything behavior is what makes the league gate degrade to suppression instead of to a wrong rest table. Any future tightening of that error handling must preserve the wholesale property — a more granular handler that let `season` fail independently while other signals survived would CREATE this exposure rather than close it. That is the counterintuitive part and the reason it is written down.

**One fix serves both triggers:** make the Varsity branch's season-absent fallback safe rather than assuming NSAA. That addresses drift, absence, and any future third route in one change — which is the strongest argument for keeping them in one file.

## DO NOT close this as "superseded by the operator pick" (recorded 2026-07-25)
E-263-02c adds an operator-PICKED competition level, and the operator's 2026-07-25 ruling on E-272's ≤14U reclassification leaned on exactly that mechanism ("the team config settles it"). A future reader may reasonably infer that the operator pick also retires this idea. **It does not**, and the reason is structural rather than a matter of degree:

Per E-272 TN-6's load-bearing fact, **the operator pick does not reach `bb report morning-run`.** That path is unattended by definition — no operator at the keyboard — so it ALWAYS infers, and inference is the sole league resolver there. Morning-of-game scheduled reports are the project's strategic forward surface, so the path this idea protects is the one that matters most going forward, not a legacy corner.

Net: after E-263-02c ships, the operator pick closes this exposure on the interactive path and leaves it fully open on the unattended one. This idea's fix retains standalone value for morning-run. Anyone triaging it should evaluate it on that basis rather than marking it resolved by a mechanism that structurally cannot reach the affected path.

## Rough Timing
Low urgency, but NOT zero — the original "no urgency" rating rested on the blanket-safe claim retired above, and the Varsity under-rest exposure argues for revisiting it. Promote when any of these trip:
- A real NRBL or bare-summer-level-word opponent is scouted and resolves to the wrong family.
- api-scout observes ANY `team_season.season` token other than lowercase `"summer"`.
- An out-of-state or otherwise unexpected opponent enters scope (this shares a revisit trigger with E-272's documented in-state/Nebraska binding assumption, TN-2 bracket-floor justification).

## Dependencies & Blockers
- [x] E-272-02 shipped (the season axis exists to drift)
- [ ] None blocking — this is additive observability, not a behavior change

## Open Questions
- **Widen the gate, or widen the log?** These are different risk profiles. Widening the GATE (e.g. substring/prefix match on `summer`) changes classification behavior and could mis-route a genuinely non-summer team; widening the LOG is observability-only and cannot mis-rest anyone. Strong prior: log first, gate only on evidence.
- Should an **unrecognized** season token log at INFO/DEBUG on every detection, independent of the bracket path? That closes the blind spot without asserting a conflict we cannot substantiate.
- Is there a cheap **corpus assertion** — a periodic api-scout check that the observed token set is still within the confirmed `{"summer", "spring"}` — that would catch drift at the source rather than at the symptom?
- Would a report-side "league inferred as X (season: Y)" provenance line be more useful to the operator than any log? That surfaces drift where someone is actually looking.

## Notes
Surfaced by code-reviewer during E-272-02 review (2026-07-25), explicitly flagged as idea-capture rather than a story blocker; PM concurred. Both reviewers and PM passed AC-7 as written — this is not a defect against any acceptance criterion, it is a durability observation about a design that is correct today.

Related: E-272 TN-4 (season vocabulary + the spring/NSAA default rationale, including its 2026-07-25 correction retiring the blanket-safety claim), OQ-1 (api-scout's corpus verification), TN-2's bracket-floor justification (which carries the parallel in-state/Nebraska documented assumption and shares a revisit trigger).

Do NOT re-litigate the spring/NSAA default itself — it was ruled deliberately and remains correct on base rates (spring teams are the modal case; defaulting to the stricter-of-both would over-rest them). But do NOT justify it as "the safe direction" either: per the 2026-07-25 correction above and E-272 TN-4's own correction, it is *spring-is-likelier*, not *spring-is-safer*. The idea here is primarily about **noticing** drift rather than changing what happens when it occurs — though the Varsity under-rest exposure is a legitimate argument for raising this idea's priority above "no urgency".

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
