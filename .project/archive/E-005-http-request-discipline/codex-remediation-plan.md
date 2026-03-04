# E-005 Codex Spec Review -- Remediation Plan

**Date**: 2026-03-04
**Requested by**: User
**Task type**: Triage

## Expert Consultations

Three experts were consulted before forming this plan.

### 1. general-dev (agent definition review)

The general-dev agent definition reveals key contract expectations:

- general-dev requires **clear, non-conditional ACs** before beginning work. Conditional ACs like "if E-005-03 is done" force the implementer to make a judgment call about whether to implement or skip -- exactly the kind of ambiguity the agent is told to escalate rather than resolve.
- general-dev explicitly references `docs/gamechanger-api.md` as source of truth for API behavior. If the integration guide (`docs/http-integration-guide.md`) contradicts the API spec by showing `Authorization: Bearer`, an implementer following the guide will produce wrong code for GameChanger.
- general-dev follows HTTP Request Discipline and uses `create_session()`. The contract works. The documentation around it does not.

### 2. claude-architect (spec drift in DONE stories)

Assessment of context-layer integrity:

- **DONE stories in ACTIVE epics are not archived.** They are mutable. The project convention is: "archived files are frozen historical records -- do not modify." E-005 is ACTIVE, not archived. Its story files can be corrected.
- **Precedent exists.** E-037 (Codex Review Remediation) retroactively fixed DONE story ACs when implementation diverged from spec. This is an established pattern, not a new one.
- **Stale ACs in DONE stories poison context.** Any agent reading E-005-04 or E-005-05 sees `Authorization: Bearer` as the auth pattern. If those stories are referenced during future work (e.g., E-002 data ingestion), the wrong pattern propagates. This is a context-layer integrity problem.
- **Recommendation:** Fix DONE story files to match implementation reality. Add a History note explaining the correction. Do not change the DONE status -- the work was completed; the spec documentation was wrong.

### 3. api-scout (auth pattern and Chrome version)

Findings from `docs/gamechanger-api.md` (source of truth):

- **Auth pattern is definitively `gc-token`**, not `Authorization: Bearer`. The API spec says: "GameChanger does **not** use `Authorization: Bearer`. Auth is carried in a custom header: `gc-token: <JWT>`."
- **Chrome version**: API captures from 2026-03-04 show Chrome 145. `sec-ch-ua` format also changed (brand ordering differs). `src/http/headers.py` still has Chrome 131 -- 14 major versions behind.
- **Missing headers**: `DNT: 1` and `Referer: https://web.gc.com/` are documented as "Standard Browser Headers" in the API spec. They are not in `BROWSER_HEADERS`.
- **Integration guide**: Should be updated. The guide is the only place where an implementer would be actively misled. The API spec already warns about this mismatch, but the guide itself does not carry the warning.
- **Chrome update timing**: Should happen now, not deferred. 14 major versions behind is well past the ">2 major versions" threshold documented in the guide itself. The `sec-ch-ua` format change means the current headers do not match any real browser in circulation.

---

## Remediation Decisions

### P1 Findings (must fix)

#### Finding 1: E-005-04 AC-6 is conditional and uses wrong auth shape

**Decision: Fix now** -- update E-005-04.md

E-005-04 AC-6 says `"if E-005-03 is done"` and references `Authorization: Bearer <token>`. Both are wrong:

1. The conditional phrasing creates an ambiguous contract. E-005-04 is DONE -- the AC was either tested or skipped. The test file confirms it was skipped (line 224: `# AC-6: SKIP`).
2. The auth shape is wrong. GameChanger uses `gc-token`, not `Authorization: Bearer`.

**Action**: Rewrite AC-6 to be unconditional and use `gc-token`. Since E-005-04 is DONE and AC-6 was explicitly skipped, this becomes a residual gap. The corrected AC-6 test should be absorbed into E-005-03 (the only remaining TODO story), which already covers GameChanger client integration verification.

**Files to update**:
- `/workspaces/baseball-crawl/epics/E-005-http-request-discipline/E-005-04.md` -- rewrite AC-6 to remove conditional, fix auth shape, add History note
- `/workspaces/baseball-crawl/tests/test_http_discipline.py` -- the skip comment (line 224-227) references the wrong auth pattern; update to reflect `gc-token`

#### Finding 2: E-005-04 has a hidden dependency on E-005-03

**Decision: Accept as-is (finding is moot)**

This finding is moot because AC-6 was skipped in the implementation (confirmed by the test file). The conditional AC was designed to be optional -- "if E-005-03 is done, add this test." E-005-03 was not done, so the test was not added. The dependency was soft by design, even if poorly expressed.

The fix for Finding 1 (rewriting AC-6) eliminates the conditional entirely, which resolves this finding transitively.

#### Finding 3: Stale `Authorization: Bearer` in planning artifacts

**Decision: Fix now** -- update three files

The `Authorization: Bearer` pattern appears in:

1. **E-005-04 AC-6** -- covered by Finding 1 fix above
2. **E-005-05 AC-1 and AC-6** -- the story says "working code example of `create_session()` usage including auth injection" and "all code examples use only the actual API." The ACs themselves do not mandate `Authorization: Bearer`, but the story's Technical Approach section (step 5) says "how to add Authorization header." This needs correction.
3. **`docs/http-integration-guide.md`** -- the Quick Start (line 17), Auth Injection Pattern section (lines 88-95), Testing section (lines 137-146), and What Not to Do section (lines 193-198) all show `Authorization: Bearer` as the example pattern.

