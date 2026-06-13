# Spec Audit — E-235 (internal review iteration 1 of 3)

Auditor: code-reviewer (spec-audit mode)
Date: 2026-06-13
Scope: epic.md + E-235-01..07 against the 9 spec-review criteria supplied by main session.
Grounding: referenced code anchors verified against the live tree (`generate_report` @ generator.py:987, `cascade_delete_team` @ 1596, `cleanup_orphan_teams` @ 1652, `is_team_eligible_for_cleanup` @ 1712, `list_reports` @ 1785; `_delete_report` @ admin.py:3233, `_get_all_reports` @ 3213, `_get_delete_confirmation_data` @ 677, `cross_persp_rows` @ 830; `scouting_runs` precedent in migrations/001; `reports.status` is free-text TEXT with no CHECK; migration 001 is the only existing migration → 002 is the correct next number).

---

## SUMMARY VERDICT
- **1 MUST FIX** (F1 — dependency graph does not serialize the generator.py edit chain it claims to).
- **3 SHOULD FIX** (F2, F3, F4).
- **3 NOTE** (F5, F6, F7).
- **PASS** on: Technical Notes completeness (TN-1..TN-8 all present and sufficiently detailed), scope boundary (no story drifts into aggregate recomputation — Epic C stays out), producer/consumer split (03 edits generator.py, 07 edits renderer.py+template — genuinely disjoint, serialized by 07←03), cleanup-mirror path coverage (story 05 enumerates _delete_report, cascade_delete_team, _get_delete_confirmation_data/cross_persp_rows + the PRAGMA caveat), and AC testability overall (the few soft spots are F5/F6).

---

## F1 — MUST FIX — Dependency graph does NOT serialize the generator.py edit chain that TN-8 claims
**Location:** epic.md Stories table (lines 58–63); E-235-04 Dependencies ("Blocked by: E-235-02"); E-235-05 Dependencies ("Blocked by: E-235-01, E-235-04").
**Criteria violated:** #2 (dependency correctness), #5 (file ownership conflicts), and the project rule in `.claude/rules/project-management.md`: *"Stories that touch the same files MUST have explicit dependency ordering."*

**Description:** TN-8 (epic.md line 143) asserts: *"stories 02→03→04→05 all touch `src/reports/generator.py`; ... The dependency chain serializes these so each builds on the prior staged state."* The actual dependency graph does **not** encode that linear chain:
- 03 blocked-by **02**
- 04 blocked-by **02** (NOT 03)
- 05 blocked-by **01, 04** (NOT 03)

So 03 and 04 are **parallel siblings** (both gated only on 02), and 05 is gated on 04 but not 03. All three (03, 04, 05) modify `src/reports/generator.py` — and there is **no explicit ordering between 03 and 04, nor between 03 and 05**. Under the project's within-epic parallelism, 03 and 04 can be dispatched concurrently, producing conflicting concurrent edits to `generate_report()`. This both (a) violates the documented same-file-ordering rule and (b) directly contradicts TN-8's serialization claim — the metadata and the Technical Note disagree.

**Suggested fix:** Make the chain linear to match TN-8:
- E-235-04: change "Blocked by" from **E-235-02** → **E-235-03**.
- E-235-05: keep "Blocked by: E-235-01, E-235-04" (now transitively after 03 via 04←03).
- Update **both** the epic.md Stories table (Dependencies column) and the individual story files' Dependencies sections so they agree.
Result: 02→03→04→05 is a true linear chain on generator.py; 06 (blocked-by 03,05) and 07 (blocked-by 03) remain correct transitively.

---

## F2 — SHOULD FIX — Story 06 touches generator.py but carries no criterion-7 no-behavior-change / E-234-guard AC
**Location:** E-235-06 — Files to Create or Modify lists `src/reports/generator.py` (`list_reports()` join); ACs/DoD.
**Criterion:** #7 (restructure-as-refactor constraint: *every* story touching generator.py carries the no-behavior-change-asserted-against-E-234 AC).

