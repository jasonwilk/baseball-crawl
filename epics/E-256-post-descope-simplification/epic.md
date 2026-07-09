# E-256: Post-Descope Simplification & Foundations

## Status
`READY`

## Overview
Retire the machinery the reports-first reframe made vestigial, and lay the foundations the project never grew. The disk-based twin load flow is production-dead but actively maintained — and E-247 shipped a stat-wiping regression on the LIVE path *introduced purely to preserve parity with the dead path*. Meanwhile there is no CI, no `.dockerignore`, two known-CVE pins with no refresh mechanism, backups nothing schedules, a deploy runbook that is dead on arrival, and — most consequentially — a reports flow that is **never actually driven at closure**, which is how a physically-impossible FPS stat reached a live report and a rest-day UTC bug slipped between two epics that both closed green.

## Background & Context
Two source documents drive this epic, both uncommitted at the repo root and both **read at planning time, not summarized**:

- **`PLATFORM-AUDIT.md`** (2026-07-03) — this epic is its candidate epic **CE-6**, absorbing the audit's 6 medium and ~12 low findings in the "simplification & foundations" cluster.
- **`AGENTIC-FLOW-REVIEW.md`** (2026-07-07) — §3.7 and §6 rows 8, 10, and 12 specify the closure runtime smoke, the CI slice, and the PII gate respectively.

The audit's upheld REVISIT decision — retiring the stored `player_season_*` tables in favor of query-time derivation — was **split out of this epic** into **E-259** by user decision (2026-07-09). Different owner, different risk profile, and a strict ordering constraint (Technical Notes §1).

E-256 also **promotes IDEA-102** (`.project/ideas/IDEA-102-committed-artifact-pii-gap.md`), whose own "cheapest lever" open question — extend the byte-gate to sweep `epics/` + `.project/` against the real denylist — is precisely what story 14 implements.

**This epic is audit-derived, not roadmap-derived.** It implements no `docs/ROADMAP.md` §5 slice (A–E are all COMPLETED). Per the §0 convention it therefore carries **no `## Roadmap` section and adds no §0 tracking row.**

**Prerequisite (E-257, satisfied).** `bb report reconcile-scoreboard --json` exists (commit `8b763a1`) and emits the axis-counter keys `dropped_pitch_events` / `no_plays_units` / `self_games` that the closure smoke consumes. The strict E-257→E-256 order recorded in the prior stub is discharged.

## Goals
- Delete the production-dead disk twin load flow and the dead-code residue the descope left behind (stories 01–03).
- Extract a client-free lifecycle/deletion module from `generator.py` and correct the third orphaned UTC site (stories 04–05).
- Stand up the absent foundations: `.dockerignore`, CI, dependency refresh, ruff, scheduled off-disk backups (stories 06–10).
- Give the reports flow its **first live runtime gate at closure** (story 11).
- Close the committed-artifact PII gap for planning trees and document the suppressor scope honestly (stories 13, 14, 16).

## Non-Goals
- **The query-time season-aggregate cutover.** Split to E-259 by user decision. E-256 must not change aggregate read/write semantics.
- **Removing `epics/` or `.project/` from `SKIP_PATHS`.** See Technical Notes §6 — the two PII gates catch disjoint classes, and this would reintroduce the noise TN-2 removed.
- **A blanket `tests/**` exemption in the PII scanner.** Ruled out; Technical Notes §6.
- **Deleting `scripts/smoke_test.py`.** Ruled out; Technical Notes §5.
- **Retargeting `smoke_test.py` at reports-era endpoints.** Real finding, captured as IDEA-109. Not this epic.
- **Chasing the retired suffixed-season taxonomy to its root.** Story 02 removes one more leaf of it. The root (on-disk `data/raw/<year>-<suffix>/` trees) is a standing user ask tracked separately. **Capture, do not chase.**
- Bug-fixing the live data path (that was CE-3 / E-253). The rest-day fix (story 05) is the sole exception: it is the orphaned third site of a systemic finding whose other two sites E-252 and E-253 already fixed.
- mypy. Explicitly deferred; ruff only.

