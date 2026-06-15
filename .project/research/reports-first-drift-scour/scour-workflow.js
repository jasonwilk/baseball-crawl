export const meta = {
  name: 'reports-first-drift-scour',
  description: 'Find code/schema/doc remnants of the abandoned multi-season/cross-team/multi-surface vision that stray from the reports-first reframe',
  phases: [
    { title: 'Find', detail: 'one finder per remnant class, against ROADMAP non-goals' },
    { title: 'Verify', detail: 'is it LIVE in the used reports path, INERT, or already tracked?' },
    { title: 'Synthesize', detail: 'triage into remnant-live / remnant-inert / already-tracked / not-a-remnant' },
  ],
}

// NOTE: this is the DRIFT scour, not the bug hunt. Yardstick = ROADMAP non-goals/cruft verdicts,
// not correctness. The archetype is season_fallback (a non-goal never traced to its machinery).

const FRAME = `
THE REFRAME (read these FIRST to learn the tightened direction):
  - docs/ROADMAP.md §7 (Explicit Non-Goals — AUTHORITATIVE), §4 (Cruft Inventory & Verdicts),
    §3 (Protected Core — what reports actually depend on at runtime; note the import-coupling caveat),
    §1 (the reframe).
  - The product is: log in → generate a one-off scouting report for a GameChanger public_id → share
    the link. Forward feature: unattended morning-of-game scheduled reports. Everything else
    (dashboard, member-team sync, tracked-opponent management, cross-season, cross-team identity,
    longitudinal/rollup analytics) is a NON-GOAL or quarantine-bound.
  - CLAUDE.md "Current strategic frame" pointer; .claude/rules/data-model.md (season_id semantics,
    "within-report game filter" vs partition key); .claude/rules/scouting-data-flows.md.

THE QUESTION (for every candidate): does this artifact BELONG under reports-first, or is it a
remnant of the old multi-season/cross-team/multi-surface vision? This is about SCOPE FIT, not bugs.

THE ARCHETYPE: season_fallback — a §7 non-goal (cross-season machinery) that survived the reframe
because the non-goals were declared at the FEATURE level but never traced down to the MACHINERY.
You are hunting its siblings.

LIVE vs INERT is the load-bearing distinction:
  - LIVE = reachable from the USED reports path (bb report generate / POST /admin/reports/generate /
    GET /reports/{slug} / the admin reports page) at runtime OR via module-import coupling that
    affects app startup for the reports surface.
  - INERT = the code/table/column exists but is not referenced by the reports path (cheap to leave;
    lower priority; flag but rank below LIVE).
`

