# Codex (5.5-xhigh) prompt — Reports-First Drift Scour

Paste into a Codex session with repo access. Run AFTER E-236 commits. This is the independent
modality that cross-checks the Claude Workflow (`scour-workflow.js`); reconcile both sets afterward.

---

````text
You are auditing the baseball-crawl codebase for REMNANTS that stray from its tightened "reports-first"
direction. This is a SCOPE-FIT audit, not a bug hunt — the yardstick is the reframe's non-goals, not
correctness. Ground every finding in a real artifact (file:line).

## Read first (learn the tightened direction before judging anything)
- docs/ROADMAP.md — §7 Explicit Non-Goals (AUTHORITATIVE), §4 Cruft Inventory & Verdicts, §3 Protected
  Core (what reports actually depend on at runtime — note the import-coupling caveat), §1 The Reframe.
- CLAUDE.md "Current strategic frame" pointer; .claude/rules/data-model.md (season_id as a
  "within-report game filter" vs a partition key); .claude/rules/scouting-data-flows.md.

The product is: log in → generate a one-off scouting report for a GameChanger public_id → share the
link. Forward feature: unattended morning-of-game scheduled reports. NON-GOALS (explicit): cross-team
player identity, cross-season/multi-season/longitudinal/rollup analytics, the member-team sync product,
the dashboard, tracked-opponent management as a surface.

## The question for every candidate
Does this artifact BELONG under reports-first, or is it a REMNANT of the old multi-season /
cross-team / multi-surface vision? ARCHETYPE: `season_fallback` — a non-goal that survived the reframe
because the non-goals were declared at the FEATURE level but never traced down to the MACHINERY. Hunt
its siblings. (Do NOT re-flag the season_fallback coach-visible line — E-236 already fixed it; DO flag
the machinery around/beneath it.)

## Remnant classes to sweep (each is a recurring pattern — sweep the whole repo for each)
1. CROSS-SEASON / LONGITUDINAL machinery: season_id used as a partition key beyond a within-report
   game filter; season selection/comparison; multi-season rollups; recency-tapering across seasons;
   the fallback_used computation (loaders/__init__.py) and ALL its consumers.
2. CROSS-TEAM / CROSS-PROGRAM IDENTITY: gc_athlete_profile_id population/reads; player tracking across
   teams/programs; cross-program blending; E-104 remnants.
3. UNUSED-SURFACE COUPLING: import-time or runtime coupling from the reports / admin-reports used path
   into dashboard, member-sync (run_member_sync), or opponent-discovery code (the
   admin.py → pipeline.trigger → crawl/load chain is the known §3 caveat — find others).
4. OLD-VISION FLAGS / GATES / SCOPE LOGIC: trust flags or quality gates whose premise is multi-season
   or multi-surface; scoping branches that over-fire under single-season reports-first.
5. DOC / RULE / CONFIG DRIFT: context-layer or docs that still assert the old multi-surface vision in
   ways that would mislead a future agent into rebuilding a non-goal (delivery/pipeline-parity rules
   referencing dashboard, key-metrics "Longitudinal" line, VISION.md layers, teams.yaml).
6. DEAD TABLES / COLUMNS: schema existing only for de-scoped capabilities.

## Method (this is what makes findings trustworthy)
- For each candidate: cite file:line, name which ROADMAP §7 non-goal / §4 verdict it violates, and
  classify LIVE vs INERT — LIVE = reachable from the used reports path (bb report generate /
  POST /admin/reports/generate / GET /reports/{slug} / admin reports page) at runtime or via import
  coupling that affects the reports surface's startup; INERT = exists but unreferenced by reports.
  Give the specific call/import/read chain as evidence.
- Then ADVERSARIALLY REFUTE your own finding two ways: (a) reachability — is it actually LIVE or just
  INERT? (b) already-handled — is it already named in ROADMAP §4/§7, an existing IDEA, or D2 scope, or
  is it actually PROTECTED CORE (§3 — e.g., the year-only season-derivation path reports DO need)?
- Classify each surviving finding:
    REMNANT-LIVE (strays + reachable),
    REMNANT-INERT (strays + unreferenced; cheap to leave),
    ALREADY-TRACKED (real but cite the §4/§7/IDEA/D2 reference),
    NOT-A-REMNANT (protected-core or actually serves reports-first — say why).

## Output
Group: "REMNANT — LIVE" (priority high→low), "REMNANT — INERT", "ALREADY-TRACKED (no new action)".
For each: file:line, the non-goal it violates, LIVE/INERT evidence, and a one-line disposition
(ROADMAP §4 row / new IDEA / fold into D2 scope / curate-the-vision). Drop NOT-A-REMNANT to a short
appendix with reasons. End with counts by class and the single highest-value LIVE remnant.
Findings feed ROADMAP §4/§7 + IDEA files + Epic D2 — NOT a new epic by default.
````

---

## Reconciliation (after both modalities run)
- Overlap (both Claude workflow + Codex flag it) → high-confidence remnant; queue the disposition.
- Single-source → trace the cited lines before trusting (the bug hunt proved either modality can
  over-refute or miss).
- Route confirmed dispositions to: ROADMAP §4/§7 edits, new IDEA files, Epic D2 scope notes, and the
  next "curate the vision" session. Do not auto-open an epic.
