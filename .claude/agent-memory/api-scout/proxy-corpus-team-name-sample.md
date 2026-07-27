---
name: proxy-corpus-team-name-sample
description: proxy/data/sessions holds ~563 distinct real team NAMES harvestable from stored response bodies -- the only durable name corpus outside the live DB; used to show Legion+Varsity co-naming is 0/563 and `\bjuniors\b` is entirely unattested
metadata:
  type: reference
---

# The proxy capture is a durable TEAM-NAME corpus (measured 2026-07-26, E-275 planning)

## Provenance and skew bound

**Where the name evidence actually lives.** `proxy/data/sessions/*/endpoint-log.jsonl`
(main checkout only -- gitignored, absent from worktrees) stores full `response_body`
payloads on SOME captures. Harvesting `name`/`team_name`/`opponent_name` from any dict
also carrying a team marker key (`age_group`, `public_id`, `team_id`, `ngb`,
`team_season`, `progenitor_team_id`, ...) yields **563 distinct team-shaped names**.

**⚠ CORRECTED 2026-07-26 -- the provenance is NARROWER than "12 sessions".** I first
wrote "12 capture sessions" and PM nearly pinned that in an operator-facing epic line.
24 session dirs exist; **12 carry an `endpoint-log.jsonl`; only 4 store response bodies
at all.** The other 8 logs are request METADATA only (method/path/status, no body) --
`2026-03-06_204244` alone logs 5,872 requests and contributes zero names. Exact figures:

| | |
|---|---|
| requests logged across all 12 logs | 16,665 |
| stored response bodies | 2,518 |
| JSON-parseable bodies (what names came from) | 1,754 |
| distinct team-shaped names | 563 |
| sessions contributing names | **4** |
| date range of contributing sessions | **2026-03-11 to 2026-03-12** |

Per contributing session (names are deduped across them, 665 -> 563):
`2026-03-11_032625` 212, `2026-03-11_034739` 331, `2026-03-11_053607` 16,
`2026-03-12_034919` 106. The 764 unparseable bodies are `binary/octet-stream`,
`text/plain` etc. -- non-JSON assets, not truncation.

**So the corpus is a TWO-DAY window from four sessions, not a week across twelve.**

**Name the two quantities separately, every time -- a corrected number with no named
distinction regenerates this error the moment someone counts session directories again:**

- **"sessions carrying a log"** = **12**. Right answer to "how many captures logged
  anything." Wrong for any provenance claim about DATA.
- **"sessions storing response bodies"** = **4**. The only one that supports a claim about
  what was measured.

They differ by 3x, both are derivable from the same `ls`, and **the wrong one supports the
conclusion just as comfortably as the right one** -- which is why nothing about it looked
wrong. It was caught by RE-DERIVING (counting bodies per session), never by re-reading.

This is the ONLY durable real-name corpus outside `data/app.db`. **E-274's much larger
probes (n=73 / 134 / 51 / 160 / 163, ~460 teams) were run LIVE and their raw output was
never persisted** -- only summary statistics survive, in
[[public-team-age-group-level-field]]. If a future question needs name-level joins, the
proxy capture is the material; the E-274 numbers cannot be re-interrogated.