**Description:** Story 06 modifies `list_reports()` in generator.py but has no E-234 guard AC; its DoD only says "No regressions in existing tests." Criterion 7 is literal: every generator.py-touching story must carry the assertion. (Mitigant: `list_reports()` is a read/list path disjoint from `generate_report()`'s stat computation, so the golden stat tables arguably do not apply — which is exactly why this should be stated rather than left implicit.)

**Suggested fix:** Either (a) add a short AC/DoD line to story 06 — "E-234 guards stay green; the `list_reports()` edit is read-path only and does not touch `generate_report()` stat output" — or (b) explicitly document in the story that the golden-assertion AC is N/A because list_reports is disjoint from the stat-generation path. Pick one so the criterion-7 sweep resolves explicitly instead of silently.

---

## F3 — SHOULD FIX — Story 04's E-234 assertion is weaker/less specific than 02 and 03
**Location:** E-235-04 AC-5 ("E-234 guards stay green").
**Criterion:** #7.

**Description:** 02 AC-6 and 03 AC-6 name the specific guards (golden stat-table test, aggregate-parity test, E-234-04 negative-path tests). 04 AC-5 only says "E-234 guards stay green." Story 04 changes the orphan-cleanup/team-deletion path — which manipulates `teams` rows that the goldens and negative-path tests depend on — so the verification surface should be named as precisely here as in 02/03.

**Suggested fix:** Mirror 02/03 wording in 04 AC-5: enumerate golden + aggregate-parity + E-234-04 negative-path tests explicitly.

---

## F4 — SHOULD FIX — Cleanup-mirror: the two-connection structure of `_delete_report` is not reflected in TN-5 / story 05
**Location:** E-235-05 AC-1; epic.md TN-5 (lines 117–121).
**Criteria:** #9 (cleanup-mirror completeness), #6 (interface clarity for the implementer).

**Description:** `_delete_report` (admin.py:3233) uses **two separate connections**: conn1 runs `DELETE FROM reports WHERE id = ?` and **commits**, then a *new* conn2 runs `cascade_delete_team`. Consequences the spec doesn't surface:
- If story 05 uses the explicit-delete mechanism, `DELETE FROM report_generation_runs WHERE report_id = ?` MUST run in **conn1, before `DELETE FROM reports`** (FK ordering, same transaction) — putting it in the cascade block (conn2) is too late and would already have hit the FK.
- If story 05 relies on `ON DELETE CASCADE`, the pragma `foreign_keys = ON` must be confirmed on **conn1 specifically** (the connection that deletes the reports row), and it must be verified that `get_connection()` sets that pragma (story 05 should confirm, not assume, the factory's pragma state).

TN-5/AC-1 say "verify the pragma on the delete-path connection," which is correct but does not call out the two-connection split — the most likely place to get this wrong.

**Suggested fix:** Add to TN-5 (and story 05 context) that the run-row removal must land in the same connection/transaction that deletes the `reports` row (conn1), before its commit; conn2's cascade runs afterward and cannot satisfy the FK on the reports delete. Direct story 05 to confirm `get_connection()`'s `foreign_keys` pragma state explicitly.

---

## F5 — NOTE — Story 04 AC-3 mixes a process gate into a testable AC
**Location:** E-235-04 AC-3 ("Mechanism is SE's call with SE+DE aligned before the story freezes").
**Criterion:** #1 (AC testability).

**Description:** "SE+DE aligned before the story freezes" is a planning/process gate, not verifiable by reading the implementation. The verifiable content (per-run attribution OR DB-backed lock with stale-lock recovery + no write-lock held across the network crawl) is present and good. The alignment clause already appears in Notes (line 48) and epic Open Questions (line 147), so the AC line is the wrong home for it.

**Suggested fix:** Trim AC-3 to the verifiable mechanism properties; leave the "SE+DE alignment before freeze" gate in Notes/Open Questions where it already lives.

---

## F6 — NOTE — Story 05 AC-3 "documents the conclusion" has no specified location
**Location:** E-235-05 AC-3.
**Criterion:** #1 (AC testability).

**Description:** AC-3 requires the audit to "explicitly determine whether `report_generation_runs` belongs in the `cross_persp_rows` UNION and document the conclusion," but does not say *where* the conclusion is recorded — making "documented" unverifiable.

**Suggested fix:** Name the artifact (e.g., a code comment at the `cross_persp_rows` site in admin.py, or the story's Notes section) so a reviewer can confirm the conclusion was recorded.

---

## F7 — NOTE — Story sizing: 02 is the heaviest unit but is appropriately bounded; flag for monitoring, do NOT split
**Location:** E-235-02.
**Criterion:** #3 (story sizing).

**Description:** Story 02 restructures a ~390-line function into 7 named stages + a context/run-record-handle object + run-record writes + new tests + E-234 verification. It is genuinely the largest unit. Assessment: it is a single cohesive atomic refactor and should **not** be split — a partial extraction cannot satisfy the "no behavior change, asserted against goldens" constraint (goldens would be red mid-restructure with no clean assertion point). Splitting would increase, not decrease, risk.

**Suggested fix:** None required. Recommend dispatch note: review 02 as one atomic refactor; the implementer should run the E-234 goldens continuously during the extraction and treat any drift as a defect (already captured in story 02 Notes).

---

## Criteria coverage ledger
| # | Criterion | Result |
|---|-----------|--------|
| 1 | AC testability/specificity | PASS w/ F5, F6 (two soft ACs) |
| 2 | Dependency correctness (incl. 03↔04 file conflict, 03→07 producer/consumer split) | **F1 (MUST)** for 03/04/05; producer/consumer (03→07) PASS |
| 3 | Story sizing (02 heaviest) | PASS — F7 (appropriately bounded, do not split) |
| 4 | Technical Notes completeness (TN-1..TN-8) | PASS (all present, detailed, no phantom refs) |
| 5 | File ownership conflicts | **F1 (MUST)** — same as #2 |
| 6 | Interface definitions for inter-story deps | PASS w/ F4 (cleanup-mirror connection detail) |
| 7 | Restructure-as-refactor constraint on every generator.py story | **F2, F3 (SHOULD)** |
| 8 | Scope boundary (no aggregate recomputation) | PASS |
| 9 | Cleanup-mirror completeness | PASS w/ F4 (two-connection detail) |
