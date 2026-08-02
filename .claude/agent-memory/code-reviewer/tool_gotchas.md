---
name: tool-gotchas
description: Measured tool behaviors that silently return the wrong answer. Each one produced a real miss or a real catch.
metadata:
  type: reference
---

- **`git checkout-index -a` honors skip-worktree bits by default.** The snapshot silently omits those
  entries. `--ignore-skip-worktree-bits` overrides. (E-256-14: a PII pre-commit gate certified
  `[doc-pii: REAL, 0 matches]` and committed the identifier.)
- **`include` in `pyproject.toml` filters directory walks, not explicitly-named paths.**
  `ruff check tests/` reports nothing; `ruff check tests/foo.py` reports its violations.
- **`files=$(git ls-files ...); ruff check $files` does not word-split** (one newline-joined arg).
  ruff warns `Failed to lint <megastring>` on **stderr**, lints nothing, and **exits 0**. Use
  `git ls-files -z ... | xargs -0`.
- **Every mid-epic baseline spelled as a REFERENCE moves under you; only a tree SHA does not.**
  `git show HEAD:<file>` was wrong because prior stories were staged, not committed — and the fix this
  entry used to give, `git show :<file>` (the index), is wrong for a *different* reason since E-280:
  the freeze (`git add -A && git write-tree` on every completion report) rewrites the index at every
  story and every remediation round, so `:` names a different blob each time you read it. **Read from
  the tree SHA in your review assignment: `git show <tree-sha>:<file>`, `git diff <prev-tree> <tree>`.**
  Generalize past git — this is CA's `tool-output-integrity.md` item 3, *name the OBJECT, not the
  POSITION*: a position is resolved when the reader arrives, so it names whatever is there then.
  **Note the shape of my own error here, because it is the one to watch for:** the entry's VERDICT
  (don't use `HEAD:`) stayed right while its REASON went stale, and any check asking "was the call
  right?" passes. A correct conclusion immunizes its false premise.
- **`fnmatch` has no `**` concept**: `fnmatch.translate("**/x")` and `translate("*/x")` are both
  `(?s:.*/x)\Z`, a regex *requiring* a slash, while Docker's `**` spans zero segments. So `fnmatch`
  over-matches on `*`-vs-`/` and **under**-matches on `**`. (E-256-06: a `.dockerignore` guard was
  blind to `**/src/`.)
- **`git diff --cached --name-only` C-quotes hostile paths, and `core.quotePath=false` only fixes
  *some* of them.** Measured with the flag ON: `a b.md` raw, `aé.md` raw, but `"a\"b.md"` and
  `"a\\b.md"` **still quoted** — `quotePath` governs non-ASCII bytes only, not `"`/`\`/control chars.
  A newline in a filename defeats line-delimited output entirely. **Only `-z` is complete:**
  `mapfile -d '' -t ARR < <(git diff --cached --name-only -z ...)`. (E-256-14: bypasses two, three,
  and four. I recommended `quotePath=false` because it was the form I had *tested*, and shipped a
  partial fix — preferring the measured half over the correct whole.)
- **`git diff`/`git diff --stat` cannot see untracked files.** A new file is byte-identical to an
  unchanged one there; use a content hash to assert a file is unchanged. **The base fact is permanent
  and still load-bearing** — at E-280's closure it was the whole of a SHOULD FIX: `codex-review`'s
  epic-mode gather is `git diff $(merge-base)`, so the external reviewer was structurally blind to the
  2 untracked files, one of which was the IDEA recording the epic's own known-open residual.
  **Two things about this entry were WRONG and are corrected 2026-08-02 (E-280):**
  - ⚰ **The per-story corollary is RETIRED.** It said a new-module story shows a `git diff` of only
    PM's status flips. The freeze cures that: `git add -A` precedes review, so untracked files are
    *in* the tree you are handed. Reviewing the assigned `git diff <prev-tree> <tree>` is not a
    false-clean any more.
  - ⚠️ **`git status --porcelain` was the prescribed instrument and it carries NO INFORMATION in a
    dispatch worktree.** It is structurally never empty there — PM's `epics/` status writes alone
    guarantee output (measured 8 lines, three separate times, at moments the review surface was
    genuinely clean). Treating its emptiness as a signal is vacuous. **Use the scoped form:**
    `git ls-files --others --exclude-standard -- <routed-paths>`, which is what THE FROZEN-STATE
    CHECK uses, and pair it with `git diff --quiet -- <routed-paths>` because neither sees what the
    other sees.
  **The general lesson is worse than either correction, and it is why I found this by sweeping my own
  memory rather than by using it:** a stale rule that routes you to a dead instrument does not merely
  fail — it **manufactures false assurance in exchange for diligence.** You run the check, it comes
  back the way the rule implied, and you are now *more* confident and *no better* informed. A rule
  that is simply absent leaves you uncertain, which is safer. (E-267-01 was the original catch: both
  changed files were untracked.)
- **A read showing exactly the defect you are hunting is a CANDIDATE, not a finding — but "the tool
  garbled it" is only one of the two explanations, and here it was the wrong one.** In E-267-03 round 2
  a Read of `src/db/reconcile_at_load.py` rendered `_pop = any(b.populated for b in blocks)`, a
  `frozenset().union(...)` of the id sets, and a `_prior_line_player_ids` accepting a `team_id` it then
  dropped from the SQL — i.e. exactly the global-OR bug the round's MUST FIX had removed. A second Read
  disagreed and a grep for those symbols returned exit 1, and this entry recorded it as a garble.
  **Re-adjudicated 2026-07-25 from transcripts: the read was ACCURATE.** SE wrote those exact lines into
  the worktree file at 21:35:44Z as a mutation-testing mutant; the Read landed at 21:36:02Z; SE restored
  from a scratchpad backup at 21:36:12Z, before the second Read (21:36:20Z) and the grep (21:36:28Z).
  The file was oscillating under a concurrent writer. So the disagreement + empty grep signature does
  NOT prove corruption — it is produced identically by a file that moved. Discriminate first (harness
  "modified on disk" note, `stat` mtime vs. read time, grep the writer's `subagents/*.jsonl` payload)
  per `.claude/rules/tool-output-integrity.md`. **During dispatch, the implementer is a live writer of
  the file you are reviewing**: had SE not restored, calling it a garble would have cleared a real
  mutation. Still confirm a parameter is bound in the SQL tuple and not merely present in the signature.
- **`bc` is NOT INSTALLED in this devcontainer, and `$(... | bc)` fails into a plausible NUMBER rather than an error.** `command not found` goes to stderr, the substitution yields the **empty string**, and a following `$((new-old))` treats the empty operand as **0** — so a total prints as `0`, a delta as the full new value, and a percentage as a clean `+0.0%`. **Nothing in the numeric output looks wrong.** (E-280 closure: measuring my own memory-dir growth, `old` came back 0 and the summary read `+0.0%`; caught only because 0 was obviously false for a 27-file directory — a less obvious operand would have shipped.) **Use `python3 -c` for any arithmetic you will report.** ⚠️ **Do NOT rely on "0 will look wrong to me" — MEASURED, it does not.** That is true only when 0 is an implausible ANSWER. Feed the same failure into a *"did anything change?"* gate and it inverts: `d=$(echo "7292 - 6727" | bc)` → empty → `$((d))` = **0** → the gate reports **"no change"** against a true delta of **565**. **A silent false PASS, which is the shape that ships.** So the trap's detectability depends entirely on whether 0 is a plausible answer to the question being asked — and in exactly the closure work where this arises (did the tree move? did the file change? is the delta zero?), **0 is the expected answer and the failure is invisible.** Same family as the ruff word-splitting entry above: the failure is on stderr and the exit path looks normal.
- **`mapfile -d` requires bash ≥ 4.4; macOS `/bin/bash` is 3.2.** On older bash it errors and leaves
  the target array **unset**, so a following `[ ${#ARR[@]} -eq 0 ] && exit 0` empty-guard reads
  "populate failed" as "nothing staged" and **fails open**. Portable, no-floor equivalent:
  `ARR=(); while IFS= read -r -d '' f; do ARR+=("$f"); done < <(... -z)`. (E-256-14 R4: a NUL-safe
  fix reintroduced a fail-open on the project's documented Mac host.)
