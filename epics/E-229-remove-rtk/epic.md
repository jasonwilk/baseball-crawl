# E-229: Remove RTK (Rust Token Killer) from baseball-crawl

**Status**: READY
**Owner**: product-manager
**Created**: 2026-05-30

## Overview

RTK (Rust Token Killer) is a CLI proxy that rewrites and compresses dev-command
output to save tokens. It is installed into this project through two devcontainer
provisioning lanes (Claude and Codex) and is referenced throughout the context
layer, docs, and pytest tooling. The user has decided RTK should no longer be
used in baseball-crawl.

This epic removes **every in-repo trace of RTK** so that:

1. **Future devcontainer rebuilds do not reinstall it.** Both provisioning lanes
   (the Claude-lane `postCreateCommand` clause and the Codex-lane
   `post-create-env.sh` block) are excised.
2. **The context layer stops carrying RTK guidance that will mislead agents.**
   Rules, skills, agent memory, AGENTS.md, Codex config, and the codex-guide doc
   are scrubbed of RTK references.
3. **The pytest tooling RTK necessitated is dropped entirely.** RTK's output
   compression silently hid pytest failures, which is why
   `.claude/rules/pytest-verbose.md`, the `pytest-verbose.sh` hook, and the
   `pytest-exitfirst-warn.sh` hook exist. With RTK gone, all three are removed
   (full drop -- nothing is added to replace them).

### Why now

RTK's compression was found to silently hide pytest failures (~67 silent failures
across E-173/E-179). The user no longer wants RTK in this project. Removing it
also eliminates the workaround tooling built solely to compensate for RTK's
output distortion.

## Non-Goals

- **Host-level RTK cleanup is out of scope.** The user's personal `~/.claude`
  RTK artifacts -- including the global command-rewrite hook -- are a separate
  cleanup the user owns. This epic touches only the in-repo (checked-in) tree.
- **No re-verification of RTK-era work.** Whether prior decisions were made on
  RTK-distorted output is a backward-looking concern captured separately as
  IDEA-072. This epic is forward-looking: stop using RTK going forward.
- **No replacement tooling.** The pytest machinery is a full drop. We do not
  introduce a new pytest wrapper, hook, or rule.
- **Archived and historical records are frozen.** `.project/archive/**` (incl.
  RTK epics E-070/E-082/E-224), `.project/research/**`, and `reviews/**` are not
  modified. `reviews/04` references `check_codex_rtk.py` as a historical finding
  -- that stays as a frozen record.

## Stories

| ID | Title | Status | Agent Hint | Depends On |
|----|-------|--------|-----------|-----------|
| E-229-01 | Remove RTK provisioning lanes + delete smoke-check script/test | TODO | software-engineer | -- |
| E-229-02 | Scrub RTK from context layer + drop pytest machinery (atomic) | TODO | claude-architect | -- |
| E-229-03 | Remove RTK Integration section from codex-guide doc | TODO | docs-writer | -- |

Story files:
- `E-229-01-provisioning-and-deletes.md`
- `E-229-02-context-layer-and-hooks.md`
- `E-229-03-docs-codex-guide.md`

## Dispatch Team

- software-engineer (E-229-01)
- claude-architect (E-229-02)
- docs-writer (E-229-03)

## Acceptance Criteria (Epic-Level)

The defining acceptance criterion is a **clean grep**, because both install lanes
fail silently/soft (`|| echo "...skipping"`) -- "the devcontainer still builds" is
NOT sufficient proof that RTK was removed.

After all stories are DONE, run from the repo root:

```
grep -rniE 'rtk|rust token killer' . \
  --exclude-dir=.git \
  --exclude-dir=worktrees \
  --exclude-dir=.codex-home \
  --exclude-dir=data \
  --exclude-dir=.pytest_cache \
  --exclude-dir=baseball_crawl.egg-info \
  --exclude-dir=.project \
  --exclude-dir=epics \
  --exclude-dir=reviews \
  --exclude-dir=agent-memory \
  --exclude=E-221-HANDOFF.md
```