## Success Criteria
- All stories DONE and the full suite green in the main checkout at closure.
- `.github/workflows/ci.yml` runs pytest + PII sweep + lockfile-drift + `docker build` on push.
- A fresh `git clone` builds via `docker compose build` with no missing-`data/seeds/` failure.
- `implement/SKILL.md` defines Step 1d, and `code-reviewer.md` authorizes CR to run it.
- No module under `src/` reads `data/raw/`.
- `pip-audit` reports zero known vulnerabilities for jinja2 and starlette.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-256-01 | Delete the disk-based twin load flow | TODO | None | software-engineer |
| E-256-02 | Delete the dead backfill-appearance-order command | TODO | None | software-engineer |
| E-256-03 | Dead-code sweep: bridge, discover_opponents, ghost dirs | TODO | None | software-engineer |
| E-256-04 | Extract a client-free lifecycle module from generator.py | TODO | E-256-03 | software-engineer |
| E-256-05 | Fix the rest-day reference date at all three UTC sites | TODO | E-256-04 | software-engineer |
| E-256-06 | Add .dockerignore; delete the orphaned data/seeds surface | TODO | None | software-engineer |
| E-256-07 | Dependency refresh and vulnerable-pin remediation | TODO | None | software-engineer |
| E-256-08 | Adopt ruff (F-class) | TODO | E-256-01, E-256-02, E-256-03, E-256-04, E-256-05, E-256-07 | software-engineer |
| E-256-09 | CI workflow (the static gate) | TODO | E-256-06, E-256-07, E-256-08, E-256-14 | software-engineer |
| E-256-10 | Operator docs/admin updates (backups + smoke pointer + seeds + backfill doc eviction) | TODO | E-256-02, E-256-06, E-256-11 | docs-writer |
| E-256-11 | Closure runtime smoke (Step 1d) | TODO | E-256-05, E-256-06 | claude-architect |
| E-256-12 | data-model.md dead-by-descope note | TODO | None | claude-architect |
| E-256-13 | Document the PII suppression mechanisms + choice hierarchy (12a-i) | TODO | None | claude-architect |
| E-256-14 | Gate planning artifacts with the doc-PII byte-gate | TODO | None | claude-architect |
| E-256-15 | Evict context-layer references to deleted surfaces | TODO | E-256-01, E-256-02, E-256-04, E-256-12 | claude-architect |
| E-256-16 | Eliminate the credential-parser test PII hit (12a-ii) | TODO | None | software-engineer |

## Dispatch Team
- software-engineer
- claude-architect
- docs-writer

## Technical Notes

### §1. Ordering with E-259 (strict: E-256 first)
E-259 (query-time season aggregates) executes **after** this epic. Three correct reasons, and one commonly-given reason that is **wrong**:

- **Correct.** The two epics collide on `_query_batting` / `_query_pitching`. Story 04 leaves them at a clean seam; E-259 rewrites them there.
- **Correct.** E-259 is the highest-risk read-path change in the backlog, and is exactly the populated-DB DELETE+rebuild regression class that fresh-DB goldens provably cannot see (E-247 F1). Step 1d should exist before it lands.
- **Correct.** Between E-256's close and E-259's DROP the stored tables **still exist**, so cache staleness remains a real and detectable divergence class — **and E-256's own closure sits inside that window.** Step 1d's `verify-aggregates` sub-check guards that interval. Omitting it would leave the interval unguarded in order to pre-pay for a deletion that has its own story.
- **WRONG — do not write this.** "E-259 could not pass its cutover gate otherwise." E-259's operator gate depends only on `bb report verify-aggregates` **existing in the tree**, not on Step 1d naming it.

### §2. It is Step 1d, not Step 1c
`.claude/skills/implement/SKILL.md:420` already defines **Step 1c** as the Closure CR Integration Review. The runtime smoke is **Step 1d**, wired into Step 8 as sub-step **5b**. Both `AGENTIC-FLOW-REVIEW.md` and the prior E-256 stub say "Step 1c"; both are wrong. This file corrects the stub. `AGENTIC-FLOW-REVIEW.md` is an uncommitted root artifact and is **not modified by this epic** — flagged, not corrected.

