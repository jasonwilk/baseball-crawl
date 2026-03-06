# Holistic Pre-Implementation Review: E-051 through E-055

Date: 2026-03-06

## Advisory Scope (Read First)

- Everything in this document is a **suggestion**, not a directive.
- Nothing here should be auto-applied without PM triage.
- The PM should consult its own engineers before deciding whether to include or defer any item.
- The PM should explicitly consult relevant agent experts (at minimum: **software-engineer**, **claude-architect**, and where applicable **api-scout** and **ux-designer**) when evaluating these suggestions.

## Executive Summary

- **E-051** is mostly implementation-ready.
- **E-052** and **E-055** are appropriately `DRAFT`; they still contain contract mismatches that should be resolved before dispatch.
- **E-053** and **E-054** are marked `READY`, but there are cross-epic risks that could cause rework if not aligned first.

## Priority Findings (Cross-Epic + Isolation)

### P1 (Recommended to resolve before starting implementation)

1. **Session pointer model conflicts with default report workflows**  
   - References: `E-052-01 AC-6`, `E-052-04 AC-1/AC-5`, `E-054-01 AC-8`.
   - Problem: `stop.sh` removes `proxy/data/current`, but report tooling defaults to `proxy/data/current/...`. This breaks the stated post-stop review workflow.
   - Suggestion: choose one consistent model (e.g., keep `current` as latest closed session + add separate `active` marker, or keep `current` during closed state and track `status` only in `session.json`).
   - PM consult: software-engineer + claude-architect.

2. **Mobile traffic classification risk can break E-053 and E-054 outcomes**  
   - References: `E-053-01 AC-2/AC-3`, `E-054-01 AC-3`, current `proxy/addons/gc_filter.py` behavior.
   - Problem: epics depend on reliable `ios` detection, but current source detection does not explicitly match `Odyssey/...` UAs. If traffic is classified `unknown`, E-053 drops credentials and E-054 ignores updates.
   - Suggestion: add an explicit source-detection hardening requirement (and tests) as a prerequisite or first task.
   - PM consult: software-engineer + api-scout.

3. **Credential workflow contradiction between E-053 and E-055**  
   - References: `E-053` Non-Goals (refresh flow remains flat-key), `E-053` Success Criteria (no unsuffixed fallback), `E-055-02 AC-2/AC-3/AC-4`.
   - Problem: `bb creds refresh` wraps `refresh_credentials.py` (flat keys), while E-053 removes flat-key support from runtime credential loading.
   - Suggestion: decide one of: (a) make refresh flow profile-scoped, (b) make `bb creds refresh` explicitly web-only and write `_WEB`, or (c) remove/defer that command until aligned.
   - PM consult: software-engineer + claude-architect.

4. **Proxy CLI flag contract mismatch (`--unreviewed`)**  
   - References: `E-052-04` (report flags), `E-055-04 AC-2`.
   - Problem: `bb proxy report` expects `--unreviewed`, but E-052 only defines that filter for endpoints.
   - Suggestion: either add `--unreviewed` to `proxy-report.sh` spec or remove it from `bb proxy report` spec.
   - PM consult: software-engineer.

5. **E-055 packaging/install contract is under-specified and likely brittle**  
   - References: `E-055-01 AC-3/AC-6`, `E-055` wrapper design importing `scripts.*`.
   - Problem: CLI is packaged via `bb` entry point, but wrappers depend on `scripts/` modules and shell scripts; production Dockerfile currently doesn’t include that path contract. Build metadata/tooling assumptions are also incomplete.
   - Suggestion: decide whether CLI is devcontainer-only or production-supported, then lock packaging rules accordingly (including script availability and build-system expectations).
   - PM consult: software-engineer + claude-architect.

### P2 (Should tighten before marking epics fully ready)

1. **`status` command shape is inconsistent inside E-055**  
   - References: `E-055-01 AC-9` (status as sub-app/group), `E-055-06` notes (status as top-level command).
   - Suggestion: pick one command shape and keep all stories consistent.

2. **Duration requirement is contradictory in E-052-05**  
   - References: `E-052-05 AC-1` vs Notes (“skip computed duration if fiddly”).
   - Suggestion: either require duration strictly or make it optional in AC text.

3. **Test file paths are inconsistent with current repo layout**  
   - References: `E-052-02`, `E-053-01`, `E-054-01` file lists mention `tests/test_*.py`, but current proxy tests live under `tests/test_proxy/`.
   - Suggestion: normalize expected test paths to avoid duplicate/fragmented coverage.

4. **Documentation ownership overlaps across epics**  
   - References: `E-053-04`, `E-054-02`, `E-055-07` all modify `CLAUDE.md` commands.
   - Suggestion: consolidate doc updates into one final pass or define precedence to reduce churn/conflicts.

5. **E-055 story-level dependencies don’t reflect external epic interface dependencies**  
   - References: `E-055` epic-level dependency notes vs story dependency tables.
   - Suggestion: explicitly mark stories blocked by required upstream interfaces where needed.

## Isolation Notes by Epic

## E-051 (proxy cert persistence)

- Scope is tight and testable.
- Minor suggestion: codify exact verification commands (fingerprint command/file) in AC text for repeatability.

## E-052 (proxy data lifecycle)

- Strong lifecycle concept, but not yet contract-consistent due to `current` symlink semantics and downstream default behavior.
- Best to resolve pointer/selection semantics before implementation to avoid rework in scripts and docs.

## E-053 (profile-scoped credentials)

- Core direction is sound.
- Main risk is cross-epic operator workflow inconsistency (`refresh_credentials` behavior vs profile-only runtime expectations).

## E-054 (header parity refresh)

- Valuable automation target.
- Depends heavily on accurate source classification and consistent session-path semantics from E-052.

## E-055 (unified CLI)

- Good long-term usability move.
- Should be treated as an interface-consolidation epic after upstream script contracts are frozen.

## Suggested PM Decision Gates (Non-Binding)

1. Resolve the five P1 contract decisions in a short PM + expert sync.
2. Freeze cross-epic interface contracts (session pointers, credential key policy, proxy script flags).
3. Update story ACs/dependencies to reflect those decisions.
4. Then dispatch implementation in the intended order.

## Final Advisory Reminder

All findings above are **suggestions only**. The PM should decide inclusion/deferral after consulting its own engineers and the relevant agent experts.