**On the exclusions** (grep `--exclude-dir` matches a directory *basename*, not a path, so values containing `/` match nothing):

- `--exclude-dir=worktrees` covers `.claude/worktrees/` (basename match). Do NOT write `--exclude-dir=.claude/worktrees` -- the slash makes it a no-op.
- `--exclude-dir=data` covers both `data/` and `proxy/data/` (basename `data`).
- `--exclude-dir=.project` covers the whole planning tree (`archive/`, `research/`, `ideas/`, `templates/`). These are planning/historical artifacts that legitimately reference RTK -- notably IDEA-072 (the RTK retrospective-audit idea) and other ideas (016/024/047/068). A forward-looking removal does not touch them.
- `--exclude-dir=epics` covers the entire `epics/` tree -- including THIS epic's own files (E-229 is *about* removing RTK, so its files necessarily contain the word) and other active epics (e.g. E-230) that mention RTK in passing.
- `--exclude-dir=reviews` covers the frozen `reviews/` tree.
- `--exclude-dir=agent-memory` covers `.claude/agent-memory/`. Excluded because (a) api-scout and software-engineer memory legitimately contain the `rtkn` JWT field (the same false positive as the auth docs -- permanent, not RTK tooling, and per finding 1 NOT swept), and (b) all agent memory references this epic by its slug `remove-rtk` and prior RTK work historically. PM cleans its own real E-224 RTK note (`product-manager/MEMORY.md`) at closure as a separate obligation, not enforced by this grep.
- `--exclude=E-221-HANDOFF.md` excludes one frozen historical handoff doc that contains two stale `rtk proxy` command references (lines 88, 90). Per scope it is left frozen, not edited, so it is excluded from the grep by filename.
- `/tmp/.worktrees/` is outside the grep root (`.`), so it needs no exclusion.

This tree-wide grep is the integrative backstop. The primary proof is per-touchpoint: each story carries an AC that its owned files are RTK-free.

This grep MUST return hits in **exactly two FILES** (six lines total), all the `rtkn` JWT refresh-token field (false positive -- the field name contains the substring `rtk`): `docs/api/auth.md` (3 lines) and `docs/api/endpoints/post-auth.md` (3 lines). These files must NOT be modified.

## Technical Notes

### Authoritative scope inventory

Derived from a complete grep + file reads of the active tree.

**Two install lanes:**

- **Claude lane** -- `.devcontainer/devcontainer.json`, `postCreateCommand`
  (line 17). The `&&`-joined clause:
  `((curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh && rtk init -g --auto-patch) || echo "rtk install failed -- skipping")`.
  This clause is *interior* to the chained command -- it sits between
  `pip install -e .` and `mkdir -p ~/.docker`. Excise it surgically; the
  surrounding clauses must stay joined with a single `&&` (no dangling/doubled
  `&&`). devcontainer.json is JSONC (`//` comments), so strict JSON parsers
  reject it by design -- validate against the JSONC schema, not `jq`/`json.tool`.
- **Codex lane** -- `.devcontainer/post-create-env.sh` (lines 142-207). The
  trailing block from the
  `# ---- Project-local RTK install for Codex lane (E-082-01) ----` header
  through EOF -- including `RTK_CODEX_VERSION`, `RTK_CODEX_DIR`, the
  `_install_rtk_codex()` function, and the final invocation. Truncate cleanly so
  the file ends on the Codex-trust `fi` plus a single trailing newline (no double
  blank). Everything above (`set -euo pipefail`, managed-block logic) is
  untouched.

**All touchpoints (with owning story):**