Provenance skew, which bounds every conclusion: `/teams/{id}/opponents` contributes 313
names (the operator's own schedules -- 19 Legion-token, 17 varsity), `/search/opponent-
import` 159 (mostly bracket/travel; only 1 Legion, 2 varsity), then `/search`,
`/me/teams`, `/organizations/{id}/teams`, recap-story. One program's network, one region,
captured **2026-03-11 to 2026-03-12** (corrected -- this line said "March 2026" and
contradicted the table above).

## The "18-team sample" is a MISNOMER -- it was never a name corpus

Both IDEA-172 and baseball-coach's RULING 4 send readers to "api-scout's 18-team sample"
for a name check. That sweep was an **`age_group`-population** probe of
`membership_type='tracked'` opponents, and `docs/api/endpoints/get-public-teams-public_id.md`
already records its population as a **sampling artifact** (it contained no HS varsity
teams). It cannot answer a naming question and never could. Do not send anyone there
again.

## What the 563-name corpus shows about level-word tokens

Distinct-name counts: `varsity` 31, `reserve(s)` 19, `post N` 14, `legion` 11, `seniors`
8, `jv` 8, `freshman` 7, `sophomore` 0, **`juniors` 0**. 213 names carry a `\d+U` bracket
(so never reach the level-word list); 273 carry no level signal at all.

- **`\bjuniors\b` is entirely unattested** -- 0 in the name set AND 0 across all 2,518 raw
  response bodies by substring. All 4 singular-`Junior` occurrences are `Junior Varsity`;
  **zero are `Junior Legion`**. (Verified twice; an intermediate probe's `junior. varsity`
  regex was buggy and disagreed -- the `\bjunior\s+varsity\b` result is the correct one.)
  **⚠ But `0/563` is the WRONG denominator for the naming-convention question, and citing
  it overstates my own finding.** "Do Legion teams name themselves Juniors?" is asked of
  LEGION teams: **0 of 22**, which is a weak null, not 0 of 563. (For contrast, of those
  same 22: plural `seniors` 3, singular `Senior` 1.) IDEA-206's editorial note caught this
  before I did -- it is right, and `0/22` is the figure to cite.
- **`Senior Legion` (singular) IS attested, once.** So Legion's division convention in the
  wild leans singular -- which the plural-only `\bseniors\b`/`\bjuniors\b` patterns match
  by accident at best.
- **Legion-token names essentially never state a tier.** Of the 22 names carrying
  `legion`/`post N`: **9** carry no tier word at all, **5 carry `reserve(s)`**, 4 a bracket
  only, 3 `seniors`, 1 singular `Senior`, and **0 `varsity`**. Sums to 22. All 22 are
  distinct under aggressive case/punctuation normalisation.

  **⚠ CORRECTED 2026-07-26 (spec audit F10) -- this line read "14 carry no tier word at
  all" and that was WRONG; it is 9.** The breakdown was computed with a tier set of
  {varsity, jv, seniors, juniors, senior, junior, bracket} that **OMITTED `reserve(s)`**,
  so the 5 Legion+Reserve names fell into the "no tier word" bucket. 14 = 9 + 5.
  **This is the exact omission this file warns about two sections below** ("PM's tier set
  omits `reserve`... they are invisible under PM's framing purely because of that
  omission") -- I identified the failure mode and then committed it one section earlier,
  uncaught, in the same document. **Any breakdown of level words must state its tier set
  explicitly and include `reserve(s)`.**

  **Side effect worth knowing: this DISSOLVES the "two different 14s" collision.** 14(a)
  (Legion-token names with no tier word) is now **9**; only 14(b) (the senior/junior-token
  pool) remains a 14. There is no longer a coincidence to disambiguate.

## The two results that matter for IDEA-172 / RULING 4

1. **`Legion Varsity` is CONSTRUCTED: 0 of 563** -- and the negative is informative
   because BOTH families are well represented (22 Legion-token names x 31 varsity names,
   zero overlap). Rule-of-three 95% upper bound on the co-naming rate among Legion-named
   teams: ~13.6%.
2. **The reorder is a behavioural NO-OP on this corpus: 0 divergences of 563**, for the
   full 4-pattern move AND for a narrowed `legion`/`post N`-only move. Coach's falsifier
   condition (`seniors`/`juniors` beside `varsity`/`jv`) is likewise **0 of 563** -- so
   the ruling is neither falsified nor confirmed, it is untriggered.

## The collision that DOES occur -- Legion + Reserve, 5 of 563

Five distinct names carry a Legion token together with `\breserves?\b` (all from
`/teams/{id}/opponents`, no brackets, distinct ids). `reserve` sits at priority 3, ahead
of the Legion patterns in BOTH the current and the ruled order, so **the reorder does not
touch the only real collision in the corpus** -- these keep resolving SUBVARSITY. Whether
a Legion program's reserve squad should take the NSAA sub-varsity table or Legion's is a
coaching question nobody has been asked.

**SETTLED 2026-07-26 (spec audit F10) -- all 5 carry a HARD Legion token, so the shape is
REAL and the safety reasoning was applied to the right thing.** Re-derived explicitly:
`legion` x3, `legion`+`post N` x1, `post N` x1; **zero** carry `seniors`/`juniors` without
a hard token. So they are genuine Legion/Post-N programs with a Reserve squad, they sit
INSIDE the 22, and a `legion`+`reserves?` guard sentinel describes a shape that exists.
(19 names carry `reserve(s)` corpus-wide; 5 of those 19 also carry a hard Legion token.)

## Live `\bseniors\b` misfire on a school-family team

One name carries `seniors`, no Legion token, no bracket, and `age_group: high_varsity` --
a school-family team that resolves `legion` today off the `seniors` pattern. `high_varsity`
matches neither `\d+U` nor the range regex (the documented parser gap), so it falls through
to the name words and the misfire is LIVE. Independent of the reorder.

**⚠ "TWO INDEPENDENT CORPORA" IS TOO STRONG -- say "two observations, same operator
network."** It corroborates the 1-of-73 `"... Seniors 2"` case in
[[public-team-age-group-level-field]], but both come from the same operator's network.
**Establishes that the misfire HAPPENS; establishes nothing about how OFTEN.**

**THE CONCLUSION RESTS ON NETWORK OVERLAP ALONE. My "sibling squad" inference was
OVERSTATED and is retracted -- 2026-07-26, tested at team-lead's request.** I wrote that
this corpus's `Seniors`-plus-digit name was "almost certainly the sibling squad of the very
team E-274 saw." **That is not supported.** What the test actually shows, so a reader can
judge rather than inherit it:

- This corpus holds exactly **1** name matching a `Seniors <digit>` suffix; its digit is
  `1`. **There is no `Seniors 2` in this corpus at all.**
- That name's program prefix (4 words) IS shared by exactly **1** other name, whose tail
  carries no digit and no level word -- so the program fields at least two teams. That is
  the only real support for a numbered-squad family.
- **The fatal gap: E-274's instance survives only as the ELIDED string `"... Seniors 2"`.
  Its program prefix was never persisted, so THE PREFIXES CANNOT BE COMPARED.** The raw
  E-274 output is gone (see the note above on unpersisted probes). Same-program is
  untestable, not merely unproven.
- Squad numbering is rare corpus-wide -- 3 names end in a bare digit, only 1 with a level
  word -- which cuts both ways and settles nothing on n=1.

**So the honest basis is just: both observations come from the same operator's network,
which is certain and sufficient to defeat any independence claim.** The sibling inference
added nothing and should not be repeated. Note the shape -- **the VERDICT ("not
independent") survived while its stated REASON was wrong**, which is exactly the failure
mode where a correct conclusion immunises a false premise from review.

**Do not inflate the count.** 4 of 563 names carry `seniors` with no Legion token and no
bracket, but only ONE is a confirmed live misfire. A second carries
`age_group: "Between 13 - 18"` -- superficially the rec-age-cohort case coach hypothesised,
but the range regex fires BEFORE the name words, so it resolves `youth_travel` and never
reaches `seniors`. **It is not a live misfire.** The remaining 2 have no captured
`age_group`, so they are unclassifiable, not confirmed. **1 live, not 4.**

## Re-run under PM's NARROWER framing (2026-07-26, same corpus)

PM reframed the query from the bare token to the CO-OCCURRENCE that the reorder
actually moves. Run against the literal token sets, denominator 563:

- {`legion`, `american legion`, `post N`, `seniors`, `juniors`} x {`varsity`, `jv`,
  `junior varsity`} in one name string: **0 / 563.** Legion-set names 27, tier-set names
  35, intersection empty. Per token: `legion` 11/0, `american legion` 1/0, `post N` 14/0,
  `seniors` 8/0, `juniors` **0 present at all**.
- Denominators reconcile: union(legion, post N) = 22; +5 `seniors`-without-a-hard-token
  = 27; varsity 31 + bare-`jv`-not-varsity 4 = 35. No name carries both a senior* and a
  junior* token.

**⚠ The 0 and the 5 answer DIFFERENT questions -- do not let them merge.** PM's tier set
omits `reserve`. The 5 Legion+Reserve collisions above are real; they are invisible under
PM's framing purely because of that omission. "0 co-occurrences" must never be relayed as
"no Legion-vs-tier-word collisions exist."

## The zero is LOAD-BEARING on the patterns being plural-only

Widening the Legion `seniors`/`juniors` patterns to accept the SINGULAR form takes the
legion-set from 27 to 32 names and **co-occurrence from 0 to 4 -- and all 4 are `Junior
Varsity`**, where the singular "Junior" is half of the tier phrase, not a Legion division
name. Widening would manufacture four false Legion signals from four ordinary JV teams.
(They would still resolve sub-varsity, since `\bjv\b|\bjunior\s+varsity\b` is priority 1.)
Read together with `\bjuniors\b` being unattested across all 2,518 bodies: **the problem
with `seniors`/`juniors` is the patterns themselves, not their POSITION in the list.**

## Coach's bare-token bar is NOT met and cannot be met from repo material

baseball-coach set a floor of **30-50 distinct names containing senior/junior tokens**.
The corpus holds **14** (`seniors` 8, singular `Senior` 2, `juniors` 0, singular `Junior`
4) -- shortfall 16. `season` is absent on all 14 (opponent/search payloads carry no
`team_season`), so coach's requested season stratification is unavailable here at any
sample size. **The bare-token falsifier CANNOT BE RUN; that is not the same as "ran
clean," and a 14-name zero must not be cited as though it were a 40-name zero.**

## AC-9 / TN-5 trigger-set counts (derived 2026-07-26 for PM2)

**Cite THIS section for AC-9, not the 22-name breakdown above.** The breakdown answers a
different question with a different tier set, and transplanting its figure across the
definitional boundary is the F10 defect repeated.

TN-5's sets: Legion-family = {`legion`, `american legion`, `post \d+`, `\bseniors\b`,
`\bjuniors\b`}; tier = {`\bvarsity\b`, `\bjv\b`|`junior varsity`, `\bfreshman\b`|`\bfrosh\b`,
`\breserves?\b`, `\bsophomore\b`}. **Under these sets `seniors` is a Legion-family token,
NOT a tier word, and a `\d+U` bracket is NEITHER.** Denominator 563.

| quantity | count |
|---|---|
| names carrying >=1 TN-5 Legion-family token | 27 |
| **Q1 -- Legion-family token AND NO tier word (the AC-9 over-broad figure)** | **22** |
| **Q2 -- Legion-family token AND >=1 tier word (what the flag SHOULD fire on)** | **5** |

Q1 composition: 17 hard-token names without a tier word + 5 soft-`seniors`-only names.
Q2 is entirely Legion+`reserve(s)`: `legion` x3, `legion`+`post N` x1, `post N` x1.

**TN-5's existing figure of 5 is CORRECT and does not undercount.** The specific worry --
that a soft-`seniors` name might also carry `reserve`/`freshman`/`sophomore` -- is
**0 of 5**; no soft-only name carries any tier word.

### ⚠ THE THIRD NUMERIC COINCIDENCE IN THIS FILE -- two different 22s

**`22` now denotes two different sets of the same size, and they are NOT the same names:**

- **22 (a)** = names carrying a HARD Legion token (`legion`|`american legion`|`post N`).
  The denominator of the level-word breakdown above.
- **22 (b)** = Q1 above: any TN-5 Legion-family token, no tier word. The AC-9 figure.

They share only **17** members. 22(a) *includes* the 5 Legion+`reserve` names that 22(b)
excludes; 22(b) *includes* the 5 soft-`seniors`-only names that 22(a) excludes. Equal size
by arithmetic accident (27 - 5 = 22, and separately 22 hard-token names). **Never
substitute one for the other, and always say which one is meant.** This is the third such
collision here -- two 14s (now dissolved) and now two 22s -- so in this material **a
matching count is not evidence that two figures are the same quantity.**

## Method note for a re-run

Scripts are ephemeral (scratchpad). The harvest is ~2 min over 254 MB. Read from the MAIN
checkout (`/workspaces/baseball-crawl/proxy/data/sessions`) -- worktrees have an empty
`proxy/data/`. Emit counts and shapes only; the corpus is raw real names.

Related: [[public-team-age-group-level-field]], [[search-endpoint-notes]],
[[docs-api-pii-corpus]].
