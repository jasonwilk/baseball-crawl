---
name: testing-gotchas
description: Non-obvious pytest/SQLite/ruff gotchas in this repo — db-fixture backing differs per test file (db.backup deadlock), never trust a piped pytest exit code, worktree-pytest src-resolution (pytest DOES see worktree src), and ruff parsing `# noqa` inside prose comments
metadata:
  type: feedback
---

# Testing gotchas (project-specific)

## In an epic worktree, `pytest` exercises the WORKTREE src — but plain `python` does NOT (verified E-247-03)
**Rule:** During dispatch the spawn prompt warns "pytest tests the main checkout's code (not worktree changes) due to the editable install." In practice the resolution depends on HOW you invoke Python, and I verified (E-247-03) it is the OPPOSITE for `pytest`:
- `python -m pytest ...` from the worktree → `import src.*` resolves to the **WORKTREE** source (pytest puts rootdir/cwd on `sys.path` ahead of the editable `.pth`). So pytest DOES exercise your refactored worktree code directly. Verified via `python -c "import src...; print(mod.__file__)"` run *through pytest* → worktree path; a worktree-only new symbol imports fine under pytest.
- plain `python script.py` from the worktree → `import src.*` resolves to the **MAIN** checkout (`/workspaces/baseball-crawl`, the editable install). A worktree-only new symbol raises ImportError.

**Why:** I assumed (per the spawn note) pytest couldn't see my changes and built an importlib harness to compensate; then `test_url_parser.py` importing a brand-new `is_gc_uuid` PASSED under pytest, proving pytest was loading worktree src.

**How to apply:** (1) You can usually just run `pytest` in the worktree to validate refactors directly — don't assume it's testing stale main code. (2) For a genuine PRE-vs-POST byte-identical diff (HARD-GATE stories), exploit the asymmetry: a plain-`python` importlib script gets PRE from normal `from src...` imports (main/editable) and POST by `importlib`-loading the worktree files (inject into `sys.modules` under the canonical name so cross-imports resolve to worktree). That gave a real main-vs-worktree resolver/predicate diff in E-247-03. (3) Don't over-trust either assumption blindly — confirm with `module.__file__` in the exact invocation you're using.

**RE-CONFIRMED E-256-08, and the MECHANISM is now known — it is CONDITIONAL, so do not carry
"pytest sees the worktree" forward unconditionally.**

The editable install is a `MetaPathFinder` whose `MAPPING` really does hardcode
`{'src': '/workspaces/baseball-crawl/src'}` — that half of the old caveat is TRUE. But `install()`
**appends** `_EditableFinder` to `sys.meta_path`, *after* `PathFinder`. `PathFinder` searches
`sys.path` and is consulted first, so whenever the repo root is on `sys.path` the local `src/` wins
and the editable finder is never reached. Counterfactual: repo root ON `sys.path` → worktree; OFF →
`/workspaces/baseball-crawl/src`.

**Two load-bearing conditions:**
1. **`tests/__init__.py` must exist** — pytest's `prepend` import mode walks up past every
   `__init__.py` to find basedir, landing the repo root on `sys.path`. Delete it and bare `pytest`
   falls through to the editable finder → main's `src/`.
2. **cwd / `sys.path` must contain the repo root.**

Confirmed for BOTH `python -m pytest` and bare `pytest` in `/tmp/.worktrees/baseball-crawl-E-256`.
It mattered: story 08 deleted a DB read from a live auth path, and the suite genuinely exercised it.

