# E-262-07: Admin Docs Hygiene

## Epic
[E-262: Post-Program Housekeeping](epic.md)

## Status
`TODO`

## Description
After this story is complete, four admin-doc items are cleared: stale local port references are corrected, the architecture.md historical schema changelog is reconciled to real migration files, the operations.md credential-recovery recipe is collapsed to the minimal current steps, and the Step 1d closure-smoke procedure in `production-deployment.md` is synced to the settled story-06 skill text (so the operator-facing procedure and the skill agree).

## Context
Three docs-writer fold-in ideas over `docs/admin/`, plus one propagation sync surfaced by Codex spec review (P1):
- **IDEA-010 (port map) — LIKELY ALREADY FIXED; verify-only (docs-writer review):** the idea (2026-03-05) cited a stale "Traefik dashboard at `localhost:8080`" reference in `docs/admin/getting-started.md`. docs-writer confirmed the live file (updated 2026-07-08) already shows the correct map (`:59-61`: app direct `8001`, Traefik `8000`, Traefik dashboard `8180`) and every `8080` hit in `docs/admin/` is correctly mitmproxy-related. So this is a VERIFY-ONLY item — confirm no stale Traefik-`8080` reference remains. Do NOT add mitmproxy `8080`/mitmweb `8081` rows to getting-started.md's Access Points table: those correctly live in `mitmproxy-guide.md`, and the CLAUDE.md Proxy Boundary rule deliberately keeps Mac-host proxy details out of the Docker-service port table — forcing them in would blend two network models the docs correctly separate. (The originally-co-flagged `docs/agent-browsability-workflow.md` was deleted in E-255-02 — out of scope.)
- **IDEA-105 (architecture.md schema changelog):** the "Schema Changes" changelog in `docs/admin/architecture.md` still cites pre-E-220 migration numbers that no longer map to real `migrations/*.sql` files (E-220 squashed prior migrations into `001_initial_schema.sql`; real migrations 002–010 reused some numbers). E-255-05 added a clarifying note + fixed one false claim but did not rewrite the historical changelog. Reconcile the historical entries to the real migration files (the operations.md live "Schema Migrations" table, real 001–010, is the canonical current-state reference — this is only the architecture.md HISTORICAL changelog).
- **IDEA-111 (operations.md creds-recovery recipe) — real, but the `:884` anchor is DEAD (docs-writer review):** the credential-recovery recipe predates the current `bb creds check` (itself an end-to-end `/me/user` probe, confirmed in `src/cli/creds.py`). The cited `operations.md:884` is stale — live `:884` is an unrelated `docker compose ps` line. The actual recipe now lives at `docs/admin/operations.md:717-746` under `## Credential Rotation` → `### GameChanger API Tokens` (with `scripts/smoke_test.py` at `:737`, and a second recovery mention at `:837`). Locate the section by HEADING/CONTENT, not the dead `:884` line ref. Review and collapse to the minimal current steps, using `bb creds check` as the primary liveness probe. (IDEA-109 smoke_test retarget is a SEPARATE out-of-scope idea; do this collapse standalone.)
- **Codex P1 (production-deployment.md Step 1d sync — propagation):** `docs/admin/production-deployment.md:503` carries a `## Closure Runtime Smoke (Step 1d)` section that MIRRORS the skill's Step 1d procedure, and `implement/SKILL.md:490` explicitly DEFERS to it as the authoritative operator-facing "full smoke procedure." Story 06 changes the skill's Step 1d text (IDEA-122 + IDEA-123); this doc must be synced to match, or the operator-facing source stays stale. Concretely: the preflight `credentials live (bb creds check)` at `:536` becomes `bb creds check --profile web`; the `.smoke-fixture` section (`:512-529`) gains the terminal-fixture REQUIREMENT for the `generate` target (a completed-season GC team page with high play-by-play coverage) plus the one-time bootstrap re-snapshot + plays-coverage check. Requirement/description language ONLY — no real GC identifiers in the doc (the actual id stays in the gitignored `.smoke-fixture`). **This sub-item is `Blocked by: E-262-06`** so the doc mirrors the settled skill text rather than pre-empting it.