| Touchpoint | Action | Story |
|-----------|--------|-------|
| `.devcontainer/devcontainer.json` (line 17 clause) | Excise interior clause | 01 |
| `.devcontainer/post-create-env.sh` (lines 142-207) | Truncate trailing block | 01 |
| `.gitignore` (lines 30-31) | Remove comment + `.tools/` entry | 01 |
| `scripts/check_codex_rtk.py` | DELETE | 01 |
| `tests/test_check_codex_rtk.py` | DELETE | 01 |
| `.codex/config.toml` (lines 7-9) | Remove 3-line RTK comment block | 02 |
| `AGENTS.md` (~lines 17-48) | Remove entire `## RTK Usage` section | 02 |
| `.agents/skills/claude-context-bridge/SKILL.md` (lines 31-33) | Remove `## RTK (Token Optimization)` section | 02 |
| `.claude/rules/pytest-verbose.md` | DELETE | 02 |
| `.claude/hooks/pytest-verbose.sh` | DELETE | 02 |
| `.claude/hooks/pytest-exitfirst-warn.sh` | DELETE | 02 |
| `.claude/settings.json` (PreToolUse Bash matcher) | Deregister the two pytest hooks | 02 |
| `.claude/skills/implement/SKILL.md` (line ~224 bullet) | Strip `-x/--exitfirst` RTK bullet (carries `rtk proxy` + pytest-verbose.md cross-ref) | 02 |
| `.claude/skills/context-fundamentals/SKILL.md` | Recompute context-budget numbers (table + worked example + prose) | 02 |
| `docs/admin/codex-guide.md` (RTK Integration section) | Remove section; keep `## Checked-In Layer` list; add staleness header | 03 |
| `.claude/agent-memory/product-manager/MEMORY.md` | PM sweeps own RTK note (E-224 archival note) | closure (PM), not a story |

Agent memory other than PM's is NOT a touchpoint: `api-scout/MEMORY.md` and
`software-engineer/endpoint-parsing-notes.md` match only the `rtkn` JWT field (a
false positive, not Rust Token Killer); `claude-architect/` has zero RTK hits.
See the "Agent-memory: no in-epic sweep" note below.

**Agent-memory: no in-epic sweep.** A verified grep established that the agent
memory dirs need no sweep, and an attempted sweep would do harm:
- `api-scout/MEMORY.md` and `software-engineer/endpoint-parsing-notes.md` -- the
  only `rtk` hit in each is the `rtkn` JWT access-token field (the same false
  positive as the auth docs), NOT Rust Token Killer. Removing those lines would
  delete valid API-payload notes.
- `claude-architect/` -- ZERO RTK hits. Nothing to sweep.
- `product-manager/MEMORY.md` -- the ONLY real RTK memory content (an E-224
  archival note mentioning "RTK/Pytest" + "rtk proxy"). This is PM's own memory
  and is cleaned by the PM at closure (the standing carve-out), before the
  closing grep runs.
Net: story 02 makes NO agent-memory edits. Because those `rtkn` false positives
and epic-slug references therefore remain in the tree permanently, the closing
grep EXCLUDES `.claude/agent-memory/` via `--exclude-dir=agent-memory` (see the
"On the exclusions" bullet in the epic-level Acceptance Criteria). PM-own memory
is cleaned at closure as a separate obligation, not enforced by the grep.

**`.codex/config.toml`**: keep lines 1-5 (model/effort/header); remove only the
3-line RTK comment block.

**`docs/admin/codex-guide.md`**: remove the full `## RTK Integration (Codex
Lane)` section including its binary-location, "What This Lane Does NOT Use",
"Coexistence", and "RTK Smoke Check" (the `python scripts/check_codex_rtk.py`
block) subsections. Keep the `## Checked-In Layer` list -- those files remain in
the repo; their own RTK content is removed by their own stories. The file has no
staleness header today; story 03 adds one (`Source: E-229`).

**`.claude/settings.json`**: in the PreToolUse `"Bash"` matcher hooks array,
remove ONLY the `pytest-verbose.sh` and `pytest-exitfirst-warn.sh` entries. KEEP
`pii-check.sh` and `epic-archive-check.sh`. Leave the Write/Edit `worktree-guard`
matchers untouched. (Order in the Bash matcher: pii-check, epic-archive-check,
pytest-verbose, pytest-exitfirst-warn -- remove the last two.)

