# E-280-06 — trigger-phrase worklist (AC-3 pre-registration)

**Written and reported BEFORE the first edit**, per the story's Technical Approach. AC-3 is checkable
only against a pre-change enumeration; reconstructing it from the diff afterwards is the failure
mode this repo's 8-of-8 author-detection record predicts. Review base:
`a4aac1b3628a8f62f48ef0e22209766482325fab`.

**Extracted mechanically, not by eye** — a script parses `CLAUDE.md`'s `## Workflows` section, splits
on bullets, and pulls every double-quoted span. **The extraction deliberately over-matches**: under-match
is silent, over-match is visible, and every over-matched span gets a resolution below.

---

## Pre-change measurements

| Measure | Value | Method |
|---|---|---|
| `CLAUDE.md` bytes (**AC-6 before**) | **22,157** | `wc -c < CLAUDE.md` |
| `CLAUDE.md` lines | 168 | `wc -l` |
| `.claude/skills` lines (**AC-5 before**) | **3,413** | `cat .claude/skills/*/SKILL.md \| wc -l` |
| SKILL.md files | 10 | `ls .claude/skills/*/SKILL.md` |
| Files with YAML frontmatter | **0** | `head -1` is `---` in zero files |
| Files with `## Activation Triggers` | **10** | `grep -c '^## Activation Triggers'` |
| Activation Triggers **body** lines | **133** | awk between `## Activation Triggers` and the next `## ` |

The 133 figure reproduces the story's Context claim exactly. Zero-of-ten frontmatter confirmed
independently here, making a third confirmation after PM's and the design owner's.

## The seven-bullets / six-skills arithmetic, re-checked against the file

The story warns an earlier draft got this wrong **in both halves** and says to re-check rather than
trust either version. Re-checked:

**7 bullets. 6 name a skill. 1 names none** — *Curate the vision* invokes the product-manager in
curate mode. So the section covers **6 of 10** skills. The story's current statement is correct.

**The four skills with NO Workflows bullet** — `agent-standards`, `context-fundamentals`,
`filesystem-context`, `multi-agent-patterns` — are why **AC-3 is silently vacuous for 40% of the
work**, and why AC-8's countable 10-and-0 exists. Their descriptions must derive from their in-body
triggers, not from CLAUDE.md.

---

## The 35 quoted spans, classified and pre-assigned

**Class T = trigger phrase** (user says it, skill loads) · **M = modifier** (alters an existing
trigger's behavior) · **S = path selector** (describes branch selection inside a bullet, not a
phrase a user utters as a trigger).

All three classes must survive somewhere; the class determines *where*, and AC-7's two permitted
locations are a frontmatter `description` or the CLAUDE.md Workflows pointer.

### Plan → `.claude/skills/plan/SKILL.md`
| # | Phrase | Class | Planned post-change location |
|---|---|---|---|
| 1 | `plan an epic for X` | T | plan frontmatter `description` |
| 2 | `plan E-NNN` | T | plan frontmatter |
| 3 | `create an epic for X` | T | plan frontmatter |
| 4 | `write stories for X` | T | plan frontmatter |
| 5 | `let's plan X` | T | plan frontmatter |
| 6 | `design an epic for X` | T | plan frontmatter |
| 7 | `plan and dispatch` | **M** | plan frontmatter (compound modifier chaining into implement) |

### Implement → `.claude/skills/implement/SKILL.md`
| # | Phrase | Class | Planned post-change location |
|---|---|---|---|
| 8 | `implement E-NNN` | T | implement frontmatter |
| 9 | `start epic` | T | implement frontmatter |
| 10 | `execute E-NNN` | T | implement frontmatter |
| 11 | `dispatch E-NNN` | T | implement frontmatter |
| 12 | `kick off E-NNN` | T | implement frontmatter |
| 13 | `and review` | **M** | implement frontmatter (chaining modifier) |

### Ingest endpoint → `.claude/skills/ingest-endpoint/SKILL.md`
| # | Phrase | Class | Planned post-change location |
|---|---|---|---|
| 14 | `ingest endpoint` | T | ingest-endpoint frontmatter |
| 15 | `curl is ready` | T | ingest-endpoint frontmatter |
| 16 | `new endpoint to analyze` | T | ingest-endpoint frontmatter |

