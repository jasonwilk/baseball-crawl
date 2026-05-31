# E-229-01: Remove RTK provisioning lanes + delete smoke-check script/test

## Status
`DONE`

## Epic
E-229

## Story
Remove the two RTK install lanes from devcontainer provisioning, drop the
`.tools/` cache from `.gitignore`, and delete the RTK smoke-check script and its
paired test. After this story, a devcontainer rebuild will not install RTK via
either lane, and no Python module or test references the smoke-check.

## Acceptance Criteria

1. **Claude lane removed.** In `.devcontainer/devcontainer.json`, the
   `postCreateCommand` (line 17) no longer contains the RTK install clause
   (`curl ... rtk-ai/rtk ... install.sh`, `rtk init -g --auto-patch`, or the
   `rtk install failed -- skipping` echo). The clause is *interior* to the chained
   command -- it sits between `pip install -e .` and `mkdir -p ~/.docker`. After
   removal those surrounding clauses remain intact and joined with a single `&&`:
   no `&&` at the start or end of the joined string, no doubled `&& &&`.
2. **devcontainer.json still parses as JSONC** (the file contains `//` comments,
   so strict JSON parsers such as `jq` / `python -m json.tool` reject it by design
   -- do NOT gate this AC on a strict-JSON parser). Concrete verify: strip
   line-comments first, then parse, e.g.
   `python3 -c "import re,json; s=open('.devcontainer/devcontainer.json').read(); json.loads(re.sub(r'(?m)^\s*//.*$','',s))"`
   exits 0. The structural check (AC-1: no dangling/doubled `&&`) is the primary
   gate; this parse is the secondary confirmation that the file is still
   well-formed after the clause excision.
3. **Codex lane removed.** In `.devcontainer/post-create-env.sh`, the trailing
   block from the `# ---- Project-local RTK install for Codex lane (E-082-01) ----`
   header through EOF is removed (including `RTK_CODEX_VERSION`, `RTK_CODEX_DIR`,
   `_install_rtk_codex()`, and the final invocation line). Everything above that
   header (the `set -euo pipefail` line and managed-block logic) is unchanged.
   After truncation the file ends on the Codex-trust `fi` followed by a single
   trailing newline (no double blank line).
4. **post-create-env.sh still parses** -- `bash -n .devcontainer/post-create-env.sh`
   exits 0.
5. **`.gitignore` cleaned.** Exactly lines 30-31 are removed: the comment
   `# Project-local tool cache (gitignored binaries -- e.g. RTK for Codex lane)`
   and the `.tools/` entry. No other `.gitignore` entry is touched. In particular,
   the canonical `.codex-home/` entry (line 28, under "Codex local runtime state")
   STAYS -- there is NO duplicate `.codex-home/` to remove.
6. **`scripts/check_codex_rtk.py` is deleted.**
7. **`tests/test_check_codex_rtk.py` is deleted.**
8. **No remaining import of the deleted module.** A grep for `check_codex_rtk`
   across `src/`, `tests/`, and `scripts/` returns zero hits.
9. **The test suite passes** with plain pytest (`python -m pytest tests/ -v`),
   confirming nothing else depended on the deleted script or test. (Note: the
   pytest hooks are still registered until E-229-02; running pytest here is the
   deletion-pair check, not hook verification.)

## Files to Create or Modify

- `.devcontainer/devcontainer.json` (modify -- excise the interior Claude-lane clause)
- `.devcontainer/post-create-env.sh` (modify -- truncate the Codex-lane block, lines 142-207)
- `.gitignore` (modify -- remove only lines 30-31: comment + `.tools/`)
- `scripts/check_codex_rtk.py` (delete)
- `tests/test_check_codex_rtk.py` (delete)

## Technical Approach

The Claude-lane edit is a surgical removal of one `&&`-joined clause from a
single chained command string; the clause is interior, so the surrounding
`pip install -e .` and `mkdir -p ~/.docker` clauses must stay wired together
without a broken or doubled `&&`. The Codex-lane edit is a tail truncation of a
clearly delimited trailing block in `post-create-env.sh`, ending cleanly on the
Codex-trust `fi` and one trailing newline. The two deletions are 1:1 -- the
script only smoke-checks the RTK binary and the test pairs to it -- so removing
both leaves no orphan references. Verify with `bash -n` (script syntax), JSONC
validation (devcontainer, NOT strict JSON), a `check_codex_rtk` grep, and a full
pytest run.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `post-create-env.sh` passes `bash -n`
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests (suite passes; smoke-check test removed cleanly)

## Non-Goals

- Do not touch host-level RTK artifacts (the `~/.claude` global hook from
  `rtk init -g --auto-patch` is the user's cleanup, per epic Non-Goals).
- Do not modify any context-layer file (those are E-229-02).
- Do not modify `docs/admin/codex-guide.md` (that is E-229-03).

## Notes
- The gitignored `.tools/rtk/rtk` binary is not a committed file; it disappears on
  next rebuild once the installer is gone.
- The `.codex-home/` ignore (line 28) is canonical and must stay; only `.tools/`
  (and its comment) is RTK-related.