const FIND_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'artifact', 'lines', 'remnant_class', 'non_goal_ref', 'claim', 'live_or_inert', 'evidence'],
        properties: {
          title: { type: 'string', description: 'one-line summary' },
          artifact: { type: 'string', description: 'file path (code, migration, doc, rule, or config)' },
          lines: { type: 'string', description: 'line number/range or "whole file"' },
          remnant_class: { type: 'string', enum: ['cross-season', 'cross-team-identity', 'unused-surface-coupling', 'old-vision-flag-or-scope', 'doc-config-drift', 'dead-table-or-column'] },
          non_goal_ref: { type: 'string', description: 'which ROADMAP §7 non-goal / §4 verdict it violates' },
          claim: { type: 'string', description: 'why this strays from reports-first' },
          live_or_inert: { type: 'string', enum: ['LIVE', 'INERT', 'UNSURE'] },
          evidence: { type: 'string', description: 'the call/import/read path that makes it LIVE, or why INERT' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['verdict', 'priority', 'reasoning', 'disposition'],
  properties: {
    verdict: { type: 'string', enum: ['REMNANT_LIVE', 'REMNANT_INERT', 'ALREADY_TRACKED', 'NOT_A_REMNANT'] },
    priority: { type: 'string', enum: ['high', 'medium', 'low', 'n/a'] },
    reasoning: { type: 'string', description: 'the refutation attempt: prove it is reachable-and-straying, OR show it is already-tracked / protected-core / not-a-remnant. Quote the deciding lines.' },
    disposition: { type: 'string', description: 'one-line: ROADMAP §4 row update / new IDEA / fold into D2 scope / curate-the-vision / already covered by <ref> / dismiss' },
  },
}

const LENSES = [
  { key: 'cross-season', label: 'cross-season / multi-season / longitudinal machinery',
    focus: `season_id used as a PARTITION KEY beyond "within-report game filter"; season
selection/comparison; multi-season rollups; recency-tapering across seasons; longitudinal player/team
tracking; the fallback_used computation (loaders/__init__.py) and ALL its consumers; any code that
assumes more than one season's data coexists. §7 says this applies "all the way down to the
machinery." CALIBRATION (already decided, do not re-flag the coach line): the season_fallback
COACH-visible line is fixed by E-236; you are hunting the MACHINERY beneath/around it.` },
  { key: 'cross-team-identity', label: 'cross-team / cross-program player identity',
    focus: `gc_athlete_profile_id population/reads; player tracking across teams/programs;
cross-program blending of one player's record; E-104 remnants; any "same human across teams"
assumption. §7: per-team identity is sufficient; cross-team identity is an explicit non-goal.` },
  { key: 'unused-surface-coupling', label: 'dashboard / member-sync / tracked-opponent coupling in the used path',
    focus: `import-time or runtime coupling from the reports/admin-reports used path into
quarantine-bound surfaces: run_member_sync, opponent discovery (seeder/resolver/opponent_links/
team_opponents), dashboard queries, the admin.py→pipeline.trigger→crawl/load import chain (§3
caveat). Flag what is LIVE-coupled (affects reports startup/runtime) vs merely co-located.` },
  { key: 'old-vision-flag-or-scope', label: 'flags / gates / scope logic encoding the old vision',
    focus: `trust flags, quality gates, or scoping branches whose PREMISE is multi-season or
multi-surface — e.g., gates that over-fire under single-season reports-first, scope filters that
assume a season registry, "degraded" interpretations of what is actually the normal reports-first
case. season_fallback was one; find others.` },
  { key: 'doc-config-drift', label: 'docs / rules / CLAUDE.md / config asserting the old vision',
    focus: `context-layer and docs that still describe the multi-surface vision in ways that would
mislead a future agent into rebuilding non-goals: delivery-parity / pipeline-parity rules referencing
dashboard, key-metrics "Longitudinal" line, VISION.md layers 2-4, teams.yaml, any rule that assumes
member-sync or tracked-opponent surfaces are live. Report as drift even though it is not code.` },
  { key: 'dead-table-or-column', label: 'tables / columns serving only dead capabilities',
    focus: `schema that exists ONLY for de-scoped capabilities (cross-season partitioning, cross-team
identity, member/opponent flows): gc_athlete_profile_id, scouting_runs, crawl_jobs, opponent_links,
user_team_access, team_opponents, multi-season season rows. Classify each as LIVE (reports read/write
it) vs INERT (exists but unread by reports). Per §4, inert tables are cheap — rank low.` },
]

const results = await pipeline(
  LENSES,
  (lens) => agent(
    `You are scouring the baseball-crawl codebase for ONE class of REMNANT that strays from the
reports-first reframe. This is a SCOPE-FIT audit, not a bug hunt. Ground every finding in a real
artifact: cite file + lines, name which ROADMAP §7 non-goal / §4 verdict it violates, and classify
LIVE vs INERT with the specific call/import/read path as evidence.

${FRAME}

YOUR REMNANT CLASS THIS PASS: ${lens.label}
${lens.focus}

Sweep the WHOLE codebase for this one class (src/, migrations/, docs/, .claude/rules/, CLAUDE.md,
config). Read the reframe docs first. Prefer LIVE remnants (reachable from the used reports path) but
record INERT ones too, clearly tagged. If you find nothing real for this class, return an empty
findings array — do not pad. Do NOT re-flag the season_fallback COACH-visible line (E-236 owns it);
DO flag the machinery around/beneath it.`,
    { label: `find:${lens.key}`, phase: 'Find', schema: FIND_SCHEMA, agentType: 'Explore' }
  ),
  (found, lens) => parallel((found?.findings || []).map((f) => () =>
    agent(
      `Adversarially VERIFY this drift finding against the real code/docs. Default posture: SKEPTICAL.
Open the cited artifact at the cited lines and trace it yourself. Two refutation angles:
 (1) REACHABILITY: is it actually LIVE in the used reports path, or INERT (exists but unreferenced)?
     Trace the import/call/read chain. An INERT remnant is still a remnant but lower priority.
 (2) ALREADY-HANDLED: is it already named in ROADMAP §4/§7, an existing IDEA, or D2 scope? Is it
     actually PROTECTED CORE (§3 — e.g., the year-only season-derivation path reports DO need)?
     If protected-core or already-tracked, it is not a new finding.

${FRAME}

FINDING:
- title: ${f.title}
- artifact: ${f.artifact}
- lines: ${f.lines}
- remnant_class: ${f.remnant_class}
- non_goal_ref: ${f.non_goal_ref}
- claim: ${f.claim}
- finder's LIVE/INERT call: ${f.live_or_inert}
- finder's evidence: ${f.evidence}

Verdict:
- REMNANT_LIVE: strays from reports-first AND reachable from the used path. Priority high/medium.
- REMNANT_INERT: strays, but not referenced by reports (cheap to leave). Priority low.
- ALREADY_TRACKED: real, but already in ROADMAP §4/§7 / an IDEA / D2 scope — point to where.
- NOT_A_REMNANT: protected core, or it actually serves reports-first — explain why.
Quote the deciding lines in your reasoning.`,
      { label: `verify:${f.artifact}:${f.lines}`, phase: 'Verify', schema: VERDICT_SCHEMA }
    ).then((v) => ({ ...f, ...v }))
  ))
)

const all = results.flat().filter(Boolean)

phase('Synthesize')
const report = await agent(
  `You are the synthesis step of a REPORTS-FIRST DRIFT scour. Below is the full JSON array of verified
findings (each carries a verdict, priority, reasoning, disposition). Produce a clean operator-facing
report in MARKDOWN that feeds ROADMAP §4/§7 + IDEA files + Epic D2 scope (NOT a new epic by default).

Requirements:
- DROP every NOT_A_REMNANT (but list their titles in a short "Refuted (protected-core / not remnants)"
  appendix so they are not re-raised).
- Put ALREADY_TRACKED findings in their own short section with the §4/§7/IDEA/D2 reference each maps
  to — these confirm coverage, no new action.
- Dedupe findings pointing at the same machinery (merge them).
- Main body = NEW remnants, two sections: "REMNANT — LIVE (reachable from the used reports path)"
  (priority high→low) and "REMNANT — INERT (exists but unreferenced; cheap to leave)".
- For each: artifact:lines, the §7/§4 non-goal it violates, the LIVE/INERT evidence, and the
  disposition (ROADMAP row / new IDEA / D2 scope / curate-the-vision).
- End with an executive summary: counts by verdict, and the single highest-value LIVE remnant.
- Explicitly note this is the CLAUDE-side set; it will be reconciled against an independent Codex
  5.5-xhigh pass (codex-prompt.md). Flag which findings would most benefit from Codex corroboration.

FINDINGS JSON:
${JSON.stringify(all, null, 2)}`,
  { label: 'synthesize', phase: 'Synthesize' }
)

return { totalCandidates: all.length, report }
