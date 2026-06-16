# E-239 Spec Audit — code-reviewer (planning-phase), internal iteration 1

**Reviewer:** code-reviewer (spec-audit mode, not code review)
**Date:** 2026-06-16
**Scope reviewed:** all 7 epic/story files (`epic.md`, `E-239-01`…`E-239-06`), both recon artifacts (`.project/research/E-239-deletion-inventory.md`, `.project/research/E-239-season-machinery.md`), and `docs/ROADMAP.md` context. Load-bearing recon claims (§5 nav coupling, admin.py global registration) verified against live `main` code.

**Summary:** 2 MUST FIX, 4 SHOULD FIX, 1 minor note. Well-specified deletion epic overall — preserves are LOUD, the DAG is internally consistent, the shared `db.py` edit is correctly serialized, and the operator-run canary is correctly an epic-closure gate.

---

## MUST FIX

### Finding 1 — `base.html` nav cleanup is assigned to NO story
- **Severity:** MUST FIX
- **Location:** recon `E-239-deletion-inventory.md §5`; gap manifests in `E-239-02` and `E-239-03` (neither lists `base.html`); also absent from `epic.md`.
- **Criterion violated:** #6 (coverage-loss trap) and #2 (file ownership / coverage gap).
- **Description:** Verified against live code: `src/api/templates/base.html:14` is `<a href="/admin/teams">Admin</a>` (the `/admin/teams` route is deleted in Story 03), and `base.html:32/37/42` are bottom-nav links to `/dashboard`, `/dashboard/batting`, `/dashboard/pitching` (routes deleted in Story 02). `base.html` appears in zero story files. After removal, the global top-nav Admin link and the bottom-nav point at deleted routes → 404s in live nav on the surviving reports surface. Recon §5 explicitly calls for both edits.
- **Suggested fix:** Add `base.html` to **Story 02** Files list + an AC (remove the dashboard bottom-nav block, lines 32-42) and to **Story 03** Files list + an AC (retarget the Admin link, line 14, to `/admin/reports`).

### Finding 2 — `get_unresolved_opponent_count` module-level import + Jinja global registration not in any AC
- **Severity:** MUST FIX
- **Location:** Story `E-239-03` (AC-3 deletes the db.py helper); live `src/api/routes/admin.py:60` (`from … import get_unresolved_opponent_count`) and `admin.py:90` (`templates.env.globals["get_unresolved_opponent_count"] = get_unresolved_opponent_count`).
- **Criterion violated:** #1 (AC specificity) — latent app-startup break.
- **Description:** Story 03 AC-3 deletes the `get_unresolved_opponent_count` helper from `db.py` but never names the admin.py-side module-level import (L60) or the Jinja global registration (L90). An implementer following the ACs literally would delete the helper and leave L60/L90 in place → `ImportError`/`NameError` at app import. Recon §5 explicitly requires dropping both the registration and its import.
- **Suggested fix:** Add an explicit Story 03 AC: "Remove the `get_unresolved_opponent_count` module-level import (admin.py:60) and its `templates.env.globals[...]` registration (admin.py:90) together with the helper deletion."

---

## SHOULD FIX

### Finding 3 — Decoupling-approach choice diverges from the SE recon and is under-justified
- **Severity:** SHOULD FIX
- **Location:** `epic.md` §15 (import hazard); `E-239-01` Context; `E-239-03` Context.
- **Criterion violated:** #4 (Technical Notes completeness / approach justification).
- **Description:** SE recon §1 explicitly recommends approach **(a) extraction-then-delete** and states "Prefer this over (b) trim-in-place / lazy-import," giving four reasons (lowest churn; severs all four problem imports — `trigger`, `bridge`, `team_resolver`, `merge` — at once; removal stories `git rm` whole files; no lingering dead imports). The epic silently chose **(b) lazy-import + trim-in-place**. Story 03 even asserts "the cleanest path is to trim in place… since the surviving routes can't be cleanly separated," directly contradicting the recon. The choice may be defensible (more incremental, smaller per-story blast radius), but the epic should record *why* it overrode an explicit recon recommendation, and acknowledge the consequence: the lazy-import choice is precisely what makes Story 03 oversized (Finding 4) — under extraction, admin.py is git-rm'd and Story 03 nearly disappears.
- **Suggested fix:** Add a short rationale (epic Technical Notes or Story 01 Context) explaining the lazy-import/trim-in-place decision over the SE-recommended extraction, rebutting the recon's four reasons — or reconsider adopting extraction.

