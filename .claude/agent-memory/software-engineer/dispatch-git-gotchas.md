---
name: dispatch-git-gotchas
description: git rm stages a deletion, hiding it from code-reviewer's unstaged `git diff` during dispatch; restore the staging boundary before reporting
metadata:
  type: project
---

# Dispatch git gotchas

## `git rm` silently stages the deletion — CR cannot see it

During dispatch, the staging boundary is: **staged (`git diff --cached main`) = prior
completed stories; unstaged (`git diff`) = the story under review.** Code-reviewer
reviews the *unstaged* diff.

`git rm <path>` deletes the file **and stages the deletion**. The removal therefore
lands in the staged half, mixed in with prior stories' content, and `git diff` shows
**nothing**. A reviewer looking at the current story's diff sees no evidence the file
was ever deleted — the AC "passes" against an invisible change.

Hit in E-256-03: `git rm src/gamechanger/bridge.py` folded a 97-line deletion into
stories 01/02/07's staged content.

**Fix (index-only, worktree deletion preserved):**
```
git restore --staged <path>     # index entry back to HEAD; file stays deleted
git status --porcelain <path>   # expect " D" (unstaged deletion), not "D "
```

**Prefer:** delete files with the `rm` shell builtin or a filesystem delete, not
`git rm`, so the deletion stays unstaged and reviewable. If `git rm` is already run,
unstage it before reporting and *disclose it* — `git restore` is outside the usual
permitted `git status/diff/log` set.

**Also invisible to `git diff`:** a **new untracked file** (e.g. a created `.dockerignore`) never
appears in `git diff` or `git diff --stat`. Use `git status --porcelain` for any completeness claim,
and `md5sum` when asserting a file is *unchanged*.

**Baselines:** mid-epic, the index is the baseline, not `HEAD`. `git show :<file>` reads the staged
tree (prior completed stories); `git show HEAD:<file>` predates every staged story and reports false
deltas.

See [[testing-gotchas]] for the worktree-vs-main import mechanics.

## Stale `.pyc` outlives its source, even mid-dispatch

Deleting `foo.py` does not remove `__pycache__/foo.cpython-*.pyc`, and any later
`pytest` run leaves more bytecode behind. A directory holding **only** `__pycache__`
and no `.py` is untracked (`__pycache__/` is gitignored), so it exists in the operator's
main checkout but **not** in the epic worktree, and no commit can delete it.

Import semantics of such a directory (verified E-256-03):
- `import pkg` **succeeds** — an implicit namespace package resolves on the directory alone.
- `import pkg.submodule` **fails** — `__pycache__` bytecode is not importable without source.

So they are inert, but a bare package name still resolves. Never report "removed the
ghost directories" as a satisfied AC: it produces no diff, CR cannot verify it, and a
`rm` in the main checkout violates worktree isolation.