**`.claude/skills/implement/SKILL.md`**: the RTK footprint is a single bullet at
line ~224 -- it carries the `-x`/`--exitfirst` prohibition, the "RTK compression
hides suite truncation" wording, the `rtk proxy` bypass reference, AND the
`pytest-verbose.md` cross-reference all on one line. Removing that one bullet
clears all RTK from the file (verified -- no second RTK reference).

**`.claude/skills/context-fundamentals/SKILL.md`** (recompute, multi-location):
dropping the `pytest-verbose` rule (56 lines) changes the count in several places,
not just the budget table:

- the universal-rules table total (currently "8 rules / ~394 lines", ~line 79);
- the worked-example block (~lines 155/159/182: the "8 files / ~394" figure, the
  "Ambient subtotal" line, and the "Total" line);
- the prose aggregate-target / estimate figures (~lines 28, 74, 83: the
  "~704-974" / "~680-950" ambient ranges).

Do NOT blind-subtract 56. Re-measure the 7 surviving universal rule files with
`wc -l`, recompute the table total from the measured sum, then propagate the
corrected rules figure through the worked-example subtotals and prose ranges so
the file is internally consistent. (The current file already contains arithmetic
self-corrections; the recompute should leave one coherent set of numbers.)
`context-fundamentals/SKILL.md` itself contains no `rtk` substring -- its work is
purely the numeric recompute.

### Pytest machinery: full drop (user decision)

`.claude/rules/pytest-verbose.md`, `.claude/hooks/pytest-verbose.sh`, and
`.claude/hooks/pytest-exitfirst-warn.sh` exist solely to compensate for RTK's
output compression (which hid pytest pass/fail counts and suite truncation). With
RTK removed, plain pytest output is honest again. The user decided on a FULL DROP:
delete all three and add nothing.

### Allowed grep exceptions -- verified

The closing grep returns hits in exactly two FILES (six lines total), all the
`rtkn` JWT refresh-token field (false positive -- the field name contains the
substring `rtk`):

- `docs/api/auth.md` (lines 15, 39, 463)
- `docs/api/endpoints/post-auth.md` (lines 80, 84, 316)

Verified against the live tree:
- A case-insensitive `rtk` grep over all of `docs/` returns these two files
  (plus `docs/admin/codex-guide.md`, which story 03 scrubs to zero).
- `docs/E-221-HANDOFF.md` -- contains TWO real `rtk proxy` references (lines 88,
  90) in a completed-epic handoff doc. It is left FROZEN (historical record) and
  EXCLUDED from the grep by filename (`--exclude=E-221-HANDOFF.md`), not cleaned.
- `scripts/install-hooks.sh` -- **ZERO `rtk` matches**; not a grep exception.
  (Note: `scripts/check_codex_rtk.py` IS rtk-laden today, but story 01 DELETES it,
  so it is gone before the closing grep runs -- it is not a residual.)

### Sequencing rationale

E-229-02 holds the **atomic** settings-unwiring + hook-file deletion in a single
story, so the repo is never left in a deleted-but-wired state (hook file gone but
still registered in `settings.json`, or vice versa). This is the only ordering
hazard. The three stories otherwise touch disjoint file sets and may execute in
any order; encoding them to run serially (01 -> 02 -> 03) is acceptable since
dispatch executes stories serially regardless.

### Expert consultation

No domain-expert consultation required -- this is a pure removal of a development
tool with a complete, pre-verified inventory. claude-architect owns the
context-layer story by routing rule; software-engineer and docs-writer own the
provisioning and docs stories respectively.

## Open Questions

- **Should pytest discipline be re-anchored elsewhere after the full drop?**
  Considered and DECLINED for this epic. The `-v` requirement and `-x`
  prohibition existed only because RTK's compression hid pytest output; with RTK
  gone, plain pytest output is honest, so no replacement rule/hook/`addopts`
  default is added. (A `pyproject.toml` `addopts = "-v"` fallback was weighed and
  declined -- it is out of scope for a removal epic and would reintroduce
  tooling the user asked to drop. If pytest-output discipline turns out to matter
  post-removal, capture it as a fresh idea.)

