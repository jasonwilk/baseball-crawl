# E-051-055 Holistic Review Triage

Date: 2026-03-06
PM: product-manager
Experts consulted: software-engineer, claude-architect, api-scout

## Methodology

The holistic pre-implementation review at `/workspaces/baseball-crawl/E-051-055-holistic-review.md` identified 5 P1 and 5 P2 findings across epics E-051 through E-055. Three domain experts assessed findings within their areas of expertise. This document records the PM's final disposition for each finding, citing the expert input that informed the decision.

---

## P1 Findings

### P1-1: Session pointer model conflicts with default report workflows

**Decision: ACCEPT**

**Expert input:**
- SE (PARTIALLY_VALID): The review's premise that "stop.sh removes current" is false for the *current* code -- `stop.sh` today is just `docker compose down`. However, E-052-01 AC-6 *specifies* that `stop.sh` will remove the symlink, and E-052-04 AC-1/AC-5 default to reading from `proxy/data/current/`. The conflict exists in the *planned* state, not the current code.
- Architect (ACCEPT): Recommends keeping `current` always pointing to the latest session (active or closed). Active/closed status is already tracked in `session.json`. Removing the symlink on stop breaks every downstream consumer's default path.

**PM rationale:** Architect's recommendation is the cleanest contract. The `current` symlink should be a stable pointer; session status belongs in `session.json`. One AC change in E-052-01 resolves the contradiction across E-052-04 and E-054-01 without touching those stories.

**Changes required:**
- `epics/E-052-proxy-data-lifecycle/E-052-01.md`: Amend AC-6 from "removes the `current` symlink after finalizing `session.json`" to "`stop.sh` leaves the `current` symlink in place, pointing to the now-closed session. The symlink is only updated (never removed) by `start.sh`."
- `epics/E-052-proxy-data-lifecycle/epic.md`: Update Technical Notes Session Directory Layout comment: remove "(removed on stop)" from the `current` symlink description. Update the `stop.sh` bullet under Session Metadata to remove symlink removal.

---

### P1-2: Mobile traffic classification risk breaks E-053 and E-054

**Decision: ACCEPT**

**Expert input:**
- Scout/api-scout (VALID -- confirmed bug): Tested `detect_source()` against the real iOS Odyssey UA (`Odyssey/2026.7.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0`). None of the five current `ios_patterns` match. Returns `"unknown"`. Live `proxy/data/header-report.json` confirms the iOS session was classified as `"unknown"`. This means E-053 will drop all mobile credentials (AC-3 triggers instead of AC-2) and E-054 will never update `MOBILE_HEADERS`.
- SE (INVALID -- alignment issue): Correctly noted `Odyssey/` is not in the pattern list but speculated `CFNetwork/` might suffice for actual traffic. Did not have access to real UA data.

**PM rationale:** Scout's evidence is definitive -- they tested the actual UA string from real proxy captures. SE's speculation that `CFNetwork/` might be present was reasonable but disproved by the data. The Odyssey app does NOT include `CFNetwork/` in its UA. This is a prerequisite bug that makes E-053 mobile credential extraction and E-054 mobile header refresh dead on arrival.

**Changes required:**
- `proxy/addons/gc_filter.py`: Add `"odyssey/"` and `"alamofire/"` to `ios_patterns`. One-line fix.
- `tests/test_gc_filter.py` (or equivalent): Add regression test covering the Odyssey UA string.
- **Execution**: Fold into E-053-01 as a new AC-0 ("detect_source returns 'ios' for the Odyssey app UA: `Odyssey/2026.7.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0`") since E-053-01 already modifies the credential extractor code path. Add gc_filter.py to E-053-01 "Files to Create or Modify." Add corresponding test requirement to AC-7.

---

### P1-3: Credential workflow contradiction between E-053 and E-055

**Decision: ACCEPT**

**Expert input:**
- SE (VALID): Confirmed `refresh_credentials.py` writes flat keys via `credential_parser.py`. After E-053 removes flat-key fallback, `bb creds refresh` will write keys that `GameChangerClient` ignores. Operator gets silent success followed by `ConfigurationError`.
- Architect (ACCEPT): Recommends making `refresh_credentials.py` write `_WEB` keys explicitly. The curl-paste path is inherently web-only. Writing `_WEB` suffixed keys is ~5 lines of code. Fold into E-053 since that epic owns the credential key contract change.