### Finding 4 — Story 03 is oversized; recommend split
- **Severity:** SHOULD FIX
- **Location:** `E-239-03` (whole story); flagged in `epic.md` Open Questions.
- **Criterion violated:** #3 (story sizing).
- **Description:** Confirmed large for one session: teams CRUD (~6 routes: list/add/confirm/edit/toggle-active/delete) + team merge + team sync + opponents (connect/resolve/disconnect) + programs + 8 templates + ~10 `db.py` opponent/finalize helpers + `_subnav.html` + (Finding 1) base.html + (Finding 2) the global-registration drop — all by trimming a ~3400-line file in place.
- **Suggested fix:** Split along route-group lines: **03a** = teams CRUD + merge + sync routes/templates + base.html Admin-link retarget; **03b** = opponents + programs routes/templates + the `db.py` opponent/finalize helpers + `_subnav` + global-registration drop. Confines the shared `db.py` edit to a single story (03b), still serialized after 02. (Moot if extraction per Finding 3 is adopted.)

### Finding 5 — Story 03 specifies cleaning only the `merge` module-level import, not the other now-dead ones
- **Severity:** SHOULD FIX
- **Location:** `E-239-03` Technical Approach.
- **Criterion violated:** #1 (specificity).
- **Description:** Story 03 explicitly handles removing `from src.db.merge import …` from admin.py, but is silent on the other module-level imports the deleted routes use — `from src.gamechanger.team_resolver import …` (recon §1, lines 71-75) and `from src.gamechanger.bridge import …` (lines 66-69). Because `team_resolver` is preserved and `bridge` survives, leaving these is not a startup break — but it produces dead imports, the exact "lingering dead imports" downside the recon attributes to trim-in-place.
- **Suggested fix:** Have Story 03 specify cleaning *all* now-unused module-level imports left behind by the deleted routes (team_resolver, bridge, merge), not only `merge`.

### Finding 6 — `test_strike_pct.py` coverage-loss confirmation not encoded as an AC
- **Severity:** SHOULD FIX
- **Location:** `E-239-02` AC-6; recon `E-239-deletion-inventory.md §4` (⚠️ note on `test_strike_pct.py`).
- **Criterion violated:** #6 (coverage-loss trap).
- **Description:** Recon §4 flags that `test_strike_pct.py` exercises the dashboard-local `_compute_*_pitching_rates` duplicates, and deleting it is safe *only if* report-side strike_pct stays covered by `test_report_workload.py` / `test_report_generator.py` (reports have an independent `_compute_pitching_rates` at `generator.py:484`). Story 02 AC-6 deletes dashboard tests generically but does not encode this coverage-confirmation step, so protected-core strike_pct coverage could be silently dropped.
- **Suggested fix:** Add a one-line Story 02 AC requiring confirmation that report-side strike_pct coverage survives (`test_report_workload.py` / `test_report_generator.py`) before deleting `test_strike_pct.py`.

---

## Minor (note, not a finding)

- Story 06 (claude-architect) edits `docs/ROADMAP.md §0` to flip slice D2 → COMPLETED. ROADMAP §0 flips are normally a PM/main planning-commit + closure action; bundling the flip into the context-layer story is slightly off-owner but harmless.

---

## Verified clean

- **Dependency DAG** matches across the epic story table and individual story files: 01→{02,03,04,05}; 02 blockedBy 01; 03 blockedBy 01+02; 04 blockedBy 01; 05 blockedBy 02+03+04; 06 blockedBy 02-05.
- **File-ownership serialization** correct: `src/api/db.py` (02 then 03 — 03 blockedBy 02), `src/api/routes/admin.py` (01 then 03), `src/cli/data.py` (01 then 04), `src/api/main.py` (02 only). No unserialized shared-file conflict.
- **Context-layer routing** clean: deletion stories 02-05 touch no `.claude/` path; Story 06 is the sole home for context-layer edits and is gated on 05; no deletion story edits a rule's `paths:` frontmatter (06 AC-6 cleans dangling frontmatter after code deletion).
- **Preserve set** well-specified: `gc_uuid_resolver.py` (05 AC-2, LOUD), `game_loader.py`/`plays_loader.py`/`backfill.py` (05 AC-3), season-derivation primitive + `seasons` table (02 AC-3 / Technical Notes §C), report-delete cascade (03 AC-4).
