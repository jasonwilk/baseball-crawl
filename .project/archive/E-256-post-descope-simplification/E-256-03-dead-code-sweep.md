# E-256-03: Dead-code sweep — bridge, discover_opponents, ghost dirs, utcnow

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

## Description
After this story is complete, the descope's dead-code residue is gone: the `bridge.py` module (implements the endpoint the rules ban for opponents), the test-only `discover_opponents` dead code, three ghost package directories carrying only stale pre-E-239 bytecode, and the two divergent `_utcnow_iso` implementations — consolidated into a single public `utcnow_iso` helper.

## Context
**api-scout consultation not required (rationale, per the epic's Consultation Triggers):** although this story deletes GameChanger endpoint-pattern code (`bridge.py`, `discover_opponents`), that code is **DEAD** — `bridge.py` is an E-239 deletion-set survivor implementing the opponent-bridge endpoint the rules already BAN (`.claude/rules/gc-uuid-bridge.md`), and `discover_opponents` is test-only dead code from the removed discovery surface. No LIVE API behavior is exercised or changed, so there is no api-scout question to answer; the deletion is a pure dead-code removal.

Each item is an independent E-239 deletion-set survivor. The two `_utcnow_iso` implementations (`generator.py:225` vs `scouting.py:466`) format-invert lexical ordering same-second and one is imported cross-module by underscore name. Publicizing to `utcnow_iso` and consolidating kills the cross-module underscore imports at `morning_run.py:52` and `reports_admin.py:541` — which is also a prerequisite for story 04's lifecycle extraction (Technical Notes §13). A present-tense docstring references `src.pipeline.trigger`; the ghost dirs (`src/pipeline/` etc.) contain only bytecode.

## Acceptance Criteria
- [ ] **AC-1**: Given `bridge.py`, when this story is complete, then the module and any import of it are removed, and no code path issues the banned opponent-bridge endpoint.
- [ ] **AC-2**: Given `discover_opponents` (`src/gamechanger/team_resolver.py:160`) and its test-only callers, when this story is complete, then both are removed.
- [ ] **AC-3** (REWRITTEN by PM pre-dispatch, 2026-07-09 — the original was **partly unsatisfiable in the worktree**; see below): Given the present-tense prose referencing deleted modules, when this story is complete, then **no docstring or comment in `src/` or `tests/` references `src.pipeline.*` or `src.gamechanger.bridge` as live**. The known site is `src/api/routes/reports_admin.py:17` (which names *both* `src.pipeline.trigger` and `src.gamechanger.bridge`). **Enumerate by grepping, not by trusting the count** — this epic is now six-for-six on hand-lists that undercounted (Technical Notes §15, IDEA-115). Apply the doc-sweep concept expansion: a sentence may describe the deleted module without naming it.
- [ ] **AC-3b** (PM, pre-dispatch): Given the "three ghost package directories," when this story is complete, then the completion report **states what was actually found**, because the original AC could not have been satisfied as written:
  - **`src/pipeline/` does not exist in the epic worktree.** PM confirmed via two independent channels (a Glob of `src/pipeline/**` returns nothing, and a repo-wide `*.pyc` listing shows a `__pycache__` for every real `src/` subpackage and none for `pipeline`). A path absent from the worktree is not tracked by git — a tracked file would have been materialized on checkout.
  - **`__pycache__/` is gitignored** (`.gitignore:2`). So the "ghost dirs carrying only stale bytecode" are **untracked, gitignored artifacts in the operator's MAIN checkout**, not repository content.
  - Therefore deleting them **produces no diff**, cannot ride the closure patch, and **cannot be verified by code-reviewer**, who reviews via `git diff`. An implementer who "removed the directories" in the worktree would be reporting a no-op; one who did it in the main checkout would be violating worktree isolation.
  - **Disposition**: the directory removal is **main-checkout housekeeping**, not a story deliverable. Record it as such, and do NOT report it as a satisfied AC. Note also that stale bytecode regenerates: `src/gamechanger/loaders/__pycache__/backfill.cpython-313.pyc` still exists in this worktree after story 02 deleted `backfill.py`. A one-time `rm` does not make this a durable class of problem worth an AC.
  - **If the grep finds a TRACKED file under any ghost directory** (contradicting PM's finding above), stop and escalate to PM — that inverts the analysis and the AC needs rewriting again, not silent adaptation.
- [ ] **AC-4**: Given the two `_utcnow_iso` implementations, when this story is complete, then there is exactly one public `utcnow_iso` helper, the cross-module underscore imports at `morning_run.py:52` and `reports_admin.py:541` import the public name, and no second implementation remains.
- [ ] **AC-5**: Given the full suite, when this story is complete, then it is green.
- [ ] **AC-6**: Given the two remaining `src/` readers of `data/raw/` outside story 02's `backfill.py` (PM-surfaced during dispatch), when this story is complete, then both are resolved:
  - **`src/gamechanger/crawlers/scouting_spray.py:82,106,110`** — `_DATA_ROOT` is a module constant used only as a default ctor arg, stored as `self._data_root` and **never read**. Remove the constant, the parameter, and the attribute.
  - **`src/cli/status.py:21-23,56`** — `_get_last_crawl()` globs `_RAW_DATA_ROOT / "*/manifest.json"` to populate `bb status`'s last-crawl panel. **Decision rule** (do not punt): grep `src/` for any writer of `manifest.json`. If **no writer exists**, the panel is vacuous — it can only ever report "no crawl" — so remove `_get_last_crawl()`, its `_RAW_DATA_ROOT` constant, and the panel row it feeds; a permanently-empty field is worse than an absent one because it reads as "the crawl never ran." If a **live writer does exist**, leave the code untouched, do not remove the panel, and report the writer's location to PM — the epic's "no `src/` module reads `data/raw/`" Success Criterion then needs a PM re-scope, not a silent deletion.
  - Together with story 01 (loaders) and story 02 (`backfill.py`), this discharges the epic Success Criterion "No module under `src/` reads `data/raw/`", which is verified at closure across all three stories — no single story owns it.

    **PM PREMISE CORRECTION (2026-07-09, post-implementation).** PM's rationale above — *"the panel is vacuous; it can only ever report 'no crawl'"* — is **FALSE**, and the true reason is stronger. SE found the operator's gitignored host-mounted `data/raw/` still holds three pre-E-239 manifests (`2025/`, `2026-spring-hs/`, `2025-summer-usssa/`). `bb status` has therefore been globbing them and displaying a **real, months-stale crawl date and file count** — not an empty field. A panel asserting a fresh-looking "Last crawl: <date> (N files)" for a pipeline deleted in E-239 is **worse** than the empty field PM imagined, and cuts directly against CLAUDE.md's Data Philosophy guidance on presenting stale sync dates. The removal branch is unchanged; only PM's reason was wrong. **Stories 10 and 15 must not carry the word "vacuous" into prose** — the panel was *actively misleading*, not empty. PM reasoned from where the symptom was noticed (the code path) rather than from where the mechanism lives (the host volume that code path reads) — the same error shape the epic History records for story 07.

    **Closure trap (SE-surfaced, PM confirms).** The Success Criterion must be verified as **READS, not MENTIONS**. A closure-time token grep for `data/raw` still hits `src/gamechanger/signing.py:7`, a comment citing the doc path `data/raw/gc-signature-algorithm.md` — a reference, not a read. Do not report it as a violation.

## Technical Approach
Locate the single natural home for `utcnow_iso` (a small time helper both `reports` and `gamechanger` layers can import without inverting the layering — e.g. `src/util/`). Delete the ghost dirs including their `.pyc`. The `bridge.py` endpoint ban is documented in `.claude/rules/gc-uuid-bridge.md` (BANNED PATH section) — deleting the module is consistent with it; do not edit that rule here (it already bans the path).

## Dependencies
- **Blocked by**: None
- **Blocks**: E-256-04 (the lifecycle split depends on the single public `utcnow_iso`); E-256-15 (eviction sweep)

## Files to Create or Modify
- `src/.../bridge.py` (delete)
- `src/gamechanger/team_resolver.py` (remove `discover_opponents`)
- ~~`src/pipeline/` and the two other ghost dirs (delete)~~ — **not in the worktree; untracked gitignored bytecode. See AC-3b.**
- `src/api/routes/reports_admin.py` (`:17` docstring naming `src.pipeline.trigger` + `src.gamechanger.bridge`, AC-3)
- The `utcnow_iso` home module (create or select)
- `src/reports/generator.py`, `src/gamechanger/crawlers/scouting.py` (remove duplicate `_utcnow_iso`)
- `src/reports/morning_run.py` (`:52`), `src/api/routes/reports_admin.py` (`:541`) (import the public name)
- `src/gamechanger/crawlers/scouting_spray.py` (AC-6: remove the dead `_DATA_ROOT` / `_data_root`)
- `src/cli/status.py` (AC-6: `_get_last_crawl` disposition per the decision rule)
- Any test files referencing the deleted symbols

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-256-04**: the single public `utcnow_iso` name and location, which the lifecycle split consumes.
- **Produces for E-256-15**: the deleted symbol set (`bridge`, `discover_opponents`, `src.pipeline.*`) for the eviction sweep.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests updated and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## PM AC-Verification (2026-07-09)
**ALL ACs PASS** (AC-1, AC-2, AC-3, AC-3b, AC-4, AC-5, AC-6). Verified against the worktree.

- **AC-1 PASS.** `src/gamechanger/bridge.py` absent (Glob); zero `gamechanger.bridge` references in `src/`.
- **AC-2 PASS.** Zero `discover_opponents` in `src/`.
- **AC-3 PASS.** Zero `src.pipeline` references in `src/` — `reports_admin.py:17` (which named *both* `src.pipeline.trigger` and `src.gamechanger.bridge`) is clean.
- **AC-3b PASS — the escalation branch did NOT fire.** SE independently confirmed PM's finding by three methods: `git ls-files` returns zero tracked files under each of `src/pipeline/`, `src/gamechanger/pipelines/`, `src/gamechanger/resolvers/`; `git status --porcelain --ignored` marks all three `!!`; the worktree has no such paths. The count of three was right and all three are now **named**. The directory removal remains **main-checkout housekeeping, not a story deliverable** — correctly reported as such, not claimed as a satisfied deletion. SE's discriminating predicate (**has `__pycache__` AND zero `.py`**) is better than the naive "directory with no `.py`", which over-matches `src/api/static`, the five `src/api/templates/*`, and the live `src/baseball_crawl.egg-info`.
- **AC-4 PASS.** Exactly one `utcnow_iso` in `src/` (`src/util/timezone.py:136`); both `_utcnow_iso` copies gone; `morning_run.py:53` and `reports_admin.py:52` import the public name. Home is stdlib-only and already imported by both layers, so no layering inversion.
- **AC-5 PASS.** Suite `3803 passed, RC=0`.
- **AC-6 PASS.** `_get_last_crawl` / `_RAW_DATA_ROOT` gone from `status.py`; `scouting_spray.py`'s dead `_DATA_ROOT` constant, ctor param, and attribute gone. Third and final leg of the epic Success Criterion.

**Ruling — `UTC_ISO_FORMAT` constant: APPROVED, in scope.** It is one line beyond AC-4's letter but squarely inside its intent. AC-4 exists because two divergent format strings inverted lexical ordering; the invariant that actually protects the four comparison sites is *"both sides of the comparison share one format,"* which was previously implicit across three separate string literals. A named constant makes the invariant checkable. PM verified the format choice independently: `expires_at` is compared lexically at `morning_run.py:327` and `reports_admin.py:540`, and `generator.py:1864` writes it via `UTC_ISO_FORMAT` — the no-dot format sits on both sides. The dotted format would have flipped an at-expiry-second report from expired to non-expired.

**Ruling — `scouting_runs` mixed-format column: ACCEPTED.** PM verified SE's claim rather than taking it: `scouting_runs` appears in `src/` only in `INSERT` / `UPDATE` / `DELETE` statements (`scouting.py:389,323,420`; `generator.py:2815`). No `SELECT`, no ordering, no `MAX()`, no parse of `started_at` / `completed_at` anywhere. The mixed shape is cosmetic and unread. Accepted as the correct trade: forcing historical-row consistency would mean a migration for a column nothing reads.

**Ruling — the two out-of-list files: BOTH IN SCOPE.** `src/gamechanger/crawlers/__init__.py` (a docstring naming a `crawl_all()` that exists nowhere) and `tests/test_cli.py` (patched `_get_last_crawl`) are the same class as story 01's seventh test file and story 07's `pyproject.toml`. Found by scope-discovery grep, not assumed from the Files list. That is the AC-3-criterion discipline working, and it is now the **eighth** seed-list undercount this epic.

**SHOULD FIX for CR's consideration (not an AC failure).** `tests/test_admin_reports.py:24` and `tests/test_report_routes.py:23,29` each hardcode `"%Y-%m-%dT%H:%M:%SZ"` in local `_utcnow_iso` / `_future_iso` helpers. They agree with `UTC_ISO_FORMAT` today, so nothing is broken — but they reintroduce, in the tests, exactly the "same format asserted by separate literals" shape that `UTC_ISO_FORMAT` was extracted to eliminate. They should import the constant. PM's call: cheap, zero behavior change, and it closes the loop the story opened. Deferred to CR.

**Disclosures 1-3: all accepted, and disclosure 1 is the important one.** SE's `git rm` had staged the `bridge.py` deletion, which would have hidden a 97-line deletion from code-reviewer (who reviews the *unstaged* diff). SE corrected it and **disclosed rather than leave CR blind** — the staging boundary is the mechanism the whole two-gate review depends on, and a silent index change would have defeated it invisibly. The two reverted Bash heredoc writes (verified byte-identical via `diff -q`) and the three pre-existing ruff findings left for story 08 are both correct calls; absorbing the ruff findings would corrupt story 08's baseline, mirroring story 02's handoff.

**`signing.py:7` — captured, not chased.** The pointer is **accurate, not stale**: `data/raw/gc-signature-algorithm.md` exists, but in the gitignored host-mounted `data/`, so it dangles on any fresh clone. Relocating it to `docs/api/` is api-scout's call, out of scope here.

**`tests/test_app_import_isolation.py` — PM ruling (2026-07-09, round 2): KEEP, unchanged. It is NOT a tombstone. No closure follow-up.** PM read the file rather than accept the framing. Its docstring already states its own nature honestly: *"This test is therefore a standing guard against the chain being re-formed, not a check on live code… The name survives here only as the thing being excluded."* A negative regression guard is *supposed* to pass while the thing it excludes is absent. The only test-quality question is whether it **can still fail** — and it can: re-introduce a `src.pipeline` import into the app's graph and the subprocess assertion trips. SE's own probe reinforces this: `import ghostpkg` resolves as an implicit namespace package, so a bare `import src.pipeline` would land in `sys.modules` and be caught. The guard is live. "Tombstone" conflates *"asserts something currently true"* with *"cannot be made false"*; only the second is a defect. **Removed from the closure list.**

## PM AC-Verification Round 2 (2026-07-09)
**AC-4 and AC-5 re-verified: PASS.** (Other ACs undisturbed — tests only this round.)

- **AC-4 PASS.** `grep '"%Y-%m-%dT%H:%M:%SZ"'` across `src/` + `tests/` returns **exactly one line**: the definition at `src/util/timezone.py:133`. Both local `_utcnow_iso` test helpers are gone (the name survives only in a `test_util_timezone.py` docstring describing what was consolidated). SE **deleted** the duplicate helpers rather than feeding them the constant — correct: importing `UTC_ISO_FORMAT` into a byte-identical re-implementation of `utcnow_iso()` would have closed half the loop and left the other half.
- **AC-5 PASS.** `3803 passed, RC=0`, count unchanged (two tests rewritten, none added or removed).
- **The MUST FIX was inside AC-4's blast radius, and PM missed it.** `test_util_timezone.py:61-65` asserted `base.strftime(F) == base.strftime(F)` — an `x == x` tautology passing under every format including the dotted one, while its docstring claimed to prove AC-4's exact property. PM verified AC-4 in round 1 by checking the *consolidation* (one definition, imports re-pointed) and did not apply the delete-the-behavior teeth test to the test that claimed to guard it. The rewrite pins golden literals (`:42.000000` and `:42.999999` → `"2026-07-09T03:17:42Z"`), which PM read and confirms is falsifiable under the dotted format.
- **SE's SHOULD-FIX extension beyond PM's line list was right.** PM named two files; SE grepped the literal and found it **six times across three**, including `test_report_generator.py:4313`, which appeared in no list. Ninth seed-list undercount this epic — and this one was PM's.
None.
