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
- **`git show HEAD:<file>` is the wrong baseline mid-epic** — prior stories are staged, not committed.
  Use `git show :<file>` (the index).
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
  unchanged one there. Use `git status --porcelain`; use a content hash to assert a file is unchanged.
- **`mapfile -d` requires bash ≥ 4.4; macOS `/bin/bash` is 3.2.** On older bash it errors and leaves
  the target array **unset**, so a following `[ ${#ARR[@]} -eq 0 ] && exit 0` empty-guard reads
  "populate failed" as "nothing staged" and **fails open**. Portable, no-floor equivalent:
  `ARR=(); while IFS= read -r -d '' f; do ARR+=("$f"); done < <(... -z)`. (E-256-14 R4: a NUL-safe
  fix reintroduced a fail-open on the project's documented Mac host.)