### Spec review → `.claude/skills/codex-spec-review/SKILL.md`
| # | Phrase | Class | Planned post-change location |
|---|---|---|---|
| 17 | `spec review` | T | codex-spec-review frontmatter |
| 18 | `spec review E-NNN` | T | codex-spec-review frontmatter |
| 19 | `codex spec review` | T | codex-spec-review frontmatter |
| 20 | `spec review prompt` | T | codex-spec-review frontmatter |
| 21 | `codex spec review prompt` | T | codex-spec-review frontmatter |
| 22 | `prompt` | **S** | codex-spec-review frontmatter — the path selector, kept as the rule *"a trigger containing `prompt` selects the prompt-generation path"* |

### Code review → `.claude/skills/codex-review/SKILL.md`
| # | Phrase | Class | Planned post-change location |
|---|---|---|---|
| 23 | `codex review` | T | codex-review frontmatter |
| 24 | `review with codex` | T | codex-review frontmatter |
| 25 | `code review` | T | codex-review frontmatter |
| 26 | `review epic` | T | codex-review frontmatter |
| 27 | `codex review prompt` | T | codex-review frontmatter |
| 28 | `code review prompt` | T | codex-review frontmatter |
| 29 | `post-dev review` | T | codex-review frontmatter |
| 30 | `prompt` | **S** | codex-review frontmatter — same path-selector rule |

### Curate the vision → **NO SKILL**
| # | Phrase | Class | Planned post-change location |
|---|---|---|---|
| 31 | `curate the vision` | T | **CLAUDE.md Workflows pointer — the ONLY permitted location.** There is no skill file to carry it, so this is the phrase AC-7's second branch exists for. **It must NOT be deleted from CLAUDE.md**, and it is the single strongest reason the Workflows section cannot be reduced to a bare pointer with no content. |

### Workflow help → `.claude/skills/workflow-help/SKILL.md`
| # | Phrase | Class | Planned post-change location |
|---|---|---|---|
| 32 | `/workflow-help` | T | workflow-help frontmatter |
| 33 | `what commands do I have` | T | workflow-help frontmatter |
| 34 | `show me the workflows` | T | workflow-help frontmatter |
| 35 | `cheat sheet` | T | workflow-help frontmatter |

**35 spans: 31 T, 2 M, 2 S.** Every one has exactly one planned location, which is what AC-3
requires — a phrase in zero locations and a phrase in two are both RED.

---

## The one phrase that constrains the whole design

**`curate the vision` has no skill file.** Any design that empties CLAUDE.md's Workflows section
entirely loses it, taking AC-3 and AC-7 RED together. The section therefore becomes a **pointer plus
the one non-skill workflow**, not a bare pointer.

---

# POST-CHANGE RESULTS

## AC-3 verdict — 33 of 33 in exactly one location

Verified by script against the post-change tree: **0 spans in zero locations, 0 spans in two or
more**, with a negative control confirming the checker discriminates. Two spans of the original 35
(`prompt`, counted twice) are path selectors folded into their skills' descriptions as the
branch rule, so the checked set is 33 distinct strings.