**Files to update**:
- `/workspaces/baseball-crawl/epics/E-005-http-request-discipline/E-005-05.md` -- update Technical Approach to say "how to add auth headers (gc-token for GameChanger)" instead of "Authorization header". Add History note.
- `/workspaces/baseball-crawl/docs/http-integration-guide.md` -- replace `Authorization: Bearer` examples with `gc-token` examples for GameChanger. Keep a note that the session factory is generic (other integrations may use Bearer), but show the actual GameChanger pattern as the primary example since that is the only current consumer.

### P2 Findings (should fix)

#### Finding 4: E-005-03 appears already satisfied

**Decision: Fix in E-005-03** (bundle into the remaining story dispatch)

The codex review correctly identifies that `client.py` already uses `create_session()`, injects `gc-token`/`gc-device-id`/`gc-app-name`, has no bare `httpx.Client()` calls, and 16 tests pass. E-005-03 was already rewritten as a verification story (not a retrofit) on 2026-03-04. The story description says: "If all acceptance criteria already pass with no code changes, confirm that and report back."

When E-005-03 is dispatched, the implementing agent will verify all ACs, confirm they pass, and report back. This is working as designed. No spec change needed -- just dispatch the story.

**Additional scope for E-005-03 dispatch**: The corrected AC-6 from Finding 1 (integration test verifying GameChanger client sends `gc-token` AND all browser headers) should be added to E-005-03's scope, since E-005-04's AC-6 was skipped and this is the natural place to close that gap.

#### Finding 5: Chrome 131 stale in headers.py

**Decision: Capture as follow-up**

Chrome 131 -> 145 is a 14-version gap, well past the ">2 major versions" threshold. However, this is explicitly listed in the epic's "Gaps Identified During Refinement" section and marked as "outside E-005 scope." The epic notes say: "This should be a small follow-up task."

This should NOT be bundled into E-005-03 (which is a verification story for the client integration, not a header update story). It should be a new story or a small standalone task after E-005 completes.

**Action**: After E-005 completes, create a small follow-up task (or idea) to update `src/http/headers.py` to Chrome 145, add `DNT: 1` and `Referer: https://web.gc.com/`, and update the integration guide's header table. This is a single-file change with a test update.

#### Finding 6: E-005-05 marked DONE but guide uses `Authorization: Bearer`

**Decision: Fix now** -- covered by Finding 3 action

The integration guide fix in Finding 3 resolves this. The guide's examples will be updated to show `gc-token` as the primary pattern.

#### Finding 7: Missing api-scout consultation record

**Decision: Accept as-is**

The epic was created before the structured consultation protocol (E-016, E-020). The api-scout's knowledge is already incorporated into the epic's Technical Notes (Auth Injection Pattern section documents `gc-token` correctly, citing `docs/gamechanger-api.md`). The gap is in the story-level artifacts (E-005-04, E-005-05), not in the epic-level understanding.

Adding a retroactive "consultation completed" note would be revisionist. The real fix is correcting the artifacts that got the auth pattern wrong (Findings 1 and 3).

### P3 Findings

#### Finding 8: E-005-05 DoD subjectivity

**Decision: Accept as-is**

"A second reader can follow the guide without asking clarifying questions" is indeed subjective, but it is also a reasonable documentation quality bar. The guide exists, is well-structured, and covers the required topics. The only concrete problem with the guide is the `Authorization: Bearer` examples (Finding 3), which is being fixed.

Rewriting the DoD for a DONE story has no practical value -- it will not be re-evaluated.

---

## Summary of Actions

### Fix Now (before dispatching E-005-03)

| # | File | Change |
|---|------|--------|
| 1 | `epics/E-005-http-request-discipline/E-005-04.md` | Rewrite AC-6: remove "if E-005-03 is done" conditional, replace `Authorization: Bearer` with `gc-token` + browser headers. Add History note explaining the correction. |
| 2 | `epics/E-005-http-request-discipline/E-005-05.md` | Update Technical Approach step 5 from "Authorization header" to "auth headers (gc-token for GameChanger)". Add History note. |
| 3 | `docs/http-integration-guide.md` | Replace all `Authorization: Bearer` examples with `gc-token` pattern for GameChanger. Add a note that the session factory is generic. Update the header table to note Chrome version is from original capture (131). |
| 4 | `tests/test_http_discipline.py` | Update the AC-6 skip comment (lines 224-227) to reference `gc-token` instead of `Authorization`. |

### Fix in E-005-03 Dispatch

| # | Change |
|---|--------|
| 5 | Add a new AC to E-005-03: "Given `GameChangerClient()` with mocked credentials and mocked HTTP, when `client.get()` is called, then the outgoing request contains `gc-token`, `gc-device-id`, `gc-app-name` AND all 10 required browser headers from `BROWSER_HEADERS`." This closes the gap left by E-005-04's skipped AC-6. |

### Capture as Follow-Up (after E-005 completes)

| # | Item |
|---|------|
| 6 | Chrome 131 -> 145 update in `src/http/headers.py` + add `DNT: 1`, `Referer: https://web.gc.com/`. Update integration guide header table. Single follow-up task. |

### Accept As-Is

| # | Finding | Reason |
|---|---------|--------|
| 7 | Hidden dependency (Finding 2) | Moot -- conditional AC being rewritten eliminates the dependency question. |
| 8 | Missing consultation record (Finding 7) | Retroactive annotation is revisionist. Knowledge is in Technical Notes. |
| 9 | Subjective DoD (Finding 8) | DONE story DoD will not be re-evaluated. No practical value in rewriting. |

---

## Execution Order

1. **PM fixes now** (items 1-4): Update the four files listed above. These are spec/doc corrections, not code changes.
2. **PM updates E-005-03** (item 5): Add the integration-test AC before dispatch.
3. **PM dispatches E-005-03**: The verification story, now with the additional AC covering the E-005-04 gap.
4. **PM completes E-005**: After E-005-03 is DONE, close the epic.
5. **PM creates follow-up**: Chrome version update task (item 6).
