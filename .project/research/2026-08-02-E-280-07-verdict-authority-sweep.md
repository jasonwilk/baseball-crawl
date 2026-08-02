# E-280-07 — regenerated verdict-authority sweep and the layer-wide verification

Deliverable for AC-2 (regenerated sweep, superset of TN-11's floor, verdict per site) and AC-1c
(layer-wide verification with a positive control). Review base: `3d2274cead16c460108ac6f680b4927b9c1ec0df`.

---

## AC-1c — the layer-wide check, and why its zero is interpretable

**This is the one AC in the epic where a false clean is more likely than a false finding**, because
**zero is what success looks like**. A sweep returning zero *because it looked with the wrong
instrument* is indistinguishable from one that verified absence — and nothing downstream catches it,
since E-280-08's terminal verifications read this story's output rather than the layer.

### ⚰ ROUND 1's SWEEP WAS REFUTED — do not reproduce it

⚰ **RETIRED, do not run:** ~~a three-alternative invocation over `unstaged changes = current story`,
`unstaged = (current|this) story`, `changes are **unstaged**`, with control `frozen tree` = 34,
concluding "AC-1c PASSES."~~

**That sweep returned a false clean and code-reviewer refuted it.** All three alternatives are
**token** forms. The invariant also survives in a **consequence** form that shares none of its
tokens, and **this very artifact had already proved that** — the AC-2 section below records the two
`dispatch-pattern.md` sites as carrying *"neither `unstaged` nor `current story`"*. **The
verification then ran a token sweep anyway.** The zero was true of the tokens and false of the
invariant.

**Two occurrences survived it**, both found by CR: `.claude/skills/multi-agent-patterns/SKILL.md:50`
and `.claude/agents/product-manager.md:123`, each carrying *"the staging boundary (`git add -A` after
each story passes review)"*. Both are false on both clauses — the freeze stages on the completion
report, and the frozen tree is what isolates. **`product-manager.md` was telling PM the wrong
ordering in PM's own definition.** Both are now fixed.

### The rebuilt instrument — what it matches, and what it does not

⚠️ **READ THE LABEL BEFORE THE RESULT. This pattern is NOT class-capable, and an earlier version of
this section claimed it was.** It matches **the three token forms plus the two consequence literals
that were actually OBSERVED in the two survivors** — nothing more. **No finite pattern is
class-capable for a prose class**, so widening it only moves the line. Under `doc-sweep.md` this is
**steps 1 and 2**; the CLASS is reachable only by **step 3, the semantic read**. Do not inherit this
invocation as a class check.

**Token forms AND the two observed consequence literals AND a known-present control, one invocation.**

```
grep -rnoiE "unstaged changes = current story|unstaged = (current|this) story|changes are \*\*unstaged\*\*|after each story passes review|staging boundary protocol|frozen tree" \
     CLAUDE.md .claude/rules/ .claude/skills/ .claude/agents/
```

| Alternative | Hits |
|---|---|
| token forms (×3) | **0** |
| **consequence forms** — `after each story passes review`, `staging boundary protocol` | **0** |
| **`frozen tree` (POSITIVE CONTROL)** | **36** |

