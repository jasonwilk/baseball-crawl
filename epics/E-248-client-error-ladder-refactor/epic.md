# E-248: GC API Client Error-Ladder Refactor

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Extract the 401/403/429/5xx error-handling ladder that the **4 live** GC API client verb methods (`get`, `get_public`, `get_paginated`, `post_json`) currently re-implement into a single shared send-with-retries helper, leaving the verbs as thin wrappers, and make future retry-policy changes a one-edit change instead of 4. The two **dead** verbs (`post`, `delete`) are deleted as dead code in E-246 (story E-246-07), not refactored here — so the original "`post()` 5xx gap" dissolves and this epic becomes a **pure, behavior-preserving dedup** (the 4 live verbs already share consistent 5xx handling). Because every crawl flows through this client, the refactor is gated behind dedicated per-status test coverage written first.

## Background & Context
A whole-project code-quality sweep over all of `src/` surfaced 13 maintainability themes. This is the single HIGH-blast-radius theme (H5), isolated into its own epic so it gets focused review and a test-coverage prerequisite. The sweep originally counted 6 client verbs re-implementing near-identical status handling, and flagged `post()` as missing the 5xx backoff the others have.

**Scope fork resolved (Option A — delete the dead verbs).** During Codex spec-review triage, api-scout (gc-uuid-bridge owner) verified by grep that `post()` (`client.py:722`) and `delete()` (`client.py:794`) are **dead verbs**: zero production call sites in `src/`/`scripts/`, exercised only by `tests/test_client.py`. Their sole historical caller was the follow→bridge→unfollow path removed in E-239 and now BANNED per `.claude/rules/gc-uuid-bridge.md`. `post_json("/search")` is the ONLY live-traffic POST and is already 5xx-retried (`/search` is idempotent-in-effect — a read query). The user delegated the scope decision to PM, who chose **Option A** (simple-first / "removing is harder but better" / dead-code-cleanup intent): the two dead verbs are deleted as dead code in **E-246-07** (E-246's deletion domain, fresh-grep-confirmed), and **E-248 refactors only the 4 live verbs** (`get`, `get_public`, `get_paginated`, `post_json`). The "`post()` 5xx gap" dissolves entirely — the only verb lacking 5xx backoff was the now-deleted `post()`; the 4 live verbs already share consistent 5xx handling — so **E-248 is a pure dedup with zero behavior change.**

The report explicitly gates this refactor: "High blast radius — every crawl flows through here; requires per-status test coverage before/after." This epic therefore sequences a characterization-test story first, then the refactor, so the per-status behavior is pinned before any code moves.

**Expert consultation (api-scout, gc-uuid-bridge owner), recorded verbatim:** *"POST /search is the sole live-traffic POST and is idempotent-in-effect (read query); post() and delete() are dead verbs since E-239 removed the follow/unfollow path. Deleting them removes the only 5xx-ladder divergence; the surviving 4-verb ladder consolidation carries no live-traffic or stats-collection risk, and /search's existing retry behavior is unchanged."*

The full triage report is the evidence base. **Cross-epic ordering:** E-246-07 deletes `post()`/`delete()` from `src/gamechanger/client.py` (and their `tests/test_client.py` tests), and E-248 refactors the same file — so **E-246 MUST dispatch before E-248**, so the dead verbs are gone before E-248 pins/refactors the survivors. E-248 shares no files with E-247.

This epic implements no `docs/ROADMAP.md` §5 slice — internal maintainability work, so the Roadmap reference convention does not apply.

## Goals
- Pin each of the 4 live verbs' actual per-status contract with dedicated test coverage before refactoring (the matrix differs per verb — see Technical Notes).
- Extract the shared error/retry ladder into a single helper; reduce each live verb to a thin wrapper.
- Make a future retry-policy change a single-edit change.

## Non-Goals
- **Deleting the dead `post()`/`delete()` verbs — that is E-246-07** (E-246's dead-code domain), not this epic.
- ANY behavior change. With the dead verbs removed, this epic is a pure behavior-preserving dedup — no change to retry counts, backoff timing, status handling, or success-path response shapes.
- Touching any caller of the client — the 4 live verbs keep their existing signatures.
- The other sweep themes (E-246, E-247).

## Success Criteria
- **Stats integrity (HARD GATE — outranks the cleanup):** every crawl's data *collection* flows through this client, so a refactor regression means missing or dropped games — a stats-collection regression. Each of the 4 live verbs' actual per-status contract MUST be covered by tests that pass against the pre-refactor client BEFORE the refactor lands (E-248-01), and the **same tests must pass unchanged after** (E-248-02) — with the dead verbs removed there is NO sanctioned behavior change, so any test that must change to pass means the refactor is not behavior-preserving and is not shipped. See Technical Notes "Stats Integrity — HARD GATE."
- Per-verb characterization tests exist for the 4 live verbs (each verb's real status matrix), and they pass against the current code before the refactor.
- After the refactor, the same tests pass byte-for-byte (no assertion changes), demonstrating behavior is preserved.
- The error/retry ladder is expressed once; each of the 4 live verbs is a thin wrapper.
- `python -m pytest tests/` reports 0 failed in the main checkout after both stories land.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-248-01 | Pin per-status characterization tests for the 4 live verbs | TODO | None | - |
| E-248-02 | Extract shared send-with-retries helper across the 4 live verbs | TODO | E-248-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Stats Integrity — HARD GATE (non-negotiable, outranks the cleanup)
This client is the data-*collection* path for every crawl. A refactor regression here does not corrupt a computed stat — it drops or misses games, which is a stats-collection regression and is equally unacceptable. The protection is the test-first gate below: each live verb's actual per-status contract is pinned by tests that pass against the pre-refactor client BEFORE any code moves, and the extraction must keep them green **with no assertion changes** (with the dead verbs deleted in E-246-07, there is NO sanctioned behavior change here). If the extraction cannot be proven behavior-preserving against those tests, it is **cut/deferred — never shipped on faith.** The full-suite-green closure gate applies as usual. (No `bb report verify-aggregates` step here — this epic touches no aggregate/derivation code, only the HTTP error ladder.)

### Per-verb status matrix (the contracts differ — tests are NOT one uniform set)
The 4 live verbs do not share an identical ladder, so E-248-01 must pin each verb's real contract:
- `get` / `get_paginated` / `post_json`: full ladder — 401-refresh-and-retry / 403 / 429 retry-after / 5xx backoff / unexpected-status raise.
- `get_public`: NO auth path — 200 / 429 / 5xx backoff / unexpected only (it never carries `gc-token`, so no 401-refresh).
The ACs anchor on these public-verb contracts, NOT on the private `_get_with_retries()` helper (which `get()` calls and the refactor will reshape).

### Test-first gate (mandatory)
The refactor (E-248-02) MUST NOT begin until E-248-01's per-verb characterization tests exist and pass against the current, un-refactored client. This is the report's stated prerequisite for this high-blast-radius change. The tests are the proof that the extraction preserves behavior: they pass before (pinning current behavior) and after (proving equivalence) — with the dead verbs removed, there is no behavior-change exception, so the SAME assertions must hold after.

### Cross-epic ordering with E-246-07 (dead-verb deletion)
E-246-07 deletes `post()` (`client.py:722`) and `delete()` (`client.py:794`) plus their `tests/test_client.py` tests. E-248 refactors the same `client.py` and extends the same `test_client.py`. Therefore **E-246 MUST dispatch before E-248** — the dead verbs must be gone before E-248-01 pins the survivors and E-248-02 reshapes the ladder. If E-248 somehow ran first, it would pin/refactor verbs that E-246-07 then deletes (wasted/conflicting work). This is the same E-246-first ordering already required for E-247.

### Evidence base and clean re-read
Verified locations (re-confirm before acting): the 4 live verbs at `src/gamechanger/client.py:233` (`get_paginated`), `:389` (`get`), `:426` (`get_public`), `:611` (`post_json`); private helper `_get_with_retries` at `:512`. The dead verbs (`post` `:722`, `delete` `:794`) are removed by E-246-07 before this epic runs.

### HTTP discipline preserved
The refactor must not change request headers, session behavior, or rate-limiting — the client must continue to present as a normal browser per `.claude/rules/http-discipline.md`. Only the error/retry handling is consolidated.

## Open Questions
All pre-dispatch sign-offs are resolved. None remain open.
- **[RESOLVED] Dead-verb scope fork — Option A (delete).** The user delegated the fork to PM; PM chose Option A: `post()`/`delete()` are deleted as dead code in **E-246-07**, and E-248 refactors only the 4 live verbs. Rationale: simple-first / "removing is harder but better"; the verbs' only caller (follow/unfollow) was removed in E-239 and is now banned; deleting them shrinks the one HIGH-blast-radius refactor (6→4 verbs) and dissolves the only 5xx-gap, making E-248 a zero-behavior-change dedup. The earlier "POST-on-5xx retry" question is **moot** — `post()` is deleted, not refactored.
- **No parity gate here.** This epic touches only the HTTP error ladder — no aggregate/derivation code — so `bb report verify-aggregates` is not a closure gate for E-248 (confirmed with the user). The protection is the test-first per-verb gate plus full-suite-green at closure.

## History
- 2026-06-29: Created (READY). Isolated from the whole-project code-quality sweep as the sole HIGH-blast-radius theme (H5), gated behind a per-status test-coverage prerequisite.
- 2026-06-30: Dead-verb scope fork resolved (user-delegated to PM) — **Option A**: `post()`/`delete()` are dead (api-scout grep-verified: zero production callers, only-caller path removed in E-239 + banned). Deletion moved to E-246-07; E-248 rescoped to the 4 live verbs as a pure zero-behavior-change dedup. Removed the `post()` 5xx-gap behavior change. Recorded api-scout consult. Cross-epic ordering: E-246 before E-248. Applied Codex P2 (anchor tests on public verbs, not `_get_with_retries`) + P3 (artifact). No `verify-aggregates` gate (no aggregate surface).