## History

- 2026-05-30: Epic created (DRAFT) after discovery completed by prior PM. Scope
  inventory verified via complete grep + file reads.
- 2026-05-30: Resolved a concurrent-PM race that produced duplicate story files
  and a duplicate idea. Per team-lead direction, kept the short-named story set
  (`provisioning-and-deletes`, `context-layer-and-hooks`, `docs-codex-guide`) as
  survivors and ported superior content from the long-named variants into them
  (staleness-header AC, atomicity AC, ownership detail). Incorporated internal
  review findings: grep `--exclude-dir` basename fix (worktrees, data covers
  proxy/data); JSONC-not-strict-JSON AC; multi-location context-fundamentals
  recompute via `wc -l`; in-epic agent-memory sweep with verbatim-only guard;
  `.gitignore` lines-30-31-only with no phantom `.codex-home`. Corrected the
  allowed-exception paths to `docs/api/auth.md` +
  `docs/api/endpoints/post-auth.md` (Glob-confirmed -- the two files sit at
  different directory levels). Still DRAFT.
- 2026-05-30: Redesigned the closing-grep AC per user decision: excluded
  planning/historical artifacts (`epics/`, `.project/`) and the frozen
  `docs/E-221-HANDOFF.md` (which carries two stale `rtk proxy` refs); the
  tree-wide grep is now an integrative backstop atop per-touchpoint ACs.
  Corrected the earlier false "E-221-HANDOFF has zero matches" note. Deleted the
  3 duplicate long-named story files (short-named trio is canonical).
- 2026-05-30: Consistency follow-up to the finding-1 fix: added
  `--exclude-dir=agent-memory` to the closing grep. Dropping the agent-memory
  sweep (finding 1) left the `rtkn` JWT false positives and the epic-slug
  references permanently in `.claude/agent-memory/`; without this exclusion the
  closing grep would return five files, not two. PM-own memory is still cleaned at
  closure as a separate obligation.
- 2026-05-30: Incorporated Codex spec-review findings (5 accepted): (1) DROPPED
  the in-epic agent-memory sweep -- verified the api-scout/SE memory hits are the
  `rtkn` JWT false positive and claude-architect's dir is empty, so a sweep would
  delete valid API notes; removed the 3 touchpoint rows, the story-02 AC, and the
  ownership Technical Note. (2) Corrected "exactly two hits" to "exactly two FILES
  (six lines)" -- the `rtkn` field appears 3x per file. (3) Moved the tree-wide
  closing grep to an epic-level gate only (removed it as a story-02 AC) so
  story-02 is independently completable with `Blocked by: None`. (4) Scoped the
  "scripts/ clean" note to install-hooks.sh (check_codex_rtk.py is rtk-laden but
  deleted by story 01). (5) Gave E-229-01 AC-2 a concrete comment-stripping JSONC
  parse command.
- 2026-05-30: Set to READY. Closing-grep simulation confirmed achievable (resolves
  to exactly `docs/api/auth.md` + `docs/api/endpoints/post-auth.md` after the 3
  stories scrub their touchpoints, with the agent-memory/epics/.project/E-221-HANDOFF
  exclusions in place).

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal review (CR spec audit + holistic team) | 8 | 8 | 0 |
| Codex spec review | 5 | 5 | 0 |
| Consistency follow-up (agent-memory exclusion) | 1 | 1 | 0 |
| **Total** | **14** | **14** | **0** |

Note on the internal-review row: of the 8 findings, finding 4 ("allowed exceptions"
count) was triaged as DISMISS on the alleged undercount itself (the count was
correct) but surfaced a real exception-path bug that was fixed -- so it is recorded
as accepted (a fix landed). The two duplicate-artifact findings (duplicate story
files, duplicate idea) are folded into this count as a single consolidation finding
alongside the substantive spec findings (grep `--exclude-dir` basename fix, JSONC
AC, multi-location context-fundamentals recompute, agent-memory ownership,
`.gitignore` accuracy, post-create-env tail truncation, E-229-03 staleness header).