An independent second pattern over the same class with different wording
(`staging boundary…isolat`, `isolat…staging boundary`, `` add -A` after ``): **zero**.

### The NEGATIVE control — and round 2's failure, which was the same shape one level down

**The three-member rule. The third line is what makes the pair usable rather than performable, and
it is the one round 2 lacked:**

- A **positive** control proves the pattern **RAN**.
- A **negative** control proves the pattern can **SEE** — **only if the seed was written
  independently of the pattern.**
- **A seed drawn from the pattern's own alternatives tests NOTHING. Write the seed from the CLASS,
  before or without reference to the regex — ideally by a different party.** It is cheap: CR's seed
  took one sentence.

⚰ **RETIRED, do not cite:** ~~a negative control reporting the round-1 token pattern `0 — BLIND` and
the rebuilt pattern `1 — CATCHES`, concluding the rebuilt pattern can see the class.~~ **My seed was
drawn from the two consequence literals the pattern was written from, so it was guaranteed to match.
It proved the pattern matches its own literals — not that it has any reach.** That is this
artifact's own positive/negative distinction one level down, and it is round 1's failure shape
iterated rather than fixed.

**The valid negative control is code-reviewer's, seeded independently — a sentence written from the
class, by a different party, without reference to my regex:**

> *"The main session stages each story after review passes, and that boundary isolates per-story
> changes."*

| Pattern | Result on CR's independent seed |
|---|---|
| my "class-capable" pattern | **0 — BLIND** |
| CR's independently worded consequence pattern | **1 — CATCHES** |

**So the instrument of record does NOT see the class**, and the label above says so.

### What AC-1c's result actually rests on, and its residual

**AC-1c PASSES** — the claim about the layer is true, and code-reviewer confirmed it independently
(0 token / 0 consequence across 199 `.md` files in all four trees, control `frozen tree` firing in
7 files). But the basis is worth stating exactly, because **E-280-08 inherits this artifact**:

- **Layer-wide, steps 1+2 only**: verified absence of the three token forms and the two observed
  consequence literals. Positive control fired, so the pattern form, path set and tool resolved.
- **Step 3, the semantic read, covers the three OWNED files** — the AC-2 table below resolves all 14
  sites by reading, and the surviving-`unstaged` table resolves every match by reading rather than
  by the match.
- ⚠️ **RESIDUAL, unclosed by anything here**: a consequence-form instance in a file nobody read,
  sharing none of the five literals, would survive both passes. No instrument in this story closes
  that, and no wider regex would. **08 should treat layer-wide semantic coverage as NOT
  established** rather than reading this section's zero as a class-level clean.

⚠️ **A third failure in round 1, recorded because the AC names it.** My first combined invocation used
a control string of `POSITIVECONTROL_frozen tree`, which matches nothing — **a control that also
returns zero, which proves the instrument rather than the absence, and is itself the finding.**
Caught on re-read and re-run with a real control. **So round 1 produced AC-1c's second RED and then
its first: a control that could not fire, then a pattern that could not see.**

**Every surviving `unstaged` in the four trees, resolved by reading rather than by the match:**

| Site | Verdict |
|---|---|
| `implement/SKILL.md` Step 8 clean-tree preflight (×2 lines) | **`no change needed`** — main checkout at closure, a correct unrelated use. Named in AC-1c. |
| `implement/SKILL.md` "Why freeze before reviewing rather than stage after" | **`no change needed`** — describes the retired practice as a hazard; not a definition of the review surface |
| `implement/SKILL.md` "`git diff` does not see untracked files at all" | **`no change needed`** — about the check's own commands |
| `worktree-isolation.md` `git checkout --` prohibition | **CHANGED per AC-6** — prohibition preserved, reasoning updated |
| `codex-review/SKILL.md` ×4 (standalone invocation path) | **`no change needed`** — the standalone no-worktree path; ruled in E-280-06 |

---

## AC-2 — regenerated sweep across the three owned files

Regenerated by search, not read off TN-11. **TN-11 is a floor for FINDING sites, never a list of
sites to change** — under OQ-5 most entries resolve to `no change needed`, and that is a **successful
sweep, not a wasted one**.

| # | Site | TN-11? | Verdict |
|---|---|---|---|
| 1 | `dispatch-pattern.md` — main-session role ¶, *"manages the staging boundary between stories (`git add -A` after each story passes review)"* | — | **CHANGED** — carried the **retired ORDERING**; see the doc-sweep note below |
| 2 | `dispatch-pattern.md` — Team Roles item 1, same retired ordering | **TN-11 (item 2)** | **CHANGED** — same |
| 3 | `dispatch-pattern.md` — Team Roles item 4, *"(unstaged = current story)"* | **TN-11 (item 4)** | **CHANGED** — the only literal instance of the retired invariant left in the layer; now the frozen tree |
| 4 | `dispatch-pattern.md` — *"Both PM and code-reviewer must approve before the staging boundary advances"* | **TN-11** | **`no change needed`** — TRUE under one-of-each; **AC-1b REDs on deleting it** |
| 5 | `dispatch-pattern.md` — *"PM is authoritative on ACs"* | **TN-11** | **`no change needed`** — same; the operator ruled *"pm owns acceptance"* |
| 6 | `dispatch-pattern.md` — permitted-orchestration bullet, `git add -A` staging boundary | — | **CHANGED** — freeze-first wording |
| 7 | `dispatch-pattern.md` — *"Effect in the artifact is a receipt"* ¶ | — | **CHANGED per AC-4** — reduced to mechanism + bound; **the ⚠ bound kept in force as its own paragraph**, not a parenthetical |
| 8 | `dispatch-pattern.md` — closure merge sequence, merge-base warnings | — | **`no change needed`** — depends on `main` moving during an epic, which the freeze does not touch. Checked rather than assumed, per the Technical Approach. |
| 9 | `worktree-isolation.md` — Purpose, *"the staging boundary protocol (`git add -A` after each story passes review) isolates per-story changes"* | — | **CHANGED per AC-5** — the frozen tree is what isolates |
| 10 | `worktree-isolation.md` — "Who works here", staging boundary | — | **CHANGED** — names the freeze |
| 11 | `worktree-isolation.md` — `git checkout --` prohibition | — | **CHANGED per AC-6** — prohibition **preserved**, reasoning updated (below) |
| 12 | `worktree-isolation.md` — own-memory deliverables ¶, "bypasses the per-story staging boundary" | — | **`no change needed`** — the boundary still exists and is still bypassed by a main-checkout write; the freeze changes *when* it is established, not that it exists |
| 13 | `workflow-discipline.md` — PM's dispatch-time AC role | **TN-11** | **`no change needed`** — the clearest expected instance under OQ-5, exactly as the AC predicted |
| 14 | `workflow-discipline.md` — Context-Layer Assessment Gate, *"all eight triggers"* | — | **CHANGED per AC-8** — no numeric count survives |

**14 sites: 9 changed, 5 `no change needed`.** All five TN-11 entries appear; **three of five resolve
to `no change needed`**, which is the OQ-5 shape and evidence the sweep read the ruling rather than
the superseded floor.

### Doc-sweep step 2 — the judgement that depended on the invariant and shared none of its tokens

Sites 1 and 2 are the payoff. Both said **`git add -A` after each story passes review** — the
**retired ORDERING**, carrying neither `unstaged` nor `current story`. A token sweep for the
invariant returns zero on both. They survived because they encode a *consequence* of the invariant
rather than the invariant itself, which is precisely what `doc-sweep.md` warns about: *a retired
claim survives as a rating, a risk adjective, or a summary line sharing none of its tokens.*

**The merge-base warnings were checked rather than assumed** (site 8) and are **not** in this class:
they exist because `main` moves while an epic runs, which the freeze does not affect.

---

## AC-6 — the prohibition survives; its reasoning is now the freeze

The `git checkout --` / `checkout-index` / `restore` prohibition is **unchanged in force**. Its
stated reason was stale: it said the index holds *the PREVIOUS story's state*, which was true when
staging happened after review.

Updated: the index now holds **the last FROZEN state** — prior stories plus this story as it stood
when frozen — so an index restore **destroys whatever was written since that freeze**, which is
exactly the remediation work in flight when someone reaches for a revert. **The mechanism changed and
the prohibition did not**; before, a restore destroyed the whole story, now it destroys the round.
Both silent, neither recoverable from git.

---

## AC-3 — one answer, everywhere

Every verdict-authority site across all four trees states the same thing, re-derived from
`implement/SKILL.md` **as it stands now** (post-E-280-09, not post-E-280-02 — that file has been
edited by 06 and 09 since):

**PM issues the AC verdict; code-reviewer issues the review verdict; each exactly once per frozen
state; neither re-askable about a tree already ruled on.**

Sites confirmed in agreement: `dispatch-pattern.md` (×2), `code-reviewer.md`, `product-manager.md`,
`implement/SKILL.md` (×3). **No instruction pair in tension.**

## AC-7 — the residual floor is intact

No edit reduces what a single verdict must establish. Every change bounds **how many times** a
verdict is issued or restates the mechanism it is issued against. The per-claim verification
discipline is untouched, and AC-4's bound — the half that keeps the artifact-effect technique honest
— was strengthened rather than trimmed.