### §3. Step 1d design constraints
- **Runs in the main checkout, post-patch-apply**, alongside the Step 8 full-suite gate. The epic worktree has no `bb`, no Docker, no `.env`, no `data/`.
- **Runs against the LIVE dev DB, not a fixture DB.** A fresh fixture DB is empty, so `verify-aggregates` and `reconcile-scoreboard` would both pass **vacuously** — precisely the failure class Step 1d exists to close.
- **`bb report generate` runs BEFORE `reconcile-scoreboard`**, so the ratchet measures the state the smoke just produced.
- **Honest limitation, stated in the skill text.** Whole-game plays idempotency means the scoreboard cannot see an ingestion-parser change until data is re-ingested. Do not oversell the gate.
- **The smoke fixture is a gitignored two-field `.smoke-fixture` file at the repo root — NOT `.env`** (CA Q4). It holds `generate=<public_id>` (for `bb report generate`) and `morning-run=<lsb-url-1> <lsb-url-2> …` (positional team URLs for `bb report morning-run --dry-run`, which requires them per `report.py:608`) — both LSB's own real identifiers, neither committed. `.claude/hooks/secret-read-guard.sh` denies any Bash command literally naming `.env*` or `secrets/**`, so a fixture stored there would be unreadable by the reviewer that must read it. Morning-run's asserted invariant is **exit 0 only** (resolve-and-preview ran without crashing); its honest limitation (LSB usually has no games on an arbitrary closure date, so the resolution ladder doesn't fire — it gates entry-point wiring + schedule-read API path + `operating_today()` timezone plumbing, not end-to-end resolution) is stated in the skill text.
- **env-FAIL vs epic-FAIL.** Step 1d opens with a preflight (fixture present, stack up, creds live, baseline exists). **Preflight failures escalate to the user and hold the closure; they do NOT enter the remediation loop.** Only post-preflight failures are epic-FAILs. Without this split the smoke manufactures false remediation rounds on expired credentials.
- **CR self-evaluates the trigger.** The main session assigns Step 1d unconditionally; CR runs `git diff --cached --stat main` itself and reports "not triggered" when nothing matches. Routing that read through the main session would be a `dispatch-pattern.md` domain-work violation.
- **Trigger paths:** `src/reports/`, `src/db/`, `src/api/`, `src/gamechanger/loaders/`, `src/gamechanger/parsers/`, `migrations/`.
- **Two carve-outs are required in `.claude/agents/code-reviewer.md`, or the smoke is self-contradicting:** a named second exception in the **Test-Execution-Constraint** (beside the existing closure-pytest carve-out), AND an exception to **Anti-Pattern #5's read-only Bash allowlist** (`bb report generate` mutates the DB).
- Doc pointer for the smoke procedure: `docs/admin/production-deployment.md`.

### §4. The disk-flow deletion is a re-point, not a mass delete
159 test functions enter through a disk surface. **Only NINE genuinely die** — those whose *assertion is about the filesystem*. The remaining ~150 are **re-pointed** at `load_payload` / `load_from_data`; their subjects (boxscore parsing, team-key detection, `_find_duplicate_game` dedup, perspective tagging) are unaffected by which surface feeds them. **The gate is the criterion (filesystem-assertion), not the count** — the number is guidance; a test is deleted iff its assertion is about the filesystem. **Total assertion coverage must not drop.**

The nine filesystem-asserting deletions (SE-verified by reading each candidate, not by regex — the regex pass produced false positives):
- `tests/test_loaders/test_game_loader.py` (note the `test_loaders/` subdir): `test_no_games_dir_returns_empty_result`, `test_missing_summaries_file_returns_error`, `test_nonexistent_boxscore_file_returns_error`
- `tests/test_plays_loader.py`: `test_load_result_no_plays_dir`, `test_empty_plays_dir`
- `tests/test_scouting_loader.py`: `test_e247_disk_path_matches_in_memory`, `test_e247_disk_malformed_roster_counts_error`, `test_e247_disk_non_array_roster_counts_error`, `test_e247_disk_missing_roster_no_error`
- `tests/test_scouting_spray_loader.py`: `test_load_all_no_dirs_returns_empty_result`

**PORTS (not a deletion):** `tests/test_scouting_spray_loader.py::test_unknown_public_id_skips_directory` — its subject is `public_id` resolution, which `load_from_data` also performs, so it re-points rather than dies (SE's lean, committed per Codex's ten-vs-borderline reconciliation). This is why the count is nine, not ten.

Note the signal: **four of the ten are E-247's own guard tests for disk/in-memory parity.** The twin is exactly what E-247 was defending, at the cost of a stat-wiping near-miss on the live path.

### §5. `scripts/smoke_test.py` STAYS — and the flow review's binary is false
`AGENTIC-FLOW-REVIEW.md` says "wire it into CI or delete it." **Both branches are wrong.** It cannot go in CI (needs a live app + credentials) and must not be deleted: `tests/test_script_entry_points.py:102` tests it, and `docs/admin/operations.md:884` prescribes it as a credential-expiry recovery step. It remains a **manual operator step** and does **not** become a Step 1d command. Story 09 records this verdict explicitly so the next reader does not reopen it.

Separately, SE found that all three endpoints it probes (`/me/teams`, `/teams/{id}/game-summaries`, `/teams/{id}/players`) are **member-team endpoints the reports product abandoned in E-239** — so it proves credential liveness against a surface nobody uses, while `bb creds check` already proves liveness via a real authenticated `/me/user` call (`credentials.py:175`). Retargeting it is real work, captured as **IDEA-109**, and is **out of scope here**.

### §6. The two PII gates catch disjoint classes
- The **pattern scanner** (`src/safety/pii_scanner.py`) matches *shapes*. A 10-digit run looks like a phone number whether or not it is one — exactly the noise that put `epics/` and `.project/` into `SKIP_PATHS` (rationale comment tagged TN-2 at `src/safety/pii_patterns.py:168`).
- The **byte-gate** (`scripts/check_doc_pii.sh`) matches *literal known identifiers* from a denylist. A literal match in `epics/` is **never noise** — it is a real identifier in a committed file.

The byte-gate therefore extends coverage to the planning trees **without a single false positive**, and `SKIP_PATHS` **keeps** `epics/` and `.project/`. Story 14 must not modify `src/safety/pii_patterns.py`.

**Suppression mechanisms (both already shipped in E-254-06) and their TRUE scope:** per-line `# pii-ok` (`pii_scanner.py:151-153`, checked *before* the pattern loop) and the whole-file `synthetic-test-data` marker (`SYNTHETIC_MARKER`, `pii_scanner.py:145-148`, evaluated before the per-line loop). Both sit OUTSIDE the `COMPILED_PATTERNS` loop, so **both suppress ALL patterns including credential patterns** (`bearer_token`, `api_key_assignment`), not just shape heuristics — despite the names. This is by design and load-bearing (a synthetic auth fixture legitimately contains `Authorization: Bearer test-token-…`, which matches `bearer_token`). But it means a real credential behind either marker is silently unscanned — so a real credential value behind either marker is a **MUST FIX**, not a sanctioned suppression.

**Choice hierarchy (story 13 records this in `pii-safety.md`):** (1) **change the data** so no pattern matches — always preferred; leaves no standing suppression; (2) **line-scoped `# pii-ok`** on the one offending line; (3) **file-level `synthetic-test-data`** only for an end-to-end synthetic fixture, and **NEVER on a file that handles, parses, or could receive real credentials**. The credential-parser test file is the worst possible place for a file-level suppressor precisely because it is the file most likely to receive a real token when a dev pastes a curl to reproduce (story 16's fix follows this: change the fake value, not add a marker).

**A blanket `tests/**` exemption is rejected on evidence** (shape heuristics fire zero times) and on the visibility-to-review axis: a marker is a **literal token in the diff** that the reviewer sees (CLAUDE.md §4g then tells CR to scrutinize it), so suppression is an explicit, reviewable authorial act. A path exemption is **invisible in the diff** — every future fixture under `tests/` is silently unscanned for credentials forever, no author intent recorded, nothing for CR to look at. Independently, `email` / `bearer_token` / `api_key_assignment` MUST keep running on `tests/**` (CLAUDE.md names "test fixtures using real credentials" a MUST FIX), so any carve-out would have to be per-pattern — strictly worse than a marker.

**§4g is a review-time control, not a structural closure (CA ruling).** The reviewability argument above is why a marker beats a path exemption — but §4g does NOT close the staged-blob hole where a `GC_REFRESH_TOKEN=<real> # pii-ok` line is staged, scanned, certified clean, and never reviewed (an ad-hoc operator commit, an unread file, or a marker added in one epic with a real token added to that file epics later). Treating §4g as a closure would be the same category error as accepting Cloudflare as CSRF mitigation. That residual is a real hole, captured as **IDEA-112** (a measurement-first suppressor-narrowing idea — NOT this epic).

### §7. Byte-gate exit-code disposition in the commit hook
The pre-commit hook does **not** invoke the byte-gate today (`.githooks/pre-commit:21` runs only `python3 -m src.safety.pii_scanner --stdin`), so exit-3 semantics are a design decision this epic makes, not a live contradiction.

| Exit | Meaning | Hook behavior |
|---|---|---|
| 0 | REAL mode, zero matches | Pass; emit `[doc-pii: REAL, 0 matches]` |
| 1 | Denylisted identifier present | **BLOCK** |
| 2 | Self-test failed / malformed denylist | **BLOCK** (fail closed) |
| 3 | Denylist absent → EXAMPLE MODE | **Announce loudly, do NOT block**; emit `[doc-pii: INCONCLUSIVE — example mode]` |

`.claude/rules/pii-safety.md` says exit 3 "MUST NOT be recorded as a pass" — it does **not** say "must block." Emitting a *different confirmation token* satisfies both: **the announcement IS the not-recorded-as-a-pass.** Exit 2 blocking follows the `pii-check.sh:37-58` precedent (a broken scanner must not let a commit through).

Blocking on exit 3 would destroy the gate. The denylist is gitignored, so **exit 3 is the default state on every fresh clone**; a hook that makes a fresh clone uncommittable is uninstalled within a day, and then nothing runs — including the exit-1 detection that is the entire point. **CI never invokes the byte-gate**, so exit 3 never arises on a runner.

### §8. Byte-gate wrapper: the index-vs-working-tree hazard
`scripts/check_doc_pii.sh` takes **exactly one** positional arg (`TARGET="${1:-}"`; extras silently ignored) and **requires a directory** (`[ ! -d "$TARGET" ]` → exit 2). All three matchers are `grep -r`. Multiple trees are handled by invoking it once per tree and aggregating exit codes — **no script change**.

The real hazard: **the byte-gate greps the WORKING TREE, but a commit hook must judge the INDEX.** These diverge under `git add -p`, or staged-then-edited. A working-tree grep in a commit hook lets a real identifier ride into the commit while the gate greps a clean working copy — a **false pass**, strictly worse than the exit-3 inconclusive we chose to tolerate.

Design: `git checkout-index --prefix="$tmp/" -a` into a `mktemp -d`, invoke `check_doc_pii.sh "$tmp/<tree>"` once per tree, aggregate exit codes, `rm -rf`. The temp path is a directory, so the `-d` guard passes. **Zero modification to `check_doc_pii.sh`** — its single-directory contract, self-test, and four exit codes all survive. The wrapper lives in `.githooks/pre-commit`, where the staged-vs-worktree concern belongs. Do **not** teach the script a `--staged` mode; that duplicates `git checkout-index` inside a script whose entire value is being a small, self-testing, PII-free harness.

### §9. `data/seeds/` — DELETE, do not commit
Git forensics (SE): commit `cf176e8`'s message claims it deleted `seed_dev.sql`, but `--diff-filter=D` shows it deleted **only `scripts/seed_dev.py`**. The SQL file was **never tracked** — the author's local `rm` left no git trace, so the file survives on every pre-E-228 machine while `git ls-files data/` is empty. `cf176e8` touched neither `Dockerfile` nor `.gitignore`; that is the orphan.

Committing it would resurrect ~21 KB of demo data E-228 removed on purpose, and contradict the documented `bb db reset` empty-DB invariant (`.claude/rules/data-model.md`).

### §10. `backup.py` — the audit's stated reason is wrong
"Invoked by nothing" is **false**: `src/db/backup.py::backup_database` is the live `bb db backup` command (`src/cli/db.py:11,43`), with `scripts/backup_db.py:40` a second wrapper, prescribed in three docs. A story author working from the audit's wording would hunt for a caller that already exists and conclude the finding was stale.

The real finding is two-part: (a) **nothing schedules it**, and (b) `_BACKUPS_DIR = _PROJECT_ROOT / "data" / "backups"` (`src/db/backup.py:20`) is **inside the same host-mounted `./data` volume as `app.db`** — one disk loss destroys the database and every backup together.

### §11. Dependency refresh moves ~11 packages, not 2
SE ran the full suite against the upgraded stack in an isolated venv: **`3849 passed, RC=0`**. Target: `fastapi==0.139.0` + `starlette==1.3.1`, plus jinja2 3.1.6, matplotlib 3.11.0, numpy 2.5.1, uvicorn 0.51.0, typer 0.26.8, webauthn 2.8.0, python-multipart 0.0.32. FastAPI 0.139 dropped its starlette upper bound entirely, permanently un-sticking future starlette patches. Only `requirements.in:9` (`starlette~=0.41`) needs widening — `fastapi~=0.115` already permits 0.139.

The matplotlib 3.10.8→3.11.0 move **resolves** the existing drift (the suite already runs 3.11.0 via the unpinned devcontainer editable install). State the ~11-package scope in the story or a reviewer reads it as scope creep.

### §12. ruff scope
**17 F-class violations in `src/`** (8 F401, 5 F541, 4 F841), not the audit's 12; 22 including `scripts/`. Repo-wide 96, of which **6 are false positives** — F821 undefined-name in `tests/test_cli_creds.py`, all string return annotations paired with function-local imports, never evaluated at runtime; the clean fix is a `TYPE_CHECKING` block. Config: `[tool.ruff.lint] select = ["F"]`, scoped initially to `src/` + `scripts/`. Two F841s sit in code story 02 deletes (`backfill.py:184-185`); one deserves its own look (`src/api/routes/auth.py:648`, `existing_creds` assigned never used). **mypy is explicitly skipped.**

### §13. `generator.py` split (lifecycle extraction)
`generator.py` is **3,034 lines** (not the stub's 2,792). Target: `src/reports/lifecycle.py`, client-free, ~640 lines — the contiguous deletion tail (`generator.py:2577-3034`) plus the scattered lifecycle helpers. SE verified **zero** references to any heavy import (`GameChangerClient`, crawlers, loaders, `render_report`, `reconcile_game`, `parse_team_url`, `CredentialExpiredError`) across the moved regions. `_utcnow_iso` is publicized as `utcnow_iso`, killing the cross-module underscore imports at `morning_run.py:52` and `reports_admin.py:541` in one stroke. SE asks for **two commits** — contiguous tail first — because `generate_report` sits at `:1655` *between* the two blocks.

### §14. The season-fetch seam — DE's relocation contract (E-256 relocates the fetch; E-259 substitutes the SQL)
**FINAL contract (option (c) was rejected).** SE conceded to DE after verifying in code that `_query_batting` ends `_apply_name_cascade` and `_query_pitching` ends `_apply_name_cascade` + `_compute_pitching_rates` (which writes the display strings `era`/`k9`/`whip`/`strike_pct`). SE's earlier objection rested on a false premise — E-259 does NOT supersede the relocation; it substitutes the *SQL body inside* the already-relocated pure function, so the move is a **prerequisite**, not wasted work.

- **E-256 (story 04)**: extract the pure SQL fetch into `src/api/db.py` as `get_season_batting`/`get_season_pitching(conn, team_id, season_id) -> list[dict]`. `_query_batting`/`_query_pitching` **stay in `generator.py`** as thin wrappers: fetch → `_apply_name_cascade` → (pitching) `_compute_pitching_rates`. The presentation helpers stay in `src/reports/`.
- **E-259 (its story 01)**: rewrite ONLY the SQL body inside `get_season_batting`/`get_season_pitching` against `player_game_*`, adding the `perspective_team_id` filter, in one hunk.

**Why (c) loses (record verbatim):** E-259's whole risk is one silent semantic change — the perspective filter, whose failure is a plausible-looking double-count. Under DE's contract E-259's diff is **old-SQL-vs-new-SQL side by side**. Under (c) E-259 would be a delete-from-`generator.py` + add-to-`db.py`-with-different-SQL, which git renders as a delete plus an unrelated-looking add — the reviewer **never sees the old-vs-new SQL diff at all**. Relocate where relocation is cheap (E-256); substitute where the diff must be legible (E-259).

**Acyclicity (record verbatim):** the *fetch-only* move is what keeps the import graph acyclic. `src/api/db.py` is a clean stdlib + `src.db.paths` leaf and the pure fetches add no imports. A **wholesale** move (dragging `_apply_name_cascade`/`_compute_pitching_rates` into `db.py`) WOULD create a cycle, because those are report-layer helpers and `generator.py:29-35` already imports *from* `src.api.db`. DE's split doesn't just improve layering — it is what prevents the cycle. So the fetch relocates; the presentation helpers do NOT.

**SE's two clarifications to DE's contract (both adopted):**
1. **Dict-keys scope qualifier (critical — prevents an implementer error).** "Do not change the returned dict keys" means *the wrapper's* keys. `get_season_pitching` returns rows **WITHOUT** `era`/`k9`/`whip`/`strike_pct` — those are created by `_compute_pitching_rates`, which stays in reports. Stated loosely, an implementer could conclude the fetch must return `era` and drag the formatter along (re-introducing the cycle). The fetch returns the **raw SUM columns**; the *wrapper* output is golden-stable.
2. **ORDER BY is an E-259 flag, not E-256.** Both clauses currently order over stored aggregate columns (`_query_batting`: `(ab+bb+hbp+shf) DESC, last_name ASC`; `_query_pitching`: `COALESCE(psp.ip_outs,0) DESC, last_name ASC`). In E-256 this is a **pure relocation** (unchanged). In E-259 they become expressions over per-game SUMs — E-259 must **reproduce the same ordering semantics over the new projection**. Named in E-259's story now so it is not discovered mid-cutover.

**Golden test:** zero-diff through both epics, via the **wrapper** (not the fetch). `tests/test_report_golden.py` calls `_query_batting`/`_query_pitching` and sees the composed output, which is stable across relocation (E-256) and SQL-swap (E-259). **Neither epic may touch the golden test to make itself pass.**

E-256's contract for story 04's fetch relocation:
1. Extract `get_season_batting`/`get_season_pitching(conn, team_id, season_id) -> list[dict]` into `src/api/db.py`, returning the **raw SUM columns** (no `era`/`k9`/`whip`/`strike_pct`).
2. `_query_*` stay in `generator.py` as thin wrappers: fetch → `_apply_name_cascade` → (pitching) `_compute_pitching_rates`.
3. Keep the ORDER BY clauses and dict keys **as they are** — pure relocation, no semantic change; the perspective filter and the SUM-expression ORDER BY are E-259's.
4. Do **not** move `_apply_name_cascade`/`_compute_pitching_rates` — they stay in `src/reports/` (acyclicity).
5. Do **not** delete `batting_recompute_select()`/`pitching_recompute_select()` from `src/db/season_aggregates.py` — E-259 uses them so exactly one SUM projection survives.
6. **Golden test unchanged — no import edits, no expectation edits, zero diff.**

### §15. Backfill-appearance-order eviction is grep-and-reconcile, routed by ownership (NOT a hand-list)
Deleting `bb data backfill-appearance-order` (story 02) requires evicting its references across code, docs, context layer, and agent memory. Codex round 2 proved the hand-listed set undercounts: the story's original 2 surfaces → Codex's +3 → PM's whole-repo grep found ~11. The durable fix (IDEA-115): **story 02 runs the authoritative repo-wide grep** (`backfill.appearance.order` across `src/ scripts/ tests/ docs/ .claude/ CLAUDE.md docs/ROADMAP.md`), reconciles the surfaces it owns, and routes the rest. **The list below is a SEED, not a ceiling** — the grep at implement time is authoritative; a reference not listed here that the grep finds is still in scope.

Routing table (owner ← surface):

| Owner (story) | Surfaces (seed) |
|---|---|
| **software-engineer (02)** | `src/cli/__init__.py` (command-list docstring); `src/db/backfill_game_dates.py`, `src/gamechanger/loaders/plays_reload.py` (precedent docstrings — re-point to a surviving precedent); `tests/test_cli_data.py` (command-list references); plus the deletion-target files 02 removes outright |
| **docs-writer (10)** | `docs/admin/operations.md` (backfill runbook section + precedent refs), AC-6 |
| **claude-architect (15)** | `CLAUDE.md` (Commands sentence + Footgun note); `.claude/rules/data-model.md` (mention + `verify-aggregates` footgun), AC-3 |
| **owning agent (closure)** | `.claude/agent-memory/code-reviewer/recompute_tail_noop_populated_db.md`; `.claude/agent-memory/data-engineer/season_tables_are_a_pure_cache.md` — reconciled by each owning agent; since neither is on E-256's team, PM flags them for a main-session follow-up sweep at closure (reconcile-not-strike: a reference is a candidate, not an automatic strike) |
| **product-manager (closure)** | `docs/ROADMAP.md:219,376` (the "QUARANTINE, deletion-guarded" cruft verdict + "survives" note → annotate "QUARANTINE → DELETED by E-256"; strategic/PM-owned, docs-writer must not edit ROADMAP); PM's own `.claude/agent-memory/product-manager/MEMORY.md` (Memory Retirement) |

Doc-sweep discipline (`.claude/rules/doc-sweep.md`) applies to every prose surface: token grep + synonym expansion + semantic read.

## Open Questions
- None. The season-fetch seam (formerly the sole open question) is resolved as **DE's relocation contract** — E-256 relocates the pure fetch to `src/api/db.py`, E-259 substitutes the SQL body in place (Technical Notes §14). Option (c) was rejected.

## History
- 2026-07-04: Created as a DRAFT capture stub from the platform audit (CE-6).
- 2026-07-07: agentic-flow-review items registered; E-257→E-256 sequencing made strict.
- 2026-07-07: CA design review corrections applied.
- 2026-07-09: Refined to full DRAFT. Aggregate cutover split out to E-259 (user decision). E-257 landed, discharging the upstream dependency. Expert consultation completed with software-engineer, data-engineer, and claude-architect. Flow-review item 12 pulled into scope (user decision). Promotes IDEA-102. Captures IDEA-109/110/111.
- 2026-07-09 (final rulings): **Season-fetch seam resolved as DE's relocation contract** — E-256 relocates the pure fetch to `src/api/db.py`, E-259 substitutes the SQL body in place (option (c) rejected; Technical Notes §14). **Item 12a split into two stories** by routing: 13 (claude-architect, `pii-safety.md` + choice hierarchy) and **16 (software-engineer, `tests/test_credential_parser.py:81` fixture fix)** — 16 stories total. §4g ruled a review-time control, NOT a structural closure; the staged-blob residual captured as **IDEA-112** (measurement-first suppressor narrowing, sibling of E-254, NOT this epic).
- 2026-07-09 (internal review + Codex): CR spec audit + SE/DE/CA holistics + Codex spec-review incorporated. **CA routing rule (Q1)** applied — no story carries a mandatory cross-domain edit: E-256-02's CLAUDE.md edit folded into story 15 (CA); the `docs/admin/` edits from stories 06 (architecture.md seeds) and 11 (production-deployment.md smoke procedure) consolidated into **story 10** (docs-writer), which is retitled "Operator docs/admin updates" and is now the epic's SOLE `docs/admin/` owner. Same-file collision edges added post-refactor: 11 blockedBy 06 (`.gitignore`), 15 blockedBy 12 (`data-model.md`), 10 blockedBy 06 (seeds line follows the surface removal); the 10↔11 `production-deployment.md` collision DISSOLVED (11 now only references the doc). Mechanical fixes: E-256-09 PII CI invocation pinned (bare command is a no-op), E-256-01 AC-3 reconciled to nine filesystem-asserting deletions (criterion is the gate, `test_unknown_public_id_skips_directory` ports), E-256-03 api-scout-skip rationale added (dead code). **CA Q4 (E-256-11):** `.smoke-fixture` widened to two labeled fields (`generate=` + `morning-run=`); morning-run `--dry-run` kept with an **exit-0-only** invariant + a stated honest limitation (gates entry-point/schedule-API/timezone plumbing, not the resolution ladder), order-independent after `curl /health`; preflight requires both fields non-empty (env-FAIL if missing). Story count unchanged at 16.
- 2026-07-09 (Codex round 2, 2 findings incorporated — circuit breaker, no round 3): **P1 dependency correctness** — the round-1 Q1 routing refactor made story 10 consume story 11's Step 1d smoke procedure but only added `10←06`; added `E-256-10 blockedBy E-256-11` (acyclic: 11←05,06, no back-edge). **P2 propagation completeness** — the `backfill-appearance-order` eviction was incomplete (story's 2 surfaces → Codex's +3 → PM's whole-repo grep ~11). Reframed story 02's eviction as an **authoritative repo-wide grep-and-reconcile routed by ownership** (new §15 routing table + AC-3): SE (02) owns the grep + its `src/`/`tests/` surfaces (`cli/__init__.py`, two precedent docstrings, `test_cli_data.py`); `docs/admin/operations.md`→story 10 (new AC-6, `10←02`); context-layer CLAUDE.md/data-model.md→story 15 (AC-3 tied to §15); agent-memory (code-reviewer, data-engineer) → owning-agent closure sweep (PM-flagged, off-team); `docs/ROADMAP.md:219,376` + PM's own memory → PM closure. Surfaces are a SEED not a ceiling (IDEA-115 captures the recurring hand-list-undercount lesson, routed to CA). Story count unchanged at 16.
- 2026-07-09 (**READY** — review scorecard). Set READY after two Codex iterations plus internal review (circuit breaker — no third round). Review-Scorecard:

  | Pass | Findings | Accepted | Dismissed |
  |---|---|---|---|
  | Internal iter 1 — CR spec audit | 7 (session) | 5 | **2** (CR F4 story-04 sizing; CR F6 morning-run `--dry-run` email — both refuted against code, `report.py:581`/`:666`) |
  | Internal iter 1 — holistic (SE/DE/CA) | SE 3, DE 3, CA 4 (GAP-1/GAP-2 + 2 nits) | all | 0 |
  | Codex round 1 | 8 | 8 | 0 (shaped by CA rulings Q1–Q4) |
  | Codex round 2 | 2 | 2 | 0 |
  | **Total (E-256)** | — | — | **2, both internal-CR (not Codex)** |

  Notes: the CR spec-audit and SE/DE/CA holistic passes were session-wide (both epics); the 2 dismissals are E-256 (CR false-positives). Codex rows are E-256-specific. Story count 16 unchanged across every pass. The only two Codex-round dismissals across the session were zero — every Codex finding (round 1 + round 2, both epics) was accepted or resolved via a CA ruling.