**Six spans initially resolved to two or three locations, and none was a duplicate declaration.**
Each extra occurrence was a *discriminator* (`codex-review` naming the spec-review case to route it
away, and vice versa) or a *routing-away list* (`plan`'s "NOT this skill"). Removing them would
satisfy AC-3 while making routing worse — the "spec" discriminator exists precisely because these
two skills are confusable.

**Resolved by expressing cross-references as RULES rather than by quoting the other skill's
phrases**: *"a review request that LACKS the word spec belongs to the codex-review skill"* instead of
quoting `"codex review"`. This satisfies AC-3's literal test **and** keeps the disambiguation — the
option that required arguing the AC into a looser reading was declined.

One further collision was `plan`'s workflow summary saying *"automatic spec review"* — a description
of a workflow phase, not a trigger declaration. Reworded to "specification review".

## ⚠️ AC-3 scope divergence — reported, not papered over

**The `workflow-help` cheat sheet contains trigger phrases** (`"plan E-NNN"`, `"implement E-NNN"`,
`"spec review E-NNN"`, `"codex review E-NNN"`, `"ingest endpoint"`, `"curate the vision"`). My AC-3
checker did **not** include it — it checked CLAUDE.md's Workflows section and the ten descriptions.

**Under AC-3's literal wording that is a second location for six spans.** Under the design it is not
a *source*: the cheat sheet is a **rendering** whose entire function is to display those phrases to
the user, and its own Maintenance section already deferred to the skill files as authoritative.

**Not silently resolved.** The Maintenance section is updated to say explicitly that the cheat sheet
is a rendering of the single source and must be re-derived from the frontmatter descriptions rather
than edited independently, and its "Vision curation" pointer — which named the PM agent definition —
now correctly names CLAUDE.md's Workflows section, the only place that phrase lives. **PM should rule
whether a rendering counts as a location for AC-3.** If it does, the remedy is a cheat sheet that
prints phrase *categories* rather than literals, which costs the user real utility.

## AC-4 — per-file verdict on every in-body `## Activation Triggers` section

**10 files, 10 verdicts, 0 retained.**

| Skill | Verdict |
|---|---|
| `agent-standards` | **REMOVED** — content became the `description` |
| `context-fundamentals` | **REMOVED** — content became the `description` |
| `filesystem-context` | **REMOVED** — content became the `description` |
| `multi-agent-patterns` | **REMOVED** — content became the `description` |
| `ingest-endpoint` | **REMOVED** — phrases to `description`; the time-sensitivity note preserved there |
| `workflow-help` | **REMOVED** — phrases to `description` |
| `codex-spec-review` | **REMOVED** — phrases to `description`; **the "spec" mode discriminator preserved**, re-expressed as a rule |
| `codex-review` | **REMOVED** — phrases to `description`; **the absence-of-"spec" discriminator preserved**, re-expressed as a rule |
| `plan` | **REMOVED, but NOT wholesale** — the section also set `compound_dispatch = true` for Phase 5 handoff. That is operational state the workflow reads later, so it survives under a new `## Compound Dispatch Flag` heading. The non-trigger routing list moved into the `description` as rules. |
| `implement` | **REMOVED, but NOT wholesale** — the section also carried the **Chaining modifier** paragraph (including the load-bearing note that Step 1c is unconditional) and the **Plan skill handoff** paragraph setting `handoff_from_plan = true`, both cross-referenced from Phases 1, 2, 4 and 5. Both survive under a new `## Modifiers and Handoff` heading. |

**The last two are the AC-5c shape from story 02**: deleting a block wholesale because most of it is
triggers is how the non-trigger minority gets lost. Two of ten sections contained operational state
assignments that nothing else sets.

## AC-9 — review-surface sites in the two owned skills, regenerated by search

| # | File / site | Verdict |
|---|---|---|
| 1 | `plan/SKILL.md` — CR role-transition block, *"(unstaged changes = current story)"* | **CHANGED** — a verbatim instance of the exact retired phrase; now the frozen-tree pair, matching `implement/SKILL.md`'s post-E-280-02 wording |
| 2 | `plan/SKILL.md` — same block, `git diff --cached main` | **CHANGED** — **bare `main` in a worktree context**, the E-278 phantom-finding hazard; now the merge base |
| 3 | `plan/SKILL.md` — Step 2a planning-commit staging (`git add`, `git diff --cached --stat`, unstage/inspect options) | **`no change needed`** — the **main checkout** at planning time, an unrelated and correct use of staging |
| 4 | `codex-review/SKILL.md` — WORKDIR path, `git -C <epic-worktree-path> diff main` | **CHANGED — NOT IN THE AC's FLOOR.** Bare `main` as a diff base *inside the epic worktree*; now the merge base, with the E-278 reason stated |
| 5 | `codex-review/SKILL.md` — "Standalone invocation (no epic worktree)" staged/unstaged/untracked triple | **`no change needed`** — the standalone path is a user reviewing local changes **outside dispatch**; it never equates unstaged with "the current story" |
| 6 | `codex-review/SKILL.md` — the assembled `--- Staged changes --- / --- Unstaged changes ---` template | **`no change needed`** — output format of site 5, same reason |
| 7 | `codex-review/SKILL.md` — *"standalone (non-WORKDIR) staged/unstaged path"* in the large-refactor guidance | **`no change needed`** — an accurate reference to site 5's path, naming it correctly as the non-WORKDIR case |

**7 sites, 3 changed, 4 `no change needed`.** `grep -c "current story"` in `codex-review/SKILL.md`
returns **0** — the AC's floor named its staged/unstaged template as a site, but on reading, that
template is the standalone path and is a correct use. **The real defect in that file was one the
floor did not name: a bare `main` diff base in the epic-worktree path** — the identical shape as
E-280-04's AC-15 site 2, and the second time a floor pointed at correct text while the actual defect
sat one paragraph away.