**PM rationale:** Both experts agree this is a real contradiction. Architect's approach is cleaner than SE's alternatives: fix it at the source (in E-053, where the key contract changes) rather than patching it downstream (in E-055's wrapper). The refresh path IS web-only, so writing `_WEB` keys is semantically correct.

**Changes required:**
- `epics/E-053-profile-scoped-credentials/epic.md`: Amend Non-Goals from "Making `refresh_credentials.py` profile-aware -- that path remains web-only and writes flat keys" to "`refresh_credentials.py` is updated to write `_WEB` suffixed keys (it is inherently web-only); no `--profile` flag or multi-profile support is added." Update Migration Notes to reflect that `refresh_credentials.py` now writes `_WEB` keys directly.
- `epics/E-053-profile-scoped-credentials/E-053-02.md`: Add AC requiring `credential_parser.py` / `refresh_credentials.py` to write `_WEB` suffixed keys instead of flat keys. Add `scripts/refresh_credentials.py` and `src/gamechanger/credential_parser.py` to "Files to Create or Modify." Add test coverage for the suffix.
- `epics/E-055-unified-cli/E-055-02.md`: No changes needed -- `bb creds refresh` wraps the same logic, which now writes the correct keys.

---

### P1-4: Proxy CLI flag contract mismatch (`--unreviewed`)

**Decision: ACCEPT**

**Expert input:**
- SE (PARTIALLY_VALID): Confirmed E-052-04 defines `--unreviewed` only for `proxy-endpoints.sh`, not `proxy-report.sh`. E-055-04 AC-2 expects `proxy-report.sh` to accept `--unreviewed`. Straightforward spec inconsistency.

**PM rationale:** Header reports are point-in-time snapshots, not aggregatable logs. `--unreviewed` for header reports would mean "show the header report from the most recent unreviewed session" -- which is valid but low-value (the operator almost always wants the latest capture regardless of review status). The simpler fix is to remove `--unreviewed` from E-055-04's `bb proxy report` flags, aligning with E-052-04's deliberate omission.

**Changes required:**
- `epics/E-055-unified-cli/E-055-04.md`: Remove `--unreviewed` from AC-2 (`bb proxy report` flags). Keep `--session` and `--all`.
- `epics/E-055-unified-cli/epic.md`: Update Technical Notes Command Map for `bb proxy report` flags.
- No changes to E-052-04 (the omission was intentional).

---

### P1-5: E-055 packaging/install contract under-specified

**Decision: ACCEPT**

**Expert input:**
- SE (PARTIALLY_VALID): The `pyproject.toml` version gap is already documented in E-055-01. The real risk is that `scripts/` is not copied into the production Docker image, so proxy commands would fail. But proxy analysis commands are explicitly devcontainer-only.
- Architect (ACCEPT): Recommends removing E-055-01 AC-6 entirely (Dockerfile changes). The CLI is an operator tool, not a production runtime component. Installing Typer+Rich+Click in the production image adds attack surface and image size for zero benefit. The production container runs `uvicorn`.

**PM rationale:** Architect is correct. The `bb` CLI is an operator/dev tool. The production container runs the API server. Installing CLI tooling there is waste. If production CLI access is needed later, it becomes a separate story.

**Changes required:**
- `epics/E-055-unified-cli/E-055-01.md`: Remove AC-6 (Dockerfile changes). Remove `Dockerfile` from "Files to Create or Modify."
- `epics/E-055-unified-cli/epic.md`: Add to Non-Goals: "Installing the CLI in the production Docker image (the production container runs the API server only; operator CLI is devcontainer-only)." Remove Dockerfile references from Technical Notes "Entry Point Configuration and Installation" section.

---

## P2 Findings

### P2-1: `status` command shape inconsistent inside E-055

**Decision: ACCEPT**

**Expert input:**
- Architect (ACCEPT): `bb status` is a single command with no subcommands. It should use `@app.command()` on the main app, not `app.add_typer()` which creates a command group. Amend E-055-01 AC-9 to distinguish status from the group-based sub-apps.

**PM rationale:** Architect's Typer analysis is correct. A top-level command is the right pattern for a single command with no children.

**Changes required:**
- `epics/E-055-unified-cli/E-055-01.md`: Amend AC-9 to note that `status.py` defines a standalone function registered via `@app.command()` on the main app (not via `add_typer()`). Update Technical Approach accordingly.

---

### P2-2: Duration requirement contradictory in E-052-05

**Decision: ACCEPT**

**Expert input:** Not explicitly assessed by experts, but the finding is clear from the story text.

**PM rationale:** E-052-05 AC-1 requires duration, while the Notes say "skip computed duration if fiddly." Make duration optional: always print start/stop timestamps; print computed duration if platform supports it.

**Changes required:**
- `epics/E-052-proxy-data-lifecycle/E-052-05.md`: Amend AC-1 to: "...includes: session ID, profile, started_at and stopped_at timestamps, and endpoint count. Duration (human-readable elapsed time) is included if computable; otherwise, the timestamps alone are sufficient."

---

### P2-3: Test file paths inconsistent with repo layout

**Decision: ACCEPT**

**Expert input:**
- SE (PARTIALLY_VALID): Confirmed `tests/test_proxy/` directory exists. Story file lists reference flat `tests/test_*.py` paths instead.

**PM rationale:** Test file placement should follow existing conventions. Proxy addon tests belong in `tests/test_proxy/`.

**Changes required:**
- `epics/E-053-profile-scoped-credentials/E-053-01.md`: Change `tests/test_credential_extractor.py` to `tests/test_proxy/test_credential_extractor.py` in "Files to Create or Modify." Same for `tests/test_credential_parser.py`.
- `epics/E-053-profile-scoped-credentials/epic.md`: Update File Impact Summary test paths.
- `epics/E-054-header-parity-refresh/E-054-01.md`: Change `tests/test_header_capture.py` to `tests/test_proxy/test_header_capture.py` in "Files to Create or Modify."
- E-052-02: Check during refinement (E-052 is still DRAFT).

---

### P2-4: Documentation ownership overlaps across epics

**Decision: REJECT**

**Expert input:**
- Architect (no change needed): Sequential execution handles this. E-055-07 runs last and restructures everything. Even if E-053-04 and E-054-02 produce messy intermediate states, E-055-07 cleans it up.

**PM rationale:** Agree with architect. The execution order (E-053/E-054 before E-055) is already enforced at the epic level. No spec changes needed.

---

### P2-5: Cross-epic dependencies at story level

**Decision: REJECT**

**Expert input:**
- Architect (no change needed): Epic-level dependency is sufficient. Story-level cross-epic deps are brittle and add maintenance burden. The PM enforces epic completion order at dispatch time.

**PM rationale:** Agree with architect. Epic-level ordering is the right abstraction.

---

## Expert Disagreement Log

**P1-2**: SE assessed as INVALID (speculated `CFNetwork/` might cover iOS traffic). Scout assessed as VALID with proof (tested real Odyssey UA against `detect_source()`, confirmed `"unknown"` return, verified in live proxy data). PM sided with scout -- empirical evidence from actual proxy captures overrides speculation about what iOS UAs might contain. The Odyssey app UA does NOT include `CFNetwork/`, `GameChanger/`, `Darwin/`, `iPhone`, or `iPad`.

**P1-5**: The prior (pre-expert) triage REJECTED this finding, assuming the Dockerfile install was well-specified. Architect's assessment changed the disposition to ACCEPT by identifying that the CLI should not be in the production image at all -- a design insight the PM had missed.

---

## Summary Table

| Finding | Severity | Decision | Scope of Change |
|---------|----------|----------|-----------------|
| P1-1 Session pointer | P1 | ACCEPT | E-052-01 AC-6 + epic Technical Notes |
| P1-2 Mobile UA classification | P1 | ACCEPT | gc_filter.py fix + fold into E-053-01 |
| P1-3 Credential workflow | P1 | ACCEPT | E-053 Non-Goals + E-053-02 AC + Migration Notes |
| P1-4 `--unreviewed` mismatch | P1 | ACCEPT | E-055-04 AC-2 (remove flag) |
| P1-5 CLI packaging | P1 | ACCEPT | E-055-01 AC-6 removal + E-055 Non-Goal |
| P2-1 Status command shape | P2 | ACCEPT | E-055-01 AC-9 wording |
| P2-2 Duration requirement | P2 | ACCEPT | E-052-05 AC-1 wording |
| P2-3 Test file paths | P2 | ACCEPT | E-053-01, E-054-01 file paths |
| P2-4 Doc ownership overlaps | P2 | REJECT | No changes needed |
| P2-5 Cross-epic story deps | P2 | REJECT | No changes needed |

---

## Changes by Epic

### E-051 (READY -- no changes)
Unaffected by any finding. Can be dispatched independently.

### E-052 (DRAFT -- apply during refinement)
1. E-052-01 AC-6: Keep `current` symlink after stop (P1-1)
2. E-052 epic Technical Notes: Remove "(removed on stop)" from session layout (P1-1)
3. E-052-05 AC-1: Make duration optional (P2-2)
4. E-052-02: Check test file paths during refinement (P2-3)

### E-053 (READY -- targeted fixes before dispatch)
5. E-053-01: Add AC-0 for Odyssey UA detection fix in gc_filter.py (P1-2)
6. E-053-01: Add gc_filter.py + test file to "Files to Create or Modify" (P1-2)
7. E-053-01: Fix test paths to `tests/test_proxy/` (P2-3)
8. E-053-02: Add AC for `refresh_credentials.py` writing `_WEB` keys (P1-3)
9. E-053 epic Non-Goals: Amend refresh_credentials.py language (P1-3)
10. E-053 epic Migration Notes: Update for `_WEB` key writing (P1-3)
11. E-053 epic File Impact Summary: Fix test paths (P2-3)

### E-054 (READY -- targeted fixes before dispatch)
12. E-054-01: Fix test paths to `tests/test_proxy/` (P2-3)

### E-055 (DRAFT -- apply during refinement)
13. E-055-01 AC-6: Remove Dockerfile changes (P1-5)
14. E-055-01 AC-9: Clarify status as top-level command (P2-1)
15. E-055-04 AC-2: Remove `--unreviewed` from `bb proxy report` (P1-4)
16. E-055 epic Non-Goals: Add "CLI not in production image" (P1-5)
17. E-055 epic Technical Notes: Remove Dockerfile refs, clarify status pattern (P1-5, P2-1)

## Next Steps

1. Apply the 17 changes listed above to the affected epic and story files.
2. E-051 is unaffected and can be dispatched immediately.
3. E-053 and E-054 need targeted fixes (items 5-12 above) before dispatch.
4. E-052 and E-055 remain DRAFT; changes will be incorporated during refinement.