## Acceptance Criteria
- [ ] **AC-1**: Given `docs/admin/getting-started.md`, when its local URL/port references are verified, then no stale Traefik-port reference (e.g. Traefik dashboard labeled `8080`) exists — the map reads app direct `8001`, Traefik `8000`, Traefik dashboard `8180`. A documented verify-only result (no edit needed) satisfies this AC. Mitmproxy/mitmweb port rows are NOT added to getting-started.md (they belong in `mitmproxy-guide.md` per the Proxy Boundary rule).
- [ ] **AC-2**: Given the "Schema Changes" changelog in `docs/admin/architecture.md`, when its entries are read, then each references a resolvable state (either the consolidated `001_initial_schema.sql` with a pre-E-220-numbering note, or discrete real 002–010 entries) with no phantom migration numbers that map to no file.
- [ ] **AC-3**: Given the credential-recovery recipe in `docs/admin/operations.md` (located by its `## Credential Rotation` → `### GameChanger API Tokens` heading near `:717-746`, NOT the dead `:884` ref), when it is read, then it reflects the current `bb creds check` end-to-end probe as the primary liveness step and carries no redundant/superseded steps.
- [ ] **AC-4 (Codex P1, Blocked by E-262-06)**: Given the `## Closure Runtime Smoke (Step 1d)` section in `docs/admin/production-deployment.md`, when it is read after story 06 lands, then it agrees with the settled skill text — the preflight names `bb creds check --profile web` (not bare `bb creds check`), and the `.smoke-fixture` `generate`-target description carries the terminal-fixture requirement (completed-season GC team page, high play-by-play coverage), the one-time bootstrap re-snapshot, and the plays-coverage check — with NO real GC identifiers (requirement/description language only).

## Technical Approach
Docs-only edits across `docs/admin/getting-started.md`, `docs/admin/architecture.md`, `docs/admin/operations.md`, and `docs/admin/production-deployment.md`. Confirm the current canonical port map and the real migration file set (`ls migrations/`) before editing. Apply the doc-sweep discipline (`.claude/rules/doc-sweep.md`) for the changelog reconciliation. The changelog target shape (rewrite-in-place vs collapse-pre-E-220-to-one-line) is a docs-writer call per IDEA-105. For AC-4, mirror the exact settled Step 1d text that story 06 lands in `implement/SKILL.md` (read the merged skill text, do not re-derive) — the two must agree; keep real GC identifiers out of the doc.

## Dependencies
- **Blocked by**: E-262-06 (AC-4 only — the production-deployment.md Step 1d sync mirrors the skill text story 06 settles; AC-1/2/3 are independent). Because stories dispatch serially, story 07 running after story 06 satisfies this.
- **Blocks**: None

## Files to Create or Modify
- `docs/admin/getting-started.md`
- `docs/admin/architecture.md`
- `docs/admin/operations.md`
- `docs/admin/production-deployment.md` (AC-4, Step 1d sync)

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Sources: IDEA-010, 105, 111, plus Codex P1 (production-deployment.md Step 1d sync). All docs/admin, one agent (docs-writer). Separated from docs/api cleanup (story 09) so each lands with one agent and one doc tree. (Story 08, docs/coaching, was DROPPED after review — premise resolved by E-239.)

**Codex spec review P1 incorporated (2026-07-12):** the settled story-06 Step 1d fix (IDEA-122 `--profile web` + IDEA-123 terminal-fixture mechanism) is mirrored in `docs/admin/production-deployment.md:503`, to which `implement/SKILL.md:490` defers as the authoritative operator-facing procedure. Landed here (docs-writer, admin docs) rather than in CA's story 06 to keep one-agent-per-story; gated `Blocked by: E-262-06` so the doc mirrors the merged skill text. Landing CONFIRMED by docs-writer (2026-07-12) — docs-writer verified both ends (skill defers to the doc; the doc's `:503-551` carries the exact staleness) and confirmed the AC-4 scoping and the `Blocked by: E-262-06` gate.

**docs-writer holistic review (2026-07-12) incorporated:** IDEA-105 (architecture.md changelog) confirmed real + current (still cites Migration 014/009/007/006 that don't map to files) — no story change. IDEA-010 narrowed to verify-only (getting-started.md already correct; mitmproxy-port clause dropped to avoid blending network models). IDEA-111 anchor corrected from the dead `:884` to the real `## Credential Rotation` section (~`:717-746`).