**The dispatch spawn note and team-lead reminders assert the opposite** ("pytest tests the main
checkout's code"). They are wrong under the two conditions above. Confirm with `module.__file__` in
the exact invocation you are using before relying on either answer.

## Three ways a tool reported zero when the answer was not zero (all E-256-08, all verified)

1. **`files=$(git ls-files ...); ruff check $files` does not word-split** in this shell. ruff got
   **one** argument — a newline-joined mega-string — lint*ed nothing*, warned
   `Failed to lint tests/__init__.py\ntests/conftest.py\n...` on stderr, and **exited 0**. A single
   file yields 4 violations; the "whole tree" yielded 0. The same bug produced
   `python -m pytest $files -> RC=4, "no tests ran"`. **Use `git ls-files -z '<pathspec>' | xargs -0 <tool>`.**
   To check: `set -- $files; echo $#`.

2. **`include` in `pyproject.toml` filters directory walks, not explicitly-named paths.** With
   `[tool.ruff] include = ["src/**/*.py", "scripts/**/*.py"]`, `ruff check tests/` reports
   `All checks passed!` (vacuous), while `ruff check tests/test_cli_creds.py` reports its real
   violations. Count `tests/` with explicit paths or you get a confident zero.

3. **`.pyc` orphans under `__pycache__` are invisible to `git status`** (gitignored). After deleting
   a temp file, `ls` and `git status` said clean; `find . -name '<pattern>'` found the leftover
   `.pyc`. Use `find` for cleanup verification.

## Three more ways a grep reported zero — MARKUP moved, content did not (E-276, all verified)

> **Read this first if you are about to write a measurement into a memory file.** *A handoff
> artifact is at least read once, soon, by someone who might notice. A memory file is read cold,
> months later, by someone with no thread to check it against.* So: **never write a number from a
> live thread into memory — wait for it to settle, or record the mechanism instead of the
> measurement.** Generalizes past greps to anything numeric arriving mid-revision. (This entry
> shipped a retracted figure once; see the magnitude note below.)

Same family as the three above, but the cause is different and none is a synonym problem, so
`.claude/rules/doc-sweep.md`'s synonym-expansion step does **not** reach them. These are the *same
words* with markdown interpolated. Three agents hit all three within an hour, and **each was one
step from a fabricated finding** — #5 reads as "the preservation copy was deleted", #6 as "this
section cites a docstring phrase that does not exist."

4. **`**emphasis**` inside a quoted phrase breaks a literal-phrase grep.** Searching
   `"adequate bound on pre-existing"` returned **2** hits repo-wide and missed
   `epics/E-276-.../epic.md`, whose text is `an adequate **bound** on pre-existing loss`. An
   emphasis-normalized sweep found **7**. The conclusion drawn from the 2-hit result ("no copy in
   the epic") happened to be right — but *the grep was incapable of being right*, and it returned
   the comfortable answer. Had a real assertive copy existed it would have been missed identically.

5. **An anchored pattern silently narrows when blockquote nesting changes.** `^> A cap is not
   sufficient` returned 1 match where it had returned 2 — exactly what a deleted section looks
   like. Nothing was deleted: the text had moved from `> ` to `> > `. Read the section; do not
   rule on the count.

6. **A quoted phrase wrapped across a line break defeats a single-line pattern.** grep is
   line-oriented; reflowed prose splits a phrase that is still fully present, and the search
   returns **EMPTY** against text that is right there.

7. **A finding-record carries EVERY token of the defect it records — and no normalization
   separates them.** A sweep for a bad phrase hits the doc that *quotes it as a defect*, the
   preservation appendix, and the retraction note, with strings **identical** to a live assertion.
   Markup did not move; there is nothing to normalize. **Only reading the line distinguishes
   "asserts X" from "quotes X while calling it false".** Hit this directly: an emphasis-normalized
   sweep returned 7 `adequate bound` hits and **all 7 were quotations-as-defect or preservation
   copies — zero assertive**. A tool cannot make this call; budget for reading every hit.

> **⚠️ THIS LIST IS ITSELF A MISDIAGNOSIS HAZARD.** Having several narrowing cases catalogued makes
> the *next* unexpected empty look like narrowing. It often is not. On 2026-07-25, three of four
> "unexpected empty" events were narrowing and **the fourth was a MOVED FILE** — the content simply
> did not exist yet when the grep ran, and the empty result was ACCURATE. The two etiologies produce
> identical symptoms (`.claude/rules/tool-output-integrity.md`), and **a tally of narrowing cases is
> not evidence about the next one.** The reflex below holds either way; the DIAGNOSIS needs the
> `stat -c '%y %s'` differential, never the pattern-match.
>
> **And scope provenance PER OBSERVATION, not per message.** A write-up covering several calls
> across several file states tends to carry ONE timestamp — usually the newest — so a stale read
> ends up labelled with metadata from a later call that never covered it. **Quoting *a* timestamp
> reads as rigour and is worth less than quoting *the* timestamp**: cite the state of the read that
> produced each finding. Mirror-image obligation when you are the WRITER: do not edit a file while
> someone is reviewing it — on 2026-07-25 a file moved under a reviewer four times mid-review, and
> the fix on the reader's side (content-anchor, re-state the verified state) does not remove the
> cost the writer created. **Answer such a dispute by quoting the LITERAL LINE, never a count** —
> a count leaves both parties arguing about states.

**The unifying reflex, and the part worth actually remembering (CR-2's wording, which is broader
than mine was): an unexpected count is a CROSS-CHECK TRIGGER, never a finding — ANY count you did
not predict, in EITHER direction.** One match where there were two looks exactly like a deletion;
two hits where you expected none looks exactly like a live defect. **Both happened in one day.**
Cost when ignored is not a missed hit but a *fabricated* one.

**Which direction each one pushes — this is the operational half.** #5 and #6 return what a
**deleted section** looks like, so they push toward a *false alarm*: alarming, investigated,
self-correcting. #4 returns what a **clean tree** looks like, so it pushes toward a *false
all-clear* — **and that is the direction that ships.** A sweep that under-reports and reports
CLEAN is the dangerous member of the family; a sweep that screams gets checked. So when a
literal-phrase sweep comes back clean over marked-up prose, **that** is the result to distrust,
not the noisy one.

**Do NOT attach a magnitude to this.** The asymmetry is a property of the FAILURE MODE, not a
measurement: #4 *cannot* fail in the alarming direction, and that is what makes it dangerous —
not how many hits it missed on any given run. A prior version of this entry cited "6 hits vs 15
emphasis-tolerant" from a live sweep; **that comparison was retracted as confounded** — the two
runs used different term lists, so it measured term-list expansion, not emphasis tolerance.
Same-terms, the real delta was at most one and plausibly zero. The lesson never rested on the
count and is stronger without it. Still mark such a CLEAN result superseded and uncitable, on the
ground that **a method that cannot fail toward false-clean is not the same as one that happened
not to.**

> **Why that wrong number got here** — the surface is new and worth its own line. The figure
> reached this file *before* its retraction did: inherited mid-flight from another agent still
> revising it, and written straight into durable storage. **A memory file is the
> highest-persistence, lowest-revisit artifact I have**, so a retired number does more damage here
> than anywhere else — it outlives the thread that corrected it, and the next reader has no way to
> know it was withdrawn. **Never write a number from a live thread into memory. Wait for it to
> settle, or record the mechanism instead of the measurement.**

**Mitigation for any literal-phrase sweep of this repo's prose** — strip emphasis and normalize
quote depth before matching, then read the hits:

```python
flat = text.replace('**','').replace('__','')          # kills gotcha 4
for line in flat.splitlines():
    if pat.search(line.lstrip('> ')): ...              # kills gotcha 5
```

**Recovering an artifact that exists only in agent messages.** Related, and it is what made the
above checkable: sent `SendMessage` payloads persist in
`~/.claude/projects/<cwd-slug>/<session-id>/subagents/agent-<NAME>-<id>.jsonl`, as `tool_use`
blocks with `name == "SendMessage"` and the text at `input.message`. Iterate the JSONL, filter on
that, and you get **verbatim** text. Use this instead of reconstructing from memory whenever the
question turns on exact wording — a reconstruction that happens to render the disputed word
correctly is *worse* than one that gets it wrong, because it looks like evidence.

## `ruff` parses `# noqa` inside ordinary prose comments
**Rule:** Never write the literal token `# noqa` inside an explanatory comment, even in prose or backticks. ruff's directive scanner does not care that you were *talking about* suppression.

**Why:** In E-256-08 the comment explaining the `TYPE_CHECKING` fix said "...as opposed to a `# noqa` that would hide..." — ruff emitted `warning: Invalid # noqa directive on tests/test_cli_creds.py:24: expected ':' followed by a comma-separated list of codes`. I wrote a lint violation into the comment explaining why I was not writing a lint suppression.

**How to apply:** Say "a blanket suppression comment" instead. Same class as `grep -ci mypy pyproject.toml` → `1`, where the only match was the word "mypy" inside a comment I had just written.

## Never trust a `pytest | tail` exit code as a pass signal
**Rule:** Always capture pytest's OWN return code, never a pipeline's. `python -m pytest ... | tail` reports `tail`'s exit code (≈always 0), NOT pytest's — a hung or failing run can look like "exit 0".

**Why:** During E-236-04 I reported spray tests "passed, exit 0" based on `pytest | tail` background runs; when I re-ran capturing the real RC the truth was RC=124 (timeout/hang). The team lead called this out as exactly the tool-output-integrity trap the repo guards against.

**How to apply:** Run `python -m pytest ... > /tmp/out.txt 2>&1; echo "RC=$?" >> /tmp/out.txt` (RC appended WITHOUT a pipe), then read the file for the real RC and the `N passed`/`N failed` summary line. The harness "background command completed (exit code 0)" also reflects the whole compound command's last stage — not pytest — so don't rely on it either. Also: `-p no:cacheprovider` avoids cache contention; a `pytest-timeout` of 30s/test is configured, so a single hung test is killed at 30s but can still stall a shared run.

## The `db` fixture backing differs per test file — check before reusing `db.backup()`
**Rule:** Before copying a `db.backup(file_conn)` pattern between report test files, check what the source file's `db` fixture is backed by.
- `tests/test_report_plays.py` → `db` is **`:memory:`** → `db.backup(disk_conn)` copies memory→disk (correct).
- `tests/test_report_generator.py` → `db` is **disk-backed at `tmp_path/test.db`** (via `load_real_schema`) → calling `db.backup(file_conn)` where `file_conn` points at that **same path DEADLOCKS SQLite** (the run hangs).

**Why:** In E-236-04 I copied the plays-test backup pattern into a test_report_generator.py test; it deadlocked and stalled shared suite runs, which I initially (wrongly) blamed on environment WAL contention.

**How to apply:** In test_report_generator.py, the `db` fixture already persists committed rows to `tmp_path/test.db`, so a `_fresh_conn()` that opens that same path sees the data directly — NO backup needed. Only use `db.backup()` when the source `db` is `:memory:` and you need it on disk for a function that opens its own connections.
