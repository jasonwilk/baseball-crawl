# E-280-04 — per-file verdicts and the review-surface sweep

Deliverable artifacts for E-280-04 (AC-2, AC-15). Review base: tree
`cd1c4cd44c3509dbc15833e52ed2b6be46ee4eb5` (E-280-02's approved tree).

---

## AC-2 — every agent file, with a written verdict

**9 files, 9 verdicts.** The 6-adapter / 3-Sonnet split was **verified against the files**, not taken
from the story, per its Technical Approach. It matches: adapters on `api-scout`,
`claude-architect`, `code-reviewer`, `data-engineer`, `product-manager`, `software-engineer`;
Sonnet-pinned `baseball-coach`, `docs-writer`, `ux-designer`.

| Agent | Model | Schema before | Verdict |
|---|---|---|---|
| `software-engineer` | `opus[1m]` | none | **schema ADDED** + ceiling. Files Changed / Test Results / Behavioral Changes |
| `data-engineer` | `opus[1m]` | none | **schema ADDED** + ceiling. Same three sections; schema changes named as behavioral |
| `api-scout` | `opus` | none | **schema ADDED** + ceiling. Adds `## Endpoints Touched`; explicit no-credentials rule |
| `claude-architect` | `opus[1m]` | none | **schema ADDED** + ceiling. Consultation variant (`## Recommendation` / `## Reasoning`) |
| `product-manager` | `opus[1m]` | none | **schema ADDED** + ceiling. `## Status Changes` / `## AC Verdict` / `## Blockers`; AC verdict named un-trimmable |
| `docs-writer` | `sonnet` | none | **schema ADDED** + ceiling (AC-3). States plainly that doc pages are uncapped |
| `ux-designer` | `sonnet` | none | **schema ADDED** + ceiling (AC-3). Design artifacts uncapped; over-ceiling → artifact + path |
| `baseball-coach` | `sonnet` | none | **schema ADDED** + ceiling (AC-3). Sample-size caveat named un-trimmable |
| `code-reviewer` | `opus[1m]` | **`## Structured Findings Format` — already had one** | **schema RETAINED, unchanged in shape**; scope statement added; **ceiling deliberately NOT applied** (AC-18) |

`baseball-coach`'s existing `## Output Standards` was examined and is **not** a report schema — it
governs the *substance* of recommendations (specificity, prioritization, sample size), not the shape
of the message. The new schema references it rather than duplicating it.

---

## AC-16 / AC-17 — the ceiling, and its honest provenance

**6,000 characters (~1,500 tokens), labelled an ESTIMATE in every file that carries it.**

Checked against TN-19's measured tables:

| Role | measured p50 | under the 6,000 ceiling? |
|---|---|---|
| main | 2,990 | yes |
| product-manager | 3,063 | yes |
| claude-architect | 3,291 | yes |
| code-reviewer | 4,013 | *excluded from the ceiling* |
| **all roles** | **3,080** | yes |
| **measured max** | **13,882** | ceiling sits well below it |

**AC-16 both-sided check**: 6,000 is **above every covered role's p50** (highest covered = 3,291), so
it does not bind normal traffic; and **below the measured max of 13,882**, so it binds something. It
would have caught `claude-architect`'s 11,911 outlier and `code-reviewer`'s 13,882 — the latter now
excluded by AC-18.

**AC-17**: every ceiling states *"an ESTIMATE, not a measured threshold"* and *"no report-length
regression was measured"*, with the TN-19 finding named: E-279's payloads sit inside the
peak-Opus-4.8-era range and below that era's heaviest session on every statistic. **The figure is
not presented as measured or as derived from the wall-clock analyses.** The 2x verbosity finding is
per-**turn** and does not transfer to reports.

**On restatement (TN-7).** The ceiling paragraph appears in 8 files. This is not the restatement
defect: an agent loads only its own definition, so a ceiling stated in another agent's file cannot
reach it. Per-file statement is *necessary*, not duplicative. What is single-sourced is the
derivation — it lives in TN-19 and here, not in eight copies.

---

## AC-18 — code-reviewer's exclusion, with an evaluable reason

The exclusion is stated **in `code-reviewer.md` itself**, with the reason a later editor can assess:
CR pins `claude-opus-5`; the vendor documents that this model may follow a conservatism instruction
literally and report *less*, its remedy being to *"ask it to report everything and filter in a
separate pass instead"*; **a length ceiling is a conservatism instruction wearing different
clothes**; and CR's length is structurally driven by finding count, making it the most tempting
target and the one where truncation costs most. **Code-reviewer still has a schema** — only the
ceiling is withheld.

---

## AC-8 / AC-9 — tier keying

The **tier-to-rubric mapping is authored in `code-reviewer.md`** (`### Review depth by tier`), and it
names **no path classes** — path classification stays in the routing seam. Mapping:

| Tier | Priorities applied |
|---|---|
| A | all seven (1–7) |
| B | **1, 3, 4, 6, 7** + prose-claim resolution; **only 2 and 5 skipped** as executable-behavior checks |
| C | no *per-story* CR pass; tier C content still reaches CR at the unconditional Step 1c closure review |

**AC-9**: all seven priorities appear in tier A, so no priority is orphaned. Escalation is one-way
and must be stated; de-escalation prohibited.

### ⚠️ Corrected in review: tier B originally skipped Priority 4, which deleted the only PII review from the only trees tier B covers

My first mapping skipped **2, 4 and 5** with one rationale: *"they target executable behavior, and a
tier B diff changes none."* **True of 2 and 5. False of 4** — a correct conclusion for two of three
members, which is why the sentence read cleanly.

Priority 4's sensitive-path trigger requires, verbatim: *"**PII across ALL artifact types** -- not
just source and logs, but also test fixtures, cached API responses, generated reports, error
messages, and **committed docs**."* That is a **content** check. **Tier B is the only tier that
reviews `docs/`.**

And nothing backstops it. `.claude/rules/pii-safety.md` (verified first-hand, line 50): the
pre-commit scanner **cannot regex-detect NAMES** — credentials/email/phone only — and the doc-PII
byte-gate is **scoped to `docs/api/` alone**. So for `docs/admin/` and `docs/coaching/`, the trees
docs-writer owns, **neither automated gate reaches a name, and under my original mapping the reviewer
no longer looked either.** The remedy is splitting the rationale, not widening the tier: 2 and 5 stay
skipped for the reason given; 4 is retained on the reason that actually applies to it.

**Knock-on recorded for E-280-06** — see the AC-8 note above. With Priority 4 retained, the seam
clause *"skipping rubric priorities 2, 4 and 5"* is now **wrong as well as misplaced**. **06's remedy
must DELETE the clause, not transcribe a corrected version of it** — otherwise the story that exists
to stop the seam restating rubric content would faithfully restate a stale list.

⚠️ **AC-8's first RED limb is NOT satisfied, and the site is outside this story's Files list.**
AC-8 REDs on *"the routing seam restating rubric content"*. `implement/SKILL.md`'s tier table
currently says tier B is *"Code-reviewer ACs + prose-claim resolution, skipping rubric priorities 2,
4 and 5"* — naming rubric priorities in the seam. **I authored that line in E-280-02 and cannot
reach the file from this story.** Reported rather than fixed. The remedy is one clause: the seam
should say only *"tier B depth per `code-reviewer.md`"*. **E-280-06 owns the next edit to that
file.** I have matched the mapping to the seam's current wording so the two agree in substance while
the duplication stands.

---

## AC-15 — review-surface invariant in `code-reviewer.md`, every site with a verdict

Regenerated by search (`unstaged|staged|staging boundary|git diff|untracked|uncommitted`), not read
off the story's floor of four.

| # | Site | Verdict |
|---|---|---|
| 1 | Step 1 untracked-file warning — *"the review loop is structurally BLIND to an UNTRACKED file"* | **RECONCILED, not deleted.** The freeze **cures** the blindness: `git add -A` captures untracked files, so they now enter the review surface. **The E-276 instance is preserved verbatim as evidence of what was observed**; only the still-blind framing changed. A residual `git status` use is retained for a *different* failure — a write landing after the freeze. |
| 2 | Deploy-time safety — *"in the current unstaged diff"* **and** `git diff --cached main` | **CHANGED.** Rewritten to the frozen tree, which contains prior stories' and this story's migrations by construction. **This site carried two defects, and the second was not in AC-15's floor: a bare `main` diff base in a worktree context** — the E-278 phantom-finding hazard. |
| 3 | Worktree Review intro — *"the staging boundary protocol isolates per-story changes"* | **CHANGED** → the frozen tree is what isolates per-story changes |
| 4 | *"The current story's changes are **unstaged**… Prior stories' changes are staged."* | **CHANGED** → frozen-tree framing with two tree SHAs |
| 5 | The `git diff` command directly beneath site 4 | **CHANGED** → `git diff <previous-tree-sha> <this-tree-sha>`, with the merge-base fallback for the epic's first story |
| 6 | *"all accumulated changes"* + `git diff main` | **CHANGED** → `git diff --cached $(git merge-base epic/E-NNN main)`, labelled the whole-epic closure view and explicitly **not** a per-story surface; bare-`main` warning added |
| 7 | Test Execution Constraint — *"the worktree's own uncommitted `src/`"* | **`no change needed`.** "Uncommitted" remains accurate under the freeze — staged is still uncommitted — and the claim is about pytest's `sys.path` resolution, not about staging state. |
| 8 | Anti-pattern 5 listing `git diff` as a permitted read-only command | **`no change needed`.** About which Bash commands are permitted, not about what the review surface is. |
| 9 | Step 1d trigger read `git diff --cached --stat $(git merge-base …)` | **`no change needed`.** Already merge-based; it is the closure cumulative view, which is the correct surface there. |

**9 sites, 6 changed, 3 `no change needed`.** The story's floor named four; the regenerated sweep
found nine. Site 2 is the one the floor's wording would not have led me to — AC-15 places *"in the
current unstaged diff"* as its own item, but on disk that clause lives **inside the Deploy-time
safety paragraph**, alongside a second defect the AC did not name.

A **new verdict-economy paragraph** was added at site 4/5: the reviewer's verdict is issued once
against the frozen tree and is not re-askable; a moved tree is the main session's to re-freeze, and
remediation yields a new tree, which is a first verdict on a different artifact.

---

## AC-5 — the one exhortation the sweep surfaced, with its verdict

`grep -niE '"?(be concise|keep it brief|avoid verbosity)"?'` across all nine files returns **one
hit**: `docs-writer.md:101`, *"**Be concise.** Say what needs to be said, then stop. Coaches do not
want to read a textbook; Jason does not want to read filler."*

**Verdict: `no change needed`, and AC-5 is GREEN**, on two independent grounds — either alone is
sufficient:

1. **It is not the sole length control.** AC-5's RED is *"such a sentence present as the **sole**
   length control for that agent."* `docs-writer` now carries a schema and a 6,000-character
   ceiling, so the mechanism is structural; this line is no longer doing that work.
2. **It governs a different surface.** It sits in `## Documentation Standards`, among "Write for the
   audience" and "Use examples" — guidance on the **documentation** docs-writer produces, not on its
   `SendMessage` reports. The new schema states explicitly that doc pages are uncapped.

Recorded rather than silently passed over, because a grep hit on an AC's own banned phrase is
exactly the kind of thing a later reviewer re-finds and must re-adjudicate from scratch.

## AC-14 — trigger-count de-restatement

`product-manager.md`'s closure checklist read *"evaluate each of the **eight** triggers"*. Now
*"evaluate **every trigger in that file's numbered list**"*. No numeral or number-word quantifying
the triggers survives in that file.

---

## Finding: the story's Context carries a false count, and I acted on it before checking

The story's Context says *"The vendor line already in the **six** Opus 5 adapters governs written
documents on disk."* **It is in two** — `claude-architect` and `product-manager`. The other four
adapter sections (`api-scout`, `code-reviewer`, `data-engineer`, `software-engineer`) contain only
**Scope.** and **Verification.**

**AC-4 is unaffected and GREEN**: its RED is *"any diff hunk touching that line"*, and no diff line
adds or removes vendor-line text anywhere. AC-4's own wording — *"every **existing**"* — already
tolerates the line being absent.

**But I inherited the six-adapter premise and wrote it into four files before checking it.** My first
draft of the scope statement said *"The Model Adapter's written-document guidance below is a separate
surface"* in `software-engineer`, `data-engineer`, `api-scout` and `code-reviewer` — **a false claim
about each of those files**, since no such guidance exists in them. Caught when the verification grep
for the vendor line returned **2 where I expected 6**, and corrected: those four now state the scope
without referencing guidance that is not there. The two that do carry the line keep the reference,
where it is accurate and does the disambiguating work AC-4 exists to protect.

This is the inherited-claim shape: a premise arriving in a story's Context, restated into four files
before being resolved against the repo. **The unexpected count is what caught it** — not re-reading.
